# Atom11 campaign-performance-review methodology

The `campaign_performance_review` recipe owns ranking, threshold
normalization, and every delta. The skill owns intake, narrative, and
presentation.

## Parameters

`date_range` (required); `rank_metric` `ad_sales_attributed` (default) or
`ad_spend`; `comparison_metric` same choices (drives growth/shrink flags);
`comparison_window_days` 0 = compare the report window with its preceding
equal window, N = trailing-N-days vs the N before; `missing_target_policy`
`unavailable` (default) or `account_average`; `meaningful_change_percent`
(default 20); `limit` (default 10, max 100); `freshness_policy` default
`allow_partial`.

## Result contract

`outputs[0]` summary: `ranked_by`, `comparison_ranked_by`, `selection_limit`,
`matching_campaigns`, `returned_campaigns`, `date_range`,
`comparison_date_range`, `previous_comparison_date_range`,
`account_average_acos`, `missing_target_policy`,
`meaningful_change_percent`, `attribution_window_days` (always 14),
`ad_scope` (SP + SB + SD), `note`.

Rows: `campaign`, `sponsored_type`, performance (`ad_spend`,
`ad_sales_attributed`, `ad_orders_attributed`, `acos`, `roas`, `ctr`,
`ad_cvr`, `ad_impressions`, `ad_clicks`); targets (`target_acos_value` as
stored, `acos_threshold` normalized ratio, `acos_threshold_source`
campaign_target/account_average/unavailable, `above_acos_threshold`
true/false/null); movement (`comparison_status` new/disappeared/
present_both/unavailable, `delta_ad_spend`, `percent_change_ad_spend`,
`delta_ad_sales`, `percent_change_ad_sales`, `delta_ad_orders`, `delta_acos`,
`delta_roas`, previous values, `meaningful_spend_increase`,
`percent_change_permitted`, `largest_growth`, `largest_shrink`). Internal
`campaign_ref` must never be displayed.

## Interpretation rules

- Uniform 14-day SP+SB+SD attribution — an analytical profile; disclose that
  dashboard values can differ.
- `acos` and `acos_threshold` are ratios (0.32 → 32.0%); `delta_acos` is a
  ratio difference — present it as percentage points, never as a percent
  change.
- `percent_change_*` are ratios and exist only when
  `percent_change_permitted`; absolute `delta_*` values are returned
  regardless and may be shown as returned.
- `largest_growth`/`largest_shrink` are extremes of the SELECTED campaigns on
  the chosen comparison metric — never account-wide claims.
- `comparison_status: new` means no previous-window row (often a launch);
  `disappeared` means no current-window row in the comparison dataset.
- `above_acos_threshold` compares window ACOS to a normalized target; a
  single window above target is a review prompt, not proof of failure
  (seasonality, launches, and halo effects are outside this data).
- Account-average fallback applies only when explicitly requested; quote the
  `account_average_acos` whenever it stands in.

## Allowed / avoided language

Allowed: review, investigate, validate against goals. Avoided: pause now,
cut budget, raise bid, and any cause claim ("declined because…") the rows
cannot prove.
