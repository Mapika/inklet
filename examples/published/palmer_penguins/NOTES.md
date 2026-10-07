# Palmer penguins: notes on fidelity

`figure.py`: 61 lines (about 35 of figure code). Output: double column,
183 x 80 mm, two panels lettered a and b,
`gallery/published/palmer_penguins.{png,svg,pdf}`. `figure.report()`:
`inklet lint: clean, 0 diagnostics`.

## Matches the original

- Panel a reproduces the palmerpenguins "Penguin bill dimensions" plot: bill
  length (mm) on x, bill depth (mm) on y, one colour and marker shape per
  species (Adelie orange circles, Chinstrap purple triangles, Gentoo teal
  squares, the package's darkorange/purple/cyan4) and a least-squares line per
  species. Axis ranges match (x 30-62, y 12.5-22).
- The pooled fit of the "Simpson's paradox" companion plot is drawn on the same
  panel as a dashed grey line: slope -0.085 mm/mm over all 342 birds, against
  +0.18 (Adelie), +0.22 (Chinstrap) and +0.20 (Gentoo) within species.
- Panel b reproduces "Penguin flipper lengths": overlapping, translucent
  histograms of flipper length by species on shared bins, frequency on y,
  same colours, same 170-235 mm range.

## Differs, and why

- The per-species lines carry 95% confidence bands; the package plot uses
  `se = FALSE`. The bands are cheap and show that each within-species slope
  is clearly positive, which is the point of the Simpson's comparison.
- Two panels merged into one journal figure with letters and no titles
  (the package plots have ggplot titles/subtitles), one key per panel placed
  inside the empty corner of each plot area instead of a key outside.
- Histogram bins are 2 mm wide starting at 172 mm (ggplot used 30 bins over
  the range, about 2.03 mm), so the tallest Adelie bar is 29 instead of 25;
  the shapes of the distributions are the same.
- Histograms are drawn as filled outlines (inklet's grouped-hist style)
  rather than bars with internal edges. Each outline closes only under the
  group's own bins, so the x-axis baseline stays grey (ISSUES-earth-life.md
  #4, fixed).
