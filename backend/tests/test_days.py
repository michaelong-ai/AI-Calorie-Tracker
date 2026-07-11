"""Tests for the Days API — per-day summaries powering the History screen."""

from tests.conftest import VALID_ENTRY


def _log(client, local_date, calories):
    """Helper: log one entry with given date and calories."""
    client.post("/entries", json={**VALID_ENTRY, "local_date": local_date,
                                  "calories": calories})


def test_days_aggregates_entries_per_day(client):
    """Two entries on one day sum into one row; a second day is separate."""
    _log(client, "2026-07-04", 600)
    _log(client, "2026-07-04", 400)
    _log(client, "2026-07-05", 500)

    days = client.get("/days", params={"start": "2026-07-01", "end": "2026-07-31"}).json()

    assert len(days) == 2
    assert days[0]["local_date"] == "2026-07-05"  # newest first
    assert days[1]["calories"] == 1000            # 600 + 400 summed
    assert days[1]["entry_count"] == 2


def test_days_outside_range_are_excluded(client):
    _log(client, "2026-06-30", 500)
    _log(client, "2026-07-02", 500)

    days = client.get("/days", params={"start": "2026-07-01", "end": "2026-07-31"}).json()
    assert [d["local_date"] for d in days] == ["2026-07-02"]


def test_each_day_paired_with_goal_active_that_day(client):
    """The versioning rule applied to history: a July 5 day must carry the
    goal that was active July 5, even after a newer goal exists."""
    goal = {"calories_target": 2200, "protein_g_target": 144,
            "carbs_g_target": 220, "fat_g_target": 61,
            "effective_from": "2026-07-01"}
    client.post("/goals", json=goal)                                   # v1: 2200
    client.post("/goals", json={**goal, "calories_target": 2000,
                                "effective_from": "2026-07-10"})       # v2: 2000

    _log(client, "2026-07-05", 500)   # while v1 active
    _log(client, "2026-07-15", 500)   # while v2 active

    days = client.get("/days", params={"start": "2026-07-01", "end": "2026-07-31"}).json()
    by_date = {d["local_date"]: d for d in days}

    assert by_date["2026-07-05"]["target"]["calories_target"] == 2200
    assert by_date["2026-07-15"]["target"]["calories_target"] == 2000


def test_day_before_any_goal_has_null_target(client):
    _log(client, "2026-07-05", 500)  # no goal exists at all

    days = client.get("/days", params={"start": "2026-07-01", "end": "2026-07-31"}).json()
    assert days[0]["target"] is None
