#!/usr/bin/env bash
# ECHTER Restore in die Live-Datenbank (überschreibt Daten!). Stoppt die App währenddessen.
# Aufruf: scripts/restore.sh <backup-datei> --yes
source "$(dirname "$0")/lib.sh"
FILE="${1:?Aufruf: $0 <backup-datei> --yes}"
[[ "${2:-}" == "--yes" ]] || die "Sicherheitsabfrage: bitte mit --yes bestätigen (überschreibt die Live-DB)"
[[ -f "$FILE" ]] || die "Datei nicht gefunden: $FILE"
PGUSER="${POSTGRES_USER:-minikos}"; PGDB="${POSTGRES_DB:-minikos}"
load_state
log "Stoppe Apps …"; compose stop "app_${ACTIVE}" 2>/dev/null || true
log "Spiele $FILE ein …"
gunzip -c "$FILE" | compose exec -T db psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -q >/dev/null
log "Starte App …"; compose up -d --no-deps "app_${ACTIVE}"
wait_healthy "app_${ACTIVE}" 90 && log "Restore abgeschlossen"
