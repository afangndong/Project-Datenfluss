from app import flags
from app.config import settings


def test_write_requires_key_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "geheim")
    body = {"vorname": "A", "nachname": "B", "geburtsdatum": "1990-01-01"}
    assert client.post("/api/patients", json=body).status_code == 401
    assert client.post("/api/patients", json=body, headers={"X-API-Key": "falsch"}).status_code == 401
    assert client.post("/api/patients", json=body, headers={"X-API-Key": "geheim"}).status_code == 201
    assert client.get("/api/patients").status_code == 200  # Lesen bleibt offen


def test_flag_env_override(monkeypatch):
    monkeypatch.setenv("FEATURE_WARTUNGSHINWEIS", "true")
    assert flags.is_enabled("wartungshinweis") is True
    monkeypatch.setenv("FEATURE_NEUES_DASHBOARD", "off")
    assert flags.is_enabled("neues_dashboard") is False


def test_sim_disabled_in_prod(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "prod")
    assert client.get("/api/sim/error").status_code == 404


def test_seed_is_idempotent(client):
    from app.seed import seed

    assert seed(5) == 5
    assert seed(5) == 0
    assert client.get("/api/stats").json()["patienten"] == 5
