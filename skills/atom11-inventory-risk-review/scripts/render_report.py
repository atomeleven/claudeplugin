#!/usr/bin/env python3
"""Render Atom11 inventory-risk analyses (restock_priority,
campaign_out_of_stock_products, ad_group_low_stock_products) as one
offline-safe HTML brief. Each input is the exact run_analysis envelope."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

# Atom11 icon, drawn as inline SVG so the report needs no image file.
ATOM11_ICON = (
    '<svg class="logo" viewBox="0 0 338 338" width="32" height="32" role="img" aria-label="Atom11">'
    '<rect width="338" height="338" rx="22" fill="#2250F3"/>'
    '<circle cx="126" cy="107.5" r="36" fill="#fff"/>'
    '<path d="M158 154.5A55.75 55.75 0 1 0 158 264Z" fill="#fff"/>'
    '<path d="M184 265V71.5A64 64 0 0 1 248 135.5V265Z" fill="#fff"/>'
    '</svg>'
)

NARRATIVE_MODULES = ("restock", "campaign_oos", "ad_group_low")
STATUS_LABELS = {
    "out_of_stock": ("Out of stock", "warn-strong"),
    "low": ("Low stock", "warn"),
}
RESTOCK_TILES = (
    ("qualifying_products", "Qualifying products"),
    ("returned_products", "Products shown"),
)
CAMPAIGN_OOS_TILES = (
    ("matching_campaigns", "Campaigns"),
    ("matching_products", "Out-of-stock ASINs"),
    ("matching_campaign_product_pairs", "Campaign-ASIN pairs"),
)
AD_GROUP_LOW_TILES = (
    ("matching_ad_groups", "Ad groups"),
    ("matching_products", "Matching ASINs"),
    ("matching_ad_group_product_pairs", "Ad-group-ASIN pairs"),
)
BAR_TONES = {"out_of_stock": "oos", "low": "low"}
_CHART_ROW_LIMIT = 30
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


def _integer(value: Any) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number:,.0f}"


def _number(value: Any, places: int = 2) -> str:
    number = _decimal(value)
    return "—" if number is None else f"{number:,.{places}f}"


def _timestamp(value: Any) -> str:
    if not value:
        return "—"
    text = re.sub(r"\.\d+", "", str(value))
    return text.replace("T", " ").replace("+00:00", " UTC").replace("Z", " UTC")


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


def _status_tag(status: Any) -> str:
    label, tone = STATUS_LABELS.get(
        str(status or ""), (str(status or "—").replace("_", " ").title(), "na")
    )
    return f'<span class="status-tag {tone}">{_escape(label)}</span>'


def _guard_notice(guard: dict[str, Any] | None) -> str:
    guard = guard or {}
    excluded = int(guard.get("stale_rows_excluded") or 0) + int(
        guard.get("rows_without_timestamp_excluded") or 0
    )
    if guard.get("status") == "unverifiable_snapshot":
        return (
            '<aside class="notice" role="note"><strong>Coverage note</strong>'
            "<ul><li>Snapshot freshness could not be verified; rows were "
            "withheld rather than shown stale.</li></ul></aside>"
        )
    if excluded:
        return (
            '<aside class="notice" role="note"><strong>Coverage note</strong>'
            f"<ul><li>Excluded {excluded} row(s) older than the current "
            "snapshot window or missing a timestamp.</li></ul></aside>"
        )
    return ""


def _extract(payload: dict[str, Any] | None, recipe_id: str) -> tuple[dict, dict, list]:
    if payload is None:
        return {}, {}, []
    outputs = payload.get("outputs")
    if not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], dict):
        raise ValueError(f"{recipe_id}: input is not a run_analysis response")
    if not outputs[0].get("summary"):
        raise ValueError(f"{recipe_id}: first output row is not the summary")
    got = payload.get("recipe_id")
    if got is not None and got != recipe_id:
        raise ValueError(f"input is {got}, expected {recipe_id}")
    return payload, outputs[0], outputs[1:]


def _tiles(summary: dict, fields: tuple[tuple[str, str], ...]) -> str:
    """Headline counts exactly as the recipe's summary row returned them, plus
    the snapshot time they describe. Nothing here is summed or derived."""
    tiles = []
    for field, label in fields:
        value = _decimal(summary.get(field))
        if value is None:
            continue
        tiles.append(
            f'<div class="tile"><span class="micro">{_escape(label)}</span>'
            f"<strong>{_escape(_integer(value))}</strong></div>"
        )
    snapshot = (summary.get("freshness_guard") or {}).get("snapshot_as_of")
    tiles.append(
        '<div class="tile as-of"><span class="micro">Snapshot as of</span>'
        f"<strong>{_escape(_timestamp(snapshot) if snapshot else 'Not returned')}</strong></div>"
    )
    return f'<div class="tiles">{"".join(tiles)}</div>'


def _bar_cell(text: str, value: Any, scale: Decimal | None, tone: str) -> str:
    """A numeric cell with a small bar against the column scale. An unknown
    value gets no bar at all, so it never reads as zero."""
    number = _decimal(value)
    if scale is None or number is None:
        return f"<td>{_escape(text)}</td>"
    share = 0.0 if number <= 0 else min(float(number / scale) * 100, 100.0)
    return (
        f'<td class="bar-cell"><span class="cell-bar {tone}" aria-hidden="true">'
        f'<span style="width:{share:.1f}%"></span></span><span class="cell-num">{_escape(text)}</span></td>'
    )


def _column_max(rows: list[dict[str, Any]], field: str) -> Decimal:
    values = [_decimal(row.get(field)) for row in rows]
    return max((value for value in values if value is not None), default=Decimal(0))


def _bar_scale(rows: list[dict[str, Any]], field: str, ceiling: Any = None) -> Decimal | None:
    """The full-bar value for one table column (the returned ceiling when there
    is one, else the column maximum), or None when bars would mean nothing:
    fewer than two known values, or nothing above zero."""
    if sum(_decimal(row.get(field)) is not None for row in rows) < 2:
        return None
    scale = _decimal(ceiling) or _column_max(rows, field)
    return scale if scale > 0 else None


def _status_share(summary: dict, rows: list) -> str:
    """Out-of-stock vs low-stock split of the returned restock rows. Drawn only
    when every row states a known status; a bounded list is labelled as the
    rows shown, never as the whole account."""
    statuses = [row.get("stock_status") for row in rows]
    if len(statuses) < 2 or any(status not in STATUS_LABELS for status in statuses):
        return ""
    shown = len(statuses)
    qualifying = _decimal(summary.get("qualifying_products"))
    if summary.get("ranking_is_complete") is True and qualifying == shown:
        title = f"Stock status across all {shown} qualifying products"
    else:
        title = f"Stock status among the {shown} products shown"
        if qualifying is not None:
            title += f" (of {_integer(qualifying)} qualifying)"
    segments, legend = [], []
    for status, (label, _) in STATUS_LABELS.items():
        count = statuses.count(status)
        share = count / shown * 100
        if count:
            segments.append(
                f'<span class="share-seg st-{status}" style="width:{share:.2f}%"></span>'
            )
        legend.append(
            f'<span><i class="sw st-{status}"></i>{_escape(label)} {count} ({share:.1f}%)</span>'
        )
    return (
        f'<div class="share-block"><div class="share-row"><span class="micro">{_escape(title)}</span>'
        f'<div class="share-bar" role="img" aria-label="{_escape(title)}">{"".join(segments)}</div>'
        f'<p class="share-legend">{"".join(legend)}</p></div></div>'
    )


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


def _tick(value: Decimal) -> str:
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.1f}"


def _cover_chart(params: dict, summary: dict, rows: list) -> str:
    """One horizontal bar per returned restock product, in the table's order.
    Reference lines are the threshold and reorder target the run returned;
    a value the run did not return gets no line. Unknown cover is written as
    "Unknown" with no bar. Without a viewBox the x positions are percentages
    and text keeps its real size, so the chart stays legible at phone width."""
    plotted = rows[:_CHART_ROW_LIMIT]
    covers = [_decimal(row.get("days_of_cover")) for row in plotted]
    covers = [None if cover is None or cover < 0 else cover for cover in covers]
    known = [cover for cover in covers if cover is not None]
    if len(known) < 2 or max(known) <= 0:
        return ""
    refs = []
    for field, css, label in (
        ("max_days_of_cover", "max", "Max"),
        ("reorder_target_days", "target", "Target"),
    ):
        value = _decimal(params.get(field))
        if value is not None and value >= 0:
            refs.append((value, css, label))
    top, step = _axis(max(known + [value for value, _, _ in refs]))
    left, right, row_height, bar_height = 22.0, 88.0, 24, 14

    def sx(value: Decimal) -> float:
        return left + float(value / top) * (right - left)

    label_rows = [0] * len(refs)
    ordered = sorted(range(len(refs)), key=lambda i: refs[i][0])
    for previous, current in zip(ordered, ordered[1:]):
        if sx(refs[current][0]) - sx(refs[previous][0]) < 12:
            label_rows[current] = label_rows[previous] + 1
    head = 8 + (13 * (max(label_rows) + 1) if refs else 0)
    plot_bottom = head + len(plotted) * row_height
    height = plot_bottom + 26

    parts = []
    tick = Decimal(0)
    while tick <= top:
        x = sx(tick)
        unit = " days" if tick == top else ""
        parts.append(
            f'<line class="grid" x1="{x:.2f}%" y1="{head}" x2="{x:.2f}%" y2="{plot_bottom}"/>'
            f'<text class="tick" x="{x:.2f}%" y="{plot_bottom + 16}" text-anchor="middle">'
            f"{_escape(_tick(tick) + unit)}</text>"
        )
        tick += step
    for index, (row, cover) in enumerate(zip(plotted, covers)):
        middle = head + index * row_height + row_height / 2
        name = str(row.get("product") or "Unnamed product")
        status = row.get("stock_status")
        tone = BAR_TONES.get(status, "other")
        status_label = STATUS_LABELS.get(status, ("Status not stated", ""))[0]
        on_hand = row.get("on_hand_units")
        on_hand_text = "unknown" if _decimal(on_hand) is None else _integer(on_hand)
        if cover is None:
            bar, end = "", left
            value_text = "Unknown"
            hover = f"{name} — {status_label}: days of cover unknown; on hand {on_hand_text}"
        else:
            end = sx(cover)
            bar = (
                f'<rect class="bar {tone}" x="{left:.2f}%" y="{middle - bar_height / 2:.1f}" '
                f'width="{end - left:.2f}%" height="{bar_height}"/>'
            )
            value_text = _number(cover, 1) + (" · out of stock" if status == "out_of_stock" else "")
            hover = (
                f"{name} — {status_label}: {_number(cover, 1)} days of cover; "
                f"on hand {on_hand_text}"
            )
        parts.append(
            f"<g><title>{_escape(hover)}</title>"
            f'<text class="bar-label" x="{left - 1.5:.2f}%" y="{middle + 4:.1f}" text-anchor="end">'
            f"{_escape(_clip(name, 14))}</text>{bar}"
            f'<text class="bar-value {tone if cover is not None else "unknown"}" x="{end:.2f}%" dx="5" '
            f'y="{middle + 4:.1f}">{_escape(value_text)}</text></g>'
        )
    legend = []
    for status in dict.fromkeys(row.get("stock_status") for row in plotted):
        label = STATUS_LABELS.get(status, ("Status not stated", ""))[0]
        legend.append(f'<span><i class="sw st-{BAR_TONES.get(status, "other")}"></i>{_escape(label)}</span>')
    for (value, css, label), label_row in zip(refs, label_rows):
        x = sx(value)
        y = 17 + 13 * label_row
        parts.append(
            f'<line class="ref-line {css}" x1="{x:.2f}%" y1="{y + 3}" x2="{x:.2f}%" y2="{plot_bottom}"/>'
            f'<text class="ref-label {css}" x="{x:.2f}%" y="{y}" text-anchor="middle">'
            f"{_escape(label)} {_escape(_tick(value))}</text>"
        )
        legend.append(
            f'<span><i class="sw ref {css}"></i>'
            + (
                f"Max days of cover: {_escape(_tick(value))}"
                if css == "max"
                else f"Reorder target: {_escape(_tick(value))} days"
            )
            + "</span>"
        )
    legend.append("<span>Lowest cover first, same order as the table</span>")
    if len(rows) > len(plotted):
        legend.append(
            f"<span>Chart shows the first {len(plotted)} of the {len(rows)} rows "
            "returned; the table lists all</span>"
        )
    snapshot = (summary.get("freshness_guard") or {}).get("snapshot_as_of")
    if snapshot:
        legend.append(f"<span>As of {_escape(_timestamp(snapshot))}</span>")
    return (
        '<figure class="chart bars">'
        f'<svg width="100%" height="{height}" role="img" '
        f'aria-label="Days of cover for {len(plotted)} restock products shown">'
        f'{"".join(parts)}</svg>'
        f'<figcaption class="share-legend">{"".join(legend)}</figcaption></figure>'
    )


def _restock_module(payload: dict, summary: dict, rows: list, narrative: dict | None) -> str:
    if not summary:
        return ""
    params = payload.get("params") or {}
    reorder_scale = _bar_scale(rows, "recommended_reorder_quantity")
    body = []
    for row in rows:
        reorder = row.get("recommended_reorder_quantity")
        body.append(
            "<tr>"
            f"<th>{_escape(row.get('product') or 'Unnamed product')}</th>"
            f"<td>{_status_tag(row.get('stock_status'))}</td>"
            f"<td>{_escape(_integer(row.get('on_hand_units')))}</td>"
            f"<td>{_escape(_number(row.get('daily_sales_velocity')))}</td>"
            f"<td>{_escape(_number(row.get('days_of_cover'), 1))}</td>"
            f"{_bar_cell(_integer(reorder), reorder, reorder_scale, 'cobalt')}"
            f"<td>{_escape(_timestamp(row.get('updated_at_utc')))}</td>"
            "</tr>"
        )
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Product</th><th>Status</th><th>On hand</th><th>Daily velocity</th>"
        "<th>Days of cover</th><th>Suggested reorder qty</th><th>Updated</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        if body
        else '<p class="empty">No current qualifying restock risks were returned.</p>'
    )
    scope = (
        f"Showing {_integer(summary.get('returned_products'))} of "
        f"{_integer(summary.get('qualifying_products'))} qualifying products, "
        "lowest days of cover first."
    )
    threshold = params.get("max_days_of_cover")
    target = params.get("reorder_target_days")
    if threshold is not None:
        scope += (
            f" Filter: sales velocity above zero, at most {_integer(threshold)} "
            "days of cover."
        )
    if target is not None:
        scope += (
            f" Reorder quantities close a {_integer(target)}-day demand gap."
        )
    return (
        '<section class="module"><header class="module-head">'
        '<span class="tab rose">Restock priority</span>'
        "<h2>Products closest to stock-out</h2>"
        "<p>A current as-of run-rate watchlist — not historical inventory for any date range.</p>"
        f"</header>{_analyst_note(narrative, 'restock')}{_guard_notice(summary.get('freshness_guard'))}"
        f"{_tiles(summary, RESTOCK_TILES)}"
        f'<p class="scope-line">{_escape(scope)}</p>'
        f"{_status_share(summary, rows)}{_cover_chart(params, summary, rows)}{table}</section>"
    )


def _campaign_oos_module(payload: dict, summary: dict, rows: list, narrative: dict | None) -> str:
    if not summary:
        return ""
    ads_scale = _bar_scale(rows, "enabled_product_ads")
    body = []
    for row in rows:
        ads = row.get("enabled_product_ads")
        body.append(
            "<tr>"
            f"<th>{_escape(row.get('campaign') or 'Unnamed campaign')}</th>"
            f"<td>{_escape(row.get('sponsored_type') or '—')}</td>"
            f"<td>{_escape(row.get('product') or '—')}</td>"
            f"<td>{_escape(_integer(row.get('on_hand_units')))}</td>"
            f"{_bar_cell(_integer(ads), ads, ads_scale, 'cobalt')}"
            f"<td>{_escape(_timestamp(row.get('inventory_updated_at_utc')))}</td>"
            "</tr>"
        )
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Campaign</th><th>Type</th><th>Advertised ASIN</th><th>On hand</th>"
        "<th>Enabled product ads</th><th>Inventory updated</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        if body
        else '<p class="empty">No enabled campaigns are advertising a currently out-of-stock ASIN.</p>'
    )
    scope = f"Scope: {summary.get('scope') or 'enabled product ads'}."
    if not summary.get("is_complete", True):
        scope += " Bounded inputs continued; this is an honest partial set."
    return (
        '<section class="module"><header class="module-head">'
        '<span class="tab citrus">Ads on empty shelves</span>'
        "<h2>Campaigns advertising out-of-stock ASINs</h2>"
        "<p>Enabled product ads whose advertised ASIN currently has zero sellable on-hand units.</p>"
        f"</header>{_analyst_note(narrative, 'campaign_oos')}{_guard_notice(summary.get('freshness_guard'))}"
        f"{_tiles(summary, CAMPAIGN_OOS_TILES)}"
        f'<p class="scope-line">{_escape(scope)}</p>{table}</section>'
    )


def _ad_group_low_module(payload: dict, summary: dict, rows: list, narrative: dict | None) -> str:
    if not summary:
        return ""
    # A full cover bar means "at the returned threshold".
    cover_scale = _bar_scale(rows, "days_of_cover", summary.get("max_days_of_cover"))
    ads_scale = _bar_scale(rows, "enabled_product_ads")
    body = []
    for row in rows:
        cover, ads = row.get("days_of_cover"), row.get("enabled_product_ads")
        body.append(
            "<tr>"
            f"<th>{_escape(row.get('ad_group') or 'Unnamed ad group')}</th>"
            f"<td>{_escape(row.get('campaign') or '—')}</td>"
            f"<td>{_escape(row.get('sponsored_type') or '—')}</td>"
            f"<td>{_escape(row.get('product') or '—')}</td>"
            f"<td>{_status_tag(row.get('stock_status'))}</td>"
            f"<td>{_escape(_integer(row.get('on_hand_units')))}</td>"
            f"{_bar_cell(_number(cover, 1), cover, cover_scale, 'citrus')}"
            f"{_bar_cell(_integer(ads), ads, ads_scale, 'cobalt')}"
            "</tr>"
        )
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Ad group</th><th>Campaign</th><th>Type</th><th>ASIN</th>"
        "<th>Status</th><th>On hand</th><th>Days of cover</th><th>Enabled ads</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
        if body
        else '<p class="empty">No enabled ad groups are advertising a low-stock ASIN under the selected threshold.</p>'
    )
    scope = (
        "Threshold: positive velocity with under "
        f"{_integer(summary.get('max_days_of_cover'))} days of cover "
        "(zero stock always included)."
    )
    if not summary.get("is_complete", True):
        scope += " Bounded inputs continued; this is an honest partial set."
    return (
        '<section class="module"><header class="module-head">'
        '<span class="tab teal">Low-stock exposure</span>'
        "<h2>Ad groups advertising products running low</h2>"
        "<p>Enabled product ads on selling ASINs whose current cover sits under the review threshold.</p>"
        f"</header>{_analyst_note(narrative, 'ad_group_low')}{_guard_notice(summary.get('freshness_guard'))}"
        f"{_tiles(summary, AD_GROUP_LOW_TILES)}"
        f'<p class="scope-line">{_escape(scope)}</p>{table}</section>'
    )


def _trust_notes(bundles: list[tuple[dict, dict]]) -> str:
    notes: list[str] = []
    for payload, summary in bundles:
        if not summary:
            continue
        note = summary.get("note")
        if note:
            notes.append(str(note))
        for warning in payload.get("warnings", []) or []:
            text = warning.get("message") if isinstance(warning, dict) else warning
            if text:
                notes.append(str(text))
        if payload.get("result_coverage_completeness") == "partial":
            notes.append(
                "One or more bounded inputs are incomplete; claims are limited "
                "to returned rows."
            )
    notes.append(
        "All figures are current as-of snapshots. Verify live and inbound "
        "inventory before pausing, scaling, or continuing advertising; null "
        "on-hand quantities are unknown, not zero."
    )
    unique: list[str] = []
    for note in notes:
        if note not in unique:
            unique.append(note)
    return "".join(f"<li>{_escape(note)}</li>" for note in unique)


def render(
    restock: dict[str, Any] | None,
    campaign_oos: dict[str, Any] | None,
    ad_group_low: dict[str, Any] | None,
    account_name: str | None = None,
    narrative: dict[str, Any] | None = None,
) -> str:
    if restock is None and campaign_oos is None and ad_group_low is None:
        raise ValueError("At least one analysis input is required")
    if not isinstance(narrative, dict):
        narrative = None
    r_payload, r_summary, r_rows = _extract(restock, "restock_priority")
    c_payload, c_summary, c_rows = _extract(campaign_oos, "campaign_out_of_stock_products")
    a_payload, a_summary, a_rows = _extract(ad_group_low, "ad_group_low_stock_products")
    scope = (
        (r_payload or c_payload or a_payload).get("scope") or {}
    )
    account = account_name or scope.get("display_name") or "Selected Atom11 account"
    marketplace = scope.get("marketplace") or "—"
    currency = scope.get("currency") or "—"
    timezone_name = scope.get("timezone") or "—"
    snapshot = (
        ((r_summary.get("freshness_guard") or {}).get("snapshot_as_of"))
        if r_summary
        else None
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    restock_cell = (
        f"{_integer(r_summary.get('returned_products'))} of "
        f"{_integer(r_summary.get('qualifying_products'))}"
        if r_summary
        else "Not run"
    )
    oos_cell = (
        _integer(c_summary.get("matching_campaign_product_pairs"))
        if c_summary
        else "Not run"
    )
    low_cell = (
        _integer(a_summary.get("matching_ad_group_product_pairs"))
        if a_summary
        else "Not run"
    )

    reading = ""
    if narrative and (narrative.get("verdict") or narrative.get("verdict_note")):
        verdict = _escape(_clip(narrative.get("verdict") or "Inventory reading", _VERDICT_LIMIT))
        note = narrative.get("verdict_note")
        note_html = f"<p>{_escape(_clip(note, _NOTE_LIMIT))}</p>" if note else ""
        reading = (
            '<section class="module reading"><header class="module-head">'
            '<span class="tab cobalt">Analyst reading</span>'
            f"<h2>{verdict}</h2>{note_html}</header></section>"
        )

    modules = (
        _restock_module(r_payload, r_summary, r_rows, narrative)
        + _campaign_oos_module(c_payload, c_summary, c_rows, narrative)
        + _ad_group_low_module(a_payload, a_summary, a_rows, narrative)
    )
    missing = []
    if not r_summary:
        missing.append("restock priority")
    if not c_summary:
        missing.append("campaigns on out-of-stock ASINs")
    if not a_summary:
        missing.append("ad groups on low stock")
    missing_note = ""
    if missing:
        missing_note = (
            '<aside class="notice"><strong>Not included in this run:</strong> '
            f"{_escape(', '.join(missing))}.</aside>"
        )
    bundles = [(r_payload, r_summary), (c_payload, c_summary), (a_payload, a_summary)]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Atom11 Inventory Risk Review — {_escape(account)}</title>
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
font-size:clamp(38px,6vw,64px);font-weight:500;letter-spacing:-.045em;line-height:.98;margin:0;max-width:12ch}}
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
th:first-child,td:first-child{{text-align:left}} thead th{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--subtle);
background:#FAFAF8}} tbody th{{font-weight:720;max-width:300px;overflow:hidden;text-overflow:ellipsis}}
.status-tag{{display:inline-block;padding:3px 7px;background:#F0F2F7;font-size:11px}}
.status-tag.ok{{background:var(--teal-soft)}} .status-tag.warn{{background:var(--citrus-soft)}}
.status-tag.warn-strong{{background:var(--rose-soft)}} .status-tag.na{{background:#F0F2F7}}
.empty{{padding:18px;background:#F6F7F9;color:var(--subtle)}}
.tiles{{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);
border:1px solid var(--line);margin:0 0 18px}} .tile{{flex:1 1 150px;background:var(--surface);padding:16px 18px}}
.tile strong{{display:block;font-family:Georgia,"Times New Roman",serif;font-size:28px;font-weight:500;margin:4px 0 2px;
font-variant-numeric:tabular-nums}} .tile.as-of strong{{font-family:inherit;font-size:15px;font-weight:750;margin-top:8px}}
.share-block{{display:grid;gap:16px;margin:0 0 22px}} .share-bar{{display:flex;height:22px;background:#F0F2F7;margin-top:6px}}
.share-seg{{display:block;height:100%}} .share-seg+.share-seg{{border-left:2px solid var(--surface)}}
.share-legend{{display:flex;flex-wrap:wrap;gap:6px 16px;margin:7px 0 0;font-size:12px;color:var(--subtle)}}
.sw{{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px}}
.st-out_of_stock,.st-oos{{background:var(--rose)}} .st-low{{background:var(--citrus)}} .st-other{{background:var(--subtle)}}
.sw.ref{{height:0;background:none;border-top:2px dashed}} .sw.ref.max{{border-color:var(--ink)}} .sw.ref.target{{border-color:var(--cobalt)}}
.chart{{margin:0 0 22px;padding-top:12px;border-top:2px solid var(--ink)}} .bars svg{{width:100%;display:block;overflow:visible}}
.chart .grid{{stroke:var(--line);stroke-width:1}} .chart .tick{{font-size:10px;fill:var(--subtle)}}
.bar.oos{{fill:var(--rose)}} .bar.low{{fill:var(--citrus)}} .bar.other{{fill:var(--subtle)}}
.bar-label{{font-size:11px;font-weight:720;fill:var(--ink)}}
.bar-value{{font-size:10px;font-weight:750;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:3px}}
.bar-value.oos{{fill:var(--rose)}} .bar-value.unknown{{fill:var(--subtle);font-style:italic}}
.ref-line{{stroke-width:1.5;stroke-dasharray:5 4}} .ref-line.max{{stroke:var(--ink)}} .ref-line.target{{stroke:var(--cobalt)}}
.ref-label{{font-size:10px;font-weight:800}} .ref-label.max{{fill:var(--ink)}} .ref-label.target{{fill:var(--cobalt)}}
.cell-bar{{display:inline-block;width:72px;height:8px;background:#F0F2F7;margin-right:10px;vertical-align:middle}}
.cell-num{{display:inline-block;min-width:5ch;text-align:right}} .cell-bar>span{{display:block;height:100%}} .cell-bar.cobalt>span{{background:var(--cobalt)}} .cell-bar.citrus>span{{background:var(--citrus)}}
.trust{{background:var(--ink);color:white;border-radius:var(--radius);padding:34px;margin-top:30px}} .trust h2{{font-family:Georgia,serif;
font-size:30px;font-weight:500;margin:0 0 18px}} .trust ul{{columns:2;column-gap:38px;margin:0;padding-left:18px}}
.trust li{{break-inside:avoid;margin:0 0 11px;color:#D7DAE1;font-size:13px}} footer{{display:flex;justify-content:space-between;
gap:20px;color:var(--subtle);font-size:12px;padding:24px 4px}}
@media(max-width:760px){{.cover{{grid-template-columns:1fr}}.cover-main{{padding:34px 28px}}.stamp{{gap:28px}}
.status-ribbon{{grid-template-columns:1fr 1fr}}.status-ribbon>div:nth-child(3){{border-left:0;border-top:1px solid #3B3E48}}
.status-ribbon>div:nth-child(4){{border-top:1px solid #3B3E48}}.module{{padding:26px 20px}}.module-head{{grid-template-columns:1fr}}
.module-head p{{grid-column:1}}.tab{{grid-row:auto;margin-bottom:14px;width:max-content}}.trust ul{{columns:1}}
.cell-bar{{width:40px}}}}
@media print{{@page{{margin:14mm}}body{{background:white}}.top-signal{{display:none}}.page{{width:100%;margin:0}}
.module,.cover{{box-shadow:none;break-inside:avoid}}tr,.chart,.tiles,.share-block{{break-inside:avoid}}
.share-seg,.sw,.cell-bar>span{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.table-wrap{{overflow:visible}}table{{font-size:11px}}th,td{{padding:8px 5px;white-space:normal}}.cell-bar{{width:32px;margin-right:5px}}.trust{{background:white;color:var(--ink);border:1px solid var(--ink)}}
.trust li{{color:var(--ink)}}}}
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
      <span class="kicker">Retail inventory × Sponsored Ads</span>
      <h1>Inventory risk review</h1>
      <p>Products closest to stock-out, and the enabled campaigns and ad groups still driving traffic to ASINs that cannot support it.</p>
    </div>
    <aside class="stamp">
      <dl>
        <div><dt>Account</dt><dd>{_escape(account)}</dd></div>
        <div><dt>Marketplace · Currency</dt><dd>{_escape(marketplace)} · {_escape(currency)}</dd></div>
        <div><dt>Inventory snapshot</dt><dd>{_escape(_timestamp(snapshot))}</dd></div>
        <div><dt>Data kind</dt><dd>Current as-of snapshot</dd></div>
      </dl>
      <small>Timezone: {_escape(timezone_name)}<br>Generated {_escape(generated)}</small>
    </aside>
  </section>
  <section class="status-ribbon" aria-label="Review status">
    <div><span class="micro">Restock risks shown</span><strong>{_escape(restock_cell)}</strong></div>
    <div><span class="micro">Campaign-ASIN OOS pairs</span><strong>{_escape(oos_cell)}</strong></div>
    <div><span class="micro">Low-stock ad-group pairs</span><strong>{_escape(low_cell)}</strong></div>
    <div><span class="micro">Action level</span><strong>Human review</strong></div>
  </section>
  {reading}
  {missing_note}
  {modules}
  <section class="trust">
    <h2>How to read this review</h2>
    <ul>{_trust_notes(bundles)}</ul>
  </section>
  <footer><span>Prepared with Atom11</span><span>Read-only analysis · Verify live and inbound inventory before acting</span></footer>
</main>
</body>
</html>
"""


def _load(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render Atom11 inventory-risk analyses as one HTML brief."
    )
    parser.add_argument("--restock", help="restock_priority run_analysis JSON path")
    parser.add_argument("--campaign-oos", help="campaign_out_of_stock_products JSON path")
    parser.add_argument("--adgroup-low", help="ad_group_low_stock_products JSON path")
    parser.add_argument("--output", required=True, help="Destination HTML path")
    parser.add_argument("--account-name", help="Account display name")
    parser.add_argument(
        "--narrative",
        help=(
            "Optional analyst-narrative JSON path: {verdict, verdict_note, "
            "module_notes:{restock, campaign_oos, ad_group_low}}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    narrative = None
    if args.narrative:
        try:
            narrative = _load(args.narrative)
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"--narrative could not be read as JSON: {exc}")
    document = render(
        _load(args.restock),
        _load(args.campaign_oos),
        _load(args.adgroup_low),
        account_name=args.account_name,
        narrative=narrative,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
