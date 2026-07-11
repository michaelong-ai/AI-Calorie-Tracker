"""Unit tests for the TDEE service — pure math, so tests use known answers.

Each expected number below was worked out by hand from the published
formulas; if a test fails, either the code or the constant changed.
"""

from app.services import tdee


def test_bmr_male_known_answer():
    """80 kg, 180 cm, 30-year-old male:
    10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780."""
    assert tdee.bmr_mifflin_st_jeor(80, 180, 30, "male") == 1780


def test_bmr_female_known_answer():
    """60 kg, 165 cm, 25-year-old female:
    10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161 = 1345.25."""
    assert tdee.bmr_mifflin_st_jeor(60, 165, 25, "female") == 1345.25


def test_tdee_applies_activity_multiplier():
    """Moderate activity multiplies BMR by 1.55: 1780 * 1.55 = 2759."""
    assert tdee.tdee_from_bmr(1780, "moderate") == 1780 * 1.55


def test_maintain_keeps_tdee():
    """Rate 0 (maintain) must change nothing."""
    assert tdee.daily_calorie_target(2500, 0) == 2500


def test_cut_subtracts_calories():
    """-0.5 kg/week = 0.5*7700/7 = 550 kcal/day deficit."""
    assert tdee.daily_calorie_target(2500, -0.5) == 2500 - 550


def test_bulk_adds_calories():
    """+0.25 kg/week = 0.25*7700/7 = 275 kcal/day surplus."""
    assert tdee.daily_calorie_target(2500, 0.25) == 2500 + 275


def test_macro_split_adds_back_up_to_calories():
    """The three macros' calories must re-total (approximately) the target.
    Rounding to whole grams can shift the sum by a few kcal — that's fine;
    a big gap would mean the split math is wrong."""
    target = 2200
    macros = tdee.macro_targets(target, weight_kg=80)

    recomposed = (
        macros["protein_g_target"] * tdee.KCAL_PER_G_PROTEIN
        + macros["carbs_g_target"] * tdee.KCAL_PER_G_CARB
        + macros["fat_g_target"] * tdee.KCAL_PER_G_FAT
    )
    assert abs(recomposed - target) < 15  # within rounding error


def test_macro_protein_follows_bodyweight():
    """Protein = 1.8 g per kg: 80 kg -> 144 g."""
    assert tdee.macro_targets(2200, weight_kg=80)["protein_g_target"] == 144


def test_carbs_never_negative():
    """Absurdly low calorie target: carbs clamp to 0, not negative."""
    macros = tdee.macro_targets(500, weight_kg=100)
    assert macros["carbs_g_target"] == 0


def test_full_pipeline_produces_all_fields():
    result = tdee.calculate_targets(
        weight_kg=80, height_cm=180, age=30,
        sex="male", activity_level="moderate", rate_kg_per_week=-0.5,
    )
    assert set(result) == {
        "bmr", "tdee", "calories_target",
        "protein_g_target", "carbs_g_target", "fat_g_target",
    }
    # Sanity: a cut target must sit below TDEE.
    assert result["calories_target"] < result["tdee"]
