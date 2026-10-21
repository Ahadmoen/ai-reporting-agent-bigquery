# Case study: an AI reporting agent that never invents a number

**Client:** a national internet and TV provider, through its marketing agency's AI division
**Role:** AI data engineer, delivery team of a consulting firm
**Period:** late August to October 2026
**Stack:** BigQuery, Cloud Run, Vertex AI Agent Engine, Agent Development Kit, Gemini Enterprise, GA4 Data API, Windsor.ai, Apps Script, n8n

![Agent answering in Gemini Enterprise](../images/s15-agent-in-gemini-enterprise.png)

## 1. Context

The agency produces a weekly report for the provider that consolidates into a monthly one. It is not a dashboard: every slide follows Insight, Action and Business impact, so each number has to support a business claim with its comparison and context.

The report has three layers. Layer 1 is the business outcome: sales closed and installations completed, by market. Layers 2 and 3, digital demand and media visibility, exist only to explain movement in layer 1. That set the order of the work: the sales layer had to be correct first, because cost per sale and return on spend both divide by sales, and wrong sales make those ratios wrong while looking right.

The agency's brief asked for an engine-agnostic, hallucination-free data layer: any reasoning engine should be able to ask the audited history a question and get the same correct answer.

## 2. The challenge

**Sales live in a spreadsheet.** There is no Salesforce API, by corporate policy. The operations team types sales and installations into a Google Sheet built for people: one column per day, market names only on the first row of each group, subtotal rows and one Total row.

**The existing model was broken in ways that did not show.**
- Version 1 summed the sheet, which holds both market rows and a Total row, so the national figure was counted twice.
- Version 2 kept only the Total row. It matched the corporate reports but dropped all market detail and only offered weeks.
- The staging layer worked out each date from the column position, with one month hardcoded in the SQL. When the team started keeping several months side by side, June was published as July and August was not read at all.
- The weekly view behind the agent had stopped working: two tabs had been renamed with a leading space.
- A number typed with a comma was read as zero, and one published week was 236 sales short.

**An agent needs more than a dashboard.**
- Gemini Enterprise imports base tables, not views, so none of the existing views were visible to it.
- A language model that adds rows on its own produces numbers that look right and are wrong.
- Weeks cross month boundaries, and weekly, half month, monthly and month to date figures must never contradict each other.

**The digital data had traps.** A GA4 purchase is an online service request, not a sale, so the two cannot form a conversion rate. Campaign names followed three different conventions. Windsor's GA4 figures differed from the Analytics screen by up to 1%.

**Reporting was manual.** The weekly product report took about three hours: 20 minutes of exports, 10 minutes running a Python script on one computer, and two to two and a half hours writing. The daily and weekly Slack updates were assembled by hand.

## 3. Approach

- **Read the client's own reports first.** The weekly deck showed that sales explain everything else, which set the priority.
- **Fix the cause, not the symptom.** The brief considered a Python parser, but the real fault was a date taken from a column position. No parser would have fixed it.
- **Let the data layer do the arithmetic.** Every total, period and comparison arrives already calculated, with flags that say when a figure is incomplete or does not reconcile.
- **Report source errors instead of patching them.** The audited figure stays the client's.
- **Build alongside, never on top.** No client object was edited or deleted.

![Architecture](../images/s00-architecture.png)

## 4. What was built

### Sales and installations
- External tables over the sheet rebuilt with 702 declared columns, because BigQuery fixes a connection's width when it is created. The originals stopped at 106 to 118 columns, so new months would have fallen outside them. There is now room for about 18 more months.
- The date of every column is read from the sheet's header row, so a new month needs no SQL change.
- An Apps Script records which plaza each district belongs to every morning, because BigQuery does not keep row order. It refuses to save if it reads fewer than 50 districts, so a bad read fails loudly. Result: 83 districts in 44 plazas, none orphaned or duplicated.
- The national figure is read from the Total row and never calculated. The sum of markets is kept as a check, and every period carries a flag saying whether the two agree.
- National, market and regional figures sit in separate tables, so an agent cannot add a national row to the rows it is summarizing.

### Digital layer
- Windsor field names confirmed by testing, not by reading labels: three first guesses were wrong.
- Ads reach backfilled into its own table, because it cannot be added across days and Google keeps it for only 92 days.
- A duplicate sweep found 61 duplicate rows written by an unrelated task; backed up, then cleaned from 139,510 to 139,449 rows.
- Campaign classification moved from name rules to a mapping tab the agency owns, with two checks: spend with no mapping, and mapping rows that match no campaign.
- Seven layers: media, acquisition, behaviour, channel groups, products, apps in packages and an event campaign.

### Reporting cut
- For any day or week: total, e-commerce and call center sales, GA4 sessions, users and closing rate, the subchannel that drove the movement, the top packages, and notes on any difference between the two sales sheets.
- A 1% tolerance rule decides when the subchannel explanation is safe to show.
- When any day has no sales data, the cut returns `incompleto` and names the missing days. This stopped a false 34% drop from being published.
- A key-protected Cloud Run endpoint gives n8n the cut and nothing else.

### Agent
- Vertex AI Agent Engine, built with the Agent Development Kit, published in Gemini Enterprise.
- 9 tools, one per module, and 20 written rules: always call a tool before giving a figure, the total row is the official figure, never add a breakdown, warn before any non-final figure, never mix national and market figures, never compute a GA4 to sales conversion rate.

![Weekly reporting cut chart](../images/s10-weekly-cut-chart.png)

## 5. Results

| Area | Before | After |
|---|---|---|
| Sales history | Dates from column positions; June published as July, August invisible | Dates read from the sheet; full history correct; new months picked up automatically |
| National and market | National weekly figure only | National, 44 plazas, 83 districts and 9 regions, never mixed; 168 of 168 periods reconcile |
| Periods | Weeks only | Six period types plus custom ranges |
| Agent | Weekly view returning an error, one tool | 9 tools, every figure from the data layer, warnings when a figure is not final |
| Digital data | Raw tables with duplicates, wrong fields and unmapped campaigns | Seven layers with totals that reconcile and client-owned mapping |
| Reporting cut | Built by hand from exports and a script | Ready in 6 to 20 seconds with chart and text, in the agent or through n8n |
| GA4 figures | 1 to 2% above the Analytics screen | Exact match, refreshed three times a day |

### Validation highlights
- National total against the sum of markets: 167 of 168 periods on the first run. The one exception was a cell typed as 236,000 instead of 236. It was reported, not patched; the client fixed it and the check passed 168 of 168.
- Against published weekly reports: 8 of 10 figures exact; the other two by 1 and 3 sales.
- GA4 Data API against the team's manual exports, weeks 31 to 40: 8 weeks exact on items, orders and order lines; the other two within 0.3%, explained by export timing.
- Channel data against the team's channel export, three weeks: 26 of 27 figures exact, the other by one purchase.
- The team's weekly Python script reproduced in SQL: all 8 figures for one week matched exactly.

### Speed under pressure
The agent had to move to a different Gemini Enterprise application 50 minutes before a client presentation. A new entry pointing to the same engine was created, tested across every module and confirmed with time to spare, without redeploying anything.

## 6. Lessons

- **Compare properties after recreating anything.** Recreating two connections silently cut them from 702 columns to 110 and 112. A before and after check caught it the same day.
- **Stop incomplete data before publishing.** A cut that knows which days are missing cannot announce a fake drop.
- **Match the screen the client looks at.** Moving to the GA4 Data API removed a gap that would otherwise need explaining every week.
- **Small, reversible changes.** Everything was built alongside the existing objects with a rollback reference, so nothing the client relied on broke.

## 7. What came next

A phased proposal to retire the weekly manual process: replace the manual exports with a GA4 Data API sync (7 to 9 hours), move the script's rules into one BigQuery view shared by the agent and the report and render the charts in the cloud (13 to 15 hours), and optionally let the agent draft the report text.
