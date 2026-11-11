#!/usr/bin/env bash
# Verbindet das lokale Repository mit GitHub und pusht main (+ Tags).
# Aufruf:  scripts/push_to_github.sh <owner/repo> [--create]
#   --create   legt das Repository (privat) per GitHub-CLI an (`gh auth login` vorher nötig)
# Ohne --create muss das (leere) Repository auf github.com schon existieren.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REPO="${1:?Aufruf: $0 <owner/repo> [--create]}"
CREATE="${2:-}"

git rev-parse --git-dir >/dev/null 2>&1 || { echo "Kein Git-Repository – erst 'git init' bzw. das mitgelieferte .git verwenden" >&2; exit 1; }
git branch -M main

if [[ "$CREATE" == "--create" ]]; then
  command -v gh >/dev/null || { echo "GitHub-CLI 'gh' fehlt (https://cli.github.com)" >&2; exit 1; }
  gh auth status >/dev/null 2>&1 || { echo "Bitte erst anmelden: gh auth login" >&2; exit 1; }
  gh repo create "$REPO" --private --source=. --remote=origin --push
else
  git remote get-url origin >/dev/null 2>&1 && git remote set-url origin "git@github.com:${REPO}.git" \
    || git remote add origin "git@github.com:${REPO}.git"
  git push -u origin main
fi
git push --tags 2>/dev/null || true

cat <<MSG

Gepusht: https://github.com/${REPO}
Die CI (Lint, Tests, Build, Trivy) startet automatisch: https://github.com/${REPO}/actions

Optional einrichten (Settings des Repositories):
  1. Branch protection für main: Pull Request + Status-Checks (Lint, Tests, Build) verlangen, 1 Freigabe.
  2. Environments: "test" und "production" anlegen; bei "production" 'Required reviewers' setzen (Vier-Augen-Prinzip).
  3. Deployment aktivieren: Variable DEPLOY_ENABLED=true und Secrets ANSIBLE_SSH_KEY, SSH_KNOWN_HOSTS,
     ANSIBLE_VAULT_PASS; Self-hosted Runner mit Label 'on-prem' registrieren. Details: docs/CI-CD.md
MSG
