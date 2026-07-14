"""AI nutrition estimation — photo/text in, validated numbers out (F1 + E2).

The flow, in plain language:

  1. Build a request for Claude (Anthropic's vision model): the meal photo
     (if any) + the user's text (if any) + our instructions.
  2. Ask for STRUCTURED OUTPUT: we hand the API a JSON schema and it
     guarantees the reply is valid JSON matching it — no "hopefully the
     model returns JSON" parsing games.
  3. Validate the reply into an Estimate object anyway (defense in depth —
     the schema guarantees shape, Pydantic re-checks it and gives us typed
     access).

Two modes, one prompt (decision E2): the model itself distinguishes a plate
of food (kind="estimate" — it guesses) from a nutrition facts panel
(kind="label" — it transcribes the printed values). kind="unknown" means it
couldn't identify food at all, and the wizard falls back to manual entry.

The image is passed to the API in memory and NEVER stored (privacy decision
in ARCHITECTURE.md). The API key is read from the environment (backend/.env)
— it must never appear in code or in the frontend.
"""

import base64
import logging
import os
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Which Claude model to use. Overridable via .env so we can trade
# cost/quality without a code change. claude-opus-4-8 is Anthropic's
# current recommended default.
MODEL = os.environ.get("ESTIMATE_MODEL", "claude-opus-4-8")


class EstimationError(Exception):
    """Raised when we can't get a usable estimate (API down, bad key,
    malformed reply). The router turns this into a clean HTTP error the
    frontend can show — the raw exception never reaches the user."""


# --- What the model must return -------------------------------------------------


class LabelBasis(BaseModel):
    """For label scans only: what the printed numbers refer to, so the
    wizard can ask 'how much did you have?' and scale correctly."""

    per: Literal["100g", "serving", "package"]
    serving_size_g: Optional[float] = None  # grams per serving, if printed


class Ingredient(BaseModel):
    """One component of the meal with its share of the calories (D4).

    Exists so the total is AUDITABLE: the user can see '350g seasoned rice
    → 520 kcal' and challenge the one line that looks inflated, instead of
    arguing with a single opaque number (PO feedback: totals felt high)."""

    name: str  # e.g. "seasoned rice (~350g)"
    calories: float


class Estimate(BaseModel):
    """The structured estimate as the frontend receives it."""

    kind: Literal["estimate", "label", "unknown"]
    description: str
    # The model's visible working — portion size, preparation, brand —
    # shown on the estimate card so the user knows what to correct.
    assumptions: list[str]
    # Per-component calorie breakdown (D4). Empty for label scans (the
    # printed total needs no justification) and for kind=unknown.
    items: list[Ingredient]
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    # null unless kind == "label"
    label_basis: Optional[LabelBasis] = None
    confidence: Literal["low", "medium", "high"]


# The same shape as a JSON Schema — this is what the API *enforces* on the
# model's output. Structured outputs require additionalProperties: false
# and every property listed in "required".
ESTIMATE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["estimate", "label", "unknown"],
            "description": "estimate = prepared food judged by eye; "
            "label = values transcribed from a nutrition facts panel; "
            "unknown = no food or label identifiable in the input",
        },
        "description": {
            "type": "string",
            "description": "Short human-readable summary of the food/product",
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Assumptions made: portion size, cooking method, "
            "brand. Empty for exact label transcriptions.",
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The component with its estimated "
                        "portion, e.g. 'seasoned rice (~350g)'",
                    },
                    "calories": {"type": "number"},
                },
                "required": ["name", "calories"],
                "additionalProperties": False,
            },
            "description": "Per-component calorie breakdown for kind="
            "estimate. The components' calories MUST sum to the total "
            "calories. Empty array for label/unknown.",
        },
        "calories": {"type": "number"},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "label_basis": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "per": {"type": "string", "enum": ["100g", "serving", "package"]},
                        "serving_size_g": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    },
                    "required": ["per", "serving_size_g"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ],
            "description": "For kind=label only: what the numbers refer to",
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": [
        "kind", "description", "assumptions", "items", "calories",
        "protein_g", "carbs_g", "fat_g", "label_basis", "confidence",
    ],
    "additionalProperties": False,
}

# The instructions sent with every request. Kept as one constant so the
# S1 spike findings can tune it in exactly one place.
SYSTEM_PROMPT = """You are the nutrition estimator inside a calorie-tracking app.
The user sends a photo and/or a text description of what they are eating.

Decide which case applies:
1. A nutrition facts panel / ingredient label on a packaged product or drink
   is clearly readable -> kind="label". TRANSCRIBE the printed values exactly
   as stated for the basis printed on the label (per 100g, per serving, or
   per package) and report that basis in label_basis. Do not scale them.
2. Prepared/plated food (or a text description of a meal) -> kind="estimate".
   Work BOTTOM-UP: break the meal into its visible components, estimate each
   component's portion and calories separately in items (name the portion in
   the item, e.g. "seasoned rice (~350g)"), and make the total calories
   equal the SUM of the items — never a round number picked first and
   justified later. Estimate protein/carbs/fat for the whole portion. List
   every assumption you make (portion weight, cooking oil, hidden
   ingredients) in assumptions.
3. Neither food nor a label is identifiable -> kind="unknown", zeros, empty items.

Be realistic, not padded: restaurant and hawker food is often oilier than
home cooking, but do NOT add safety margin on top of each component — the
per-component estimates should each be your honest middle guess, so the sum
is realistic rather than worst-case. When torn between two portion sizes,
pick the one the photo actually supports and state it as an assumption. If
the user's text contradicts the photo, trust the text (they know what they
ate)."""


def estimate_nutrition(
    image_bytes: Optional[bytes],
    image_media_type: Optional[str],
    text: Optional[str],
) -> Estimate:
    """Call the vision model and return a validated Estimate.

    Inputs: raw image bytes + their MIME type (both None for text-only), and
    the user's text description (None for photo-only). At least one of
    image/text must be present — the router enforces that before calling us.
    Returns an Estimate. Raises EstimationError with a human-readable
    message when anything goes wrong.
    """
    # Build the user message content blocks. Order matters a little:
    # image first, then text, is the pattern Anthropic recommends.
    content: list[dict] = []
    if image_bytes is not None:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type,
                    # The API wants base64 TEXT, not raw bytes.
                    "data": base64.standard_b64encode(image_bytes).decode("utf-8"),
                },
            }
        )
    content.append(
        {
            "type": "text",
            "text": text.strip()
            if text and text.strip()
            else "No text description provided — analyze the image.",
        }
    )

    # The client reads ANTHROPIC_API_KEY from the environment automatically.
    # Constructed per-call (cheap) so a key added to .env after startup is
    # picked up on server reload without extra plumbing.
    client = anthropic.Anthropic()

    # App-event log (D2): every AI call is money + latency — always logged.
    logger.info(
        "AI estimate requested: model=%s image=%s text=%s",
        MODEL, image_bytes is not None, bool(text and text.strip()),
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,  # the JSON reply is small; no need for more
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            # Structured outputs: the API guarantees the reply text is valid
            # JSON conforming to our schema — the key reliability feature here.
            output_config={
                "format": {"type": "json_schema", "schema": ESTIMATE_SCHEMA}
            },
        )
    except anthropic.AuthenticationError as e:
        raise EstimationError(
            "AI service rejected the API key — check ANTHROPIC_API_KEY in backend/.env"
        ) from e
    except anthropic.RateLimitError as e:
        raise EstimationError(
            "AI service is rate-limited right now — wait a moment and try again"
        ) from e
    except anthropic.APIConnectionError as e:
        raise EstimationError(
            "Could not reach the AI service — check the internet connection"
        ) from e
    except anthropic.APIStatusError as e:
        raise EstimationError(f"AI service error ({e.status_code}) — try again") from e

    # A refusal (safety systems declined) has no usable content.
    if response.stop_reason == "refusal":
        raise EstimationError("The AI declined to analyze this input — try another photo")

    # Extract the text block and validate it into our typed model.
    raw = next((b.text for b in response.content if b.type == "text"), None)
    if raw is None:
        raise EstimationError("AI returned no result — try again")
    try:
        result = Estimate.model_validate_json(raw)
        logger.info(
            "AI estimate ok: kind=%s kcal=%s confidence=%s",
            result.kind, result.calories, result.confidence,
        )
        return result
    except ValidationError as e:
        # Should be impossible with structured outputs, but never trust,
        # always verify — a malformed reply must not reach the tracker.
        raise EstimationError("AI returned an unreadable result — try again") from e
