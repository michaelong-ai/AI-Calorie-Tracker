"""Tests for the Entries API — the app's single write path.

These call the API exactly like the frontend does (HTTP verbs + JSON), so
they test the full stack: routing, validation, SQL, and response shapes.
Each test gets a fresh temp database via the `client` fixture (conftest.py).
"""

from tests.conftest import VALID_ENTRY


# --- Creating -----------------------------------------------------------------


def test_create_returns_entry_with_server_fields(client):
    """POST stores the entry and returns it with id/timestamp/source added."""
    response = client.post("/entries", json=VALID_ENTRY)
    assert response.status_code == 201  # 201 = Created

    body = response.json()
    assert body["id"] == 1
    assert body["description"] == VALID_ENTRY["description"]
    assert body["source"] == "manual"       # server decides, not the client
    assert body["logged_at_utc"]            # server stamped the UTC time


def test_create_rejects_negative_calories(client):
    """Validation: negative nutrition values must be refused with 422
    (Unprocessable Entity) before reaching the database."""
    bad = {**VALID_ENTRY, "calories": -100}
    assert client.post("/entries", json=bad).status_code == 422


def test_create_rejects_blank_description(client):
    bad = {**VALID_ENTRY, "description": ""}
    assert client.post("/entries", json=bad).status_code == 422


def test_create_rejects_malformed_local_date(client):
    """local_date must be YYYY-MM-DD — the day-boundary rule depends on it."""
    bad = {**VALID_ENTRY, "local_date": "05/07/2026"}
    assert client.post("/entries", json=bad).status_code == 422


# --- Listing -------------------------------------------------------------------


def test_list_returns_only_the_requested_day(client):
    """GET /entries?local_date=... must filter by day — the Today screen and
    daily totals depend on this boundary being exact."""
    client.post("/entries", json=VALID_ENTRY)  # on 2026-07-05
    client.post("/entries", json={**VALID_ENTRY, "local_date": "2026-07-06"})

    on_5th = client.get("/entries", params={"local_date": "2026-07-05"}).json()
    on_6th = client.get("/entries", params={"local_date": "2026-07-06"}).json()
    on_7th = client.get("/entries", params={"local_date": "2026-07-07"}).json()

    assert len(on_5th) == 1
    assert len(on_6th) == 1
    assert on_7th == []  # empty day -> empty list, not an error


# --- Updating ------------------------------------------------------------------


def test_update_overwrites_fields(client):
    created = client.post("/entries", json=VALID_ENTRY).json()

    edited = {**VALID_ENTRY, "description": "chicken rice, small", "calories": 450}
    response = client.put(f"/entries/{created['id']}", json=edited)

    assert response.status_code == 200
    assert response.json()["calories"] == 450
    assert response.json()["description"] == "chicken rice, small"


def test_update_missing_entry_gives_404(client):
    assert client.put("/entries/999", json=VALID_ENTRY).status_code == 404


# --- Deleting ------------------------------------------------------------------


def test_delete_removes_the_entry(client):
    created = client.post("/entries", json=VALID_ENTRY).json()

    assert client.delete(f"/entries/{created['id']}").status_code == 204
    # And it's really gone:
    remaining = client.get("/entries", params={"local_date": VALID_ENTRY["local_date"]}).json()
    assert remaining == []


def test_delete_missing_entry_gives_404(client):
    assert client.delete("/entries/999").status_code == 404


# --- Food library: GET /entries/frequent (T6.4) ---------------------------------


def test_frequent_groups_and_sorts_by_times_logged(client):
    """The food eaten most often must come first, with a per-food count."""
    # Laksa twice, toast once → laksa leads the list.
    client.post("/entries", json={**VALID_ENTRY, "description": "Laksa"})
    client.post("/entries", json={**VALID_ENTRY, "description": "Laksa"})
    client.post("/entries", json={**VALID_ENTRY, "description": "Kaya toast"})

    foods = client.get("/entries/frequent").json()

    assert [f["description"] for f in foods] == ["Laksa", "Kaya toast"]
    assert foods[0]["times_logged"] == 2
    assert foods[1]["times_logged"] == 1


def test_frequent_groups_case_insensitively_latest_values_win(client):
    """"laksa" and "Laksa" are one food, carrying the NEWEST log's numbers
    (portions drift — the last log is the best default)."""
    client.post("/entries", json={**VALID_ENTRY, "description": "laksa", "calories": 600})
    client.post("/entries", json={**VALID_ENTRY, "description": "Laksa", "calories": 800})

    foods = client.get("/entries/frequent").json()

    assert len(foods) == 1
    assert foods[0]["times_logged"] == 2
    assert foods[0]["calories"] == 800  # the later entry's value, not the first


def test_frequent_empty_history_gives_empty_list(client):
    """First-ever launch: no history yet → empty list, not an error."""
    assert client.get("/entries/frequent").json() == []


def test_frequent_respects_limit(client):
    """?limit=N caps the list so the dropdown stays scannable."""
    for name in ["a", "b", "c"]:
        client.post("/entries", json={**VALID_ENTRY, "description": name})

    assert len(client.get("/entries/frequent", params={"limit": 2}).json()) == 2
