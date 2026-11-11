# Sicherheit und Datenschutz

Mini-KOS verarbeitet im Demo-Betrieb ausschließlich **fiktive Daten**. Klinikdaten sind besondere Kategorien personenbezogener Daten (Art. 9 DSGVO). Dieses Dokument trennt, was **umgesetzt** ist, was **bewusst vereinfacht** wurde und was vor einem Echtbetrieb **zwingend** nachzuholen wäre.

## Umgesetzt

| Maßnahme | Wo |
|---|---|
| Container läuft als non-root (UID 10001), keine Build-Tools im Runtime-Image | `Dockerfile` |
| Image-Scan als Pipeline-Gate (HIGH/CRITICAL) + Config-Scan | `.gitlab-ci.yml`, `.trivyignore` |
| Eingabevalidierung (Pydantic): Längen, Datumslogik, Enums | `app/schemas.py` |
| SQL-Injection-Schutz durch ORM/parametrisierte Abfragen | `app/routers/*` |
| **XSS-Schutz in der GUI:** Daten ausschließlich per `textContent`, nie `innerHTML` | `app/static/app.js` |
| Schreibschutz per API-Key (konstante Vergleichszeit) | `app/security.py` |
| **Keine Personendaten in Logs** (nur Pfad ohne Query-String, IDs, Status) | `app/main.py`, `logging_conf.py` |
| Logstash-Schwärzung von Datums-/E-Mail-Mustern als Sicherheitsnetz | `elk/logstash/pipeline/logstash.conf` |
| Log-Retention 14 Tage (Datenminimierung) | `elk/setup_ilm.sh` |
| Geheimnisse nur über Vault/Umgebung, Rechte 0600, `.gitignore` | `ansible/`, `.gitignore` |
| Prod-Playbook bricht bei Platzhalter-Geheimnissen ab | `playbooks/deploy.yml` |
| Störungs-Endpunkte in Prod abgeschaltet | `app/routers/system.py` |
| Metrics-Endpunkt am Proxy gesperrt | `nginx/conf.d/default.conf` |
| Alerts enthalten keine Patientendaten | `monitoring/alert_rules.yml` |
| Backups mit Integritätsprüfung und Restore-Test | `scripts/backup.sh`, `restore_test.sh` |
| Vier-Augen-Prinzip für Produktion (GitLab-Konfiguration) | [CI-CD](CI-CD.md) |

## Bewusste Demo-Vereinfachungen (nicht für Echtbetrieb)

| Vereinfachung | Risiko | Echtbetrieb |
|---|---|---|
| Kein Benutzer-/Rollenkonzept, nur gemeinsamer API-Key | jeder mit Key darf alles; Lesen ist offen | SSO/OIDC (Keycloak/LDAP), Rollen, Mandanten-/Stationsfilter |
| Kein Audit-Trail (wer sah/änderte welche Akte) | keine Nachvollziehbarkeit | unveränderlicher Zugriffs-/Änderungslog |
| Kein TLS im Proxy | Klartext im Netz | TLS 1.2+ im nginx, interne CA/Zertifikate |
| Standardpasswörter (Postgres, Grafana, Unleash) | triviale Übernahme | starke Passwörter aus dem Vault, Netzsegmentierung |
| Elasticsearch/Kibana ohne Security | offene Logdaten | X-Pack Security/Rollen, Netz begrenzen |
| Backups unverschlüsselt, am selben Host | Datenabfluss/Totalverlust | Verschlüsselung (z. B. age/GPG), Kopie auf getrenntes System |
| `create_all` statt Migrationen | unkontrollierte Schemaänderung | Alembic, versionierte Migrationen |
| Kein Rate-Limiting / keine WAF | Missbrauch, Brute-Force | Limits im Proxy, WAF |
| Docker-Socket in Filebeat gemountet | weitreichender Hostzugriff bei Kompromittierung | Log-Treiber/Dateipfade statt Socket, Rootless-Docker |
| Unleash-Auswertung vereinfacht (nur „enabled“) | Strategien werden ignoriert | offizielles Unleash-Client-SDK |

## Vor dem Einsatz mit echten Daten (Checkliste)

- [ ] Rechtsgrundlage, Verzeichnis der Verarbeitungstätigkeiten, Datenschutz-Folgenabschätzung, Auftragsverarbeitung
- [ ] Berechtigungskonzept, Authentifizierung (ggf. 2FA), Protokollierung aller Zugriffe
- [ ] Verschlüsselung in Transit (TLS) und at Rest (Platte/DB/Backups)
- [ ] Löschkonzept und Aufbewahrungsfristen
- [ ] Notfallkonzept mit gemessenen RPO/RTO, regelmäßige Restore-Tests
- [ ] Penetrationstest, Härtung des Hosts, Patch-Prozess
- [ ] Regulatorik prüfen (u. a. Medizinprodukte-Einstufung, KRITIS/B3S Krankenhaus, BSI IT-Grundschutz)

## Externe Dienste und KI

Metriken/Logs dieses Projekts enthalten bewusst keine Patientendaten. Dennoch gilt: **Patientendaten dürfen nie an externe APIs (auch KI-Dienste) gesendet werden**, außer es liegen Auftragsverarbeitungsvertrag und eine geprüfte Rechtsgrundlage vor. Technische Metadaten (z. B. Trivy-Berichte, aggregierte Metriken) sind unkritischer, sollten aber vor der Weitergabe geprüft werden.
