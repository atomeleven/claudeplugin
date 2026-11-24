# Atom11 search-term opportunities methodology

The `keyword_opportunities` recipe owns qualification, totals, and source
context. The skill owns intake, narrative, and presentation.

## Parameters

`date_range` (required); `attribution_window_days` 14 (SP+SB) or 7 (SP only);
`harvest_min_orders` (default 2); `harvest_min_clicks` (default 1);
`harvest_max_acos_percent` (optional strict cap); `waste_min_clicks` (default
5, inclusive ≥); `limit` (default 25, both queues); `freshness_policy`
default `allow_partial`.

## Result contract

`outputs[0]` is the summary bundle: `harvest_candidates` and
`negative_candidates` summaries. Later rows carry `section:
"harvest_candidates"` or `section: "negative_candidates"`.

Harvest summary: `matching_source_terms`, `returned_source_terms`,
`is_complete`, `attribution_window_days`, `ad_scope`, `qualification`
(`minimum_orders`, `minimum_clicks`, `maximum_acos_percent`,
`targeted_terms`), `already_targeted_excluded`, `targeted_check_complete`,
`note`. Harvest rows: `term`, `match`, `source_kind`, `source_target` (the
human-readable producing target), `ad_clicks`, `ad_spend`,
`ad_orders_attributed`, `ad_sales_attributed`, `acos` (ratio), plus internal
`*_ref` fields that must never be displayed.

Waste summary: `total_wasted_spend`, `returned_wasted_spend`,
`matching_search_term_groups`, `returned_search_term_groups`,
`detail_is_complete`, `total_is_complete`, `metric_profile`,
`attribution_window_days`, `ad_scope`, `qualification` (clicks operator +
value, zero orders, grain `term`), `dashboard_comparison`, `note`. Waste
rows: `term`, `ad_clicks`, `ad_spend`, `ad_orders_attributed`,
`ad_sales_attributed`.

## Interpretation rules

- This recipe runs on the uniform `amazon_14d` (or `sp_7d`) analytical
  attribution profile — an explicit opt-in that can differ from the
  dashboards' account-aware profile. Disclose this whenever numbers are
  compared to what the user sees in the app.
- Harvest candidates are conversion evidence, not guaranteed winners:
  harvesting a term into exact match shifts traffic and can cannibalize its
  source target — that is exactly the review a human performs.
- `targeted_terms: include` (default) keeps terms that already run as
  keywords; only explicit "not targeted" requests use the exclusion, and the
  exclusion is only as complete as `targeted_check_complete` says.
- Waste totals are exact for the qualified population; the displayed list is
  bounded (`returned_search_term_groups` of `matching_search_term_groups`).
- A zero-order term still needs relevance and attribution-lag review before
  becoming a negative; recent windows undercount lagging conversions.
- ACOS values are ratios (0.32 → 32.0%).

## Allowed / avoided language

Allowed: review, validate, harvest candidate, negative candidate. Avoided:
add now, negate now, guaranteed savings, projected sales lift.
