#!/usr/bin/env bash
# Legt eine ILM-Richtlinie an: Logs werden nach 14 Tagen gelöscht (Datenminimierung/DSGVO).
set -euo pipefail
ES="${ES_URL:-http://localhost:9200}"
curl -fsS -X PUT "$ES/_ilm/policy/minikos-14d" -H 'Content-Type: application/json' -d '{
  "policy": {"phases": {"hot": {"actions": {}}, "delete": {"min_age": "14d", "actions": {"delete": {}}}}}
}' && echo
curl -fsS -X PUT "$ES/_index_template/minikos-logs" -H 'Content-Type: application/json' -d '{
  "index_patterns": ["minikos-logs-*"],
  "template": {"settings": {"index.lifecycle.name": "minikos-14d", "number_of_replicas": 0}}
}' && echo
echo "ILM-Richtlinie minikos-14d aktiv."
