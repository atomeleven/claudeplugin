# Report document

The renderer (`scripts/render_report.py`) consumes one JSON document and the
raw evidence files (the unedited MCP responses). It lays out the Atom11
decision brief and verifies that every number and every name in the document
exists in the evidence. The document is yours to compose; the evidence is
never edited.

## Shape

```json
{
  "schema_version": 1,
  "report": {
    "title": "Weekly Business Review",
    "report_type": "weekly",
    "account": {
      "display_name": "Atom11 Demo Storefront US",
      "system": "Sponsored Ads + Retail",
      "marketplace": "US",
      "currency": "USD",
      "timezone": "America/Los_Angeles"
    },
    "period": {
      "start": "2026-10-05", "end": "2026-10-11",
      "previous_start": "2026-09-28", "previous_end": "2026-10-04",
      "label": "Oct 5 – Oct 11, 2026"
    },
    "generated_on": "2026-10-13",
    "cadence": "weekly",
    "prepared_for": "Acme Brands — brand team",
    "data_completeness": "complete",
    "verdict": "Spend held flat while attributed sales fell nine percent",
    "verdict_note": "Two to four sentences, each quoting a returned value or name."
  },
  "status_items": [
    {"label": "Review flags", "value": "4"},
    {"label": "Observed zero-order spend", "value": "$1,204.18"}
  ],
  "sections": [
    {
      "id": "performance",
      "heading": "Account performance",
      "source_label": "Sponsored Ads and whole-store retail data (dashboard profile)",
      "status": "ok",
      "status_note": "",
      "analyst_note": "One evidence-cited takeaway for this section.",
      "kpis": [
        {"label": "Ad Spend", "value": "12894.55", "format": "currency",
         "previous": "12790.10", "percent_change": "0.0082",
         "change_permitted": true, "good_direction": "neutral",
         "group": "Sponsored Ads (attributed)"}
      ],
      "tables": [
        {
          "title": "Top campaigns by spend",
          "columns": [
            {"key": "campaign", "label": "Campaign", "format": "text"},
            {"key": "ad_spend", "label": "Ad Spend", "format": "currency"},
            {"key": "acos", "label": "ACOS", "format": "percent"}
          ],
          "rows": [{"campaign": "SP | Brand | Exact", "ad_spend": "2210.40", "acos": "0.284"}],
          "coverage": "Top 10 of 25 inspected high-spend campaigns",
          "footnote": "Attributed sales, dashboard profile.",
          "chart": {"type": "bar", "label_key": "campaign", "value_key": "ad_spend", "format": "currency"}
        }
      ],
      "bullets": ["Short evidence-backed observations when a table is overkill."],
      "warnings": ["Sponsored Display data complete through 2026-10-09; the last two days are partial."],
      "coverage": "Section-level coverage statement when the tables do not carry one."
    }
  ],
  "decision_queue": [
    {"title": "Review 'SP | Auto | Discovery' for zero attributed sales",
     "detail": "Spent $412.30 with zero attributed sales among 25 inspected rows.",
     "evidence": "Campaign focus table, row 7.",
     "section_id": "performance"}
  ],
  "trust_notes": [
    "All figures were returned by Atom11's reviewed analyses; nothing was recomputed.",
    "This report is read-only and review-only."
  ],
  "methodology": ["Optional short lines on profiles, windows, thresholds."]
}
```

## Field rules

**report**

- `title`, `report_type`, `account.display_name`, `period.start`,
  `period.end`, `generated_on` are required. `cadence` is `weekly`,
  `monthly` or `one-off`. `data_completeness` is `complete` or `partial`.
- `period.previous_*` only when a module returned a previous window; the
  renderer prints "Compared with …" from it.
- `verdict` is at most twelve words; `verdict_note` two to four sentences.
  Both are free text and are not provenance-checked, so keep them honest
  by quoting returned values exactly.

**sections** (ordered as in `report-types.md`)

- `id` is the module id; `heading` is the business heading; `source_label`
  names the data in business words ("Sponsored Products data"), never a
  recipe, dataset, table or leg name.
- `status`: `ok`, `partial` (freshness or coverage incomplete), `unavailable`
  (the catalog had no such analysis for this scope), `failed` (error
  envelope; put the plain-language message in `status_note`), `skipped`
  (planned but not run; say why). Sections with a non-`ok` status keep their
  heading and render the note instead of being dropped.
- `analyst_note` is optional free text; omit it when you have no
  evidence-backed reading.
- `kpis[]`: `label`, `value`, `format`; optional `previous`,
  `percent_change` (a ratio such as `0.0082`, or the percent string the
  result returned — the renderer accepts either and verifies both forms),
  `change_permitted` (default false: without it no change is drawn),
  `good_direction` (`up`, `down`, `neutral`; colours the change), `group`
  (ledger grouping label), `note` (short qualifier such as "attributed").
- `tables[]`: `title`, `columns[]` (`key`, `label`, `format`, optional
  `signed: true` for deltas, optional `verify: false` for a free-text
  column such as a status label you wrote yourself), `rows[]` (objects keyed
  by column key), optional `coverage`, `footnote`, `chart`.
- `chart`: `{"type": "bar" | "hbar", "label_key", "value_key", "format"}`.
  `bar` draws vertical bars in row order (trends, hour of day); `hbar` draws
  horizontal signed bars (movers). The renderer draws from the same rows,
  so a chart never introduces a value that is not in the table.
- `bullets[]`, `warnings[]`, `coverage` are free text. Put freshness and
  coverage warnings in `warnings` of the section they affect.

**decision_queue[]**: `title`, `detail`, optional `evidence`, `section_id`.
Order is the order shown. Use review verbs.

**trust_notes[]**: one consolidated list at the end (completeness,
attribution, boundedness, methodology, unavailable sections, read-only).

## Formats

| format | input | rendered |
|---|---|---|
| `text` | string | escaped text |
| `integer` | number or numeric string | `1,234` |
| `number` | number or numeric string | `1,234.56` |
| `currency` | number or numeric string | `$1,234.56` using `report.account.currency` |
| `percent` | ratio (`0.284`) | `28.4%` |
| `percent_value` | already a percent (`28.4`) | `28.4%` |
| `multiplier` | number | `3.52×` |
| `date` | `YYYY-MM-DD` | as given |

Null or missing values render as a muted dash, never as zero.

## Provenance verification

Before writing HTML the renderer indexes every number and string in the
evidence files, recursively, including numbers stored as strings (recipes
return decimals as strings). It then checks:

- every KPI `value`, `previous` and `percent_change`;
- every table cell in a column whose `format` is not `text`, and every
  `text` cell unless the column says `verify: false`;
- `report.account.display_name`, `period.start` and `period.end`.

A number verifies when the evidence contains the same value exactly, or the
same value rounded to two decimals, or the value divided or multiplied by
100 (percent conversions). A string verifies when the evidence contains it
exactly after trimming and case-folding.

The renderer also refuses any column key, KPI label or cell that looks like
an internal identifier (`scope_id`, `trace_id`, `interaction_id`, keys ending
in `_ref` or `_id`, long opaque tokens). Replace them with names.

On failure it prints each offending location and exits non-zero. Fix the
document and rerun. `--no-verify` exists only for an explicitly requested
preview and stamps the report "values not verified against evidence".

## Composition tips

- Build each section from one module's saved evidence file and copy values
  verbatim as the result gave them (strings stay strings).
- Prefer a short KPI ledger plus one or two bounded tables per section.
  Three tables and no reading is a dump, not a report.
- When a module returned nothing (an account with no goals, no movers above
  threshold), keep the section with `status: ok`, no tables, and a bullet
  saying what the result returned.
