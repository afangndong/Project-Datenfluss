import os
import tempfile

# Muss VOR dem Import der App gesetzt werden
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["APP_ENV"] = "test"
os.environ["LOG_JSON"] = "false"
os.environ.pop("API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def patient(client):
    r = client.post(
        "/api/patients",
        json={
            "vorname": "Anna",
            "nachname": "Muster",
            "geburtsdatum": "1980-05-17",
            "geschlecht": "weiblich",
            "versicherung": "gesetzlich",
        },
    )
    assert r.status_code == 201
    return r.json()
