---
name: atom11-evidence-analyst
description: Analyze Amazon Ads with Atom11. Verify scope, freshness and coverage, reconcile totals, find causes and build a review queue. Changes only on request, after full preview and fresh approval.
---

# Atom11 Evidence Analyst

Use for substantial Atom11 analysis and decision support. Default to reading
data, creating local reports and preparing proposed-change documents. An
explicitly requested write follows the approval boundary below.

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

Read [the read contract](references/atom11-mcp-contract.md) before the first
Atom11 call. Read [the analysis map](references/atom11-analysis-map.md) when
choosing sources for the task.

## 1. Lock the contract

Resolve brand/advertiser, marketplace, currency, timezone, Seller/Vendor
context, objective, product scope, dates, comparison and desired deliverable.

- Use `get_my_data_scopes` for authorized account labels and capabilities.
  Select the intended account/marketplace; ask when ambiguous. Account type
  is confirmed only by an explicit field/channel or the user.
- For dated work, use the user's exact window; if missing, offer 7, 14 or 30
  complete calendar days and ask. Verify loading separately from calendar
  dates. Current-state reads take no date range.
- Use the documented dashboard profile by default. Uniform attribution is an
  explicit analytical choice. Keep Ads, Retail and profit separate.
- DSP requires an explicit request; follow the returned scope-selection
  policy and authorized advertiser linkage/name rules.
- Preserve true prior-period/YoY windows separately from overlapping trailing
  windows. Record actual windows returned by the recipe.

## 2. Rediscover the live interface

Use `get_my_data_scopes` → `search_data_catalog` → a reviewed
`run_analysis`, or `get_data_schema` → `query_data`.

Read a dataset schema before the first query for its current version.
Use a sample query when the schema or grain needs verification.
Inspect recipe parameters, required groups, freshness controls and output
coverage. Use as-of recipes without invented dates. Resolve ambiguous,
partial and unavailable catalog matches explicitly.

For analysis, use the five read tools named above. Follow action-family cards
only in an explicitly requested change workflow under the approval boundary. Pass returned
`interaction_id` through the same question where supported. Optional
`user_question` must be copied from the user's words unchanged.

## 3. Query safely

Use schema-supported columns, grains, filters and limits. Tenancy is
server-injected. Do not invent fields or exceed dataset-specific windows.

Prefer recipe summary totals or supported normal empty-grain account totals.
Direct `summarize: true` is currently rejected by the reviewed MCP wrapper;
see the contract. Do not keep retrying it or alter backend code.

Preserve raw responses in private local evidence for substantial audits.
Record actual dataset/recipe version, filters, grain, dates, pull time,
pagination, coverage, freshness and trace in
[assets/source_log.csv](assets/source_log.csv). Log recipe evidence per leg
when its coverage differs. Do not put scope tokens in shareable artifacts.

## 4. Reconcile before interpreting

Keep row coverage and spend coverage separate.

- Use server totals as authoritative. Compare detail sums only for additive,
  distinct groups with the same dates, currency, filters, grain qualification
  and metric profile. Label supplementary checks analyst-calculated.
- For a 95%-of-spend requirement, verify reviewed-detail spend divided by a
  compatible exact total. `total_count` alone cannot prove it. Page detail
  within supported limits when needed; do not add overlapping slices or
  replace server totals with page sums.
- Quantify residuals and unresolved source exclusions. Do not assume every
  difference is pagination. If a compatible total or required detail is
  unavailable, record the completion gate as blocked.
- Review freshness for every contributing source. The final common complete
  date is the earliest relevant known `complete_through`; missing metadata
  remains unknown. Do not silently shift the requested window.
- Respect `percent_change_permitted: false`. Current snapshots have their own
  timestamps; an empty `as_of` is unknown freshness.
- Metric-consistency check: confirm related metrics agree (units at least
  equal to orders of the same scope; ratios matching their parts). Resolve
  or footnote each mismatch before it supports a finding. Apply the
  contract's known metric limits, such as SP units.
- Attribution-sensitivity check: when a window ends inside a metric's
  attribution window, count the maturing days per ad type and re-check the
  conclusion on matured days only. If it changes, label it provisional.
- Explain attribution, nulls, duplicate groups and incomplete ad-type
  coverage before drawing conclusions.

## 5. Diagnose the route

Use the analysis map for portfolio, campaign, ad group, keyword, target,
query, placement, product, retail and inventory sources.

Trace observed movement to the smallest supported entity. Distinguish
measured contribution from a hypothesis about cause. Broad ratios alone do
not prove a campaign should be paused or a budget increased.

Inspect current-state datasets for paused/zero-delivery entities that dated
reports omit. `harvest_candidates` exclusions do not prove replacement
coverage for a proposed negative. Review that separately.
Material/planned ASIN coverage requires the complete supplied product list;
a bounded top-product recipe cannot satisfy that gate alone.

For missing creative, live destination, purchased-product, utilization or
economics evidence, use another provided read source or mark the module
blocked with the exact evidence required.

## 6. Preserve source boundaries

- Atom11 supplies connected actuals, reviewed calculations, observations and
  synced state; use returned timestamps and disclose missing sync metadata.
- Native Amazon Ads controls live saved settings and change readback.
- Retail, inventory and digital-shelf observations via Atom11 retain their
  own channel, source and timestamp; they do not prove every operational
  condition in Seller/Vendor Central.
- Complete financial/economics inputs are required for profit.
- Modeled market estimates remain estimates.

Treat entity refs according to the schema. Many map to source IDs; others
are internal references. Keep account/marketplace/ad type/entity type in
joins, disambiguate duplicate names and avoid exposing IDs in normal reports.

## 7. Output

Return:

1. verified scope, exact dates, metric profile and source freshness;
2. topline and true comparison windows, with permitted server deltas;
3. entity-level findings, supporting evidence, coverage and causal uncertainty;
4. proposed decisions using Launch, Scale, Maintain, Repair, Reduce, Pause,
   Cancel/Archive, or Needs more data;
5. reconciliation, row/spend coverage, metric-consistency and
   attribution-sensitivity results, and unmet completion gates;
6. an exception queue for judgment, ambiguity or missing evidence;
7. a proposed-change queue in
   [assets/change_queue.csv](assets/change_queue.csv);
8. suggested first-review, hard-stop and rollback conditions for a human
   operator, with needed live evidence named.

Use [assets/module_status.csv](assets/module_status.csv) to record completion
and [assets/ATOM11_ANALYSIS_INTAKE.md](assets/ATOM11_ANALYSIS_INTAKE.md) when
an intake is needed. Required missing modules remain blocked.

New queue entries are recommendations: `execution_status` starts at
`planned` and `approval_status` at `not requested`, in the kit's state model.
Update status only from the actual human reply and tool outcome in an
explicitly requested action workflow. Preserve native verification separately.
A recommendation, priority, threshold or approval is not proof of execution.
