---
name: atom11-campaign-performance-review
description: "Rank Amazon campaigns and review recorded target ACOS and supported period movement through Atom11. Produce a read-only campaign performance brief."
---

# Atom11 Campaign Performance Review

Produce a read-only campaign review brief from Atom11's reviewed
`campaign_performance_review` analysis: a bounded global campaign ranking
with current performance, per-campaign target-ACOS flags, and an
equal-window comparison. Never reconstruct rankings, thresholds, or deltas
yourself.

## Before running

Confirm the Atom11 MCP exposes `get_my_data_scopes`, `search_data_catalog`,
and `run_analysis`. Read
[references/audit-methodology.md](references/audit-methodology.md) first.

## Intake

1. Call `get_my_data_scopes`; select exactly one `ads_profile`. Never show a
   `scope_id`.
2. Require an explicit reporting window (exact dates, or a duration converted
   to inclusive dates in the account timezone ending yesterday; if missing,
   ask once and offer 7, 14, or 30 complete days).
3. In the same question, offer the typed choices (defaults in parentheses):
   - rank by attributed ad sales (default) or ad spend;
   - how many campaigns (10);
   - when a campaign has no target ACoS: show "No target" (default) or flag
     against the account average (`missing_target_policy: account_average`);
   - meaningful spend-growth threshold (20%).
   Use the user's values verbatim; never invent a target.

## Run the reviewed analysis

1. `search_data_catalog` with intent `campaign performance review target acos
   movement`; copy the user's complete request into `user_question`.
2. Confirm the `campaign_performance_review` recipe; if unavailable, stop.
3. Call `run_analysis` once with `date_range` plus only the parameters the
   user changed (`rank_metric`, `limit`, `missing_target_policy`,
   `meaningful_change_percent`, `comparison_metric`,
   `comparison_window_days`).
4. Treat rankings, thresholds, deltas, and flags as authoritative. On an
   error envelope, explain and stop.
5. If freshness warnings show only trailing day(s) incomplete, deliver, then
   offer exactly one rerun ending at the earliest `complete_through` date.

## Write the analyst narrative

```json
{
  "verdict": "One headline of at most 12 words",
  "verdict_note": "Two to four sentences expanding the verdict.",
  "module_notes": {"ranking": "...", "movement": "..."}
}
```

Rules: every sentence quotes a returned campaign name, value, or flag; lead
with the sharpest finding (the largest decline, or the biggest above-target
spender); quote targets with their source ("above its 25.0% campaign
target" / "above the 25.6% account average"); movement flags apply only to
the selected campaigns — never call anything the account's largest mover;
review-only verbs; if `percent_change_permitted` is false, say deltas are
absolute only.

## Produce the deliverable

1. Save the exact `run_analysis` JSON unedited; save the narrative JSON.
2. Run:

   ```bash
   python3 <skill-directory>/scripts/render_report.py \
     --input <analysis-json> \
     --narrative <narrative-json> \
     --output atom11-campaign-review-<account-slug>-<end-date>.html \
     --account-name "<display name>"
   ```

3. Return the file plus at most five evidence-backed review priorities.

If file generation is unavailable, produce a compact Markdown brief with the
same sections and disclosure rules.

## Non-negotiable controls

- The ranking is global but bounded: always "top N of M matching campaigns";
  growth/shrink flags are extremes of the selected set only.
- Target flags come from the recipe (`above_acos_threshold`,
  `acos_threshold_source`); never compute your own threshold comparison, and
  always disclose when the account average stood in for a missing target.
- Metrics use the uniform 14-day SP+SB+SD analytical profile — disclose that
  it can differ from dashboard values.
- Present percent changes only when the row's `percent_change_permitted` is
  true; absolute deltas may still be shown as returned.
- "Above target" is a review flag, not a verdict — pausing or bid changes
  need goals, margins, and history the report does not contain.
- Never display campaign reference IDs.

## Completion check

Account, marketplace, currency, both windows, and the ranking basis are
visible; target flags carry their source; movement flags stay set-relative;
narrative traces to returned evidence; read-only language intact; no remote
resources.
