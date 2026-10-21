# Delivery report

## Timeline

| Date (2026) | Milestone |
|---|---|
| Late August | Brief, recent reports and the operational sheet received. First diagnosis: dates taken from column positions, market detail still present in staging |
| August 25 | Sales ingestion approach proposed: read the date from the sheet, split national and market, add missing periods |
| August 26 | Approach approved. Built, validated and documented the same day: 167 of 168 periods reconcile |
| August 27 | Owner fixes the bad cell and tab names; check passes 168 of 168. A rename quietly narrowed two connections; caught and fixed the same evening |
| August 28 to 31 | Digital ingestion reviewed: Windsor tasks fixed, campaign mapping moved to a client-owned sheet, duplicates removed |
| September 2 | New agent engine created and validated. Plaza level rows added after testing caught a plaza total taken from a single district |
| First half of September | Deck-style charts, automatic period comparison and short readings added |
| September 10 | Digital answers working in Gemini Enterprise. Product layer added. Sales flow closed after a 15 question regression run |
| Mid September | Nine commercial regions added |
| September 23 to 30 | Test rounds with the client. Channel groups, custom date ranges and apps in packages added. Sales and leads sheet connected |
| October 1 | Daily and weekly reporting cut live in the agent |
| October 2 | GA4 Data API live in the cut. Agent published in a second Gemini Enterprise application within 50 minutes, before a client presentation |
| October 5 | Key protected n8n endpoint delivered and handed over. Technical reference v1 |
| October 6 | Packages, apps and add-ons review |
| October 7 to 8 | Digital documentation v5 and v5.1 with closure assessment. Phased automation proposal for the weekly report |
| October 9 | Technical reference v2 with a full object classification |
| October 19 | Handover notes: deploy files, production verification, identity migration steps |

## Deliverables

| Area | Delivered | State |
|---|---|---|
| Sales flow | National, 44 plazas, 83 districts, 9 regions; six period types plus custom ranges; charts | Live, validated |
| Digital flow | Media, acquisition, behaviour, channel groups, products, apps, event campaign | Live, validated |
| Reporting cut | Daily and weekly cut with reconciled figures, chart and text; key protected endpoint for n8n | Live, handed over |
| GA4 Data API | Sessions, active users and closing rate, three syncs a day | Live, matches the Analytics screen |
| Gemini Enterprise | Agent published, with a backup application | Live |
| Reviews | Product coverage review; phased automation proposal | Delivered |
| Documentation | Sales flow document, digital documentation v5.1, technical reference v2, n8n handover, handover notes | Delivered |

## Validation log

Every difference recorded with metric, period, source, size, cause and decision.

| Comparison | Difference | Cause | Decision |
|---|---|---|---|
| National total against sum of markets | 1 of 168 periods | One source cell typed as 236,000 | Reported; national figure stays the Total row; owner fixed the cell |
| Agent against published weekly reports | 2 of 10 figures, by 1 and 3 sales | Not confirmed; e-commerce sales can change after a report is written | Reported |
| Sales and leads sheet against operational sheet | Up to 2 sales a day | Two sheets filled separately | 1% tolerance agreed, difference always shown |
| GA4 via Windsor against Analytics screen | Up to about 1% of sessions | Different GA4 query paths | Accepted when clearly labeled |
| Channel view against general purchase total | 2,628 against 2,630 in one week | Two separate GA4 queries | Explained, both labeled |
| GA4 BigQuery export against Analytics screen | About 1.8% of sessions | Export counts differ from the screen | Cut switched to the GA4 Data API, now exact |
| GA4 Data API against manual exports, 10 weeks | 2 weeks, by 7 to 8 items | Export timing, spread across articles in both directions | Recent weeks refreshed for several days before they are final |
| Channel data against channel export, 3 weeks | 1 of 27 figures, by 1 purchase | Timing | Accepted |
| SQL against the team's Python script, 1 week | None, 8 of 8 figures | | Basis for moving the script rules into the data layer |

## Problems solved

| Problem | Cause | Fix | Result |
|---|---|---|---|
| One month published as another, the next not read | Dates from column position, month hardcoded | Date read from the header row, applied to full history | Every month in place; new months need no SQL change |
| National counted twice, then market detail lost | v1 summed markets and Total row; v2 kept only Total | Separate national and market tables; Total row as national, plazas as check | 168 of 168 reconcile, markets back |
| New months would fall outside the connection | External table width fixed on creation (106 to 118 columns) | Rebuilt with 702 declared columns | Room for about 18 more months |
| Weekly view returned an error | Two tabs renamed with a leading space | Reported; new connections use clean names | Fixed at source |
| Agent could not see the model | Gemini Enterprise imports tables, not views | Agent tables built by scheduled queries | Readable by any engine |
| Plaza total taken from one district | Market table held district rows only | Plaza level rows from the plaza view | Checked across all period types |
| Agent engine stopped working | Repeated in place updates | New engine, old one kept as backup | Validated end to end |
| Weekly cut timed out at 61 seconds | Live sheet read about five times per request | Hourly copy to BigQuery, 300 second timeout | 10 to 20 seconds |
| GA4 1 to 2% above the screen | Export counts differ | Cut moved to GA4 Data API, export as backup | Exact match |
| False 34% drop in a weekly cut | Three days not loaded yet | Cut marked incomplete with the missing days | Never published |
| Subchannel explanation dropped over one sale | Tolerance too strict | 1% rule on the subchannel sum, agreed with the client | Explanation kept when gaps are small |
| Agent missing from the licensed application 50 minutes before a presentation | License renewed on another application | New entry pointing to the same engine | Live and tested in time |
| Awkward generated text ("bajaron -3", "1 ventas") | Text built from signed numbers | Wording rules for signs and singular forms | Clean text |
| 61 duplicate rows in a GA4 table | Written by an unrelated task | Backed up, then deduplicated | 139,449 clean rows |

## Open items at handover
Decisions with the client: reference metric for product questions, how one bundled add-on should be classified, ownership of the product ID tab, whether order-level add-ons are in scope (5 to 6 hours), approval of the automation proposal (20 to 24 hours), access to one GA4 exploration, an optional total row for the event campaign (about 1 hour), and public access on the n8n endpoint.
