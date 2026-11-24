#!/usr/bin/env python3
"""Mark every recommended change that an automation rule already covers, or
that was changed in the last 7 days (wait before changing it again).

Usage:
  python3 check_rule_coverage.py --report report.json \
      --rules rules.json --rule-actions rule_actions.json [--today YYYY-MM-DD]

--rules         saved query_data answer(s) from the automation_rule dataset
--rule-actions  saved query_data answer(s) from the automation_rule_action
                dataset (every page), filtered to the recommended campaigns

--history       saved query_data answers from automation_activity for the
                last 7 days (the manual read and the rule read, every page)
--wait-days     waiting period after a change (default 7)

All files may hold one query_data answer, a list of answers (pages) or a
plain list of rows. The script writes `rule_check` into every change that has
an `action`, in place (or to --output), and prints a summary.

A change is "covered" when an ENABLED, not-deleted rule that is inside its
active dates has an ACTIVE rule-action row that changes the same field on the
same campaign (and, when the change names a target, on that target or on the
whole campaign). If either file is missing or a page was left unread, changes
that are not proven covered are marked "unknown" so the page says so.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom11_io import describe, load_answers  # noqa: E402

# Atom11 action family -> automation_rule_action.changed_field values that
# change the same thing. Families not listed have no matching rule field.
FAMILY_FIELDS: dict[str, set[str]] = {
    "keyword_bid_change": {"BID_CHANGE_KEYWORD"},
    "product_target_bid_change": {"TARGET_BID_CHANGE"},
    "theme_bid_change": {"BID_CHANGE_KEYWORD"},
    "campaign_budget_change": {"CAMPAIGN_BUDGET_CHANGE"},
    "campaign_placement_adjustment": {"CAMPAIGN_BID_ADJUSTMENT_CHANGE"},
    "product_ad_state_change": {"PAUSE_PRODUCT"},
    "negative_keyword_add": {"NEGATIVE_SEARCH_TERM"},
    "negative_search_term_add": {"NEGATIVE_SEARCH_TERM"},
    "negative_target_search_term_add": {"NEGATIVE_SEARCH_TERM"},
    "negative_target_add": {"NEGATIVE_SEARCH_TERM"},
    "search_term_to_keyword": {"BID_CHANGE_SEARCH_TERM"},
    "search_term_to_target": {"BID_CHANGE_SEARCH_TERM"},
    "keyword_add": {"BID_CHANGE_SEARCH_TERM"},
    "product_target_add": {"BID_CHANGE_SEARCH_TERM"},
}
STATE_FIELDS = {  # direction-specific families
    "keyword_state_change": {"PAUSED": {"PAUSE_KEYWORD"}, "ENABLED": {"ENABLE_KEYWORD"}},
    "theme_state_change": {"PAUSED": {"PAUSE_KEYWORD"}, "ENABLED": {"ENABLE_KEYWORD"}},
    "product_ad_state_change": {"PAUSED": {"PAUSE_PRODUCT"}},
}
FIELD_WORDS = {
    "BID_CHANGE_KEYWORD": "keyword bids",
    "TARGET_BID_CHANGE": "target bids",
    "CAMPAIGN_BUDGET_CHANGE": "the daily budget",
    "CAMPAIGN_BID_ADJUSTMENT_CHANGE": "placement bid adjustments",
    "PAUSE_PRODUCT": "pausing product ads",
    "PAUSE_KEYWORD": "pausing keywords/targets",
    "ENABLE_KEYWORD": "enabling keywords/targets",
    "NEGATIVE_SEARCH_TERM": "negating search terms",
    "BID_CHANGE_SEARCH_TERM": "harvesting search terms",
}
CAMPAIGN_WIDE = {"", "0", "None", "null"}

# Dayparting rules record their slot changes as these fields; a dayparting bid
# rule holds every keyword AND product target of its campaigns.
DAYPARTING_FIELD_FAMILIES: dict[str, set[str]] = {
    "TARGET_BID_CHANGE": {"keyword_bid_change", "product_target_bid_change", "theme_bid_change"},
    "CAMPAIGN_BUDGET_CHANGE": {"campaign_budget_change"},
}
# Live change -> the dayparting base-value family to use under an OVERRIDE rule.
DAYPARTING_BASE_FAMILY = {
    "keyword_bid_change": "dayparting_default_keyword_bid",
    "theme_bid_change": "dayparting_default_keyword_bid",
    "product_target_bid_change": "dayparting_default_target_bid",
    "campaign_budget_change": "dayparting_default_budget",
}
DAYPARTING_BASE_FAMILIES = set(DAYPARTING_BASE_FAMILY.values())
# Changes to a rule itself: no rule-coverage or wait check applies to them.
RULE_LEVEL_FAMILIES = {"autorules_rule_state", "autorules_rule_campaigns"}
# Never a button on the report (kept in step with build_action_report.NO_BUTTON_FAMILIES).
CHAT_ONLY_FAMILIES = {"undo", "campaign_create", "autorules_rule_create", "autorules_rule_clone", "autorules_rule_edit",
                      "autorules_rule_delete", "autorules_rule_run_now", "autorules_rule_adgroups_refresh",
                      "dayparting_rule_create", "dayparting_schedule_edit", "dayparting_rule_campaigns",
                      "dayparting_defaults_sync"}
BUDGET_FAMILIES = {"campaign_budget_change", "dayparting_default_budget"}

# Atom11 action family -> automation_activity.action_kind values (manual and
# rule wording differ) that change the same entity in the same way.
HISTORY_KINDS: dict[str, set[str]] = {
    "keyword_bid_change": {"BID_CHANGE_KEYWORD"},
    "product_target_bid_change": {"BID_CHANGE_PRODUCT_TARGET", "TARGET_BID_CHANGE"},
    "theme_bid_change": {"THEME_BID_CHANGE", "BID_CHANGE_KEYWORD"},
    "campaign_budget_change": {"CAMPAIGN_BUDGET_CHANGE"},
    "campaign_placement_adjustment": {"CAMPAIGN_BID_ADJUSTMENT_CHANGE"},
    "campaign_audience_bid_adjustment": {"CAMPAIGN_AUDIENCE_BID_ADJUSTMENT_CHANGE"},
    "dayparting_default_budget": {"CAMPAIGN_BUDGET_CHANGE"},
    "dayparting_default_keyword_bid": {"BID_CHANGE_KEYWORD"},
    "dayparting_default_target_bid": {"BID_CHANGE_PRODUCT_TARGET", "TARGET_BID_CHANGE"},
    "campaign_state_change": {"CAMPAIGN_STATE_CHANGE"},
    "keyword_state_change": {"KEYWORD_STATE_CHANGE", "PAUSE_KEYWORD", "ENABLE_KEYWORD"},
    "theme_state_change": {"KEYWORD_STATE_CHANGE", "PAUSE_KEYWORD", "ENABLE_KEYWORD"},
    "product_target_state_change": {"PRODUCT_TARGET_STATE_CHANGE", "PAUSE_KEYWORD", "ENABLE_KEYWORD"},
    "product_ad_state_change": {"ENABLE_AND_PAUSE_PRODUCT", "PAUSE_PRODUCT"},
}
# Adds create something new, so they match on the same text in the same campaign.
HISTORY_ADD_KINDS: dict[str, set[str]] = {
    "negative_keyword_add": {"NEGATIVE_KEYWORD", "NEGATIVE_SEARCH_TERM"},
    "negative_search_term_add": {"NEGATIVE_KEYWORD", "NEGATIVE_SEARCH_TERM"},
    "negative_target_add": {"NEGATIVE_PRODUCT_TARGET", "NEGATIVE_SEARCH_TERM"},
    "negative_target_search_term_add": {"NEGATIVE_PRODUCT_TARGET", "NEGATIVE_SEARCH_TERM"},
    "keyword_add": {"ADD_KEYWORD", "BID_CHANGE_SEARCH_TERM"},
    "search_term_to_keyword": {"ADD_KEYWORD", "BID_CHANGE_SEARCH_TERM"},
    "product_target_add": {"ADD_PRODUCT_TARGET", "BID_CHANGE_SEARCH_TERM"},
    "search_term_to_target": {"ADD_PRODUCT_TARGET", "BID_CHANGE_SEARCH_TERM"},
}


def history_kinds_needed() -> list[str]:
    out: set[str] = set()
    for kinds in (*HISTORY_KINDS.values(), *HISTORY_ADD_KINDS.values()):
        out |= kinds
    return sorted(out)


def is_dayparting(row: dict[str, Any], dayparting_refs: set[str]) -> bool:
    return "DAY_PARTING" in str(row.get("rule_kind") or "").upper() or str(row.get("rule_ref")) in dayparting_refs


def event_day(row: dict[str, Any]) -> dt.date | None:
    for key in ("date_day", "event_timestamp_utc"):
        value = row.get(key)
        if value:
            try:
                return dt.date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    return None


def counts_as_change(row: dict[str, Any]) -> bool:
    source = str(row.get("action_source") or ("rule" if row.get("rule_ref") not in (None, "") else "manual")).lower()
    if source == "manual":
        return str(row.get("run_status") or "SUCCESS").upper() != "ERROR"
    return str(row.get("reverted") or "false").lower() != "true"


def recent_change(change: dict[str, Any], rows: list[dict[str, Any]], dayparting_refs: set[str],
                  today: dt.date, wait_days: int) -> dict[str, Any] | None:
    """Latest counted change to the same entity inside the waiting period, or None."""
    action = change["action"]
    family = action.get("family_id")
    match = action.get("rule_match") or {}
    payload = action.get("payload") or {}
    entity_ids = {str(i.get("entity_id")) for i in payload.get("items", []) if isinstance(i, dict) and i.get("entity_id")}
    best = None
    for row in rows:
        kind = row.get("action_kind")
        if family in HISTORY_KINDS:
            if kind not in HISTORY_KINDS[family] or str(row.get("object_ref")) not in entity_ids:
                continue
        elif family in HISTORY_ADD_KINDS:
            text = str(match.get("text") or "").strip().lower()
            if (kind not in HISTORY_ADD_KINDS[family] or not text
                    or str(row.get("campaign_ref")) != str(match.get("campaign_ref"))
                    or str(row.get("object") or "").strip().lower() != text):
                continue
        else:
            continue
        if is_dayparting(row, dayparting_refs) or not counts_as_change(row):
            continue
        day = event_day(row)
        if day is None or day + dt.timedelta(days=wait_days) <= today:
            continue
        if best is None or str(row.get("event_timestamp_utc") or day) > str(best[1].get("event_timestamp_utc") or best[0]):
            best = (day, row)
    if best is None:
        return None
    day, row = best
    is_rule = row.get("rule_ref") not in (None, "") or str(row.get("action_source") or "").lower() == "rule"
    out = {"status": "recent", "source": "rule" if is_rule else "manual", "date": day.isoformat(),
           "wait_until": (day + dt.timedelta(days=wait_days)).isoformat(), "wait_days": wait_days,
           "before": row.get("previous_value"), "after": row.get("new_value")}
    if is_rule and row.get("rule"):
        out["rule"] = row["rule"]
    return out


LOAD_NOTES: list[str] = []


def load_rows(path: str | None) -> tuple[list[dict[str, Any]] | None, bool]:
    """Rows from saved query_data answers, and whether the file PROVES it is complete
    (every page present and rows == total_count). Unproven files count as incomplete."""
    rows, proof = load_answers(path)
    if path and not proof["complete"]:
        LOAD_NOTES.append(f"{Path(path).name}: {describe(proof)}")
    return rows, proof["complete"]


def rule_is_live(rule: dict[str, Any], today: dt.date) -> bool:
    if str(rule.get("status", "")).upper() != "ENABLED":
        return False
    if str(rule.get("deleted", "false")).lower() in {"true", "1", "yes"}:
        return False
    for key, cmp in (("active_start_date", lambda d: d <= today), ("active_end_date", lambda d: d >= today)):
        value = rule.get(key)
        if value:
            try:
                if not cmp(dt.date.fromisoformat(str(value)[:10])):
                    return False
            except ValueError:
                pass
    return True


def fields_for(action: dict[str, Any]) -> set[str]:
    family = action.get("family_id")
    if family in STATE_FIELDS:
        states = {str(i.get("state", "")).upper() for i in (action.get("payload") or {}).get("items", []) if isinstance(i, dict)}
        out: set[str] = set()
        for state in states:
            out |= STATE_FIELDS[family].get(state, set())
        return out
    return FAMILY_FIELDS.get(family, set())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", required=True)
    ap.add_argument("--rules")
    ap.add_argument("--rule-actions", help="automation_rule_action answers (older source)")
    ap.add_argument("--campaign-rules", help="automation_campaign_rule answers (preferred source)")
    ap.add_argument("--portfolios", help="ads_portfolio_setting answers, for the budget-cap check")
    ap.add_argument("--history", nargs="*", default=None)
    ap.add_argument("--wait-days", type=int, default=7)
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--output")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.report).read_text())
    today = dt.date.fromisoformat(args.today)
    rules, rules_complete = load_rows(args.rules)
    acts, acts_complete = load_rows(args.rule_actions)
    if args.campaign_rules:
        crow, acts_complete = load_rows(args.campaign_rules)
        acts = None if crow is None else [
            {"rule_ref": r.get("rule_ref"), "rule": r.get("rule"), "changed_field": r.get("changed_field"),
             "campaign_ref": r.get("campaign_ref"), "target_ref": "0",
             "status": "ACTIVE" if str(r.get("rule_status", "")).upper() == "ENABLED" else "INACTIVE"}
            for r in crow]
    checkable = rules is not None and acts is not None
    portfolios, portfolios_complete = load_rows(args.portfolios)
    port_by_ref = {str(r.get("portfolio_ref")): r for r in (portfolios or [])}
    history: list[dict[str, Any]] | None = None
    history_complete = False
    if args.history:
        history, history_complete = [], True
        for path in args.history:
            rows, complete = load_rows(path)
            if rows is None:
                history, history_complete = None, False
                break
            history.extend(rows)
            history_complete = history_complete and complete
    dayparting_refs = {str(r.get("rule_ref")) for r in (rules or []) if "DAY_PARTING" in str(r.get("rule_kind") or "").upper()}
    rcounts = {"recent": 0, "none": 0, "unknown": 0}
    live = {str(r.get("rule_ref")): r for r in (rules or []) if rule_is_live(r, today)}
    problems: list[str] = []
    counts = {"covered": 0, "not_covered": 0, "unknown": 0, "dayparting_adaptive": 0, "dayparting_override": 0}
    pcounts = {"capped": 0, "ok": 0, "unknown": 0}

    for i, change in enumerate(doc.get("changes", [])):
        action = change.get("action")
        if not action:
            continue
        family = action.get("family_id")
        match = action.get("rule_match") or {}
        if family in CHAT_ONLY_FAMILIES:
            problems.append(f"changes[{i}] ({change.get('id')}): {family} never gets a button on the report; "
                            "remove the action and give the change a manual_reason (prepare it in chat if asked)")
            continue
        if family in RULE_LEVEL_FAMILIES:
            change["rule_check"] = {"status": "not_covered", "note": "This changes the rule itself."}
            change["recent_change"] = {"status": "none", "note": "Rule settings have no 7-day wait."}
            counts["not_covered"] += 1
            rcounts["none"] += 1
            continue
        cref = str(match.get("campaign_ref") or "")
        tref = str(match.get("target_ref") or "")
        fields = fields_for(action)
        if not cref:
            problems.append(f"changes[{i}] ({change.get('id')}): action.rule_match.campaign_ref is required for the rule check")
            continue
        hits: dict[str, set[str]] = {}
        maybe: set[str] = set()  # custom bid rules that may also change product-target bids (unconfirmed)
        dayparting: dict[str, dict[str, Any]] = {}
        live_family = next((k for k, v in DAYPARTING_BASE_FAMILY.items() if v == family), family)
        for row in acts or []:
            if str(row.get("status", "")).upper() != "ACTIVE" or str(row.get("campaign_ref")) != cref:
                continue
            rref = str(row.get("rule_ref"))
            if rref not in live:
                continue
            rule = live[rref]
            if "DAY_PARTING" in str(rule.get("rule_kind") or "").upper():
                if live_family in DAYPARTING_FIELD_FAMILIES.get(row.get("changed_field"), set()):
                    dayparting[rule.get("rule") or row.get("rule") or "Unnamed rule"] = rule
                continue
            if (family in ("product_target_bid_change", "dayparting_default_target_bid")
                    and row.get("changed_field") == "BID_CHANGE_KEYWORD"):
                maybe.add(rule.get("rule") or row.get("rule") or "Unnamed rule")
            if family in DAYPARTING_BASE_FAMILIES or row.get("changed_field") not in fields:
                continue
            row_t = str(row.get("target_ref") if row.get("target_ref") is not None else "")
            if tref and row_t not in CAMPAIGN_WIDE and row_t != tref:
                continue
            hits.setdefault(rule.get("rule") or row.get("rule") or "Unnamed rule", set()).add(row["changed_field"])
        if hits:
            names = sorted(hits)
            what = sorted({FIELD_WORDS.get(f, f.lower()) for fs in hits.values() for f in fs})
            change["rule_check"] = {"status": "covered", "rules": names, "what": ", ".join(what)}
        elif maybe:
            change["rule_check"] = {"status": "unknown", "rules": sorted(maybe), "note": (
                "A custom bid rule runs on this campaign (" + ", ".join(sorted(maybe)) + "). Atom11’s data doesn’t say "
                "whether it also changes product-target bids, so this was not checked. Check the rule before acting.")}
        elif dayparting:
            name, rule = sorted(dayparting.items())[0]
            kind = str(rule.get("conflict_kind") or "").upper()
            if kind == "OVERRIDE":
                change["rule_check"] = {"status": "dayparting_override", "rules": [name],
                                        "base_family": DAYPARTING_BASE_FAMILY.get(live_family)}
                if family not in DAYPARTING_BASE_FAMILIES:
                    problems.append(
                        f"changes[{i}] ({change.get('id')}): the campaign is in the OVERRIDE dayparting rule "
                        f"\"{name}\", which rewrites live values at its next slot. Use family "
                        f"{DAYPARTING_BASE_FAMILY.get(live_family)} (the rule's base value) for this change.")
            elif kind == "ADAPTIVE":
                change["rule_check"] = {"status": "dayparting_adaptive", "rules": [name]}
            else:
                change["rule_check"] = {"status": "unknown", "rules": [name],
                                        "note": f"The dayparting rule \"{name}\" has no OVERRIDE/ADAPTIVE setting in the rule data."}
        elif family in DAYPARTING_BASE_FAMILIES:
            problems.append(f"changes[{i}] ({change.get('id')}): {family} needs a campaign in a live dayparting rule, "
                            "and none was found for it.")
            continue
        elif not fields:
            change["rule_check"] = {"status": "not_covered", "note": "No Atom11 rule type changes this setting."}
        elif not checkable or not (rules_complete and acts_complete):
            change["rule_check"] = {"status": "unknown",
                                    "note": "Automation rules could not be fully checked for this change."}
        else:
            change["rule_check"] = {"status": "not_covered"}
        counts[change["rule_check"]["status"]] += 1

        # Portfolio budget cap: a budget increase can't help while the portfolio is out of budget.
        if family in BUDGET_FAMILIES:
            pref = str(match.get("portfolio_ref") or "")
            before = action.get("report_before") or {}
            ups = []
            for item in (action.get("payload") or {}).get("items", []):
                try:
                    ups.append(float(item.get("budget")) > float(str(before.get(str(item.get("entity_id")))).replace("$", "")))
                except (TypeError, ValueError):
                    ups.append(True)
            if not any(ups) or not pref:
                change["portfolio_check"] = {"status": "ok"}
            elif portfolios is None or pref not in port_by_ref:
                change["portfolio_check"] = {"status": "unknown", "note": "The portfolio budget could not be checked."}
            else:
                prow = port_by_ref[pref]
                capped = (str(prow.get("budget_policy") or "NO_CAP").upper() != "NO_CAP"
                          and str(prow.get("within_budget")).lower() == "false")
                change["portfolio_check"] = (
                    {"status": "capped", "portfolio": prow.get("portfolio"), "budget": prow.get("budget_amount"),
                     "policy": prow.get("budget_policy")} if capped else {"status": "ok"})
            pcounts[change["portfolio_check"]["status"]] += 1

        if family not in HISTORY_KINDS and family not in HISTORY_ADD_KINDS:
            change["recent_change"] = {"status": "none", "note": "No change history is kept for this type of change."}
        elif history is None:
            change["recent_change"] = {"status": "unknown", "note": "Recent changes could not be checked."}
        else:
            found = recent_change(change, history, dayparting_refs, today, args.wait_days)
            if found:
                change["recent_change"] = found
            elif not history_complete:
                change["recent_change"] = {"status": "unknown", "note": "Recent changes could not be fully checked."}
            else:
                change["recent_change"] = {"status": "none"}
        rcounts[change["recent_change"]["status"]] += 1

    for note in LOAD_NOTES:
        print(f"Not proven complete → treated as not checked: {note}", file=sys.stderr)
    if problems:
        print("Rule check not done. Fix these first:", file=sys.stderr)
        for p in problems:
            print(f"- {p}", file=sys.stderr)
        return 1
    Path(args.output or args.report).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    note = "" if checkable and rules_complete and acts_complete else " (rule data missing or not every page read: some marked unknown)"
    print(f"Rule check: {counts['covered']} covered by an automation rule, {counts['not_covered']} not covered, "
          f"{counts['dayparting_adaptive']} in an ADAPTIVE dayparting rule (button + note), "
          f"{counts['dayparting_override']} in an OVERRIDE dayparting rule (base-value button), "
          f"{counts['unknown']} unknown{note}.")
    if sum(pcounts.values()):
        print(f"Portfolio check: {pcounts['capped']} blocked by a portfolio budget, {pcounts['ok']} fine, "
              f"{pcounts['unknown']} unknown.")
    hnote = "" if history is not None and history_complete else " (history missing or not every page read: some marked unknown)"
    print(f"Recent-change check ({args.wait_days} days): {rcounts['recent']} changed recently (wait), "
          f"{rcounts['none']} not changed, {rcounts['unknown']} unknown{hnote}.")
    if dayparting_refs:
        print(f"Dayparting rules ignored for the wait: {', '.join(sorted(dayparting_refs))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
