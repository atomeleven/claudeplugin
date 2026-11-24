# Atom11 Inventory Risk Review design

The deterministic renderer owns the layout; this reference exists for the
Markdown fallback and review.

Shared Atom11 decision-brief system: warm paper `#F7F4EA`, white surfaces,
cobalt `#2250F3`, citrus `#FFC01E`, teal `#23967F`, rose `#CD1230` for
out-of-stock; serif display over system sans; square-edged tables, offset
color tabs; no external resources or JavaScript; none of the competitor's
navy/orange dashboard motifs.

## Document structure

1. Briefing cover — account, marketplace · currency, inventory snapshot
   timestamp, "current as-of snapshot" data-kind stamp (no date range).
2. Status ribbon — restock risks returned-of-qualifying, campaign-ASIN OOS
   pairs, low-stock ad-group pairs, read-only action level.
3. Analyst reading — narrative verdict + expansion.
4. Restock priority (rose) — summary tiles, stock-status share, days-of-cover
   chart, then product, status tag, on hand, velocity, days of cover,
   suggested reorder qty, updated; threshold and reorder-target line.
5. Ads on empty shelves (citrus) — summary tiles, then campaign, type, ASIN,
   on hand, enabled product ads, inventory updated.
6. Low-stock exposure (teal) — summary tiles, then ad group, campaign, type,
   ASIN, status, on hand, days of cover, enabled ads; threshold line.
7. Trust notes — recipe notes, freshness-guard exclusions, bounded-input
   disclosures, "verify live and inbound inventory" guardrail.

Sections not run are named in a notice, never silently absent.

## Charts

The renderer draws every chart itself as inline SVG or CSS, from returned
values only; nothing is fetched and no JavaScript runs.

- Each module's evidence starts with tiles for the counts its summary row
  returns (qualifying vs shown products, matching campaigns, ad groups,
  ASINs, pairs) plus the snapshot "as of" time. Nothing is summed or
  derived.
- Stock status uses a straight share bar, never a donut. It counts the
  returned restock rows and says "among the N products shown (of M
  qualifying)" unless the full qualifying list came back.
- Days of cover is one horizontal bar per returned restock product, in table
  order. The dashed lines are the max days of cover and reorder target the
  run returned; a value the run did not return gets no line. Over 30 rows,
  the chart shows the first 30 and says so.
- Table cells for suggested reorder qty, enabled product ads and ad-group
  days of cover carry a small bar, scaled to the largest value in that
  column (ad-group days of cover: to the returned threshold).
- Unknown values (null cover, on hand, reorder qty) get no bar and read
  "Unknown" or "—", never zero.
- A chart needs at least two usable rows; otherwise it is left out and the
  table carries the evidence.
- Hovering a bar shows the product, status, days of cover and on hand.
- The Markdown fallback has no charts; it keeps the same section order.

## Writing style

Out-of-stock exposure leads; every count is returned-of-qualifying; as-of
wording throughout; review-only verbs.
