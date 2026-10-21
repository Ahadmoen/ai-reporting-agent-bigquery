# Handover and operations

## Deploy files

| Path | What it is |
|---|---|
| services/agent/deploy_agent.py | Defines and deploys the agent: 9 tools, instructions and requirements |
| services/reporting-agent-api/ | Cloud Run service the agent calls for every figure, chart and cut (main.py, charts.py, corte.py, ga4_api.py, Dockerfile, requirements.txt) |
| services/cut-gateway/ | Key protected endpoint that returns the reporting cut to n8n (main.py, Dockerfile, requirements.txt) |

### Proving the deployed version
At handover, the deploy script's last save was compared with the engine's last update (four minutes apart) and the script's tool list was compared with the deployed agent (same 9 tools).

## Redeploy

Agent:
1. Python 3.12 with google-cloud-aiplatform 1.163.0, google-adk 2.6.2 and cloudpickle 3.1.2 (pinned in the script).
2. `python3 services/agent/deploy_agent.py`
3. The script updates the existing engine in place and stages the package in a staging bucket. Gemini Enterprise points to the same engine, so nothing changes there.
4. Running the script updates production directly. Test changes on a separate engine first.

Cloud Run service:
```bash
cd services/reporting-agent-api
gcloud run deploy reporting-agent-api --source . --region REGION \
  --project PROJECT_ID --no-allow-unauthenticated
```

## How the pieces connect

| Item | Setting |
|---|---|
| Who can call reporting-agent-api | Agent Engine, Vertex AI and Gemini Enterprise service agents, each with Cloud Run Invoker |
| Identity of both services | Project service account, 300 second timeout |
| cut-gateway key | `API_KEY` environment variable; no key in code |
| Public access on cut-gateway | Needs a project Owner to allow it |

## Scheduled query identity migration

Scheduled queries ran with a user's credentials. They keep working only while that user has access. Steps to move them to a service account without a gap:

1. Create or choose a service account in the project.
2. Grant BigQuery Job User on the project, BigQuery Data Editor on the dataset and BigQuery Data Viewer on the GA4 export dataset.
3. Share the four source Google Sheets with it as Viewer.
4. Switch with an account that has BigQuery Admin and Service Account User on that service account.
5. Start with the hourly sales and leads copy: it reads a sheet and runs every hour, so the result shows quickly.
6. Confirm the next run succeeds. If the sheet cannot be read under the service account, use a team user account instead.
7. Move the other queries one at a time.
8. Remove the old user's access only after every query has run under the new identity.

```bash
bq update --transfer_config --update_credentials \
  --service_account_name=SERVICE_ACCOUNT_EMAIL \
  CONFIG_NAME
```

The plaza map Apps Script runs under its trigger owner; check that owner in the same move (Extensions, Apps Script, Triggers).

## Daily operation checks
`scripts/health_check.sh` prints the weekly cut status, scheduled query states and the latest loaded date of each source. Publish a cut only when `estado = ok`.
