#!/usr/bin/env bash
# Pulls items, orders and order lines per week from the GA4 Data API test route,
# to compare with the team's manual exports (sql/validation/02_orders_per_week.sql).
# Result in production: 8 of 10 weeks exact, the other two within 0.3%.
# Usage: API_URL=https://... ./ga4_api_vs_exports.sh "2026-07-27 2026-08-02" "2026-08-03 2026-08-09" ...
set -euo pipefail
: "${API_URL:?}"
TOKEN=$(gcloud auth print-identity-token)
for W in "$@"; do
  set -- $W
  curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/v1/ga4_items_prueba?inicio=$1&fin=$2&modo=pedidos" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('$1', d.get('items_total'), d.get('pedidos'), d.get('filas'))"
done
