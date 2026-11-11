def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_checks_db(client):
    assert client.get("/ready").status_code == 200


def test_version(client):
    body = client.get("/api/version").json()
    assert body["name"] == "Mini-KOS" and body["env"] == "test"


def test_gui_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Mini-KOS" in r.text


def test_flags_and_links(client):
    assert set(client.get("/api/flags").json()) == {"neues_dashboard", "wartungshinweis"}
    assert "Grafana" in client.get("/api/links").json()


def test_metrics_exposed(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert "minikos_http_requests_total" in body
    assert "minikos_patients_total" in body
    assert "minikos_db_up 1.0" in body


def test_simulated_error_returns_500_and_is_counted(client):
    assert client.get("/api/sim/error").status_code == 500
    assert 'status="500"' in client.get("/metrics").text


def test_stats_empty(client):
    s = client.get("/api/stats").json()
    assert s["patienten"] == 0 and s["aktuelle_aufenthalte"] == 0
