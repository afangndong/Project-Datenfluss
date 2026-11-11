def _stay(client, pid, **kw):
    body = {"patient_id": pid, "station": "Chirurgie", "zimmer": "210", "aufnahme": "2026-01-01"}
    body.update(kw)
    return client.post("/api/stays", json=body)


def test_stay_flow_and_discharge(client, patient):
    s = _stay(client, patient["id"]).json()
    assert s["entlassung"] is None
    assert len(client.get("/api/stays", params={"nur_aktuell": True}).json()) == 1
    assert client.post(f"/api/stays/{s['id']}/entlassen").json()["entlassung"] is not None
    assert client.post(f"/api/stays/{s['id']}/entlassen").status_code == 409
    assert client.get("/api/stays", params={"nur_aktuell": True}).json() == []


def test_stay_validation(client, patient):
    assert _stay(client, patient["id"], entlassung="2025-12-31").status_code == 422
    assert _stay(client, 9999).status_code == 404


def test_appointment_flow(client, patient):
    r = client.post(
        "/api/appointments", json={"patient_id": patient["id"], "termin": "2026-06-01T09:30:00", "art": "Visite"}
    )
    assert r.status_code == 201 and r.json()["patient_name"] == "Muster, Anna"
    aid = r.json()["id"]
    assert client.patch(f"/api/appointments/{aid}/status", params={"status": "erledigt"}).json()["status"] == "erledigt"
    assert client.patch(f"/api/appointments/{aid}/status", params={"status": "kaputt"}).status_code == 422
    assert client.get("/api/appointments", params={"status": "geplant"}).json() == []
    assert client.delete(f"/api/appointments/{aid}").status_code == 204


def test_appointment_unknown_patient(client):
    r = client.post("/api/appointments", json={"patient_id": 1, "termin": "2026-06-01T09:30:00"})
    assert r.status_code == 404


def test_stats_reflect_data(client, patient):
    _stay(client, patient["id"])
    s = client.get("/api/stats").json()
    assert s["patienten"] == 1 and s["belegung_je_station"] == {"Chirurgie": 1}
