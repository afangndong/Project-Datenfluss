# Deployment-Strategien

Vier Wege, eine neue Version auszurollen – alle als Skript (`scripts/deploy_*.sh`), per `make` und per Ansible (`-e deploy_strategy=…`) nutzbar.

## Entscheidungshilfe

| | Downtime | Zusatz-Ressourcen | Rollback | Risiko für Nutzer | Geeignet für |
|---|---|---|---|---|---|
| **Recreate** | ja (Sekunden bis Minuten) | keine | neu deployen | alle betroffen | Wartungsfenster, inkompatible DB-Änderungen, Dev/Test |
| **Rolling** | nein | gering (1 Replika extra) | neu deployen (rückwärts rollen) | schrittweise, kurz gemischte Versionen | Standard für Prod bei kompatiblen Änderungen |
| **Blue-Green** | nein | doppelt (2 Umgebungen) | **sofort** (Umschalten) | alle auf einmal, aber vorab getestet | kritische Releases, schnelles Zurück gefordert |
| **Canary** | nein | gering | Canary verwerfen (Sekunden) | nur ein kleiner Anteil | riskante Änderungen, Verhalten unter echter Last prüfen |

Faustregel: *Standard = Rolling. Kritisch = Blue-Green. Unsicher = Canary → bei guten Metriken promoten. Wartungsfenster = Recreate.*

## Zustand

Skripte merken sich in `.deploy/state.env`, welche Farbe aktiv ist und welcher Tag wo läuft (`ACTIVE`, `PREVIOUS`, `BLUE_TAG`, `GREEN_TAG`, `CANARY_TAG`, `CANARY_PERCENT`).
Abbruchverhalten ist überall gleich: **wird die neue Version nicht „healthy“, bleibt die alte aktiv** und das Skript endet mit Fehler (CI-Job wird rot).

## Blue-Green

```bash
scripts/deploy_bluegreen.sh 1.4.0            # Tag/Version
scripts/deploy_bluegreen.sh 1.4.0 --stop-old # alte Farbe danach stoppen (spart Ressourcen, kein Sofort-Rollback mehr)
scripts/rollback.sh                          # zurück zur vorherigen Farbe
```

Ablauf:
1. Inaktive Farbe mit neuem Tag starten (`app_green`, wenn `blue` aktiv ist).
2. Warten, bis **alle** Container „healthy“ sind (Healthcheck = `/ready`, prüft DB).
3. Direkt im Docker-Netz `GET /api/version` an die neue Farbe (am Proxy vorbei).
4. `00-routing.conf` auf neue Farbe, `nginx -t`, `nginx -s reload`.
5. Gegenprobe: `X-Served-By`-Header über den Proxy muss die neue Farbe nennen, sonst automatisches Zurückschalten.
6. Zustand speichern; alte Farbe läuft weiter (für Rollback) oder wird gestoppt.

## Rolling

```bash
scripts/deploy_rolling.sh 1.4.0 2     # Ziel: 2 Replikas
```

Je alter Replika: (1) **einen neuen** Container mit neuem Image dazustarten (`--scale N+1 --no-recreate`), (2) auf „healthy“ warten, (3) den alten stoppen und entfernen, (4) kurz warten, bis nginx per DNS neu auflöst (5 s). Zum Schluss auf Zielzahl skalieren.
Wird ein neuer Container nicht gesund, wird er entfernt und das Skript bricht ab – die alten Replikas bedienen weiter.

*Beachten:* Während des Rollouts laufen beide Versionen parallel → API und DB-Schema müssen **abwärtskompatibel** sein.

## Canary

```bash
scripts/deploy_canary.sh 1.4.0 10   # 10 % des Traffics auf die neue Version
# … Grafana beobachten: Fehlerrate, Latenz, Requests je pool=app_canary …
scripts/deploy_canary.sh --promote  # gut → wird per Blue-Green zur Hauptversion
scripts/deploy_canary.sh --abort    # schlecht → Canary stoppen, Routing zurück
```

Die Verteilung nutzt `split_clients` über `IP + User-Agent` – ein Nutzer bleibt in seiner Gruppe. In der GUI (System → „Bedient von“) sieht man, welche Instanz antwortet.
Promotion-Kriterien (Beispiel): 30 Minuten lang Fehlerrate Canary ≤ Hauptversion, p95-Latenz höchstens +20 %, keine neuen Fehler in Kibana.

## Recreate

```bash
scripts/deploy_recreate.sh 1.4.0
```
Stoppt den aktiven Service, startet ihn neu, wartet auf „healthy“. Während dessen liefert der Proxy 502 – vorher ggf. das Banner-Flag `wartungshinweis` setzen.

## Datenbank-Änderungen (Expand/Contract)

Bei Blue-Green, Rolling und Canary sehen zwei Versionen dieselbe Datenbank. Daher in zwei Releases migrieren:

1. **Expand:** neue Spalte/Tabelle nullable hinzufügen; alte und neue Version laufen damit.
2. **Migrieren/umstellen:** Code schreibt in beide/neue Struktur, Daten umkopieren.
3. **Contract:** erst im Folgerelease alte Spalten entfernen.

Nicht rückwärtskompatible Änderung (Spalte umbenennen/löschen, Typ ändern) → **Recreate** im Wartungsfenster mit frischem Backup.
(Das Demo-Projekt nutzt `create_all`; für echte Migrationen Alembic einführen.)

## Feature Flags als Ergänzung

Funktionen lassen sich unabhängig vom Deployment schalten (Unleash oder `FEATURE_*`-Variablen): Code ausrollen, Funktion **aus**; später aktivieren – und bei Problemen ohne Rollback wieder abschalten. Siehe `app/flags.py`.

## Ansible

```bash
ansible-playbook -i inventories/prod playbooks/deploy.yml --ask-vault-pass \
  -e app_tag=ab12cd34 -e deploy_strategy=bluegreen
```
Das Playbook arbeitet Host für Host (`serial: 1`, `max_fail_percentage: 0`): scheitert Host 1, wird Host 2 nicht angefasst. Nach jedem Host: `/ready`-Prüfung und Rauchtest.
