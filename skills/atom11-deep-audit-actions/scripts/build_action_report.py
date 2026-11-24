#!/usr/bin/env python3
"""Build the deep-audit action report: one HTML page with a Take action button
beside every recommended change Atom11 can apply, and Undo after it is applied.

Inputs
  --input    the report document (JSON; format in references/action-report.md)
  --schemas  the saved get_action_schema answers for every family the report
             uses, keyed by family_id (required when any change has an action)

The script refuses to build when a change uses a family that is unknown,
blocked, irreversible or not offered as a button, when a payload does not match
the family's payload_schema, or when visible text carries internal identifiers.

Run:
  python3 build_action_report.py --input report.json --schemas schemas.json \
      --output report.html
  python3 build_action_report.py ... --mode preview_only   # buttons preview and cancel only
  python3 build_action_report.py ... --demo --standalone   # simulated Atom11, for previews
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "action-report-template.html"
DEMO_CONNECTOR = SKILL_DIR / "assets" / "demo-connector.js"
WARNINGS: list[str] = []


def _data_uri(path: Path) -> str:
    import base64
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


LOGO_LIGHT = _data_uri(SKILL_DIR / "assets" / "atom11-logo.png")
LOGO_DARK = _data_uri(SKILL_DIR / "assets" / "atom11-logo-dark.png")
RULE_STATUSES = {"covered", "not_covered", "unknown", "dayparting_adaptive", "dayparting_override"}
RECENT_STATUSES = {"recent", "none", "unknown"}
ADD_FAMILIES = {"negative_keyword_add", "negative_search_term_add", "negative_target_add", "negative_target_search_term_add",
                "keyword_add", "search_term_to_keyword", "product_target_add", "search_term_to_target"}
MONEY_FAMILIES = {"keyword_bid_change", "product_target_bid_change", "theme_bid_change", "campaign_budget_change", "ad_group_bid_change"}
CURRENCY_SIGNS = {"USD": "$", "CAD": "CA$", "AUD": "A$", "GBP": "£", "EUR": "€", "INR": "₹", "JPY": "¥", "MXN": "MX$"}

DEFAULT_SERVER = "Atom11 MCP"
NO_BUTTON_FAMILIES = {
    "undo": "undo is offered on the page after a change is applied",
    "campaign_create": "creating campaigns needs a full template review in chat",
    "autorules_rule_create": "creating a rule needs a full review in chat",
    "autorules_rule_clone": "copying rules needs a full review in chat",
    "autorules_rule_edit": "editing a rule's settings needs a full review in chat",
    "autorules_rule_delete": "deleting a rule can't be undone",
    "autorules_rule_run_now": "running a rule by hand can't be undone",
    "autorules_rule_adgroups_refresh": "rule upkeep is done in chat or on the Rules page",
    "dayparting_rule_create": "creating a dayparting rule needs a full review in chat",
    "dayparting_schedule_edit": "changing a dayparting schedule needs a full review in chat",
    "dayparting_rule_campaigns": "dayparting membership changes are prepared in chat",
    "dayparting_defaults_sync": "resetting every base value of a rule is prepared in chat",
}
# Rule-level buttons the report may offer, and the only operation each may use.
RULE_LEVEL_OPERATIONS = {"autorules_rule_state": "pause", "autorules_rule_campaigns": "remove"}
DAYPARTING_BASE_FAMILIES = {"dayparting_default_budget", "dayparting_default_keyword_bid", "dayparting_default_target_bid"}
BUDGET_FAMILIES = {"campaign_budget_change", "dayparting_default_budget"}
PORTFOLIO_STATUSES = {"capped", "ok", "unknown"}
CHANGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
LEAK_PATTERNS = (
    (re.compile(r"\bscp_[A-Za-z0-9_-]{6,}"), "an Atom11 scope id"),
    (re.compile(r"\bprop_[A-Za-z0-9_-]{6,}"), "an Atom11 proposal id"),
    (re.compile(r"\biq_[0-9a-f]{16,}"), "an Atom11 interaction id"),
    (re.compile(r"\b[0-9a-f]{32}\b"), "a trace id"),
    (re.compile(r"(?<![\d.,])\d{10,}(?![\d.,])"), "a long numeric id (entity references stay out of visible text)"),
)
DETAIL_ORDER = (
    "evidence_window", "root_cause", "evidence", "expected_benefit", "risk", "confidence",
    "destination_state", "owner", "review_date", "first_review", "hard_stop", "rollback",
)
DETAIL_LABELS = {
    "evidence_window": "Evidence window",
    "root_cause": "Root cause",
    "evidence": "Evidence",
    "expected_benefit": "Expected benefit",
    "risk": "Risk",
    "confidence": "Confidence",
    "destination_state": "Destination",
    "owner": "Owner",
    "review_date": "Review date",
    "first_review": "First review",
    "hard_stop": "Hard stop",
    "rollback": "Rollback",
}
CALLOUT_TONES = {"info", "warn", "bad", "ok"}


class BuildError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


# -- JSON schema subset ------------------------------------------------------

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer()),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def schema_errors(value: Any, schema: dict[str, Any], path: str, root: dict[str, Any] | None = None) -> list[str]:
    """Check value against the JSON-schema keywords Atom11 action schemas use."""
    root = root if root is not None else schema
    if "$ref" in schema:
        return schema_errors(value, _resolve(schema["$ref"], root), path, root)
    errors: list[str] = []

    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_TYPES.get(name, lambda v: True)(value) for name in names):
            return [f"{path}: must be {' or '.join(names)}"]

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {', '.join(map(str, schema['enum']))}")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must be {schema['const']!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: must have at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: must have at most {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")

    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: must be at most {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: must be more than {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: must be less than {schema['exclusiveMaximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: allows at most {schema['maxItems']} item(s)")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f"{path}: items must not repeat")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                errors.extend(schema_errors(item, schema["items"], f"{path}[{i}]", root))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing {key}")
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(schema_errors(item, props[key], f"{path}.{key}", root))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(schema_errors(item, schema["additionalProperties"], f"{path}.{key}", root))

    for sub in schema.get("allOf", []):
        errors.extend(schema_errors(value, sub, path, root))
    if "anyOf" in schema and not any(not schema_errors(value, sub, path, root) for sub in schema["anyOf"]):
        errors.append(f"{path}: matches none of the allowed shapes")
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if not schema_errors(value, sub, path, root))
        if matches != 1:
            errors.append(f"{path}: must match exactly one allowed shape (matches {matches})")
    return errors


# -- validation ----------------------------------------------------------------

def load_schemas(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict) and isinstance(raw.get("families"), dict):
        raw = raw["families"]
    if not isinstance(raw, dict):
        raise BuildError(["--schemas must be a JSON object keyed by family_id"])
    problems = []
    for fid, entry in raw.items():
        if not isinstance(entry, dict) or "family" not in entry or "payload_schema" not in entry:
            problems.append(f"schemas: {fid} must be the saved get_action_schema answer (family + payload_schema)")
    if problems:
        raise BuildError(problems)
    return raw


# A sentence that says something is absent ("no rule", "none of the campaigns", "missing") is a claim
# about a whole population. It may only appear when the data proves that population was read in full.
ABSENCE = re.compile(
    r"\b(?:no|none of the|never|zero)\s+(?:\w+\s+){0,3}?(?:rule|rules|automation|campaigns?|keywords?|targets?|"
    r"negatives?|ads?|asins?|products?|portfolios?|budgets?|placements?|audiences?|search terms?)\b"
    r"|\b(?:missing|untargeted|not targeted|has no|have no|without any)\b", re.IGNORECASE)
NOT_CHECKED = re.compile(r"not (?:been )?checked|could not be checked|wasn’t checked|weren’t checked|was not checked|"
                         r"were not checked|not scored|not loaded|not read", re.IGNORECASE)


def sentences(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"(?<=[.!?])\s+", str(text)) if t.strip()]


def evidence_ok(ev: Any) -> bool:
    return (isinstance(ev, dict) and ev.get("source") and isinstance(ev.get("rows_read"), int)
            and ev.get("total_count") == ev.get("rows_read") and ev.get("population"))


def accuracy_problems(doc: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Blocking: unproven absence claims, sections without sources. Warnings: lists that should be tables."""
    problems, warnings = [], []
    report_ev = [e for e in doc.get("evidence", []) if isinstance(e, dict) and e.get("text") and e.get("proof")]

    def check(text: str, where: str, block_ev: Any = None) -> None:
        for sent in sentences(text):
            if ABSENCE.search(sent) and not NOT_CHECKED.search(sent) and not evidence_ok(block_ev) \
                    and not any(e["text"] in sent for e in report_ev):
                problems.append(f"{where}: “{sent[:120]}” says something is absent, but no proof that the full "
                                "population was read. Add evidence (rows_read == total_count) or write “not checked”.")

    for k, line in enumerate(doc.get("summary", [])):
        check(line, f"summary[{k}]")
    for i, section in enumerate(doc.get("sections", [])):
        where = f"sections[{i}] ({section.get('title')})"
        if not section.get("sources"):
            problems.append(f"{where}: sources is required — list the datasets (and window) this section was built from")
        for j, block in enumerate(section.get("blocks", [])):
            bw, ev = f"{where}.blocks[{j}]", block.get("evidence")
            kind = block.get("type")
            texts = []
            if kind in ("paragraph", "callout"):
                texts = [block.get("text", "")]
            elif kind == "bullets":
                texts = list(block.get("items", []))
                if len(texts) > 5:
                    starts = {" ".join(str(t).split()[:2]).lower() for t in texts}
                    if len(starts) <= len(texts) // 2 or len(texts) > 8:
                        warnings.append(f"{bw}: {len(texts)} bullets with a repeating pattern; show them as a table")
            elif kind == "table":
                texts = [block.get("caption", "")]
                for row in block.get("rows", []):
                    texts.extend(str(c) for c in row)
                    for c in row:
                        if len(str(c)) > 300:
                            warnings.append(f"{bw}: a table cell is {len(str(c))} characters; shorten it or split it")
            for t in texts:
                check(t, bw, ev)
                if kind == "bullets" and len(str(t)) > 300:
                    warnings.append(f"{bw}: a bullet is {len(str(t))} characters; this should be a table")
    return problems, warnings


def visible_strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every string a reader can see: the whole document except action objects."""
    out: list[tuple[str, str]] = []
    if isinstance(node, str):
        out.append((path, node))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(visible_strings(item, f"{path}[{i}]"))
    elif isinstance(node, dict):
        for key, item in node.items():
            if key == "action":
                continue
            out.extend(visible_strings(item, f"{path}.{key}" if path else key))
    return out


def payload_entity_ids(payload: Any) -> set[str]:
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return set()
    return {str(i["entity_id"]) for i in items if isinstance(i, dict) and "entity_id" in i}


def validate(doc: dict[str, Any], schemas: dict[str, dict[str, Any]] | None) -> list[str]:
    problems: list[str] = []
    account = doc.get("account")
    if not isinstance(account, dict) or not account.get("display_name") or not account.get("marketplace"):
        problems.append("account: display_name and marketplace are required")
    elif account.get("scope_type", "ads_profile") != "ads_profile":
        problems.append("account: only an Ads profile is supported; DSP is out of scope")

    for path, text in visible_strings(doc):
        for pattern, what in LEAK_PATTERNS:
            if pattern.search(text):
                problems.append(f"{path}: visible text contains {what}")

    placed: dict[str, list[str]] = {}
    for i, block_section in enumerate(doc.get("sections", [])):
        if not block_section.get("title"):
            problems.append(f"sections[{i}]: title is required")
        for j, block in enumerate(block_section.get("blocks", [])):
            kind = block.get("type")
            where = f"sections[{i}].blocks[{j}]"
            if kind not in {"paragraph", "bullets", "table", "callout", "tiles", "changes"}:
                problems.append(f"{where}: unknown block type {kind!r}")
            elif kind == "changes":
                ids = block.get("ids")
                if not isinstance(ids, list) or not ids:
                    problems.append(f"{where}: a changes block needs ids, the change ids to show here")
                else:
                    for cid in ids:
                        placed.setdefault(str(cid), []).append(where)
            elif kind == "table":
                cols = block.get("columns") or []
                for r, row in enumerate(block.get("rows", [])):
                    if len(row) != len(cols):
                        problems.append(f"{where}.rows[{r}]: has {len(row)} cells for {len(cols)} columns")
            elif kind == "callout" and block.get("tone", "info") not in CALLOUT_TONES:
                problems.append(f"{where}: tone must be one of {', '.join(sorted(CALLOUT_TONES))}")

    changes = doc.get("changes")
    if not isinstance(changes, list) or not changes:
        problems.append("changes: at least one recommended change is required")
        return problems

    seen: set[str] = set()
    for i, change in enumerate(changes):
        where = f"changes[{i}]"
        cid = str(change.get("id", ""))
        if not CHANGE_ID.match(cid):
            problems.append(f"{where}: id must be 1-40 letters, digits, _ or -")
        elif cid in seen:
            problems.append(f"{where}: duplicate id {cid}")
        seen.add(cid)
        for key in ("entity", "category", "why"):
            if not change.get(key):
                problems.append(f"{where}: {key} is required")
        action = change.get("action")
        if action is None:
            if not change.get("manual_reason"):
                problems.append(f"{where}: a change without an action needs manual_reason (why it has no button)")
            continue
        problems.extend(validate_action(action, f"{where}.action", schemas))
        rc = change.get("rule_check")
        if not isinstance(rc, dict) or rc.get("status") not in RULE_STATUSES:
            problems.append(f"{where}: rule_check is missing; run scripts/check_rule_coverage.py before building "
                            "(every change with an action must be checked against automation rules)")
        elif rc["status"] == "covered" and not rc.get("rules"):
            problems.append(f"{where}.rule_check: a covered change must name the rule(s)")
        rec = change.get("recent_change")
        if not isinstance(rec, dict) or rec.get("status") not in RECENT_STATUSES:
            problems.append(f"{where}: recent_change is missing; run scripts/check_rule_coverage.py with --history "
                            "(every change with an action must be checked for changes in the last 7 days)")
        elif rec["status"] == "recent" and not (rec.get("date") and rec.get("wait_until")):
            problems.append(f"{where}.recent_change: a recent change needs date and wait_until")
        fid = action.get("family_id") if isinstance(action, dict) else None
        if isinstance(rc, dict) and rc.get("status") == "dayparting_override" and fid not in DAYPARTING_BASE_FAMILIES:
            problems.append(f"{where}: the campaign is in an OVERRIDE dayparting rule; use "
                            f"{rc.get('base_family') or 'a dayparting base-value family'} instead of {fid}")
        if fid in BUDGET_FAMILIES:
            pc = change.get("portfolio_check")
            if not isinstance(pc, dict) or pc.get("status") not in PORTFOLIO_STATUSES:
                problems.append(f"{where}: portfolio_check is missing; run scripts/check_rule_coverage.py with --portfolios")
        if fid in RULE_LEVEL_OPERATIONS:
            rs = change.get("rule_scope")
            if not isinstance(rs, dict) or not rs.get("rule") or not isinstance(rs.get("campaigns"), list):
                problems.append(f"{where}: rule_scope is required for a rule-level button: the rule name and every "
                                "campaign in it (from automation_health.py), so the preview can show who is affected")
            elif not (rs.get("complete") is True and isinstance(rs.get("campaign_count"), int)
                      and isinstance(rs.get("count_source"), dict)
                      and rs["count_source"].get("total_count") == rs["campaign_count"]
                      and rs["campaign_count"] >= len(rs["campaigns"])):
                problems.append(f"{where}.rule_scope: the rule’s full campaign count was not proven (needs complete, "
                                "campaign_count and count_source.total_count from automation_health.py). Without it "
                                "there is no button: give the change a manual_reason “full campaign list for this rule "
                                "was not loaded”.")
            elif fid == "autorules_rule_campaigns" and not rs.get("removed"):
                problems.append(f"{where}.rule_scope: name the campaign(s) leaving the rule in removed")
    for cid, wheres in placed.items():
        if cid not in seen:
            problems.append(f"{wheres[0]}: change id {cid} is not in changes")
        if len(wheres) > 1:
            problems.append(f"change {cid} is placed in more than one changes block ({', '.join(wheres)}); "
                            "place each change once so it has one button")
    return problems


def validate_action(action: Any, where: str, schemas: dict[str, dict[str, Any]] | None) -> list[str]:
    if not isinstance(action, dict):
        return [f"{where}: must be an object"]
    fid = action.get("family_id")
    if fid in NO_BUTTON_FAMILIES:
        return [f"{where}: {fid} gets no button ({NO_BUTTON_FAMILIES[fid]}); use manual_reason"]
    if schemas is None:
        return [f"{where}: --schemas is required when a change has an action"]
    entry = schemas.get(fid)
    if entry is None:
        return [f"{where}: no saved schema for family {fid!r}; call get_action_schema and add it to --schemas"]
    family = entry["family"]
    problems = []
    if family.get("blocked_reason"):
        problems.append(f"{where}: {fid} is blocked on this account ({family['blocked_reason']})")
    if family.get("irreversible"):
        problems.append(f"{where}: {fid} is irreversible, so it gets no button; use manual_reason")
    if action.get("ad_type") not in family.get("ad_types", []):
        problems.append(f"{where}: ad_type must be one of {', '.join(family.get('ad_types', []))}")
    payload = action.get("payload")
    rm = action.get("rule_match")
    if rm is not None and (not isinstance(rm, dict) or set(rm) - {"campaign_ref", "target_ref", "text", "portfolio_ref"}):
        problems.append(f"{where}.rule_match: only campaign_ref, target_ref, text and portfolio_ref are allowed")
    problems.extend(schema_errors(payload, entry["payload_schema"], f"{where}.payload"))
    if fid in RULE_LEVEL_OPERATIONS:
        ops = {i.get("operation") for i in (payload or {}).get("items", []) if isinstance(i, dict)}
        if ops != {RULE_LEVEL_OPERATIONS[fid]}:
            problems.append(f"{where}: on the report, {fid} may only {RULE_LEVEL_OPERATIONS[fid]}; "
                            "prepare anything else in chat")
        if fid == "autorules_rule_state" and len((payload or {}).get("items", [])) != 1:
            problems.append(f"{where}: pause one rule per change, so each button names one rule")
    if "scp_" in json.dumps(payload):
        problems.append(f"{where}.payload: must not contain a scope id")
    bounds = entry.get("bounds") or {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if isinstance(items, list) and bounds.get("max_entities") and len(items) > int(bounds["max_entities"]):
        problems.append(f"{where}.payload: {len(items)} items is over the family limit of {bounds['max_entities']}")
    before = action.get("report_before") or {}
    # Non-blocking: a move past Atom11's guideline still builds; Atom11 shows a
    # large_change warning the human must tick before Yes works.
    if isinstance(items, list) and isinstance(before, dict) and bounds.get("max_delta_pct"):
        limit = float(bounds["max_delta_pct"])
        for item in items:
            if not isinstance(item, dict):
                continue
            old = before.get(str(item.get("entity_id")))
            for key in ("bid", "budget", "percentage"):
                try:
                    o, n = float(str(old).replace("$", "")), float(item[key])
                except (KeyError, TypeError, ValueError):
                    continue
                if o > 0 and abs(n - o) / o * 100 > limit:
                    WARNINGS.append(f"{where}: {key} moves {abs(n - o) / o * 100:.0f}%, past Atom11's {limit:g}% guideline; "
                                    "the preview will carry a warning the clicker must tick")
    if not isinstance(before, dict):
        problems.append(f"{where}.report_before: must map entity ids to the value seen in the report")
    else:
        extra = set(map(str, before)) - payload_entity_ids(payload)
        if extra:
            problems.append(f"{where}.report_before: {', '.join(sorted(extra))} not in the payload")
    return problems


# -- rendering -------------------------------------------------------------------

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def account_label(account: dict[str, Any]) -> str:
    name, market = str(account["display_name"]), str(account["marketplace"])
    return name if re.search(rf"\b{re.escape(market)}\b", name) else f"{name} ({market})"


def render_block(block: dict[str, Any], by_id: dict[str, dict[str, Any]] | None = None) -> str:
    kind = block["type"]
    if kind == "changes":
        return render_changes_block(block, by_id or {})
    if kind == "paragraph":
        return f"<p>{esc(block.get('text'))}</p>"
    if kind == "bullets":
        return '<ul class="bullets">' + "".join(f"<li>{esc(i)}</li>" for i in block.get("items", [])) + "</ul>"
    if kind == "callout":
        title = f"<strong>{esc(block['title'])}</strong>" if block.get("title") else ""
        return f'<div class="callout" data-tone="{esc(block.get("tone", "info"))}">{title}<p>{esc(block.get("text"))}</p></div>'
    if kind == "tiles":
        tiles = []
        for t in block.get("items", []):
            note = f'<span class="note">{esc(t["note"])}</span>' if t.get("note") else ""
            tiles.append(f'<div class="tile"><span class="label">{esc(t.get("label"))}</span>'
                         f'<span class="value">{esc(t.get("value"))}</span>{note}</div>')
        return '<div class="tiles">' + "".join(tiles) + "</div>"
    cols = block.get("columns", [])
    align = block.get("align") or ["l"] * len(cols)
    right = [k < len(align) and align[k] == "r" for k in range(len(cols))]
    head = "".join(('<th class="r">' if right[k] else "<th>") + f"{esc(c)}</th>" for k, c in enumerate(cols))
    body = "".join("<tr>" + "".join(('<td class="r num">' if k < len(right) and right[k] else "<td>") + f"{esc(cell)}</td>"
                                    for k, cell in enumerate(row)) + "</tr>"
                   for row in block.get("rows", []))
    caption = f'<p class="caption">{esc(block["caption"])}</p>' if block.get("caption") else ""
    title = f'<h3 class="table-title">{esc(block["title"])}</h3>' if block.get("title") else ""
    return f'{title}<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{caption}'


def placements(doc: dict[str, Any]) -> dict[str, str]:
    """change id -> title of the section whose changes block shows it."""
    out: dict[str, str] = {}
    for section in doc.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("type") == "changes":
                for cid in block.get("ids", []):
                    out[str(cid)] = section["title"]
    return out


def render_changes_block(block: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    items = [by_id[str(c)] for c in block.get("ids", []) if str(c) in by_id]
    title = block.get("title") or "Recommended fixes"
    with_button = sum(1 for c in items if has_button(c))
    count = f"{len(items)} change" + ("" if len(items) == 1 else "s")
    if with_button:
        count += f" · {with_button} with Take action"
    return (f'<div class="group inline-fixes"><div class="group-head"><h3>{esc(title)}</h3>'
            f'<span class="count">{count}</span></div>' + "".join(render_change(c) for c in items) + "</div>")


def render_index_row(change: dict[str, Any], where: str) -> str:
    cid = esc(change["id"])
    move = ""
    if change.get("current") is not None or change.get("proposed") is not None:
        move = f'<span class="move num">{esc(change.get("current", "—"))} → {esc(change.get("proposed", "—"))}</span>'
    label = "Take action" if has_button(change) else "Details"
    status = ("Not started" if has_button(change) else "Covered by automation rule" if is_covered(change)
              else f"Wait until {short_date(change['recent_change']['wait_until'])}" if is_waiting(change)
              else "Portfolio budget used up" if is_capped(change) else "No button")
    tone = (' data-tone="rule"' if is_covered(change) else ' data-tone="wait"' if is_waiting(change) or is_capped(change)
            else "")
    return (f'<div class="index-row" data-index="{cid}"><span class="entity">{esc(change["entity"])}</span>{move}'
            f'<span class="state" data-role="mirror"{tone}>{status}</span>'
            f'<a class="jump" href="#change-{cid}">{label} in “{esc(where)}” ↑</a></div>')


def is_covered(change: dict[str, Any]) -> bool:
    return bool(change.get("action")) and (change.get("rule_check") or {}).get("status") == "covered"


def is_waiting(change: dict[str, Any]) -> bool:
    return (bool(change.get("action")) and not is_covered(change)
            and (change.get("recent_change") or {}).get("status") == "recent")


def is_capped(change: dict[str, Any]) -> bool:
    return (bool(change.get("action")) and not is_covered(change) and not is_waiting(change)
            and (change.get("portfolio_check") or {}).get("status") == "capped")


def has_button(change: dict[str, Any]) -> bool:
    return bool(change.get("action")) and not is_covered(change) and not is_waiting(change) and not is_capped(change)


def name_list(names: list[str], limit: int = 12) -> str:
    names = [str(n) for n in names]
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "")


def scope_notice(change: dict[str, Any]) -> str:
    """Plain statement of who a rule-level change affects; shown on the card and in the preview."""
    rs = change.get("rule_scope") or {}
    fid = (change.get("action") or {}).get("family_id")
    rule, campaigns = rs.get("rule", "this rule"), list(rs.get("campaigns") or [])
    n = int(rs.get("campaign_count") or len(campaigns))
    known = (f", including the ones in this report: {name_list(campaigns)}" if campaigns and len(campaigns) < n
             else f": {name_list(campaigns)}" if campaigns else "")
    def on(k: int) -> str:
        return "its only campaign" if k == 1 else "both campaigns" if k == 2 else f"all {k} campaigns"
    if fid == "autorules_rule_state":
        return (f"This changes the rule itself, so it affects every campaign in it. Pausing “{rule}” stops it on "
                f"{on(n)}{known}. What the rule already changed stays as it is. "
                "This page can’t undo it; to turn the rule back on, enable it in Atom11.")
    removed = list(rs.get("removed") or [])
    others = [c for c in campaigns if c not in removed]
    rest = n - len(removed)
    keep = ("" if rest <= 0 else
            f"The rule keeps running on the other campaign{': ' + name_list(others) if others else ''}." if rest == 1 else
            f"The rule keeps running on the other {rest} campaigns"
            + (f", including: {name_list(others)}." if others and len(others) < rest else
               f": {name_list(others)}." if others else "."))
    return (f"This changes the rule “{rule}”, which runs on {n} campaign{'s' if n != 1 else ''}. "
            f"{name_list(removed)} will leave the rule and stop being managed by it. {keep} "
            "This page can’t undo it; to put it back, add the campaign to the rule again in Atom11.").replace("  ", " ")


def info_note(change: dict[str, Any]) -> str:
    rc = change.get("rule_check") or {}
    fid = (change.get("action") or {}).get("family_id")
    if fid in RULE_LEVEL_OPERATIONS:
        return scope_notice(change)
    rule = ", ".join(rc.get("rules") or [])
    if rc.get("status") == "dayparting_adaptive":
        return (f"Dayparting is on for this campaign (rule “{rule}”). Atom11 takes this change as the rule’s new base "
                "value, so the proposed value is the normal (1x) value. Amazon’s live value can look different because "
                "it includes the current hour’s multiplier. Best applied during a 1x hour.")
    if rc.get("status") == "dayparting_override":
        return (f"Dayparting is on for this campaign (rule “{rule}”), and it overwrites live values every slot. So this "
                "changes the rule’s base value instead. The rule uses it from its next time slot; the live value isn’t "
                "changed right now.")
    return ""


def short_date(iso: str) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.strftime('%b')} {d.day}"


def show_value(value: Any, family: str, currency: str | None) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return ""
    if family in MONEY_FAMILIES:
        try:
            return f"{CURRENCY_SIGNS.get(currency or '', '')}{float(text):,.2f}"
        except ValueError:
            return text
    if family in ("campaign_placement_adjustment", "campaign_audience_bid_adjustment"):
        return text if text.endswith("%") else f"{text}%"
    return text.replace("_", " ").lower() if text.isupper() else text


def wait_message(change: dict[str, Any], currency: str | None) -> str:
    rec = change["recent_change"]
    family = change["action"].get("family_id", "")
    before = show_value(rec.get("before"), family, currency)
    after = show_value(rec.get("after"), family, currency)
    move = f" ({before} → {after})" if before and after and before != after else ""
    who = (f"by the automation rule “{rec['rule']}”" if rec.get("source") == "rule" and rec.get("rule")
           else "by an automation rule" if rec.get("source") == "rule" else "manually")
    days = rec.get("wait_days", 7)
    subject = "This search term was updated" if family in ADD_FAMILIES else "This was changed"
    return (f"{subject} {who} on {short_date(rec['date'])}{move}. A change needs about {days} days to show "
            f"results, so it’s best not to change it again yet. You can act on this from {short_date(rec['wait_until'])}.")


CURRENCY: dict[str, str | None] = {"code": None}


def render_change(change: dict[str, Any]) -> str:
    cid = esc(change["id"])
    covered = is_covered(change)
    waiting = is_waiting(change)
    action = change.get("action") if not (covered or waiting) else None
    tags = [*change.get("tags", [])]
    for key in ("priority", "decision"):
        if change.get(key):
            tags.append(change[key])
    tag_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags)
    move = ""
    if change.get("current") is not None or change.get("proposed") is not None:
        note = f'<span class="delta num">{esc(change["change_note"])}</span>' if change.get("change_note") else ""
        move = (f'<span class="move num">{esc(change.get("current", "—"))} → {esc(change.get("proposed", "—"))}</span>{note}')
    rc = change.get("rule_check") or {}
    hold = ""
    capped = is_capped(change)
    if capped:
        action = None
    if covered:
        rules = ", ".join(rc.get("rules") or [])
        what = f" It already changes {rc['what']} here." if rc.get("what") else ""
        side = '<span class="state" data-tone="rule">Covered by automation rule</span>'
        hold = (f'<p class="hold" data-tone="rule"><strong>Covered by automation rule.</strong> Rule: {esc(rules)}.'
                f'{esc(what)} Change the rule in Atom11 instead of acting here.</p>')
    elif waiting:
        side = f'<span class="state" data-tone="wait">Wait until {esc(short_date(change["recent_change"]["wait_until"]))}</span>'
        hold = f'<p class="hold" data-tone="wait"><strong>Wait {esc(str(change["recent_change"].get("wait_days", 7)))} days.</strong> {esc(wait_message(change, CURRENCY["code"]))}</p>'
    elif capped:
        pc = change["portfolio_check"]
        side = '<span class="state" data-tone="wait">Portfolio budget used up</span>'
        limit = f" (limit {show_value(pc.get('budget'), 'campaign_budget_change', CURRENCY['code'])})" if pc.get("budget") else ""
        hold = (f'<p class="hold" data-tone="wait"><strong>Portfolio budget used up.</strong> The portfolio '
                f'“{esc(pc.get("portfolio") or "")}” has spent its budget{esc(limit)}. Raising this campaign’s budget won’t '
                'increase spend until the portfolio budget is raised.</p>')
    elif action:
        notes = []
        if rc.get("status") == "unknown":
            notes.append(rc.get("note") or "Automation rules could not be checked.")
        rec = change.get("recent_change") or {}
        if rec.get("status") == "unknown":
            notes.append(rec.get("note") or "Recent changes could not be checked.")
        unknown = "".join(f'<p class="manual">{esc(n)}</p>' for n in notes)
        if (change.get("portfolio_check") or {}).get("status") == "unknown":
            unknown += f'<p class="manual">{esc(change["portfolio_check"].get("note") or "The portfolio budget could not be checked.")}</p>'
        side = (f'<span class="state" data-role="state">Not started</span>'
                f'<button type="button" class="btn-primary" data-role="take" id="take-{cid}">Take action</button>{unknown}')
        info = info_note(change)
        if info:
            tone = "scope" if (change.get("action") or {}).get("family_id") in RULE_LEVEL_OPERATIONS else "info"
            fid_ = (change.get("action") or {}).get("family_id")
            label = ("Affects every campaign in this rule." if fid_ == "autorules_rule_state"
                     else "Changes this rule." if tone == "scope" else "Dayparting.")
            hold = f'<p class="hold" data-tone="{tone}"><strong>{label}</strong> {esc(info)}</p>'
    else:
        side = f'<span class="state">No button</span><p class="manual">{esc(change.get("manual_reason"))}</p>'
    details = change.get("details") or {}
    rows = []
    for key in [*DETAIL_ORDER, *[k for k in details if k not in DETAIL_ORDER]]:
        if details.get(key):
            rows.append(f"<dt>{esc(DETAIL_LABELS.get(key, key.replace('_', ' ').capitalize()))}</dt><dd>{esc(details[key])}</dd>")
    more = (f'<details class="more"><summary>Evidence, risk and review</summary><dl>{"".join(rows)}</dl></details>'
            if rows else "")
    panel = '<div class="panel" data-role="panel" aria-live="polite" hidden></div>' if action else ""
    attr = (f'data-change="{cid}"' if action else f'data-covered="{cid}"' if covered
            else f'data-waiting="{cid}"' if waiting else f'data-capped="{cid}"' if capped else f'data-manual="{cid}"')
    return (f'<article class="change" id="change-{cid}" {attr}><div class="change-row">'
            f'<div class="what"><span class="entity">{esc(change["entity"])}</span><div class="tags">{tag_html}</div>'
            f'<p class="why">{esc(change["why"])}</p></div>'
            f'<div class="move-box">{move}</div><div class="side">{side}</div></div>{hold}{more}{panel}</article>')


def render_body(doc: dict[str, Any], mode: str, demo: bool) -> str:
    account = doc["account"]
    window = doc.get("window") or {}
    meta = [account["marketplace"]]
    if account.get("currency"):
        meta.append(account["currency"])
    if window.get("start") and window.get("end"):
        meta.append(f"{window['start']} to {window['end']}")
    if window.get("latest_complete_date"):
        meta.append(f"data complete through {window['latest_complete_date']}")
    if doc.get("prepared"):
        meta.append(f"prepared {doc['prepared']}")

    parts = ['<header class="head"><div class="brand">'
             f'<img class="logo logo-light" src="{LOGO_LIGHT}" alt="Atom11" width="144" height="32">'
             f'<img class="logo logo-dark" src="{LOGO_DARK}" alt="Atom11" width="144" height="32">'
             '<span class="brand-name">Deep Audit</span></div>'
             f'<h1>{esc(account_label(account))}</h1><p class="meta">{esc(" · ".join(meta))}</p></header>']
    if demo:
        parts.append('<div class="notice" data-tone="warn" role="note"><p><strong>Demo.</strong> Atom11 is simulated on '
                     'this page with sample data. Nothing is sent to Atom11 or Amazon. Try Take action, Yes and then '
                     'Undo on any change.</p></div>')
    elif mode == "live":
        parts.append('<div class="notice" role="note"><p><strong>Take action</strong> asks Atom11 for a preview first. '
                     'Nothing changes on Amazon until you click Yes. After a change is applied, Undo stays here while '
                     'this page is open.</p><p>The buttons work in claude.ai for people with the Atom11 connector and '
                     'access to this account, under their own Atom11 login. The first click asks you to allow this page '
                     'to use Atom11.</p></div>')
    else:
        parts.append('<div class="notice" role="note"><p><strong>Preview only.</strong> Take action asks Atom11 for a '
                     'preview, which you can cancel. Applying is switched off on this page.</p></div>')
    parts.append('<div class="notice" data-tone="warn" data-role="unavailable" role="note" hidden><p>Take action '
                 'buttons work only when this page is open in claude.ai by someone with the Atom11 connector. '
                 'They are switched off here.</p></div>')
    parts.append('<div class="notice" data-tone="warn" data-role="halt" role="alert" hidden></div>')

    if doc.get("summary"):
        parts.append('<section class="section"><h2>Summary</h2><ul class="bullets">'
                     + "".join(f"<li>{esc(s)}</li>" for s in doc["summary"]) + "</ul></section>")
    CURRENCY["code"] = account.get("currency")
    by_id = {str(c["id"]): c for c in doc["changes"]}
    placed = placements(doc)
    for section in doc.get("sections", []):
        blocks = "".join(render_block(b, by_id) for b in section.get("blocks", []))
        src = section.get("sources") or []
        src_html = f'<p class="sources">Data: {esc("; ".join(str(x) for x in src))}</p>' if src else ""
        parts.append(f'<section class="section"><h2>{esc(section["title"])}</h2>{blocks}{src_html}</section>')

    changes = doc["changes"]
    order = list(doc.get("categories") or [])
    for change in changes:
        if change["category"] not in order:
            order.append(change["category"])
    with_button = sum(1 for c in changes if has_button(c))
    covered_n = sum(1 for c in changes if is_covered(c))
    waiting_n = sum(1 for c in changes if is_waiting(c))
    groups = []
    for category in order:
        items = [c for c in changes if c["category"] == category]
        if not items:
            continue
        count = f"{len(items)} change" + ("" if len(items) == 1 else "s")
        groups.append(f'<div class="group"><div class="group-head"><h3>{esc(category)}</h3>'
                      f'<span class="count">{count}</span></div>'
                      + "".join(render_index_row(c, placed[str(c["id"])]) if str(c["id"]) in placed else render_change(c)
                                for c in items) + "</div>")
    parts.append(f'<section class="section" id="change-queue"><h2>Change queue</h2><p class="caption">'
                 f'{len(changes)} recommended change{"" if len(changes) == 1 else "s"} · {covered_n} covered by an automation rule · {waiting_n} changed in the last 7 days (wait) · {with_button} with a Take action '
                 f'button. Changes shown under their table above link back there.</p>{"".join(groups)}</section>')

    parts.append('<section class="section"><h2>How the buttons work</h2><ul class="bullets">'
                 '<li>Take action asks Atom11 for a preview. Nothing changes on Amazon at this step.</li>'
                 '<li>You see Atom11\'s current value, the new value, every warning and when the preview expires. '
                 'Warnings need a tick before Yes works.</li>'
                 '<li>Yes applies exactly that preview. No cancels it.</li>'
                 '<li>After a change is applied, Undo shows Atom11\'s undo preview the same way. Undo stays on this page '
                 'until you close or reload it; after that, ask Claude to undo the change using the code shown.</li>'
                 '<li><strong>Covered by automation rule</strong> means an Atom11 rule already manages this '
                 'setting, so there is no button. Change the rule in Atom11 instead.</li>'
                 '<li><strong>Dayparting</strong> notes explain how a change works with a dayparting rule: an '
                 'adaptive rule takes the change as its new base value; an override rule gets its base value changed '
                 'instead, from its next time slot.</li>'
                 '<li>Buttons that pause a rule or take a campaign out of a rule change the rule itself. The preview '
                 'lists every campaign the rule runs on and needs a tick before Yes works.</li>'
                 '<li><strong>Portfolio budget used up</strong> means a budget increase can’t help until the portfolio '
                 'budget is raised, so there is no button.</li>'
                 '<li><strong>Wait until …</strong> means this setting was changed in the last 7 days, by a person or '
                 'by a rule. A change needs about a week to show results, so there is no button until then. '
                 'Hourly dayparting changes don\'t count.</li>'
                 '<li>If Atom11 can\'t tell whether a change ran, the page pauses every button until you check History '
                 'in Atom11.</li></ul></section>')
    return "\n".join(parts)


def page_data(doc: dict[str, Any], server: str, mode: str) -> dict[str, Any]:
    account = doc["account"]
    changes = {}
    for change in doc["changes"]:
        action = change.get("action")
        if not action or not has_button(change):
            continue
        move = ""
        if change.get("current") is not None or change.get("proposed") is not None:
            move = f": {change.get('current', '—')} → {change.get('proposed', '—')}"
        changes[change["id"]] = {
            "label": f"{change.get('decision') or 'Change'} {change['entity']}{move}",
            "entity_label": change["entity"],
            "family_id": action["family_id"],
            "ad_type": action["ad_type"],
            "payload": action["payload"],
            "report_before": action.get("report_before") or {},
            "reason": str(change["why"])[:300],
        }
        if action["family_id"] in RULE_LEVEL_OPERATIONS:
            changes[change["id"]]["scope_notice"] = scope_notice(change)
    return {
        "config": {
            "server": server,
            "mode": mode,
            "account": {
                "scope_type": account.get("scope_type", "ads_profile"),
                "display_name": account["display_name"],
                "marketplace": account["marketplace"],
                "currency": account.get("currency"),
                "label": account_label(account),
            },
        },
        "changes": changes,
    }


def safe_json(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=None, separators=(",", ":"))
    for raw, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(raw, escaped)
    return text


def build(doc: dict[str, Any], schemas: dict[str, dict[str, Any]] | None, *, server: str = DEFAULT_SERVER,
          mode: str = "live", demo: bool = False, standalone: bool = False) -> str:
    problems = validate(doc, schemas)
    acc_problems, acc_warnings = accuracy_problems(doc)
    problems += acc_problems
    WARNINGS.extend(acc_warnings)
    if problems:
        raise BuildError(problems)
    if demo:
        mode = "live"
    title = doc.get("title") or f"{doc['account']['display_name']} Deep Audit"
    demo_script = f"<script>\n{DEMO_CONNECTOR.read_text()}\n</script>" if demo else ""
    page = (TEMPLATE.read_text()
            .replace("@@ATOM11_TITLE@@", esc(title))
            .replace("@@ATOM11_BODY@@", render_body(doc, mode, demo))
            .replace("@@ATOM11_DATA@@", safe_json(page_data(doc, server, mode)))
            .replace("@@ATOM11_DEMO@@", demo_script))
    # Always a complete document: the Artifact tool publishes whole HTML files,
    # and phones need the viewport tag. (--standalone is kept as a no-op alias.)
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + page.replace("</style>", "</style>\n</head>\n<body>", 1)
            + "\n</body>\n</html>\n")
    return page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="report document JSON")
    parser.add_argument("--schemas", help="saved get_action_schema answers keyed by family_id")
    parser.add_argument("--output", required=True, help="where to write the HTML page")
    parser.add_argument("--server", default=DEFAULT_SERVER,
                        help="the Atom11 connector's display name in claude.ai (default: %(default)s)")
    parser.add_argument("--mode", choices=("live", "preview_only"), default="live",
                        help="live = Yes applies; preview_only = preview and cancel only")
    parser.add_argument("--demo", action="store_true", help="simulate Atom11 with the page's own data (previews only)")
    parser.add_argument("--standalone", action="store_true", help="no-op: output is always a full HTML document")
    args = parser.parse_args(argv)

    try:
        doc = json.loads(Path(args.input).read_text())
        schemas = load_schemas(json.loads(Path(args.schemas).read_text())) if args.schemas else None
        page = build(doc, schemas, server=args.server, mode=args.mode, demo=args.demo, standalone=args.standalone)
    except BuildError as exc:
        print("Not built. Fix these first:", file=sys.stderr)
        for problem in exc.problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Not built: {exc}", file=sys.stderr)
        return 1
    if re.search(r"\s", Path(args.output).name):
        print(f"Not built: output name {Path(args.output).name!r} has spaces; the Artifact tool refuses it. "
              "Use letters, digits and - only.", file=sys.stderr)
        return 1
    Path(args.output).write_text(page)
    for warning in WARNINGS:
        print(f"Note: {warning}", file=sys.stderr)
    buttons = sum(1 for c in doc["changes"] if has_button(c))
    covered = sum(1 for c in doc["changes"] if is_covered(c))
    waiting = sum(1 for c in doc["changes"] if is_waiting(c))
    print(f"Built {args.output}: {len(doc['changes'])} changes, {buttons} with a Take action button, "
          f"{covered} covered by an automation rule, {waiting} waiting after a recent change, "
          f"{sum(1 for c in doc['changes'] if is_capped(c))} blocked by a portfolio budget, "
          f"mode {('demo' if args.demo else args.mode)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
