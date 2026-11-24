# Atom11 Decision Brief design (report system)

Create a self-contained, client-ready document that reads like an analytical
brief, not a dashboard screenshot or sales brochure.

## Visual direction

Use an editorial **signal-board** system:

- warm paper background with white working surfaces;
- Atom11 cobalt as the navigation accent;
- a citrus highlight for attention, not decoration;
- teal for favorable movement and red only for risks;
- square-edged ledger rows and offset color tabs rather than a wall of rounded
  cards;
- asymmetric briefing cover followed by calm, readable evidence modules;
- section names, not numbered sections;
- system fonts only, with a serif display face and sans-serif body face;
- no external resources, tracking pixels, remote fonts, or JavaScript.

Suggested tokens:

```css
--ink: #181B25;
--subtle: #525866;
--line: #D9DEE8;
--paper: #F7F4EA;
--surface: #FFFFFF;
--cobalt: #2250F3;
--cobalt-soft: #E5EBFF;
--citrus: #FFC01E;
--citrus-soft: #FFF3C4;
--teal: #23967F;
--rose: #CD1230;
```

Do not use a dark navy masthead, blue cockpit strip, framed sheet with crop
marks, numbered vertical spine, dominant recoverable-spend hero, dumbbell
chart, donut chart, or closing sales CTA. Those motifs do not belong to the
Atom11 report system.

## Document structure

The renderer produces this order from the report document; the composer
decides what goes in each module.

1. **Briefing cover** — Atom11 wordmark, report title, account, marketplace,
   currency, current period, comparison period when one exists, cadence and
   generated date.
2. **Status ribbon** — data completeness, number of decision-queue items,
   any extra status items the composer supplied, and a clear read-only
   label.
3. **Analyst reading** — the verdict (a serif headline of at most 12 words)
   and its note. Each module may open with one cobalt "Analyst note" line:
   the single evidence-cited takeaway. Notes are the loud tier; tables and
   charts are the quiet evidence beneath them.
4. **Modules, in report order** — each with its heading, a business source
   label, a status line when not `ok`, a KPI ledger (grouped rows with
   current value, approved relative change and a small proportional change
   rail; a muted dash where no change is permitted), bounded tables with
   their coverage line, optional inline SVG bar charts drawn from the same
   rows, bullets, and warnings rendered beside the module.
5. **Decision queue** — review tasks in the composer's order with their
   evidence lines.
6. **Trust notes** — completeness, attribution, boundedness, methodology,
   unavailable sections, read-only statement.

A module with no usable data keeps its heading and explains its status. It
is never silently removed.

## Writing style

- The analyst voice is terse and evidence-first: one sharp finding per module,
  quoting exact returned values and entity names; never generic restatements
  of what a section contains.
- Start each module with a factual one-sentence takeaway.
- Separate observation, interpretation, and suggested review.
- Prefer precise qualifiers such as “among 25 inspected high-spend campaigns.”
- Use compact tables for evidence and short prose for implications.
- Do not use alarmist account-health labels.
- Do not imply that a review task has been applied.

## Accessibility and print

- Use semantic headings and real HTML tables.
- Pair color with text and symbols; never make color the only signal.
- Include visible focus styles for expandable notes.
- Repeat table headers when printing.
- Avoid breaking a module or table row across pages when practical.
- Ensure the report remains legible at 320 CSS pixels and when saved as PDF.
