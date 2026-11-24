#!/usr/bin/env python3
"""Render an Atom11 campaign_performance_review MCP response as HTML."""

from __future__ import annotations

import argparse
import base64
import html
import json
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "atom11-logo.png"


def brand_mark() -> str:
    """Atom11 logo for the report header, embedded so the file stays self-contained.

    Falls back to the text wordmark when the logo file is not beside the script.
    """
    try:
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    except OSError:
        return '<div class="wordmark">ATOM11<i aria-hidden="true"></i></div>'
    return f'<img class="logo" src="data:image/png;base64,{data}" alt="Atom11" width="144" height="32">'


NARRATIVE_MODULES = ("ranking", "movement")
RANK_LABELS = {
    "ad_sales_attributed": "attributed ad sales",
    "ad_spend": "ad spend",
}
STATUS_TAGS = {
    "new": ("New in window", "ok"),
    "disappeared": ("No current-window activity", "warn"),
    "unavailable": ("Comparison unavailable", "na"),
}
TARGET_STATUS_LABELS = {
    "above": "Above target",
    "within": "At or below target",
    "none": "No target",
}
PERIOD_METRICS = (
    ("ad_sales", "Attributed sales"),
    ("ad_spend", "Ad spend"),
)
_VERDICT_LIMIT = 120
_NOTE_LIMIT = 700
_MODULE_NOTE_LIMIT = 500


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _currency_symbol(code: str | None) -> str:
    return {
        "USD": "$", "INR": "₹", "GBP": "£", "EUR": "€", "JPY": "¥",
        "CAD": "C$", "AUD": "A$",
    }.get((code or "").upper(), f"{(code or '').upper()} " if code else "")


def _money(value: Any, currency: str | None) -> str:
    number = _decimal(value)
    if number is None:
        return "—"
    places = 0 if abs(number) >= 1000 else 2
    return f"{_currency_symbol(currency)}{number:,.{places}f}"


def _money_signed(value: Any, currency: str | None) -> str:
    number = _decimal(value)
    if number is None:
        return "—"
    sign = "+" if number > 0 else "−" if number < 0 else ""
    return f"{sign}{_money(abs(number), currency)}"


def _percent(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number * 100:,.1f}%"


def _points(value: Any) -> str:
    number = _decimal(value)
    if number is None:
        return "—"
    return f"{number * 100:+,.1f} pts"


def _multiple(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number:,.2f}×"


def _integer(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number:,.0f}"


def _pct_delta(value: Any, *, good_when_up: bool | None) -> str:
    delta = _decimal(value)
    if delta is None:
        return '<span class="delta muted">—</span>'
    if good_when_up is None:
        direction = "neutral"
    elif delta == 0:
        direction = "neutral"
    else:
        favorable = delta > 0 if good_when_up else delta < 0
        direction = "good" if favorable else "risk"
    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    sign = "+" if delta > 0 else ""
    return (
        f'<span class="delta {direction}">{arrow} '
        f"{sign}{delta * 100:,.1f}%</span>"
    )


def _clip(text: Any, limit: int) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _analyst_note(narrative: dict | None, module: str) -> str:
    notes = (narrative or {}).get("module_notes") or {}
    text = notes.get(module) if isinstance(notes, dict) else None
    if not text:
        return ""
    return (
        '<p class="analyst-note"><span class="micro">Analyst note</span>'
        f"{_escape(_clip(text, _MODULE_NOTE_LIMIT))}</p>"
    )


def _period(window: dict[str, Any] | None) -> str:
    window = window or {}
    start, end = window.get("start"), window.get("end")
    return f"{_escape(start)} – {_escape(end)}" if start and end else "Not supplied"


def _extract(payload: dict[str, Any]) -> tuple[dict, dict, list]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], dict):
        raise ValueError("Input is not an Atom11 run_analysis response with outputs")
    summary = outputs[0]
    if not summary.get("summary") or "ranked_by" not in summary:
        raise ValueError("First output is not a campaign_performance_review summary")
    recipe_id = payload.get("recipe_id")
    if recipe_id is not None and recipe_id != "campaign_performance_review":
        raise ValueError("Input analysis is not campaign_performance_review")
    return payload, summary, outputs[1:]


def _target_tag(row: dict[str, Any]) -> str:
    above = row.get("above_acos_threshold")
    threshold = row.get("acos_threshold")
    source = row.get("acos_threshold_source")
    if above is None or threshold is None:
        return '<span class="status-tag na">No target</span>'
    suffix = " (account avg)" if source == "account_average" else ""
    if above:
        return (
            f'<span class="status-tag warn-strong">Above {_percent(threshold)}'
            f"{_escape(suffix)}</span>"
        )
    return (
        f'<span class="status-tag ok">Within {_percent(threshold)}'
        f"{_escape(suffix)}</span>"
    )


def _target_status(row: dict[str, Any]) -> str:
    """The recipe's own target flag, bucketed exactly like the table tag."""
    above = row.get("above_acos_threshold")
    if above is None or row.get("acos_threshold") is None:
        return "none"
    return "above" if above else "within"


def _target_phrase(row: dict[str, Any]) -> str:
    status = _target_status(row)
    if status == "none":
        return "no target"
    threshold = _percent(row.get("acos_threshold"))
    reference = (
        f"the {threshold} account average"
        if row.get("acos_threshold_source") == "account_average"
        else f"its {threshold} campaign target"
    )
    return f"{'above' if status == 'above' else 'at or below'} {reference}"


def _headline_tiles(summary: dict[str, Any], rank_label: str) -> str:
    """Only figures the recipe's summary returned; nothing is summed or derived."""
    fallback = summary.get("missing_target_policy") == "account_average"
    candidates = (
        ("Matching campaigns", summary.get("matching_campaigns"), _integer,
         "ranked globally for the window"),
        ("Campaigns shown", summary.get("returned_campaigns"), _integer,
         f"top by {rank_label}"),
        ("Account average ACOS", summary.get("account_average_acos"), _percent,
         "stands in for missing targets" if fallback else "reference only; no target fallback"),
        ("Spend-growth threshold", summary.get("meaningful_change_percent"),
         lambda value: f"{_integer(value)}%", "for the meaningful spend growth flag"),
    )
    tiles = [
        '<div class="tile">'
        f'<span class="micro">{_escape(label)}</span>'
        f"<strong>{_escape(fmt(value))}</strong>"
        f'<span class="tile-note">{_escape(note)}</span></div>'
        for label, value, fmt, note in candidates
        if _decimal(value) is not None
    ]
    return f'<div class="tiles">{"".join(tiles)}</div>' if tiles else ""


def _axis(maximum: Decimal) -> tuple[Decimal, Decimal]:
    """A rounded axis top and tick step (1, 2, 2.5 or 5 × 10^n, about four ticks)."""
    raw = maximum / 4
    magnitude = Decimal(10) ** (len(str(int(raw))) - 1) if raw >= 1 else Decimal(1)
    step = next(
        magnitude * factor
        for factor in (Decimal(1), Decimal(2), Decimal("2.5"), Decimal(5), Decimal(10))
        if magnitude * factor >= raw
    )
    return step * (maximum / step).to_integral_value(rounding=ROUND_CEILING), step


def _compact_money(value: Decimal, currency: str | None) -> str:
    symbol = _currency_symbol(currency)
    if value >= 1_000_000:
        return f"{symbol}{value / 1_000_000:,.1f}m"
    if value >= 1000:
        return f"{symbol}{value / 1000:,.1f}k".replace(".0k", "k")
    return f"{symbol}{value:,.0f}"


def _campaign_map(summary: dict[str, Any], rows: list[dict], currency: str | None) -> str:
    """Spend against attributed sales for the returned campaigns, numbered like
    the tables. Colour is the recipe's own target flag; the dashed line is the
    account average ACOS the recipe returned, so points above it run below it."""
    points = []
    for index, row in enumerate(rows, 1):
        spend, sales = _decimal(row.get("ad_spend")), _decimal(row.get("ad_sales_attributed"))
        if spend is None or sales is None or spend < 0 or sales < 0:
            continue
        orders = _decimal(row.get("ad_orders_attributed"))
        points.append((index, row, spend, sales, orders if orders is not None and orders >= 0 else None))
    if len(points) < 2 or max(p[2] for p in points) <= 0 or max(p[3] for p in points) <= 0:
        return ""
    width, height, left, right, top, bottom = 640, 340, 64, 34, 24, 46
    x_top, x_step = _axis(max(p[2] for p in points))
    y_top, y_step = _axis(max(p[3] for p in points))

    def sx(value: Decimal) -> float:
        return left + float(value / x_top) * (width - left - right)

    def sy(value: Decimal) -> float:
        return height - bottom - float(value / y_top) * (height - top - bottom)

    parts = []
    tick = Decimal(0)
    while tick <= x_top:
        x = sx(tick)
        parts.append(
            f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - bottom}"/>'
            f'<text class="tick" x="{x:.1f}" y="{height - bottom + 16}" text-anchor="middle">'
            f"{_escape(_compact_money(tick, currency))}</text>"
        )
        tick += x_step
    tick = Decimal(0)
    while tick <= y_top:
        y = sy(tick)
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>'
            f'<text class="tick" x="{left - 8}" y="{y + 3:.1f}" text-anchor="end">'
            f"{_escape(_compact_money(tick, currency))}</text>"
        )
        tick += y_step
    parts.append(
        f'<text class="axis-label" x="{(left + width - right) / 2:.0f}" y="{height - 6}" '
        'text-anchor="middle">Ad spend</text>'
        f'<text class="axis-label" transform="translate(14 {(top + height - bottom) / 2:.0f}) rotate(-90)" '
        'text-anchor="middle">Attributed sales</text>'
    )
    acos = _decimal(summary.get("account_average_acos"))
    legend_line = ""
    if acos is not None and acos > 0:
        x_end = min(x_top, y_top * acos)
        parts.append(
            f'<line class="ref-line" x1="{sx(Decimal(0)):.1f}" y1="{sy(Decimal(0)):.1f}" '
            f'x2="{sx(x_end):.1f}" y2="{sy(x_end / acos):.1f}"/>'
        )
        legend_line = (
            f'<span><i class="sw ref"></i>Account average ACOS {_escape(_percent(acos))}: '
            "campaigns above the line run below it</span>"
        )
    max_orders = max((p[4] for p in points if p[4] is not None), default=Decimal(0))
    fallback_drawn = hollow_drawn = False
    for index, row, spend, sales, orders in sorted(points, key=lambda p: -(p[4] or 0)):
        radius = 5 + (13 * float((orders / max_orders).sqrt()) if orders and max_orders > 0 else 0)
        status = _target_status(row)
        classes = f"dot dot-{status}"
        if status != "none" and row.get("acos_threshold_source") == "account_average":
            classes += " dot-avg"
            fallback_drawn = True
        if orders is None:
            classes += " dot-hollow"
            hollow_drawn = True
        label = (
            f"{index}. {row.get('campaign') or 'Unnamed campaign'}: spend "
            f"{_money(spend, currency)}, attributed sales {_money(sales, currency)}, "
            f"orders {_integer(orders) if orders is not None else 'not returned'}, "
            f"ACOS {_percent(row.get('acos'))}, {_target_phrase(row)}"
        )
        x, y = sx(spend), sy(sales)
        parts.append(
            f'<g><title>{_escape(label)}</title>'
            f'<circle class="{classes}" cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"/>'
            f'<text class="dot-label" x="{x + radius + 2:.1f}" y="{y - radius + 4:.1f}">{index}</text></g>'
        )
    statuses = {_target_status(p[1]) for p in points}
    legend = [
        f'<span><i class="sw dot-sw st-{status}"></i>{_escape(label)}</span>'
        for status, label in TARGET_STATUS_LABELS.items()
        if status in statuses
    ]
    if fallback_drawn:
        legend.append(
            '<span><i class="sw dot-sw st-avg"></i>Dashed outline: no campaign '
            "target, flagged against the account average</span>"
        )
    if hollow_drawn:
        legend.append('<span><i class="sw dot-sw st-hollow"></i>Hollow: orders not returned</span>')
    legend.append("<span>Bubble size: attributed orders</span>")
    if legend_line:
        legend.append(legend_line)
    if len(points) < len(rows):
        legend.append(
            f"<span>{len(points)} of {len(rows)} shown campaigns drawn; the rest "
            "returned no spend or sales value</span>"
        )
    legend.append("<span>Numbers match the tables below</span>")
    return (
        '<figure class="chart">'
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Ad spend against attributed sales for {len(points)} returned campaigns">'
        f'{"".join(parts)}</svg>'
        f'<figcaption class="share-legend">{"".join(legend)}</figcaption></figure>'
    )


def _bar_cell(text: str, value: Any, maximum: Decimal, tone: str) -> str:
    number = _decimal(value)
    if number is None:
        return f"<td>{_escape(text)}</td>"
    share = 0.0 if number <= 0 or maximum <= 0 else min(float(number / maximum) * 100, 100.0)
    return (
        f'<td class="bar-cell"><span class="cell-bar {tone}" aria-hidden="true">'
        f'<span style="width:{share:.1f}%"></span></span>'
        f'<span class="cell-val">{_escape(text)}</span></td>'
    )


def _column_max(rows: list[dict[str, Any]], field: str) -> Decimal:
    values = [_decimal(row.get(field)) for row in rows]
    return max((value for value in values if value is not None), default=Decimal(0))


def _period_bars(summary: dict[str, Any], rows: list[dict], currency: str | None) -> str:
    """This comparison window against the previous one, per campaign. A row is
    drawn only when the recipe compared it like-for-like: comparison_status is
    present_both, its percent_change_permitted flag is true, and both windows
    returned values. Bars show returned values only; no delta is computed."""
    drawn = []
    left_out: dict[str, list[str]] = {}
    for index, row in enumerate(rows, 1):
        status = str(row.get("comparison_status") or "")
        values = {
            field: (
                _decimal(row.get(f"comparison_current_{field}")),
                _decimal(row.get(f"previous_{field}")),
            )
            for field, _ in PERIOD_METRICS
        }
        if status != "present_both":
            reason = STATUS_TAGS.get(status, STATUS_TAGS["unavailable"])[0].lower()
        elif row.get("percent_change_permitted") is not True:
            reason = "window not like-for-like"
        elif any(value is None or value < 0 for pair in values.values() for value in pair):
            reason = "values not returned"
        else:
            drawn.append((index, row, values))
            continue
        left_out.setdefault(reason, []).append(f"#{index}")
    if len(drawn) < 2:
        if left_out.get("window not like-for-like"):
            return (
                '<p class="scope-line">This-period against previous-period bars '
                "are left out: the comparison windows are not like-for-like.</p>"
            )
        return ""
    scales = {
        field: max(max(values[field]) for _, _, values in drawn)
        for field, _ in PERIOD_METRICS
    }
    body = []
    for index, row, values in drawn:
        name = row.get("campaign") or "Unnamed campaign"
        cells, hover = [], [f"{index}. {name}"]
        for field, label in PERIOD_METRICS:
            lines = []
            for tone, value in zip(("now", "prev"), values[field]):
                share = float(value / scales[field]) * 100 if scales[field] > 0 else 0.0
                lines.append(
                    f'<span class="pair-line {tone}"><span class="pair-bar">'
                    f'<span style="width:{share:.1f}%"></span></span>'
                    f'<span class="pair-val">{_escape(_money(value, currency))}</span></span>'
                )
            cells.append(f'<div class="pair-metric">{"".join(lines)}</div>')
            current, previous = values[field]
            hover.append(
                f"{label.lower()} {_money(current, currency)} this period, "
                f"{_money(previous, currency)} previous"
            )
        body.append(
            f'<div class="pair-row" title="{_escape("; ".join(hover))}">'
            f'<div class="pair-name"><span class="pair-rank">{index}</span>{_escape(name)}</div>'
            f'{"".join(cells)}</div>'
        )
    head = "".join(f'<span class="micro">{_escape(label)}</span>' for _, label in PERIOD_METRICS)
    coverage = f"{len(drawn)} of {len(rows)} shown campaigns compared like-for-like"
    if left_out:
        coverage += "; left out: " + "; ".join(
            f"{', '.join(numbers)} {reason}" for reason, numbers in left_out.items()
        )
    return (
        '<figure class="chart pairs" aria-label="This period against the previous '
        'period for campaigns compared like-for-like">'
        f'<div class="pair-head"><span></span>{head}</div>{"".join(body)}'
        '<figcaption class="share-legend">'
        f'<span><i class="sw now"></i>This period {_period(summary.get("comparison_date_range"))}</span>'
        f'<span><i class="sw prev"></i>Previous period {_period(summary.get("previous_comparison_date_range"))}</span>'
        f"<span>{_escape(coverage)}</span><span>Numbers match the tables</span>"
        "</figcaption></figure>"
    )


def _ranking_table(summary: dict, rows: list[dict], currency: str | None) -> str:
    if not rows:
        return '<p class="empty">No campaign rows were returned for this window.</p>'
    max_spend = _column_max(rows, "ad_spend")
    max_sales = _column_max(rows, "ad_sales_attributed")
    body = []
    for index, row in enumerate(rows, 1):
        body.append(
            "<tr>"
            f'<td class="rank">{index}</td>'
            f"<th>{_escape(row.get('campaign') or 'Unnamed campaign')}</th>"
            f"<td>{_escape(row.get('sponsored_type') or '—')}</td>"
            f"{_bar_cell(_money(row.get('ad_spend'), currency), row.get('ad_spend'), max_spend, 'cobalt')}"
            f"{_bar_cell(_money(row.get('ad_sales_attributed'), currency), row.get('ad_sales_attributed'), max_sales, 'teal')}"
            f"<td>{_escape(_integer(row.get('ad_orders_attributed')))}</td>"
            f"<td>{_escape(_percent(row.get('acos')))}</td>"
            f"<td>{_target_tag(row)}</td>"
            f"<td>{_escape(_multiple(row.get('roas')))}</td>"
            "</tr>"
        )
    return (
        f"{_campaign_map(summary, rows, currency)}"
        '<div class="table-wrap"><table><thead><tr>'
        '<th class="rank">#</th><th>Campaign</th><th>Type</th><th>Ad Spend</th><th>Attributed Sales</th>'
        "<th>Orders</th><th>ACOS</th><th>vs Target</th><th>ROAS</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _movement_tags(row: dict[str, Any]) -> str:
    tags = []
    status = str(row.get("comparison_status") or "")
    if status in STATUS_TAGS:
        label, tone = STATUS_TAGS[status]
        tags.append(f'<span class="status-tag {tone}">{_escape(label)}</span>')
    if row.get("largest_growth"):
        tags.append('<span class="status-tag ok">Largest growth</span>')
    if row.get("largest_shrink"):
        tags.append('<span class="status-tag warn-strong">Largest decline</span>')
    if row.get("meaningful_spend_increase"):
        tags.append('<span class="status-tag warn">Meaningful spend growth</span>')
    return " ".join(tags) if tags else '<span class="status-tag na">Present both windows</span>'


def _movement_table(summary: dict, rows: list[dict], currency: str | None) -> str:
    if not rows:
        return '<p class="empty">No comparison rows were returned.</p>'
    pct_ok = all(
        bool(row.get("percent_change_permitted")) for row in rows
    ) if rows else False
    body = []
    for index, row in enumerate(rows, 1):
        spend_pct = (
            _pct_delta(row.get("percent_change_ad_spend"), good_when_up=None)
            if pct_ok
            else '<span class="delta muted">—</span>'
        )
        sales_pct = (
            _pct_delta(row.get("percent_change_ad_sales"), good_when_up=True)
            if pct_ok
            else '<span class="delta muted">—</span>'
        )
        body.append(
            "<tr>"
            f'<td class="rank">{index}</td>'
            f"<th>{_escape(row.get('campaign') or 'Unnamed campaign')}</th>"
            f"<td>{_escape(_money_signed(row.get('delta_ad_spend'), currency))}</td>"
            f"<td>{spend_pct}</td>"
            f"<td>{_escape(_money_signed(row.get('delta_ad_sales'), currency))}</td>"
            f"<td>{sales_pct}</td>"
            f"<td>{_escape(_points(row.get('delta_acos')))}</td>"
            f"<td>{_movement_tags(row)}</td>"
            "</tr>"
        )
    notice = ""
    if not pct_ok:
        notice = (
            '<aside class="notice"><strong>Percent changes suppressed.</strong> '
            "At least one comparison window is incomplete, so period-over-"
            "period percentages are not like-for-like; absolute deltas are "
            "shown as returned.</aside>"
        )
    return (
        notice
        + _period_bars(summary, rows, currency)
        + '<div class="table-wrap"><table><thead><tr>'
        '<th class="rank">#</th><th>Campaign</th><th>Δ Spend</th><th>Δ Spend %</th><th>Δ Sales</th>'
        "<th>Δ Sales %</th><th>Δ ACOS</th><th>Flags</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _focus_cards(rows: list[dict], currency: str | None) -> str:
    growth = [row for row in rows if row.get("largest_growth")]
    shrink = [row for row in rows if row.get("largest_shrink")]
    above = [row for row in rows if row.get("above_acos_threshold")]
    above.sort(key=lambda row: _decimal(row.get("acos")) or Decimal(0), reverse=True)

    def card(tone: str, title: str, entries: list[dict], value) -> str:
        if not entries:
            return ""
        items = "".join(
            '<li><span class="focus-name">'
            f'{_escape(row.get("campaign") or "Unnamed campaign")}</span>'
            f'<span class="focus-value">{_escape(value(row))}</span></li>'
            for row in entries[:5]
        )
        return (
            f'<div class="focus-card {tone}"><h3>{_escape(title)}</h3>'
            f"<p>among returned campaigns</p><ul>{items}</ul></div>"
        )

    cards = (
        card("teal", "Largest sales growth", growth,
             lambda row: _money_signed(row.get("delta_ad_sales"), currency))
        + card("rose", "Largest sales decline", shrink,
               lambda row: _money_signed(row.get("delta_ad_sales"), currency))
        + card("citrus", "Above ACOS target", above,
               lambda row: _percent(row.get("acos")))
    )
    return f'<div class="focus-grid">{cards}</div>' if cards else ""


def _trust_notes(payload: dict, summary: dict) -> str:
    notes: list[str] = []
    if summary.get("note"):
        notes.append(str(summary["note"]))
    days = summary.get("attribution_window_days")
    scope = summary.get("ad_scope")
    if days is not None:
        notes.append(
            f"Metrics use a uniform {_integer(days)}-day attribution profile "
            f"over {scope or 'Sponsored Ads'} — an explicit analytical profile "
            "that can differ from dashboard values."
        )
    if summary.get("missing_target_policy") == "account_average":
        notes.append(
            "Campaigns without their own target ACoS are flagged against the "
            f"account average of {_percent(summary.get('account_average_acos'))} "
            "(marked 'account avg')."
        )
    elif summary.get("missing_target_policy") == "unavailable":
        notes.append(
            "Campaigns without their own target ACoS show 'No target'; no "
            "account-average fallback was requested."
        )
    if summary.get("meaningful_change_percent") is not None:
        notes.append(
            "'Meaningful spend growth' marks spend up at least "
            f"{_integer(summary.get('meaningful_change_percent'))}% versus the "
            "previous comparison window."
        )
    for warning in payload.get("warnings", []) or []:
        text = warning.get("message") if isinstance(warning, dict) else warning
        if text:
            notes.append(str(text))
    if payload.get("result_coverage_completeness") == "partial":
        notes.append(
            "One or more bounded result sections are incomplete; claims are "
            "limited to returned rows."
        )
    notes.append(
        "This review identifies campaigns for human assessment. It does not "
        "establish causes, profitability, or incrementality, and it authorizes "
        "no bid, budget, pause, or targeting change."
    )
    unique: list[str] = []
    for note in notes:
        if note not in unique:
            unique.append(note)
    return "".join(f"<li>{_escape(note)}</li>" for note in unique)


def render(
    payload: dict[str, Any],
    account_name: str | None = None,
    narrative: dict[str, Any] | None = None,
) -> str:
    payload, summary, rows = _extract(payload)
    if not isinstance(narrative, dict):
        narrative = None
    scope = payload.get("scope") or {}
    account = account_name or scope.get("display_name") or "Selected Atom11 account"
    currency = scope.get("currency")
    marketplace = scope.get("marketplace") or "—"
    timezone_name = scope.get("timezone") or "—"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    completeness = str(payload.get("data_completeness") or "not stated").replace("_", " ")
    returned = summary.get("returned_campaigns")
    matching = summary.get("matching_campaigns")
    campaigns_cell = (
        f"{_integer(returned)} of {_integer(matching)}"
        if returned is not None and matching is not None
        else "—"
    )
    above_count = sum(1 for row in rows if row.get("above_acos_threshold"))
    rank_label = RANK_LABELS.get(str(summary.get("ranked_by")), str(summary.get("ranked_by") or "—"))
    scope_line = (
        f"Top {_integer(returned)} of {_integer(matching)} campaigns by "
        f"{rank_label}. Attribution: {_integer(summary.get('attribution_window_days'))}-day, "
        f"{summary.get('ad_scope') or '—'}."
    )

    reading = ""
    if narrative and (narrative.get("verdict") or narrative.get("verdict_note")):
        verdict = _escape(_clip(narrative.get("verdict") or "Campaign reading", _VERDICT_LIMIT))
        note = narrative.get("verdict_note")
        note_html = f"<p>{_escape(_clip(note, _NOTE_LIMIT))}</p>" if note else ""
        reading = (
            '<section class="module reading"><header class="module-head">'
            '<span class="tab cobalt">Analyst reading</span>'
            f"<h2>{verdict}</h2>{note_html}</header></section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Atom11 Campaign Performance Review — {_escape(account)}</title>
<style>
:root{{--ink:#181B25;--subtle:#525866;--line:#D9DEE8;--paper:#F7F4EA;--surface:#FFF;
--cobalt:#2250F3;--cobalt-soft:#E5EBFF;--citrus:#FFC01E;--citrus-soft:#FFF3C4;
--teal:#23967F;--teal-soft:#E1F4EF;--rose:#CD1230;--rose-soft:#FCE8EB;--radius:18px}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}}
.top-signal{{height:12px;background:linear-gradient(90deg,var(--cobalt) 0 68%,var(--citrus) 68%)}}
.page{{width:min(1120px,calc(100% - 32px));margin:28px auto 52px}}
.mast{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:18px 0 28px}}
.mast .logo{{height:32px;width:auto;display:block}}
.wordmark{{font-weight:900;letter-spacing:.16em;font-size:20px}} .wordmark i{{display:inline-block;width:10px;height:10px;
background:var(--citrus);border-radius:50%;margin-left:3px}} .classification{{font-size:12px;font-weight:800;
letter-spacing:.1em;text-transform:uppercase;color:var(--subtle)}}
.cover{{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,.7fr);background:var(--surface);
border:1px solid var(--line);border-radius:28px;overflow:hidden}}
.cover-main{{padding:54px}} .kicker{{display:inline-block;color:var(--cobalt);font-size:12px;font-weight:800;
letter-spacing:.12em;text-transform:uppercase;margin-bottom:20px}} h1{{font-family:Georgia,"Times New Roman",serif;
font-size:clamp(38px,6vw,64px);font-weight:500;letter-spacing:-.045em;line-height:.98;margin:0;max-width:13ch}}
.cover-main>p{{font-size:18px;color:var(--subtle);max-width:55ch;margin:24px 0 0}}
.stamp{{background:var(--cobalt-soft);padding:42px 34px;display:flex;flex-direction:column;justify-content:space-between}}
.stamp dl{{margin:0;display:grid;gap:20px}} dt,.micro{{font-size:10px;font-weight:850;letter-spacing:.12em;
text-transform:uppercase;color:var(--subtle);display:block}} dd{{margin:4px 0 0;font-weight:750;font-variant-numeric:tabular-nums}}
.status-ribbon{{display:grid;grid-template-columns:repeat(4,1fr);margin:18px 0 44px;border:1px solid var(--ink);
background:var(--ink);color:white}} .status-ribbon>div{{padding:18px 20px;border-left:1px solid #3B3E48}}
.status-ribbon>div:first-child{{border-left:0}} .status-ribbon .micro{{color:#B8BECA}} .status-ribbon strong{{display:block;
font-size:19px;margin-top:4px;font-variant-numeric:tabular-nums}}
.module{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:34px;margin:0 0 22px;
box-shadow:7px 7px 0 rgba(24,27,37,.06)}} .module-head{{display:grid;grid-template-columns:170px 1fr;column-gap:24px;
align-items:start;margin-bottom:24px}} .module-head h2{{font-family:Georgia,"Times New Roman",serif;font-size:30px;
font-weight:500;line-height:1.1;letter-spacing:-.025em;margin:0}} .module-head p{{grid-column:2;color:var(--subtle);margin:8px 0 0}}
.tab{{grid-row:1/span 2;align-self:start;padding:9px 12px;border-left:8px solid;font-size:11px;font-weight:850;
letter-spacing:.08em;text-transform:uppercase}} .tab.cobalt{{background:var(--cobalt-soft);border-color:var(--cobalt)}}
.tab.citrus{{background:var(--citrus-soft);border-color:var(--citrus)}} .tab.teal{{background:var(--teal-soft);border-color:var(--teal)}}
.tab.rose{{background:var(--rose-soft);border-color:var(--rose)}}
.notice{{margin:0 0 20px;padding:14px 16px;background:var(--citrus-soft);border-left:6px solid var(--citrus);font-size:13px}}
.notice ul{{margin:7px 0 0;padding-left:18px}} .scope-line{{color:var(--subtle);font-size:13px;margin:0 0 12px}}
.analyst-note{{margin:0 0 20px;padding:12px 16px;background:var(--cobalt-soft);border-left:6px solid var(--cobalt);font-size:14px;line-height:1.55}}
.analyst-note .micro{{margin-bottom:3px}} .reading .module-head{{margin-bottom:0}}
.delta{{font-size:13px;font-weight:800}} .delta.good{{color:var(--teal)}}
.delta.risk{{color:var(--rose)}} .delta.neutral,.muted{{color:var(--subtle)}}
.table-wrap{{overflow:auto;border-top:2px solid var(--ink)}} table{{width:100%;border-collapse:collapse;font-size:13px;
font-variant-numeric:tabular-nums}} th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}} thead th{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--subtle);
background:#FAFAF8}} tbody th{{font-weight:720;max-width:300px;overflow:hidden;text-overflow:ellipsis}}
.status-tag{{display:inline-block;padding:3px 7px;background:#F0F2F7;font-size:11px}}
.status-tag.ok{{background:var(--teal-soft)}} .status-tag.warn{{background:var(--citrus-soft)}}
.status-tag.warn-strong{{background:var(--rose-soft)}} .status-tag.na{{background:#F0F2F7}}
.focus-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:22px}}
.focus-card{{border:1px solid var(--line);border-top:4px solid var(--line);padding:14px 16px;background:#FDFDFB}}
.focus-card.rose{{border-top-color:var(--rose)}} .focus-card.teal{{border-top-color:var(--teal)}} .focus-card.citrus{{border-top-color:var(--citrus)}}
.focus-card h3{{margin:0;font-size:13px}} .focus-card>p{{margin:2px 0 10px;font-size:11px;color:var(--subtle)}}
.focus-card ul{{list-style:none;margin:0;padding:0}} .focus-card li{{display:flex;justify-content:space-between;gap:10px;
padding:6px 0;border-bottom:1px solid #EFF1F4;font-size:12px}} .focus-card li:last-child{{border-bottom:0}}
.focus-name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.focus-value{{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:750}}
.empty{{padding:18px;background:#F6F7F9;color:var(--subtle)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);
border:1px solid var(--line);margin:0 0 26px}} .tile{{background:var(--surface);padding:16px 18px}}
.tile strong{{display:block;font-family:Georgia,"Times New Roman",serif;font-size:28px;font-weight:500;margin:4px 0 2px;
font-variant-numeric:tabular-nums}} .tile-note{{display:block;font-size:12px;color:var(--subtle)}}
.share-legend{{display:flex;flex-wrap:wrap;gap:6px 16px;margin:7px 0 0;font-size:12px;color:var(--subtle)}}
.sw{{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px}}
.sw.dot-sw{{border-radius:50%;border:1.5px solid}} .sw.st-above{{background:var(--rose);border-color:var(--rose)}}
.sw.st-within{{background:var(--teal);border-color:var(--teal)}} .sw.st-none{{background:var(--subtle);border-color:var(--subtle)}}
.sw.st-avg{{background:transparent;border:2px dashed var(--subtle)}} .sw.st-hollow{{background:transparent;border-color:var(--subtle)}}
.sw.ref{{height:0;border-top:2px dashed var(--ink);vertical-align:3px}}
.sw.now{{background:var(--cobalt)}} .sw.prev{{background:var(--cobalt);opacity:.35}}
.chart{{margin:0 0 22px;padding-top:12px;border-top:2px solid var(--ink)}} .chart svg{{width:100%;height:auto;display:block}}
.chart .grid{{stroke:#EFF1F4;stroke-width:1}} .chart .tick{{font-size:10px;fill:var(--subtle)}}
.chart .axis-label{{font-size:11px;font-weight:700;fill:var(--subtle)}}
.dot{{fill-opacity:.5;stroke-width:1.5}} .dot-above{{fill:var(--rose);stroke:var(--rose)}}
.dot-within{{fill:var(--teal);stroke:var(--teal)}} .dot-none{{fill:var(--subtle);stroke:var(--subtle)}}
.dot-avg{{fill-opacity:.22;stroke-width:2;stroke-dasharray:3 2}} .dot-hollow{{fill-opacity:0}}
.dot-label{{font-size:10px;font-weight:800;fill:var(--ink)}} .ref-line{{stroke:var(--ink);stroke-width:1.2;stroke-dasharray:5 4}}
.pair-head,.pair-row{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr) minmax(0,1fr);gap:6px 20px;align-items:center}}
.pair-head{{padding:0 0 6px;border-bottom:1px solid var(--line)}} .pair-row{{padding:9px 0;border-bottom:1px solid var(--line)}}
.pair-name{{font-size:13px;font-weight:720;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.pair-rank{{display:inline-block;min-width:24px;color:var(--subtle);font-weight:600}}
.pair-metric{{display:grid;gap:3px}} .pair-line{{display:grid;grid-template-columns:minmax(0,1fr) 76px;gap:8px;align-items:center;
font-size:12px;font-variant-numeric:tabular-nums}} .pair-val{{text-align:right}} .pair-line.prev .pair-val{{color:var(--subtle)}}
.pair-bar{{display:block;height:8px;background:#F0F2F7}} .pair-bar>span{{display:block;height:100%;background:var(--cobalt)}}
.pair-line.prev .pair-bar>span{{opacity:.35}} .pairs .share-legend{{margin-top:10px}}
.cell-bar{{display:inline-block;width:72px;height:8px;background:#F0F2F7;margin-right:10px;vertical-align:middle}}
.cell-bar>span{{display:block;height:100%}} .cell-val{{display:inline-block;min-width:4.8em}} .cell-bar.cobalt>span{{background:var(--cobalt)}} .cell-bar.teal>span{{background:var(--teal)}}
td.rank,th.rank{{text-align:left;color:var(--subtle);width:32px;padding-right:0}} td.rank+th,th.rank+th{{text-align:left}}
.trust{{background:var(--ink);color:white;border-radius:var(--radius);padding:34px;margin-top:30px}} .trust h2{{font-family:Georgia,serif;
font-size:30px;font-weight:500;margin:0 0 18px}} .trust ul{{columns:2;column-gap:38px;margin:0;padding-left:18px}}
.trust li{{break-inside:avoid;margin:0 0 11px;color:#D7DAE1;font-size:13px}} footer{{display:flex;justify-content:space-between;
gap:20px;color:var(--subtle);font-size:12px;padding:24px 4px}}
@media(max-width:760px){{.cover{{grid-template-columns:1fr}}.cover-main{{padding:34px 28px}}.stamp{{gap:28px}}
.status-ribbon{{grid-template-columns:1fr 1fr}}.status-ribbon>div:nth-child(3){{border-left:0;border-top:1px solid #3B3E48}}
.status-ribbon>div:nth-child(4){{border-top:1px solid #3B3E48}}.module{{padding:26px 20px}}.module-head{{grid-template-columns:1fr}}
.module-head p{{grid-column:1}}.tab{{grid-row:auto;margin-bottom:14px;width:max-content}}.focus-grid{{grid-template-columns:1fr}}
.trust ul{{columns:1}}.cell-bar{{width:40px}}.pair-head,.pair-row{{grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:14px}}
.pair-name{{grid-column:1/-1}}.pair-head>span:first-child{{display:none}}.pair-line{{grid-template-columns:minmax(0,1fr) 62px;gap:6px}}
.chart .tick{{font-size:17px}}.chart .axis-label{{font-size:18px}}.dot-label{{font-size:18px}}}}
@media print{{@page{{margin:14mm}}body{{background:white}}.top-signal{{display:none}}.page{{width:100%;margin:0}}
.module,.cover{{box-shadow:none;break-inside:avoid}}tr,.focus-card,.tiles,.pair-row,svg{{break-inside:avoid}}
.sw,.cell-bar>span,.pair-bar>span{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.table-wrap{{overflow:visible}}table{{font-size:10px}}th,td{{padding:7px 4px}}thead th{{font-size:8.5px;letter-spacing:.04em;white-space:normal}}
tbody th{{white-space:normal;max-width:170px}}.status-tag{{font-size:9.5px;padding:2px 5px}}.delta{{font-size:10px}}
.cell-bar{{width:28px;margin-right:5px}}.cell-val{{min-width:4.4em}}.trust{{background:white;color:var(--ink);border:1px solid var(--ink)}}
.trust li{{color:var(--ink)}}}}
</style>
</head>
<body>
<div class="top-signal"></div>
<main class="page">
  <header class="mast">
    {brand_mark()}
    <div class="classification">Read-only · Client decision brief</div>
  </header>
  <section class="cover">
    <div class="cover-main">
      <span class="kicker">Sponsored Ads campaigns</span>
      <h1>Campaign performance review</h1>
      <p>A bounded global campaign ranking with target-ACOS flags and equal-window movement — evidence for review, not a full-account export.</p>
    </div>
    <aside class="stamp">
      <dl>
        <div><dt>Account</dt><dd>{_escape(account)}</dd></div>
        <div><dt>Marketplace · Currency</dt><dd>{_escape(marketplace)} · {_escape(currency or '—')}</dd></div>
        <div><dt>Report window</dt><dd>{_period(summary.get('date_range'))}</dd></div>
        <div><dt>Compared with</dt><dd>{_period(summary.get('previous_comparison_date_range'))}</dd></div>
      </dl>
      <small>Timezone: {_escape(timezone_name)}<br>Generated {_escape(generated)}</small>
    </aside>
  </section>
  <section class="status-ribbon" aria-label="Review status">
    <div><span class="micro">Data completeness</span><strong>{_escape(completeness.title())}</strong></div>
    <div><span class="micro">Campaigns shown</span><strong>{_escape(campaigns_cell)}</strong></div>
    <div><span class="micro">Above ACOS target (shown)</span><strong>{above_count:,}</strong></div>
    <div><span class="micro">Action level</span><strong>Human review</strong></div>
  </section>
  {reading}
  <section class="module"><header class="module-head">
    <span class="tab cobalt">Ranked performance</span>
    <h2>The campaigns that matter most</h2>
    <p>Current-window performance for the top-ranked campaigns, each flagged against its own target ACoS where one exists.</p>
  </header>{_analyst_note(narrative, 'ranking')}{_headline_tiles(summary, rank_label)}<p class="scope-line">{_escape(scope_line)}</p>{_ranking_table(summary, rows, currency)}</section>
  <section class="module"><header class="module-head">
    <span class="tab teal">Movement</span>
    <h2>How the selected campaigns moved</h2>
    <p>Equal-window deltas restricted to the selected campaigns — growth and decline flags mark the extremes of this set only.</p>
  </header>{_analyst_note(narrative, 'movement')}{_movement_table(summary, rows, currency)}{_focus_cards(rows, currency)}</section>
  <section class="trust">
    <h2>How to read this review</h2>
    <ul>{_trust_notes(payload, summary)}</ul>
  </section>
  <footer><span>Prepared with Atom11</span><span>Read-only analysis · Verify goals and margins before acting</span></footer>
</main>
</body>
</html>
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render an Atom11 campaign_performance_review response as HTML."
    )
    parser.add_argument("--input", required=True, help="Input JSON path, or - for stdin")
    parser.add_argument("--output", required=True, help="Destination HTML path")
    parser.add_argument("--account-name", help="Account display name")
    parser.add_argument(
        "--narrative",
        help=(
            "Optional analyst-narrative JSON path: {verdict, verdict_note, "
            "module_notes:{ranking, movement}}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.input == "-":
        import sys

        payload = json.load(sys.stdin)
    else:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    narrative = None
    if args.narrative:
        try:
            with Path(args.narrative).open("r", encoding="utf-8") as handle:
                narrative = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"--narrative could not be read as JSON: {exc}")
    document = render(payload, account_name=args.account_name, narrative=narrative)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
