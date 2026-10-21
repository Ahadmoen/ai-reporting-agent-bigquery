#!/usr/bin/env bash
# Lineage audit: for every object in a BigQuery dataset, lists which views, table functions,
# scheduled queries and service source files reference it. Objects referenced by nothing are
# candidates for the "do not use" list. Read only.
# Usage: PROJECT_ID=... DATASET=... LOCATION=us SERVICE_DIR=services/reporting-agent-api ./audit_dataset_lineage.sh
set -euo pipefail
: "${PROJECT_ID:?}"; : "${DATASET:?}"; LOCATION="${LOCATION:-us}"; SERVICE_DIR="${SERVICE_DIR:-services/reporting-agent-api}"
TMP=$(mktemp -d)
bq query --use_legacy_sql=false --format=json --max_rows=1000 \
  "SELECT table_name, view_definition FROM \`$PROJECT_ID.$DATASET.INFORMATION_SCHEMA.VIEWS\`" > "$TMP/views.json"
bq query --use_legacy_sql=false --format=json --max_rows=1000 \
  "SELECT routine_name, routine_definition FROM \`$PROJECT_ID.$DATASET.INFORMATION_SCHEMA.ROUTINES\`" > "$TMP/routines.json"
bq ls --transfer_config --transfer_location="$LOCATION" --format=json "$PROJECT_ID" > "$TMP/tc.json"
bq ls --format=json --max_results=1000 "$PROJECT_ID:$DATASET" > "$TMP/objs.json"
python3 - "$TMP" "$SERVICE_DIR" <<'PY'
import json, re, glob, sys
tmp, svc = sys.argv[1], sys.argv[2]
objs = sorted(o['tableReference']['tableId'] for o in json.load(open(f'{tmp}/objs.json')))
src = {}
for r in json.load(open(f'{tmp}/views.json')): src['view:' + r['table_name']] = r['view_definition'] or ''
for r in json.load(open(f'{tmp}/routines.json')): src['fn:' + r['routine_name']] = r['routine_definition'] or ''
for c in json.load(open(f'{tmp}/tc.json')): src['sq:' + c['displayName']] = c.get('params', {}).get('query', '')
for f in glob.glob(f'{svc}/*.py'): src['code:' + f.split('/')[-1]] = open(f).read()
for o in objs:
    pat = re.compile(r'(?<![\w-])' + re.escape(o) + r'(?![\w-])')
    users = [k for k, v in src.items() if pat.search(v) and k.split(':', 1)[1] != o]
    print(o, '|', ', '.join(users) if users else 'NOT REFERENCED')
PY
rm -rf "$TMP"
