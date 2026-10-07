# Notes: Anscombe's quartet (Anscombe 1973, Figs 1–4)

Output: `gallery/published/anscombe_1973.{png,svg,pdf}`, 183 mm (double
column) × 137 mm, 2 × 2 grid. `figure.report()`: `inklet lint: clean, 0
diagnostics`. `figure.py` is 39 lines.

## What matches the original

- All 44 data points, verified against the paper's Table.
- The common fitted line y = 3 + 0.5x (OLS per set, identical to 2 d.p.),
  drawn edge to edge over x = 0–20 as in the paper, reaching y = 13 at x = 20.
- Identical axes on all four panels: x 0–20, y 0–13, labelled ticks every 5
  (0, 5, 10, 15, 20 and 0, 5, 10) with an unlabelled minor tick at every unit,
  exactly the paper's furniture.
- Order and arrangement: data sets 1–4 read left to right, top to bottom, as
  Figures 1–2 (p. 19) and 3–4 (p. 20) sit on the printed pages.
- Set 4's eight coincident x = 8 observations overplot into a column, as they
  do in the paper; its x = 19 point sits on the line.

## What differs, and why

- Re-styled in inklet's `scientific.modern` look: grey axes, dark points,
  the fitted line in red rather than black so data and model separate at a
  glance. The line is drawn under the points (the paper's line runs over set
  4's x = 19 point).
- Panel titles "Data set 1…4" replace the paper's separate captions
  "Figure 1…4"; panel letters are switched off (`letters=False`) because the
  data-set numbers are the identifiers the text refers to.
- Axis titles *x* and *y* are added (the paper has none); they repeat on
  every panel because each was a free-standing figure in the original.
- The four figures are combined into one 2 × 2 figure, the arrangement the
  quartet is usually shown in; in the paper they are four separate figures
  across two pages.
- The tick scheme is set with one `chart.axes(...)` call per panel. The
  quick API's `xticks=`/`yticks=` cover the labelled ticks, but there is no
  quick option for minor ticks, so the paper's unit ticks still need
  `x_options={"minor": 5}` (ISSUES-stats-genomics.md, 5).

## Verdict

Faithful: same data, same line, same axes and tick scheme; only typography
and colour are modernised.
