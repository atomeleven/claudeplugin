# Atom11 Search-Term Opportunities design

The deterministic renderer owns the layout; this reference exists for the
Markdown fallback and review.

Shared Atom11 decision-brief system: warm paper `#F7F4EA`, white surfaces,
cobalt `#2250F3`, citrus `#FFC01E`, teal `#23967F` favorable, rose `#CD1230`
risk; serif display over system sans; square-edged tables, offset color tabs;
no external resources or JavaScript; never the competitor's navy masthead,
numbered spine, charts-with-CTA look.

## Document structure

1. Briefing cover — account, marketplace · currency, period, attribution
   profile.
2. Status ribbon — completeness, harvest candidates returned-of-matching,
   observed zero-order spend, read-only action level.
3. Analyst reading — narrative verdict + expansion.
4. Headline tiles — summary-block numbers only: qualifying harvest source
   terms, qualifying zero-order terms, observed zero-order spend, spend in
   the shown terms, and already-targeted terms excluded when that policy is
   on.
5. Harvest candidates (teal) — qualification line (orders/clicks/ACOS cap,
   targeted-terms policy), a bar chart of attributed orders, then a numbered
   table: term · source target · clicks · spend · orders · sales · ACOS.
6. Negative candidates (rose) — zero-order hero figure, qualification and
   coverage cells, a spend bar chart beside a clicks-against-spend scatter,
   then the numbered bounded term table.
7. Trust notes — attribution-profile disclosure, recipe notes, dashboard
   reconciliation note, completeness.

## Charts

The renderer draws every chart itself as inline SVG or CSS, from returned
values only; nothing is fetched and no JavaScript runs.

- Tiles show summary-block counts and totals exactly as returned; nothing is
  summed or derived. The recipe returns no comparison period, so tiles carry
  no change arrows.
- Bar charts show the top 10 rows by attributed orders (harvest) and by
  observed spend (negative), numbered to match the table, and say how they
  relate to the full list, e.g. "Top 10 of 26 qualifying terms".
- The scatter plots ad clicks against observed spend for the shown
  zero-order terms; dots are numbered like the table, and hovering one shows
  the term and its returned figures.
- Table orders, sales and spend cells carry a small proportional bar, scaled
  to the largest value in that column.
- A chart needs at least two usable rows; otherwise it is left out and the
  table carries the evidence. A missing value is left out of every chart and
  gets no table bar, so unknown never reads as zero.
- Bars and share-style comparisons stay straight bars, never a donut. Charts
  never show reference IDs.
- The Markdown fallback has no charts; it keeps the same section order.

## Writing style

One evidence-cited finding per module; both queues framed as human review
queues; bounded lists always qualified with returned-of-matching counts.
