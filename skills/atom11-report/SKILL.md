---
name: atom11-report
description: "Builds a clean, shareable HTML report from your Atom11 data. Ask for any report, review, recap, summary, scorecard or update, or ask how you did this week or month, even without the word report. Report types include weekly or monthly business review, account performance, campaigns, search terms, products, inventory, DSP, ads and DSP together, goals, placements, dayparting, Search Query Performance, digital shelf, recommendations and automation activity. Name the account and dates; if dates are missing it asks once and offers the last 7, 14 or 30 days. Every number in the report is checked against the Atom11 data before the report is made, and missing or partial data is stated clearly. You get headline numbers with changes against the period before, charts, tables and a short list of what to review. It can also save your report setup and run it every week or month. Not for a single number or for changing your account."
---

# Atom11 Report

Produce one trustworthy, client-ready report for one authorized Atom11 account
by running reviewed Atom11 analyses and rendering them in the Atom11 decision
brief design. The report is read-only and review-only: it ranks what a human
should look at, it never changes an Amazon account, and every number in it is
a number the Atom11 MCP returned.

The skill has two entry points:

- **On demand** — the user asks for a report in conversation. You resolve the
  brief with at most one round of questions.
- **Scheduled** — a saved *report profile* (JSON) describes the account,
  cadence, modules and options. A scheduled run reads the profile, resolves the
  reporting window itself, asks nothing, and delivers.

Both paths end in the same place: a report document, rendered by the bundled
renderer, plus a short chat recap.

## Before running

Confirm the connected Atom11 MCP exposes `get_my_data_scopes`,
`search_data_catalog`, `get_data_schema`, `query_data` and `run_analysis`. If
not, say the Atom11 connector must be enabled and authenticated; never
substitute another source and call it an Atom11 report. Scheduled runs cannot
re-authenticate, so a connector that answers "unauthenticated" ends the run
with a plain-language note telling the owner to reconnect the connector.

Read these before calling the MCP, in this order:

1. [references/report-types.md](references/report-types.md) — what each named
   report contains and when to pick it.
2. [references/module-catalog.md](references/module-catalog.md) — one card per
   module: the Atom11 analysis behind it, its parameters, what to read from
   the result, and what must be disclosed. Read only the cards you will run.
3. [references/report-document.md](references/report-document.md) — the JSON
   the renderer consumes, before you compose.

Read [references/scheduling.md](references/scheduling.md) when setting up or
executing a scheduled run, and
[references/report-profile.md](references/report-profile.md) when creating or
editing a profile.

## Step 1 — Resolve the brief

A brief is: one account, one window, one report type, the module list, and
the options the modules need. Fill it from a profile when one is supplied;
otherwise from the conversation.

**Account.** Call `get_my_data_scopes` first and select exactly one
`ads_profile` by the user's account or brand name (retail data rides on it).
If the name is absent or ambiguous, show only display names, marketplaces and
currencies and ask. Never show a `scope_id`. DSP is never implied: a DSP
module runs only when the user or profile explicitly asks for DSP, and only
on a `dsp_advertiser` whose exact display name they confirmed; never pair a
DSP advertiser to an Ads profile from similar names. The one exception is a
scope card whose `ads_profile_linkage` is `declared`: that mapping is
operator-verified, so an explicit DSP request for that brand may use the
declared advertiser directly. Do not offer DSP as an option in the normal
account follow-up.

**Window.** Dated modules need an explicit inclusive window. Accept exact
dates or an explicit duration; convert durations to exact dates in the
account timezone, ending yesterday. If no window is given, ask once and offer
the last 7, 14 or 30 complete days (a monthly report defaults to the last
complete calendar month). As-of modules (inventory, serving, recommendations)
take no window and must not be described as period data. In a scheduled run
the profile's cadence resolves the window; run
`python3 <skill-directory>/scripts/plan_report.py --profile <profile.json>`
to compute it deterministically, and never ask.

**Report type and modules.** Match the request to a report type in
`report-types.md`; use its default modules unless the user or profile adds or
removes some. "Everything" is not a report type: pick `monthly` as the widest
sensible default and say what is in it. One report can take several minutes
across many analyses, so do not add modules nobody asked for.

**Options.** Fold every optional decision into the same single question:
target ACOS or TACoS (used only to frame the narrative, never invented),
thresholds the modules expose (wasted-spend click threshold, days-of-cover,
list sizes), and anything to prioritize. Use defaults from the catalog cards
when the user does not care. Preserve user-supplied values verbatim.

Interactive runs ask at most once. Scheduled runs never ask: a missing or
ambiguous account, a profile that fails `plan_report.py`, or a connector that
cannot be used ends the run with a short, honest explanation of what to fix.

## Step 2 — Run the modules

Each module maps to one reviewed Atom11 analysis (`run_analysis` with a
recipe id) or one bounded dataset query (`get_data_schema` then
`query_data`). The catalog card for each module says which. Reviewed
analyses own all cross-dataset math; you never recompute, adjust, blend or
replace a value they return, because different metric profiles and
attribution windows do not mix into one figure.

For every module:

1. Call `search_data_catalog` under the selected scope with the card's
   intent and confirm the expected recipe or dataset id. One search that
   already returned the cards you need serves several modules. If
   `match_status` is `ambiguous`, follow `clarification_note`. If the recipe
   is missing, or the card says `scope_availability: unavailable`, mark the
   module unavailable with the card's reason in plain words; do not rebuild
   it from raw datasets. The scope's `available_domains` from
   `get_my_data_scopes` already tells you which module groups can run at
   all (no `DIGITAL_SHELF` means no digital-shelf modules, and so on).
2. Call `run_analysis` once (or `get_data_schema` once then `query_data`) with
   the window and only the parameters the user or profile changed. Copy the
   user's complete request unchanged into `user_question` on every call; in a
   scheduled run that is the profile's standing request line. Pass the
   `interaction_id` from the first result to every further call in this run.
3. Save the exact JSON response to its own file, unedited. These files are
   the evidence the renderer verifies against.
4. On an error envelope (`error`/`message` instead of `outputs`), record the
   message for that module and continue with the others. Never retry with
   invented parameters. A report with one failed section is still delivered;
   the section keeps its heading and says what happened.
5. Treat returned coverage, freshness, comparison permissions and
   completeness fields as authoritative.

**Freshness.** Sponsored Ads data lands a day or more late. When freshness
warnings show only the trailing day(s) of the window incomplete, deliver
this report with the warning beside the affected numbers. Interactively, then
offer exactly one rerun ending on the earliest `complete_through` date so
comparisons can qualify. In a scheduled run, apply the profile's
`freshness_policy` (see `scheduling.md`) and say in the report which rule
applied.

Keep the whole run read-only. Use no write-capable tool even if the connector
exposes one; a report never proposes, confirms or applies an action.

## Step 3 — Compose the report document

Write one JSON file in the shape defined by `report-document.md`: report
metadata, ordered sections, a decision queue and trust notes. Each section
carries KPIs, tables, bullets and warnings taken from exactly one module's
result, following that module's catalog card for which fields to read and
how to label them.

Rules that make the document trustworthy:

- Every KPI value, previous value, percent change and table cell is copied
  from a returned result. The renderer checks each one against the evidence
  files and refuses to render a value it cannot find. Fix the document, not
  the evidence.
- Show a percent change only where the result says it is permitted
  (`percent_change_permitted` true). Otherwise leave the change out; the
  renderer draws a muted dash. Never compute a delta yourself.
- Keep ad-attributed and whole-store retail figures labelled as such; keep
  promoted and halo DSP figures separately labelled; never present retail
  minus ad sales as organic.
- Bounded lists stay bounded: write coverage as "top 10 of 312 matching
  campaigns" using returned counts; never say "all" unless the result says
  complete.
- Use the business labels Ad Spend, Ad Sales, Ad Orders, Ad Clicks,
  Impressions, ROAS, ACOS, and plain source labels such as "Sponsored
  Products data". Never show scope ids, recipe, dataset, variant, trace or
  interaction ids, leg names, table names, or any `_ref`/`_id` value.
- An incomplete Sponsored Ads type is unknown, never zero or inactive.

**Narrative.** You supply the reading; the renderer supplies the numbers.
Write a verdict of at most twelve words, a two-to-four sentence verdict note,
and one analyst note per section — the single thing the reader must take
away, quoting the exact returned value or name. Review-only verbs (review,
validate, investigate, confirm); never "pause", "negate", "raise the bid",
"move budget", or a promise of savings or growth. State co-movement, not
cause; no projections, no invented benchmarks; a target appears only when
the user supplied it. If comparisons were suppressed or data is partial, the
verdict says so instead of claiming a trend. If you have no evidence-backed
reading for a section, omit its note rather than restating what it contains.

**Decision queue.** Build it from the modules' own review flags and the
sharpest bounded findings, each with its evidence line. Keep server order
when unlike quantities cannot be ranked safely; do not invent a health score.

## Step 4 — Render and deliver

1. Run the renderer with the document and every evidence file:

   ```bash
   python3 <skill-directory>/scripts/render_report.py \
     --document <report-document.json> \
     --evidence <evidence-dir-or-files> \
     --output atom11-<report-type>-<account-slug>-<end-date>.html
   ```

   It fails with a list of unverifiable values or forbidden identifiers. Fix
   the document and rerun; do not pass `--no-verify` except for a preview the
   user explicitly asked for, and say so in the recap if you did.
2. Return the file plus a recap of at most five evidence-backed review
   priorities, the exact window, and any completeness caveat. In a scheduled
   run the recap is the delivered message.

If the host cannot write or execute files, produce a compact Markdown report
with the same section order, labels and disclosure rules. Do not hand-author
imitation HTML.

## Scheduling a report

When the user wants the report "every week" or "every month", first run the
report once interactively so they can approve the modules and options, then
save those choices as a profile (`report-profile.md`) and create the
scheduled task from the template in
[assets/scheduled-task-prompt.md](assets/scheduled-task-prompt.md), with the
profile JSON embedded, because a scheduled run starts with no memory of this
conversation. `scheduling.md` covers the platform steps, the run-time rules,
and the window rule for each cadence. Prefer a run time a day or two after
the window closes so late-arriving Sponsored Ads data is complete.

## Non-negotiable controls

- Read-only, review-only; findings are prompts for a human decision.
- No internal identifiers in the report or recap.
- No client-side math over returned values; no blended metrics except from
  the blended analysis the user explicitly requested.
- Percent changes only where permitted; bounded results stay bounded;
  as-of snapshots are never period data.
- Null inventory is unknown; a missing ad type is unknown; observed zero-order
  spend is never "recoverable savings".
- Freshness and coverage warnings sit beside the affected content, with one
  consolidated trust note at the end.
- The HTML contains no remote scripts, fonts, images or tracking.

## Completion check

Before delivery confirm: account name, marketplace, currency and exact
window are visible; every planned module is present or explicitly marked
unavailable/failed/skipped with a reason; suppressed comparisons show no
deltas; coverage is stated for every bounded list; the narrative traces to
returned values and names; the report says it is read-only; the renderer
verified every value; no internal identifiers appear anywhere.
