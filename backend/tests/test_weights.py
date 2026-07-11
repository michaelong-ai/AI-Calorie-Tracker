"""Tests for the Weights API — the body-weight log."""


def test_log_and_list_weights_newest_first(client):
    client.post("/weights", json={"weight_kg": 82.5, "local_date": "2026-07-01"})
    client.post("/weights", json={"weight_kg": 82.1, "local_date": "2026-07-05"})

    weights = client.get("/weights").json()
    assert [w["weight_kg"] for w in weights] == [82.1, 82.5]  # newest first


def test_weight_must_be_positive(client):
    bad = {"weight_kg": 0, "local_date": "2026-07-01"}
    assert client.post("/weights", json=bad).status_code == 422


def test_delete_weight(client):
    created = client.post(
        "/weights", json={"weight_kg": 82.5, "local_date": "2026-07-01"}
    ).json()

    assert client.delete(f"/weights/{created['id']}").status_code == 204
    assert client.get("/weights").json() == []


def test_delete_missing_weight_gives_404(client):
    assert client.delete("/weights/999").status_code == 404
