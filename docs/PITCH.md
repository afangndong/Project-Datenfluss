# Mini-KOS in 3 Minuten

## Kernaussage
„Mini-KOS ist ein kleines Klinik-Informationssystem, an dem ich die **komplette On-Premise-Lieferkette** gebaut habe: vom Commit über Tests, Image-Build und Security-Scan bis zum Rollout per Ansible mit wählbarer Strategie – inklusive Monitoring, Logging, Backup und Restore-Test.“

## Ablauf (ca. 3 min)
1. **Problem (20 s):** Software im Klinikumfeld muss verfügbar, nachvollziehbar und datenschutzkonform ausgeliefert werden – ohne Cloud, ohne Kubernetes.
2. **Pipeline (50 s):** GitLab CI: Lint und Tests parallel (`needs`), pip-Cache über Hash der requirements, Docker-Layer-Cache über die Registry, Trivy blockiert bei HIGH/CRITICAL, Test automatisch, Produktion manuell mit Vier-Augen-Freigabe (Protected Environment).
3. **Betrieb (50 s):** Ansible provisioniert Docker-Hosts idempotent und rollt host-weise aus (`serial: 1`). Vier Strategien: Rolling (Standard), Blue-Green (Sofort-Rollback), Canary (Risiko begrenzen), Recreate (Wartungsfenster). nginx schaltet per Variable um – ohne Neustart.
4. **Beobachtbarkeit (40 s):** Prometheus/Grafana (RED-Metriken, Fachkennzahlen), Alertmanager mit Routing nach Schweregrad und Unterdrückung, ELK mit strukturierten Logs und Request-ID; Alarme verweisen auf Runbooks.
5. **Sicherheit & Daten (20 s):** keine Personendaten in Logs, Schwärzung als Netz, Backups mit Integritätsprüfung und **Restore-Test**, Geheimnisse im Vault.

## Demo-Reihenfolge (live)
1. GUI zeigen → System-Reiter („Bedient von: blue“).
2. `make bluegreen TAG=…` → Seite neu laden: „Bedient von: green“ → `make rollback`.
3. `make alerts-errors` → Prometheus-Alerts → Webhook-Log.
4. `make backup restore-test` → „RESTORE-TEST BESTANDEN“.

## Typische Rückfragen
| Frage | Antwort in Stichpunkten |
|---|---|
| Warum Compose statt Kubernetes? | Zielumgebung On-Premise mit Docker; weniger Betriebsaufwand. Bei mehreren Hosts/Autoscaling wäre Orchestrierung der nächste Schritt. |
| Wie vermeidest du Downtime bei DB-Änderungen? | Expand/Contract: erst kompatibel erweitern, später aufräumen; sonst Recreate im Wartungsfenster mit Backup. |
| Was ist der Unterschied Ansible ↔ Bash? | Ansible beschreibt den **Soll-Zustand** und ist idempotent (`apt: state=present`, `systemd: state=started`); Bash führt Befehle aus und prüft nichts von allein. |
| Wie weißt du, dass das Backup funktioniert? | Restore-Test in temporärer DB, Vergleich der Zeilenzahlen, Metrik + Alert bei Alter > 26 h. |
| Wie gehst du mit Alarmflut um? | Symptom-Alarme, `for:`-Dauer, Gruppierung, Inhibit-Regeln, Schweregrade mit unterschiedlichen Empfängern. |
| Wie schützt du Patientendaten im Monitoring? | Gar nicht erst loggen (nur IDs/Pfade), Logstash-Schwärzung, kurze Retention, RBAC; keine Daten an externe Dienste. |
| Was würdest du als Nächstes verbessern? | Benutzer-/Rollenkonzept (OIDC), TLS, Audit-Trail, Alembic-Migrationen, verschlüsselte Offsite-Backups. |
| Was ist **nicht** getestet? | Siehe README „Teststatus“: Container-Betrieb und echte GitLab-Pipeline wurden nicht live ausgeführt. |
