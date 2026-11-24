# Atom11 analysis map

Read the area relevant to the user's question. This is a routing aid reviewed
against the current Atom11 release on 2026-10-13, not a promise that every connected
account has every source. Confirm each recipe card and dataset schema at runtime.

| Need | Reviewed recipes | Relevant datasets and scope notes |
|---|---|---|
| Account reporting | `account_report`, `account_overview`, `tacos_trend` | `ads_dashboard_overview`, `ads_dashboard_period_comparison`, `ads_campaign`, `retail_sales`. Explicit PPC/retail reports use `account_report`; general account overview uses `account_overview`. |
| Campaign review | `campaign_health`, `campaign_performance_review`, `wow_campaign_movers`, `campaign_wasted_spend`, `campaign_not_serving` | `ads_campaign_state`, `ads_eligibility_campaign`, `ads_campaign_period_comparison`, `ads_campaign_mixed_period_comparison`, `ads_ad_group`, `ads_ad_group_state`, `ads_ad_group_period_comparison`. Current status differs from dated performance. |
| Keywords and queries | `top_search_terms`, `wasted_spend`, `harvest_candidates`, `keyword_opportunities`, `keyword_bid_efficiency`, `exact_keywords_paused_recently` | `ads_search_term`, `ads_search_term_summary`, `ads_search_term_period_comparison`, `ads_keyword`, `ads_keyword_state`, `ads_keyword_text_period_comparison`, `ads_match_period_comparison`, `ads_product_target`, `ads_product_target_state`, `ads_product_target_period_comparison`, `ads_negative_target`. Observe each dataset's identity grain and attribution. |
| Placement | — | `ads_placement` and `ads_placement_summary` (SP/SB); `ads_placement_period_comparison` (SP). No SD placement report. Placement performance alone does not establish current bid adjustments or bidding strategy. |
| Products | `top_advertised_products`, `asin_daily`, `label_product_performance`, `advertised_product_auto_manual_mismatch`, `ineligible_ad_products` | `ads_advertised_product`, `ads_advertised_product_state`, `ads_advertised_product_period_comparison`, `ads_asin_campaign_type_share`, `ads_asin_abc_performance`, `ads_eligibility_product`. Full purchased-product cross-sell detail is unavailable. Same-SKU measures are not a substitute. |
| Inventory and retail readiness | `restock_priority`, `campaign_out_of_stock_products`, `ad_group_low_stock_products` | `retail_sales`, `retail_inventory`, `retail_inventory_warehouse`, `retail_run_rate`, `product_catalog`. Current run-rate differs from dated inventory. Check planned ASINs explicitly; top-N pages omit others. |
| Mix, goals and structure | `targeting_mix`, `term_mix`, `goal_performance` | `ads_targeting_type_share`, `ads_term_classification_share`, `ads_targeting_share`, `ads_term_share`, `ads_portfolio_performance`, `ads_label`, `ads_label_performance`, `ads_goal`. One supported label kind per label-performance query. |
| Observed performance drops | `entity_drop_rca` | Follow its entity and level parameters. Contributions explain where measured movement occurred; they do not prove the business cause. |
| Audiences | `audience_period_comparison` | `ads_audience` (SP/SB), `dsp_audience_segment`, `amc_audience` are different systems; do not combine them. |
| Hourly data | — | `ads_hourly_performance`: availability depends on AMS source capability; 28-day maximum. Use only schema-listed hour/campaign/placement grains. |
| Shelf and search visibility | `digital_shelf_bsr_decline` | `product_catalog`, `digital_shelf_product`, `digital_shelf_search_rank`, `digital_shelf_bsr_change`, `search_query_performance`, `search_query_performance_comparison`. Tracked marketplace observations differ from live Seller Central state; SQP is weekly Brand Analytics, not the Ads search-term report. |
| Automation history | `exact_keywords_paused_recently` | `automation_rule`, `automation_rule_condition`, `automation_rule_action`, `automation_activity`. Configuration reads and recorded events do not authorize edits or execution. |
| Stored recommendations | `current_recommendations` | `recommendation_feed`, `recommendation_suggested_bid`, `insight`. Use the stored evidence and timestamp; no automatic execution. |
| Explicit DSP reporting | `dsp_account_report`, `dsp_campaign_movers`, `dsp_weekday_weekend` | `dsp_campaign`, `dsp_campaign_period_comparison`, `dsp_line_item`, `dsp_creative`, `dsp_advertised_product`, `dsp_audience_segment`, `dsp_inventory`. Confirm the authorized DSP scope and separate promoted and halo-inclusive definitions. |
| Explicit blended reporting | `blended_ppc_dsp_overview` | Requires separately authorized PPC/Retail and DSP scopes. Preserve its blended-estimate disclosure; do not add attributed sales as unique revenue. |
| AMC troubleshooting | — | `amc_instance`, `amc_workflow`, `amc_workflow_execution`, `amc_audience`: requires an available linked AMC scope/domain. Read only. |

## Parameters that matter

- A missing date range needs clarification only for dated analyses.
- `account_report` defaults to account-aware dashboard metrics and a bounded
  report. Consume requested sections, coverage, omissions and review flags.
- `wasted_spend` and `top_search_terms` distinguish dashboard-row grain
  from aggregated term grain. Read the current card and returned params:
  question-derived defaults can affect the chosen qualification/profile.
- `harvest_candidates` with `targeted_terms: exclude` filters already
  targeted terms. This does not prove replacement coverage or that a negative
  would preserve productive demand; additional account evidence is required.
- Threshold operators (`gt` versus `gte`), output limits, freshness
  controls and comparison modes must come from the current recipe card.
- `asin_daily` combines period Ads/Retail with current inventory. Label the
  dates separately. It inspects a bounded product set.
- Stock urgency recipes disclose examined, accepted and returned counts.
  Stale stock rows and unknown on-hand quantities need explicit notes.

## Unsupported completion claims

A full cross-source audit still needs other sources for live saved settings,
creative/Store/PDP content, suppression and operational readiness, complete
purchased-product paths, market estimates and verified unit economics.
Some retail schemas expose vendor shipped COGS, but that is not a complete
profit or contribution-margin model. Budget amount and non-serving status
alone do not prove budget utilization, lost demand or a causal diagnosis.

Record these modules as blocked with the exact evidence needed unless the
user supplies another source. Every proposed change remains a review document.
