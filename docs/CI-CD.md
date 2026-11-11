# CI/CD mit GitHub Actions und GitLab CI

Beide Systeme führen denselben Ablauf aus und nutzen dieselben `make`-Ziele und Skripte. Wo das Repository liegt, entscheidet, welche Datei läuft:

| | GitHub | GitLab |
|---|---|---|
| Datei | `.github/workflows/ci.yml`, `deploy.yml`, `security.yml` | `.gitlab-ci.yml` |
| Registry | ghcr.io (`GITHUB_TOKEN`, keine Einrichtung nötig) | GitLab Container Registry |
| Vier-Augen-Prinzip | Environment „production“ mit *Required reviewers* | Protected Environment + Approval Rules |
| Prod-Freigabe | manuell: Actions → *Deploy* → *Run workflow* | manueller Job `deploy:prod` |
| Lokal prüfen | `make ci` (oder `make act JOB=test`) | `make ci` |

## GitHub Actions

### Workflows

| Datei | Auslöser | Inhalt |
|---|---|---|
| `ci.yml` | Push auf `main`, Tags `v*`, Pull Requests | 5 Lint-Jobs und Tests parallel → Build → **Trivy-Scan vor dem Push** → Push nach ghcr.io → optional Deploy auf Test |
| `deploy.yml` | aufgerufen von `ci.yml` oder manuell | Ansible-Deployment (Umgebung, Image-Tag und Strategie wählbar) auf einem Self-hosted Runner |
| `security.yml` | montags 03:17 UTC, manuell | Trivy auf Repository (Abhängigkeiten, Konfiguration) und auf das veröffentlichte Image |
| `dependabot.yml` | wöchentlich | Update-PRs für pip, Docker-Basisimage und Actions |

Bei Pull Requests wird das Image gebaut und gescannt, aber **nicht** gepusht. Auf `main` wird erst nach bestandenem Scan gepusht (Tags `<kurzhash>`, `latest`, `cache`). Layer-Cache: `type=gha`; pip-Cache: `setup-python` mit Hash von `requirements-dev.txt`.

### Einrichtung (einmalig)

1. Repository anlegen und pushen: `make github-push REPO=deinname/mini-kos CREATE=1`
   (oder manuell: Repository auf github.com anlegen, dann `make github-push REPO=deinname/mini-kos`).
2. **Settings → Actions → General → Workflow permissions:** „Read and write permissions“ (damit `GITHUB_TOKEN` nach ghcr.io pushen darf; die Workflows fordern `packages: write` selbst an).
3. **Branch protection für `main`:** Pull Request verlangen, Status-Checks *Lint*, *Tests* und *Build* als Pflicht, mindestens 1 Freigabe.
4. **Deployment auf eigene Server aktivieren** (erst wenn Server und Runner bereitstehen):
   - **Settings → Environments:** `test` und `production` anlegen; bei `production` *Required reviewers* eintragen.
   - **Settings → Secrets and variables → Actions:** Secrets `ANSIBLE_SSH_KEY`, `SSH_KNOWN_HOSTS`, `ANSIBLE_VAULT_PASS`; Variable `DEPLOY_ENABLED` = `true`.
   - Self-hosted Runner mit Label `on-prem` im Firmennetz registrieren (Settings → Actions → Runners).
   - Das Image in ghcr.io für die Server lesbar machen: Pull-Zugang (PAT mit `read:packages`) in `ansible/inventories/<env>/vault.yml` als `vault_registry_user` / `vault_registry_password`.

Ohne `DEPLOY_ENABLED=true` bleiben die Deploy-Jobs aus – Lint, Tests, Build und Scan laufen trotzdem, die Pipeline ist also auch ohne Server grün.

### Produktion ausrollen

*Actions → Deploy → Run workflow*: Umgebung `production`, Image-Tag (Kurzhash des CI-Laufs), Strategie wählen. Der Job wartet auf die Freigabe der Reviewer, läuft dann host-weise per Ansible und endet mit Gesundheitsprüfung und Rauchtest.

## GitLab CI


## Pipeline-Übersicht

```
lint:ruff ─────┐
lint:shell     │
lint:dockerfile├─► build:image ─► scan:trivy ─► deploy:test (auto, main) ─► deploy:prod (manuell)
lint:yaml-ansible                                 deploy:review (MR, manuell) ─► stop:review
lint:prometheus│
test:pytest ───┘                                  report:cache (manuell/Schedule)
```

Alle Lint- und Test-Jobs haben `needs: []` und laufen **parallel** vom ersten Moment an; spätere Jobs hängen per `needs` nur an dem, was sie wirklich brauchen (DAG statt starrer Stage-Reihenfolge).

| Job | Prüft / tut | Bricht ab bei |
|---|---|---|
| `lint:ruff` | Stil, Bugs, Sicherheitsmuster (flake8-bandit), Formatierung | jedem Befund |
| `lint:shell` | shellcheck für alle Skripte | Warnung oder schlimmer |
| `lint:dockerfile` | hadolint | Regelverstoß (DL3008/DL3013 bewusst ignoriert) |
| `lint:yaml-ansible` | yamllint, `ansible-playbook --syntax-check`, Dashboard-JSON | Syntaxfehler |
| `lint:prometheus` | `promtool check rules` | ungültige Alert-Regel |
| `test:pytest` | Tests, Coverage, JUnit-Bericht im MR | fehlgeschlagener Test |
| `build:image` | BuildKit-Build, Push `:<sha>`, `:cache`, auf main `:latest` | Build-Fehler |
| `scan:trivy` | Image-Scan, **Gate: HIGH/CRITICAL (mit Fix verfügbar)** | Fund; JSON-Bericht als Artefakt |
| `deploy:test` | Ansible-Deployment auf Test (automatisch auf `main`) | Fehler im Playbook/Health-Check |
| `deploy:prod` | wie Test, aber **manuell** + `resource_group` | – |
| `deploy:review` / `stop:review` | temporäre Umgebung je Merge Request | – |
| `report:cache` | Cache-HIT/MISS-Auswertung (CSV + PNG) | – |

## Caching – zwei Ebenen

1. **pip-Cache (Job-Ebene):** `cache.key.files: [requirements.txt, requirements-dev.txt]` – solange sich die Abhängigkeiten nicht ändern, wird derselbe Cache wiederverwendet; bei Änderung entsteht automatisch ein neuer.
2. **Docker-Layer-Cache (Registry):** `docker pull $IMAGE:cache` + `--cache-from`; `requirements.txt` wird vor dem Code kopiert, damit der Dependency-Layer bei reinen Codeänderungen aus dem Cache kommt. Im Dockerfile zusätzlich `RUN --mount=type=cache` für pip.

Wirkung messen: `scripts/pipeline_cache_report.py` (siehe unten).

## Benötigte Variablen (Settings → CI/CD → Variables)

| Variable | Typ | Zweck |
|---|---|---|
| `ANSIBLE_SSH_KEY` | File, masked/protected | privater Schlüssel des Deploy-Users |
| `ANSIBLE_VAULT_PASS` | File, protected | Passwort für `vault.yml` |
| `SSH_KNOWN_HOSTS` | File | Host-Keys der Zielserver (`ssh-keyscan -H kos-prod-01`) |
| `DEPLOY_STRATEGY` | Variable | `rolling` (Standard) · `bluegreen` · `canary` · `recreate` – beim manuellen Start überschreibbar |
| `REPORT_TOKEN` | masked | Project-Access-Token (`read_api`) für `report:cache` |

`CI_REGISTRY*`, `CI_COMMIT_*` liefert GitLab selbst. Die Deploy-Jobs brauchen einen Runner mit Tag **`on-prem`** (Zugriff auf die Server).

## Vier-Augen-Prinzip (Konfiguration, kein Pipeline-Code)

In der GitLab-Oberfläche einstellen:

1. **Settings → Repository → Protected branches:** `main` – Push: niemand, Merge: Maintainer.
2. **Settings → Merge requests → Approval rules:** mindestens 1 Freigabe von jemand anderem als dem Autor; „Prevent approval by author“ aktivieren.
3. **Settings → CI/CD → Protected environments:** `production` – nur eine Genehmigergruppe darf `deploy:prod` auslösen (bei Premium zusätzlich *Required approvals*).
4. Geheimnisse (`ANSIBLE_*`) als **protected** markieren → nur auf geschützten Branches sichtbar.

## Trivy

- Gate: `--severity HIGH,CRITICAL --ignore-unfixed` – nur Funde, die man auch beheben könnte.
- Ausnahmen in `.trivyignore`, **jeweils mit Begründung und Prüfdatum**.
- Zusätzlich `trivy config .` (informativ) für Fehlkonfigurationen in Dockerfile/Compose.
- Der vollständige JSON-Bericht liegt 30 Tage als Artefakt vor.
- Empfehlung: nächtliche Schedule-Pipeline, damit *neu bekannte* CVEs in alten Images auffallen.

## Pipeline-Cache-Report

```bash
GITLAB_TOKEN=glpat-… python scripts/pipeline_cache_report.py --project 12345 --pipelines 20 --out reports
```

Holt die letzten erfolgreichen Pipelines, lädt die Job-Logs von `lint:ruff` und `test:pytest`, erkennt „Successfully extracted cache“ (HIT) bzw. „cache not found / No URL provided“ (MISS) und vergleicht die mittleren Laufzeiten. Ausgabe: `reports/cache_report.csv` und (mit `matplotlib`) `cache_report.png`.
Hinweis: Die Erkennung hängt an den Log-Texten des GitLab-Runners; bei Runner-Updates ggf. `HIT_MARKERS`/`MISS_MARKERS` im Skript anpassen (Tests: `tests/test_cache_report.py`).

## Lokal dasselbe wie die Pipeline

```bash
make lint test
docker build -t mini-kos:local .
trivy image --severity HIGH,CRITICAL mini-kos:local     # falls Trivy installiert
```

## Grenzen

Die GitHub-Workflows sind mit `actionlint` geprüft, die GitLab-Pipeline als YAML. **Keiner von beiden** wurde in einer echten Umgebung ausgeführt. Runner-Details (Docker-in-Docker-Rechte, Tags, Registry-Hostnamen, Image-Pfade in `ansible/inventories/*/group_vars/all.yml`) müssen an die eigene Umgebung angepasst werden – die Stellen sind mit `TODO` markiert.
