# inklet issues found while recreating hodgkin_huxley_1952 and snow_cholera_1854

Found 2026-10-07 with the working tree at master plus local changes. Both
repros run as written with the venv at `.venv/bin/python`.

## 1. `plot_spec(width, height)` is stretched to the page column

A plot built with explicit millimetres inside a document is drawn at the page
column's width, not at the width it was given, so the aspect ratio is wrong.
This breaks equal scale for any map or other figure that needs x and y at the
same mm per unit.

```python
import inklet as i

p = i.plot_spec(100, 50, x=(0, 10), y=(0, 10))   # asks for 100 mm x 50 mm
p.outline(stroke_width=0.5)                       # frame, to measure
doc = i.preset("scientific.modern", format="double-column").document()
doc.add("a", p)
doc.compile().save("box.png", dpi=100)            # measure the frame in pixels
```

- **actual:** the frame is 175 mm wide and 50 mm tall (SVG root is `183mm`
  wide; the plot takes the column width less the 4 mm margin on each side).
  `figure.report()` is clean.
- **expected:** a 100 x 50 mm plot, or a warning that the document column
  overrides the plot width (e.g. `WIDTH_OVERRIDDEN`), naming the fix.
- **workaround used:** set the page to the plot's size plus margins:
  `i.preset("scientific.modern").document(width=side + 2 * MARGIN, margin=MARGIN)`
  (snow_cholera_1854/figure.py). With that, the measured frame is 136.3 x
  136.3 mm for a 136 mm square.

## 2. The OVERLAP message names a scatter mark only by index path

When text overlaps one mark of a large scatter, the warning gives the element
path, not where the mark is, so the author must count indices to find it.

```python
import numpy as np, inklet as i

pts = np.random.default_rng(0).uniform(0, 10, (200, 2))
p = i.plot_spec(60, 60, x=(0, 10), y=(0, 10))
p.scatter(pts, marker="square", size=0.9)
p.text(5.0, 5.0, "a label", anchor="w")
doc = i.preset("scientific.modern").document(width=70, margin=4)
doc.add("a", p)
print(doc.compile().report())
```

- **actual:** `OVERLAP cell-a/0/0/0/160/0 overlaps cell-a/0/1/0/0 'a label' ...`
  (the trailing 160 is an index into the scatter; the message does not give
  its data coordinates or its size).
- **expected:** the data coordinates of the mark and its size, so it can be
  found on the axes, or `--json` output with the bounding box of each target.
- **workaround:** the figure's own data were searched in millimetres to find a
  clear label position (snow_cholera_1854/figure.py). `inklet check --json`
  gives the targets but no geometry.

## Not an issue (checked)

* `annotate(side=...)` does move its label: the label's SVG transform differs
  for n, s, e and w, so the earlier suspicion was wrong.
