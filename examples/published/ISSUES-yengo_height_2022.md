# inklet issues found while recreating Yengo et al. (2022), Figures 1 and 2

Found with the worktree at commit 51ada61 (inklet 4.8.1), 2026-10-17. Each
entry has a minimal repro where one could be made; the workaround is what the
figure scripts do now.

## 1. Default tick thinning crashes compile when explicit labels are dropped

Explicit x ticks with a per-tick `format` and `rotate=90`, on a width where some
labels must be thinned, make `doc.compile()` fail with an `AttributeError`
inside `plot/axis.py`. It happened on the real chromosome centres of Figure 2
(chromosomes 21 and 22 are narrow). The minimal repro is below; the traceback
ends in `line 320, in <genexpr>: "labels": tuple("".join(line.text for line in
texts[j].prim.lines)`, with `'NoneType' object has no attribute 'lines'`.

```python
import numpy as np
import inklet as i

LENGTH_MB = [249.25, 243.20, 198.02, 191.15, 180.92, 171.12, 159.14, 146.36,
             141.21, 135.53, 135.01, 133.85, 115.17, 107.35, 102.53, 90.35,
             81.20, 78.08, 59.13, 63.03, 48.13, 51.30]
OFFSET = np.concatenate([[0.0], np.cumsum(LENGTH_MB)[:-1]])
centres = list(OFFSET + np.array(LENGTH_MB) / 2)
names_at = {round(c, 6): str(n + 1) for n, c in enumerate(centres)}
p = i.plot_spec(170, 40, x=(0, float(sum(LENGTH_MB))), y=(0, 30))
p.scatter([(1, 1)], size=1)
p.axes(x="Chromosome", x_options=dict(ticks=centres,
       format=lambda v: names_at[round(v, 6)], rotate=90))
doc = i.preset("scientific.nature", format="double-column").document()
doc.add("a", p)
doc.compile()          # AttributeError: 'NoneType' object has no attribute 'lines'
```

* Actual: `AttributeError`; the warning "axis omitted 11 of 22 explicitly
  supplied ticks" is printed first, then the crash.
* Expected: either the thinned ticks are skipped cleanly, or the thinning is
  reported and the figure builds.
* Workaround: `thin=False` in `x_options` (keeps all 22 labels, which fit
  rotated at 183 mm). The Figure 2 scripts use it.

## 2. A second `legend()` call adds a second key; the guide says it updates the first

The guide's method table says `legend(...)` is "the key; updates the one already
drawn". In fact a second call on the same panel draws a second key, in its own
corner. Repro:

```python
import inklet as i

p = i.plot_spec(70, 50, x=(0, 10), y=(-1, 1), clip=True)
p.scatter([(1, 0.5), (2, -0.5)], color="#1E90FF", size=1.5, name="Group A")
p.scatter([(3, 0.2), (4, -0.2)], color="#DAA520", size=1.5, name="Group B")
p.line([(0, 0.8), (10, 0.8)], stroke="#B2182B", name="Curve X")
p.line([(0, -0.8), (10, -0.8)], stroke="#FF7256", name="Curve Y")
p.axes(x="x", y="y")
p.legend(corner="ne", names=["Group A", "Group B"])
p.legend(corner="se", names=["Curve X", "Curve Y"])
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", p)
doc.compile().save("two_keys.png", dpi=200)   # two keys: ne and se
```

* Actual: two keys are drawn (the output does show both). The guide's wording
  suggests the second call would replace the first.
* Expected: whichever is intended, documented. Two keys per panel is exactly
  what Figure 1 needs (five P-value classes plus two power curves), so the
  guide wording should say it adds a key.
* Workaround: none needed; the figure uses two calls.

## 3. Lint CROWDING message with a clearance that does not match the picture (not reproduced)

During a build of `fig2.py` (before the final key placement), lint reported that
the key label "Hispanic ethnicities or ancestries" was 0.24 mm from a data
triangle at y = 12.5. In the PNG the label sits at y = 25 and the nearest mark is
about 18 mm away. The message went away after the key's label offset and the
plot height were changed, so I could not reproduce it in isolation. Recorded
because the distance it reports does not match the rendering.

* Actual: `CROWDING ... only 0.24mm apart (the nearest of 2 marks within the clearance)`.
* Expected: no message, or a distance that matches the drawn positions.
* Workaround: none needed in the final version.

## 4. A 36,000-square vector scatter gives a 10.8 MB SVG

Figure 2 draws each SNP as squares from 0 to its density: about 36,000 markers.
Two series (odd and even chromosomes) each stay under the 20,000-point raster
threshold, so `scatter()` keeps them vector. The faithful SVG is 10.8 MB, and the
improved SVG is 5.6 MB. Passing `raster=True` to those series gives a 183 KB and
158 KB SVG, with the PDF and PNG unchanged in appearance.

```python
import numpy as np
import inklet as i

rng = np.random.default_rng(0)
x = rng.uniform(0, 3000, 36000)
heights = rng.integers(0, 3, 36000)
pts = [(float(a), k) for a, h in zip(x, heights) for k in range(int(h) + 1)]
half = len(pts) // 2                      # two series of ~36k markers in total
p = i.plot_spec(170, 40, x=(0, 3000), y=(0, 30))
p.scatter(pts[:half], marker="square", size=0.8, color="#DAA520", stroke="none")
p.scatter(pts[half:], marker="square", size=0.8, color="#000000", stroke="none")
p.axes(x="Position", y="Density")
doc = i.preset("scientific.nature", format="double-column").document()
doc.add("a", p)
doc.compile().save("dense.svg")   # 10.9 MB; with raster=True on both scatters, 30 KB
```

* Actual: a 10.9 MB vector SVG for 72,000 markers in this repro (10.8 MB for the
  real Figure 2 scripts).
* Expected: either the raster threshold counts the whole figure's markers, or
  the docs suggest `raster=True` for dense square or glyph layers.
* Workaround: `raster=True` on the square layers (both Figure 2 scripts).

## 5. Lint FONT_SUBSTITUTED is noisy in environments without Arial (environment, not a library bug)

The Nature preset expects Arial. The sandbox has only Liberation Sans, which is
metric-compatible with Arial, so every build reports 20–46 text primitives as
`FONT_SUBSTITUTED` and asks to "install 'Arial'". The message's own suggestion
is `expected_fonts=None`, which it says accepts Liberation Sans; I did not
change the scripts to use it.

* Actual: one WARNING per build, listing dozens of primitives.
* Expected: a metric-compatible fallback reported as INFO, or a preset option
  that accepts it without a warning.
* Workaround: none applied. All four figures report this single warning and
  nothing else.

## 6. Default tick format writes zero as "0.0" when the other ticks have a decimal

With explicit y ticks that include 0 and have one decimal (-0.3 ... 0.3), the
default formatter labels the zero tick "0.0", while the original labels it "0".
This is consistent with the other ticks (one decimal everywhere), so it may be
intended. It is still awkward: getting "0" needs a callable `format=` on that
axis, which the guide does not mention.

```python
import inklet as i

p = i.plot_spec(70, 50, x=(0, 1), y=(-0.3, 0.3))
p.scatter([(0.5, 0.1)], size=1)
p.axes(y_options=dict(ticks=[-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]))
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", p)
doc.compile().save("ticks.png", dpi=200)   # zero label reads "0.0"
```

* Actual: the zero tick reads "0.0" (seen in `fig1.py` before the fix).
* Expected: either a way to say "zero is written as 0" in the axis options, or
  the guide says that a `format=` callable is the way to do it.
* Workaround: `format=y_label` in `fig1.py` and `fig1_improved.py`, where
  `y_label` writes 0 as "0" and uses U+2212 for minus.

## Pass 2

Found on master at b8b4e34, while redoing figures 1 and 2 at print size.

### 7. A second `legend()` call on one panel silently replaces the first key

Issue 2 no longer reproduces: on master, the second `legend()` call replaces the
first, as the `Panel.legend` docstring says ("A later `legend()` call replaces
the options of the one before it"). The first key is dropped, and no lint
message names it. Repro (`two_keys.py`):

```python
import inklet as i

p = i.plot_spec(70, 50, x=(0, 10), y=(-1, 1), clip=True)
p.scatter([(1, 0.5), (2, -0.5)], color="#1E90FF", size=1.5, name="Group A")
p.scatter([(3, 0.2), (4, -0.2)], color="#DAA520", size=1.5, name="Group B")
p.line([(0, 0.8), (10, 0.8)], stroke="#B2182B", name="Curve X")
p.line([(0, -0.8), (10, -0.8)], stroke="#FF7256", name="Curve Y")
p.axes(x="x", y="y")
p.legend(corner="ne", names=["Group A", "Group B"])
p.legend(corner="se", names=["Curve X", "Curve Y"])
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("a", p)
doc.compile().save("two_keys.png", dpi=200)
```

* Actual: only the "Curve X / Curve Y" key is drawn. "Group A" and "Group B" are
  gone. The lint warning is KEY_COVERS_DATA for the second key only.
* Expected: either both keys, or a lint warning that the first key was replaced.
  Figure 1 has two keys in the original (five P-value classes and two power
  curves), so a second key on one panel is needed.
* Workaround in `fig1.py`: the class key is the panel's legend, and the two
  power curves are line swatches with text labels in the lower right.

### 8. `plot_spec` cannot place a diagram built from its own panel

`plot_spec` records calls and replays them on a panel, so `point()` is not
available while the spec is being built. The obvious way to place a second key
in the plot therefore fails:

```python
import inklet as i

p = i.plot_spec(72, 50, x=(0, 50), y=(-0.3, 0.3))
p.place([(p.point(40.0, -0.25), p.key_diagram(names=["x"]))])
# AttributeError: point   (document/spec.py, __getattr__)
```

* Expected: a spec-level form of `point()` or `place()`, or a note in the
  `plot_spec` docs that such placement needs a `Panel`.
* Workaround: `p.line(...)` and `p.text(...)` in data coordinates.

### 9. `corner="auto"` finds no placement where a fixed corner with a tighter row gap is clear

The five-entry class key on the 72 × 50 mm plot of figure 1, with the
power-curve swatches in the lower right:

* `p.legend(corner="ne", names=...)`: KEY_COVERS_DATA, two markers under the key
  at MAF 42.8% and 44% (y 0.07 and 0.08).
* `p.legend(corner="auto", names=...)`: `DiagramError: no clear legend/content
  placement found`.
* `p.legend(corner="ne", row_gap=0.4, names=...)`: no warning. The key is clear.

Expected: `corner="auto"` tries the tighter spacing before it gives up, or its
error names the spacing it could have used. Workaround: `corner="ne"` with
`row_gap=0.4`, as in `fig1.py`.
