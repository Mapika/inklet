# inklet issues found while recreating katrin_2022 (Figs 3 and 4)

Found with the worktree at commit 51ada61 (inklet 4.8.1), 2026-10-17. All open.
Repros were run with `PYTHONPATH=<worktree>/src` and the worktree's venv.

## 1. No public contour of a gridded field (highest-density regions of a histogram)

**OPEN.** `Panel.kde2d` draws contours only from raw points, and `Panel.matrix`
draws cells only. A 2D histogram (bin counts on a grid) can't be contoured at a given
level, so `fig3.py` imports the private helper `inklet.plot.outlines._contours`.

```python
import numpy as np, inklet as i
from inklet.plot.outlines import _contours          # private
grid = np.random.default_rng(0).random((40, 40))
level = np.quantile(grid, 0.9)
g = [[grid[j, k] - level for k in range(40)] for j in range(40)]
rings = _contours(g)                               # rings in index units
```

- actual: the only contour routes are `kde2d(points)` and the private helper.
- expected: `Panel.contour(grid, x=..., y=..., levels=...)`, or `Panel.matrix(...,
  contour=[levels])`, returning rings in data coordinates.

Workaround: `_data.py` calls `_contours` on the bin counts, with a border below the
level, and maps the rings back to data units.

## 2. Horizontal bars with `width=` in data units inflate the page with no pointer to the cause

**OPEN.** `Panel.bars(..., orient="h", width=1.0)` on a y axis that spans 0.23 units
makes the bars 1.0 units tall. The row then grows to 1,147 mm. The lint reports only
the page, not the bars.

```python
import numpy as np, inklet as i
ys = np.linspace(18573.57, 18573.80, 42)
p = i.plot_spec(14, 50, x=(0, 10), y=(ys[0] - 0.003, ys[-1] + 0.003))
p.bars(ys, np.ones_like(ys) * 5, width=1.0, orient="h")
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", p)
f = doc.compile()
print(round(f.cells["a"].height, 1))              # 1147.6, expected 50
print([l for l in f.report().splitlines() if "PAGE" in l])   # only PAGE_TOO_TALL
```

- actual: cell height 1147.6 mm; the lint says `PAGE_TOO_TALL` with no mention of
  the bars or their width.
- expected: a diagnostic such as `BAR_WIDTH_EXCEEDS_SCALE` naming the bars and the
  domain, or the width clamped to the scale's step (the bar pitch).

Workaround: `width=dy` (the bin pitch in data units).

## 3. No way to draw a histogram from bin edges and counts

**OPEN.** `Panel.hist` and `hist2d` take raw values or points. A histogram that is
already binned (the Source Data for Fig. 3 gives counts per bin) has no entry point.

```python
import numpy as np, inklet as i
edges = np.linspace(0, 1, 11)
counts = np.arange(10)
p = i.plot_spec(60, 40, x=(0, 1), y=(0, 10))
p.hist(counts, bins=edges)  # runs, but bins the counts as raw observations
p.axes()
```

- actual: `hist()` bins whatever it is given, so the counts are treated as data; there
  is no way to say "these are already counts in these edges".
- expected: `Panel.histogram(edges, counts, orient=...)` (or `bars(at=centres,
  width=edge widths)` documented as the way to do this).

Workaround: `Panel.bars(centres, counts, width=bin_width, gap=0)`, with
`orient="h"` for the right-hand marginal. The docs don't say that `width` is in data
units along the bar's own axis.

## 4. `inset(width=...)` shrinks the inset's text, and the lint suggests the wrong fix

**OPEN.** The inset is scaled to `width=` of the parent's plot area, and its text scales
with it. When long row labels narrow the parent's plot area, the inset's ticks fall
below 5 pt. The lint suggests a bigger font, which works arithmetically but is not
the fix: the inset should be built at its printed size with `width=None`, as the
cookbook says.

```python
import inklet as i
sub = i.plot_spec(height=36, x=(-10, 3), y=(0.5, 7.5), clip=True)
sub.line([(-9, 7), (2, 7)], stroke="#1f7ae0")
sub.axes(x=None, y=None, x_options=dict(ticks=[-8, -6, -4, -2, 0, 2]))
main = i.plot_spec(60, 86, x=(-240, 70), y=(0.5, 14.5), clip=True)
main.line([(-226, 14), (-68, 14)], stroke="#127d7d")
main.axis("left", ticks=[14, 1], format=lambda v: "KATRIN (combined)")
main.inset(sub, corner="sw", width=0.5, zoom=(-10, 3, 0.5, 7.5))
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", main)
print([l for l in doc.compile().report().splitlines() if "TINY" in l][:1])
# actual:   TINY_TEXT ... renders at 4.2pt (6.0pt at 0.698x scale)
# expected: no warning; or the lint says "build the inset at its printed size
#           and pass width=None" instead of "set font_size to at least 7.2pt"
```

Workaround: build the inset as a 30 x 36 mm plot and pass `width=None`. The
text then keeps its size.

## 5. `document(columns=2)` silently replaces a plot's authored width

**OPEN.** A plot built at `plot_spec(60, 50)` placed in a `columns=2` document on an
89 mm page is drawn 37.5 mm wide. Nothing says the authored width was ignored.

```python
import inklet as i
main = i.plot_spec(60, 50, x=(0, 1), y=(0, 1)); main.axes()
right = i.plot_spec(14, 50, x=(0, 1), y=(0, 1)); right.line([(0, 0), (1, 1)])
doc = i.preset("scientific.nature", format="single-column").document(columns=2)
doc.add("m", main, row=0, column=0); doc.add("r", right, row=0, column=1)
print(round(doc.compile().cells["m"].width, 1))   # 37.5, authored 60
```

- actual: 37.5 mm, no diagnostic.
- expected: the same `columns=[1, 0.25]` answer, or a note that columns override the
  plot's width.

Workaround: `columns=[1, 0.25]` with `gap=1`, so the main plot gets most of the
width. The marginal panel then gets 14 mm.

## 6. Lint counts empty matrix cells as marks, so labels over blank bins are flagged

**OPEN.** `Panel.matrix` with `missing=` draws a rectangle for every missing cell. A
label, tick label or key over those blank cells is reported as overlapping marks.
Here the cells carry no data.

```python
import inklet as i
vals = [[None] * 10 for _ in range(10)]
vals[5][5] = 1.0
r = i.plot_spec(50, 50, x=(0, 10), y=(0, 10))
r.matrix(vals, ramp=i.ramp("viridis"), missing="#ffffff")
r.text(2, 2, "label over empty cells")
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("d", r)
print([l[:120] for l in doc.compile().report().splitlines() if "OVERLAP" in l])
# actual:   OVERLAP ... overlaps 4 marks inside cell 'd'
# expected: no overlap, because the label sits on blank cells
```

In `fig3.py` and `fig3_improved.py`, nearly every OVERLAP and CROWDING is of this kind.
Checked against the data: the faithful key covers one non-empty bin, at 0.032
against a peak of 45.7.

Workaround: none in the figure. The NOTES.md section "Lint" explains each one. A
blank cell is probably not a mark, so `missing=` cells should be exempt.

## 7. A corner colour bar's title is stacked above the bar and cannot be rotated along it

**OPEN (minor).** `Panel.colorbar(title=...)` puts the title in horizontal text above
the bar. The original figure (and most journal colour bars) sets it along the bar,
which takes less space and reads better beside a tall heatmap.

```python
import inklet as i
q = i.plot_spec(60, 50, x=(0, 1), y=(0, 1))
q.matrix([[0.1, 0.5], [0.9, 0.2]], ramp=i.ramp("viridis"))
q.colorbar(corner="se", length=24, title="Normalized entries (1/eV^{3})")
```

- actual: a horizontal title above the bar.
- expected: `title_rotation=90` (or `title_side="left"`) so the title runs along the bar.

Workaround: a two-line horizontal title, `"Normalized\nentries (1/eV^{3})"`.

## 8. Corner colour bar raises `inset colorbar does not fit` during the document's trial layout

**OPEN, not reduced to a minimal repro.** In `fig3.py` with `columns=2`, `colorbar(corner="se",
length=24, title=...)` raised `ValueError: inset colorbar does not fit; shorten length or
reduce padding`. A debug hook showed the call was made at 37.5 x 50 mm (the first
layout), then 37.5 x 256 mm, and then 17.3 x 50 mm, so the failure came from a
narrower trial width the document tried. The message names the bar length, which was
not the limit at the width the figure was finally drawn.

- actual: the message points at `length` and `pad`, and names neither the width tried
  nor the width needed.
- expected: the message says which dimension failed, and at what size, or the layout
  search treats an unfit key as an infeasible width instead of raising.

Workaround: a panel wide enough that the trial widths all fit. (Pinning `columns=[1,
0.25]` avoids the narrow trial.)

## 9. INCONSISTENT_STROKE counts intended stroke weights as inconsistency

**OPEN (info only).** Every figure here reports `INCONSISTENT_STROKE`, even where
the widths are deliberate: contour lines and their halos, heatmap cell edges,
spines, and the grey zero rule. The message says "uses 4 distinct stroke widths
(max 3)", which doesn't say which are counted.

```python
# lint of examples/published/katrin_2022/fig4.py:
#   INCONSISTENT_STROKE figure uses 4 distinct stroke widths (max 3):
#   0.11mm on 33 (cell-results/0/58), 0.20mm on 1 (...), 0.35mm on 63 (...), 0.50mm on 2 (...)
```

- actual: an info line on every figure with more than one weight.
- expected: the message names the role of each width (spine, data line, reference
  rule), or the check ignores weights of different roles.

Workaround: none; the NOTES say each weight was chosen on purpose.
