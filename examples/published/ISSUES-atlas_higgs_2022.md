# inklet issues found while recreating atlas_higgs_2022 (Figure 5)

Found with the worktree at commit 51ada61 (inklet 4.8.1), 2026-10-17. Each repro
was run with `PYTHONPATH=src` and the repository's `.venv` Python.

## 1. `errorbars(stroke=<list>)` crashes the SVG renderer

**Actual:** passing one colour per point to `errorbars` raises an uncaught
`AttributeError` when the figure is written:

```python
import inklet as i
p = i.plot_spec(60, 40, x=(0, 1), y=(0, 1))
p.errorbars([(0.3, 0.5), (0.7, 0.5)], yerr=[(0.1, 0.1), (0.1, 0.1)],
            stroke=["#ff0000", "#0000ff"])
doc = i.preset("scientific.nature", format="single-column").document()
doc.add("p", p)
doc.compile().to_svg()
# AttributeError: 'tuple' object has no attribute 'replace'
#   (render/svg.py, _escape)
```

**Expected:** either per-point colours work, as `scatter(color=<list>)` does, or
the call is refused with a message that names the argument. `figure.report()` is
silent in both cases.

**Workaround:** draw one `errorbars` and one `scatter` call per particle, each with
a single colour (`fig5.py`, `fig5_improved.py`).

## 2. A log-scale whisker cannot run down to zero

**Actual:** a lower bound of exactly 0 is a common outcome for a fitted coupling, and
the log axis rejects it:

```python
import inklet as i
p = i.plot_spec(60, 30, x=(0.05, 300), y=i.log((1e-4, 1)))
p.errorbars([(0.6, 8e-5)], yerr=[(8e-5, 7e-3)], cap=0.7)   # lower bound 0
i.preset("scientific.nature", format="single-column").document().compile()
# inklet.plot.scale.ScaleError: a log scale cannot place 0.0; ... use symlog()
```

The error is clear, but the suggested fix (`symlog`) changes the axis, which is
wrong here: the scale should stay logarithmic.

**Expected:** a way to say "this whisker runs to the panel edge" (for example
`yerr` down with `clip=True` allowed to reach 0, or a `floor=` option on
`errorbars`). The original figure does exactly this.

**Workaround:** pass the lower distance as `value - floor`, where `floor` is the
panel's lower limit, so the whisker ends at the axis. This is noted in the scripts
and in NOTES.md.

## 3. `legend(size=...)` suggests the wrong keyword

**Actual:**

```python
p.legend(corner="nw", size="7pt")
# TypeError: legend() got unknown keyword size= (did you mean side=?)
```

**Expected:** `did you mean font_size=?`. The key's text size is `font_size=`, and
`side=` is the key's placement, which is a different thing.

**Workaround:** `legend(..., font_size="7pt")`.

## 4. The meaning of `text(anchor=, offset=)` is not stated

**Actual:** the API line for `Panel.text` gives the signature only. The docs I read
do not say what `anchor` refers to, or in which direction `offset` moves the label.
Working it out from renders: `anchor` is the label's point of contact with the data
point (`"nw"` puts the label's top-left corner on the point, so the label sits below
and to the right), and a positive y in `offset` moves the label down, in millimetres.

**Expected:** one sentence beside the signature, with a small example.

## 5. `annotate(side=...)` placed a label off the axis

**Actual:** `top.annotate(x, y, "c", side="n", leader=False)` for the lowest point on a
log axis put the label on the panel's bottom edge. The lint reports the result as
`OFF_PANEL` (0.51 mm below the box). I could not tell from the docs whether `side`
names where the label goes or where its leader comes from, and the label moved
where I did not expect.

**Workaround:** place the label with `text(..., anchor=, offset=)` and check
`figure.report()`.

## 6. Label clearance: dense clusters get many `CROWDING` infos

**Actual:** the clearance is 1.00 mm, so every label within 1 mm of any mark is
reported. In the W/Z/t cluster of this figure (80 to 170 GeV, all within a few mm)
the report lists four to six `CROWDING` infos in both figures, even with the
labels on their clear sides, because the markers are close to each other.

**Expected:** an option to accept a clearance for one label (or for the cluster),
or an info that counts crowded labels rather than listing each one. The labels
are readable in the rendered PNG, but the lint cannot be made clean by placement
alone.

## 7. `INCONSISTENT_STROKE` names a path I cannot map to a setting

**Actual:** the faithful figure reports one element at 0.18 mm, at the path
`cell-top/0/24/0/1/0/1/0/0/1`, inside the particle-table inset. I set no 0.18 mm
stroke, and the path does not say which primitive it is (the inset's frame or a
tile's border, I suspect). The improved figure, which has no such inset, does not
report it.

**Workaround:** none found. The faithful figure keeps 0.18 mm, and NOTES.md records
it.

## 8. `FONT_SUBSTITUTED` on every `scientific.nature` figure without Arial

**Actual:** Arial is not installed on this machine, so every figure in the
`scientific.nature` preset gets a `FONT_SUBSTITUTED` warning (Liberation Sans is
used). Liberation Sans is metric-compatible with Arial, so the measured layout is
correct, but the warning appears on every run and in every figure.

The warning's own text mentions `expected_fonts=None`, which "accepts 'Liberation
Sans'". I did not test that option, and I did not find it in the docs I read.

**Expected:** a documented way to accept a metric-compatible substitute, for example
`font_family=` with a fallback list, or a preset option for it.

**Workaround:** none in the figure scripts. The warning is left in NOTES.md, as the
profile was not changed.

## Things that worked well

* Plotting the particle table as an inset built in millimetres (`i.plot_spec` with
  `x=(0, W)`, `y=(0, H)`, `rect()` and `text()`, placed with `top.inset(...,
  width=None, plate=False)`) made the key easy to place and to check against the
  original's pixels.
* `legend(entries=[(name, marker(...))])` takes diagram glyphs, so the key can show a
  hollow or dashed symbol that the series record cannot.
* `scatter(..., hollow=True)` and `stroke_dash=` on a line both worked first time.

## Pass 2

Found while revising the figure to the journal's look (89 mm, the original's ticks
and italics). Worktree at master b8b4e34, 2026-10-17.

### P2.1. A log axis under four decades writes plain numbers, not powers of ten

**Actual:** the x axis spans 0.046 to 300 GeV, 3.8 decades. A log axis with explicit
ticks writes `0.1, 1, 10, 100`. The original, and the journal's house style for this
figure, write `10^{-1}, 10^{0}, 10^{1}, 10^{2}`. The y axis writes powers because its
ticks run past four decades, so the two axes of one figure read differently.

```python
import inklet as i
p = i.plot_spec(77, 30, x=i.log((0.046, 300)), y=(0, 1))
p.axis("bottom", ticks=[0.1, 1, 10, 100])     # labels: 0.1  1  10  100
```

**Expected:** a preset or axis option that asks for powers of ten on a log scale
under four decades (for example `format="power"`), or a note in the log-scale docs
that `format=power_label` from `inklet.plot` is the way to do it.

**Workaround:** `from inklet.plot import power_label` and pass `format=power_label`
to the bottom axis. Both scripts do this.

### P2.2. `FONT_SUBSTITUTED` is now INFO (resolved)

Item 8 above: on master the warning is INFO, and `expected_fonts=None` is no longer
needed. The scripts do not use it. The info still appears without Arial installed,
and NOTES.md records that.
