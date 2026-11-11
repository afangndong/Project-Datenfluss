# Betriebshandbuch (Runbook)

Für Administratoren: Start, Stopp, Updates, Backup, Fehlersuche. Alle Befehle im Projektverzeichnis (auf Servern `/opt/mini-kos`).

## Start und Stopp

| Aktion | Befehl |
|---|---|
| Kern starten (db, app, proxy) | `make up` |
| Monitoring / ELK / Flags zuschalten | `make up-monitoring` · `make up-elk` · `make up-flags` |
| Status | `make ps` |
| Stoppen (Daten bleiben) | `make down` |
| **Alles löschen** (inkl. Datenbank!) | `make reset` – nur in dev/test |

Auf Servern ohne `make`: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db app_blue proxy`.

## Umgebungen

| Umgebung | Compose-Override | Env-Datei | Besonderheiten |
|---|---|---|---|
| dev | `docker-compose.dev.yml` | `env/dev.env` | Quellcode live eingebunden, DB-Port 5432 offen, Debug-Logs |
| test | `docker-compose.test.yml` | `env/test.env` | DB flüchtig (tmpfs), API-Key gesetzt |
| prod | `docker-compose.prod.yml` | `env/prod.env` (von Ansible erzeugt) | Ressourcenlimits, Log-Rotation, kein DB-Port, Simulation `/api/sim/*` abgeschaltet |

Umgebung wählen: `DEPLOY_ENV=prod scripts/backup.sh` (Skripte) bzw. `-f docker-compose.prod.yml` (Compose).

## Geheimnisse

- `env/prod.env` und `.env` enthalten Passwörter → Rechte `0600`, **nie** ins Git (`.gitignore` schützt).
- Auf Servern erzeugt Ansible beide Dateien aus dem **Ansible Vault** (`ansible/inventories/prod/vault.yml`).
- Vault anlegen: `cp vault.example.yml vault.yml && ansible-vault encrypt vault.yml`; Deployment mit `--ask-vault-pass` bzw. in CI mit `ANSIBLE_VAULT_PASS`.
- Das Playbook bricht ab, wenn in Prod noch Platzhalter („BITTE …“) oder ein API-Key unter 16 Zeichen steht.
- Rotation: Wert im Vault ändern → Playbook erneut laufen lassen → Container werden mit neuer Umgebung gestartet.

## Updates / Deployments

Regulär über die Pipeline ([CI-CD](CI-CD.md)). Manuell auf dem Server:

```bash
DEPLOY_ENV=prod scripts/deploy_rolling.sh <image-tag> 2
```

Strategiewahl und Rollback: [DEPLOYMENT-STRATEGIEN](DEPLOYMENT-STRATEGIEN.md).

**Vor jedem Prod-Deployment:** letztes Backup < 24 h? (`ls -l .backup/`, Grafana-Kachel „Letztes Backup“).

## Backup & Restore

### Backup
`scripts/backup.sh` (nachts 02:30 per Cron, eingerichtet von Ansible) erstellt `.backup/minikos_<zeitstempel>.sql.gz`:

1. `pg_dump` → gzip, in eine `.part`-Datei
2. Integritätsprüfung (`gzip -t`) und Mindestgröße
3. Erst dann umbenennen (nie ein halbes Backup in der Liste)
4. Retention: Dateien älter als `KEEP_DAYS` (7) werden gelöscht
5. Metrik `minikos_backup_last_success_timestamp_seconds` → Alert `BackupTooOld` (> 26 h)

> Das Backup liegt zunächst **auf demselben Host**. Für echten Schutz die Dateien regelmäßig auf ein anderes System kopieren (rsync/NAS/Bandlaufwerk) und dort verschlüsseln.

### Restore-Test (regelmäßig – z. B. wöchentlich/monatlich)
```bash
scripts/restore_test.sh            # neuestes Backup
scripts/restore_test.sh .backup/minikos_20261101_023000.sql.gz
```
Spielt das Backup in eine **temporäre** Datenbank ein, vergleicht Tabellen (Patienten, Aufenthalte, Termine) mit der Live-DB, löscht die Test-DB. Live-Daten bleiben unberührt. Exit-Code ≠ 0 bei Fehler.

### Echter Restore (Notfall)
```bash
scripts/restore.sh .backup/minikos_20261101_023000.sql.gz --yes
```
Stoppt die App, spielt das Backup in die Live-DB ein (`--clean --if-exists` ersetzt Tabellen), startet die App und wartet auf „healthy“.
Danach: Smoke-Test (`scripts/smoke_test.sh`), Stichproben in der GUI, Vorfall dokumentieren.

## Logs

| Was | Wo |
|---|---|
| App (JSON) | `docker compose logs -f app_blue` · Kibana: Index `minikos-logs-*` |
| Proxy | `docker compose logs proxy` |
| Alarme | `docker compose logs alert-webhook` |
| Backup | `.backup/backup.log` (Cron-Ausgabe) |

Log-Felder: `@timestamp, level, logger, message, service, env, instance, version, method, path, status, duration_ms, request_id`.
**Keine Patientendaten in Logs** – nur Pfade (ohne Query-String) und technische IDs. Logs in Elasticsearch werden nach 14 Tagen gelöscht (`elk/setup_ilm.sh` einmalig ausführen).

## Fehlersuche – Schnellreferenz

| Symptom | Erste Prüfung | Typische Ursache |
|---|---|---|
| GUI nicht erreichbar | `make ps`; `curl -i localhost:8080/healthz` | Proxy aus; Port belegt (`PROXY_PORT`) |
| GUI lädt, Daten fehlen / rote Meldung | `curl localhost:8080/ready` | DB nicht erreichbar → `docker compose logs db` |
| Container „unhealthy“ | `docker inspect --format '{{json .State.Health}}' <id>` | DB noch nicht bereit, falsche `DATABASE_URL` |
| 502/503 vom Proxy | `docker compose ps app_blue app_green` | aktive Farbe ist gestoppt → `scripts/rollback.sh` oder `docker compose start app_<farbe>` |
| Nach Deployment Fehler | Grafana: Fehlerrate je `pool` | fehlerhafte Version → `scripts/rollback.sh` (Blue-Green) |
| Prometheus-Target rot | Prometheus → Status → Targets | Container down/umbenannt; `docker network inspect minikos_kos` |
| Kein Dashboard | Grafana → Dashboards → Mini-KOS | Profil `monitoring` nicht gestartet; Mount-Fehler: `docker compose logs grafana` |
| ELK-Container beenden sich | `docker compose logs elasticsearch` | zu wenig RAM / `vm.max_map_count` |
| Plattenplatz knapp | `docker system df`; `du -sh .backup` | Images/Volumes/Backups aufräumen: `docker image prune`, `KEEP_DAYS` senken |

## Wartung

- **Images aufräumen:** `docker image prune -f` (nach erfolgreichem Deployment).
- **Prometheus-Regeln neu laden:** `curl -X POST localhost:9090/-/reload`.
- **Grafana-Passwort ändern:** `GRAFANA_PASSWORD` in `.env` bzw. Vault setzen, `docker compose --profile monitoring up -d grafana`.
- **Dependencies aktualisieren:** `requirements.txt` anpassen → Pipeline (Tests + Trivy) entscheidet.
