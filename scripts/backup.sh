#!/usr/bin/env bash
# Logisches Backup (pg_dump, gzip) mit Integritätsprüfung, Retention und Prometheus-Metrik.
# Aufruf: scripts/backup.sh            Umgebung: BACKUP_DIR (Standard .backup), KEEP_DAYS (Standard 7)
source "$(dirname "$0")/lib.sh"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/.backup}"
KEEP_DAYS="${KEEP_DAYS:-7}"
PGUSER="${POSTGRES_USER:-minikos}"; PGDB="${POSTGRES_DB:-minikos}"
mkdir -p "$BACKUP_DIR/metrics"

STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/minikos_${STAMP}.sql.gz"
TMP="${FILE}.part"

log "Backup von Datenbank '$PGDB' → $FILE"
if ! compose exec -T db pg_dump -U "$PGUSER" -d "$PGDB" --no-owner --clean --if-exists | gzip -9 >"$TMP"; then
  rm -f "$TMP"; die "pg_dump fehlgeschlagen"
fi
gzip -t "$TMP" || { rm -f "$TMP"; die "Archiv defekt"; }
SIZE="$(stat -c %s "$TMP")"
(( SIZE > 200 )) || { rm -f "$TMP"; die "Backup verdächtig klein ($SIZE Bytes)"; }
mv "$TMP" "$FILE"

# Retention
find "$BACKUP_DIR" -maxdepth 1 -name 'minikos_*.sql.gz' -mtime "+${KEEP_DAYS}" -print -delete | sed 's/^/gelöscht: /' || true

# Metrik für node-exporter (textfile collector) → Alert BackupTooOld
{
  echo "# HELP minikos_backup_last_success_timestamp_seconds Unix-Zeit des letzten erfolgreichen Backups"
  echo "# TYPE minikos_backup_last_success_timestamp_seconds gauge"
  echo "minikos_backup_last_success_timestamp_seconds $(date +%s)"
  echo "# HELP minikos_backup_last_size_bytes Größe des letzten Backups"
  echo "# TYPE minikos_backup_last_size_bytes gauge"
  echo "minikos_backup_last_size_bytes $SIZE"
} >"$BACKUP_DIR/metrics/minikos_backup.prom.tmp"
mv "$BACKUP_DIR/metrics/minikos_backup.prom.tmp" "$BACKUP_DIR/metrics/minikos_backup.prom"
log "Backup OK (${SIZE} Bytes)"
