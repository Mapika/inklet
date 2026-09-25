# Migration

<span id="migrating-to-inklet-31"></span>

## From 4.3 to 4.4

4.4 is the deprecation release before 5.0. Nothing is removed and every 4.3
recipe still runs. Each old spelling now raises
`inklet._compat.InkletDeprecationWarning`, a `DeprecationWarning` subclass.
The warning points at your line and names the replacement. Everything in the
table below goes in 5.0.

Two changes alter figure output without a warning: the
[default series colours](#default-series-colours) of the `nature` and
`notebook` themes, and the [label positions](#label-placement) chosen by
`Panel.label_points`.

To find every deprecated spelling in a project, run it or its tests with the
warning turned into an error:

```text
python -W error::DeprecationWarning my_figure.py
pytest -W error::inklet._compat.InkletDeprecationWarning
```

To silence only Inklet's warnings while you migrate, filter on that class:
`warnings.filterwarnings("ignore", category=InkletDeprecationWarning)` after
`from inklet._compat import InkletDeprecationWarning`.

### Import paths

| Old (warns) | New |
| --- | --- |
| `inklet.experimental.volume`, `.sections`, `.slabs`, `.regions`, `.channels`, `.contours`, `.measurements`, `.tiff` | `inklet.volume` |
| `inklet.experimental.selection` | `inklet.selection` |
| `inklet.experimental.temporal` | none. `KeyedTable` converts dates itself; `inklet.experimental.browser.timeaxis` still exports `time_value`, `time_seconds` and `time_milliseconds` |
| `inklet.experimental._table_adapters` | `KeyedTable.from_pandas()` / `KeyedTable.from_polars()` |
| `inklet.experimental.project`, `.project.assets`, `.project.identity` | `inklet.project`, `inklet.project.assets`, `inklet.project.identity` |
| `inklet.experimental.layout_editor` | `inklet.editor` |
| `inklet.experimental.scene_viewer` | `RenderScene.to_html()` |
| `inklet.experimental.engineering` (`BoxComponent`, `BoxAssembly`) | none. Removed in 5.0; pin `inklet<5` for recipes that use it |

The old modules now re-export only Inklet's own names. The standard-library
names they used to expose, such as `json` or `dataclass`, are gone. These were
never part of a released `__all__`.

### American spelling and one keyword per idea

Public names now use American spelling. Panel keywords follow one rule:

- `color=` sets the colour. It takes one colour, or a sequence or mapping with
  one colour per series or group.
- `name=` sets the legend name. It takes one string for a single series, or a
  sequence with one name per series.
- `size=` sets the mark size.
- `**style` collects the extra keywords of methods that take `Style` fields,
  such as `stroke=` or `fill=`.

A handful of methods (`annotate`, `axes`, `axis`, `bracket`, `brackets`,
`colorbar`, `inset`, `label_points`, `ribbon`, `at_risk`, `twin_x`, `twin_y`)
pass their extra keywords on to another helper as options. Those keep
`**kwargs`. Renaming a `**` parameter would break released call shapes, so no
rename was made there. `label=` is text drawn on the figure and never names a
series.

| Old (warns) | New |
| --- | --- |
| `Panel.bars(colors=, names=)` | `Panel.bars(color=, name=)` |
| `Panel.stackarea / dumbbell / volcano / split_violin(colors=, names=)` | `(color=, name=)` |
| `Panel.hist / boxplot / violin / swarm / ridgeline / raincloud / dendrogram / kaplan_meier(colors=)` | `(color=)` |
| `Panel.embedding(colors=, centre=)` | `Panel.embedding(color=, center=)` |
| `Panel.dotplot(sizes=, colors=)` as keywords | `Panel.dotplot(size=, color=)`. Positional calls are unchanged and do not warn. A string `color=` paints every dot, as before |
| `PolarPanel.pie / breakout(colors=, names=)` | `(color=, name=)` |
| `PolarPanel.centre` | `PolarPanel.center` |
| `inklet.text_on_arc(centre=)`, `inklet.typeset.onpath.text_on_arc / baseline_arc(centre=)`, `inklet.draw.shapes.arc_cubics(centre=)` | `center=`. `baseline_arc`'s positional fourth argument is unchanged |
| `inklet.plot.raster.uniform_pitch(centres=)` | `centers=` |
| `inklet.plot.cluster_centres` | `inklet.plot.cluster_centers` |
| `inklet.plot.embedding.CENTRE_METHODS` | `CENTER_METHODS` |
| `inklet.plot.matrix.matrix_centres`, `default_colouring` | `matrix_centers`, `default_coloring` |
| `inklet.diagnostics.image.average_colour` | `average_color` |
| `inklet.assets.Harmonise` | `inklet.assets.Harmonize` |
| `inklet.assets.harmonise.as_harmonise`, `harmonise` | `as_harmonize`, `harmonize` |

Giving an old keyword and its new spelling in the same call raises `TypeError`.
Option values keep their spelling: `anchor="centre"`, the `"grey"` CSS colours
and the saved `"harmonised"` asset metadata are data, not API names.

Some names stay as they are for 4.x. `Plane(centre_xyz=)` in `inklet.volume`,
and `Length(metres=)` and `Length.between(metres_per_unit=)` in
`inklet.experimental.figure_planner`, are positional dataclass fields. They
are also written into saved section and planner data, so renaming them waits
for 5.0 and a new schema.

The plots added in 4.4 (`treemap`, `network`, `waterfall`, `slope` and the
rest) were never released with plural keywords, so they take `color=`,
`name=` and `size=` directly and have no aliases. `network` and
`arc_diagram` take node values as `size=` and their label font size as
`label_size=`.

### Default series colours

The `nature` and `notebook` themes now colour series with the
[`inklet` palette](palettes.md#default-series-colours) instead of Okabe-Ito
(`nature`) and Tol's muted set (`notebook`). `slides` keeps Tol's bright set.
Figures that relied on the automatic series colours change colour; explicit
`color=` values, presets and the accent colour do not. To keep the 4.3
colours, use the theme with its old palette:

```python
import inklet as i
from inklet.themes import NATURE, NOTEBOOK

nature_43 = NATURE.with_palette("okabe-ito")
notebook_43 = NOTEBOOK.with_palette("tol-muted")
i.use_theme(nature_43)                          # new panels use it
fig = i.figure(width=89, theme=nature_43)       # and so does the figure
```

### Label placement

`Panel.label_points`, and the labels drawn by `volcano(labels=...)` and the
embedding scatters, now use the joint placement engine
(`inklet.layout.label_search`). The call and its keywords are unchanged, but
the labels land in different places than in 4.3:

- labels are chosen together (greedy start, best response, seeded annealing
  and a pair repair pass) rather than one after another, so a label may sit on
  a different side of its point;
- bands and filled areas are measured by their outline rather than their
  bounding box, so labels may now sit in the empty part of a band's box, and
  legends count as obstacles;
- a label with no room nearby moves further out on a hairline leader instead
  of staying in an overlap, and leaders no longer cross each other or run
  through labels;
- fewer labels end up in the `point_labels` note's `unresolved` list, and the
  note gains `covering_marks`. Dense label sets place much faster.

Placement is still deterministic: the same figure gives the same positions on
every run. There is no option to restore the 4.3 placement. To keep a 4.3
layout exactly, pin `inklet==4.3.0` for that recipe, or place the few labels
that matter yourself with `annotate`. `place_labels` and `label_plan` keep
their `"greedy"` default; the joint search there is opt-in with
`method="joint"`. The new `LABEL_UNPLACED` lint warning names any label a
placer could not resolve.

### Experimental classes and saved files

- `inklet.experimental.browser.BrowserScatter(table, views)` warns. Use
  `BrowserFigure(table, views, columns=len(views))`, which it already returned.
- Composition layout files written with schema `inklet.composition-layout/0.1`
  to `0.4` still load, but warn. Re-save them to write `0.5`:
  `composition.layout_overrides(base)` does this, and so does saving from the
  layout editor. Inklet 5.0 may not read the older versions.

## From 4.2 to 4.3

4.3 moves the microscopy, selection, project and editor APIs out of
`inklet.experimental` into stable packages. Nothing is removed: the old import
paths still work and return the same objects. They do not warn in 4.3, and
they warn from 4.4 ([above](#from-43-to-44)). They will not be removed before
5.0. Saved-file schema identifiers are unchanged, so existing selections,
asset inventories and project bundles load as before.

| Old import (still works) | New import |
| --- | --- |
| `inklet.experimental.volume` (`Volume`, `Slice`) | `inklet.volume` |
| `inklet.experimental.sections` (`Plane`, `SampledSection`, `reslice`) | `inklet.volume` |
| `inklet.experimental.slabs` (`Slab`, `SlabProjection`, `project_slab`) | `inklet.volume` |
| `inklet.experimental.regions` (`BoxRegion`) | `inklet.volume` |
| `inklet.experimental.channels` (`Channel`, `Composite`) | `inklet.volume` |
| `inklet.experimental.contours` (`LabelContour`) | `inklet.volume` |
| `inklet.experimental.measurements` (`LabelMeasurements`, `measure_labels`) | `inklet.volume` |
| `inklet.experimental.tiff` (`TiffImage`, `read_tiff`) | `inklet.volume` |
| `inklet.experimental.selection` (`KeyedTable`, `SelectionState`, `RebasedSelection`) | `inklet.selection` |
| `inklet.experimental.project` (`FigureProject`), `.project.assets` (`Asset`, `AssetManifest`), `.project.identity` (`EntityMap`) | `inklet.project` |
| `inklet.experimental.layout_editor` (`LayoutEditor`) | `inklet.editor` |
| `inklet.experimental.scene_viewer` | `RenderScene.to_html()`; the runtime is private (`inklet.render._viewer`) |

`import inklet` still does not import `inklet.volume` or its dependencies;
import the package you use. Browser documents, fields, grids, engineering
drawings, image measurement and the figure planner stay in
`inklet.experimental` (see [experimental features](experimental.md)).

Behaviour change: `FigureProject.open(..., verify_export=True)`, the default,
now opens a project whose reconstructed SVG differs from the saved digest. It
emits `inklet.project.ExportDriftWarning` and records the comparison in
`project.open_report`. Pass `verify_export='strict'` for the previous
`ValueError`, or turn the warning into an error with the `warnings` module.

## From 4.1.0 to 4.2.0

4.2.0 adds plot types and finishes several layout behaviours. Existing recipes
run unchanged. Pin `inklet==4.1.0` to keep the previous output.

Output changes:

- `share_plot_margins=True` with an automatic page height shares data heights
  along each row only, so rows keep the heights set on their plots. Before, every
  plot got the tallest data height in the grid. Pass `share_plot_margins='all'`
  for the previous rule.
- `Panel.label_points` places its labels when the panel is built, clear of
  marks drawn after the call as well. Output is unchanged when nothing is drawn
  after the call. The label node and its `point_labels` note exist only after
  `build()`; until then `_over` holds an empty placeholder. A wrong number of
  labels is still refused at the call.
- `PolarPanel.breakout` also turns a pie that shares its panel with other
  content, when `polar()` was given no `zero` or `winding`. The other content
  is drawn again under the turned angles. Pass `zero=` and `winding=` to
  `polar()` to keep the pie as drawn.
- Pie labels outside the rim search nearby spots before moving far out, and
  get a hairline leader to their slice when they end up away from it. The
  `pie_labels` note lists them under `leaders`.
- `radar_grid(values=True)` places ring values in the clearest spoke gap when
  the panel is built, on a paper halo, and drops values that cannot stay clear
  of the data. The default stays off.
- `examples/dense_figure.py` turns on `share_plot_margins`.

## From 4.0.1 to 4.1.0

4.1.0 adds plot types and changes several presentation defaults. Existing
recipes run unchanged, but pages can come out smaller or differently spaced.
Regenerate a representative figure and compare it with the archived output
before replacing files. Pin `inklet==4.0.1` to keep the previous output.

Default output changes:

- `scientific.general`, `scientific.science` and `scientific.cell` use 7 pt
  text over 6 pt ticks and keys (was 8/7 pt). `scientific.cell` is now a dense
  page preset: 6/5 pt type, 0.25 pt hairlines, smaller gaps and in-plot legends.
- Ticks are shorter, axis names sit closer to the tick labels, outside legends
  and colorbars sit one `xs` step from the plot, and colorbars are thinner.
- `share_plot_margins=True` shares top and bottom margins within each row and
  left and right margins along each vertical grid line, instead of across the
  whole grid. Pass `share_plot_margins='all'` for the previous rule.
- Top and bottom legends can use the whole panel width when that saves rows.
- `matrix()` without `ramp=` uses a default colour ramp: reversed magma for
  one-sided data, blue-white-red when the data cross zero or `center=` is given.
  An explicit `ramp=` keeps its previous meaning.
- A heatmap axis with no ticks draws no spine; pass `spine=True` to keep it.
- Orthogonal links leave and enter through the face of their anchors, and
  labels on short links move to the nearest clear spot (lint `LABEL_OFF_LINK`).
- Bold panel letters are embedded with the bold face.
- `polar()` leaves `zero` and `winding` unset by default; they still resolve to
  east and counter-clockwise. `PolarPanel.breakout` turns the pie to face its
  bar only when neither was given.

New plot types are listed in the [changelog](https://github.com/Mapika/inklet/blob/master/CHANGELOG.md).

## From 4.0.0 to 4.0.1

4.0.1 is an engine maintenance release. Existing authoring recipes and export
calls continue to work. Upgrade with `python -m pip install --upgrade inklet`,
or pin `inklet==4.0.1` with the extras your workflow needs.

`CompiledFigure.build()` now exposes its resolved placements through a read-only
mapping. Code that only reads placements needs no change. If you previously
mutated that mapping, move those edits to the document or composition and
compile again; editing a placement mapping is not a supported layout workflow.
Compiled exports also retain the font selections from compilation. Recompile
the authoring document when you want an updated snapshot.

Review a representative SVG/PDF pair with your usual fonts and renderers before
replacing archived outputs. See [export and review](export-review.md) for revision
comparison and [the authoring model](concepts.md#compilation) for snapshot behavior.

## From 3.1 to 4.0

**4.1.0 is stable.** Upgrade with `python -m pip install --upgrade inklet`,
or pin `inklet==4.1.0` for reproducible environments.

Existing `figure()`, `document()`, `panel()`, `plot_spec()`, compositions and
SVG/PDF exports remain the authoring path. There is no required conversion to a
browser document or figure project. Keep existing recipes and first regenerate
a representative figure with the same fonts, dimensions and source data.

| Existing workflow | 4.0 action |
| --- | --- |
| Static 3.1 recipe | Run it unchanged, then review layout and vector output |
| Dense vector matrix | Review rendered equivalence; compact PDF operators change output bytes and size |
| PNG or raster layers | Keep the `render` extra and installed fonts |
| Blender scenes | Keep the separate tested Blender installation and source assets |
| Linked selection | Use `inklet.selection` (4.3; `inklet.experimental.selection` before) with the experimental `.browser`; supply explicit stable row IDs |
| Saved composition edits | Keep the Python recipe alongside the JSON overrides; reconcile missing targets explicitly |
| Reusable project bundle | Use `inklet.project` (4.3; `inklet.experimental.project` before); retain the trusted recipe, source files and dependency versions |

New scientific layout options are explicit: use measured legends, colourbars,
`Panel.placed()` and `Panel.guide()` when the figure needs them. Existing recipes
do not need these options. See [scientific authoring](scientific-authoring.md).

Exports are not promised to be byte-identical across package versions. Dev16's
PDF changes preserve the tested rendered geometry while changing serialization.
Compare pixels and geometry with the same renderer and fonts before accepting
new baselines; keep explicit colours, typography and placement decisions.

### Saved files from development previews

Do not rename a JSON schema to make it load. Composition-layout readers accept
versions 0.1 through 0.5; new files use 0.5. A missing composition target is a
revision conflict, not a format upgrade. Use the documented `missing='drop'`
policy only after reviewing the returned orphan/removal report.

Project bundles record the Inklet version, asset hashes, selections and layout
choices. Opening checks source bytes before invoking your trusted recipe, then
checks the reconstructed SVG by default. A changed font, dependency or recipe
can fail that final check even if the bundle schema still loads. Reproduce the
original environment first; use `verify_export=False` only for an intentional,
reviewed reconstruction and save the revised result separately.

[Compatibility](compatibility.md#api-and-saved-file-policy) defines the 4.0 scope
and saved-file policy. Experimental imports remain experimental in 4.0; a stable package release
does not silently promote them into the stable top-level API.

### Recorded migration checks

The released 3.1.0 and RC1 wheels were installed in isolated environments on the
same Linux host. RC1 retains all 204 top-level exports; review of 450 callable
signatures found 12 additions and no removed public parameters or newly required
arguments. This checks call shapes, not every default value or semantic behavior.

The unchanged publication example rendered pixel-identically at its original
width and at 190 mm. A bundle written by the published dev16 wheel reopened in
RC1 with strict SVG verification, its selected entity and its saved placement
intact. These are representative checks with fixed fonts and dependencies;
[recorded measurements](assets/core-performance/migration-rc1.json) identify the
recipe, environment and output hashes.

CI checks the captured 3.1 and 4.2 API inventories and the archived dev16
project, layout and selection files. The fixtures include released-wheel URLs and hashes;
they are not regenerated by tests. Run the checks from a checkout:

```sh
python tools/check_compatibility.py --output out/compatibility.json
python -m pytest -q tests/test_compatibility.py
```

## From 3.0 to 3.1

Existing 3.0 plotting, document, diagram, scene and export APIs remain supported.
Upgrade the core package with `python -m pip install --upgrade inklet`, or use
`python -m pip install --upgrade 'inklet[render]'` for PNG and raster layers.
Python 3.11 remains the minimum supported version.

The default axis rules are lighter, and top/bottom legends choose columns using
measured space. Axis font overrides now affect measurement and tick thinning.
These changes can alter an existing figure's appearance and panel margins.
Review regenerated artwork; preserve intentional choices with explicit stroke,
font and legend-column options rather than assuming pixel-identical defaults.

Dense raster scatter, repeated-image exports and fixed-component layout reuse
are improved. Vector lines keep every authored vertex by default. To opt into
physical-tolerance reduction, pass `simplify='0.02mm'` to a straight, open line;
see [dense data](dense-data.md) for the approximation's limits.

This example uses the new line and measured-axis controls:

```python
import math
import inklet as i

points = [(k / 1000, math.sin(k / 1000)) for k in range(6001)]
p = i.plot_spec(x=(0, 6), y=(-1.1, 1.1), height=35)
p.line(points, simplify='0.02mm', stroke='#176b9b')
p.axis('bottom', label='Time / s', tick_font_size='8pt', label_font_size='9pt')
p.axis('left', label='Response', tick_font_size='8pt', label_font_size='9pt')
doc = i.document(width=100)
doc.add('signal', p)
figure = doc.compile()
figure.save('migration-31.svg', 'migration-31.pdf')
assert not any(d.severity == 'error' for d in figure.diagnostics)
```

![A four-panel review of line reduction, axis typography and matrix labels](../gallery/plot-engine-review.png)

The [plot rendering review](plotting-engine.md) shows these controls in a complete
figure, with its source and separate manuscript caption.

NumPy array inputs are now copied when recorded, so later edits to the original
array do not change a pending recipe. Use datasets for live updates or explicitly
replace/configure the input. Component factories receive arrays with their shape
and dtype preserved, but must copy them before performing in-place operations.

`read_csv` adds typed tables without pandas. `module(max_width=...)` wraps
measured labels; document cell alignment supports compass positions such as
`align='nw'`. See [live data](data.md), [diagrams](diagrams.md) and [layout](layout.md).

The package also includes opt-in tools under `inklet.experimental`. Figure
planning, microscopy APIs and their report schemas remain experimental and may
change in later releases. Numerical microscopy requires `inklet[volume]`;
ordinary plots and native 3D do not acquire those optional dependencies.
See [the research preview](research-preview.md) before depending on these APIs.

## From 2.6 to 3.0

Upgrade the core package with `python -m pip install --upgrade inklet`, or include
rendering dependencies with `python -m pip install --upgrade 'inklet[render]'`.
See [installation](installation.md) and the [tested support matrix](compatibility.md).

Existing `figure()`, `document()`, plotting, layout, presets and vector export
APIs remain supported. There is no required rewrite of a 2.6 figure. The main
upgrade change is the **default PNG preview renderer**, now resvg instead of
Chromium. Install the `render` extra for PNG export, masks and rasterization:

```sh
python -m pip install --upgrade 'inklet[render]'
```

`images` supplies Pillow and NumPy, but does not supply resvg. Combine extras
as `inklet[render,images,three]`
when you also need image processing, numeric arrays or additional mesh formats.

| Operation | 2.6 | 3.0 |
| --- | --- | --- |
| Save SVG/PDF | Core package; Pillow for raster images | Same |
| Default review PNG | Chromium plus image support | `inklet[render]`, using resvg |
| Keep the Chromium preview | Default | `png_backend='chromium'` or CLI `--png-backend chromium` |
| Independent PDF preview | Poppler | Poppler; `compare_pdf=False` or `--no-pdf-preview` omits it |
| Review without Chrome or Poppler | Vector-only output | `render` extra plus `compare_pdf=False` |
| Blender for ordinary plots/native 3D | Optional | Still optional |

The existing figure below saves vectors with core dependencies:

```python
import inklet as i

doc = i.document(width=89)
doc.add('response', i.plot_spec(x=(0, 2), y=(0, 4))
        .line([(0, 1), (1, 3), (2, 2)]).axes(x='Time', y='Response'))
figure = doc.compile()
figure.save('response.svg', 'response.pdf')
```

With the `render` extra, the same compiled figure exports a review bundle:

<!-- Requires preview renderers. -->

```python
figure.export('review', compare_pdf=False)
```

Inspect PNG differences when upgrading: resvg rasterizes shaped glyph outlines,
and antialiasing can differ from Chromium even when vector geometry is unchanged.
Keep the same fonts, DPI and page size when comparing. Do not automatically
refresh visual baselines to remove differences. Use `inklet doctor` to inspect
the installed tools.

### New rendering behavior

- Cycles scenes default to an available GPU, with CPU fallback when discovery
  finds none. Use `device='CPU'` for an explicit CPU render. A GPU render error
  does not silently retry on CPU; the selected backend is recorded in provenance.
- Masks and `rasterize()` create explicit image layers in SVG and PDF. Keep
  editable annotations outside those layers. A Blender scene is also an image;
  its Inklet labels, paths and dimensions can remain vector.
- Projection and dimensions use Blender world coordinates. Set `scale=` and
  `unit=` explicitly when converting a dimension to physical units. Overlay
  scene annotations with `align='origin'`.
- Scene caches are derived outputs. Changed workers, assets, settings or Blender
  versions can trigger a fresh render. Keep source assets; do not depend on cache
  filenames or exact pixel equality across GPUs and Blender builds.

The original mesh-to-vector Blender backend requires **4.2 LTS**. Complete
scene rendering and templates are tested with both 4.2 and 4.5 LTS. You can keep
both installations and select one per call with `blender=`. See
[complete scenes](blender-scenes.md) and [render jobs](render-jobs.md).

## Historical package rename

The package and Python import are now `inklet`. The figure API is the same:

```python
import inklet

fig = inklet.figure(width="89mm")
fig.add(inklet.box("Hello, Inklet"))
fig.save("hello.svg")
```

For an existing development checkout, replace the old editable installation:

```bash
uv pip uninstall dgm
uv pip install -e ".[dev]"
```

Update `import dgm` and `from dgm...` to use `inklet`, along with qualified
calls such as `inklet.figure(...)`. There is no `dgm` compatibility package.

| Previous name | Inklet name |
| --- | --- |
| `DGM_CACHE_DIR` | `INKLET_CACHE_DIR` |
| `DGM_BLENDER` | `INKLET_BLENDER` |
| `mouse.dgm.json` asset sidecar | `mouse.inklet.json` |
| Default cache directory `$XDG_CACHE_HOME/dgm/assets` | `$XDG_CACHE_HOME/inklet/assets` |

Rename existing sidecars to keep their anchors and attribution available.
Derived assets rebuild in the new cache directory; `INKLET_CACHE_DIR` can point
to an existing cache if you want to reuse it. When `XDG_CACHE_HOME` is unset,
the cache lives under `~/.cache`.

New SVG and PDF exports identify Inklet in their metadata. SVG background IDs
and generated font names also use the new prefix, so output bytes change even
when a figure's geometry is identical.

## V2 documents

Existing `inklet.figure()`, `panel()`, diagrams and SVG/PDF exports remain
supported. The live document API was introduced in 2.0 and extended in 2.5.

| Existing authoring | Live v2 equivalent |
|---|---|
| `p = inklet.panel(40, 30, ...)` | `p = inklet.plot_spec(40, 30, ...)` |
| `fig.add(p.build())` | `doc.add('panel', p)` |
| Recreate a panel after changing data | Keep data in `Dataset`; call `update()` |
| Add axes before outside keys/insets | Record instructions in any order; compilation resolves phases |
| Manually repeat colours and legend names | Use `Series` or `CategoryEncoding` |
| `fig.save('f.svg', 'f.pdf')` | `doc.save('f.svg', 'f.pdf')` |
| Inspect separate files after every edit | `inklet watch author.py --output out/review` |

V2 documents default to embedded, searchable text in SVG and PDF. Legacy
`Figure.save()` keeps its existing defaults. A compiled document is a snapshot;
a later edit requires `doc.compile()` again and does not mutate prior output.
Use `key=` to name plot instructions you intend to revise. Calling a drawing
method again adds another instruction; `replace(key, ...)` revises one.

For a new project, start with the [quickstart](quickstart.md) and
[authoring model](concepts.md). The [v2.5 guide](v2.5.md) covers nested grids,
measured compositions, publication defaults and revision review.

The new layout preserves typography. It raises `LayoutError` when cells cannot
fit the requested page. Fixed Diagram and Panel inputs retain their original
size. See [the v2 guide](v2.md) for live plot and component definitions.
