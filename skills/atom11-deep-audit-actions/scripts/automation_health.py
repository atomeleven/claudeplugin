#!/usr/bin/env python3
"""Build the "Automation health" section of the deep-audit report.

Usage:
  python3 automation_health.py --input health.json --output health_out.json

It only states what the saved data proves. Anything not read is written as
"not checked", never as "none". health.json (see SKILL.md step 5c):
{
  "currency": "USD",
  "rule_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, "lookback_days": 5,
  "rules_file": "/home/claude/audit/rules.json",                 # automation_rule answers (with page info)
  "campaign_rules_file": "/home/claude/audit/campaign_rules.json", # automation_campaign_rule answers (with page info)
  "rule_map_campaign_refs": ["..."],   # the campaign_ref "in" filter used for that read
  "campaigns": [{"campaign_ref": "...", "campaign": "...", "spend": 410.0}],   # the audited campaigns
  "bid_rules_ranked": {"file": "/home/claude/audit/rule_activity.json"},  # automation_activity, grain [rule_ref, rule]
  "rule_perf": [{"rule": "...", "rule_ref": "17705", "actions_count": 234, "acos_positive_count": 10,
                 "acos_negative_count": 35, "orders_positive_count": 44, "orders_negative_count": 67,
                 "spend_before": "2713.61", "spend_after": "4409.45", "sales_before": "13849.62", "sales_after": "13347.68"}],
  "dayparting": [{"rule": "...", "rule_ref": "12147", "conflict_kind": "ADAPTIVE", "rule_start_date": "2026-01-19",
                  "weeks": [{"week_start": "2026-01-12", "spend": "6857.66", "roas": "2.87", "is_rule_start_week": "false"}]}],
  "rule_counts": {"17705": {"rule": "...", "file": "/home/claude/audit/rule_17705_count.json"}}
                 # automation_campaign_rule filtered rule_ref eq 17705 + rule_status ENABLED, page_size 1:
                 # its total_count is the number of campaigns the rule runs on
}
Output: {"section": {...}, "review_rules": [...], "rule_scopes": {rule_ref: {...}}, "notes": [...]}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom11_io import describe, load_answers  # noqa: E402

SIGNS = {"USD": "$", "CAD": "CA$", "AUD": "A$", "GBP": "£", "EUR": "€", "INR": "₹", "JPY": "¥", "MXN": "MX$"}
# Dayparting bid rules (TARGET_BID_CHANGE) and keyword-bid rules change the same bids.
SETTING = {"BID_CHANGE_KEYWORD": "Bids", "TARGET_BID_CHANGE": "Bids",
           "CAMPAIGN_BUDGET_CHANGE": "Budget", "CAMPAIGN_BID_ADJUSTMENT_CHANGE": "Placement"}
SETTING_ORDER = ["Bids", "Budget", "Placement"]
NAME_LIMIT = 5


def num(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return 0.0


def money(value: float, sign: str) -> str:
    return f"{sign}{value:,.0f}"


def pct_change(before: float, after: float) -> str:
    if before <= 0:
        return "n/a"
    d = (after - before) / before * 100
    return f"{'+' if d >= 0 else '−'}{abs(d):.0f}%"


def names_cell(names: list[str]) -> str:
    """First few names + an exact count of the rest; never a silent cut."""
    if len(names) <= NAME_LIMIT:
        return ", ".join(names)
    return ", ".join(names[:NAME_LIMIT]) + f" and {len(names) - NAME_LIMIT} more"


def direction(rule: str, label: str) -> str:
    text = f"{rule} {label}".lower()
    if "daypart" in text:
        return "changes by hour"
    if re.search(r"\b(increase|raise|higher|boost|up)\b", text):
        return "raises"
    if re.search(r"\b(decrease|reduce|lower|cut|down)\b", text):
        return "lowers"
    if "pause" in text:
        return "pauses"
    return "changes"


def rule_read(r: dict[str, Any]) -> tuple[str, bool]:
    pos, neg = int(num(r.get("acos_positive_count"))), int(num(r.get("acos_negative_count")))
    flagged = pos + neg
    sb, sa = num(r.get("spend_before")), num(r.get("spend_after"))
    vb, va = num(r.get("sales_before")), num(r.get("sales_after"))
    spend_up_sales_flat = sb > 0 and sa >= sb * 1.2 and va <= vb
    if (flagged >= 10 and neg >= 2 * max(pos, 1)) or (spend_up_sales_flat and neg > pos):
        return (f"Worth reviewing: ACOS got worse after {neg} of {flagged} flagged changes"
                + (f"; spend {pct_change(sb, sa)}, sales {pct_change(vb, va)}." if sb > 0 and vb > 0 else "."), True)
    if flagged and pos > neg:
        return f"Mostly helping: ACOS improved after {pos} of {flagged} flagged changes.", False
    if not flagged:
        return "Not enough change yet to judge.", False
    return f"Mixed: ACOS improved after {pos} and got worse after {neg} of {flagged} flagged changes.", False


def roas_weighted(weeks: list[dict[str, Any]]) -> float | None:
    spend = sum(num(w.get("spend")) for w in weeks)
    return None if spend <= 0 else sum(num(w.get("spend")) * num(w.get("roas")) for w in weeks) / spend


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    data = json.loads(Path(args.input).read_text())
    sign = SIGNS.get(str(data.get("currency") or ""), "")
    blocks: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    notes: list[str] = []
    sources: list[str] = []

    rules_rows, rules_proof = load_answers(data.get("rules_file"))
    rule_info = {str(r.get("rule_ref")): r for r in (rules_rows or [])}
    map_rows, map_proof = load_answers(data.get("campaign_rules_file"))
    map_refs = [str(x) for x in data.get("rule_map_campaign_refs") or []]
    map_complete = bool(map_proof["complete"] and map_refs)
    if not map_complete:
        notes.append(f"Rule map {describe(map_proof)}; overlaps and 'no rule' are written as not checked.")
    map_rows = [r for r in (map_rows or []) if str(r.get("rule_status", "ENABLED")).upper() == "ENABLED"]
    camp_name: dict[str, str] = {}
    audited_name = {str(c.get("campaign_ref")): c.get("campaign") or str(c.get("campaign_ref")) for c in data.get("campaigns", [])}
    by_campaign: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    rule_label: dict[str, str] = {}
    rule_name: dict[str, str] = {}
    rule_setting: dict[str, str] = {}
    rule_campaigns_seen: dict[str, list[str]] = defaultdict(list)
    for row in map_rows:
        cref, rref = str(row.get("campaign_ref")), str(row.get("rule_ref"))
        camp_name[cref] = row.get("campaign") or cref
        rule_name[rref] = row.get("rule") or rule_name.get(rref) or "Unnamed rule"
        rule_label[rref] = row.get("rule_label") or ""
        if camp_name[cref] not in rule_campaigns_seen[rref]:
            rule_campaigns_seen[rref].append(camp_name[cref])
        setting = SETTING.get(row.get("changed_field"))
        if setting:
            rule_setting[rref] = setting
            by_campaign[cref][setting].add(rref)
    if data.get("campaign_rules_file"):
        sources.append(f"automation_campaign_rule ({describe(map_proof)}, {len(map_refs)} campaigns in this report)")

    # ---------- 1. Custom bid-rule scorecard ----------
    perf = [r for r in data.get("rule_perf", []) if num(r.get("actions_count")) > 0]
    ranked_rows, ranked_proof = load_answers((data.get("bid_rules_ranked") or {}).get("file"))
    dayparting_refs = {ref for ref, r in rule_info.items() if "DAY_PARTING" in str(r.get("rule_kind") or "").upper()}
    # automation_activity rows are per rule AND action_kind; add them up per rule.
    agg: dict[str, dict[str, Any]] = {}
    for r in ranked_rows or []:
        ref = str(r.get("rule_ref"))
        if ref in dayparting_refs:
            continue
        e = agg.setdefault(ref, {"rule_ref": ref, "rule": r.get("rule"), "actions_count": 0, "kinds": set()})
        e["actions_count"] += int(num(r.get("actions_count")))
        e["kinds"].add(str(r.get("action_kind") or ""))
    ranked = sorted(agg.values(), key=lambda r: -r["actions_count"])
    scored_refs = {str(r.get("rule_ref")) for r in perf}
    bid_kinds = {"BID_CHANGE_KEYWORD", "TARGET_BID_CHANGE", "BID_CHANGE_PRODUCT_TARGET"}
    not_scored = [r for r in ranked if str(r.get("rule_ref")) not in scored_refs]
    kind_words = {"CAMPAIGN_BUDGET_CHANGE": "budgets", "PAUSE_KEYWORD": "pauses keywords/targets",
                  "ENABLE_KEYWORD": "enables keywords/targets", "PAUSE_PRODUCT": "pauses product ads",
                  "NEGATIVE_SEARCH_TERM": "negates search terms", "BID_CHANGE_SEARCH_TERM": "harvests search terms",
                  "CAMPAIGN_BID_ADJUSTMENT_CHANGE": "placement adjustments", "BID_CHANGE_KEYWORD": "bids",
                  "TARGET_BID_CHANGE": "bids", "BID_CHANGE_PRODUCT_TARGET": "bids"}
    win = data.get("rule_window") or {}
    if perf:
        rows = []
        for r in sorted(perf, key=lambda x: -num(x.get("actions_count"))):
            read, flag = rule_read(r)
            rows.append([r.get("rule") or "Unnamed rule", f"{int(num(r.get('actions_count'))):,}",
                         f"{int(num(r.get('acos_positive_count')))} / {int(num(r.get('acos_negative_count')))}",
                         f"{money(num(r.get('spend_before')), sign)} → {money(num(r.get('spend_after')), sign)}",
                         f"{money(num(r.get('sales_before')), sign)} → {money(num(r.get('sales_after')), sign)}", read])
            if flag:
                review.append({"rule": r.get("rule"), "rule_ref": str(r.get("rule_ref") or ""), "reason": read})
        total_neg = sum(int(num(r.get("acos_negative_count"))) for r in perf)
        total_flag = total_neg + sum(int(num(r.get("acos_positive_count"))) for r in perf)
        bid_total = len([r for r in ranked if r["kinds"] & bid_kinds]) or len(perf)
        coverage = (f"Scored {len(perf)} of {max(bid_total, len(perf))} rules that changed bids in the window "
                    "(the most active ones)." if ranked_proof["complete"] else
                    f"Scored {len(perf)} bid rule{'s' if len(perf) != 1 else ''}; whether other rules made changes was "
                    "not checked.")
        blocks.append({"type": "paragraph", "text": (
            f"{coverage} Together they made {sum(int(num(r.get('actions_count'))) for r in perf):,} bid changes. "
            f"ACOS got worse after {total_neg} of {total_flag} changes Atom11 flagged as clearly better or worse."
            + (f" {len(review)} rule{'s are' if len(review) != 1 else ' is'} worth reviewing." if review else ""))})
        blocks.append({"type": "table",
                       "columns": ["Rule", "Bid changes", "ACOS better / worse", "Spend before → after",
                                   "Sales before → after", "What happened next"],
                       "align": ["l", "r", "r", "r", "r", "l"], "rows": rows,
                       "caption": (f"Atom11 Custom Rules → Performance, changes from {win.get('start', '?')} to "
                                   f"{win.get('end', '?')}, {data.get('lookback_days', 5)} days before vs "
                                   f"{data.get('lookback_days', 5)} days after each change. Before/after shows what "
                                   "happened next, not proof the rule caused it.")})
        sources.append(f"automation_rule_performance ({win.get('start', '?')} to {win.get('end', '?')}, "
                       f"{len(perf)} rule{'s' if len(perf) != 1 else ''})")
    if not_scored:
        rows = []
        top8 = {r["rule_ref"] for r in [x for x in ranked if x["kinds"] & bid_kinds][:8]}
        for r in not_scored:
            what = ", ".join(sorted({kind_words.get(k, k.lower()) for k in r["kinds"]}))
            if not r["kinds"] & bid_kinds:
                why = "Atom11’s rule performance data covers bid changes only"
            elif r["rule_ref"] in top8:
                why = "performance was not read in this run"
            else:
                why = "not among the 8 most active bid rules"
            rows.append([r.get("rule") or "Unnamed rule", what, f"{r['actions_count']:,}", why])
        blocks.append({"type": "table", "columns": ["Not scored in this report", "What it changed",
                                                    "Changes in the window", "Why not scored"],
                       "align": ["l", "l", "r", "l"], "rows": rows,
                       "caption": "These rules also made changes in the window. No verdict is given for them."})
    if ranked_rows is not None:
        sources.append(f"automation_activity rule changes ({describe(ranked_proof)})")
    if not perf:
        blocks.append({"type": "paragraph", "text": "Bid-rule performance was not checked in this report."})

    # ---------- 2. Dayparting scorecard ----------
    dp_rows, dp_notes = [], []
    rough = False
    for d in data.get("dayparting", []):
        weeks = sorted(d.get("weeks", []), key=lambda w: str(w.get("week_start")))
        name = d.get("rule") or "Unnamed rule"
        if not weeks:
            dp_notes.append(f"{name}: Atom11 returned no weekly data, so it was not scored.")
            continue
        start_i = next((i for i, w in enumerate(weeks) if str(w.get("is_rule_start_week")).lower() == "true"), None)
        if start_i is None:
            start = str(d.get("rule_start_date") or "")
            if start and start < str(weeks[0].get("week_start")):
                start_i = 0  # started before the data begins: no baseline weeks
                dp_notes.append(f"{name}: started {start}, before Atom11’s weekly data begins, so there is no before/after.")
            else:
                dp_notes.append(f"{name}: no week is marked as the rule’s start week, so it was not scored.")
                continue
        before, since, last4 = weeks[:start_i], weeks[start_i:], weeks[-4:]
        rb, rs, r4 = roas_weighted(before), roas_weighted(since), roas_weighted(last4)
        avg_spend = sum(num(w.get("spend")) for w in since) / max(len(since), 1)
        if 0 < len(before) < 2:
            rough = True
        if rb is None or rs is None:
            read = "Atom11’s weekly data starts after the rule began, so there is no before/after comparison."
        elif rs >= rb * 1.05:
            read = f"ROAS higher since the rule started ({rb:.2f} → {rs:.2f})."
        elif rs <= rb * 0.95:
            read = f"Worth reviewing: ROAS lower since the rule started ({rb:.2f} → {rs:.2f})."
        else:
            read = "About the same ROAS as before the rule started."
        dp_rows.append([name, str(d.get("conflict_kind") or "—").capitalize(), str(len(before)),
                        f"{rb:.2f}" if rb is not None else "—", f"{rs:.2f}" if rs is not None else "—",
                        f"{r4:.2f}" if r4 is not None else "—", money(avg_spend, sign), read])
    all_dp = [r for ref, r in rule_info.items() if ref in dayparting_refs
              and str(r.get("status", "")).upper() == "ENABLED" and str(r.get("deleted", "false")).lower() != "true"]
    given = {str(d.get("rule_ref")) for d in data.get("dayparting", [])}
    dp_missing = [r.get("rule") or "Unnamed rule" for r in all_dp if str(r.get("rule_ref")) not in given]
    if dp_rows:
        blocks.append({"type": "table",
                       "columns": ["Dayparting rule", "Type", "Weeks before start", "ROAS before", "ROAS since start",
                                   "ROAS last 4 weeks", "Avg weekly spend", "What happened next"],
                       "align": ["l", "l", "r", "r", "r", "r", "r", "l"], "rows": dp_rows,
                       "caption": ("Atom11 Dayparting performance chart, spend-weighted ROAS of the rule’s campaigns."
                                   + (" Some rules have only one week of data before they started, so that comparison "
                                      "is rough." if rough else ""))})
        sources.append(f"automation_dayparting_performance ({len(dp_rows)} rule{'s' if len(dp_rows) != 1 else ''})")
    extra = dp_notes + ([f"Not scored in this report: {names_cell(dp_missing)}."] if dp_missing else [])
    if extra:
        blocks.append({"type": "bullets", "items": extra})
    notes.extend(dp_notes)

    # ---------- 3. Rule map: Table A (rules) + Table B (campaign groups) ----------
    if map_complete:
        changes_by_rule = {str(r.get("rule_ref")): int(num(r.get("actions_count"))) for r in perf}
        changes_by_rule.update({str(r.get("rule_ref")): r["actions_count"] for r in ranked
                                if str(r.get("rule_ref")) not in changes_by_rule})
        a_rows = []
        for rref in sorted(rule_setting, key=lambda x: (SETTING_ORDER.index(rule_setting[x]), rule_name.get(x, ""))):
            label = "Dayparting" if "daypart" in rule_label.get(rref, "").lower() else rule_label.get(rref, "")
            changes = changes_by_rule.get(rref)
            a_rows.append([rule_setting[rref], rule_name.get(rref, "Unnamed rule"),
                           direction(rule_name.get(rref, ""), label), str(len(rule_campaigns_seen[rref])),
                           f"{changes:,}" if changes is not None else ("Hourly (not scored)" if label == "Dayparting"
                                                                        else "Not scored")])
        if a_rows:
            blocks.append({"type": "table", "title": "Rules that change the same settings",
                           "columns": ["Setting", "Rule", "What it does (from its name)", "Campaigns in this report",
                                       "Changes in the window"],
                           "align": ["l", "l", "l", "r", "r"], "rows": a_rows,
                           "caption": "“What it does” is read from the rule’s name and type."})
        groups: dict[tuple, list[str]] = defaultdict(list)
        for cref in map_refs:
            sets = by_campaign.get(cref, {})
            key = tuple(tuple(sorted(sets.get(s, set()))) for s in SETTING_ORDER)
            groups[key].append(camp_name.get(cref) or audited_name.get(cref, cref))

        def cell(refs: tuple) -> str:
            if not refs:
                return "—"
            kinds: dict[str, int] = defaultdict(int)
            for r in refs:
                kinds[direction(rule_name.get(r, ""), rule_label.get(r, ""))] += 1
            parts = [("dayparting" if k == "changes by hour" else f"{v} {k.replace('raises', 'raise').replace('lowers', 'lower').replace('pauses', 'pause').replace('changes', 'change')}")
                     for k, v in sorted(kinds.items(), key=lambda kv: kv[0] != "changes by hour")]
            return f"{len(refs)} ({', '.join(parts)})"

        def overlap(key: tuple) -> str:
            hit = []
            for s, refs in zip(SETTING_ORDER, key):
                has_dp = any("daypart" in rule_label.get(r, "").lower() for r in refs)
                if len(refs) >= 3 or (has_dp and len(refs) >= 2):
                    hit.append(s.lower())
            return ", ".join(hit) or "—"

        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))
        shown = ordered[:15]
        b_rows = [[str(len(names)), names_cell(sorted(names)), cell(k[0]), cell(k[1]), cell(k[2]), overlap(k)]
                  for k, names in shown]
        blocks.append({"type": "table", "title": "Which campaigns share which rules",
                       "columns": ["Campaigns", "Campaign names", "Bid rules", "Budget rules", "Placement rules",
                                   "More than one rule pulls the same setting"],
                       "align": ["r", "l", "l", "l", "l", "l"], "rows": b_rows,
                       "caption": (f"Campaigns with the exact same rules are grouped into one row. Covers the "
                                   f"{len(map_refs)} campaigns in this report"
                                   + (f"; {len(ordered) - 15} more groups ({sum(len(n) for _, n in ordered[15:])} "
                                      "campaigns) are not shown." if len(ordered) > 15 else ".")
                                   + " “More than one rule” means 3 or more rules, or dayparting plus another rule, "
                                     "on one setting. Check they don’t work against each other.")})
        bare = [c for c in data.get("campaigns", []) if str(c.get("campaign_ref")) in set(map_refs)
                and not by_campaign.get(str(c.get("campaign_ref"))) and str(c.get("campaign_ref")) not in camp_name]
        if bare:
            bare.sort(key=lambda c: -num(c.get("spend")))
            blocks.append({"type": "paragraph",
                           "text": (f"{len(bare)} of the {len(map_refs)} campaigns checked "
                                    f"{'has' if len(bare) == 1 else 'have'} no enabled automation rule"
                                    f"{', the biggest by spend' if len(bare) > 1 else ''}: "
                                    + names_cell([f"{c.get('campaign')} ({money(num(c.get('spend')), sign)})" for c in bare])
                                    + "."),
                           "evidence": {"source": "automation_campaign_rule", "rows_read": map_proof["rows"],
                                        "total_count": map_proof["total_count"],
                                        "population": f"{len(map_refs)} campaigns in this report"}})
    unchecked = [c for c in data.get("campaigns", []) if str(c.get("campaign_ref")) not in set(map_refs)]
    if not map_complete and data.get("campaigns"):
        blocks.append({"type": "paragraph", "text": (
            f"Automation rules were not checked for the {len(data['campaigns'])} campaigns in this report, because the "
            f"rule map read was {describe(map_proof)}.")})
    elif unchecked:
        blocks.append({"type": "paragraph", "text": (
            f"Automation rules were not checked for the other {len(unchecked)} campaigns in this report.")})

    # ---------- rule_scopes for Pause / Remove cards ----------
    scopes: dict[str, Any] = {}
    for rref, spec in (data.get("rule_counts") or {}).items():
        rows, proof = load_answers(spec.get("file"))
        total = proof.get("total_count")
        # A count read fetches page 1 only; the proof is Atom11's total_count for the rule_ref filter.
        ok = rows is not None and total is not None
        scopes[str(rref)] = {
            "rule": spec.get("rule") or rule_name.get(str(rref)) or "Unnamed rule",
            "campaigns": rule_campaigns_seen.get(str(rref), []),
            "campaign_count": total if ok else None,
            "count_source": ({"dataset": "automation_campaign_rule", "filter": f"rule_ref eq {rref}, rule_status ENABLED",
                              "total_count": total} if ok else None),
            "complete": bool(ok and total is not None and total >= len(rule_campaigns_seen.get(str(rref), [])))}
        if not scopes[str(rref)]["complete"]:
            notes.append(f"Rule {scopes[str(rref)]['rule']}: campaign count not proven ({describe(proof)}); no Pause/Remove button.")

    section = {"title": "Automation health", "sources": sources or ["No automation data was provided"],
               "blocks": blocks}
    Path(args.output).write_text(json.dumps({"section": section, "review_rules": review, "rule_scopes": scopes,
                                             "notes": notes}, indent=2, ensure_ascii=False))
    print(f"Automation health: {len(perf)} bid rules scored ({len(review)} worth reviewing), {len(not_scored)} listed "
          f"as not scored; {len(dp_rows)} dayparting rules scored, {len(dp_missing)} not given; rule map "
          f"{describe(map_proof)}.")
    for n in notes:
        print(f"Note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
