"""Tests for the /estimate endpoint and the label-source schema change.

IMPORTANT TESTING IDEA: these tests never call the real AI API (that would
need a key, cost money, and make tests slow/flaky). Instead we monkeypatch
`estimate_nutrition` — the function the router calls — with a fake that
returns a canned Estimate. The endpoint's own logic (input validation,
error mapping, response shape) is what's under test, not Claude itself.
"""

import pytest

import app.routers.estimate as estimate_router
from app.services.estimation import Estimate, EstimationError
from tests.conftest import VALID_ENTRY

# A canned successful estimate the fake model returns.
FAKE_ESTIMATE = Estimate(
    kind="estimate",
    description="chicken rice, large plate",
    assumptions=["~450g portion", "cooked with rendered chicken fat"],
    calories=702,
    protein_g=33,
    carbs_g=80,
    fat_g=28,
    label_basis=None,
    confidence="medium",
)

# A tiny valid PNG (1x1 transparent pixel) for upload tests — the fake
# doesn't look at it, but the endpoint's type/size checks do run.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63640000000600023081d02f0000000049454e44ae426082"
)


@pytest.fixture()
def fake_model(monkeypatch):
    """Replace the real AI call with a controllable fake.

    Returns a dict the test can inspect (what inputs the fake received)
    and mutate (what it should return or raise).
    """
    state = {"received": None, "result": FAKE_ESTIMATE, "error": None}

    def fake_estimate_nutrition(image_bytes, media_type, text):
        state["received"] = {
            "image_bytes": image_bytes,
            "media_type": media_type,
            "text": text,
        }
        if state["error"]:
            raise state["error"]
        return state["result"]

    # Patch the name the ROUTER uses (it did `from ... import
    # estimate_nutrition`, so the router module holds its own reference).
    monkeypatch.setattr(estimate_router, "estimate_nutrition", fake_estimate_nutrition)
    return state


# --- Input validation (no AI involved) -----------------------------------------


def test_neither_photo_nor_text_is_rejected(client, fake_model):
    response = client.post("/estimate")
    assert response.status_code == 400
    assert fake_model["received"] is None  # never reached the AI


def test_wrong_file_type_is_rejected(client, fake_model):
    response = client.post(
        "/estimate",
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported image type" in response.json()["detail"]


# --- Happy paths -----------------------------------------------------------------


def test_text_only_estimate(client, fake_model):
    response = client.post("/estimate", data={"text": "chicken rice, large"})
    assert response.status_code == 200

    body = response.json()
    assert body["kind"] == "estimate"
    assert body["calories"] == 702
    assert body["assumptions"]  # the model's working is exposed to the UI

    # The service received the text and no image.
    assert fake_model["received"]["text"] == "chicken rice, large"
    assert fake_model["received"]["image_bytes"] is None


def test_photo_upload_reaches_the_service(client, fake_model):
    response = client.post(
        "/estimate",
        files={"image": ("meal.png", TINY_PNG, "image/png")},
    )
    assert response.status_code == 200
    assert fake_model["received"]["image_bytes"] == TINY_PNG
    assert fake_model["received"]["media_type"] == "image/png"


def test_label_scan_shape_passes_through(client, fake_model):
    """A label transcription carries its basis so the UI can do portion math."""
    fake_model["result"] = Estimate(
        kind="label",
        description="Oat drink, 1L carton",
        assumptions=[],
        calories=46,
        protein_g=1.0,
        carbs_g=6.6,
        fat_g=1.5,
        label_basis={"per": "100g", "serving_size_g": None},
        confidence="high",
    )
    body = client.post("/estimate", data={"text": "oat milk carton"}).json()
    assert body["kind"] == "label"
    assert body["label_basis"]["per"] == "100g"


def test_unknown_kind_passes_through(client, fake_model):
    """'Not food' is a normal answer, not an error — the wizard uses it to
    fall back to manual entry (spec F1 acceptance criterion)."""
    fake_model["result"] = Estimate(
        kind="unknown", description="No food identified", assumptions=[],
        calories=0, protein_g=0, carbs_g=0, fat_g=0,
        label_basis=None, confidence="low",
    )
    body = client.post("/estimate", data={"text": "asdfghjkl"}).json()
    assert body["kind"] == "unknown"


# --- Failure path (T3.4) ---------------------------------------------------------


def test_ai_failure_becomes_clean_502(client, fake_model):
    fake_model["error"] = EstimationError("AI service is rate-limited right now")
    response = client.post("/estimate", data={"text": "chicken rice"})
    assert response.status_code == 502
    assert "rate-limited" in response.json()["detail"]


# --- Migration 002: the 'label' source (E2) --------------------------------------


def test_entries_accept_ai_and_label_sources(client):
    """After migration 002 the wizard can save with source 'ai' or 'label'."""
    for source in ("manual", "ai", "label"):
        response = client.post("/entries", json={**VALID_ENTRY, "source": source})
        assert response.status_code == 201, source
        assert response.json()["source"] == source


def test_entries_reject_unknown_source(client):
    response = client.post("/entries", json={**VALID_ENTRY, "source": "guess"})
    assert response.status_code == 422  # Pydantic's Literal check fires
