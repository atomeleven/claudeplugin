# Scheduling a report

A scheduled report is the same skill run from a saved profile with nobody
in the loop. Everything below exists so the run finishes on its own and is
honest about what it could not do.

## Setting one up (interactive session)

1. Run the report once interactively and let the user approve the modules,
   options and window rule.
2. Save those choices as a profile (`report-profile.md`). Validate it with
   `plan_report.py`.
3. Create the scheduled task from
   [assets/scheduled-task-prompt.md](../assets/scheduled-task-prompt.md):
   paste the profile JSON into the prompt, because the scheduled run starts
   with no memory of this conversation and no access to its files unless
   they live in the task's own workspace.
4. Pick the run time from the window rule. Sponsored Ads reports arrive a
   day or more late, so a Monday–Sunday week is best run Tuesday or
   Wednesday morning; a monthly report on the 2nd or 3rd. Stagger clients
   across the morning rather than putting every client at 08:00 — each
   report is many analyses against the same service.
5. Tell the user what will arrive, where, and when, and that the connector
   must stay connected: a scheduled run cannot sign in, and an Atom11
   connector that has not been used for about a month needs reconnecting.

Where the task lives depends on the host:

- **Claude Desktop / claude.ai scheduled tasks (Cowork)**: the sidebar's
  "Scheduled" area or the `/schedule` command create a recurring task from a
  prompt; the task uses the same connectors and skills as the session. In
  the desktop app, local scheduled tasks run only while the app is open
  (a missed run fires at next launch); check the current product behaviour
  before promising cloud execution.
- **Claude Code routines**: a cron-scheduled cloud run of a prompt with the
  connected MCP servers; the profile can be a file in the repository and
  the skill a committed skill directory.
- **A client's own automation** (API, Managed Agents scheduled deployment):
  the same prompt and profile, with the Atom11 connector configured on the
  agent.

If none of those is available, the fallback is a calendar reminder that
pastes the scheduled prompt; the skill behaves identically.

## Rules inside a scheduled run

1. Start with `plan_report.py --profile` (the profile JSON is in the prompt;
   write it to a file first). If it fails, deliver its message and stop.
2. Call `get_my_data_scopes`. Select the scope whose display name equals
   `account.display_name` exactly. Zero or several matches, or a connector
   error, ends the run with a plain note naming the display name that was
   expected. Never pick a near match.
3. Run every planned module in the planned order with the planned
   parameters; copy `profile.request` into `user_question` on every call;
   pass the `interaction_id` from the first result to all later calls.
4. Apply `cadence.freshness_policy` after the first dated module returns:
   - `shift_to_complete` (default): take the earliest `complete_through`
     among that result's freshness entries. If it is inside the window and
     at most two days before the planned end, rerun the dated modules with
     the window ending on that date (same length, shifted back only at the
     end), and write the shift into `methodology` and the status ribbon.
     Otherwise deliver the planned window with `data_completeness:
     partial` and the warnings beside each affected section.
   - `deliver_partial`: never shift; flag.
   - `strict`: never shift; flag and mark comparisons "not like-for-like".
5. A failed module keeps its section with `status: failed` and the
   plain-language message; the run continues. Only a scope failure or a
   connector failure stops the run.
6. Never ask a question. Never widen the module set. Never use a write tool.
7. Deliver the HTML path and the recap (window, verdict, up to five review
   priorities, completeness caveat, which freshness rule applied). The recap
   is what the owner reads when the file is not opened, so it must stand on
   its own.

## Window rules

All windows end yesterday in the account timezone ("complete days").

| `cadence.window` | Start | End |
|---|---|---|
| `last_7_complete_days` | yesterday − 6 | yesterday |
| `last_14_complete_days` | yesterday − 13 | yesterday |
| `last_30_complete_days` | yesterday − 29 | yesterday |
| `last_complete_week` | the Monday of the most recent Monday–Sunday week whose Sunday ≤ yesterday | that Sunday |
| `last_complete_month` | first day of the previous calendar month | last day of that month |
| `month_to_date` | first day of this month (requires ≥ 1 complete day) | yesterday |
| `{"kind": "last_complete_days", "days": N}` | yesterday − (N−1) | yesterday |

Per-module adjustments the planner applies: as-of modules ignore the
window; `dayparting` is clamped to the last 28 days of the window; `sqp`
and `sqp_movement` keep the window and present the weeks returned.

## Troubleshooting

- *"Unauthenticated" / 401 from the connector*: the owner must reconnect
  the Atom11 connector; refresh tokens expire after about 30 days without
  use.
- *Account name not found*: the display name in the profile must match the
  scope list exactly; a renamed account needs a profile update.
- *Partial every week*: move the run later in the week or switch the window
  to end two days earlier; do not switch to `strict`.
- *Dayparting unavailable*: the hourly source is capacity-limited; the
  section reports unavailable and the rest of the report stands.
- *Report takes long*: each analysis can take up to a minute; a monthly
  report with every optional module is 15–20 analyses. Trim modules rather
  than shortening windows.
