#!/usr/bin/env bash
# Example requests to the key protected cut gateway (what n8n calls).
# Usage: GATEWAY_URL=https://... API_KEY=... ./cut_requests.sh
set -euo pipefail
: "${GATEWAY_URL:?}"; : "${API_KEY:?}"
curl -s "$GATEWAY_URL/corte?tipo=diario&fecha=2026-09-28" -H "X-API-Key: $API_KEY" | python3 -m json.tool | head -40
curl -s "$GATEWAY_URL/corte?tipo=semanal&fecha=2026-09-21" -H "X-API-Key: $API_KEY" | python3 -m json.tool | head -40
# Without the key the gateway must answer 401:
curl -s -o /dev/null -w "%{http_code}\n" "$GATEWAY_URL/corte?tipo=diario&fecha=2026-09-28"
