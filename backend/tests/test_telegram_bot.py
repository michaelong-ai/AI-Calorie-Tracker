"""Tests for the Telegram bot's rendering (T6.2) and slash commands (D8).

The polling loop and Telegram HTTP calls need a live bot to exercise, so they
are verified by hand. What we CAN test cheaply and meaningfully is the pure
functions that build the chat text — the estimate card, and the /today
summary (which reads the database through the same helpers the web app uses).
"""

from app.services.estimation import Estimate, Ingredient
from app.telegram_bot import _format_day, _format_estimate, _macro_line
from tests.conftest import VALID_ENTRY


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


# --- /today-style day summaries (D8) -------------------------------------------


def test_macro_line_shows_remaining_and_over():
    """A macro row counts down to the target, and flips to 'over' past it."""
    assert _macro_line("Protein", 88, 144, "g") == "Protein: 88 / 144g · 56g to go"
    assert _macro_line("Calories", 2400, 2190, " kcal").endswith("210 kcal over")
    # No goal that day -> consumed only, no score.
    assert _macro_line("Carbs", 150, None, "g") == "Carbs: 150g"


def test_day_summary_lists_totals_and_meals(client):
    """/today reports the day's totals and the meals behind them.

    Uses the `client` fixture purely for its temp database — the formatter
    reads through the same list_entries/active_goal the web app uses.
    """
    day = VALID_ENTRY["local_date"]
    client.post("/entries", json=VALID_ENTRY)                      # 650 kcal
    client.post("/entries", json={**VALID_ENTRY,
                                  "description": "Kaya toast", "calories": 200})

    text = _format_day(day, "Today")

    assert "05-Jul-2026" in text          # DD-MMM-YYYY display format (D5)
    assert "Calories: 850" in text        # 650 + 200, summed from the entries
    assert "2 items logged" in text
    assert "Kaya toast — 200 kcal" in text


def test_day_summary_empty_day_invites_a_photo(client):
    """A day with nothing logged gets a nudge, not a wall of zeros."""
    text = _format_day("2026-07-05", "Today")

    assert "Nothing logged yet" in text
