---
name: amazon-ads-takeover-operator
description: Reconstruct an inherited Amazon Ads account with verified before/after history, a living master audit, change journal, monitoring plan and exception queue. Use for account takeovers.
---

# Amazon Ads Takeover Operator — Shareable

Convert scattered history into an operating system another analyst can use without rediscovering the account.

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

## Baseline

Capture advertiser/profile, marketplace, account type, currency, timezone, attribution, audit start date, latest complete date, active formats, campaign population, 90/30/14/7-day and recent complete-week totals, prior-period/YoY context, campaign architecture, retail readiness, economics coverage, rules/automations, prior approvals, protected pauses, and blockers.

Answer plainly:

1. What was the account spending and returning at takeover?
2. Was the main problem delivery, relevance, conversion, order value, retail readiness, or economics?
3. Which routes were healthy and which created the loss?
4. What had already changed and been verified?
5. What remained immature, unverified, blocked, or awaiting approval?

## State model

Keep these distinct:

`planned -> ready for approval -> approved -> revalidated -> submitted -> verified live -> monitoring -> kept/rolled back/blocked`

Never rewrite old state as though it never existed. Append skipped, rejected, failed, reverted, blocked, and successful actions.

## Anti-duplication gate

Before any new launch:

1. search the exact proposed name;
2. search product family and strategic job;
3. search target/query and destination;
4. inspect enabled, paused, archived, and legacy routes;
5. convert to Repair, Maintain, Scale, or Needs more data if a route already owns the job.

## Master action queue

Each row includes priority, entity, current state/value, evidence window, diagnosis, smallest next action, dependency, approval, execution status, owner, due/review date, first review, hard stop, and rollback.

Priority orders review; it does not authorize a mutation.

## Change journal

For every live change record date/time, account, marketplace, entity and ID, before, after, evidence, destination readiness, approval, native readback, expected effect, first review, hard stop, rollback, and later outcome.

Default review cadence unless account-specific evidence requires otherwise:

- 24 hours: state, eligibility, moderation, delivery, destination;
- 7 complete days: route-level traffic and conversion;
- 14 complete days: attribution-mature keep/reduce/pause/rollback;
- 21 days: multi-variable creative relaunch decision.

Never use same-day zeroes as mature evidence.

## Deliverable

Maintain one canonical system containing start-here guidance, takeover baseline, verified change ledger, master audit/to-do, build/repair runbooks, daily review and rollback, and sources/audit trail. Surface only judgment, approval, authentication, missing economics, retail dependencies, and cross-team work in the exception queue.

## Atom11 binding (native edition)

This binding supplies Atom11 read evidence for the baseline and review queue. Historical states require recorded evidence; new writes require the complete preview and fresh human approval described above.

**Baseline on Atom11.**
- Advertiser/profile name, marketplace, currency and timezone: `get_my_data_scopes`. Confirm account type from an explicit returned channel/field or the user. Attribution profile: the account report's metadata.
- 90/30/14/7-day and recent complete-week totals: one `account_overview` (or `account_report`) call per window. Each is its own window; the server never treats overlapping windows as a sequence, and neither should the baseline. Inspect each recipe's returned comparison window. Default prior periods are generally preceding equal windows; explicit comparison datasets can accept `previous_range`, including YoY, where their schema supports it.
- Campaign population and architecture: `ads_campaign_state` (as-of status, serving state, budget, targeting mode, target ACoS) paged in full when `total_count` is modest, plus `campaign_not_serving` for the complete non-serving counts; `ads_portfolio_performance` and `ads_label_performance` for structure.
- Retail readiness: `restock_priority`, `campaign_out_of_stock_products`, `ad_group_low_stock_products`, `product_catalog`.
- Rules and automations: `automation_rule` (definitions, including dayparting) and `automation_activity` (what changed, previous/new values, rule vs manual source) — this is Atom11's change record, not native Amazon's.
- Economics coverage, prior approvals, protected pauses, blockers: not in Atom11; they live in the journal.

**Anti-duplication gate on Atom11.** Exact name search → `ads_campaign_state` with an `ilike` filter on `campaign`; product family and job → `ads_advertised_product` grouped by `product` with campaign context, plus `targeting_mix` / `term_mix` for role; target/query and destination → `ads_keyword`, `ads_search_term`, `ads_negative_target`; enabled, paused, archived and legacy routes → the `status` and `serving_state` columns of the state dataset. Two campaigns can share a name; keep separate refs separate.

**Master action queue and change journal.** Atom11 supplies observations and recorded changes, with source timestamps where available. Record observed status separately from approval, submission and native readback. New recommendations start at `planned` in the state model above; `ready for approval` only once the preview has been shown, `approved` only from the human's reply. An explicitly requested supported write follows [the approved action workflow](references/approved-actions.md): complete preview, all warnings, a new human approval message, then exact-proposal confirm. Undo gets its own new preview and approval. History/audit verification is distinct from live native saved-state readback. Follow each metric's attribution window for the review cadence.


Atom11 specifics for every step above are in [references/atom11-mcp-contract.md](references/atom11-mcp-contract.md); read it before the first Atom11 call. Read [the analysis map](references/atom11-analysis-map.md) when selecting task-specific sources. Use the bundled `assets/` intake, source-log, module-status and change-queue templates.
