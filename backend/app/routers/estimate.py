"""Estimate API — the wizard's step 1→2 bridge (F1, incl. E2 label scans).

One endpoint: POST /estimate. Unlike the other routers this one accepts
multipart/form-data (how browsers send file uploads), not JSON — a photo
can't ride inside a JSON body without ugly encoding.

Nothing here writes to the database. The wizard shows the estimate, the
user edits and confirms, and THEN the frontend calls POST /entries — the
single write path. The image bytes live only in this request's memory and
are garbage-collected when it ends (photos-are-discarded decision).
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.estimation import Estimate, EstimationError, estimate_nutrition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/estimate", tags=["estimate"])

# Image formats Claude's vision API accepts.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Phone photos can be huge; the API caps request size anyway, and 10 MB is
# far more than needed to read a plate or a label.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("")
async def estimate(
    # File(None) / Form(None) = both fields optional in the multipart body.
    # `async` + `await image.read()`: file uploads arrive in chunks, and
    # reading them is I/O the server shouldn't block other requests on.
    image: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
) -> Estimate:
    """Estimate nutrition from a meal photo and/or text description.

    Returns the AI's structured estimate (kind, description, assumptions,
    macros, confidence — see services/estimation.py). 400 if neither input
    was provided, 502 if the AI call fails.
    """
    has_text = bool(text and text.strip())
    if image is None and not has_text:
        raise HTTPException(
            status_code=400,
            detail="Provide a photo, a text description, or both.",
        )

    image_bytes: Optional[bytes] = None
    media_type: Optional[str] = None
    if image is not None:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image type '{image.content_type}' — "
                "use JPEG, PNG, GIF or WebP.",
            )
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image too large (max 10 MB).")
        media_type = image.content_type

    try:
        # The service call is synchronous (the SDK handles its own HTTP);
        # image_bytes is not stored anywhere — it dies with this request.
        return estimate_nutrition(image_bytes, media_type, text)
    except EstimationError as e:
        # App-event log (D2): AI failures are the first thing to look for
        # when the wizard misbehaves in production.
        logger.warning("AI estimate failed: %s", e)
        # 502 = "bad gateway": our server is fine, the upstream AI call
        # failed. The message is already user-friendly by design.
        raise HTTPException(status_code=502, detail=str(e))
