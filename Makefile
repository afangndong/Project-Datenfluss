# Mini-KOS – Komfort-Befehle. `make help` zeigt alles.
.DEFAULT_GOAL := help
SHELL := /bin/bash
DEPLOY_ENV ?= dev
TAG ?= local
COMPOSE = docker compose -f docker-compose.yml $(if $(wildcard docker-compose.$(DEPLOY_ENV).yml),-f docker-compose.$(DEPLOY_ENV).yml)

.PHONY: help ci act github-push
help: ## Diese Hilfe
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------- Lokal ohne Docker ----------
venv: ## Python-venv + Abhängigkeiten (lokal, SQLite)
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt
run: ## App lokal starten (SQLite, http://localhost:8000) inkl. Demo-Daten
	.venv/bin/python -m app.seed && LOG_JSON=false .venv/bin/uvicorn app.main:app --reload
test: ## Tests
	.venv/bin/pytest
lint: ## Lint + Format-Check (ruff) und shellcheck (falls vorhanden)
	.venv/bin/ruff check . && .venv/bin/ruff format --check .
	@command -v shellcheck >/dev/null && shellcheck -x -S warning scripts/*.sh || echo "(shellcheck nicht installiert – übersprungen)"
format: ## Code formatieren
	.venv/bin/ruff format . && .venv/bin/ruff check --fix .

ci: lint test ## Lokal dasselbe wie die CI: Lint, Tests, Image bauen, Compose prüfen
	docker build -t mini-kos:ci .
	@created=0; test -f env/prod.env || { cp env/prod.env.example env/prod.env; created=1; }; \
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile monitoring --profile elk --profile flags --profile green --profile canary config -q; rc=$$?; \
	[ $$created = 1 ] && rm -f env/prod.env; \
	[ $$rc = 0 ] && echo "CI lokal: OK"; exit $$rc
act: ## GitHub-Actions lokal ausführen (benötigt https://github.com/nektos/act): make act JOB=test
	act -j $(or $(JOB),test)
github-push: ## Zu GitHub pushen: make github-push REPO=deinname/mini-kos [CREATE=1]
	scripts/push_to_github.sh $(REPO) $(if $(CREATE),--create)

# ---------- Docker ----------
setup: ## Einmalig: .env aus Vorlage anlegen
	@test -f .env || cp .env.example .env && echo ".env bereit"
build: ## Image bauen
	$(COMPOSE) build app_blue
up: setup ## Kern starten: db + app + proxy → http://localhost:8080
	$(COMPOSE) up -d --build db app_blue proxy
up-monitoring: ## + Prometheus/Alertmanager/Grafana/cAdvisor/Exporter
	@mkdir -p .backup/metrics
	$(COMPOSE) --profile monitoring up -d
up-elk: ## + Elasticsearch/Logstash/Kibana/Filebeat (braucht ~3 GB RAM)
	$(COMPOSE) --profile elk up -d
up-flags: ## + Unleash Feature-Flag-Server
	$(COMPOSE) --profile flags up -d
up-all: up up-monitoring up-elk up-flags ## Alles starten
down: ## Alles stoppen (Daten bleiben)
	$(COMPOSE) --profile monitoring --profile elk --profile flags --profile green --profile canary down
reset: ## ACHTUNG: alles stoppen und alle Volumes/Daten löschen
	$(COMPOSE) --profile monitoring --profile elk --profile flags --profile green --profile canary down -v
	rm -rf .deploy .backup
ps: ## Status der Container
	$(COMPOSE) --profile monitoring --profile elk --profile flags --profile green --profile canary ps
logs: ## Logs der App (folgen)
	$(COMPOSE) logs -f app_blue app_green app_canary 2>/dev/null
seed: ## Fiktive Demo-Daten in die Docker-DB laden
	$(COMPOSE) exec app_blue python -m app.seed 40
smoke: ## Rauchtest gegen http://localhost:8080
	scripts/smoke_test.sh
flags-bootstrap: ## Feature Flags in Unleash anlegen
	scripts/unleash_bootstrap.sh

# ---------- Betrieb ----------
backup: ## Backup jetzt
	scripts/backup.sh
restore-test: ## Letztes Backup in temporäre DB einspielen und prüfen
	scripts/restore_test.sh

# ---------- Deployment-Strategien (TAG=<image-tag>) ----------
bluegreen: ## Blue-Green:  make bluegreen TAG=1.1.0
	scripts/deploy_bluegreen.sh $(TAG)
rolling: ## Rolling:     make rolling TAG=1.1.0
	scripts/deploy_rolling.sh $(TAG) 2
canary: ## Canary 10 %: make canary TAG=1.1.0   (danach canary-promote / canary-abort)
	scripts/deploy_canary.sh $(TAG) 10
canary-promote: ## Canary zur Hauptversion machen
	scripts/deploy_canary.sh --promote
canary-abort: ## Canary verwerfen
	scripts/deploy_canary.sh --abort
recreate: ## Recreate (mit Downtime): make recreate TAG=1.1.0
	scripts/deploy_recreate.sh $(TAG)
rollback: ## Zurück auf die vorherige Blue-Green-Version
	scripts/rollback.sh

# ---------- Übungen ----------
alerts-errors: ## HTTP-500-Last erzeugen (Alert HighErrorRate)
	scripts/trigger_alerts.sh errors
alerts-down: ## App stoppen (Alert AppDown)
	scripts/trigger_alerts.sh down
load: ## 60 s normale Last (Grafana-Kurven)
	scripts/trigger_alerts.sh load
