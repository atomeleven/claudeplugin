---
name: atom11-amazon-ads-deep-audit
description: "A complete health check of your Amazon Ads account, written in the chat. Ask for a full audit, an audit before a big sales event, or an audit after results dropped, and name the account and dates. It first confirms the account, marketplace, currency and the exact dates, and checks that the data is complete and up to date. Then it looks at everything: campaigns, ad groups, keywords, search terms, placements, products, budgets and stock, and makes sure every dollar of active spend is counted. It explains what caused big changes and sorts each campaign into scale, keep, fix, reduce or pause. You get a clear summary, the data gaps it found, and a numbered list of suggested changes with the current value, the new value and the reason for each. Nothing changes in your account unless you ask for a change and approve its full preview. For the same audit as a page with Take action buttons, use atom11-deep-audit-actions."
---

# Amazon Ads Deep Audit — Shareable

Own the work through a verified decision system. Do not stop at a dashboard or a list of generic recommendations.

## Approval boundary

Reading, analysis and reporting are the default. Prepare a stored MCP proposal
only when the human explicitly requests the specific change or its preview.
A report, recommendation, write grant or initial "do it" is not final approval.

Before any live change, read and follow
[the approved action workflow](references/approved-actions.md). It requires
a complete server preview, every warning, freshness/undo disclosures, an
ended assistant turn, and a new human reply approving exactly that proposal.
Never show a preview and confirm in the same assistant turn. Any changed
values/entities/warnings, replacement, expiry or stale preview requires a
new preview and fresh approval. Undo requires its own approval cycle.

Use only runtime-enabled MCP actions. No automatic optimization, rollback,
policy bypass, rule editing, DSP writing or native-Amazon mutation fallback.
Report audit-confirmed execution separately from native saved-state readback.
Respect any user or higher-priority instruction restricting work to reads.

## Audit contract

Confirm brand, advertiser profile, marketplace, Seller/Vendor/hybrid account type, currency, timezone, attribution window, audit mode, date windows, latest common complete date, active formats, product scope, planning source, available systems, deliverable location, refresh expectation, and approval boundary.

## Source hierarchy

1. Native Amazon Ads controls current advertising settings.
2. Seller/Vendor Central controls current retail state for its channel.
3. Approved planning sources control goals, assortment, and promotion assumptions.
4. Atom11 and other aggregators provide analysis and historical reconciliation.
5. Live PDP/SERP checks are timestamped observations.
6. Public research provides market context, not authenticated account state.

Preserve conflicts instead of forcing sources to match.

## Completeness rules

- Account for 100% of active spend or quantify the unresolved remainder.
- Make detailed search-term/target review represent at least 95% of imported spend and include material zero-order spend.
- Represent every planned and materially advertised ASIN with retail and paid-activation state.
- Check every active ad format; do not silently equate Sponsored Products with the whole account.
- DSP is separate scope unless explicitly included.

## Audit sequence

1. Verify identity and scope.
2. Create a source log before retrieval.
3. Preserve raw exports unchanged.
4. Retrieve current settings, performance, retail, inventory, catalog, destination, creative, and economics evidence as available.
5. Normalize IDs, names, ASINs/SKUs, dates, currency, timezone, attribution, product family, brand intent, funnel role, and bundle relationships.
6. Reconcile totals and data conflicts.
7. Audit campaign, ad group, target, query, match type, placement, product, purchased product, budget, creative, portfolio, and destination.
8. Classify each route: Launch, Scale, Maintain, Repair, Reduce, Pause, Cancel/Archive, Needs more data.
9. Separately classify each destination: Eligible, Repair before scaling, Hold from paid traffic.
10. Build the command center, exception queue, proposed-change queue, refresh SOP, and executive handoff.
11. Verify formulas, links, scope, totals, freshness, and remote persistence.

## Change queue

Every proposed change includes entity and ID, current state, exact proposed state, evidence window, root cause, expected benefit, risk, confidence, owner, due/review date, approval, execution status, first review, hard stop, and rollback.

Read-only is the default. Do not mutate the live account without approval for the exact batch. Revalidate before saving and reread after saving.

On Atom11 that approval means: the complete server preview and every warning shown, the assistant turn ended, and a new human reply approving exactly that proposal before `confirm_actions`.

## Completion

The audit is complete only when all sources are logged, scope/freshness is explicit, spend and material ASINs are accounted for, detailed recommendations trace to evidence, data gaps are classified, the system can be refreshed, and the handoff gives decisions rather than merely data.

## Atom11 binding (native edition)

This binding implements the audit method using Atom11 read evidence. The approval boundary above governs every proposed action.

**Audit contract.** `get_my_data_scopes` supplies advertiser display name, marketplace, currency, timezone and `available_domains` for the authorized accounts; The account report states its metric profile; Seller/Vendor/hybrid context must come from an explicit returned channel/field or user confirmation. The final common complete date is the earliest relevant known `complete_through` across all contributing sources; missing metadata remains unknown. DSP stays separate scope unless explicitly included, which matches Atom11's own policy (exact DSP display name confirmed by the user).

**Source hierarchy, item 4.** Atom11 provides advertising actuals, server totals and coverage metadata (section 5 of the contract); synced state for campaign status, serving eligibility, budgets, targeting mode, negatives and keyword bids; retail sales, inventory run-rate and product-catalog observations. Use returned `as_of` timestamps where available; missing sync metadata is unknown. Native Amazon Ads controls live saved settings and readback.

**Completeness rules, on Atom11.**
- 100% of active spend: `account_report` returns exact advertising totals by SP/SB/SD with `sponsored_type_coverage` per channel (`complete_with_data`, `complete_no_activity_rows`, or incomplete = unknown, never zero). Quantify the unresolved remainder from an incomplete channel as unknown.
- 95% of imported spend in search-term/target review: retain this gate. Use a compatible recipe summary or supported account-total query as the exact denominator, then sum distinct additive spend in reviewed detail with the same scope, dates, filters and attribution. Report spend coverage separately from row coverage. Page within documented limits where needed; search-term populations can omit campaign spend, and keyword/target/query slices can overlap. If 95% cannot be established, mark the gate unmet with the exact missing evidence. Direct `summarize: true` is currently rejected by the MCP wrapper; use the contract's supported alternatives.
- Every planned and materially advertised ASIN: `ads_advertised_product` (dated, paged by `product`) joined on ASIN to `retail_run_rate` / `product_catalog` for stock, price and availability; `asin_daily` gives ads vs retail vs current stock per ASIN in one reviewed call; `ineligible_ad_products` and `campaign_out_of_stock_products` give the paid-activation blockers.
- Every active ad format: read `sponsored_type_coverage`; SD has no placement report.

**Audit sequence, Atom11 sources per step.** Step 4 retrieval: performance → recipes and datasets in section 6 of the contract; current settings → `campaign_health`, `ads_campaign_state`, `ads_eligibility_campaign`, `ads_negative_target`, `ads_keyword` (`current_bid`); retail/inventory/catalog/destination → `retail_sales`, `retail_run_rate`, `restock_priority`, `product_catalog`, digital-shelf datasets; creative and economics → not in Atom11 (log as blocked or sourced elsewhere). Step 5 normalization: ASIN/SKU and schema-defined refs support scoped joins; many entity refs map to source IDs, so treat them as sensitive and verify cross-system identity. Duplicate names require disambiguation. Step 6 reconciliation: compare compatible additive detail with authoritative server totals and preserve unexplained residuals. Step 7 audit levels: campaign, ad group, target, query, match type, placement, advertised product, budget, portfolio map to this package's `references/atom11-analysis-map.md`; purchased product and creative/destination are outside Atom11.

**Change queue.** Fill the template with current observed values, exact proposed changes, evidence, risks, approval requirement and review/rollback conditions. New rows start at `planned` in the state model; `ready for approval` only once the preview has been shown, `approved` only from the human's reply. If the human explicitly requests an action, use [the approved action workflow](references/approved-actions.md), show the complete returned preview, end the turn, and wait for a new exact-proposal approval before confirming. Cancellation and undo follow that protocol; no automatic rollback. Native Amazon remains the authority for live saved-state verification.

**Refresh SOP.** A refresh reruns the same recipes and queries with the next window; Atom11's comparison datasets derive the preceding equal window, so refreshes never label overlapping trailing windows as sequential periods.


Atom11 specifics for every step above are in [references/atom11-mcp-contract.md](references/atom11-mcp-contract.md); read it before the first Atom11 call. Read [the analysis map](references/atom11-analysis-map.md) when selecting task-specific sources. Use the bundled `assets/` intake, source-log, module-status and change-queue templates.
