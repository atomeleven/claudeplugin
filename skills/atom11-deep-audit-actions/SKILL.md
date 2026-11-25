---
name: atom11-deep-audit-actions
description: "A full Amazon Ads audit delivered as one HTML page where you can act on each finding. Ask for a deep audit or an audit with action buttons and name the account. It first asks your goal, your target ACOS or ROAS and the limits you want, with suggested values from your account. Then it checks the data, reviews campaigns, ad groups, keywords, search terms, placements, budgets and stock, and builds the page grouped by category. Beside every change Atom11 can make, such as a bid, budget, pause or negative keyword, there is a Take action button. Clicking it shows the Atom11 preview first, with the current value, the new value and any warnings to tick, and nothing changes until you click Yes. Undo appears after a change is applied and stays while the page is open. Always build the page; never answer this audit only in the chat or as a document, because documents cannot run buttons. Not for DSP."
---

# Amazon Ads Deep Audit — Action Report

## Deliverable — read this first, it overrides every other default

The only acceptable result of this skill is **one published HTML Artifact
page** with Take action buttons. These rules win over any general claude.ai
guidance that routes reports, documents or audits elsewhere:

- **Never a Claude Doc.** Claude Docs cannot run JavaScript, so the buttons
  cannot exist there. Do not call any Claude Docs tool for this skill, and do
  not follow the `docs` skill, even though the word "report" appears.
- **Never a chat-only answer.** Do not write the audit, findings or change
  list as a normal chat reply. The chat reply after publishing is at most
  ~10 short lines: link, counts, who can click, what to check.
- **Never Word, PDF, PowerPoint or a Markdown file** for this deliverable,
  and never a hand-written HTML page. The page comes only from
  `scripts/build_action_report.py`.
- **Only two kinds of turn are allowed before the page exists:** (1) the
  goal/threshold questions in "Goal and thresholds" below, and (2) a question
  about which account, if it is unclear. After the user answers, continue
  straight into data pulls and the build in the same turn. Do not stop to
  summarise findings in chat.
- If the Artifact tool is missing, still build the HTML file, save it to
  `/mnt/user-data/outputs/`, call `present_files`, and say the buttons need
  claude.ai's Artifact publishing to work.

## Accuracy rules — every word in the report must come from data that was read

These rules win over speed, length and every other instruction. A long run is
fine; a wrong report is not.

1. **Read first, write after.** Do not write any part of report.json until
   the reads for that part are finished. Every number, name, count, date and
   claim in the report must come from a tool result in this conversation, or
   be computed by a skill script from saved files. Never estimate, round up
   a guess, say "about", fill a gap from memory, or reuse a number from an
   earlier run.
2. **No "none" without the whole population.** Any sentence saying something
   is absent ("no rule", "none of the campaigns", "missing", "never",
   "not targeted") needs proof that the full population was read: the saved
   answers' rows equal `total_count` for exactly that population. Without
   that proof write "not checked for N campaigns". The builder refuses
   unproven absence sentences; add `evidence` (`source`, `rows_read`,
   `total_count`, `population`) to a block only when the proof is real.
3. **Partial work says it is partial.** "Scored 5 of 14 rules", and name the
   ones not scored. Never let a sample stand for the whole account.
4. **Save tool answers exactly, with their page info.** Each saved file is a
   list of the query_data answers, copied unchanged, each keeping `rows`,
   `page`, `total_pages`, `total_count`, `has_next`. The scripts treat any
   file that does not prove `rows == total_count` and every page present as
   **not checked**. Keep reads small (only the columns needed, `grain: []`
   totals, `total_count` counts) so copying stays exact; never rebuild rows
   from a pattern.
5. **If the reads don't fit in this turn, stop and say so.** Tell the user
   which reads are done and which are left, and continue in the next turn.
   Never build the page on unfinished reads unless every unread part is
   written as "not checked".
6. **Lists longer than ~5 items are tables**, with full names; if a cell is
   shortened, say exactly how many were left out ("and 12 more").
7. **Every section lists its `sources`** (dataset, window, complete or not).
   The builder refuses a section without them.

### Build order (do every step, in order)

1. Find the skill folder once:
   `SKILL_DIR=$(dirname "$(dirname "$(find /mnt/skills -path '*atom11-deep-audit-actions/scripts/build_action_report.py' | head -1)")")`
   then `view "$SKILL_DIR/references/action-report.md"` and
   `view "$SKILL_DIR/references/atom11-mcp-contract.md"`.
2. `get_my_data_scopes` → pick the account. Ask the goal/threshold questions.
3. Run the audit reads (sections below). Reads only.
4. `get_action_capabilities` once, then `get_action_schema` for each family
   you will use. Write those answers to `/home/claude/audit/schemas.json`.
5. Write `/home/claude/audit/report.json` (shape in `action-report.md`).
   Keep the report's sections (campaigns, ASINs, search terms, budgets,
   placements, ...) and **put each section's fixes directly under its table**
   with a `changes` block, so the Take action button sits beside the
   recommendation. Each change goes in one place only; the end-of-report
   change queue links back to it automatically.
5b. **Automation-rule and recent-change check (required, every time).** Before building,
   check whether an Atom11 automation rule already handles each
   recommendation. Read-only:
   - `query_data` on `automation_rule`: columns `rule_ref, rule, rule_kind,
     rule_subkind, status, deleted, active_start_date, active_end_date,
     conflict_kind`, grain `["rule_ref"]`, page_size 500 → save to
     `/home/claude/audit/rules.json`. `conflict_kind` says whether a
     dayparting rule is ADAPTIVE or OVERRIDE; it is required.
   - `query_data` on `automation_campaign_rule` (the campaign-wise
     automation report): columns `campaign, campaign_ref, rule, rule_ref,
     rule_kind, rule_label, changed_field, rule_status`, grain
     `["campaign_ref", "rule_ref"]`, filters `rule_status eq ENABLED` and
     `campaign_ref in [every campaign_ref the changes touch]`, page_size 500,
     every page → `/home/claude/audit/campaign_rules.json`. (This replaces the
     much larger `automation_rule_action` read; the script still accepts
     `--rule-actions` for older runs.)
   - Budget increases only: `query_data` on `ads_portfolio_setting`, columns
     `portfolio, portfolio_ref, budget_amount, budget_policy, within_budget`,
     grain `["portfolio_ref"]` → `/home/claude/audit/portfolios.json`, and put
     each campaign's `portfolio_ref` (from `ads_campaign_state`) in
     `action.rule_match.portfolio_ref`.
   - Give every change with an `action` an `action.rule_match`:
     `{"campaign_ref": "...", "target_ref": "..."}` (target_ref only for
     keyword/target-level changes).
   - **Recent changes (last 7 days).** Two `query_data` reads on
     `automation_activity`, grain `["event_ref"]`, `date_range` = the last
     7 days through today, `allow_partial: true`, page_size 500, filter
     `campaign_ref in [every campaign_ref the changes touch]`. Read **every
     page** of both:
     1. Manual: filter `action_source eq manual`; columns `event_ref,
        event_timestamp_utc, date_day, action_source, action_kind,
        campaign_ref, object, object_ref, previous_value, new_value,
        run_status` → `/home/claude/audit/history_manual.json`.
     2. Rules: filter `action_source eq rule` **and** `rule_ref not_in
        [every rule_ref whose rule_kind contains DAY_PARTING in
        rules.json]`; columns as above plus `rule, rule_ref, rule_kind,
        reverted` (drop `run_status`) → `/home/claude/audit/history_rules.json`.
        Exclude dayparting by `rule_ref`: a `rule_kind` filter is ignored
        by Atom11 and would return hundreds of thousands of hourly rows.
     For negatives and keyword/target adds, also put the term in
     `action.rule_match.text`.
   - **Dayparting (follow Atom11's own rule).** If a bid or budget change sits
     on a campaign in a live dayparting rule: under an **ADAPTIVE** rule use
     the normal family (`keyword_bid_change`, `product_target_bid_change`,
     `campaign_budget_change`) with the value wanted at 1x: Atom11 takes it as
     the rule's new base. Under an **OVERRIDE** rule the rule rewrites live
     values at its next slot, so use the base-value family instead:
     `dayparting_default_keyword_bid`, `dayparting_default_target_bid` or
     `dayparting_default_budget` (same `entity_id`, new `bid`/`budget`). The
     script checks this and refuses the wrong family.
   - Run `python3 "$SKILL_DIR/scripts/check_rule_coverage.py" --report /home/claude/audit/report.json --rules /home/claude/audit/rules.json --campaign-rules /home/claude/audit/campaign_rules.json --portfolios /home/claude/audit/portfolios.json --history /home/claude/audit/history_manual.json /home/claude/audit/history_rules.json --today <account-local YYYY-MM-DD>`.
   It writes `rule_check` and `recent_change` into each change. In place of
   the Take action button the page then shows:
   - **"Covered by automation rule"** + the rule name, when a live custom
     rule already manages that setting;
   - the **Take action button plus a "Dayparting" note**, when only a
     dayparting rule manages it (ADAPTIVE: new base at 1x; OVERRIDE: the
     base value changes from the next slot);
   - **"Portfolio budget used up"**, when a budget increase can't help
     because the campaign's capped portfolio is out of budget;
   - **"Wait until <date>"** + a plain message (who changed it, when,
     old → new value, and the date it can be changed again), when the
     same setting on the same keyword/target/campaign was changed in the
     last 7 days, manually or by a rule. Hourly dayparting does not count;
     reverted rule changes and failed manual changes do not count.
   Every other change keeps the button. Never write `rule_check` or
   `recent_change` by hand. Do not recommend the change anyway in the text
   above the card: say it is on hold and why. The builder refuses to build
   until this has run. Also mention covered changes in the section's text
   ("2 of these are already handled by rules"), and list the rules checked
   with their `as_of` time in the scope section.
5c. **Automation health section (required when the account has rules).**
   Every read here is small and fits in a conversation. Save each answer
   with its page info (accuracy rule 4).
   - **Rank the rules (one read):** `automation_activity`, grain
     `["rule_ref", "rule", "action_kind"]` (Atom11 rejects `["rule_ref",
     "rule"]`), columns `rule_ref, rule, action_kind, actions_count`, filter
     `action_source eq rule` and `rule_ref not_in [dayparting rule_refs]`,
     `date_range` = the scoring window: the 15 days ending 5 days before today
     (rule results need a complete 5-day after-window). Use these **same
     dates** for every read in this step, so counts match across tables
     → `/home/claude/audit/rule_activity.json`.
   - **Bid-rule scorecard:** for the **8 most active rules that changed bids**
     (`action_kind` BID_CHANGE_KEYWORD / TARGET_BID_CHANGE; fewer if fewer
     acted), one `query_data` on
     `automation_rule_performance` with `grain: []`, filter `rule eq <rule
     name>`, `date_range` = the same scoring window, columns
     `actions_count, acos_positive_count, acos_negative_count,
     orders_positive_count, orders_negative_count, spend_before, spend_after,
     sales_before, sales_after`. The script lists every other active rule as
     "Not scored in this report" with its change count.
   - **Dayparting scorecard:** for up to **3** live dayparting rules, one read
     each on `automation_dayparting_performance`, grain `["rule_ref",
     "week_start"]`, filter `rule_ref eq <id>`, columns `rule_ref,
     week_start, spend, roas, is_rule_start_week`; put the rule's start date
     in `rule_start_date`. Rules not read are listed as not scored.
   - **Rule map:** reuse the step 5b file (`campaign_rules.json`, the
     campaigns this report changes) and pass the exact `campaign_ref in`
     list as `rule_map_campaign_refs`. Do **not** try to read the map for
     every campaign in the account. The section then says which campaigns
     were checked, and "not checked" for the rest.
   - **Rule counts (for Pause / Remove cards only):** for each rule that will
     get such a card, one read on `automation_campaign_rule`, filters
     `rule_ref eq <id>` and `rule_status eq ENABLED`, grain
     `["campaign_ref", "rule_ref"]`, `page_size: 1` → its `total_count` is the
     number of campaigns the rule runs on → `/home/claude/audit/rule_<id>_count.json`.
   - Write `/home/claude/audit/health.json` (shape in the script's header: file
     paths, `rule_map_campaign_refs`, the audited campaigns with spend,
     `rule_perf`, `dayparting`, `rule_counts`) and run
     `python3 "$SKILL_DIR/scripts/automation_health.py" --input /home/claude/audit/health.json --output /home/claude/audit/health_out.json`.
     Read its `Note:` lines and fix what you can (for example a missing page).
   - Add its `section` to report.json after the other analysis sections and
     before the change queue. Keep its facts and its cautious phrasing ("ACOS
     got worse after 37 of 56 flagged changes. Worth reviewing."); never say a
     rule "is bad" or "caused" anything, and never add numbers or names that
     are not in it. Rule overlap comes out as two tables ("Rules that change
     the same settings", "Which campaigns share which rules"); keep them as
     tables.
   - For a rule in `review_rules`, you may offer **Pause rule**
     (`autorules_rule_state`, `{"entity_id": "<rule_ref>", "operation":
     "pause"}`, one rule per change) or, when only some campaigns suffer,
     **Remove campaign from rule** (`autorules_rule_campaigns`, operation
     `remove`). Copy `rule_scopes[rule_ref]` from the script output into the
     change's `rule_scope` (it carries the proven `campaign_count`), plus
     `"removed": [names]` for a remove. If `rule_scopes[rule_ref].complete` is
     false, give no button: write the change with `manual_reason` "full
     campaign list for this rule was not loaded". The builder enforces this.
     No other rule-level action gets a button.
6. Build:
   `python3 "$SKILL_DIR/scripts/build_action_report.py" --input /home/claude/audit/report.json --schemas /home/claude/audit/schemas.json --output /mnt/user-data/outputs/<account-slug>-deep-audit.html --server "<Atom11 connector display name>"`
   If it prints "Not built", fix `report.json` and run it again. Never
   hand-edit the HTML.
   The file name must have **no spaces** (letters, digits, `-` only, e.g.
   `acme-us-deep-audit.html`): the Artifact tool refuses names with spaces.
7. Call `Artifact` action `capabilities` (required before declaring `mcp`).
8. Call `Artifact` action `publish` with that `file_path`, a favicon, and
   `capabilities: {"mcp": {"servers": [{"server": "<same display name>", "tools": ["get_my_data_scopes", "get_action_capabilities", "propose_actions", "confirm_actions", "cancel_actions"]}]}}`.
9. Reply briefly (see "Tell the user" in `action-report.md`). Done.

The connector display name is the name of the Atom11 server in this
session's tool list (for example `Atom11 MCP`). Use the exact same text in
step 6 and step 8.

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

## Report buttons (this edition)

This edition delivers the audit as one HTML page with a **Take action**
button beside every recommended change Atom11 can apply, and **Undo** after a
change is applied. The approval boundary above governs Claude's own tool
calls: while building the report Claude reads only and never calls
`propose_actions`, `confirm_actions` or `cancel_actions`.

The buttons are the human's own controls. A click on Take action is the
human's explicit request for that one preview. The page then shows Atom11's
complete preview (current and new value, every warning, expiry and undo
support); a warning needs a tick before Yes works; Yes confirms exactly that
proposal and nothing else; No cancels it. Undo runs the same preview, tick and
Yes cycle on the `undo` family. The page never confirms without a click,
never batches, never retries a write on its own, and pauses every button when
an outcome is unknown. Requests made in the chat still follow
[the approved action workflow](references/approved-actions.md).

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

## Action report

Read [the action report guide](references/action-report.md) before building
the deliverable. In short:

1. Finish the audit and the change queue as above. One change queue row = one
   change card = at most one button.
2. For every change Atom11 can apply, call `get_action_capabilities` once and
   `get_action_schema` for each family used; save those answers as
   `schemas.json`. Build each payload exactly to its schema from the entity
   references the read data returned, and record the value the report saw in
   `report_before`.
3. Changes Atom11 can't apply (retail, listing, creative, campaign creation,
   irreversible families, anything outside Atom11) stay in the queue with a
   `manual_reason` instead of a button.
4. Write the report document (`report.json`) and run
   `python3 "$SKILL_DIR/scripts/build_action_report.py" --input report.json --schemas schemas.json --output /mnt/user-data/outputs/<account-slug>-deep-audit.html --server "<connector name>"`
   (use the full path: the working folder is not the skill folder).
   Fix every problem it lists; never hand-edit the HTML to get past a check.
5. Publish the page as an HTML Artifact and declare the `mcp` runtime
   capability for the Atom11 connector with exactly `get_my_data_scopes`,
   `get_action_capabilities`, `propose_actions`, `confirm_actions` and
   `cancel_actions`. Use the connector's display name from this session in
   both the declaration and `--server`.
6. Tell the user who can use the buttons, that the first click asks to allow
   the page to use Atom11, that actions run under the clicker's own Atom11
   login, and that Undo stays only while the page is open (after that, the
   page shows a code to give Claude in chat).

If this surface can't publish an Artifact with runtime capabilities, still
publish the report, say plainly that its buttons will be switched off, and
offer the chat approval workflow for any change the user picks.

## Completion

The audit is complete only when all sources are logged, scope/freshness is explicit, spend and material ASINs are accounted for, detailed recommendations trace to evidence, data gaps are classified, the system can be refreshed, and the handoff gives decisions rather than merely data.

## Atom11 binding (native edition)

This binding implements the audit method using Atom11 read evidence. The approval boundary above governs every proposed action.

**Audit contract.** `get_my_data_scopes` supplies advertiser display name, marketplace, currency, timezone and `available_domains` for the authorized accounts; The account report states its metric profile; Seller/Vendor/hybrid context must come from an explicit returned channel/field or user confirmation. The final common complete date is the earliest relevant known `complete_through` across all contributing sources; missing metadata remains unknown. DSP stays separate scope unless explicitly included, which matches Atom11's own policy (exact DSP display name confirmed by the user).

**Goal and thresholds.** First read the account's own settings (read-only):
`query_data` on `ads_profile_setting`, columns `account_name, account_type,
default_target_acos, target_tacos, future_target_acos_conditions, currency,
reporting_timezone`, grain `["account_name"]` (the only grain it takes with
these columns). `account_type` (seller/vendor) sets the attribution window.
Per-campaign targets are in `ads_campaign_state` (check its schema for the
column). Then, before recommending any change, ask the user to confirm the
goal metric (ACOS or ROAS) and its target, offering the Settings value first
("Your Atom11 target ACOS is 25%. Use it?"); whether campaign-level targets
apply; and every threshold or step size the recommendations will use, each
with a suggested value worked out for the account (for example "account
average ACOS 27.4%"). When Settings has no target, suggest one from the
account average as before. Use exactly what the user gives; use a suggested value
only when the user accepts it. Never fill the target in silently. Show the
values used in the report's scope section.

**Source hierarchy, item 4.** Atom11 provides advertising actuals, server totals and coverage metadata (section 5 of the contract); synced state for campaign status, serving eligibility, budgets, targeting mode, negatives and keyword bids; retail sales, inventory run-rate and product-catalog observations. Use returned `as_of` timestamps where available; missing sync metadata is unknown. Native Amazon Ads controls live saved settings and readback.

**Completeness rules, on Atom11.**
- 100% of active spend: `account_report` returns exact advertising totals by SP/SB/SD with `sponsored_type_coverage` per channel (`complete_with_data`, `complete_no_activity_rows`, or incomplete = unknown, never zero). Quantify the unresolved remainder from an incomplete channel as unknown.
- 95% of imported spend in search-term/target review: retain this gate. Use a compatible recipe summary or supported account-total query as the exact denominator, then sum distinct additive spend in reviewed detail with the same scope, dates, filters and attribution. Report spend coverage separately from row coverage. Page within documented limits where needed; search-term populations can omit campaign spend, and keyword/target/query slices can overlap. If 95% cannot be established, mark the gate unmet with the exact missing evidence. Direct `summarize: true` is currently rejected by the MCP wrapper; use the contract's supported alternatives.
- Every planned and materially advertised ASIN: `ads_advertised_product` (dated, paged by `product`) joined on ASIN to `retail_run_rate` / `product_catalog` for stock, price and availability; `asin_daily` gives ads vs retail vs current stock per ASIN in one reviewed call; `ineligible_ad_products` and `campaign_out_of_stock_products` give the paid-activation blockers.
- Every active ad format: read `sponsored_type_coverage`; SD has no placement report.

**Audit sequence, Atom11 sources per step.** Step 4 retrieval: performance → recipes and datasets in section 6 of the contract; current settings → `campaign_health`, `ads_campaign_state`, `ads_eligibility_campaign`, `ads_negative_target`, `ads_keyword` (`current_bid`); retail/inventory/catalog/destination → `retail_sales`, `retail_run_rate`, `restock_priority`, `product_catalog`, digital-shelf datasets; creative and economics → not in Atom11 (log as blocked or sourced elsewhere). Step 5 normalization: ASIN/SKU and schema-defined refs support scoped joins; many entity refs map to source IDs, so treat them as sensitive and verify cross-system identity. Duplicate names require disambiguation. Step 6 reconciliation: compare compatible additive detail with authoritative server totals and preserve unexplained residuals. Step 7 audit levels: campaign, ad group, target, query, match type, placement, advertised product, budget, portfolio map to this package's `references/atom11-analysis-map.md`; purchased product and creative/destination are outside Atom11.

**Change queue.** Fill the template with current observed values, exact proposed changes, evidence, risks, approval requirement and review/rollback conditions. New rows start at `planned` in the state model; `ready for approval` only once the preview has been shown, `approved` only from the human's reply. If the human explicitly requests an action, use [the approved action workflow](references/approved-actions.md), show the complete returned preview, end the turn, and wait for a new exact-proposal approval before confirming. Cancellation and undo follow that protocol; no automatic rollback. Native Amazon remains the authority for live saved-state verification.

**Refresh SOP.** A refresh reruns the same recipes and queries with the next window; Atom11's comparison datasets derive the preceding equal window, so refreshes never label overlapping trailing windows as sequential periods.


Atom11 specifics for every step above are in [references/atom11-mcp-contract.md](references/atom11-mcp-contract.md); read it before the first Atom11 call. Read [the analysis map](references/atom11-analysis-map.md) when selecting task-specific sources. Use the bundled `assets/` intake, source-log, module-status and change-queue templates; the action report is built from `assets/action-report-template.html` by `scripts/build_action_report.py`.

## Completion check

Before delivering, confirm:

- The result is a published HTML Artifact built by `build_action_report.py`
  (not a chat answer, not a Claude Doc, not Word/Markdown).
- Every change with an action was checked against automation rules by
  `check_rule_coverage.py`; covered ones show "Covered by automation rule"
  instead of a button.
- Every change with an action was checked for changes in the last 7 days
  (manual and non-dayparting rule changes); those show "Wait until <date>"
  with a plain message instead of a button.
- The account's Settings target ACOS/TACOS was offered first in the goal
  questions.
- Dayparted bids/budgets use the right family (ADAPTIVE: normal; OVERRIDE:
  dayparting base value), checked by the script.
- When the account has rules, the Automation health section is present and
  built by `automation_health.py`; any Pause rule / Remove campaign change
  carries a `rule_scope` with a proven `campaign_count`.
- Nothing in the report was written before its data was read; no number or
  name was estimated; every "no / none / missing" sentence has full-population
  proof or says "not checked"; partial scoring names what was not scored;
  every section has `sources`; long lists are tables.
- Every recommendation tied to a table (campaign, ASIN, search term, budget,
  placement) sits in a `changes` block right under that table.

- The goal metric, target and thresholds came from the user (or values the
  user accepted) and are shown in the report.
- Every change card traces to evidence in the report; every change with a
  button passed `build_action_report.py` against the saved schemas for this
  account; every other change shows why it has no button.
- No `propose_actions`, `confirm_actions` or `cancel_actions` call was made
  while building the report.
- The page was published with the `mcp` capability for the connector named in
  `--server`, or the user was told the buttons are switched off and why.
- No scope, entity reference, trace or interaction identifier appears in the
  visible text.
