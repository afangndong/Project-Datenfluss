#!/usr/bin/env bash
# Restore-TEST: spielt das neueste (oder angegebene) Backup in eine TEMPORÄRE Datenbank ein,
# vergleicht Zeilenzahlen mit der Live-DB und löscht die Test-DB wieder. Live-Daten bleiben unberührt.
# Ein Backup, dessen Restore nie getestet wurde, ist kein Backup.
# Aufruf: scripts/restore_test.sh [backup-datei]
source "$(dirname "$0")/lib.sh"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/.backup}"
PGUSER="${POSTGRES_USER:-minikos}"; PGDB="${POSTGRES_DB:-minikos}"
FILE="${1:-$(ls -1t "$BACKUP_DIR"/minikos_*.sql.gz 2>/dev/null | head -1)}"
[[ -f "$FILE" ]] || die "Kein Backup gefunden (erst scripts/backup.sh ausführen)"
TESTDB="restore_test_$(date +%s)"
psql_() { compose exec -T db psql -U "$PGUSER" -v ON_ERROR_STOP=1 -qtA "$@"; }

cleanup() { psql_ -d postgres -c "DROP DATABASE IF EXISTS $TESTDB" >/dev/null 2>&1 || true; }
trap cleanup EXIT

log "Restore-Test: $FILE → temporäre DB $TESTDB"
psql_ -d postgres -c "CREATE DATABASE $TESTDB" >/dev/null
gunzip -c "$FILE" | compose exec -T db psql -U "$PGUSER" -d "$TESTDB" -v ON_ERROR_STOP=1 -q >/dev/null

RC=0
for table in patients stays appointments; do
  restored="$(psql_ -d "$TESTDB" -c "SELECT count(*) FROM $table")"
  live="$(psql_ -d "$PGDB" -c "SELECT count(*) FROM $table")"
  printf '  %-14s Backup=%-6s Live=%-6s\n' "$table" "$restored" "$live"
  # Backup darf älter sein (weniger Zeilen), aber nicht LEER, wenn live Daten existieren
  if (( live > 0 && restored == 0 )); then warn "Tabelle $table im Backup leer!"; RC=1; fi
done
(( RC == 0 )) && log "RESTORE-TEST BESTANDEN" || die "RESTORE-TEST FEHLGESCHLAGEN"
