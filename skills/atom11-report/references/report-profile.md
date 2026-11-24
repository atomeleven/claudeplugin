# Report profile

A profile is a small JSON file that captures one client's standing report:
which account, which report type and modules, which options, and how often.
It is what turns a one-off report into a repeatable one, and it is the
"custom per client" layer — the skill stays the same for every client; the
profile differs.

Create one after the first interactive run, when the user has seen the
report and approved the modules and options. Save it next to the user's
other project files, or embed it in the scheduled task prompt (see
`scheduling.md`) because a scheduled run cannot read this conversation.

## Schema

```json
{
  "profile_version": 1,
  "name": "Acme US weekly",
  "client": "Acme Brands",
  "prepared_for": "Brand team",
  "request": "Weekly business review for Acme US: performance, movers, campaigns, search terms, inventory, recommendations.",
  "account": {
    "display_name": "Acme US",
    "system": "ads_profile",
    "timezone": "America/New_York"
  },
  "dsp": null,
  "report_type": "weekly",
  "cadence": {
    "frequency": "weekly",
    "window": "last_complete_week",
    "run_day": "Tuesday",
    "run_time": "08:00",
    "freshness_policy": "shift_to_complete"
  },
  "modules": {
    "include": [],
    "exclude": ["recommendations"]
  },
  "options": {
    "targets": {"acos": 0.25, "tacos": null},
    "wasted_spend_min_clicks": 5,
    "wasted_spend_click_operator": "gte",
    "campaign_limit": 10,
    "search_term_limit": 10,
    "max_days_of_cover": 30,
    "reorder_target_days": 15,
    "attribution_window_days": 14,
    "rank_metric": "ad_sales_attributed",
    "missing_target_policy": "account_average",
    "module_params": {
      "top_search_terms": {"rank_by": "orders", "limit": 15}
    }
  },
  "focus": ["New Q4 launch campaigns", "Brand defence terms"],
  "output": {
    "format": "html",
    "language": "en",
    "filename_prefix": "acme-us-weekly"
  }
}
```

## Fields

- `request`: the standing request line, copied unchanged into
  `user_question` on every MCP call in a scheduled run. Write it the way the
  client would say it.
- `account.display_name`: exactly the display name `get_my_data_scopes`
  returns. `system` is `ads_profile` or `dsp_advertiser`. `timezone` is
  optional; the scope's timezone wins at run time and `plan_report.py` uses
  this value only to compute the window before the scopes call.
- `dsp`: `null` unless the client explicitly wants DSP, then
  `{"display_name": "<confirmed DSP advertiser name>", "modules": ["dsp_performance", "dsp_movers"]}`.
  A DSP module never runs from a similar-looking Ads profile name; a scope
  card with `ads_profile_linkage: declared` is the only mapping the server
  itself vouches for.
- `report_type`: a type from `report-types.md`.
- `cadence.window`: one of `last_7_complete_days`, `last_14_complete_days`,
  `last_30_complete_days`, `last_complete_week` (Monday–Sunday),
  `last_complete_month`, `month_to_date`, or
  `{"kind": "last_complete_days", "days": 10}`. "Complete" means ending
  yesterday in the account timezone.
- `cadence.freshness_policy`: `deliver_partial` (run the window as planned
  and flag incomplete trailing days), `shift_to_complete` (when the earliest
  `complete_through` is inside the window and at most two days before its
  end, rerun once ending there and say so; otherwise deliver partial), or
  `strict` (deliver partial but mark the report "comparisons not
  like-for-like" without a rerun). Default `shift_to_complete`.
- `modules.include` / `exclude`: module ids added to or removed from the
  report type's core set. Optional modules must be listed in `include` to
  run.
- `options`: common options mapped by `plan_report.py` onto each module's
  parameters (the mapping is printed in the plan). `module_params` overrides
  any parameter of one module by its id and is passed through verbatim.
- `focus`: free-text priorities for the narrative; they never change
  queries.
- `output.filename_prefix`: the HTML file becomes
  `<prefix>-<end-date>.html`.

## Validating and planning

```bash
python3 <skill-directory>/scripts/plan_report.py --profile profile.json [--today YYYY-MM-DD]
```

The planner validates the profile, resolves the window for today, lists the
modules in order with the exact parameters to pass, clamps the dayparting
window, and prints the output filename. Run it at the start of every
scheduled run and whenever a profile changes. A profile that fails
validation is a run that ends with the error message, not a guess.

## Choosing between one general skill and per-client skills

Keep one skill and many profiles. A profile captures everything that
legitimately differs between clients — account, cadence, modules,
thresholds, targets, wording of the standing request — while the
workflow, the disclosure rules and the renderer stay shared and tested
once. Fork a client-specific skill only when a client needs a different
workflow (their own template, data from outside Atom11, a bespoke KPI
definition), and even then build it as a thin wrapper that sets a profile
and reuses this skill's renderer.
