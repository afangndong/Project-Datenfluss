def test_create_assigns_fallnummer(patient):
    assert patient["fallnummer"] == f"F{patient['id']:06d}"


def test_get_update_delete(client, patient):
    pid = patient["id"]
    assert client.get(f"/api/patients/{pid}").json()["nachname"] == "Muster"
    upd = dict(patient, nachname="Beispiel")
    r = client.put(
        f"/api/patients/{pid}",
        json={k: upd[k] for k in ("vorname", "nachname", "geburtsdatum", "geschlecht", "versicherung")},
    )
    assert r.json()["nachname"] == "Beispiel"
    assert client.delete(f"/api/patients/{pid}").status_code == 204
    assert client.get(f"/api/patients/{pid}").status_code == 404


def test_search_and_total_header(client, patient):
    r = client.get("/api/patients", params={"q": "must"})
    assert len(r.json()) == 1 and r.headers["X-Total-Count"] == "1"
    assert client.get("/api/patients", params={"q": "zzz"}).json() == []


def test_birthdate_in_future_rejected(client):
    r = client.post("/api/patients", json={"vorname": "A", "nachname": "B", "geburtsdatum": "2999-01-01"})
    assert r.status_code == 422


def test_delete_cascades(client, patient):
    client.post(
        "/api/stays",
        json={"patient_id": patient["id"], "station": "Innere A", "zimmer": "101", "aufnahme": "2026-01-01"},
    )
    client.delete(f"/api/patients/{patient['id']}")
    assert client.get("/api/stays").json() == []
