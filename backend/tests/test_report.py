"""Tests for the HTML report export (T5.1).

The spec's hard requirement: the report is SELF-CONTAINED — it must open
from a local file with no network. The killer test here is the one that
scans the document for any external reference.
"""

import re
from datetime import date, timedelta

from tests.conftest import VALID_ENTRY


def _seed(client):
    """A little data so the report has something to show: a goal, two days
    of entries, two weight readings."""
    client.post("/goals", json={
        "calories_target": 2200, "protein_g_target": 144,
        "carbs_g_target": 220, "fat_g_target": 61,
        "effective_from": (date.today() - timedelta(days=14)).isoformat(),
    })
    for offset, kcal in ((0, 2100), (1, 2500)):
        d = (date.today() - timedelta(days=offset)).isoformat()
        client.post("/entries", json={**VALID_ENTRY, "local_date": d, "calories": kcal})
    for offset, kg in ((7, 81.0), (0, 80.4)):
        d = (date.today() - timedelta(days=offset)).isoformat()
        client.post("/weights", json={"weight_kg": kg, "local_date": d})


def test_report_downloads_as_html(client):
    _seed(client)
    response = client.get("/report", params={"weeks": 4})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    # "attachment" is what makes the browser save a file.
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("<!doctype html>")


def test_report_is_fully_self_contained(client):
    """THE invariant (CLAUDE.md): zero external references. No stylesheet
    links, no script/img sources, no url(...) fetches, no http(s) URLs."""
    _seed(client)
    doc = client.get("/report", params={"weeks": 4}).text

    assert "<link" not in doc          # no external stylesheets
    assert "<script" not in doc        # no scripts at all — pure document
    assert " src=" not in doc          # no images/iframes fetching anything
    assert not re.search(r"url\s*\(", doc)   # no CSS-triggered fetches
    assert "http://" not in doc and "https://" not in doc


def test_report_contains_charts_and_data(client):
    _seed(client)
    doc = client.get("/report", params={"weeks": 4}).text

    assert doc.count("<svg") == 2          # weight line + intake bars
    assert "chart-target" in doc           # the goal reference line is drawn
    assert "80.4 kg" in doc                # latest weight direct-labelled
    assert "2200" in doc                   # the target appears (line legend/table)
    assert "avg kcal / logged day" in doc  # the stat tile


def test_report_works_with_empty_database(client):
    """A brand-new user exporting immediately must get a valid (if sparse)
    document, not a crash — this is also a T5.2 empty-state case."""
    response = client.get("/report", params={"weeks": 4})
    assert response.status_code == 200
    assert "No days logged" in response.text
    assert "Not enough weight readings" in response.text
