# Gutenberg-Richter law: notes on fidelity

`figure.py`: 62 lines (about 40 of figure code). Output: single column, 89 x
66 mm, `gallery/published/gutenberg_richter.{png,svg,pdf}`. `figure.report()`:
`inklet lint: clean, 0 diagnostics`. The fit is printed on run:
a = 8.299, b = 1.025 +/- 0.007, R^2 = 0.9987.

## Matches the original

- The law itself: log10 N(>=M) against M, with N the number of events per year
  at or above magnitude M, on a log y axis, and a straight least-squares line
  over the linear range. The fitted slope is b = 1.02 (1.025 +/- 0.007), close
  to 1. The 1944 paper's own fits give b = 0.88 for southern California and,
  for world shocks of magnitude 7 and over, b = 1.12 and 0.97 (Eq. 3-4).
- Points as markers and the fit as a line, the form of the modern reference
  (Wikimedia, 2016 Central Italy earthquake, points with a red fit line labelled
  with a and b). The fit is labelled on the figure with its a and b.
- The 1944 paper itself has no figure (all four pages checked, text and tables
  only). Its fit (Eq. 1-4) is for southern California and for the world at
  magnitude 7 and over, a different data set, so no line from the paper is
  overlaid here.

## Differs, and why

- The data are the global USGS catalogue for 2016-2025 (M >= 4.5), as asked.
  The 1944 study used Southern California (1934-1943) and world shocks
  (1904-1943 and 1922-1943), on the same Richter-type scale but other regions
  and periods. The figure recreates the law's form, not the 1944 numbers.
- Fit range 5.0 to 7.5, not the whole curve. Below 5.0 the cumulative counts
  are steeper than b = 1 (local slope 1.23 between 4.5 and 5.0), and above
  7.5 there are fewer than 50 events in the decade (local slope 1.84, noisy).
  Over 4.5-8.5 the same least squares gives b = 1.14. The out-of-range points
  are drawn in grey, not fitted, and the figure says so.
- Y values are events per year (counts divided by 10), not totals, so the
  intercept reads as the classic a (8.30). The brief asked for log10 N; the
  log axis shows N in the same units.
- The floor at 0.1 per year is single events (one event at M >= 8.3 in the
  decade). It is real, not a plotting artefact, but it is discrete.
- Magnitudes mix types (mb, Mww, ml and others) and are not harmonised. The
  catalogue's own preferred magnitude is used.
- Style: inklet's `scientific.modern` look, with the fitted and unfitted points
  in blue and grey, the equation with its standard error inside the plot, and a
  key drawn as text (blue fitted, grey not fitted) in the top right, where the
  plot is empty.
- No histogram panel (the Wikimedia reference has one below); the brief asked
  for the cumulative plot only.

## Verdict

Faithful to the law and its fit as the brief defines them. The fit range is the
main analytic choice; with the full range the slope would be 1.14, so it is
stated on the figure and in SOURCE.md.
