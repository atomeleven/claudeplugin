# Atom11 MCP write contract

Reviewed against the current Atom11 MCP action tools, preview rendering,
action registry and undo resolution on 2026-10-13. Runtime tool schemas and
capability responses control what this connection may do. No live write was
used to build this skill.

## Tool inputs

The connection needs the action tools registered, an active write grant,
a token with `ads:write`, authorized account membership/role, and an enabled
family within policy. Family availability varies; there is no static promise
that every action type can execute. Read tools supply account/entity identity.

| Tool | Inputs | Effect |
|---|---|---|
| `get_action_capabilities` | `scope_id`, optional `interaction_id` | Reads eligible `families`, `registry_version` and the user's `open_proposals`. |
| `get_action_schema` | `scope_id`, `family_id`, optional `interaction_id` | Reads `family`, `payload_schema`, `bounds` and `registry_version`. |
| `propose_actions` | `scope_id`, `family_id`, `ad_type`, `payload`; optional `reason`, `acknowledge_irreversible`, `acknowledge_warnings`, `user_question`, `interaction_id` | Stores a preview without calling Amazon. Can supersede an earlier same-family/ad-type/entity-set proposal in the same user/client context. |
| `confirm_actions` | `proposal_id`; optional `user_question`, `interaction_id` | Executes the stored proposal or returns its known in-flight/saved outcome. Never call it on an unapproved proposal to inspect state. |
| `cancel_actions` | Exactly one of `proposal_id` or `scope_id`; optional `user_question`, `interaction_id` | Cancels one or all of the user's open proposals for the scope. No Amazon mutation; needs the human's cancellation intent. |

Tool omission or a refused grant means no write workflow is available.
Do not ask an LLM to grant itself permissions or change deployment settings.

`families[]` descriptors include `family_id`, `ad_types`, `tier`,
`undo_supported`, `irreversible` and `blocked_reason`.
The schema gives the exact payload. Many regular payloads use `items`
with `entity_id` and the field being changed, but this is not universal;
undo has a different payload. Read the schema rather than inventing fields.

## Preview and existing proposals

A successful proposal returns:

- `proposal_id`, `family_id`, `entity_count`, `expires_at`.
- `diff`: proposal/family/ad type, `field`, `rows`, `totals`,
  `freshness`, `sync_cadence_minutes`, warnings and expiry.
- Each diff row has `entity_id`, `display_name`, `before`, `after`,
  `abs_delta` and `pct_delta`.
- `diff_markdown`: the rendered table, freshness, warnings and expiry.
- `warnings`: `kind`, `message`, affected entities, rule fields and
  optional `follow_up`.
- `superseded_proposal_ids` and a text reminder to ask before confirmation.

The complete structured diff is authoritative. Markdown may shorten names
and warning messages. Preserve the full structured warning text as well as
the table; missing names require identity resolution before confirmation.
No raw account scope token belongs in the client-facing preview.

The default review window is one hour; use the actual returned expiry.
Re-proposing invalidates any approval for the earlier proposal, even when
the requested values seem the same.

`open_proposals[]` contains the structured diff, IDs, expiry and flags
`from_this_connection`, `can_confirm`, `can_cancel`. A proposal from
another OAuth connection may be cancellable, but cannot be confirmed here.
Never treat an old preview as already approved. Re-show it and wait for a
fresh human reply if it is still eligible; if it cannot be confirmed, explain
the connection boundary. A new proposal needs an explicit human request,
the full preview and its own approval.

Warnings about dayparting, custom rules or overlapping work require the
actual user answer. Never disable a rule, cancel unrelated proposals or
acknowledge risks automatically to avoid the warning.

## Approval semantics

There is no server-stored, cryptographically verified human approval supplied
by this skill. The server implements two-step client-mediated execution.
The LLM/client must show the full diff and wait for the human reply.
`user_question` carries the user's words for diagnostics; setting it to
"approved" is not authorization.

The skill's required sequence is:

`requested → preview returned → full preview shown → human reply →
approved exact proposal → confirm → reported outcome → native verification`.

Only the human's new message after the shown preview can unlock confirmation.
Approval binds account, marketplace, ad type, entity set, values, warnings
and proposal identity. Changed scope, partial approval or a new preview
requires another confirmation cycle. No autonomous scheduled execution,
conditional "execute when ACOS rises", or automatic rollback is supported
by this skill; monitoring can only bring a proposed change back for review.

An irreversible warning needs explicit acknowledgement before preparing the
acknowledged preview, followed by final approval after showing that preview.
The same separation applies to warning acknowledgement.

## What confirmation rechecks

Confirm checks ownership/connection, current account membership and enabled
action/policy gates, expiry, stored preview definitions, available current
values and intervening recorded actions before dispatch. It submits the
frozen payload, not newly generated parameters.

Most Ads current values come from scheduled snapshots. Their last-change
timestamps may not establish last sync; the preview exposes a declared
cadence rather than a measured sync time. Confirm re-reads those sources,
not a universal direct Amazon settings API. Console edits between syncs can
remain invisible. Explain this limitation before approval; obtain separate
native read evidence when required. Do not call a snapshot authoritative
live state.

## Outcomes

Successful confirm responses include `status`, `per_entity`,
`history_ids`, `audit_verified` and `outcome_unknown`.
Refusals use `code`, `message` and `details`.

| Returned outcome | Required handling |
|---|---|
| `EXECUTED` with matching successful per-entity records and audit evidence | Report execution recorded by Atom11. Native saved-state readback remains a separate verification. |
| `PARTIAL` | Identify successful and failed entities. Stop remaining batch work. No automatic retry or rollback; a revised change needs a new preview and approval. |
| `FAILED` | Report actual failed entities and errors. `audit_verified: true` can verify a failure; it does not mean success. A new attempt needs review, a new preview and approval. |
| `OUTCOME_UNKNOWN` or `outcome_unknown` | Outcome uncertain. Stop writes on the affected account and request reconciliation using recorded history and native state; never duplicate the change. |
| `stale_preview` / `proposal_expired` | Preview/approval no longer usable. Re-read, create a new preview and ask again. |
| `proposal_in_flight` after a known approved confirm was dispatched | Keep the same proposal ID. A same-ID confirm can return the running/saved result. Do not create a new proposal or submit another payload. Use a bounded recheck and report still-pending state rather than an endless loop. |
| `proposal_in_flight` on propose/cancel, or generic transport loss | Do not assume a live confirm happened. Inspect the operation context/open proposals/history. Repeat only a known safe authorized cancellation; never use confirm to inspect a pending unapproved proposal. |
| `not_permitted` / `family_disabled` | Stop. Do not adjust grants, roles, tiers, scopes or use a different channel to bypass the restriction. |
| `policy_rejected` / `invalid_payload` | Explain the actual rejection. Any revised values, entities or batch require a revised preview and new approval; do not silently clamp or split. |
| `acknowledgement_required` | Show the actual reason/warnings and collect the human's answer. An acknowledgement is not the final approval. |
| `store_unavailable` / `internal_error` / `proposal_not_found` | Stop and preserve evidence. Do not infer successful execution or manufacture a replacement proposal. |

Safe result recovery uses the same ID only when the conversation/journal
already proves a human-approved confirm was attempted. When state is unknown
and approval history cannot be established, use read evidence and human
reconciliation instead. A repeated confirm of a still-PROPOSED record can
dispatch it; confirm is not a generic read tool.

Atom11 correlates execution with Ads action-history rows. An audit result
does not prove current native Amazon state or future business benefit.
Record proposed after-values separately from actual native readback.

## Cancellation

Declining the displayed proposal authorizes cancelling that proposal only.
Ask before cancelling all open proposals and identify that exact account
and list. Cancellation is user-owned across connections; confirmation remains
bound to the connection that prepared the preview.

An executing proposal cannot be cancelled. A cancellation timeout must never
lead to confirming it. Cancellation does not reverse an already executed
Amazon change.

## Undo

Undo uses `family_id: undo` through the same propose/show/approve/confirm
flow. It is a new live change with its own full preview and fresh approval.
Its payload accepts exactly one of:

- `{"proposal_id": "<verified confirmed proposal>"}`
- `{"history_ids": [<verified positive integer row IDs>]}`

Use the actual schema and matching ad type. Do not fabricate history IDs,
mix rule/manual source IDs, or infer history success from an arbitrary row.
Current eligibility is bounded to supported connector-originated successful
changes within 21 days, with current value/newer-action checks and an enabled
inverse family. It is not a promise of universal rollback: whether a
family's changes can be undone comes from `undo_supported` on its
capabilities descriptor and from the server's inverse resolution, never
from an assumption. A later write to the
same field can make an earlier change ineligible, even if the value appears
restored. Do not bypass a refused inverse with a manually generated restore.

Monitoring may recommend an undo and draft its evidence. It must wait for
an explicit human request to prepare it and fresh approval of the inverse.

## Use alongside reporting

This protocol is bundled into the native Evidence Analyst, Deep Audit and
Takeover Operator for explicitly requested action workflows, and is also
available as the standalone Atom11 Approved Actions skill. All three default
to reading and reporting. The cross-source research skill remains read-only.

Do not switch from a report to writes automatically. A human must request the
specific change/preview, see the complete proposal and reply with approval
before execution. Do not override a governing read-only instruction. Reports
can supply evidence; they cannot supply the human's final approval.
