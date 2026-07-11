"""Tests for the Goals API — the calculator and, crucially, goal VERSIONING.

The versioning rule (spec F3): saving a goal never overwrites; each day is
judged by the goal that was active on that day. These tests lock that in.
"""

VALID_STATS = {
    "weight_kg": 80,
    "height_cm": 180,
    "age": 30,
    "sex": "male",
    "activity_level": "moderate",
    "rate_kg_per_week": -0.5,
}

GOAL_V1 = {
    "calories_target": 2200,
    "protein_g_target": 144,
    "carbs_g_target": 220,
    "fat_g_target": 61,
    "effective_from": "2026-07-01",
}


def test_calculate_returns_targets_without_saving(client):
    """/goals/calculate is a pure calculator — verify it computes AND that
    nothing appears in the goal history afterwards."""
    response = client.post("/goals/calculate", json=VALID_STATS)
    assert response.status_code == 200

    body = response.json()
    # BMR for these stats is exactly 1780 (see test_tdee.py) — spot-check
    # the wiring end to end.
    assert body["bmr"] == 1780
    assert body["calories_target"] < body["tdee"]  # it's a cut

    # And it saved nothing:
    assert client.get("/goals").json() == []


def test_calculate_rejects_unknown_activity_level(client):
    bad = {**VALID_STATS, "activity_level": "couch"}
    assert client.post("/goals/calculate", json=bad).status_code == 422


def test_save_and_read_back_goal(client):
    assert client.post("/goals", json=GOAL_V1).status_code == 201
    history = client.get("/goals").json()
    assert len(history) == 1
    assert history[0]["calories_target"] == 2200


def test_saving_again_creates_a_new_version_not_an_overwrite(client):
    """THE core rule: two saves -> two rows in history, both kept."""
    client.post("/goals", json=GOAL_V1)
    client.post("/goals", json={**GOAL_V1, "calories_target": 2000,
                                "effective_from": "2026-07-10"})

    history = client.get("/goals").json()
    assert len(history) == 2  # nothing was overwritten


def test_each_day_gets_the_goal_active_on_that_day(client):
    """v1 effective July 1, v2 effective July 10:
    July 5 must answer v1; July 15 must answer v2."""
    client.post("/goals", json=GOAL_V1)  # 2200 kcal from 2026-07-01
    client.post("/goals", json={**GOAL_V1, "calories_target": 2000,
                                "effective_from": "2026-07-10"})

    on_jul_5 = client.get("/goals/active", params={"local_date": "2026-07-05"}).json()
    on_jul_15 = client.get("/goals/active", params={"local_date": "2026-07-15"}).json()

    assert on_jul_5["calories_target"] == 2200   # the OLD goal still judges old days
    assert on_jul_15["calories_target"] == 2000  # new days use the new goal


def test_days_before_first_goal_have_no_target(client):
    """Spec: days before the first goal show totals WITHOUT comparison.
    The API expresses that as null, never as an error."""
    client.post("/goals", json=GOAL_V1)  # effective 2026-07-01

    response = client.get("/goals/active", params={"local_date": "2026-06-15"})
    assert response.status_code == 200
    assert response.json() is None
