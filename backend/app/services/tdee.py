"""TDEE and macro-target calculations (feature F3).

Everything here is pure math: numbers in, numbers out, no database, no web.
That's deliberate — pure functions are trivial to unit test (see
tests/test_tdee.py) and can't break anything else.

The chain of reasoning, in plain language:

  BMR  (Basal Metabolic Rate)     what your body burns doing nothing at all
   × activity multiplier
  TDEE (Total Daily Energy Exp.)  what you actually burn in a typical day
   ± goal adjustment              eat less to lose, more to gain
  daily calorie target
   → split into protein / fat / carbs gram targets
"""

# Calories "stored" in one kilogram of body fat — the standard figure used
# to convert "lose X kg per week" into a daily calorie deficit.
KCAL_PER_KG_BODYFAT = 7700

# How much a typical day multiplies BMR, by lifestyle. Standard companion
# values to the Mifflin-St Jeor formula.
ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,       # desk job, little exercise
    "light": 1.375,         # light exercise 1-3 days/week
    "moderate": 1.55,       # moderate exercise 3-5 days/week
    "active": 1.725,        # hard exercise 6-7 days/week
    "very_active": 1.9,     # physical job + hard training
}

# Protein target per kg of body weight. 1.8 g/kg sits in the range sports
# nutrition research recommends for people training while managing weight.
PROTEIN_G_PER_KG = 1.8

# Fraction of daily calories allotted to fat (25% — a common, sustainable
# baseline; below ~20% long-term is generally discouraged).
FAT_KCAL_FRACTION = 0.25

# Energy content per gram of each macro — the constants that link grams
# to calories everywhere in nutrition math.
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


def bmr_mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Basal Metabolic Rate via the Mifflin-St Jeor equation (kcal/day).

    Inputs: body weight in kg, height in cm, age in years, sex "male" or
    "female" (the formula has only these two variants; it differs by a
    constant). Returns kcal/day burned at complete rest.
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def tdee_from_bmr(bmr: float, activity_level: str) -> float:
    """Total Daily Energy Expenditure: BMR scaled by lifestyle activity.

    `activity_level` must be a key of ACTIVITY_MULTIPLIERS; a KeyError here
    means the API validation upstream failed to do its job.
    """
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def daily_calorie_target(tdee: float, rate_kg_per_week: float) -> float:
    """Calorie target from TDEE and the desired weight-change rate.

    `rate_kg_per_week` is signed: negative to lose (cut), 0 to maintain,
    positive to gain (bulk). E.g. -0.5 kg/week -> eat ~550 kcal/day under
    TDEE (0.5 * 7700 / 7).
    """
    daily_adjustment = rate_kg_per_week * KCAL_PER_KG_BODYFAT / 7
    return tdee + daily_adjustment


def macro_targets(calorie_target: float, weight_kg: float) -> dict[str, float]:
    """Split a calorie target into protein/carb/fat gram targets.

    Method (a standard "protein first" split):
      1. Protein: fixed per kg of body weight (muscle preservation).
      2. Fat: fixed fraction of total calories.
      3. Carbs: whatever calories remain, converted to grams.
    Returns grams rounded to whole numbers, keys matching the goals table.
    """
    protein_g = PROTEIN_G_PER_KG * weight_kg
    fat_g = (calorie_target * FAT_KCAL_FRACTION) / KCAL_PER_G_FAT

    # Calories left over after protein and fat take their share.
    remaining_kcal = (
        calorie_target
        - protein_g * KCAL_PER_G_PROTEIN
        - fat_g * KCAL_PER_G_FAT
    )
    # max(0, ...): on a very aggressive cut the remainder could go negative;
    # a negative carb target is nonsense, so clamp at zero.
    carbs_g = max(0, remaining_kcal / KCAL_PER_G_CARB)

    return {
        "protein_g_target": round(protein_g),
        "carbs_g_target": round(carbs_g),
        "fat_g_target": round(fat_g),
    }


def calculate_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    rate_kg_per_week: float,
) -> dict[str, float]:
    """The full pipeline the Goals screen calls: stats in, targets out.

    Returns a dict with bmr and tdee (shown to the user as explanation)
    plus calories_target and the three macro gram targets (which become a
    goal row once the user confirms/edits them).
    """
    bmr = bmr_mifflin_st_jeor(weight_kg, height_cm, age, sex)
    tdee = tdee_from_bmr(bmr, activity_level)
    calories = daily_calorie_target(tdee, rate_kg_per_week)

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "calories_target": round(calories),
        **macro_targets(calories, weight_kg),
    }
