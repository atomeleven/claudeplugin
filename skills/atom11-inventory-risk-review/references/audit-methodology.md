# Atom11 inventory-risk methodology

Three reviewed recipes own all math; the skill orchestrates and presents.

## restock_priority

Params: `max_days_of_cover` (default 30), `reorder_target_days` (default 15),
`limit` (default 15). No date range — current snapshot only.

`outputs[0]` summary: `qualifying_products`, `examined_products`,
`fresh_products`, `returned_products`, `unexamined_qualifying_products`,
`ranking_is_complete`, `ranking_scope`, `freshness_guard` (snapshot anchor,
stale/missing-timestamp exclusions), `note`. Rows: `product`, `stock_status`
(`out_of_stock` when on-hand ≤ 0, else `low`), `daily_sales_velocity`,
`on_hand_units`, `days_of_cover`, `recommended_reorder_quantity`,
`updated_at_utc`. Ranking is lowest days of cover first with ASIN as the
tie-breaker; a `complete_top_n...` ranking_scope means the top-N is complete
even though more, less-urgent products qualify.

## campaign_out_of_stock_products

No params. Summary: `qualifying_inventory_products`,
`inventory_products_examined`, `advertised_product_rows_examined`,
`matching_campaigns`, `matching_products`,
`matching_campaign_product_pairs`, `is_complete`, `scope` ("enabled product
ads"), `freshness_guard`, `note`. Rows: `campaign`, `sponsored_type`,
`product`, `stock_status`, `on_hand_units`, `enabled_product_ads`,
`inventory_updated_at_utc` (+ internal `campaign_ref` — never display).

## ad_group_low_stock_products

Param: `max_days_of_cover` (default 30, strict upper bound for positive
stock; zero stock always included when velocity is positive). Summary adds
`matching_ad_groups`, `matching_ad_group_product_pairs`,
`max_days_of_cover`. Rows add `ad_group`, `daily_sales_velocity`,
`days_of_cover` (+ internal refs — never display).

## Interpretation rules

- Everything is a CURRENT snapshot; the freshness guard excludes rows older
  than the snapshot window and reports the exclusions — repeat them.
- `is_complete: false` on the join recipes means a bounded input continued:
  the rows are an honest partial set, never "every matching campaign/ad
  group".
- An enabled ad on a zero-stock ASIN is the highest-signal review item:
  spend continues while conversion is impossible — but verify live inventory
  first; snapshots lag reality.
- Low stock under threshold with high velocity outranks low stock with
  trickle velocity; the recipes already sort accordingly.
- Reorder quantity = max(0, velocity × target_days − on_hand), server-side;
  quote the target days with it.

## Allowed / avoided language

Allowed: verify, review, confirm inbound, prioritize restock. Avoided: pause
now, stop ads, guaranteed stock-out date, exact days-until-OOS claims beyond
the returned days-of-cover.
