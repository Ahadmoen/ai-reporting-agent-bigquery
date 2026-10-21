# Images for the repo and portfolio

Save each image in `images/` with the exact file name below. Before saving, hide or blur: client names and logos, project IDs, emails, keys, tokens, URLs, sheet names, and any monetary amount.

| File name | What to capture | Where to take it | Used in |
|---|---|---|---|
| s00-architecture.png | Architecture diagram | Export `architecture/architecture.mmd` from mermaid.live, or draw it in your design tool | README, CASE_STUDY section 3 |
| s01-agents-list.png | Agents list with the reporter agent enabled | Gemini Enterprise, application, Agents | CASE_STUDY section 4 |
| s02-national-week-answer.png | Agent answer for a national week with the previous week comparison | Gemini Enterprise web app | CASE_STUDY section 4 |
| s03-region-month-answer.png | Agent answer for one region and month | Gemini Enterprise web app | CASE_STUDY section 4 |
| s04-weekly-overview-chart.png | One deck-style chart opened from its link | Ask the agent for the weekly chart | CASE_STUDY section 4 |
| s05-channel-groups-answer.png | Purchases by channel group for one week | Gemini Enterprise web app | TECHNICAL section 3 |
| s06-products-by-family.png | Items purchased by family for one week | Gemini Enterprise web app | TECHNICAL section 3 |
| s07-apps-overlap-warning.png | Apps in packages with the overlap warning visible | Gemini Enterprise web app | TECHNICAL section 3 |
| s08-sessions-purchases-month.png | Sessions and digital purchases for a month (hide revenue) | Gemini Enterprise web app | TECHNICAL section 3 |
| s09-daily-cut-chart.png | Daily cut chart | Saved PNG from the cut | CASE_STUDY section 4 |
| s10-weekly-cut-chart.png | Weekly cut chart | Saved PNG from the cut | README, CASE_STUDY section 4 |
| s11-weekly-cut-text.png | Full weekly cut text in the agent | Gemini Enterprise web app | TECHNICAL section 4 |
| s12-gateway-401-200.png | Gateway test: 401 without key, 200 with key (key hidden) | Cloud Shell | TECHNICAL section 7 |
| s13-ga4-match.png | Analytics screen next to the weekly cut for the same week, same sessions and users | GA4 Reports | CASE_STUDY section 5 |
| s14-scheduler-job.png | GA4 sync Cloud Scheduler job with its three daily runs | Cloud Scheduler | TECHNICAL section 5 |
| s15-agent-in-gemini-enterprise.png | Agent selected and answering a question | Gemini Enterprise web app | CASE_STUDY header |
| s16-api-vs-exports.png | Cloud Shell output comparing GA4 Data API with the manual exports for 10 weeks | Cloud Shell | DELIVERY_REPORT validation |
| s17-docs-cover.png | First pages of the delivered documentation (titles blurred) | Delivered documents | DELIVERY_REPORT deliverables |
| s18-reconciliation-168.png | Query result showing 168 of 168 periods reconciled | BigQuery console, `qc_nacional_vs_mercados_v2` | CASE_STUDY section 5 |

To show an image in a markdown file: `![Short description](../images/FILE_NAME.png)` from `docs/`, or `![Short description](images/FILE_NAME.png)` from the README.
