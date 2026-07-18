"""Tests for the Telegram bot's pure rendering (T6.2).

The polling loop and Telegram HTTP calls need a live bot to exercise, so they
are verified by hand. What we CAN test cheaply and meaningfully is the pure
function that turns an Estimate into the chat 'card' text — no network, no DB.
"""

from app.services.estimation import Estimate, Ingredient
from app.telegram_bot import _format_estimate


def _estimate(**overrides) -> Estimate:
    """A valid food Estimate, tweakable per test."""
    base = dict(
        kind="estimate",
        description="Laksa",
        assumptions=["Standard hawker portion"],
        items=[Ingredient(name="rice noodles (~200g)", calories=260),
               Ingredient(name="coconut broth", calories=300)],
        calories=560, protein_g=25, carbs_g=55, fat_g=32,
        label_basis=None, confidence="medium",
    )
    base.update(overrides)
    return Estimate(**base)


def test_estimate_card_lists_ingredients_and_total():
    """A food estimate shows the per-item breakdown and the macro total."""
    text = _format_estimate(_estimate())

    assert "🤖 AI estimate" in text
    assert "rice noodles (~200g): 260 kcal" in text  # the breakdown line
    assert "Total: 560 kcal" in text
    assert "Confidence: medium" in text


def test_label_card_shows_basis_not_breakdown():
    """A label scan is marked as read-from-label and states its basis; label
    scans carry no per-ingredient breakdown."""
    from app.services.estimation import LabelBasis

    text = _format_estimate(_estimate(
        kind="label", items=[], assumptions=[],
        label_basis=LabelBasis(per="serving", serving_size_g=250),
    ))

    assert "🏷️ Read from label" in text
    assert "per serving" in text
    assert "kcal" in text  # still reports the total
