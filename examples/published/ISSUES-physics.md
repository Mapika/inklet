# inklet issues found while recreating ligo_gw150914 and hubble_1929

Found with the working tree at commit efd6144 plus local changes, 2026-10-07.
Status re-checked later on 2026-10-07: 1-4 are FIXED and the figures use the
new API; 5 and 6 are new and OPEN.

## 1. A key plate inside the plot hides data, and lint reports nothing

**FIXED.** Lint reports `KEY_COVERS_DATA` (warning) for both repros, naming
the series and how much is hidden, and suggests a clear corner or a wider
range. The LIGO y ranges and Hubble's `corner="se"` keep both figures clean.

`legend(corner=...)` draws the key on a knocked-out plate. When the plate
lands on data, the data under it are erased and `figure.report()` stays clean.

```python
import numpy as np, inklet as i
t = np.linspace(0, 1, 400)
p = i.plot_spec(80, 20, x=(0, 1), y=(-1, 1), clip=True)
p.line(np.c_[t, np.sin(40 * t)], name="Residual")
p.axes().legend(corner="sw")
doc = i.document(width=100); doc.add("a", p)
f = doc.compile(); print(f.report()); f.save("plate_line.png", dpi=200)
# actual:   "inklet lint: clean, 0 diagnostics"; the sine trough near x = 0.12
#           is cut out by the plate in the PNG
# expected: a warning (e.g. LEGEND_COVERS_DATA) naming the series and how much
#           is hidden, as DATA_OUTSIDE does for clipped data

q = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
q.scatter([(0.15, 0.9), (0.5, 0.5)], name="points").axes()
q.legend(corner="nw", entries=[("a long hand-written key entry", "#333333")])
doc = i.document(width=100); doc.add("b", q)
f = doc.compile(); print(f.report()); f.save("plate_point.png", dpi=200)
# actual:   clean; the point at (0.15, 0.9) is completely invisible
# expected: an error or warning: a whole data marker is hidden
```

Hit in both figures: the H1 residual panel (key over the trace) and the
Hubble plot (key over the N.G.C. 1068 disc), each found only by looking at
the PNG. Workaround: widen the y range (LIGO residual row −1.0…0.6) or move
the key (Hubble: `corner="se"`).

## 2. A hollow scatter marker gets an invisible key swatch

**FIXED.** `scatter(..., hollow=True)` draws paper-filled, series-outlined
rings, and the swatch is the marker as drawn (a per-call `stroke=` is
honoured too). `hubble_1929` now uses `hollow=True` and a plain `legend()`.

The swatch for a scatter series is the marker filled *and* stroked with the
series `color`, so per-call `stroke=` is ignored. A hollow marker
(`color="white", stroke=...`) gets a white swatch on a white plate.

```python
import inklet as i
p = i.plot_spec(60, 30, x=(0, 1), y=(0, 1))
p.scatter([(0.3, 0.4), (0.7, 0.6)], size=2, color="white", stroke="#8a5a00",
          stroke_width=0.3, name="group means")
p.axes().legend(corner="se")
doc = i.document(width=80); doc.add("a", p); doc.compile().save("hollow.png", dpi=200)
# actual:   key row "group means" with no visible swatch
# expected: an ochre ring, as drawn in the plot
```

Cause: `plot/series.py` `swatch_for()` does
`node.styled(fill=entry.color, stroke=entry.color)` and the series record
keeps no stroke. Related: there is no `hollow=True` on `scatter` (there is on
`swarm` and `stem`). Workaround in `hubble_1929/figure.py`: a hand-built key,
`legend(entries=[(name, i.overlay([invisible 4.5 mm rule, i.marker(...)]))])`.
The invisible rule keeps marker and line rows' labels aligned, because
`entries=` swatches are not centred in a common swatch width.

## 3. `Panel.line(dash=...)` fails with a raw `TypeError`, and only at compile

**FIXED.** `dash='dashed'|'dotted'|'dashdot'` (or a tuple in mm) works on
Panel marks, and unknown keywords are rejected at the call. `hubble_1929`
uses `dash="dashed"`.

The quick API takes `dash='dashed'`; the Panel method of the same name does
not, and the error comes from `Style.__init__` when the document compiles,
far from the call.

```python
import inklet as i
p = i.plot_spec().line([(0, 0), (1, 1)], dash="dashed")   # accepted here
doc = i.document(width=80); doc.add("b", p); doc.compile()
# actual:   TypeError: Style.__init__() got an unexpected keyword argument 'dash'
# expected: either accept dash='dashed'/'dotted' as i.line does, or raise at
#           the call with "use stroke_dash=(on, off) in mm"
```

Workaround: `stroke_dash=(1.6, 1.0)`.

## 4. (Minor, feature) No way to reorder an automatic key

**FIXED.** `legend(names=[...])` chooses and orders the rows. `ligo_gw150914`
lists L1 first, and `hubble_1929` uses it for its key order.

The key lists series in draw order. On the LIGO L1 panel the overlay (H1,
shifted) must be drawn first so L1 sits on top, but the original's key lists
L1 first. The only route is `entries=` with hand-built swatches, which loses
the automatic swatches (see issue 2). A `legend(order=[names...])` or
`z=`/`front=` on `line()` would cover it. Not worked around; noted in
`ligo_gw150914/NOTES.md`.

## 5. A `plus` (or `cross`) scatter marker ignores `color=` in the plot, but its key swatch uses it

**OPEN.** Found while simplifying `hubble_1929`.

```python
import inklet as i
p = i.plot_spec(60, 30, x=(0, 1), y=(0, 1))
p.scatter([(0.5, 0.5)], marker="plus", size=2.6, color="#c1121f", name="mean")
p.axes().legend(corner="se")
d = i.document(width=80); d.add("a", p); f = d.compile()
print(f.report())
# actual:   the plotted plus is stroked in the ink (#1a1a1a); the key swatch
#           is red (#c1121f); report: clean
# expected: the plotted marker in #c1121f, like a circle with color=
#           (and if they ever differ, KEY_MISMATCH)
```

Same for `marker="cross"`. Workaround in `hubble_1929/figure.py`: pass
`stroke=CROSS` as well as `color=CROSS`.

## 6. Key labels do not share a left edge when line and marker swatches differ in width

**OPEN.** Found while simplifying `hubble_1929`.

`legend()` stacks each row as swatch + gap + label, so a line swatch (about
4.5 mm wide) pushes its label further right than a marker swatch does, and
markers of different shapes differ again (`palmer_penguins` panel a:
"All species" against the marker rows, and the triangle row against the
circle and square rows).

```python
import inklet as i
p = i.plot_spec(60, 40, x=(0, 1), y=(0, 1))
p.line([(0, 0), (1, 1)], name="fit")
p.scatter([(0.3, 0.6)], name="points")
p.axes().legend(corner="se")
d = i.document(width=80); d.add("a", p); d.compile().save("key.png", dpi=300)
# actual:   "points" starts about 2 mm left of "fit"
# expected: swatches centred in one common width, labels aligned
```

The old hand-built Hubble key padded each marker with an invisible 4.5 mm
rule to align them; the plain legend now shows the offset.
