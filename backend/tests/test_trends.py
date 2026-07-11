"""Tests for the /trends endpoint — weekly bucketing and weight pairing (T4.3)."""

from datetime import date, timedelta

from tests.conftest import VALID_ENTRY


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def test_trends_returns_continuous_week_span(client):
    """Every week in the window appears, even empty ones — a continuous
    x-axis is what makes the trend readable (no collapsed gaps)."""
    body = client.get("/trends", params={"weeks": 6}).json()
    assert len(body["weeks"]) == 6
    # Weeks are oldest-first and exactly 7 days apart.
    starts = [date.fromisoformat(w["week_start"]) for w in body["weeks"]]
    assert starts == sorted(starts)
    for earlier, later in zip(starts, starts[1:]):
        assert (later - earlier).days == 7


def test_weekly_average_is_per_logged_day(client):
    """Two days in one week, 2000 and 1000 kcal → average 1500, days_logged 2.
    (Averaging per logged day, not per calendar day, so a partly-logged week
    isn't unfairly shown as low.)"""
    # Two days in the current week.
    today = date.today()
    monday = _monday_of(today)
    d1 = monday.isoformat()
    d2 = (monday + timedelta(days=1)).isoformat()
    client.post("/entries", json={**VALID_ENTRY, "local_date": d1, "calories": 2000})
    client.post("/entries", json={**VALID_ENTRY, "local_date": d2, "calories": 1000})

    body = client.get("/trends", params={"weeks": 4}).json()
    this_week = next(w for w in body["weeks"] if w["week_start"] == monday.isoformat())
    assert this_week["days_logged"] == 2
    assert this_week["avg_calories"] == 1500


def test_multiple_entries_same_day_count_as_one_day(client):
    """Two entries on ONE day sum, and that day counts once toward the
    average (breakfast + lunch is still one logged day)."""
    monday = _monday_of(date.today())
    d = monday.isoformat()
    client.post("/entries", json={**VALID_ENTRY, "local_date": d, "calories": 700})
    client.post("/entries", json={**VALID_ENTRY, "local_date": d, "calories": 800})

    body = client.get("/trends", params={"weeks": 4}).json()
    this_week = next(w for w in body["weeks"] if w["week_start"] == monday.isoformat())
    assert this_week["days_logged"] == 1
    assert this_week["avg_calories"] == 1500  # 700 + 800 on the single day


def test_weights_are_returned_oldest_first(client):
    client.post("/weights", json={"weight_kg": 80.0, "local_date": date.today().isoformat()})
    body = client.get("/trends", params={"weeks": 4}).json()
    assert len(body["weights"]) == 1
    assert body["weights"][0]["weight_kg"] == 80.0
