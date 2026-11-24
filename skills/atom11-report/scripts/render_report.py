#!/usr/bin/env python3
"""Render an Atom11 report document as a self-contained HTML decision brief.

Usage:
    python3 render_report.py --document report.json --evidence <files-or-dirs...> \
        --output report.html [--no-verify]

Every KPI value, previous value, percent change and table cell in the document
is verified against the raw MCP responses given as evidence. Values the
evidence does not contain stop the render (exit 2) and are listed. Internal
identifiers (scope/trace/interaction/recipe/dataset ids, *_ref/*_id keys,
opaque tokens) are refused regardless of --no-verify.

Standard library only (Python 3.9+). The HTML has no remote resources.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

# Atom11 icon, drawn as inline SVG so the report needs no image file.
ATOM11_ICON = (
    '<svg class="logo" viewBox="0 0 338 338" width="24" height="24" role="img" aria-label="Atom11">'
    '<rect width="338" height="338" rx="22" fill="#2250F3"/>'
    '<circle cx="126" cy="107.5" r="36" fill="#fff"/>'
    '<path d="M158 154.5A55.75 55.75 0 1 0 158 264Z" fill="#fff"/>'
    '<path d="M184 265V71.5A64 64 0 0 1 248 135.5V265Z" fill="#fff"/>'
    '</svg>'
)

SCHEMA_VERSION = 1
FORMATS = {'text', 'integer', 'number', 'currency', 'percent', 'percent_value', 'multiplier', 'date'}
STATUSES = {'ok', 'partial', 'unavailable', 'failed', 'skipped'}
CURRENCY_SYMBOLS = {
    'USD': '$', 'CAD': 'CA$', 'MXN': 'MX$', 'AUD': 'A$', 'SGD': 'S$', 'BRL': 'R$',
    'EUR': '€', 'GBP': '£', 'INR': '₹', 'JPY': '¥', 'AED': 'AED ', 'SAR': 'SAR ',
    'SEK': 'kr ', 'PLN': 'zł ', 'TRY': '₺', 'EGP': 'EGP ',
}
FORBIDDEN_KEY_RE = re.compile(r'(^|_)(scope_id|trace_id|interaction_id|recipe_id|dataset_id|variant_id|tenant)$|(_ref|_id)$')
FORBIDDEN_TEXT_RE = re.compile(r'\b(scope_id|trace_id|interaction_id|recipe_id|dataset_id|variant_id)\b', re.I)
OPAQUE_TOKEN_RE = re.compile(r'(?<![\w/.:-])[A-Za-z0-9_-]{40,}(?![\w/.:-])')


class RenderError(Exception):
    pass


# --------------------------------------------------------------------------
# Evidence index
# --------------------------------------------------------------------------
def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = value.strip().replace(',', '')
        if text.endswith('%'):
            text = text[:-1].strip()
        if text.endswith('×') or text.lower().endswith('x'):
            text = text[:-1].strip()
        if not re.fullmatch(r'[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?', text):
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _norm_num(d: Decimal) -> str:
    d = d.normalize()
    if d == 0:
        return '0'
    return format(d, 'f')


def _round2(d: Decimal) -> str:
    return _norm_num(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _norm_text(s: str) -> str:
    return ' '.join(s.split()).casefold()


class EvidenceIndex:
    def __init__(self) -> None:
        self.numbers: set[str] = set()
        self.numbers_2dp: set[str] = set()
        self.strings: set[str] = set()
        self.files: list[str] = []

    def add_file(self, path: str) -> None:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        self.files.append(path)
        self._walk(data)

    def _walk(self, node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                self._walk(value)
        elif isinstance(node, list):
            for value in node:
                self._walk(value)
        elif isinstance(node, bool) or node is None:
            return
        elif isinstance(node, (int, float)):
            d = _to_decimal(node)
            if d is not None:
                self._add_number(d)
        elif isinstance(node, str):
            self.strings.add(_norm_text(node))
            d = _to_decimal(node)
            if d is not None:
                self._add_number(d)

    def _add_number(self, d: Decimal) -> None:
        self.numbers.add(_norm_num(d))
        self.numbers_2dp.add(_round2(d))

    def has_number(self, d: Decimal) -> bool:
        for cand in (d, d * 100, d / 100):
            if _norm_num(cand) in self.numbers or _round2(cand) in self.numbers_2dp:
                return True
            if _round2(cand) in self.numbers:
                return True
        return False

    def has_string(self, s: str) -> bool:
        return _norm_text(s) in self.strings


def load_evidence(paths: Iterable[str]) -> EvidenceIndex:
    index = EvidenceIndex()
    for path in paths:
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if name.lower().endswith('.json'):
                    index.add_file(os.path.join(path, name))
        elif os.path.isfile(path):
            index.add_file(path)
        else:
            raise RenderError(f'evidence path not found: {path}')
    if not index.files:
        raise RenderError('no evidence files were found; pass the raw MCP responses')
    return index


# --------------------------------------------------------------------------
# Document validation and verification
# --------------------------------------------------------------------------
def _is_null(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in {'', '—', '-', 'null', 'None'})


def validate_document(doc: dict) -> list[str]:
    problems: list[str] = []
    if doc.get('schema_version') != SCHEMA_VERSION:
        problems.append(f'schema_version must be {SCHEMA_VERSION}')
    report = doc.get('report') or {}
    for key in ('title', 'report_type', 'generated_on'):
        if not isinstance(report.get(key), str) or not report[key].strip():
            problems.append(f'report.{key} is required')
    account = report.get('account') or {}
    if not isinstance(account.get('display_name'), str) or not account['display_name'].strip():
        problems.append('report.account.display_name is required')
    period = report.get('period') or {}
    for key in ('start', 'end'):
        if not isinstance(period.get(key), str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', period[key]):
            problems.append(f'report.period.{key} must be YYYY-MM-DD')
    if report.get('cadence') not in (None, 'weekly', 'monthly', 'one-off', 'daily'):
        problems.append('report.cadence must be weekly, monthly, daily or one-off')
    if report.get('data_completeness') not in (None, 'complete', 'partial'):
        problems.append('report.data_completeness must be complete or partial')
    verdict = report.get('verdict')
    if isinstance(verdict, str) and len(verdict.split()) > 12:
        problems.append('report.verdict must be at most twelve words')
    sections = doc.get('sections')
    if not isinstance(sections, list) or not sections:
        problems.append('sections must be a non-empty list')
        sections = []
    for si, section in enumerate(sections):
        where = f'sections[{si}]'
        if not isinstance(section, dict):
            problems.append(f'{where} must be an object')
            continue
        for key in ('id', 'heading'):
            if not isinstance(section.get(key), str) or not section[key].strip():
                problems.append(f'{where}.{key} is required')
        status = section.get('status', 'ok')
        if status not in STATUSES:
            problems.append(f'{where}.status must be one of {sorted(STATUSES)}')
        for ki, kpi in enumerate(section.get('kpis') or []):
            kw = f'{where}.kpis[{ki}]'
            if not isinstance(kpi, dict) or not isinstance(kpi.get('label'), str):
                problems.append(f'{kw} needs a label')
                continue
            if kpi.get('format', 'number') not in FORMATS:
                problems.append(f'{kw}.format {kpi.get("format")!r} is not a known format')
            if FORBIDDEN_KEY_RE.search(kpi['label'].strip().lower().replace(' ', '_')):
                problems.append(f'{kw}.label looks like an internal identifier: {kpi["label"]!r}')
        for ti, table in enumerate(section.get('tables') or []):
            tw = f'{where}.tables[{ti}]'
            if not isinstance(table, dict):
                problems.append(f'{tw} must be an object')
                continue
            columns = table.get('columns')
            if not isinstance(columns, list) or not columns:
                problems.append(f'{tw}.columns is required')
                continue
            keys = []
            for ci, col in enumerate(columns):
                if not isinstance(col, dict) or not isinstance(col.get('key'), str):
                    problems.append(f'{tw}.columns[{ci}] needs a key')
                    continue
                keys.append(col['key'])
                if FORBIDDEN_KEY_RE.search(col['key']):
                    problems.append(f'{tw}.columns[{ci}].key {col["key"]!r} is an internal identifier; use a name column')
                if col.get('format', 'text') not in FORMATS:
                    problems.append(f'{tw}.columns[{ci}].format {col.get("format")!r} is not a known format')
            for ri, row in enumerate(table.get('rows') or []):
                if not isinstance(row, dict):
                    problems.append(f'{tw}.rows[{ri}] must be an object')
                    continue
                for key in row:
                    if key not in keys:
                        problems.append(f'{tw}.rows[{ri}] has key {key!r} that is not a declared column')
            chart = table.get('chart')
            if chart is not None:
                if chart.get('type') not in ('bar', 'hbar'):
                    problems.append(f'{tw}.chart.type must be bar or hbar')
                for ck in ('label_key', 'value_key'):
                    if chart.get(ck) not in keys:
                        problems.append(f'{tw}.chart.{ck} must name a declared column')
    for di, item in enumerate(doc.get('decision_queue') or []):
        if not isinstance(item, dict) or not isinstance(item.get('title'), str):
            problems.append(f'decision_queue[{di}] needs a title')
    return problems


def _scan_text_for_identifiers(doc: dict) -> list[str]:
    problems: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f'{path}.{key}')
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f'{path}[{i}]')
        elif isinstance(node, str):
            if FORBIDDEN_TEXT_RE.search(node):
                problems.append(f'{path} mentions an internal identifier name: {node[:80]!r}')
            if 'http' not in node and OPAQUE_TOKEN_RE.search(node):
                problems.append(f'{path} contains an opaque token that looks like an internal id: {node[:80]!r}')

    walk(doc, 'document')
    return problems


def verify_document(doc: dict, evidence: EvidenceIndex) -> list[str]:
    problems: list[str] = []
    report = doc['report']

    def check_number(value: Any, where: str) -> None:
        if _is_null(value):
            return
        d = _to_decimal(value)
        if d is None:
            problems.append(f'{where}: {value!r} is not a number')
        elif not evidence.has_number(d):
            problems.append(f'{where}: value {value!r} was not found in the evidence')

    def check_text(value: Any, where: str) -> None:
        if _is_null(value):
            return
        if not isinstance(value, str):
            value = str(value)
        if not evidence.has_string(value):
            d = _to_decimal(value)
            if d is not None and evidence.has_number(d):
                return
            problems.append(f'{where}: text {value!r} was not found in the evidence')

    check_text(report['account']['display_name'], 'report.account.display_name')
    check_text(report['period']['start'], 'report.period.start')
    check_text(report['period']['end'], 'report.period.end')
    for si, section in enumerate(doc['sections']):
        where = f"sections[{si}] ({section.get('id')})"
        for ki, kpi in enumerate(section.get('kpis') or []):
            kw = f"{where}.kpis[{ki}] '{kpi.get('label')}'"
            fmt = kpi.get('format', 'number')
            if fmt in ('text', 'date'):
                check_text(kpi.get('value'), f'{kw}.value')
            else:
                check_number(kpi.get('value'), f'{kw}.value')
                check_number(kpi.get('previous'), f'{kw}.previous')
            check_number(kpi.get('percent_change'), f'{kw}.percent_change')
        for ti, table in enumerate(section.get('tables') or []):
            tw = f"{where}.tables[{ti}] '{table.get('title')}'"
            columns = table.get('columns') or []
            for ri, row in enumerate(table.get('rows') or []):
                for col in columns:
                    key = col['key']
                    if key not in row:
                        continue
                    cell = row[key]
                    cw = f'{tw}.rows[{ri}].{key}'
                    fmt = col.get('format', 'text')
                    if fmt in ('text', 'date'):
                        if col.get('verify', True):
                            check_text(cell, cw)
                    else:
                        check_number(cell, cw)
    return problems


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def _group_int(d: Decimal, places: int) -> str:
    q = Decimal(1).scaleb(-places) if places else Decimal(1)
    d = d.quantize(q, rounding=ROUND_HALF_UP)
    sign = '-' if d < 0 else ''
    d = abs(d)
    whole, _, frac = format(d, 'f').partition('.')
    whole = f'{int(whole):,}'
    return f'{sign}{whole}.{frac}' if places else f'{sign}{whole}'


def fmt_value(value: Any, fmt: str, currency: str, signed: bool = False) -> str:
    if _is_null(value):
        return '—'
    if fmt in ('text', 'date'):
        return str(value)
    d = _to_decimal(value)
    if d is None:
        return str(value)
    prefix = '+' if signed and d > 0 else ''
    if fmt == 'integer':
        return prefix + _group_int(d, 0)
    if fmt == 'number':
        return prefix + _group_int(d, 2)
    if fmt == 'currency':
        sym = CURRENCY_SYMBOLS.get(currency.upper(), f'{currency.upper()} ') if currency else ''
        body = _group_int(abs(d), 2)
        sign = '-' if d < 0 else prefix
        return f'{sign}{sym}{body}'
    if fmt == 'percent':
        return prefix + _group_int(d * 100, 1) + '%'
    if fmt == 'percent_value':
        return prefix + _group_int(d, 1) + '%'
    if fmt == 'multiplier':
        return prefix + _group_int(d, 2) + '×'
    return str(value)


def _pct_change_decimal(value: Any) -> Decimal | None:
    """Accept a ratio (0.0082) or a percent string ('0.82%'); return ratio."""
    if _is_null(value):
        return None
    if isinstance(value, str) and value.strip().endswith('%'):
        d = _to_decimal(value)
        return None if d is None else d / 100
    return _to_decimal(value)


def _pretty_date(text: str) -> str:
    try:
        return dt.date.fromisoformat(text).strftime('%b %-d, %Y')
    except (ValueError, TypeError):
        return text


def esc(value: Any) -> str:
    return html.escape('' if value is None else str(value), quote=True)


# --------------------------------------------------------------------------
# HTML pieces
# --------------------------------------------------------------------------
CSS = """
:root{--ink:#181B25;--subtle:#525866;--line:#D9DEE8;--paper:#F7F4EA;--surface:#FFFFFF;--cobalt:#2250F3;--cobalt-soft:#E5EBFF;--citrus:#FFC01E;--citrus-soft:#FFF3C4;--teal:#23967F;--teal-soft:#E0F4EE;--rose:#CD1230;--rose-soft:#FBE4E8;--mute:#8A90A0}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.serif{font-family:Georgia,"Iowan Old Style","Times New Roman",serif}
.wrap{max-width:1040px;margin:0 auto;padding:24px 16px 56px}
a{color:var(--cobalt)}
.cover{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px 32px;align-items:end;border-bottom:3px solid var(--cobalt);padding:8px 0 18px;margin-bottom:18px}
.brand{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.brand .logo{width:24px;height:24px;display:block}
.wordmark{font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--cobalt);font-size:12px}
.cover h1{margin:6px 0 2px;font-size:30px;line-height:1.15;font-weight:600}
.cover .sub{color:var(--subtle);margin:0}
.meta{display:grid;grid-template-columns:auto auto;gap:2px 14px;font-size:13px;color:var(--subtle)}
.meta dt{font-weight:600;color:var(--ink)}
.meta dd{margin:0}
.ribbon{display:flex;flex-wrap:wrap;gap:0;border:1px solid var(--line);background:var(--surface);margin:0 0 22px}
.ribbon div{padding:10px 14px;border-right:1px solid var(--line);min-width:140px;flex:1 1 auto}
.ribbon div:last-child{border-right:0}
.ribbon .k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--subtle)}
.ribbon .v{font-weight:700;font-size:16px}
.ribbon .v.partial{color:var(--rose)}
.ribbon .v.ok{color:var(--teal)}
.reading{background:var(--surface);border-left:6px solid var(--citrus);padding:18px 20px;margin:0 0 28px}
.reading h2{margin:0 0 8px;font-size:24px;line-height:1.2;font-weight:600}
.reading p{margin:0;color:var(--ink)}
.module{background:var(--surface);border:1px solid var(--line);margin:0 0 22px;padding:0 0 6px;page-break-inside:avoid}
.module>header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;padding:12px 18px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,var(--cobalt-soft) 0,var(--cobalt-soft) 6px,var(--surface) 6px)}
.module>header h2{margin:0;font-size:19px;font-weight:600}
.module>header .src{color:var(--subtle);font-size:13px}
.status{display:inline-block;padding:1px 8px;border:1px solid var(--line);font-size:12px;border-radius:2px;background:var(--paper)}
.status.partial,.status.failed{border-color:var(--rose);color:var(--rose);background:var(--rose-soft)}
.status.unavailable,.status.skipped{color:var(--subtle)}
.note{margin:12px 18px 4px;padding:8px 12px;border-left:4px solid var(--cobalt);background:var(--cobalt-soft);font-size:14px}
.note b{color:var(--cobalt)}
.statusnote{margin:12px 18px;color:var(--subtle)}
.warn{margin:8px 18px;padding:8px 12px;background:var(--citrus-soft);border-left:4px solid var(--citrus);font-size:13px}
.ledger{width:100%;border-collapse:collapse;margin:10px 0 4px;font-variant-numeric:tabular-nums}
.ledger th,.ledger td{padding:7px 18px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
.ledger th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--subtle);font-weight:600}
.ledger td.num,.ledger th.num{text-align:right;white-space:nowrap}
.ledger tr.group td{background:var(--paper);font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--subtle);padding-top:9px}
.ledger .lbl small{display:block;color:var(--subtle);font-weight:400}
.chg{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.chg .rail{display:inline-block;width:64px;height:7px;background:var(--line);position:relative;vertical-align:middle}
.chg .rail i{position:absolute;top:0;bottom:0;background:var(--mute)}
.chg.up i,.chg.up{color:var(--teal)} .chg.up i{background:var(--teal)}
.chg.down i,.chg.down{color:var(--rose)} .chg.down i{background:var(--rose)}
.chg.flat{color:var(--subtle)}
.dash{color:var(--mute)}
.tbl{margin:14px 18px 10px}
.tbl h3{margin:0 0 6px;font-size:15px;font-weight:600}
.tbl table{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.tbl th,.tbl td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.tbl th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--subtle);background:var(--paper)}
.tbl th.num,.tbl td.num{text-align:right;white-space:nowrap}
.tbl td.neg{color:var(--rose)} .tbl td.pos{color:var(--teal)}
.cov{margin:6px 0 0;font-size:12.5px;color:var(--subtle)}
.foot{margin:2px 0 0;font-size:12.5px;color:var(--subtle)}
.chart{margin:8px 0 2px}
.chart svg{width:100%;height:auto;display:block}
ul.bul{margin:10px 18px 6px;padding-left:20px}
ul.bul li{margin:3px 0}
.queue{background:var(--surface);border:1px solid var(--line);margin:0 0 22px}
.queue>header{padding:12px 18px;border-bottom:1px solid var(--line)}
.queue>header h2{margin:0;font-size:19px;font-weight:600}
.queue ol{margin:0;padding:8px 18px 12px 40px}
.queue li{margin:8px 0;padding-left:4px}
.queue li .t{font-weight:600}
.queue li .d{display:block}
.queue li .e{display:block;color:var(--subtle);font-size:13px}
.trust{border-top:3px solid var(--cobalt);padding:14px 0 0;font-size:13px;color:var(--subtle)}
.trust h2{font-size:14px;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px;color:var(--ink)}
.trust ul{margin:0;padding-left:20px}
.badge{display:inline-block;background:var(--ink);color:#fff;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:2px 8px}
details summary{cursor:pointer;color:var(--cobalt)}
details summary:focus-visible{outline:2px solid var(--citrus);outline-offset:2px}
@media (max-width:640px){.cover{grid-template-columns:1fr}.cover h1{font-size:24px}.ledger th,.ledger td{padding:6px 10px}.tbl{margin:12px 10px}.note,.warn,.statusnote,ul.bul{margin-left:10px;margin-right:10px}.ribbon div{min-width:50%}}
@media print{body{background:#fff}.wrap{padding:0}.module,.queue{border:0;border-top:1px solid var(--line)}thead{display:table-header-group}tr{page-break-inside:avoid}}
"""


def _change_html(pct: Decimal | None, permitted: bool, good: str) -> str:
    if not permitted or pct is None:
        return '<span class="dash" title="No approved comparison">—</span>'
    pct_val = pct * 100
    direction = 'flat'
    if pct_val > Decimal('0.05'):
        direction = 'up' if good in ('up', 'neutral') else 'down'
    elif pct_val < Decimal('-0.05'):
        direction = 'down' if good in ('up', 'neutral') else 'up'
    if good == 'neutral' and direction != 'flat':
        direction = 'flat'
    arrow = '▲' if pct_val > 0 else ('▼' if pct_val < 0 else '•')
    width = min(abs(pct_val), Decimal(100)) / Decimal(100) * 64
    width = max(Decimal(2), width)
    left = Decimal(32) if pct_val >= 0 else Decimal(32) - width / 2
    half = width / 2
    rail = f'<span class="rail" aria-hidden="true"><i style="left:{left if pct_val >= 0 else 32 - half:.1f}px;width:{half:.1f}px"></i></span>'
    sign = '+' if pct_val > 0 else ''
    return f'<span class="chg {direction}">{arrow} {sign}{_group_int(pct_val, 1)}% {rail}</span>'


def _ledger_html(kpis: list[dict], currency: str) -> str:
    if not kpis:
        return ''
    rows = ['<table class="ledger"><thead><tr><th>Metric</th><th class="num">Current</th><th class="num">Previous</th><th class="num">Change</th></tr></thead><tbody>']
    last_group = None
    for kpi in kpis:
        group = kpi.get('group')
        if group and group != last_group:
            rows.append(f'<tr class="group"><td colspan="4">{esc(group)}</td></tr>')
            last_group = group
        fmt = kpi.get('format', 'number')
        label = esc(kpi.get('label'))
        if kpi.get('note'):
            label += f'<small>{esc(kpi["note"])}</small>'
        cur = esc(fmt_value(kpi.get('value'), fmt, currency))
        prev = esc(fmt_value(kpi.get('previous'), fmt, currency)) if 'previous' in kpi else '<span class="dash">—</span>'
        change = _change_html(_pct_change_decimal(kpi.get('percent_change')), bool(kpi.get('change_permitted')),
                              kpi.get('good_direction', 'neutral'))
        rows.append(f'<tr><td class="lbl">{label}</td><td class="num">{cur}</td><td class="num">{prev}</td><td class="num">{change}</td></tr>')
    rows.append('</tbody></table>')
    return ''.join(rows)


def _bar_chart_svg(rows: list[dict], chart: dict, currency: str) -> str:
    label_key, value_key = chart['label_key'], chart['value_key']
    fmt = chart.get('format', 'number')
    points = []
    for row in rows:
        d = _to_decimal(row.get(value_key))
        if d is not None:
            points.append((str(row.get(label_key, '')), d))
    if not points:
        return ''
    n = len(points)
    vmax = max(d for _, d in points)
    vmin = min(d for _, d in points)
    top = max(vmax, Decimal(0))
    bottom = min(vmin, Decimal(0))
    span = (top - bottom) or Decimal(1)
    w, h, pad_l, pad_b, pad_t = max(480, 40 * n), 190, 8, 40, 10
    plot_h = h - pad_b - pad_t
    slot = (w - pad_l * 2) / n
    bar_w = max(4, slot * 0.62)
    label_every = max(1, int(-(-66 // slot)))  # ceil(66 / slot): keep 10px labels from overlapping
    zero_y = pad_t + float((top / span)) * plot_h
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(chart.get("title") or value_key)}" xmlns="http://www.w3.org/2000/svg">',
             f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{w - pad_l}" y2="{zero_y:.1f}" stroke="#D9DEE8"/>']
    for i, (label, d) in enumerate(points):
        x = pad_l + slot * i + (slot - bar_w) / 2
        bh = float(abs(d) / span) * plot_h
        y = zero_y - bh if d >= 0 else zero_y
        fill = '#2250F3' if d >= 0 else '#CD1230'
        title = f'{label}: {fmt_value(d, fmt, currency)}'
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(bh, 0.5):.1f}" fill="{fill}"><title>{esc(title)}</title></rect>')
        if i % label_every == 0:
            short = label if len(label) <= 11 else label[:10] + '…'
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{h - 22}" font-size="10" text-anchor="middle" fill="#525866">{esc(short)}</text>')
    parts.append(f'<text x="{pad_l}" y="{h - 3}" font-size="10" fill="#8A90A0">{esc(chart.get("caption") or f"{value_key} by {label_key}")}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def _hbar_chart_svg(rows: list[dict], chart: dict, currency: str) -> str:
    label_key, value_key = chart['label_key'], chart['value_key']
    fmt = chart.get('format', 'number')
    points = []
    for row in rows:
        d = _to_decimal(row.get(value_key))
        if d is not None:
            points.append((str(row.get(label_key, '')), d))
    if not points:
        return ''
    n = len(points)
    amax = max(abs(d) for _, d in points) or Decimal(1)
    has_neg = any(d < 0 for _, d in points)
    row_h, w, label_w, val_w = 22, 720, 230, 90
    h = row_h * n + 26
    plot_w = w - label_w - val_w - 16
    zero_x = label_w + 8 + (plot_w / 2 if has_neg else 0)
    scale = (plot_w / 2 if has_neg else plot_w) / float(amax)
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(chart.get("title") or value_key)}" xmlns="http://www.w3.org/2000/svg">',
             f'<line x1="{zero_x:.1f}" y1="4" x2="{zero_x:.1f}" y2="{h - 4}" stroke="#D9DEE8"/>']
    for i, (label, d) in enumerate(points):
        y = 6 + row_h * i
        bw = max(float(abs(d)) * scale, 1.0)
        x = zero_x if d >= 0 else zero_x - bw
        fill = '#23967F' if d >= 0 else '#CD1230'
        short = label if len(label) <= 34 else label[:33] + '…'
        parts.append(f'<text x="{label_w}" y="{y + 15}" font-size="11" text-anchor="end" fill="#181B25">{esc(short)}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y + 4}" width="{bw:.1f}" height="{row_h - 8}" fill="{fill}"><title>{esc(label)}: {esc(fmt_value(d, fmt, currency, signed=True))}</title></rect>')
        parts.append(f'<text x="{w - 4}" y="{y + 15}" font-size="11" text-anchor="end" fill="#525866">{esc(fmt_value(d, fmt, currency, signed=True))}</text>')
    parts.append(f'<text x="{label_w + 8}" y="{h - 5}" font-size="10" fill="#8A90A0">{esc(chart.get("caption") or f"{value_key} by {label_key}")}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def _table_html(table: dict, currency: str) -> str:
    columns = table.get('columns') or []
    rows = table.get('rows') or []
    parts = ['<div class="tbl">']
    if table.get('title'):
        parts.append(f'<h3>{esc(table["title"])}</h3>')
    if rows:
        parts.append('<table><thead><tr>')
        for col in columns:
            cls = ' class="num"' if col.get('format', 'text') not in ('text', 'date') else ''
            parts.append(f'<th{cls}>{esc(col.get("label") or col["key"])}</th>')
        parts.append('</tr></thead><tbody>')
        for row in rows:
            parts.append('<tr>')
            for col in columns:
                fmt = col.get('format', 'text')
                value = row.get(col['key'])
                text = fmt_value(value, fmt, currency, signed=bool(col.get('signed')))
                classes = []
                if fmt not in ('text', 'date'):
                    classes.append('num')
                    d = _to_decimal(value)
                    if col.get('signed') and d is not None:
                        classes.append('pos' if d > 0 else ('neg' if d < 0 else ''))
                cls = f' class="{" ".join(c for c in classes if c)}"' if classes else ''
                parts.append(f'<td{cls}>{esc(text)}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table>')
    else:
        parts.append('<p class="foot">No rows were returned for this table.</p>')
    chart = table.get('chart')
    if chart and rows:
        svg = _hbar_chart_svg(rows, chart, currency) if chart['type'] == 'hbar' else _bar_chart_svg(rows, chart, currency)
        if svg:
            parts.append(f'<div class="chart">{svg}</div>')
    if table.get('coverage'):
        parts.append(f'<p class="cov">Coverage: {esc(table["coverage"])}</p>')
    if table.get('footnote'):
        parts.append(f'<p class="foot">{esc(table["footnote"])}</p>')
    parts.append('</div>')
    return ''.join(parts)


def _section_html(section: dict, currency: str) -> str:
    status = section.get('status', 'ok')
    parts = ['<section class="module" id="' + esc(section['id']) + '"><header>',
             f'<h2>{esc(section["heading"])}</h2>']
    if section.get('source_label'):
        parts.append(f'<span class="src">{esc(section["source_label"])}</span>')
    if status != 'ok':
        parts.append(f'<span class="status {esc(status)}">{esc(status)}</span>')
    parts.append('</header>')
    if section.get('status_note'):
        parts.append(f'<p class="statusnote">{esc(section["status_note"])}</p>')
    elif status in ('unavailable', 'failed', 'skipped'):
        parts.append(f'<p class="statusnote">This section is {esc(status)} for this run.</p>')
    if section.get('analyst_note'):
        parts.append(f'<p class="note"><b>Analyst note</b> — {esc(section["analyst_note"])}</p>')
    for warning in section.get('warnings') or []:
        parts.append(f'<p class="warn">{esc(warning)}</p>')
    parts.append(_ledger_html(section.get('kpis') or [], currency))
    for table in section.get('tables') or []:
        parts.append(_table_html(table, currency))
    bullets = section.get('bullets') or []
    if bullets:
        parts.append('<ul class="bul">' + ''.join(f'<li>{esc(b)}</li>' for b in bullets) + '</ul>')
    if section.get('coverage'):
        parts.append(f'<p class="cov" style="margin:6px 18px 8px">Coverage: {esc(section["coverage"])}</p>')
    parts.append('</section>')
    return ''.join(parts)


def render_html(doc: dict, verified: bool, evidence_files: int) -> str:
    report = doc['report']
    account = report.get('account') or {}
    period = report.get('period') or {}
    currency = account.get('currency') or ''
    queue = doc.get('decision_queue') or []
    completeness = report.get('data_completeness') or 'complete'
    title = report['title']
    period_label = period.get('label') or f"{_pretty_date(period['start'])} – {_pretty_date(period['end'])}"
    parts = ['<!DOCTYPE html><html lang="' + esc(report.get('language') or 'en') + '"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{esc(title)} — {esc(account.get("display_name"))}</title>',
             f'<style>{CSS}</style></head><body><div class="wrap">']
    # Cover
    parts.append(f'<header class="cover"><div><div class="brand">{ATOM11_ICON}<div class="wordmark">Atom11</div></div>')
    parts.append(f'<h1 class="serif">{esc(title)}</h1>')
    sub = esc(account.get('display_name'))
    if account.get('system'):
        sub += f' · {esc(account["system"])}'
    if report.get('prepared_for'):
        sub += f' · Prepared for {esc(report["prepared_for"])}'
    parts.append(f'<p class="sub">{sub}</p></div><dl class="meta">')
    parts.append(f'<dt>Period</dt><dd>{esc(period_label)}</dd>')
    if period.get('previous_start') and period.get('previous_end'):
        parts.append(f'<dt>Compared with</dt><dd>{esc(_pretty_date(period["previous_start"]))} – {esc(_pretty_date(period["previous_end"]))}</dd>')
    if account.get('marketplace'):
        parts.append(f'<dt>Marketplace</dt><dd>{esc(account["marketplace"])}</dd>')
    if currency:
        parts.append(f'<dt>Currency</dt><dd>{esc(currency)}</dd>')
    if report.get('cadence'):
        parts.append(f'<dt>Cadence</dt><dd>{esc(report["cadence"])}</dd>')
    parts.append(f'<dt>Generated</dt><dd>{esc(_pretty_date(report["generated_on"]))}</dd></dl></header>')
    # Ribbon
    parts.append('<div class="ribbon">')
    parts.append(f'<div><div class="k">Data completeness</div><div class="v {"ok" if completeness == "complete" else "partial"}">{esc(completeness.capitalize())}</div></div>')
    parts.append(f'<div><div class="k">Decision queue</div><div class="v">{len(queue)} item{"" if len(queue) == 1 else "s"}</div></div>')
    for item in doc.get('status_items') or []:
        parts.append(f'<div><div class="k">{esc(item.get("label"))}</div><div class="v">{esc(item.get("value"))}</div></div>')
    parts.append('<div><div class="k">Mode</div><div class="v"><span class="badge">Read-only · review-only</span></div></div></div>')
    # Reading
    if report.get('verdict') or report.get('verdict_note'):
        parts.append('<section class="reading">')
        if report.get('verdict'):
            parts.append(f'<h2 class="serif">{esc(report["verdict"])}</h2>')
        if report.get('verdict_note'):
            parts.append(f'<p>{esc(report["verdict_note"])}</p>')
        parts.append('</section>')
    # Modules
    for section in doc['sections']:
        parts.append(_section_html(section, currency))
    # Decision queue
    parts.append('<section class="queue"><header><h2>Decision queue</h2></header>')
    if queue:
        parts.append('<ol>')
        for item in queue:
            parts.append(f'<li><span class="t">{esc(item.get("title"))}</span>')
            if item.get('detail'):
                parts.append(f'<span class="d">{esc(item["detail"])}</span>')
            if item.get('evidence'):
                parts.append(f'<span class="e">Evidence: {esc(item["evidence"])}</span>')
            parts.append('</li>')
        parts.append('</ol>')
    else:
        parts.append('<p class="statusnote">No review items were raised by the returned analyses.</p>')
    parts.append('</section>')
    # Trust notes
    notes = list(doc.get('trust_notes') or [])
    for line in doc.get('methodology') or []:
        notes.append(line)
    notes.append('This report is read-only and review-only: findings are prompts for a human decision, not changes made to the account.')
    if verified:
        notes.append(f'Every value and name in the tables and KPIs was verified against {evidence_files} raw Atom11 response file{"" if evidence_files == 1 else "s"} before rendering.')
    else:
        notes.append('Values in this report were NOT verified against evidence (rendered with --no-verify).')
    parts.append('<footer class="trust"><h2>Trust notes</h2><ul>' + ''.join(f'<li>{esc(n)}</li>' for n in notes) + '</ul></footer>')
    parts.append('</div></body></html>')
    return ''.join(parts)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--document', required=True, help='report document JSON')
    parser.add_argument('--evidence', nargs='*', default=[], help='raw MCP response JSON files or directories')
    parser.add_argument('--output', required=True, help='HTML output path')
    parser.add_argument('--no-verify', action='store_true', help='skip evidence verification (preview only)')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    try:
        with open(args.document, encoding='utf-8') as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'render error: cannot read document: {exc}', file=sys.stderr)
        return 2

    problems = validate_document(doc)
    if problems:
        print('document problems:', file=sys.stderr)
        for p in problems:
            print(f'  - {p}', file=sys.stderr)
        return 2
    id_problems = _scan_text_for_identifiers(doc)
    if id_problems:
        print('internal identifiers must not appear in a report:', file=sys.stderr)
        for p in id_problems:
            print(f'  - {p}', file=sys.stderr)
        return 2

    verified = False
    evidence_files = 0
    if not args.no_verify:
        try:
            evidence = load_evidence(args.evidence)
        except RenderError as exc:
            print(f'render error: {exc}', file=sys.stderr)
            return 2
        evidence_files = len(evidence.files)
        failures = verify_document(doc, evidence)
        if failures:
            print(f'{len(failures)} value(s) could not be verified against the evidence:', file=sys.stderr)
            for f in failures:
                print(f'  - {f}', file=sys.stderr)
            print('Fix the document (copy values exactly as returned); do not edit the evidence.', file=sys.stderr)
            return 2
        verified = True

    html_text = render_html(doc, verified, evidence_files)
    with open(args.output, 'w', encoding='utf-8') as fh:
        fh.write(html_text)
    if not args.quiet:
        n_kpis = sum(len(s.get('kpis') or []) for s in doc['sections'])
        n_tables = sum(len(s.get('tables') or []) for s in doc['sections'])
        print(f"rendered {args.output}: {len(doc['sections'])} sections, {n_kpis} KPIs, {n_tables} tables, "
              f"{len(doc.get('decision_queue') or [])} decision items; "
              f"{'verified against ' + str(evidence_files) + ' evidence file(s)' if verified else 'NOT verified'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
