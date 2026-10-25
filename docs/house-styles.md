# House styles for a figure set

A journal preset fixes what the journal asks for: page widths, type sizes,
fonts. Projects that keep a house style usually decide more than that. They use
one typeface for every figure, two or three line weights, one marker style,
named colours for the things they keep showing (groups, doses, sample sizes),
and one panel-letter style. They also have rules for text and keys, such as
"no grey annotation text" or "label series directly". Written as constants in
a style module outside inklet, these decisions get restated in every script,
and nothing reports which figure broke which rule.

`inklet.suite()` states them once as a `Suite`. Figure scripts draw through the
suite, `Suite.save` writes and lints each figure, and `Suite.build` builds a
whole set, skipping figures whose inputs have not changed.

![A four-panel figure drawn through one suite: response curves over time at four concentrations labelled at the line ends, a calibration scatter of three instruments onto y = x, standard error against sample size coloured by a sequential ramp, and bars with replicate marks, with a sample-size key under the panels](../gallery/house-style.png)

The complete script is [`examples/house_style.py`](../examples/house_style.py). All its data are synthetic.

## Define the suite

Each field has a default. The nested fields take a dict of the fields to
change.

```python
import inklet as i

house = i.suite(
    "lab",
    base="scientific.nature",                     # everything not stated here
    font="Helvetica, Arial, Nimbus Sans, Liberation Sans, sans-serif",
    ink="#222222",
    type=dict(tick=6, label=7, key=6, note=6, letter=8),        # pt
    lines=dict(data=0.6, fit=0.75, axis=0.5),                    # pt
    markers=dict(size=0.9, outline=False, ring=0.3),             # mm
    text=dict(bold="letters", muted=False, muted_colors=("#888888",), keys="outside"),
    palettes={"group": {"control": "#555555", "treated": "#0072b2"}},
    ramps={"size": {"n = 10": "#c6dbef", "n = 100": "#2171b5", "n = 1000": "#08306b"},
           "dose": "tol-ylorbr"},
    widths={"single": 89, "double": 183},
)
print(house.stroke("fit"), house.size("letter"), house.width("double"))
```

| Field | What it sets |
| --- | --- |
| `base` | A preset name or `Preset` for page geometry and journal limits. |
| `font` | The family list everything is measured in. The first installed family is embedded in PDF and SVG. TrueType and CFF OpenType (`.otf`) faces both embed as live text. |
| `allowed_fonts` | Families lint accepts (`FONT_SUBSTITUTED`). The default is the families named in `font`. |
| `type` | Sizes in pt for `tick`, `label` (axis titles), `key`, `note` (in-plot text and direct labels) and `letter`. |
| `lines` | Weights in pt for `data`, `fit` and `axis`, plus any `extra={"guide": 0.4}`. Lint allows only these weights in plot panels. |
| `markers` | Marker diameter in mm, whether filled markers have an outline, and the ring width of open markers. `min_contrast` deepens pale marker colours to that contrast on the paper. |
| `letters` | Panel-letter case and the gap to the panel. Panel letters are bold. |
| `text` | `bold="letters"` (bold only for panel letters), `muted=False` (no grey text), `muted_colors`, `label_contrast` (WCAG ratio for direct labels), `halo` and `keys="outside"` (no keys inside plot panels). |
| `palettes` | Categorical colours by name: `{key: colour}` or a sequence. |
| `ramps` | Sequential colours by name: an inklet ramp name, a list of stops interpolated in OKLab, or ordinal `{key: colour}` stops. |
| `widths` | Page widths in mm by name. |
| `export` | Formats, PNG dpi, text mode, `write="changed"` and `ids="document"`. See below. |
| `lint` | Extra `lint()` keywords, such as `min_font_pt` or `max_height_mm`. |

`house.customize(lines={"data": 0.5})` returns a copy with that field merged.
A dict merges into the nested style fields (`type`, `lines`, `markers`,
`letters`, `text`, `export`); `palettes`, `ramps`, `widths` and `lint` are
replaced whole. A suite is immutable: its mappings are read-only copies.
`house.fonts()` reports the file each style resolves to on this machine and
whether a PDF can embed it.

## Draw through it

A `with house:` block makes the suite's theme the active theme, so text,
panels and keys are measured in its font and sizes. The helpers return the
keywords or nodes for the house style:

```python
points = [(t / 10, 0.3 + 0.06 * t) for t in range(11)]
with house:
    p = house.panel(60, 40, x=(0, 1), y=(0, 1))
    house.axes(p, x="time (h)", y="response")             # tick/label sizes, axis weight
    p.line(points, **house.line("treated"))                # palette colour, data weight
    p.line([(0, 0.25), (1, 0.95)], **house.line("#222222", "fit"))
    p.scatter(points[::2], **house.mark("treated"))        # filled, no outline
    p.scatter([(0.5, 0.2)], **house.mark("control", hollow=True))   # ring in its own colour
    house.end_labels(p, {"treated": points[-1], "fit": (1, 0.95)},
                     colors={"fit": "#222222"})
```

`house.end_labels` writes each label just right of the point it names, in its
series colour. The colour is deepened along its own lightness until it reaches
`text.label_contrast` on the paper (`house.text_color`), and a grey series is
labelled in ink. Labels that would overlap are moved apart by the smallest
total distance that keeps them in order (`layout.label_search.stack`). For
curves drawn with `name=`, `Panel.label_lines` does the same from the curves.

`house.color("treated")` reads a palette, `house.ramp("dose")(0.7)` samples a
ramp, and `house.stops("size")` returns ordinal stops.
`house.marker("circle", "treated")` is a single marker for a hand-built key.
`house.label("text", role="key")` is a text node at a role's size, never bold.

## Lay out a page

`house.mosaic` is `inklet.panel_mosaic` with the suite's letters and a named
width. Letters in a row share one baseline, and the panels below them start at
the same height whether the letter is `a` or `b`. Its gap and margin default
to 3 and 2 mm; any `panel_mosaic` keyword overrides them.
`header_bounds="ink"` keeps the placement of inklet 4.9 and earlier, where
each letter was measured by its own ink.

```python
def panel(w, h):
    p = house.panel(w, h, x=(0, 1), y=(0, 1))
    house.axes(p, x="x", y="y")
    p.line(points, **house.line("treated"))
    return p

with house:
    page = house.mosaic(["a b", "c c"], {"a": panel, "b": panel, "c": panel}, height=90)
```

`house.document()` starts the suite preset's live `Document` for figures laid
out on a column grid; its panel letters follow the base preset's letter style. `house.figure()` is a plain page at a named width on the
suite theme.

## Save and check

```python
result = house.save(page, "dose_response", out="figures")
print(result.summary())
```

`save` writes `figures/dose_response.svg`, `.pdf` and `.png` and returns a
`SaveResult` with the paths, whether anything was written, the height and the
lint diagnostics. The export defaults are:

* `text="embed"`: PDF text is live TrueType (CIDFontType2, "Type 42") and SVG
  text carries a subset of each face. No font-file path is written into the
  SVG, even when `font` names a file.
* `write="changed"`: when every file's bytes would be unchanged, nothing is
  written and the timestamps are kept. When any file changes, the whole set is
  rewritten with one modification time.
* `ids="document"`: SVG element ids are numbered per file, so a figure's bytes
  do not depend on what was built before it in the same process. These ids are
  not the node ids the layout editor and viewer map elements back to; set
  `export={"ids": "nodes"}` for SVGs those tools will open.

Lint runs with the base preset's limits, the suite's fonts and its house
rules (`Suite.lint_rules()`). The house rules add five warning codes:

| Code | Reported when |
| --- | --- |
| `STROKE_TIER` | An author's stroke inside a plot panel is not one of the `lines` weights. Axis, key and colour-bar strokes are not counted. |
| `MARKER_OUTLINE` | A filled marker has an outline in another colour (`markers.outline=False`). |
| `MUTED_TEXT` | Text is grey (low OKLab chroma, lighter than slate ink) or in `text.muted_colors` (`text.muted=False`). |
| `BOLD_TEXT` | Bold text is not a panel letter (`text.bold="letters"`). |
| `KEY_IN_PANEL` | A legend, size key or colour bar is part of a plot panel, over the data or beside it, rather than one shared key outside the panels (`text.keys="outside"`). |

The same rules can be used without a suite:
`inklet.lint(node, house=inklet.diagnostics.HouseRules(bold="letters"))`.
`house.check(figure)` lints without saving. A finding you keep on purpose can
be acknowledged with `expect={"KEY_IN_PANEL"}`, as for any other lint code.

## Build a figure set

```python
def figure_one():
    with house:
        return house.mosaic(["a b"], {"a": panel, "b": panel}, height=45)

report = house.build({"dose_response": figure_one}, out="figures")
print(report.ok)
```

`build` takes `{name: callable}` or `{name: "module:function"}` (the default
function is `make_figure`). For each figure it computes a fingerprint from
the suite, the figure's function (its qualified name, any `functools.partial`
arguments and its source file), `depends=` (files every figure reads, such as
a style module), `inputs={name: [data files]}` and the inklet version. A
declared file that is missing fails that figure. A
figure whose fingerprint matches the last build in `out/.inklet-build.json`
and whose files exist is reported as `unchanged` and not built. Data files
that are not listed in `inputs` are not seen, so pass `force=True` after
changing one.

`isolate=True` (the default) restores `sys.path` after each figure and forgets
the project modules it imported. Modules from the standard library,
site-packages and inklet stay cached. Two figure modules that import different helper modules of the same
name, from different directories, then each get their own. A figure that
raises is reported as `failed` with its traceback, and the remaining figures
are still built. The printed table lists each figure's status, height, lint
counts and the house rules it breaks.

## Limits

* The house rules check what lint can see in the built tree. A colour baked
  into a raster image, or text drawn as outlines by the author, is not checked.
* `STROKE_TIER` checks strokes inside plot panels only. Strokes in schematics
  built with `place()` are not checked, because their weights are usually set
  for the drawing.
* `Suite.build` decides whether a figure changed from the files it is told
  about. It does not trace data reads, other modules the figure imports, font
  files or installed libraries; pass `force=True` after changing those.
* A `with house:` block sets the process-wide theme, so suites are not for
  use from several threads at once.
