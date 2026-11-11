# Support-Szenarien (Übung)

Vier typische Störungen mit Symptomen, Auslöser für die Simulation, Diagnosepfad und Lösung. Zum Üben **laut durchsprechen**: *Was sehe ich? Was ist meine Hypothese? Wie prüfe ich sie? Wie stelle ich her? Wie verhindere ich Wiederholung?*

Vorbereitung: `make up up-monitoring` (+ optional `make up-elk`), `make seed`, Grafana und Prometheus-Alerts im Browser offen lassen.

---

<a id="szenario-1"></a>
## Szenario 1 – Die Anwendung ist nicht erreichbar

**Meldung vom Anwender:** „Die GUI lädt nicht / Fehlerseite.“
**Auslöser:** `make alerts-down` (stoppt die aktive App-Instanz).
**Alarm:** `AppDown` bzw. `AppAbsent` (critical).

**Diagnose**
1. `make ps` – läuft `app_blue`? Läuft `proxy`?
2. `curl -i localhost:8080/healthz` – Proxy lebt? (`ok` = ja → Problem liegt dahinter; 502 = App weg)
3. `docker compose logs --tail 50 app_blue` – abgestürzt? Ursache (Exception, OOM)?
4. `docker inspect app_blue | grep -i -A5 oom` – wurde der Container wegen Speichers beendet?
5. Grafana: seit wann Kurve bei 0? Passt der Zeitpunkt zu einem Deployment?

**Lösung**
- Gestoppt: `docker compose start app_blue` → `scripts/smoke_test.sh`.
- Nach Deployment kaputt: `scripts/rollback.sh` (Blue-Green) bzw. vorherigen Tag erneut ausrollen.
- OOM: Speicherlimit prüfen (`docker-compose.prod.yml`), Ursache suchen (Speicherleck? Lastspitze?).

**Nachbereitung:** Warum wurde es nicht vor den Nutzern bemerkt? (Alarm kam nach ~1 min → akzeptabel.) Restart-Policy `unless-stopped` greift nur bei Absturz, nicht bei manuellem Stopp.

---

<a id="szenario-2"></a>
## Szenario 2 – Viele Fehler (HTTP 500)

**Meldung:** „Beim Speichern kommt manchmal ein Fehler.“
**Auslöser:** `make alerts-errors` (oder in der GUI: System → „HTTP-500 auslösen“).
**Alarm:** `HighErrorRate` (> 5 %, critical).

**Diagnose**
1. Grafana „Fehlerrate“ + „HTTP-Status“: betrifft es alle Routen oder nur eine? Nur eine Instanz (`pool`)?
2. Kibana: `level:ERROR` im Zeitraum – welche Exception, welcher `path`, welche `request_id`?
3. Mit der `request_id` den kompletten Request in Proxy- und App-Log nachverfolgen.
4. Korrelation: Beginn = Deployment? (`/api/version` → `git_sha`). Datenbankprobleme? (`pg_up`, `minikos_db_up`)

**Lösung**
- Fehler durch neue Version → Rollback (Blue-Green) oder Canary abbrechen (`make canary-abort`).
- Fehler nur bei einem Feature → **Feature Flag abschalten** (Unleash/`FEATURE_*`), ohne Deployment.
- Datenproblem → siehe Szenario 4.

**Nachbereitung:** Fehlt ein Test für den Fall? Hätte ein Canary den Fehler früher gezeigt?

---

<a id="szenario-3"></a>
## Szenario 3 – Die Anwendung ist langsam

**Meldung:** „Alles dauert ewig.“
**Auslöser:** `scripts/trigger_alerts.sh slow` (oder GUI: „Langsame Antwort“).
**Alarm:** `HighLatency` (p95 > 1 s, warning).

**Diagnose**
1. Grafana „Latenz p50/p95/p99“: Sind alle Routen betroffen oder eine? (Panel „Requests nach Route“)
2. Ressourcen: Container-CPU/-RAM (cAdvisor-Panels), Host-Disk (`DiskSpaceLow`?).
3. Datenbank: Panel „PostgreSQL-Verbindungen“; `docker compose exec db psql -U minikos -c "select * from pg_stat_activity where state <> 'idle';"`.
4. Last: ungewöhnlich viele Requests/s? Ein einzelner Client? (Kibana: Aggregation nach `path`).

**Lösung**
- Lastspitze → Replikas erhöhen: `scripts/deploy_rolling.sh <aktueller-tag> 4`.
- Langsame Abfrage → Index ergänzen, Abfrage optimieren (Expand/Contract beachten).
- Ressourcenmangel → Limits/Host vergrößern, Aufräumen (`docker system df`).

**Nachbereitung:** Schwelle sinnvoll? Zeitaufwand bis zur Ursache? Dashboard um ein fehlendes Panel ergänzen.

---

<a id="szenario-4"></a>
## Szenario 4 – Datenbankproblem / Datenverlust

**Meldung:** „Seit heute Morgen sind Patienten verschwunden“ oder „Fehler 503 beim Öffnen“.
**Auslöser (Variante A, DB weg):** `docker compose stop db`.
**Auslöser (Variante B, Datenverlust):** in dev: `docker compose exec db psql -U minikos -c "delete from appointments"`.
**Alarme:** `PostgresDown`, `DatabaseUnreachableFromApp` (critical); Variante B alarmiert **nicht** → Meldung kommt vom Anwender.

**Diagnose**
1. `curl localhost:8080/ready` → 503 = App erreicht DB nicht.
2. `docker compose logs --tail 50 db` – Absturz? Platte voll? Rechte?
3. `docker compose ps db` – healthy? Volume vorhanden (`docker volume ls | grep pgdata`)?
4. Bei Datenverlust: **nichts weiter ändern**, Zeitpunkt eingrenzen (Kibana: DELETE-Requests, `path`, `status`).

**Lösung**
- DB gestoppt: `docker compose start db` → `/ready` wird wieder 200, App heilt sich selbst (`pool_pre_ping`).
- Datenverlust: Backup wählen, das **vor** dem Zeitpunkt liegt:
  1. `scripts/restore_test.sh <datei>` – Backup ist brauchbar?
  2. `scripts/restore.sh <datei> --yes` – Live-Restore (App wird kurz gestoppt).
  3. `scripts/smoke_test.sh`, Stichproben in der GUI.
- Dokumentieren, welche Daten seit dem Backup fehlen (RPO = Zeit seit letztem Backup).

**Nachbereitung:** RPO/RTO gemessen? Restore-Test regelmäßig? Backup liegt auch auf einem **anderen** System? Schutz vor Löschungen (Rechte, Vier-Augen-Prinzip)?

---

## Allgemeines Vorgehen (Merkschema)

1. **Auswirkung klären:** Wer ist betroffen, seit wann, wie schlimm? (Priorität festlegen)
2. **Stabilisieren vor Ursachenforschung:** Rollback/Flag aus/Neustart, wenn schnell und sicher möglich.
3. **Ursache eingrenzen:** Metriken → Logs → Änderungen (Deployments, Flags, Konfiguration).
4. **Kommunizieren:** Status an Betroffene, Zeitprognose, Abschlussmeldung.
5. **Nachbereitung (ohne Schuldzuweisung):** Zeitleiste, Ursache, was hat gefehlt (Alarm, Test, Doku), konkrete Maßnahmen mit Verantwortlichen.
