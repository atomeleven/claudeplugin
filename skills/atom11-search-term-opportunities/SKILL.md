---
name: atom11-search-term-opportunities
description: "Finds search terms worth acting on in your Sponsored Ads. Ask which search terms to add as keywords, which to block as negatives, or where ad spend is wasted, and name the account. It asks for the date range (14 or 30 days are offered; 30 works best) and lets you change the limits: how many orders a term needs to be a winner (2 by default), how many clicks with no orders count as waste (5) and how many terms to list (25). You get two lists: terms that already bring orders and are worth adding as keywords, and terms that spend money with no orders and are worth reviewing as negatives. The clean HTML report has headline numbers, bar charts of both lists and a clicks-against-spend chart. Its numbers can differ slightly from the Search Terms page in Atom11 because it uses one fixed attribution window. It is read-only: it suggests changes but makes none in your account."
---

# Atom11 Search-Term Opportunities

Produce one read-only decision brief with two review queues for a Sponsored
Ads account: harvest candidates (terms that already convert) and negative
candidates (spend with zero attributed orders). Use Atom11's reviewed
`keyword_opportunities` analysis as the only analytical source. Never
reconstruct its qualification math from raw datasets, and never present the
queues as automatic keyword or negative actions.

## Before running

Confirm the Atom11 MCP exposes `get_my_data_scopes`, `search_data_catalog`,
and `run_analysis`; if not, say the connector must be enabled. Read
[references/audit-methodology.md](references/audit-methodology.md) before
calling the MCP.

## Intake

1. Call `get_my_data_scopes`; select exactly one `ads_profile` by the user's
   account or brand name (show display names to disambiguate; never show a
   `scope_id`).
2. Require an explicit reporting window (exact dates, or a duration converted
   to inclusive dates in the account timezone ending yesterday; if missing,
   ask once and offer 14 or 30 complete days — harvest thresholds need volume,
   so prefer 30 when the user has no preference).
3. In the same question, collect optional thresholds. Defaults:
   - `attribution_window_days`: 14 (SP + SB). Use 7 only if the user asks for
     SP-only.
   - `harvest_min_orders`: 2, `harvest_min_clicks`: 1,
     `harvest_max_acos_percent`: unset.
   - `waste_min_clicks`: 5.
   - `limit`: 25.
   Use the user's values verbatim when supplied.

Tell the user once: this analysis uses a uniform analytical attribution
profile (14-day SP+SB or 7-day SP), so its figures can differ from the
Search Terms dashboard's account-aware profile. For dashboard-parity waste
numbers, the Account Audit skill's waste section is the reference.

## Run the reviewed analysis

1. `search_data_catalog` with intent `keyword opportunities harvest and
   negate`; copy the user's complete request unchanged into `user_question`.
2. Confirm the `keyword_opportunities` recipe; if unavailable, stop and say
   so.
3. Call `run_analysis` once with `date_range` and the parameters above; copy
   the user's request into `user_question`.
4. Treat the returned qualification, counts, and completeness as
   authoritative. If the response is an error envelope (`error`/`message`),
   explain and stop.
5. If freshness warnings show only trailing day(s) incomplete, deliver, then
   offer exactly one rerun ending at the earliest `complete_through` date.

## Write the analyst narrative

```json
{
  "verdict": "One headline of at most 12 words",
  "verdict_note": "Two to four sentences expanding the verdict.",
  "module_notes": {"harvest": "...", "waste": "..."}
}
```

Rules: every sentence quotes a returned number or exact term; one sharp
finding per note (e.g. the highest-order harvest term with its source target,
the costliest zero-order term); review-only verbs — harvest/negative
candidates are reviews, never promises of savings or growth; note when a term
appears in BOTH queues under different targets rather than merging them; if
completeness is partial, say so.

## Produce the deliverable

1. Save the exact `run_analysis` JSON unedited; save the narrative JSON.
2. Run:

   ```bash
   python3 <skill-directory>/scripts/render_report.py \
     --input <analysis-json> \
     --narrative <narrative-json> \
     --output atom11-search-term-opportunities-<account-slug>-<end-date>.html \
     --account-name "<display name>"
   ```

3. Return the file plus at most five evidence-backed review priorities.

If file generation is unavailable, produce a compact Markdown brief with the
same two queues and disclosure rules.

## Non-negotiable controls

- Never call a candidate an automatic add or negative; both queues require
  human relevance, overlap, and business-context review.
- Preserve source context: the same term from different source targets is
  never collapsed into one recommendation.
- Never display campaign, ad-group, or target reference IDs; the source
  target TEXT and match type are the human-readable context.
- Quote the exact qualification (orders/clicks/ACOS thresholds, operator,
  grain, scope) whenever totals are mentioned; zero-order spend is observed
  spend, never guaranteed savings.
- State returned-of-matching coverage for both queues; never generalize a
  bounded list account-wide.
- Never mix this analytical attribution profile's numbers with dashboard
  numbers in one claim.

## Completion check

Account, marketplace, currency, exact dates, and the attribution profile are
visible; both queues show qualification and coverage; no internal IDs; every
narrative sentence traces to returned evidence; the report says review-only;
the HTML has no remote resources.
