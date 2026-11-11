# Monitoring, Alarmierung und Logging

Ziel: Störungen **vor den Nutzern** bemerken, nach Dringlichkeit unterscheiden und Ursachen schnell finden – ohne Alarmflut.

## Drei Säulen

| Säule | Werkzeug | Beantwortet |
|---|---|---|
| Metriken | Prometheus + Grafana | *Wie geht es dem System? Seit wann ist es schlechter?* |
| Logs | Filebeat → Logstash → Elasticsearch → Kibana | *Was ist genau passiert?* (Fehlermeldung, Request-ID) |
| Alarme | Alertmanager → Webhook (Slack optional) | *Wer muss jetzt handeln?* |

(Traces/OpenTelemetry sind nicht Teil der Demo; bei mehreren Services wäre Tempo die natürliche Erweiterung.)

## Metriken der Anwendung (`/metrics`)

| Metrik | Typ | Bedeutung |
|---|---|---|
| `minikos_http_requests_total{method,path,status}` | Counter | Rate und Fehler (Pfad = Route-Vorlage, z. B. `/api/patients/{patient_id}` → niedrige Kardinalität) |
| `minikos_http_request_duration_seconds` | Histogram | Latenz-Perzentile (p50/p95/p99) |
| `minikos_http_requests_in_progress` | Gauge | gleichzeitige Requests |
| `minikos_db_up` | Gauge | 1 = App erreicht die Datenbank |
| `minikos_patients_total`, `minikos_active_stays`, `minikos_open_appointments` | Gauge | Fachkennzahlen |

Weitere Quellen: **cAdvisor** (Container-CPU/RAM), **node-exporter** (Host-Disk/RAM + Backup-Textfile), **postgres-exporter** (Verbindungen, Transaktionen).

## Alert-Regeln (`monitoring/alert_rules.yml`)

| Alert | Bedingung | Dauer | Schwere | Runbook |
|---|---|---|---|---|
| `AppDown` | `up{job="minikos"} == 0` | 1 min | critical | Szenario 1 |
| `AppAbsent` | keine Instanz bekannt | 2 min | critical | Szenario 1 |
| `HighErrorRate` | > 5 % HTTP-5xx (5 min) | 2 min | critical | Szenario 2 |
| `HighLatency` | p95 > 1 s | 5 min | warning | Szenario 3 |
| `DatabaseUnreachableFromApp` | `minikos_db_up == 0` | 1 min | critical | Szenario 4 |
| `PostgresDown` | `pg_up == 0` | 1 min | critical | Szenario 4 |
| `PostgresTooManyConnections` | > 80 Verbindungen | 5 min | warning | – |
| `ContainerMemoryHigh` | > 90 % des Limits | 5 min | warning | – |
| `DiskSpaceLow` | < 15 % frei | 10 min | warning | – |
| `BackupTooOld` | letztes Backup > 26 h | 10 min | critical | [BETRIEB](BETRIEB.md#backup--restore) |
| `BackupMetricMissing` | noch nie ein Backup gemeldet | 30 min | warning | – |

Die `for:`-Dauer verhindert Alarme bei Sekunden-Ausreißern. Jede Regel verlinkt über `annotations.runbook` die passende Anleitung.

### Warum feste Schwellen und kein „Alles melden“?
Jeder Alarm muss **eine Handlung auslösen**. Deshalb: wenige, symptomorientierte Regeln (Nutzer spüren Fehler/Langsamkeit), Ursachen-Metriken (CPU, Verbindungen) nur als `warning`. Ein Ausbau um Anomalie-Erkennung (rollender Mittelwert ± Standardabweichung statt fester Grenze) ist sinnvoll, wenn Lastmuster stark schwanken.

## Alertmanager

```
route (Standard: team-default)
 ├─ severity=critical → team-critical  (group_wait 10 s, Wiederholung stündlich)
 └─ severity=warning  → team-default   (gebündelt, Wiederholung alle 4 h)
inhibit: AppAbsent unterdrückt Warnungen (kein Folgealarm-Sturm)
```

Beide Empfänger rufen den `alert-webhook` auf (`/alert?prio=critical|warning`): dieser schreibt eine JSON-Zeile ins Log (landet damit auch in ELK) und sendet optional an Slack (`SLACK_WEBHOOK_URL` in `.env`). Im Echtbetrieb zusätzlich E-Mail/Pager-Empfänger ergänzen (`email_configs`, PagerDuty/Opsgenie). **Alerts enthalten nur technische Labels – nie Patientendaten.**

## Grafana

Dashboard **„Mini-KOS – Überblick“** (Ordner *Mini-KOS*, automatisch provisioniert, `monitoring/grafana/dashboards/minikos.json`):

- Kopfzeile: Instanzen UP · Datenbank · Patienten · Aufenthalte · offene Termine · Alter des letzten Backups
- Requests/s je Instanz (`pool`), Fehlerrate, Latenz p50/p95/p99
- Requests je Route und HTTP-Status
- Container-CPU/-RAM, PostgreSQL-Verbindungen

Beim Blue-Green/Canary sieht man neue und alte Version nebeneinander (Label `pool`). Datenquellen: Prometheus (Standard) und Elasticsearch (Logs, nur mit Profil `elk`).

## Logging (ELK)

```
Container stdout (JSON) → Filebeat (Docker-Autodiscovery) → Logstash → Elasticsearch (Index minikos-logs-YYYY.MM.dd) → Kibana
```

- **Strukturiert:** jede Zeile ist JSON mit `level, service, instance, version, path, status, duration_ms, request_id`.
- **Request-ID:** nginx vergibt `X-Request-ID`, die App loggt sie und gibt sie zurück → ein Request ist über Proxy- und App-Logs verfolgbar.
- **Schwärzung (Datenschutz-Netz):** Logstash ersetzt Datumsformate (Geburtsdaten) und E-Mail-Adressen durch `[DATUM]` / `[EMAIL]`. Das ist ein *Sicherheitsnetz* – die App darf ohnehin keine Personendaten loggen.
- **Retention:** `elk/setup_ilm.sh` legt eine ILM-Richtlinie an (Löschung nach 14 Tagen).
- **Kibana einrichten:** Stack Management → Data Views → `minikos-logs-*`, Zeitfeld `@timestamp`. Nützliche Filter: `level:ERROR`, `status:[500 TO 599]`, `request_id:<id>`.

## Alarmkette testen

```bash
make up up-monitoring
make alerts-errors      # 5 min HTTP-500 → HighErrorRate geht nach ~2 min auf „Firing“
make alerts-down        # App stoppen → AppDown/AppAbsent
docker compose logs -f alert-webhook
```
Prüfen: Prometheus → Alerts (Pending → Firing) · Alertmanager (Gruppierung) · Webhook-Log. Wiederherstellen: `docker compose start app_blue`.
