# Action report guide

How to turn a finished deep audit into one HTML page with a **Take action**
button beside each change Atom11 can apply, and **Undo** after it is applied.
Claude builds and publishes the page; only a human click on the page asks
Atom11 for a preview, applies it or undoes it.

## 1. The report document (`report.json`)

```json
{
  "title": "One With Nature Deep Audit",
  "account": {"display_name": "<exact display_name from get_my_data_scopes>",
              "marketplace": "US", "currency": "USD", "scope_type": "ads_profile"},
  "window": {"start": "2026-09-28", "end": "2026-10-27", "latest_complete_date": "2026-10-27"},
  "prepared": "2026-11-03",
  "summary": ["Three to five short lines: the decisions, not the data."],
  "sections": [
    {"title": "Scope, sources and data gaps", "blocks": [
      {"type": "bullets", "items": ["..."]},
      {"type": "callout", "tone": "warn", "title": "Data gap", "text": "..."}]},
    {"title": "Account performance", "blocks": [
      {"type": "tiles", "items": [{"label": "Ad spend", "value": "$8,420", "note": "Previous: $8,390"}]},
      {"type": "table", "columns": ["Ad type", "Spend", "ACOS"], "align": ["l", "r", "r"],
       "rows": [["Sponsored Products", "$7,150", "30.6%"]], "caption": "Source and window."}]},
    {"title": "Campaign routes", "blocks": [
      {"type": "table", "columns": ["Campaign", "Spend", "ACOS", "Route"], "align": ["l", "r", "r", "l"],
       "rows": [["Garden hose - SP - Exact", "$640", "48%", "Reduce"]]},
      {"type": "changes", "title": "Fixes for these campaigns", "ids": ["C1"]}]}
  ],
  "categories": ["Bids", "Negatives", "Harvest", "Budgets", "Pause", "Outside Atom11"],
  "changes": [
    {"id": "C1", "category": "Bids", "priority": "P1", "decision": "Reduce",
     "entity": "garden hose 50 ft", "tags": ["Sponsored Products", "Exact"],
     "current": "$1.85", "proposed": "$1.48", "change_note": "−$0.37 · −20%",
     "why": "ACOS 48% against a 30% target on $640 spend.",
     "details": {"evidence_window": "...", "root_cause": "...", "expected_benefit": "...",
                 "risk": "...", "confidence": "High", "owner": "...", "review_date": "...",
                 "hard_stop": "...", "rollback": "..."},
     "rule_check": {"status": "not_covered"}, "recent_change": {"status": "none"},
     "action": {"family_id": "keyword_bid_change", "ad_type": "SP",
                "rule_match": {"campaign_ref": "<campaign_ref>", "target_ref": "<keyword_ref>"},
                "payload": {"items": [{"entity_id": "<keyword_ref>", "bid": 1.48}]},
                "report_before": {"<keyword_ref>": "1.85"}}},
    {"id": "C7", "category": "Outside Atom11", "priority": "P1", "decision": "Repair",
     "entity": "50 ft hose listing", "why": "...",
     "manual_reason": "Seller Central change; Atom11 can't apply it."}
  ]
}
```

- `account.display_name` and `marketplace` must match `get_my_data_scopes`
  exactly: the page finds the account by them at click time. Never write a
  `scope_id` anywhere; it differs for every Atom11 login.
- Section order follows the audit: summary, scope and data gaps, performance
  and reconciliation, key findings, campaign routes, product readiness, search
  terms, then monitoring and refresh. The builder adds the change queue
  (grouped by `categories`, then any category not listed) and a "How the
  buttons work" section.
- **Put each fix right under the table it comes from.** After a campaign
  table, add a `changes` block with the ids of the campaign fixes; after the
  ASIN/product table, the ASIN fixes; after the search-term table, the
  search-term fixes; and so on for every section with recommendations:
  `{"type": "changes", "title": "Fixes for these campaigns", "ids": ["C1", "C2"]}`.
  The Take action button then sits next to the data that justifies it. Each
  change id may appear in only one `changes` block (one button per change).
  The change queue at the end still lists every change: placed ones show as
  a short row with their live status and a link up to their button; changes
  not placed anywhere (account-wide, outside Atom11) show there in full.
  Place every change that belongs to a table; leave only genuinely
  account-wide items for the queue.
- **Every section needs `sources`**: a list of short strings naming the datasets, window and whether the read was complete, e.g. `"ads_campaign, Oct 24 – Nov 22 2026 (complete, 76 of 76 rows)"`. The page shows them as a “Data:” line under the section. The builder refuses a section without them.
- **Absence sentences need proof.** A block whose text says something is absent (“no rule”, “none of the campaigns”, “missing”) must carry `"evidence": {"source", "rows_read", "total_count", "population"}` with `rows_read == total_count`, or the sentence must say “not checked”. A report-level `evidence` list of `{"text", "proof"}` also works for one-off sentences. Otherwise the build fails.
- Tables may carry a `title` (shown above the table). Use tables, not bullets, for any list longer than ~5 items; the builder warns about repeated bullets and very long cells.
- Block types: `changes` (`ids`, optional `title`), `paragraph` (`text`), `bullets` (`items`), `table`
  (`columns`, `rows`, optional `align` with `l`/`r`, `caption`), `callout`
  (`tone` info/warn/bad/ok, optional `title`, `text`), `tiles` (`items` of
  `label`, `value`, optional `note`). All text is plain; the builder escapes it.
- **Automation rules.** Every change with an `action` carries
  `action.rule_match` (`campaign_ref`, and `target_ref` for keyword/target
  changes) and, after `scripts/check_rule_coverage.py` runs, a `rule_check`:
  `{"status": "covered", "rules": ["<rule name>"], "what": "keyword bids"}`,
  `{"status": "not_covered"}` or `{"status": "unknown", "note": "..."}`.
  Covered → the page shows "Covered by automation rule" and the rule name
  instead of the button (Take action would fight the rule). Unknown → the
  button stays with a note that rules couldn't be checked. Never write
  `rule_check` by hand; the script decides it from the rule data. A rule
  counts only when it is ENABLED, not deleted, inside its active dates, and
  has an ACTIVE action row changing the same field (for example
  `BID_CHANGE_KEYWORD` for a keyword bid) on the same campaign, and on the
  same target or the whole campaign.
- **Recent changes (7-day wait).** The same script, given `--history`,
  writes `recent_change`: `{"status": "recent", "source": "manual" | "rule",
  "rule": "<name if rule>", "date": "YYYY-MM-DD", "before": "...", "after":
  "...", "wait_until": "YYYY-MM-DD", "wait_days": 7}`, `{"status": "none"}` or
  `{"status": "unknown", "note": "..."}`. Recent → the page shows "Wait
  until <date>" and a plain sentence instead of the button, for example:
  "This was changed manually on Oct 30 ($52.00 → $40.00). A change needs
  about 7 days to show results, so it’s best not to change it again yet.
  You can act on this from Nov 6." Order: covered by a rule first, then
  wait, then the button. Unknown keeps the button with a short note.
- `details` keys map the change-queue template columns; leave out what you
  don't have.
- Visible text never carries scope, entity reference, trace or interaction
  identifiers. Entity references belong only inside `action.payload` and
  `action.report_before`.

## 2. Action data for each change

1. Call `get_action_capabilities` once for the account. Use only families it
   lists without a `blocked_reason`.
2. Call `get_action_schema` for every family the report uses. Save the answers
   keyed by `family_id` as `schemas.json`:
   `{"keyword_bid_change": {"family": {...}, "payload_schema": {...}, "bounds": {...}}, ...}`.
3. Build `payload` exactly to `payload_schema`: the entity references the read
   data returned (`keyword_ref`, `target_ref`, `ad_group_ref`, `campaign_ref`,
   and so on, as the schema's `entity_id` describes), and the proposed value in
   the schema's units. Do not round, clamp or split a value to fit a bound;
   change the recommendation instead, or leave it without a button and say why.
4. `report_before` maps each entity reference to the value the report saw. The
   page compares it with Atom11's current value at click time and says so when
   it has changed.
5. Keep one entity per change unless several must move together; a button
   makes one preview of exactly that payload.

Families that never get a button (use `manual_reason`):

| Family or kind | Why |
|---|---|
| `undo` | Offered on the page after a change is applied |
| `campaign_create` | Needs its whole template reviewed in chat |
| Rule set-up: `autorules_rule_create`, `_clone`, `_edit`, `_delete`, `_run_now`, `_adgroups_refresh`, `dayparting_rule_create`, `dayparting_schedule_edit`, `dayparting_rule_campaigns`, `dayparting_defaults_sync` | Too big or permanent for one click on a report; prepare in chat if asked |
| Any family with `irreversible: true` (renames, portfolio moves, archiving negatives) | Can't be undone; prepare it in chat with the approved action workflow if the user asks |
| Retail, listing, creative, pricing, DSP or anything outside Atom11 | Atom11 can't apply it |

Families whose `undo_supported` is `no` (for example `search_term_to_keyword`)
get a button; the preview and the result say that Atom11 can't undo them.

Rule-level buttons (only in the Automation health section):

| Family | Allowed operation | Required on the change |
|---|---|---|
| `autorules_rule_state` | `pause`, one rule | `rule_scope: {"rule", "campaigns": [every campaign in it]}` |
| `autorules_rule_campaigns` | `remove` | `rule_scope` as above plus `"removed": [campaigns leaving]` |

The card and the preview both state who is affected, naming every campaign
in the rule; the preview needs its own tick before Yes. Pausing: "This changes
the rule itself, so it affects every campaign in it…". Removing: "This
changes the rule “X”, which runs on N campaigns. Y will leave the rule… The
rule keeps running on the other N−1 campaigns: …". Neither can be undone from
the page; the text says how to put it back in Atom11.

Dayparting base values (`dayparting_default_budget`,
`dayparting_default_keyword_bid`, `dayparting_default_target_bid`) get a
normal button with a "Dayparting" note; use them only for campaigns in an
OVERRIDE dayparting rule (the script enforces this).

`portfolio_check` (written by the script for budget changes): `{"status":
"capped", "portfolio", "budget", "policy"}` replaces the button with
"Portfolio budget used up"; `ok` keeps it; `unknown` keeps it with a note.

## 3. Build

```bash
python3 "$SKILL_DIR/scripts/build_action_report.py" --input report.json --schemas schemas.json \
    --output /mnt/user-data/outputs/<account-slug>-deep-audit.html --server "<Atom11 connector display name>"
```

The script refuses to build, listing every problem, when a family is unknown,
blocked, irreversible or not offered as a button; a payload doesn't match its
schema; an ad type isn't supported; an item count is over the family limit;
`report_before` names an entity the payload doesn't; a change has neither an
action nor a `manual_reason`; or visible text carries an internal identifier.
Fix the document and run it again. `--mode preview_only` builds a page whose
buttons preview and cancel but can't apply; use it only when the user asks for
that. `--demo` is for sample previews only and never goes into a real report.

## 4. Publish

Always publish as an HTML Artifact. Never a Claude Doc (it can't run the
buttons), never a chat answer, never Word or Markdown.

Publish the built file as an HTML Artifact and declare this runtime capability
(the server name is the Atom11 connector's display name in this session, the
same text passed to `--server`):

```json
{"mcp": {"servers": [{"server": "Atom11 MCP", "tools": [
  "get_my_data_scopes", "get_action_capabilities",
  "propose_actions", "confirm_actions", "cancel_actions"]}]}}
```

Declare nothing else. If the surface can't declare runtime capabilities,
publish the report anyway and tell the user the buttons will show as switched
off; offer the chat approval workflow for any change they pick.

## 5. What the page does

For each Take action click, with the clicker's own Atom11 login:

1. Finds the account by display name and marketplace (`get_my_data_scopes`)
   and reads the enabled families (`get_action_capabilities`), once per page
   load.
2. Calls `propose_actions` with the saved payload. Nothing changes on Amazon.
3. Shows Atom11's preview: current value, new value, change, freshness, undo
   support, expiry, every warning, and a note when the value differs from the
   report. Warnings need a tick before Yes works.
4. Yes calls `confirm_actions` on that proposal (with `acknowledge_warnings`
   only when the human ticked the warnings). No calls `cancel_actions`.
5. Shows the result: applied, partly applied, failed or still running ("Check
   result" reads it again with the same proposal). After an applied change it
   offers Undo, which runs the same preview, tick and Yes cycle with
   `{"proposal_id": "<applied proposal>"}` on the `undo` family.
6. Pauses every button on the page when the outcome is unknown or a confirm
   gets no answer, until someone checks History in Atom11.

Undo lives only while the page is open; the page keeps no record. After an
applied change the page shows the applied proposal's code. If the user later
asks in chat to undo "Atom11 change <code>", prepare an `undo` proposal with
`{"proposal_id": "<code>"}` through the approved action workflow: full preview,
ended turn, fresh approval. Atom11 allows undo for 21 days when nothing else
has changed the entity since.

## 6. Tell the user

After publishing, say in a few lines:

- the report link, and how many changes have a button and how many don't;
- the buttons work in claude.ai for people with the Atom11 connector and
  access to this account, under their own login; the first click asks to allow
  the page to use Atom11;
- nothing changes until someone clicks Yes on a preview; Undo stays only while
  the page is open;
- changes made from the page appear in Atom11's History, not in this skill's
  local write journal.
