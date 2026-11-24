#!/usr/bin/env python3
"""Render an Atom11 keyword_opportunities MCP response as offline-safe HTML."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable

# Atom11 icon, drawn as inline SVG so the report needs no image file.
ATOM11_ICON = (
    '<svg class="logo" viewBox="0 0 338 338" width="32" height="32" role="img" aria-label="Atom11">'
    '<rect width="338" height="338" rx="22" fill="#2250F3"/>'
    '<circle cx="126" cy="107.5" r="36" fill="#fff"/>'
    '<path d="M158 154.5A55.75 55.75 0 1 0 158 264Z" fill="#fff"/>'
    '<path d="M184 265V71.5A64 64 0 0 1 248 135.5V265Z" fill="#fff"/>'
    '</svg>'
)

NARRATIVE_MODULES = ("harvest", "waste")
GRAIN_LABELS = {
    "dashboard_row": "per Search Terms dashboard row",
    "term": "per aggregated search term",
}
PROFILE_LABELS = {
    "amazon_14d": (
        "Uniform 14-day attribution over SP + SB — an explicit analytical "
        "profile that can differ from dashboard values."
    ),
    "sp_7d": (
        "SP-only 7-day attribution — an explicit analytical profile that can "
        "differ from the multi-channel dashboards."
    ),
    "search_terms_dashboard": (
        "Search Terms dashboard reporting profile (dashboard parity)."
    ),
}
TOP_BARS = 10
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


def _percent(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number * 100:,.1f}%"


def _integer(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number:,.0f}"


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


def _messages(items: Iterable[Any]) -> list[str]:
    output: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("message") or item.get("note")
        else:
            value = item
        if value and str(value) not in output:
            output.append(str(value))
    return output


def _period(window: dict[str, Any] | None) -> str:
    window = window or {}
    start, end = window.get("start"), window.get("end")
    return f"{_escape(start)} – {_escape(end)}" if start and end else "Not supplied"


def _extract(payload: dict[str, Any]) -> tuple[dict, dict, dict, list, list]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], dict):
        raise ValueError("Input is not an Atom11 run_analysis response with outputs")
    summary = outputs[0]
    harvest = summary.get("harvest_candidates")
    waste = summary.get("negative_candidates")
    if not isinstance(harvest, dict) or not isinstance(waste, dict):
        raise ValueError("First output is not a keyword_opportunities summary bundle")
    recipe_id = payload.get("recipe_id")
    if recipe_id is not None and recipe_id != "keyword_opportunities":
        raise ValueError("Input analysis is not the keyword_opportunities recipe")
    harvest_rows = [r for r in outputs[1:] if r.get("section") == "harvest_candidates"]
    waste_rows = [r for r in outputs[1:] if r.get("section") == "negative_candidates"]
    return payload, harvest, waste, harvest_rows, waste_rows


def _source_label(row: dict[str, Any]) -> str:
    target = str(row.get("source_target") or "").strip()
    kind = str(row.get("source_kind") or "").strip()
    match = str(row.get("match") or "").strip()
    bits = [bit for bit in (target or None, kind or None, match or None) if bit]
    return " · ".join(bits) if bits else "—"


def _headline_tiles(harvest: dict[str, Any], waste: dict[str, Any], currency: str | None) -> str:
    """Counts and totals exactly as the summary blocks return them. Nothing is
    summed here, and the recipe returns no comparison period, so no tile
    carries a change arrow."""
    tiles = []

    def tile(label: str, value: Any, text: str, note: str) -> None:
        if _decimal(value) is None:
            return
        tiles.append(
            '<div class="tile">'
            f'<span class="micro">{_escape(label)}</span>'
            f"<strong>{_escape(text)}</strong>"
            f'<span class="tile-note">{_escape(note)}</span></div>'
        )

    shown = harvest.get("returned_source_terms")
    matching = harvest.get("matching_source_terms")
    tile(
        "Harvest candidates", matching, _integer(matching),
        "qualifying source terms"
        + (f" · {_integer(shown)} shown" if _decimal(shown) is not None else ""),
    )
    if (harvest.get("qualification") or {}).get("targeted_terms") == "exclude":
        excluded = harvest.get("already_targeted_excluded")
        tile(
            "Already-targeted excluded", excluded, _integer(excluded),
            "complete keyword check"
            if harvest.get("targeted_check_complete")
            else "bounded keyword check",
        )
    shown = waste.get("returned_search_term_groups")
    matching = waste.get("matching_search_term_groups")
    tile(
        "Zero-order terms", matching, _integer(matching),
        "qualifying terms"
        + (f" · {_integer(shown)} shown" if _decimal(shown) is not None else ""),
    )
    complete = waste.get("total_is_complete")
    tile(
        "Observed zero-order spend", waste.get("total_wasted_spend"),
        _money(waste.get("total_wasted_spend"), currency),
        "exact aggregate, all qualifying terms"
        if complete is True
        else "aggregate coverage is partial"
        if complete is False
        else "aggregate over qualifying terms",
    )
    if _decimal(shown) is None or _decimal(matching) is None:
        shown_note = "bounded detail rows only"
    elif _decimal(shown) == _decimal(matching):
        shown_note = "every qualifying term is shown"
    else:
        shown_note = f"top {_integer(shown)} of {_integer(matching)} by observed spend"
    tile(
        "Spend in shown terms", waste.get("returned_wasted_spend"),
        _money(waste.get("returned_wasted_spend"), currency), shown_note,
    )
    if not tiles:
        return ""
    return f'<section class="tiles" aria-label="Headline numbers">{"".join(tiles)}</section>'


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
    places = 0 if value == value.to_integral_value() else 2
    return f"{symbol}{value:,.{places}f}"


def _tick_count(value: Decimal) -> str:
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.1f}"


def _chart_scope(drawn: int, shown: int, matching: Any, noun: str) -> str:
    """How the drawn rows relate to the shown and qualifying lists, so a
    bounded list never reads as account-wide."""
    total = _decimal(matching)
    if drawn == shown:
        if total is None:
            return f"All {shown} shown {noun}"
        if total == shown:
            return f"All {shown} qualifying {noun}"
        return f"Top {shown} of {_integer(total)} qualifying {noun}"
    if total is not None and total == shown:
        return f"Top {drawn} of {shown} qualifying {noun}"
    text = f"Top {drawn} of {shown} shown {noun}"
    return text + (f" ({_integer(total)} qualify)" if total is not None else "")


def _top_bars(
    rows: list[dict[str, Any]],
    field: str,
    formatter: Callable[[Any], str],
    *,
    title: str,
    matching: Any,
    noun: str,
    tone: str,
    detail: Callable[[dict[str, Any]], str] | None = None,
) -> str:
    """The largest returned values of one field as horizontal bars, numbered
    like the table. Rows without a usable value are left out and counted in
    the caption, never drawn as zero."""
    usable = []
    for index, row in enumerate(rows, 1):
        value = _decimal(row.get(field))
        if value is not None and value >= 0:
            usable.append((index, row, value))
    if len(usable) < 2:
        return ""
    top = sorted(usable, key=lambda item: -item[2])[:TOP_BARS]
    maximum = top[0][2]
    if maximum <= 0:
        return ""
    items = []
    for index, row, value in top:
        sub = detail(row) if detail else ""
        items.append(
            '<li class="hbar">'
            f'<span class="hbar-rank">{index}</span>'
            f'<span class="hbar-label">{_escape(row.get("term") or "Unnamed search term")}'
            + (f"<small>{_escape(sub)}</small>" if sub and sub != "—" else "")
            + "</span>"
            f'<span class="hbar-track {tone}" aria-hidden="true">'
            f'<span style="width:{float(value / maximum) * 100:.1f}%"></span></span>'
            f'<span class="hbar-value">{_escape(formatter(row.get(field)))}</span></li>'
        )
    caption = _chart_scope(len(top), len(rows), matching, noun)
    missing = len(rows) - len(usable)
    if missing:
        caption += f" · {missing} without a usable value not drawn"
    return (
        '<figure class="chart">'
        f'<figcaption class="chart-head"><span class="micro">{_escape(title)}</span>'
        f'<span class="fine">{_escape(caption)} · numbers match the table</span></figcaption>'
        f'<ol class="hbars">{"".join(items)}</ol></figure>'
    )


def _label_spot(
    x: float, y: float, radius: float, text: str,
    dots: list[tuple[float, float]], taken: list[tuple[float, float, float, float]],
    frame: tuple[float, float, float, float],
) -> tuple[float, float]:
    """Where a dot's number goes (left edge, baseline): the first spot beside
    the dot whose box clears every other dot, earlier labels and the plot
    frame; the upper-right spot when none does."""
    width, height = 7.0 * len(text) + 2, 11.0
    near, far = x + radius + 2, x - radius - 2 - width
    spots = (
        (near, y - radius - height + 4), (far, y - radius - height + 4),
        (near, y + radius - 4), (far, y + radius - 4),
        (near, y - height / 2), (far, y - height / 2),
    )

    def clear(left: float, top: float) -> bool:
        right, bottom = left + width, top + height
        if left < frame[0] or top < frame[1] or right > frame[2] or bottom > frame[3]:
            return False
        for cx, cy in dots:
            nx, ny = min(max(cx, left), right), min(max(cy, top), bottom)
            if (cx - nx) ** 2 + (cy - ny) ** 2 < (radius + 1) ** 2:
                return False
        return all(
            right <= a or left >= c or bottom <= b or top >= d for a, b, c, d in taken
        )

    left, top = next((spot for spot in spots if clear(*spot)), spots[0])
    taken.append((left, top, left + width, top + height))
    return left, top + height - 2


def _click_spend_map(
    rows: list[dict[str, Any]], matching: Any, currency: str | None
) -> str:
    """Ad clicks against observed spend for the shown zero-order terms,
    numbered like the table. Every point has zero attributed orders; the
    chart separates many cheap clicks from a few expensive ones."""
    points = []
    for index, row in enumerate(rows, 1):
        clicks, spend = _decimal(row.get("ad_clicks")), _decimal(row.get("ad_spend"))
        if clicks is None or spend is None or clicks < 0 or spend < 0:
            continue
        points.append((index, row, clicks, spend))
    if len(points) < 2 or max(p[2] for p in points) <= 0 or max(p[3] for p in points) <= 0:
        return ""
    width, height, left, right, top, bottom = 520, 340, 58, 16, 14, 46
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
            f"{_escape(_tick_count(tick))}</text>"
        )
        tick += x_step
    tick = Decimal(0)
    while tick <= y_top:
        y = sy(tick)
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>'
            f'<text class="tick" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">'
            f"{_escape(_compact_money(tick, currency))}</text>"
        )
        tick += y_step
    parts.append(
        f'<text class="axis-label" x="{(left + width - right) / 2:.0f}" y="{height - 6}" '
        'text-anchor="middle">Ad clicks</text>'
        f'<text class="axis-label" transform="translate(14 {(top + height - bottom) / 2:.0f}) rotate(-90)" '
        'text-anchor="middle">Observed spend</text>'
    )
    radius = 6.0
    dots = [(sx(p[2]), sy(p[3])) for p in points]
    frame = (float(left), 0.0, float(width), float(height - bottom))
    taken: list[tuple[float, float, float, float]] = []
    for position, ((index, row, clicks, spend), (x, y)) in enumerate(zip(points, dots)):
        label = (
            f"{index}. {row.get('term') or 'Unnamed search term'}: "
            f"{_integer(clicks)} clicks, observed spend {_money(spend, currency)}, "
            "zero attributed orders"
        )
        others = dots[:position] + dots[position + 1:]
        lx, ly = _label_spot(x, y, radius, str(index), others, taken, frame)
        parts.append(
            f"<g><title>{_escape(label)}</title>"
            f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="{radius:.0f}"/>'
            f'<text class="dot-label" x="{lx:.1f}" y="{ly:.1f}">{index}</text></g>'
        )
    caption = _chart_scope(len(points), len(rows), matching, "terms")
    missing = len(rows) - len(points)
    if missing:
        caption += f" · {missing} without usable clicks or spend not drawn"
    return (
        '<figure class="chart">'
        '<figcaption class="chart-head"><span class="micro">Ad clicks against observed spend</span>'
        f'<span class="fine">{_escape(caption)} · every dot has zero attributed orders</span></figcaption>'
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Ad clicks against observed spend for {len(points)} shown zero-order terms">'
        f'{"".join(parts)}</svg>'
        '<p class="chart-note">Numbers match the table; hover a dot for its figures.</p></figure>'
    )


def _bar_cell(text: str, value: Any, maximum: Decimal, tone: str, width: int = 0) -> str:
    """A table value with a small bar scaled to the column's largest value. A
    missing value gets no bar, so it never reads as zero. `width` (characters,
    the column's longest value) keeps every bar in the column aligned."""
    number = _decimal(value)
    if number is None:
        return f'<td class="muted">{_escape(text)}</td>'
    share = 0.0 if number <= 0 or maximum <= 0 else min(float(number / maximum) * 100, 100.0)
    return (
        f'<td class="bar-cell"><span class="cell-bar {tone}" aria-hidden="true">'
        f'<span style="width:{share:.1f}%"></span></span>'
        f'<span class="cell-num" style="min-width:{width}ch">{_escape(text)}</span></td>'
    )


def _column_max(rows: list[dict[str, Any]], field: str) -> Decimal:
    values = [_decimal(row.get(field)) for row in rows]
    return max((value for value in values if value is not None), default=Decimal(0))


def _harvest_chart(rows: list[dict], harvest: dict[str, Any]) -> str:
    return _top_bars(
        rows,
        "ad_orders_attributed",
        _integer,
        title="Attributed orders by search term",
        matching=harvest.get("matching_source_terms"),
        noun="source terms",
        tone="teal",
        detail=_source_label,
    )


def _harvest_table(rows: list[dict], currency: str | None) -> str:
    if not rows:
        return (
            '<p class="empty">No search terms met the harvest qualification '
            "in this window.</p>"
        )
    max_orders = _column_max(rows, "ad_orders_attributed")
    max_sales = _column_max(rows, "ad_sales_attributed")
    orders = [_integer(row.get("ad_orders_attributed")) for row in rows]
    sales = [_money(row.get("ad_sales_attributed"), currency) for row in rows]
    orders_width, sales_width = max(map(len, orders)), max(map(len, sales))
    body = []
    for index, (row, order_text, sales_text) in enumerate(zip(rows, orders, sales), 1):
        body.append(
            "<tr>"
            f'<td class="rank">{index}</td>'
            f"<th>{_escape(row.get('term') or 'Unnamed search term')}</th>"
            f'<td class="source">{_escape(_source_label(row))}</td>'
            f"<td>{_escape(_integer(row.get('ad_clicks')))}</td>"
            f"<td>{_escape(_money(row.get('ad_spend'), currency))}</td>"
            f"{_bar_cell(order_text, row.get('ad_orders_attributed'), max_orders, 'teal', orders_width)}"
            f"{_bar_cell(sales_text, row.get('ad_sales_attributed'), max_sales, 'teal', sales_width)}"
            f"<td>{_escape(_percent(row.get('acos')))}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th class="rank">#</th><th>Customer search term</th><th>Source target</th><th>Clicks</th>'
        "<th>Spend</th><th>Orders</th><th>Attributed Sales</th><th>ACOS</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _harvest_meta(harvest: dict[str, Any]) -> str:
    qualification = harvest.get("qualification") or {}
    bits = [
        f"≥ {_integer(qualification.get('minimum_orders'))} attributed orders",
        f"≥ {_integer(qualification.get('minimum_clicks'))} clicks",
    ]
    max_acos = qualification.get("maximum_acos_percent")
    if max_acos is not None:
        bits.append(f"ACOS below {_integer(max_acos)}%")
    if qualification.get("targeted_terms") == "exclude":
        excluded = _integer(harvest.get("already_targeted_excluded"))
        check = (
            "complete"
            if harvest.get("targeted_check_complete")
            else "bounded"
        )
        bits.append(
            f"{excluded} already-targeted terms excluded ({check} keyword check)"
        )
    else:
        bits.append("terms already running as keywords are included")
    returned = harvest.get("returned_source_terms")
    matching = harvest.get("matching_source_terms")
    coverage = ""
    if returned is not None and matching is not None:
        coverage = (
            f"{_integer(returned)} of {_integer(matching)} qualifying source "
            "terms shown, most orders first."
        )
    scope = f"{harvest.get('ad_scope') or ''}".strip()
    line = " · ".join(bit for bit in bits if bit)
    return (
        f'<p class="scope-line">Qualification: {_escape(line)}.'
        + (f" Scope: {_escape(scope)}." if scope else "")
        + (f" {_escape(coverage)}" if coverage else "")
        + "</p>"
    )


def _waste_module(waste: dict[str, Any], rows: list[dict], currency: str | None) -> str:
    qualification = waste.get("qualification") or {}
    click_rule = qualification.get("clicks") or {}
    operator = ">" if click_rule.get("operator") == "gt" else "≥"
    grain = GRAIN_LABELS.get(str(qualification.get("grain")), str(qualification.get("grain") or ""))
    max_spend = _column_max(rows, "ad_spend")
    spends = [_money(row.get("ad_spend"), currency) for row in rows]
    spend_width = max(map(len, spends), default=0)
    body = []
    for index, (row, spend_text) in enumerate(zip(rows, spends), 1):
        body.append(
            "<tr>"
            f'<td class="rank">{index}</td>'
            f"<th>{_escape(row.get('term') or 'Unnamed search term')}</th>"
            f"<td>{_escape(_integer(row.get('ad_clicks')))}</td>"
            f"{_bar_cell(spend_text, row.get('ad_spend'), max_spend, 'rose', spend_width)}"
            "</tr>"
        )
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        '<th class="rank">#</th><th>Search term</th><th>Ad Clicks</th><th>Observed Spend</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        if body
        else '<p class="empty">No search terms met the selected waste rule.</p>'
    )
    matching_terms = waste.get("matching_search_term_groups")
    charts = _top_bars(
        rows,
        "ad_spend",
        lambda value: _money(value, currency),
        title="Observed spend by search term",
        matching=matching_terms,
        noun="terms",
        tone="rose",
    ) + _click_spend_map(rows, matching_terms, currency)
    if charts:
        table = f'<div class="chart-grid">{charts}</div>{table}'
    total = _money(waste.get("total_wasted_spend"), currency)
    returned = waste.get("returned_search_term_groups")
    matching = waste.get("matching_search_term_groups")
    if returned is not None and matching is not None:
        detail = (
            f"{_integer(returned)} of {_integer(matching)} qualifying terms "
            "shown, highest observed spend first"
        )
    else:
        detail = (
            "Displayed term list is complete"
            if waste.get("detail_is_complete")
            else "Displayed term list is bounded"
        )
    completeness = (
        "Exact aggregate over the qualified population"
        if waste.get("total_is_complete", True)
        else "Aggregate coverage is partial"
    )
    scope_bits = " · ".join(
        str(bit) for bit in (waste.get("ad_scope"), grain) if bit
    )
    rule = f"{operator} {_integer(click_rule.get('value'))} clicks · zero attributed orders"
    return (
        '<div class="waste-summary">'
        '<div><span class="micro">Observed zero-order spend</span>'
        f"<strong>{_escape(total)}</strong></div>"
        '<div><span class="micro">Qualification</span>'
        f"<p>{_escape(rule)}</p>"
        f'<p class="fine">{_escape(scope_bits)}</p></div>'
        '<div><span class="micro">Coverage</span>'
        f"<p>{_escape(completeness)}</p>"
        f'<p class="fine">{_escape(detail)}</p></div>'
        f"</div>{table}"
    )


def _trust_notes(payload: dict[str, Any], harvest: dict, waste: dict) -> str:
    notes: list[str] = []
    profile = PROFILE_LABELS.get(str(waste.get("metric_profile")))
    if profile:
        notes.append(profile)
    for block in (harvest, waste):
        note = block.get("note")
        if note:
            notes.append(str(note))
    comparison_note = (waste.get("dashboard_comparison") or {}).get("note")
    if comparison_note:
        notes.append(str(comparison_note))
    notes.extend(_messages(payload.get("warnings", [])))
    if payload.get("result_coverage_completeness") == "partial":
        notes.append(
            "One or more bounded result sections are incomplete; claims are "
            "limited to returned rows."
        )
    notes.append(
        "Harvest and negative candidates are review queues. Adding keywords "
        "or negatives requires human relevance, overlap, and business-context "
        "review; nothing in this report was applied to the account."
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
    payload, harvest, waste, harvest_rows, waste_rows = _extract(payload)
    if not isinstance(narrative, dict):
        narrative = None
    scope = payload.get("scope") or {}
    account = account_name or scope.get("display_name") or "Selected Atom11 account"
    currency = scope.get("currency")
    marketplace = scope.get("marketplace") or "—"
    timezone_name = scope.get("timezone") or "—"
    window = (payload.get("params") or {}).get("date_range")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    completeness = str(payload.get("data_completeness") or "not stated").replace("_", " ")
    days = harvest.get("attribution_window_days")
    profile_cell = (
        f"{harvest.get('ad_scope') or '—'} · {_integer(days)}-day"
        if days is not None
        else str(harvest.get("ad_scope") or "—")
    )
    returned = harvest.get("returned_source_terms")
    matching = harvest.get("matching_source_terms")
    harvest_cell = (
        f"{_integer(returned)} of {_integer(matching)}"
        if returned is not None and matching is not None
        else "—"
    )
    waste_total = _money(waste.get("total_wasted_spend"), currency)

    reading = ""
    if narrative and (narrative.get("verdict") or narrative.get("verdict_note")):
        verdict = _escape(_clip(narrative.get("verdict") or "Search-term reading", _VERDICT_LIMIT))
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
<title>Atom11 Search-Term Opportunities — {_escape(account)}</title>
<style>
:root{{--ink:#181B25;--subtle:#525866;--line:#D9DEE8;--paper:#F7F4EA;--surface:#FFF;
--cobalt:#2250F3;--cobalt-soft:#E5EBFF;--citrus:#FFC01E;--citrus-soft:#FFF3C4;
--teal:#23967F;--teal-soft:#E1F4EF;--rose:#CD1230;--rose-soft:#FCE8EB;--radius:18px}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}}
.top-signal{{height:12px;background:linear-gradient(90deg,var(--cobalt) 0 68%,var(--citrus) 68%)}}
.page{{width:min(1120px,calc(100% - 32px));margin:28px auto 52px}}
.mast{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:18px 0 28px}}
.brand{{display:flex;align-items:center;gap:10px}} .brand .logo{{width:32px;height:32px;display:block}}
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
.table-wrap{{overflow:auto;border-top:2px solid var(--ink)}} table{{width:100%;border-collapse:collapse;font-size:13px;
font-variant-numeric:tabular-nums}} th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}} td.source{{text-align:left;color:var(--subtle);max-width:260px;
overflow:hidden;text-overflow:ellipsis}} thead th{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--subtle);
background:#FAFAF8}} tbody th{{font-weight:720;max-width:320px;overflow:hidden;text-overflow:ellipsis}}
td.rank,th.rank{{text-align:left;color:var(--subtle);width:32px;padding-right:0}} td.rank+th,th.rank+th{{text-align:left}}
td.muted{{color:var(--subtle)}}
.cell-bar{{display:inline-block;width:72px;height:8px;background:#EEF0F4;margin-right:10px;vertical-align:middle}}
.cell-bar>span{{display:block;height:100%}} .cell-bar.teal>span{{background:var(--teal)}} .cell-bar.rose>span{{background:var(--rose)}}
.cell-num{{display:inline-block;text-align:right}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);
border:1px solid var(--line);margin:0 0 22px;box-shadow:7px 7px 0 rgba(24,27,37,.06)}} .tile{{background:var(--surface);padding:16px 18px}}
.tile strong{{display:block;font-family:Georgia,"Times New Roman",serif;font-size:28px;font-weight:500;margin:4px 0 2px;
font-variant-numeric:tabular-nums}} .tile-note{{display:block;font-size:12px;color:var(--subtle)}}
.chart{{margin:0 0 22px;padding-top:12px;border-top:2px solid var(--ink)}} .chart svg{{width:100%;height:auto;display:block}}
.chart-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:0 30px;align-items:start}}
.chart-head{{display:block;margin:0 0 10px}} .chart-head .fine{{display:block;font-size:12px;margin-top:2px}}
.chart-note{{margin:6px 0 0;font-size:12px;color:var(--subtle)}}
.hbars{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:22px fit-content(45%) minmax(60px,1fr) auto;column-gap:12px}}
.hbar{{grid-column:1/-1;display:grid;grid-template-columns:22px minmax(0,1.3fr) minmax(60px,1fr) 76px;grid-template-columns:subgrid;
align-items:center;padding:5px 0;font-size:13px}} .hbar-rank{{color:var(--subtle);font-size:12px}}
.hbar-label{{font-weight:720;line-height:1.25;overflow-wrap:anywhere}} .hbar-label small{{display:block;font-weight:400;
font-size:11px;color:var(--subtle)}} .hbar-track{{height:14px;background:#EEF0F4}} .hbar-track>span{{display:block;height:100%}}
.hbar-track.teal>span{{background:var(--teal)}} .hbar-track.rose>span{{background:var(--rose)}}
.hbar-value{{text-align:right;font-weight:750;font-variant-numeric:tabular-nums;white-space:nowrap}}
.chart .grid{{stroke:#E6E9EF;stroke-width:1}} .chart .tick{{font-size:11px;fill:var(--subtle)}}
.chart .axis-label{{font-size:12px;font-weight:700;fill:var(--subtle)}}
.dot{{fill:var(--rose);fill-opacity:.45;stroke:var(--rose);stroke-width:1.5}} .dot-label{{font-size:11px;font-weight:800;fill:var(--ink)}}
.waste-summary{{display:grid;grid-template-columns:.8fr 1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);
margin-bottom:20px}} .waste-summary>div{{background:var(--surface);padding:20px}} .waste-summary strong{{font-family:Georgia,serif;
font-size:36px;font-weight:500;display:block;margin-top:6px}} .waste-summary p{{margin:6px 0 0;font-size:13px}}
.fine{{color:var(--subtle)}} .empty{{padding:18px;background:#F6F7F9;color:var(--subtle)}}
.trust{{background:var(--ink);color:white;border-radius:var(--radius);padding:34px;margin-top:30px}} .trust h2{{font-family:Georgia,serif;
font-size:30px;font-weight:500;margin:0 0 18px}} .trust ul{{columns:2;column-gap:38px;margin:0;padding-left:18px}}
.trust li{{break-inside:avoid;margin:0 0 11px;color:#D7DAE1;font-size:13px}} footer{{display:flex;justify-content:space-between;
gap:20px;color:var(--subtle);font-size:12px;padding:24px 4px}}
@media(max-width:760px){{.cover{{grid-template-columns:1fr}}.cover-main{{padding:34px 28px}}.stamp{{gap:28px}}
.status-ribbon{{grid-template-columns:1fr 1fr}}.status-ribbon>div:nth-child(3){{border-left:0;border-top:1px solid #3B3E48}}
.status-ribbon>div:nth-child(4){{border-top:1px solid #3B3E48}}.module{{padding:26px 20px}}.module-head{{grid-template-columns:1fr}}
.module-head p{{grid-column:1}}.tab{{grid-row:auto;margin-bottom:14px;width:max-content}}.waste-summary{{grid-template-columns:1fr}}
.trust ul{{columns:1}}.cell-bar{{width:40px;margin-right:8px}}}}
@media screen and (max-width:520px){{.hbars{{grid-template-columns:22px minmax(0,1fr) auto}}
.hbar{{grid-template-columns:22px minmax(0,1fr) auto;grid-template-columns:subgrid;row-gap:5px}}
.hbar-track{{grid-column:2/4;grid-row:2}}.hbar-value{{grid-column:3;grid-row:1}}.chart .tick{{font-size:15px}}
.chart .axis-label{{font-size:16px}}}}
@media print{{@page{{margin:14mm}}body{{background:white}}.top-signal{{display:none}}.page{{width:100%;margin:0}}
.module,.cover,.tiles{{box-shadow:none;break-inside:avoid}}tr,.chart,.hbar{{break-inside:avoid}}
.table-wrap{{overflow:visible}}table{{font-size:11px}}th,td{{padding:8px 5px}}
tbody th,td.source{{white-space:normal;max-width:none}}.cell-bar{{width:28px;margin-right:6px}}
.hbar-track>span,.cell-bar>span{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.trust{{background:white;color:var(--ink);border:1px solid var(--ink)}}.trust li{{color:var(--ink)}}}}
</style>
</head>
<body>
<div class="top-signal"></div>
<main class="page">
  <header class="mast">
    <div class="brand">{ATOM11_ICON}<div class="wordmark">ATOM11<i aria-hidden="true"></i></div></div>
    <div class="classification">Read-only · Client decision brief</div>
  </header>
  <section class="cover">
    <div class="cover-main">
      <span class="kicker">Sponsored Ads search terms</span>
      <h1>Search-term opportunities</h1>
      <p>Winning customer search terms to review for harvesting, and zero-order spend to review for negatives — from one reviewed analysis.</p>
    </div>
    <aside class="stamp">
      <dl>
        <div><dt>Account</dt><dd>{_escape(account)}</dd></div>
        <div><dt>Marketplace · Currency</dt><dd>{_escape(marketplace)} · {_escape(currency or '—')}</dd></div>
        <div><dt>Period</dt><dd>{_period(window)}</dd></div>
        <div><dt>Attribution profile</dt><dd>{_escape(profile_cell)}</dd></div>
      </dl>
      <small>Timezone: {_escape(timezone_name)}<br>Generated {_escape(generated)}</small>
    </aside>
  </section>
  <section class="status-ribbon" aria-label="Report status">
    <div><span class="micro">Data completeness</span><strong>{_escape(completeness.title())}</strong></div>
    <div><span class="micro">Harvest candidates</span><strong>{_escape(harvest_cell)}</strong></div>
    <div><span class="micro">Observed zero-order spend</span><strong>{_escape(waste_total)}</strong></div>
    <div><span class="micro">Action level</span><strong>Human review</strong></div>
  </section>
  {reading}
  {_headline_tiles(harvest, waste, currency)}
  <section class="module"><header class="module-head">
    <span class="tab teal">Harvest candidates</span>
    <h2>Terms that already convert</h2>
    <p>Customer search terms meeting the harvest qualification, with the exact source target that produced them — candidates for keyword or target review, never automatic adds.</p>
  </header>{_analyst_note(narrative, 'harvest')}{_harvest_meta(harvest)}{_harvest_chart(harvest_rows, harvest)}{_harvest_table(harvest_rows, currency)}</section>
  <section class="module"><header class="module-head">
    <span class="tab rose">Negative candidates</span>
    <h2>Observed spend with zero attributed orders</h2>
    <p>A relevance-review queue — not a list of automatic negatives or guaranteed savings.</p>
  </header>{_analyst_note(narrative, 'waste')}{_waste_module(waste, waste_rows, currency)}</section>
  <section class="trust">
    <h2>How to read this report</h2>
    <ul>{_trust_notes(payload, harvest, waste)}</ul>
  </section>
  <footer><span>Prepared with Atom11</span><span>Read-only analysis · Review relevance before adding keywords or negatives</span></footer>
</main>
</body>
</html>
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render an Atom11 keyword_opportunities response as HTML."
    )
    parser.add_argument("--input", required=True, help="Input JSON path, or - for stdin")
    parser.add_argument("--output", required=True, help="Destination HTML path")
    parser.add_argument("--account-name", help="Account display name")
    parser.add_argument(
        "--narrative",
        help=(
            "Optional analyst-narrative JSON path: {verdict, verdict_note, "
            "module_notes:{harvest, waste}}. Text is escaped and capped."
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
