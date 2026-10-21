# Services

| Folder | What it is | Runtime |
|---|---|---|
| reporting-agent-api/ | Private Cloud Run service the agent calls: one route per module (salesforce, region, rango, flujo_c, canales, producto, apps, chart, corte), the GA4 Data API sync route and read only test routes | Python, FastAPI, matplotlib, google-cloud-bigquery |
| cut-gateway/ | Public Cloud Run service for n8n: exposes only /corte, checks X-API-Key with a constant time comparison, calls reporting-agent-api with the service account identity, passes estado through | Python, FastAPI |
| agent/ | deploy_agent.py: defines the 9 ADK tools and the 20 instructions, and updates the Vertex AI Agent Engine in place | Python 3.12, google-adk, google-cloud-aiplatform |

Configuration is read from environment variables: `PROJECT_ID`, `DATASET`, `API_KEY` (gateway only), `UPSTREAM_URL` (gateway only), `CHARTS_BUCKET`. No secret is stored in code.

Deploy and redeploy steps are in [../docs/HANDOVER.md](../docs/HANDOVER.md).
