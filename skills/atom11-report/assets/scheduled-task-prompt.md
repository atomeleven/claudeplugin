# Scheduled task prompt (template)

Paste everything below the line into the scheduled task's prompt box. Replace
the angle-bracket placeholders with the client's values. Keep the wording: it
is what makes an unattended run follow the skill's scheduled-mode rules.
Validate the finished profile with `scripts/plan_report.py` before saving.

---

Generate my recurring Atom11 report using the atom11-report skill in scheduled mode. This run is unattended: ask no questions, use only the Atom11 connector's read-only tools, and follow the scheduled-run rules in the skill's references/scheduling.md. If the atom11-report skill or the Atom11 connector is not available, reply with one line saying which one is missing and stop.

Steps:
1. Save the profile JSON below to a file named report-profile.json and run the skill's scripts/plan_report.py with --profile report-profile.json. If it reports an error, reply with that message and stop.
2. Call get_my_data_scopes and select the account whose display name exactly equals the profile's account.display_name. If there is no exact match, reply naming the expected display name and stop.
3. Run every planned module in the planned order with the planned parameters. Save each raw response as its own evidence file. Copy the profile's "request" line into user_question on every call, and pass the interaction_id from the first result to every later call.
4. Apply the profile's freshness policy, compose the report document, and render it with the skill's scripts/render_report.py with verification on. Fix the document if verification fails; never edit the evidence.
5. Reply with: the HTML report file, the exact reporting window, the verdict, up to five evidence-backed review priorities, any data-completeness caveat, and which freshness rule applied. If a module failed, name it and the reason. Never show scope, trace, recipe, dataset or interaction identifiers.

Profile:

{
  "profile_version": 1,
  "name": "<CLIENT NAME> weekly",
  "client": "<CLIENT NAME>",
  "prepared_for": "<WHO READS IT, e.g. Brand team>",
  "request": "Weekly business review for <ACCOUNT NAME>: account performance, campaign movers, campaign review, top search terms, wasted spend, restock risks.",
  "account": {"display_name": "<ACCOUNT NAME exactly as shown by the Atom11 connector>", "system": "ads_profile", "timezone": "<IANA TIMEZONE, e.g. America/New_York>"},
  "dsp": null,
  "report_type": "weekly",
  "cadence": {"frequency": "weekly", "window": "last_complete_week", "run_day": "Tuesday", "run_time": "08:30", "freshness_policy": "shift_to_complete"},
  "modules": {"include": [], "exclude": []},
  "options": {"targets": {"acos": <TARGET ACOS AS A DECIMAL, e.g. 0.25, or null>, "tacos": null}},
  "focus": [],
  "output": {"format": "html", "language": "en", "filename_prefix": "<client-slug>-weekly"}
}
