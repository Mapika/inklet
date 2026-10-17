# inklet issues found while recreating jwst_wasp39b_2023 (Figure 3)

Found 2026-10-17 with the worktree at commit 51ada61 plus local changes. Both
repros run with `PYTHONPATH=<worktree>/src <venv>/bin/python`.

## 1. `annotate(..., color=)` is accepted, then fails at compile with a TypeError

`Panel.text()` takes `color=` and `fill=`, and `annotate()` does not. The call
returns without error, and the failure appears only in `doc.compile()`, deep in
`draw/annotate.py`, with a message about `Style`. A user who has just written
`text(..., color=...)` reads the error as a bug in their own code.

```python
import inklet as i

q = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
q.line([(0, 0.2), (1, 0.8)], stroke="#000000", name="line")
q.annotate(0.5, 0.5, "callout", side="n", color="#a94400")   # no error here
doc = i.document(width=100)
doc.add("a", q)
doc.compile()
# actual:   TypeError: Style.__init__() got an unexpected keyword argument 'color'
# expected: either annotate() takes color= like text() does, or the error is
#           raised at the annotate() call and names the accepted keyword
#           (text_fill= / fill=)
```

Workaround: `annotate(..., text_fill="#a94400")`. The figure uses `text()` with
`color=` for every other label.

## 2. Thinned y ticks print a UserWarning per axis, and lint reports the same thing

An 8.5 mm tall strip with three explicit y ticks (`0`, `500`, `1,000`) at 6 pt
drops the middle one. Two things are reported for that one event: a Python
`UserWarning` from `plot/panel.py:1206` (printed once per build, so twice in
a single run, and once per strip in a six-strip figure), and the lint entry
`TICKS_DROPPED`. The warning text says "use thin=False", and the lint text says the same.

Minimal, runnable:

```python
import warnings
import inklet as i

doc = i.preset("scientific.nature", format="double-column").document()
p = i.plot_spec(148, 8.5, x=(3.0, 5.5), y=(-60, 1300), clip=True)
p.line([(3.0, 0), (5.5, 1000)], stroke="#000000", stroke_width=0.25, name="x")
p.axes(x=None, y="ppm", y_options=dict(ticks=[0, 500, 1000], format="{:,.0f}"))
doc.add("a", p)
figure = doc.compile()     # UserWarning printed here
print(figure.report())     # TICKS_DROPPED: 500 left out
# actual:   two UserWarning lines "axis omitted 1 of 3 explicitly supplied
#           ticks", then TICKS_DROPPED on the same tick
# expected: one diagnostic (lint), or the warning only when the user asked for
#           thinning; a figure built with a warning filter should not repeat it
```

Workaround: supply the ticks that fit (`[0, 1000]`) for the short strips. The
figure does this, so the warning no longer appears.

## 3. FONT_SUBSTITUTED on every `scientific.nature` figure, on machines without Arial

The Nature double-column profile expects Arial or Helvetica. On this WSL2
machine neither is installed (`fc-list` finds none), so every text primitive
is set in Liberation Sans, which is metric-compatible with Arial. Lint then
reports one WARNING per figure, whatever the figure contains. The suggested
fixes are a font install or a `font_family=` path, and `expected_fonts=None`
is mentioned in the text, but nothing says whether Liberation Sans is an
accepted substitute for Arial on a Nature submission.

```python
import inklet as i
p = i.plot_spec(148, 55, x=(0, 1), y=(0, 1))
p.line([(0, 0), (1, 1)], name="line")
p.axes(x="Time (s)", y="Signal (mV)")
doc = i.preset("scientific.nature", format="double-column").document()
doc.add("a", p)
print(doc.compile().report())
# actual:   WARNING FONT_SUBSTITUTED ... 'Liberation Sans' ... expected 'Arial'
# expected: the same check, but a known metric-compatible substitute should be
#           reported as INFO (or accepted by name) rather than a WARNING, so a
#           clean figure stays clean on a machine without Arial
```

Workaround: none taken. The figures keep the preset as published and this
warning is recorded in `NOTES.md` as the only remaining diagnostic.

## Checked and fine (no issue)

* Review round: `legend(corner="ne", names=[...])` with a hollow scatter series
  gives a ring swatch and covers no data here. `text(..., anchor="se")` plus
  `arrow()` placed the 4 µm callout clear of the points and error bars. A
  `y` axis label on an 8.5 mm strip ("Added depth (ppm)") is not clipped.
  `annotate(..., side="n")` drew a diagonal leader that missed its own error
  bar in a minimal test; I did not find a case where it crosses one.
* `legend(names=[...], order="column", columns=2)` gives the published key
  order and column layout.
* `errorbars(..., cap=0)` with a scatter over it, and `scatter(hollow=True)`,
  both draw as intended and key correctly.
* `axes(x=None, ...)` with `x_options=dict(labels=False)` hides the tick labels
  and keeps the ticks, which is what a top panel above a shared axis needs.
* `CROWDING` lint caught two labels 0.96 mm apart, and moving them cleared it.

## Pass 2

Found 2026-10-17 while moving both figures to 89 mm with `axes="box"`. Repros
use `PYTHONPATH=<worktree>/src <venv>/bin/python`.

### 4. `doc.letters()` letters every cell, and there is no way to leave one unlettered

`letters({'name': 'a'})` names some cells, and every other cell takes the next
free letter. A flat grid of seven cells therefore gets seven letters. Here the
top panel is `a` and the six strips, meant to be one panel `b`, were lettered
`b` to `g`. Lint then reported CROWDING between the letter `e` and the axis
title. The only fix found was to nest the strips in a `subfigure()` that is one
named cell (`doc.letters({'observed': 'a', 'strips': 'b'})`). The docs say "to
skip a letter", which reads as skipping a cell, but it only skips a letter value.

```python
import inklet as i

doc = i.document(width=89, columns=1)
for k in range(3):
    p = i.plot_spec(60, 10, x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)], name='a')
    doc.add(f'c{k}', p, row=k)
doc.letters({'c0': 'a'})
f = doc.compile()     # c1 and c2 are lettered 'b' and 'c'; no diagnostic says so
# expected: a way to mark a cell as unlettered, or a note that the other
#           cells take letters, when names= leaves some cells unnamed
```

### 5. Lint suggests `corner='best'`, which can shrink a short plot to 58% of its width

For a 72.9 mm plot of only 26.9 mm height, `KEY_COVERS_DATA` on the top-left
corner suggests `corner='best'`. With that legend the key goes beside the plot
on the right, and the plot is drawn 42.5 mm wide, reported as
`PLOT_WIDTH_OVERRIDDEN`. The lint text does not say that `'best'` may move the key
outside, so the two suggestions contradict each other. The figure uses
`side='top'` instead.

```python
import inklet as i

doc = i.preset('scientific.nature', format='single-column', axes='box').document()
p = i.plot_spec(72.9, 26.9, x=(2.89, 5.67), y=(2.057, 2.311), clip=True)
names = ['No H_{2}O', 'No CO', 'No CO_{2}', 'No H_{2}S', 'No CH_{4}', 'No cloud', 'All opacity', 'Data']
for n in names[:7]:
    p.line([(3, 2.1), (5.5, 2.2)], name=n)
p.scatter([(3, 2.1), (4, 2.15)], size=1.3, color='#333', name='Data')
p.axes(x='Wavelength (µm)', y='Transit depth (%)')
p.legend(corner='best', names=names, order='column', columns=2)
doc.add('fig3', p)
print(doc.compile().report())   # PLOT_WIDTH_OVERRIDDEN: drawn 42.5 mm, authored 72.9 mm
```
