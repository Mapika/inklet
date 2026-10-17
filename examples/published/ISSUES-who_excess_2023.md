# inklet issues found while recreating who_excess_2023 (Msemburi et al. 2023, Figures 1, 2 and 5)

Found with the worktree at commit 51ada61 (inklet 4.8.1), 2026-10-17. Every repro
below was run in that tree. Items 1-3 cost time in every script; 4-6 are narrower.

## 1. `scientific.nature` lints FONT_SUBSTITUTED for Liberation Sans when Arial is not installed

The machine has Liberation Sans, which is metrically compatible with Arial, but
not Arial. The Nature profile lists only Arial and Helvetica, so every text
primitive warns.

```python
import numpy as np, inklet as i
p = i.plot_spec(60, 30, x=(0, 1), y=(0, 1))
p.line(np.c_[np.linspace(0, 1, 5), np.linspace(0, 1, 5)], name="a")
p.axes(x="Time", y="Value")
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", p)
print(doc.compile().report())
# actual:   1 warning, FONT_SUBSTITUTED: 14 text prim(s) are set in 'Liberation Sans' ...
# expected: no warning for a metric-compatible substitute, or a note that says
#           Liberation Sans is metric-compatible with Arial and is acceptable
```

Workaround: `i.preset("scientific.nature", format=..., expected_fonts=("Arial", "Helvetica", "Liberation Sans"))`
in all six scripts. The output PDFs and SVGs embed Liberation Sans. If the journal
wants Arial itself, install it and remove the override.

## 2. Multi-line text is centred by default, and the option that left-aligns it is undocumented

Two-line labels (a name over a value) come out with the second line centred under
the first. The left-aligned form is `align="start"`, which `Panel.text` passes
through to the text node. The `text()` docstring does not mention it.

```python
import inklet as i
p = i.plot_spec(40, 20, x=(0, 1), y=(0, 1))
p.text(0.1, 0.7, "Excess\n14.8 M", anchor="w", size=i.pt(6.5))                # centred
p.text(0.1, 0.3, "Excess\n14.8 M", anchor="w", size=i.pt(6.5), align="start")  # left
# actual:   the first label's lines are centred on each other
# expected: align documented on text(), or multi-line labels left-aligned by default
```

Workaround used in the figures: `align="start"` for the two-line key labels in
`fig2_improved.py`, which works and was verified in the render. The Figure 1 end labels
are single-line, so they do not need it.

## 3. A cell name cannot contain a space

Cell names are identifiers, and a panel title is the natural name for a region
panel. The error is clear, but the name is only an id.

```python
doc.add("African region", p)
# actual:   ValueError: cell names start with a letter and contain letters, digits, underscores or hyphens
# expected: accept any string, or state in the docs that a cell name is an id
```

Workaround: `doc.add(f"r{row}c{column}", p, row=row, column=column)`, with the
region name as the panel's `title()`.

## 4. No single axis label for a grid of panels

Figure 2 of the original has one "Month Year" centred under the bottom row and one
"P-score (%)" at the left. I found no option that puts one label under a grid of
cells. The faithful version repeats the x-title under each bottom-row panel and
the y-title under each left-column panel, which the original does not do. The
improved version drops the x-title, since the year ticks say what the axis is.

Expected: a document-level axis title or caption that spans a grid (or a
`label=` on `Document.add` that takes a spanning option).

## 5. Key order follows the order of drawing, and `band()` counts as a draw

In Figure 1, `band(..., name="excess")` is called before `line(..., name="excess")`
and `line(..., name="reported")`. The key therefore lists the excess series first,
while the original lists the reported series first.

```python
p.band(t, lo, hi, color=C, name="excess")
p.line(t, mean, name="excess")
p.line(t, rep, name="reported")
p.legend(side="bottom")
# actual:   key order excess, reported
# expected: first named line, or drawing order with band() not counted
```

Workaround: `p.legend(side="bottom", names=["reported", "excess"])`, which the
legend docstring documents.

## 6. A labelled dot plot needs numeric rows and a rounding-keyed formatter

Figure 5 is a dot-and-whisker plot with country names on the y axis. The full model
has no categorical y axis for a `scatter`/`errorbars` panel, so the rows are numeric
positions with a formatter that looks the name up by the rounded position.

```python
names = {round(y, 6): name for y, name in zip(ypos, countries)}
p.axes(y_options=dict(ticks=list(ypos), format=lambda v: names[round(v, 6)]))
# actual:   works; the lookup depends on float rounding of the tick values
# expected: a categorical y option for the full model, as the quick API has for
#           lollipop and dumbbell (orient='h')
```

I did not test `i.quick.forest` for Figure 5. It draws weight squares, which the
original does not, and I did not check whether it could be restyled to match.

## 7. Date handling was not tested, and decimal years were used instead

The time-series docs describe calendar axes for the browser preview. The figures use
numeric decimal years (`year + (month - 1) / 12`) with a `format=` callable that
writes month names, which works. I did not test `plot.dates` on these panels, so
there is no verdict on it here.

## 8. A key in an empty grid cell: the legend route fails, and drawn swatches work

Figure 2 has an empty eighth cell, which I wanted to use for a key with a swatch
for each encoding. It took about six attempts. None of the legend routes gave a
clean lint result on the first try.

- `legend(entries=[(name, colour), ...])` on a text-free panel: `KEY_MISMATCH`
  ("1 entry for colours drawn nowhere"), because `entries=` describes nothing that
  is drawn.
- Series drawn outside the axes (`clip=True`, off-range data) and then
  `legend()`: `KEY_MISMATCH` again for the band, and `EMPTY_DIAGRAM` infos. Lint does
  not count clipped marks as drawn, and I did not want to rely on that.
- `legend()` with the names drawn in the cell: the key text is measured as right
  furniture of the column, because `share_plot_margins=True` shares furniture down
  the grid line. The layout then fails with `LayoutError` in the cell above
  ("leaves only 2.11 mm for data ... the furniture takes 27.65 mm right"). Even with
  `font_size=i.pt(5.5)` the entry text was too wide for the 36 mm cell.

What worked: a plain panel with no axes, where each swatch is a `line` or `band`
drawn in the cell (a 0.14-unit sample, the same stroke and tint as the panels), with
its name set by `text(..., anchor="w", align="start")`. Lint is clean, and the render
shows the swatches and labels with no overlap. The price is that the key is not
generated from the drawn record, so if the panels' styles change, the key must be
edited by hand. A legend that could take swatches from the drawn record in a
dedicated key cell would remove that.

## Pass 2

Items 4 and 8 are answered by the new APIs: `doc.label(x=, y=)` now sets the grid's
axis names, and `Panel.key_diagram()` gives the key for the empty cell (see item 11
for the trap in using it).

## 9. A plot wider than its page's room is drawn narrower, with no diagnostic

Figure 5 at 136 mm wide, with the 25 country labels on the left, was authored as
`plot_spec(108, 122)`. The 200 dpi PNG shows the x axis about 98.8 mm long (from the
spine to the 100% end), and `figure.report()` says "clean, 0 diagnostics". The layout
does not honour the authored 108 mm, and nothing says so.

Repro: `examples/published/who_excess_2023/fig5.py` with `plot_spec(108, 84)` in
place of `plot_spec(98, 84)`, and `document(width=136)`. Measure the longest dark
run on the axis row of the PNG, and compare it with 108 mm.

I set the width to 98 mm explicitly, so the figure does not depend on the behaviour.

## 10. `doc.letters()` on a 4-column grid shrinks every plot, and reports it

With `doc.letters()` added to Figure 2's improved script (4 columns, 183 mm,
`share_plot_margins=True`, 36 mm plots), all seven lettered cells report
`PLOT_WIDTH_OVERRIDDEN`: "its plot is authored 36.0 mm wide but is drawn 28.9 mm wide,
because the cell is 40.3 mm and the plot's furniture takes 11.4 mm of it". Without the
letters the same grid is clean. `letters(anchor="cell")` gives the same result.

Repro: `fig2_improved.py` with `doc.letters()` before `doc.compile()`. I did not add
letters to the improved figure. The caption names the panels instead.

## 11. `key_diagram()` on a `plot_spec` silently returns a `PlotSpec`

`plot_spec` objects are live and take any method name without complaint, so
`key_diagram()` on one returns another `PlotSpec` and draws a full plot in the empty
cell. The first attempt at Figure 2's key did exactly this: the "key" cell showed a
second "European region" plot, and nothing was reported.

Repro:

```python
import inklet as i
p = i.plot_spec(36, 52, x=(0, 1), y=(0, 1))
p.line([(0, 0), (1, 1)], name="A")
print(type(p.key_diagram()).__name__)   # PlotSpec, not a key diagram
```

The documented form, `i.panel(...)` (a drawn `Panel`), works. The key is then built
from a drawn panel that carries every named series. A `plot_spec` should raise for
`key_diagram`, since a key cannot come from it.

## 12. The message for a drawn panel that does not fit its cell suggests the wrong fix

Adding a drawn `i.panel(36, 52, ...)` to a `share_plot_margins=True` grid fails with
"cell 'r0c0' contains 43.86 × 61.55 mm but has 40.42 × 61.55 mm. Increase its cell
size." A grid's cells are sized by the page, so the user cannot increase them. The
docs say a drawn `Panel` keeps its geometry, and that is why it fails, but the advice
should say to draw the plot as a `plot_spec`, or to take the furniture off the panel.

Repro: in `fig2_improved.py`, draw the seven regional panels with `i.panel(36, 52, ...)`
instead of `i.plot_spec(...)`, in the 4-column grid with `share_plot_margins=True`.

## 13. A bottom legend with two long names: `columns=2` fails, and the default stacks

Figure 1, panel b (`plot_spec(62, 31)`, two entries of about 40 characters). The
default `legend(side="bottom")` stacks the two entries on two rows, and the original
has one row. The options I tried:

- `columns=2` on panel b: `ValueError: legend needs 40.97 mm but max_width is 28.31 mm`.
- `columns=2` on panel a: `LayoutError` ("cell 'a' leaves only 1.31 mm for data
  after labels"). The one-row key overhangs both sides of the plot: the cell is 81 mm
  wide and the furniture takes 41.7 mm on the left and 38.0 mm on the right.
- `columns="auto", max_width=82`: the same `LayoutError`.

The `max_width` the error reports (28.31 mm) is not the cell or plot width, so the
limit it checks is hard to predict. I kept the default two-row key. Nothing here is
wrong with the data. The gap is that a bottom key cannot be one row when it is wider
than the plot, and the options do not say what width they fit.
