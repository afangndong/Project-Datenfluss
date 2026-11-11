"""Zentrale Konfiguration (12-Factor: alles über Umgebungsvariablen)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    app_name: str = "Mini-KOS"
    app_env: str = "dev"  # dev | test | prod
    app_version: str = "1.0.0"
    git_sha: str = "local"
    instance_name: str = "app"  # z. B. blue / green / canary – erscheint in /api/version

    database_url: str = "sqlite:///./minikos.db"
    # Leer = offen (Demo). Gesetzt = Schreibzugriffe brauchen Header X-API-Key.
    api_key: str = ""

    log_level: str = "INFO"
    log_json: bool = True

    # Optional: Unleash (Feature Flags). Leer = Flags aus Umgebungsvariablen FEATURE_<NAME>.
    unleash_url: str = ""
    unleash_token: str = ""

    # Links, die die GUI auf der Systemseite anzeigt
    grafana_url: str = "http://localhost:3000"
    prometheus_url: str = "http://localhost:9090"
    alertmanager_url: str = "http://localhost:9093"
    kibana_url: str = "http://localhost:5601"
    unleash_ui_url: str = "http://localhost:4242"


settings = Settings()
