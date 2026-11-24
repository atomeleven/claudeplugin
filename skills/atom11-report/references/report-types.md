# Report types

A report type is a named default module set, section order and window rule.
The user or profile can add or remove modules; the type only sets the
starting point and the vocabulary ("weekly business review", "campaign
report"). Module ids refer to cards in
[module-catalog.md](module-catalog.md).

How to choose: match the words the user used. "Weekly", "WBR", "last week",
"every Monday" → `weekly`. "Monthly", "MBR", "last month", "September" →
`monthly`. A single-topic request ("campaign report", "search term report",
"inventory report") → that topic's type. "Report" or "performance report"
with no topic → `account`. "How is my account doing" with no report wording
stays a conversational `account_overview` answer, not this skill.

| Type | Window rule | Core modules (in order) | Optional modules |
|---|---|---|---|
| `weekly` — Weekly Business Review | last 7 complete days, or the last complete Mon–Sun week when the profile says so | `performance`, `campaign_movers`, `campaign_review`, `top_search_terms`, `wasted_spend_terms`, `restock`, `recommendations` | `top_products`, `placements`, `inventory_exposure`, `serving_health`, `automation_activity` |
| `monthly` — Monthly Business Review | last complete calendar month | `performance`, `tacos_trend`, `targeting_mix`, `term_mix`, `campaign_review`, `top_products`, `top_search_terms`, `wasted_spend_terms`, `harvest_terms`, `restock`, `recommendations` | `goals`, `placements`, `audiences`, `portfolios`, `labels`, `digital_shelf_bsr`, `sqp`, `automation_activity` |
| `account` — Account / performance report | user window (ask: 7, 14 or 30 complete days) | `performance` | any |
| `campaigns` — Campaign report | user window | `campaign_review`, `campaign_movers`, `campaign_wasted_spend`, `campaign_health` | `serving_health`, `placements`, `rca` |
| `search_terms` — Search-term report | user window (prefer 14 or 30 days; harvest needs volume) | `top_search_terms`, `wasted_spend_terms`, `harvest_terms` | `keyword_bid_efficiency`, `term_mix` |
| `products` — Product / ASIN report | user window | `top_products`, `asin_scorecard` | `label_products`, `auto_manual_mismatch`, `digital_shelf_bsr`, `abc_classification` |
| `inventory` — Inventory risk report | as-of (no window) | `restock`, `inventory_exposure` | `asin_scorecard` (adds a window) |
| `dsp` — DSP advertiser report | user window; requires a confirmed DSP display name | `dsp_performance`, `dsp_movers` | `dsp_weekday_weekend`, `dsp_line_items` |
| `blended` — PPC + DSP blended view | user window; explicit request only | `blended_overview`, `performance`, `dsp_performance` (appendix) | — |
| `goals` — Goal report | user window | `goals` | `performance` |
| `keywords_bids` — Keyword and bid review | user window | `keyword_bid_efficiency`, `suggested_bids`, `keywords_paused` | `wasted_spend_terms` |
| `placements` — Placement report | user window | `placements` | `placement_movement` |
| `dayparting` — Hour-of-day report | last 28 complete days at most | `dayparting` | — |
| `sqp` — Search Query Performance report | complete weeks (native weekly grain) | `sqp`, `sqp_movement` | — |
| `portfolios_labels` — Portfolio / label report | user window | `portfolios`, `labels` | `label_products` |
| `digital_shelf` — Digital shelf report | user window for history; as-of for catalog | `digital_shelf_bsr`, `digital_shelf_rank`, `catalog_snapshot` | — |
| `automation` — Automation activity report | user window | `automation_activity`, `keywords_paused` | — |
| `serving` — Serving health check | as-of | `serving_health`, `ineligible_products` | — |
| `recommendations` — Recommendations digest | user window for cards; as-of for bids | `recommendations`, `suggested_bids` | — |
| `rca` — Performance-drop drilldown | user window; needs one ASIN, campaign or portfolio | `rca` | `performance` |

## Section order inside a report

Keep this order whatever the type, dropping sections that are not run:

1. Headline performance (`performance` or `dsp_performance` or `blended_overview`)
2. Trend and mix (`tacos_trend`, `targeting_mix`, `term_mix`, `placements`, `dayparting`, `audiences`)
3. Campaigns (`campaign_review`, `campaign_movers`, `campaign_health`, `campaign_wasted_spend`, `serving_health`, `rca`)
4. Search terms and keywords (`top_search_terms`, `wasted_spend_terms`, `harvest_terms`, `keyword_bid_efficiency`, `keywords_paused`, `sqp`, `sqp_movement`)
5. Products (`top_products`, `asin_scorecard`, `label_products`, `auto_manual_mismatch`, `abc_classification`, `portfolios`, `labels`)
6. Inventory (`restock`, `inventory_exposure`)
7. Digital shelf (`digital_shelf_bsr`, `digital_shelf_rank`, `catalog_snapshot`)
8. Recommendations and automation (`recommendations`, `suggested_bids`, `automation_activity`)
9. DSP appendix (`dsp_*`), only when explicitly requested
10. Decision queue, then trust notes

## Call budget

Each module is one or two MCP calls plus a shared catalog search. A `weekly`
report is roughly 7 analyses; a full `monthly` is 11 to 19. Each analysis
can take up to a minute. Tell the user when a report will take several
minutes, and do not add optional modules nobody asked for.

## Overlaps to avoid

- `performance` already contains a bounded top-spend campaign table, a
  dashboard-parity wasted-spend total and a restock watchlist. When
  `campaign_review`, `wasted_spend_terms` or `restock` also run, keep each
  module's figures in its own section and say which profile each uses; the
  `performance` module follows the dashboards' account-aware profile while
  most other analyses use a uniform analytical profile, so the two sets can
  legitimately differ.
- `top_search_terms` (dashboard profile) and `harvest_terms` (uniform 14-day
  or 7-day profile) answer different questions; never merge them into one
  table.
- `restock` and `inventory_exposure` are both as-of snapshots; present them
  together under one "Inventory" heading with one snapshot timestamp.
