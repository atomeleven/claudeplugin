---
name: atom11-charts
description: "Adds one or two charts on top of Atom11 answers in the chat. The charts are extra: the normal answer stays complete, with every table, metric, total and finding. Use for any answer built from Atom11 data with numbers across dates or across items: ad performance, trends, period comparisons, campaigns, ad groups, keywords, search terms, ASINs, placements, ad types, portfolios, retail sales and traffic, inventory, SQP, DSP, budgets, rule activity, or when the user asks for a chart, graph or visual. Offers an HTML version once. Single numbers stay text. Not for numbers from other sources, full reports (atom11-report), audits, Google Sheets reports or account changes."
---

# Atom11 Charts

Add one or two charts to Atom11 answers in the chat, so the numbers can be seen at a
glance. The charts are an extra. The answer itself stays exactly as it would be without
this skill. This skill reads data the normal Atom11 way and never changes the account.

## Charts are extra, never a replacement

- First work out the full answer as you would without this skill: every table with all its
  metrics, rows and totals, the findings, the data-loaded check and any notes.
- Keep all of it. Never drop a table, column, row, total or finding because a chart shows
  the same numbers. A table that repeats what a chart shows is wanted: some users read the
  table, some read the chart.
- Never shorten the answer to make room for the charts.
- Order: the charts come first, then the full answer below them, then the HTML offer.

## When to chart

- Chart when the answer is built from Atom11 data and has a metric across 2 or more dates,
  or 2 or more items or periods to compare. Any Atom11 data counts: ads, retail, inventory,
  SQP, DSP, budgets, rule activity.
- Text only, no chart, for: a single number, a yes/no answer, a list without numbers, and
  numbers that do not come from Atom11 (an uploaded file, another tool).
- Usually one chart. Two only when the answer tells two different things (for example money
  and a rate, or a trend and a ranking). Never more than two.
- If the user asks for a chart, graph or visual of Atom11 data, always chart.

## Get the data

- Use the Atom11 connector as usual; its own instructions decide which tools to call. Read
  everything the normal answer needs; never read less to make a chart.
- No date range given: ask for one, as the connector requires. Never guess it.
- The charts use the same numbers as the answer. Make one extra read only when the answer
  has nothing that fits a chart, for example a trend that needs the data grouped by time.
- Over time: ask Atom11 for the data already grouped by day, week or month, not raw rows.
  Use the grouping the user asked for; otherwise day up to 31 days, week up to about
  6 months, month for longer.
- A ranking chart shows at most 15 items; the answer's table still lists every row it
  would have listed.
- Chart only numbers Atom11 returned in this conversation. Never estimate, smooth or fill
  in missing dates: leave a gap and say why.
- If the range reaches yesterday or today, mark those days as still syncing (a lighter or
  dashed last point) and say so under the chart.

## Draw it in the chat

Use the Claude app's chart or visual feature to draw it right in the chat. Pick the
simplest chart that fits:

| The answer shows | Chart |
|---|---|
| One or two metrics over time | Line chart (bars if only 2 to 4 periods) |
| This period vs the last one | Grouped bars, current next to previous |
| A ranking of items | Horizontal bars, largest first, at most 15 |
| Share of a total (ad type, placement) | Stacked or 100% bar; no pie with more than 5 slices |
| A funnel (SQP impressions, clicks, cart adds, purchases) | Step bars in funnel order |
| Two metrics per item (spend vs sales per campaign) | Scatter, with the biggest points labelled |

- Never put money and a percentage on the same axis. Ad Spend and ACOS get two charts (or a
  second axis that is clearly labelled).
- The title names the metric, the account and the exact dates, for example
  "Ad Spend by week, Acme US, 1 Sep to 30 Nov 2026".
- Label axes with units and the account currency. Use these names: Ad Spend, Ad Sales,
  Ad Orders, Ad Clicks, Impressions, ROAS, ACOS.
- Show readable names (campaign name, product title), never internal ids.
- No separate summary under the charts: the full answer below them carries the numbers.
- If this app cannot draw visuals (for example a terminal), give the normal answer as it
  is and say in one line that the charts show in the Claude app.

## HTML version

At the end of the answer, offer it once, in one short line: "Want this as an HTML page you
can save or share?" Do not ask before answering, and do not ask again in the same
conversation after a no.

If the user says yes, make one HTML file with the same charts (drawn as inline SVG, no
outside links, so it opens anywhere), the answer's tables under them, and the title and
dates. Use exactly the numbers shown in the chat.

Give the page the Atom11 look:

- Put the Atom11 logo at the top left. The file is `assets/atom11-logo.png` in this skill's
  folder; embed it in the page as a base64 `data:` image, about 32px high, so the page still
  has no outside links. If the file cannot be read, write "Atom11" in the brand blue instead.
- Use the Atom11 blue `#2250F3` for the main series, links and the line under the header.
  Keep other colours quiet (greys for axes and gridlines) and use a second colour only when
  a chart has a second series.

## Completion check

- The full answer is there, as it would be without this skill: every table with all its
  metrics, rows and totals, the findings and the data checks. Charts were only added.
- The charts come first, then the full answer, then the HTML offer.
- At most two charts, and only for Atom11 numbers across dates or items.
- Every charted number came from an Atom11 result in this conversation.
- Each title has the metric, the account and the exact dates; axes have units and currency.
- Money and percentages are never on one axis; no internal ids are shown.
- Still-syncing days are marked; missing dates show as gaps.
- The HTML version was offered once and made only on a yes.
- An HTML version, if made, has the Atom11 logo at the top and uses the Atom11 blue.
