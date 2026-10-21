#!/usr/bin/env bash
# Monday health check: weekly cut status, scheduled query states, latest loaded date per source.
# Usage: PROJECT_ID=... DATASET=... API_URL=https://... WEEK_MONDAY=YYYY-MM-DD ./health_check.sh
set -euo pipefail
: "${PROJECT_ID:?}"; : "${DATASET:?}"; : "${API_URL:?}"; : "${WEEK_MONDAY:?}"
TOKEN=$(gcloud auth print-identity-token)
echo "== weekly cut"
curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/v1/corte?tipo=semanal&fecha=$WEEK_MONDAY" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('estado'), d.get('dias_sin_datos'), d.get('dias_sin_datos_comparacion'))"
echo "== scheduled queries"
bq ls --transfer_config --transfer_location=us --format=prettyjson "$PROJECT_ID" \
  | python3 -c "import sys,json; [print(c['displayName'],'|',c.get('state')) for c in json.load(sys.stdin)]"
echo "== latest loads"
sed -e "s/PROJECT_ID/$PROJECT_ID/g" -e "s/DATASET/$DATASET/g" sql/agent_queries/11_latest_available_dates.sql \
  | bq query --use_legacy_sql=false --format=pretty
