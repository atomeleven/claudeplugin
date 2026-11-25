---
name: atom11-inventory-risk-review
description: "Finds stock problems that hurt your sales and waste ad spend. Ask about stock, restocking, or products that are out of stock or running low, and name the account. It shows three things: products closest to running out, with how many days of stock are left and how much to reorder; campaigns still advertising products that are already out of stock; and ad groups advertising products with only a few days of stock left. It uses current stock levels, so no date range is needed. You can change how many days of stock count as low (30 by default), the reorder target (15 days) and how many products to list (15). You get a clean HTML report with headline numbers, a days-of-stock chart and tables, so you can reorder in time and pause or fix ads on products you cannot sell. It is read-only: it changes nothing in your account."
---

# Atom11 Inventory Risk Review

Produce one read-only decision brief from three reviewed Atom11 analyses:

1. `restock_priority` — selling ASINs closest to stock-out, with suggested
   reorder quantities.
2. `campaign_out_of_stock_products` — enabled campaigns advertising ASINs
   whose current sellable stock is zero.
3. `ad_group_low_stock_products` — enabled ad groups advertising ASINs under
   the days-of-cover threshold.

All figures are current as-of snapshots. Never present them as historical
inventory, and never reconstruct the joins yourself.

## Before running

Confirm the Atom11 MCP exposes `get_my_data_scopes`, `search_data_catalog`,
and `run_analysis`. Read
[references/audit-methodology.md](references/audit-methodology.md) first.

## Intake

1. Call `get_my_data_scopes`; select exactly one `ads_profile` (retail data
   rides on it). Never show a `scope_id`.
2. Do NOT ask for a date range — these are as-of analyses and take none.
3. One optional question: days-of-cover threshold (default 30), reorder
   target days (default 15), list size (default 15), and anything to
   prioritize. Use user values verbatim.

## Run the reviewed analyses

1. `search_data_catalog` with intent `restock priority low stock out of stock
   campaigns`; copy the user's request into `user_question`. Confirm the
   three recipe ids above from the catalog (they may arrive across results).
2. Call `run_analysis` three times, copying the user's request into
   `user_question` each time:
   - `restock_priority` with `max_days_of_cover`, `reorder_target_days`,
     `limit` (only when the user changed a default);
   - `campaign_out_of_stock_products` with no params;
   - `ad_group_low_stock_products` with `max_days_of_cover` when changed.
3. If one recipe returns an error envelope, keep the other results, tell the
   user which section failed and why, and render without it — never fake the
   missing section.
4. Treat every count, threshold, freshness guard, and completeness flag as
   authoritative.

## Write the analyst narrative

```json
{
  "verdict": "One headline of at most 12 words",
  "verdict_note": "Two to four sentences expanding the verdict.",
  "module_notes": {"restock": "...", "campaign_oos": "...", "ad_group_low": "..."}
}
```

Rules: every sentence quotes a returned ASIN, campaign/ad-group name, count,
or days-of-cover value; lead with the sharpest exposure (an enabled campaign
on a zero-stock ASIN outranks a 20-day-cover warning); review-only verbs —
recommend verifying live and inbound inventory, never "pause now"; note that
suggested reorder quantities close the stated demand-gap target, not a
guarantee; if any input was bounded/partial, say so.

## Produce the deliverable

1. Save each `run_analysis` JSON unedited to its own file; save the
   narrative JSON.
2. Run:

   ```bash
   python3 <skill-directory>/scripts/render_report.py \
     --restock <restock-json> \
     --campaign-oos <campaign-oos-json> \
     --adgroup-low <adgroup-low-json> \
     --narrative <narrative-json> \
     --output atom11-inventory-risk-<account-slug>-<snapshot-date>.html \
     --account-name "<display name>"
   ```

   Omit a flag only for a section that could not run.
3. Return the file plus at most five evidence-backed review priorities.

If file generation is unavailable, produce a compact Markdown brief with the
same three sections and disclosure rules.

## Non-negotiable controls

- As-of data: say "currently" / "as of the snapshot", never "during the
  period".
- Null on-hand units are unknown, never zero; excluded stale rows are
  disclosed, never silently dropped.
- Suggested reorder quantities are the recipe's demand-gap closure at the
  stated target days — present the target alongside every mention.
- Never recommend pausing or scaling ads directly; the review is "verify live
  and inbound inventory, then decide".
- Bounded inputs stay bounded: quote returned-of-qualifying counts and the
  recipe's own completeness flags.
- Never display internal reference IDs.

## Completion check

Account, marketplace, snapshot timestamp, and thresholds visible; every
returned exposure section present (or explicitly marked not-run/failed);
statuses labelled out-of-stock vs low; narrative traces to returned evidence;
read-only language intact; no remote resources in the HTML.
