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
