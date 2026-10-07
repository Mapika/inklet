# Ebbinghaus 1885: notes on fidelity

`figure.py`: 45 lines (about 28 of figure code). Output: single column,
89 x 62 mm plot, `gallery/published/ebbinghaus_1885.{png,svg,pdf}`.
`figure.report()`: `inklet lint: clean, 0 diagnostics`.

## Matches the original

- The seven savings values of Ebbinghaus's own summary table (1913 translation,
  pp. 76-77): 58.2, 44.2, 35.8, 33.7, 27.8, 25.4 and 21.1 percent, at 20 min,
  1 h, 9 h, 1 day, 2 days, 6 days and 31 days. Each is also in the German 1885
  text, and in Murre & Dros (2015) Table 3 as proportions.
- The probable error of the mean (P.E.m) as printed for each point (1.0, 1.0,
  1.0, 1.2, 1.4, 1.3, 0.8 percentage points), drawn as whiskers.
- The log-time view of Murre & Dros (2015) and the image they supplied: time
  since learning on a logarithmic axis, decades 0.01 to 100 days, savings in
  percent on y, points joined in time order.

## Differs, and why

- Time values. Ebbinghaus's table gives X in hours (0.33, 1, 8.8, 24, 48,
  144, 744); the figure uses those exactly (days = X/24). Murre & Dros use
  the section times of the experiment (19 min, 63 min, 8.75 h) for his data
  and 20 min, 1 h, 9 h for the other datasets. The figure's 20 min point is
  therefore plotted at 0.33 h, about 1 min later than the 19-min mean; the
  9 h point is at 8.8 h, not 8.75 h.
- Units of y: percent (58.2), not the 0-0.7 proportion of the Murre image.
- No model fit: Murre & Dros draw an MCM fit through the points; the classic
  figure is the data only, so the fit is left out.
- Point labels "20 min" ... "31 days" are added so each point carries its
  interval; the reference has none. The x ticks show decades only.
- Colour: one ink colour, not the Murre image's black diamonds with a fitted
  line; the markers are diamonds, like the reference.
- The savings summary is a single subject's (Ebbinghaus's) data, not a mean
  over a group. The error bars are his P.E.m, not a standard error.

## Checked and found no bug

- Log x scale with explicit decade ticks renders cleanly. Left alone, the
  log axis labels ticks as powers of ten (10^-2 and so on); the figure sets
  `x_options=dict(format=lambda v: f"{v:g}")` to print 0.01, 0.1, 1, 10, 100.
  Not a crash and the override works; logged in ISSUES-round2-b.md (item 2)
  as a default to review, not as a bug.
