# Architektur

## Überblick

Mini-KOS ist ein **Single-Tenant-On-Premise-System**: ein Docker-Host (oder wenige), keine Cloud-Dienste, keine Kubernetes-Abhängigkeit.
Alles wird über Compose-Dateien, Ansible und GitLab CI reproduzierbar ausgerollt.

```
            ┌───────────────────────────────────────────────────────────┐
 Browser ──►│ nginx (Proxy)  :8080                                      │
            │   split_clients → app_blue | app_green | app_canary       │
            └───────────┬───────────────────────────────────────────────┘
                        ▼
            ┌───────────────────┐        ┌──────────────┐
            │ FastAPI (2 Worker)│───────►│ PostgreSQL 16│
            │ /api /health /ready│       └──────────────┘
            │ /metrics  GUI      │
            └─────┬───────┬─────┘
       Metriken   │       │ JSON-Logs (stdout)
                  ▼       ▼
          Prometheus    Filebeat → Logstash → Elasticsearch → Kibana
              │  ▲
      Alertmanager│ Grafana
              ▼
        alert-webhook (Log + optional Slack)
```

## Komponenten

| Komponente | Technik | Aufgabe |
|---|---|---|
| App | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 | Fachlogik, REST-API, GUI-Auslieferung |
| Datenbank | PostgreSQL 16 (SQLite nur lokal/Tests) | Persistenz |
| Proxy | nginx 1.27 | Einstiegspunkt, **Traffic-Steuerung** für Blue-Green/Canary, DNS-basiertes Rolling |
| Metriken | Prometheus 2.55, cAdvisor, node-exporter, postgres-exporter | Zeitreihen, Alarmregeln |
| Alarme | Alertmanager 0.27 + eigener Webhook | Gruppierung, Routing nach Schweregrad, Unterdrückung |
| Dashboards | Grafana 11 (provisioniert) | Visualisierung |
| Logs | Filebeat, Logstash, Elasticsearch, Kibana 8.15 | zentrale Suche, Schwärzung, Retention |
| Flags | Unleash 6 (optional) | Funktionen ohne Deployment schalten |
| Provisionierung | Ansible | Host-Setup, Deployment, Cron |
| CI/CD | GitLab CI, Registry, Trivy | Qualität, Build, Scan, Auslieferung |

## Datenmodell

```
Patient 1 ──< Aufenthalt (Station, Zimmer, Aufnahme, Entlassung?, Diagnose)
Patient 1 ──< Termin     (Zeitpunkt, Art, Status: geplant|erledigt|abgesagt)
```

Löschen eines Patienten kaskadiert auf Aufenthalte und Termine. `Entlassung = NULL` bedeutet „aktuell auf Station“.
Die Fallnummer (`F000042`) wird beim Anlegen aus der ID erzeugt.

## Wie das Routing funktioniert (Kernidee der Deployment-Strategien)

Der Proxy kennt **keine festen Upstreams**. Er fragt den Docker-DNS (`resolver 127.0.0.11 valid=5s`) zur Laufzeit ab und nimmt den Poolnamen aus einer Variablen:

```nginx
split_clients "${remote_addr}${http_user_agent}" $minikos_pool {
    20% "app_canary";
    *   "app_green";
}
location / { proxy_pass http://$minikos_pool:8000; }
```

Die Datei `nginx/conf.d/00-routing.conf` wird von `scripts/lib.sh` (`write_routing`) geschrieben; danach `nginx -t` und `nginx -s reload` (ohne Verbindungsabbruch).
Folgen:

- nginx startet auch, wenn `app_green`/`app_canary` gar nicht laufen.
- **Rolling**: mehrere Replikas desselben Service teilen sich einen DNS-Namen → nginx verteilt per Round-Robin, ein Austausch einzelner Container ist unsichtbar.
- **Canary** ist „sticky“: derselbe Client (IP + User-Agent) landet immer im selben Pool.

Prometheus findet dieselben Instanzen per `dns_sd_configs` (blue, green, canary) – neue Replikas erscheinen automatisch, Label `pool` unterscheidet sie in Grafana.

## Zustand der Deployments

`.deploy/state.env` (auf dem Host, nicht im Git) speichert: aktive Farbe, vorherige Farbe, Image-Tags je Farbe/Canary, Canary-Prozent.
Verlorener Zustand ist unkritisch: die Skripte legen bei fehlender Datei den Standard (`blue`, Tag `local`) an.

## Entwurfsentscheidungen

| Entscheidung | Begründung | Alternative |
|---|---|---|
| Docker Compose statt Kubernetes | Zielumgebung ist On-Premise mit Docker; weniger bewegliche Teile | K8s/Nomad bei mehreren Hosts |
| Ein Compose-File mit **Profilen** | `make up` bleibt klein, Monitoring/ELK/Flags zuschaltbar | mehrere Compose-Dateien |
| Overrides je Umgebung | dev (Live-Reload), test (flüchtige DB), prod (Limits, Log-Rotation) | Helm-ähnliche Templates |
| nginx-Variablen + `split_clients` | Umschalten ohne Neustart und ohne Zusatztool (Traefik/HAProxy) | Traefik mit Labels |
| `create_all` statt Alembic | Demo bleibt überschaubar | Alembic-Migrationen (Pflicht im Echtbetrieb) |
| Synchrones SQLAlchemy | einfacher, für Demo-Last ausreichend | async + asyncpg |
| API-Key statt Benutzerverwaltung | zeigt Schreibschutz ohne IAM-Aufbau | OIDC/Keycloak/LDAP |
| Logs nur auf stdout | 12-Factor; Filebeat sammelt | Log-Dateien im Container |
| Kein `innerHTML` in der GUI | Patientennamen sind Nutzereingaben → XSS-Schutz | Framework mit Auto-Escaping |

## Grenzen

- Ein Datenbank-Container ohne Replikation → Hochverfügbarkeit der DB ist **nicht** abgedeckt (Backup + Restore-Test ersetzen sie nicht).
- Blue-Green/Rolling setzen **abwärtskompatible Datenbankänderungen** voraus (siehe DEPLOYMENT-STRATEGIEN).
- Keine Benutzer-/Rollenverwaltung, kein Audit-Trail, keine TLS-Terminierung im Demo-Proxy.
