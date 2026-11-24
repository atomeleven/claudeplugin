# Atom11 Campaign Performance Review design

The deterministic renderer owns the layout; this reference exists for the
Markdown fallback and review.

Shared Atom11 decision-brief system: warm paper `#F7F4EA`, white surfaces,
cobalt `#2250F3`, citrus `#FFC01E`, teal `#23967F` favorable, rose `#CD1230`
risk; serif display over system sans; square-edged tables, offset color
tabs; no external resources or JavaScript; none of the competitor's motifs.

## Document structure

1. Briefing cover — account, marketplace · currency, report window, previous
   comparison window.
2. Status ribbon — completeness, campaigns shown of matching, count above
   ACOS target among shown, read-only action level.
3. Analyst reading — narrative verdict + expansion.
4. Ranked performance (cobalt) — headline tiles (matching campaigns,
   campaigns shown, account average ACOS, spend-growth threshold), the scope
   line naming the rank metric and the uniform 14-day attribution, the
   spend-against-sales bubble chart, then the numbered table: campaign, type,
   spend, sales, orders, ACOS, vs-target tag (with account-avg marker), ROAS.
5. Movement (teal) — this-period against previous-period bars, then the
   numbered table: Δ spend/sales (absolute + approved %), Δ ACOS in
   percentage points, flag tags (new, largest growth/decline, meaningful
   spend growth); a notice replaces percentages when the comparison is not
   like-for-like. Focus cards: largest growth, largest decline, above-target
   list.
6. Trust notes — recipe note, attribution disclosure, target policy,
   meaningful-change threshold, completeness, review-only guardrail.

## Charts

The renderer draws every chart itself as inline SVG or CSS, from returned
values only; nothing is fetched and no JavaScript runs.

- Headline tiles show only figures the recipe's summary returned; nothing is
  summed or derived, and a tile with no returned value is left out.
- The bubble chart plots ad spend (x) against attributed sales (y) for the
  returned campaigns; bubble size is attributed orders. Colour is the
  recipe's own target flag: rose above target, teal at or below target, grey
  no target. A dashed outline marks a campaign flagged against the account
  average, and the dashed line is the returned account average ACOS. The
  legend names every colour in words; bubbles are numbered like both tables
  and hovering one shows its name, figures and target source.
- Period bars pair the returned this-period and previous-period sales and
  spend per campaign. A row is drawn only when `comparison_status` is
  `present_both`, `percent_change_permitted` is true and both windows
  returned values; the caption counts the campaigns left out and why. When
  the windows are not like-for-like, a line says the bars are left out.
- Table spend and sales cells carry a small proportional bar, scaled to the
  largest value in that table. A missing value gets no bar, never an empty
  one.
- No donut or dumbbell charts. A chart needs at least two usable rows;
  otherwise it is left out and the table carries the evidence.
- The Markdown fallback has no charts; it keeps the same section order.

## Writing style

Set-relative claims only ("largest decline among the 10 shown"); targets
quoted with their source; percentage points never conflated with percent
change.
