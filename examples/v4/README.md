# 4.0 reference projects

These are development fixtures and a first interaction experiment. They do not
implement the complete workflows in the [roadmap](../../docs/roadmap.md).
All fixture data and geometry are original simulated MIT material by Mark Marosi;
see [the manifest](fixtures/manifest.json). No external downloads are needed.

## Regional analysis

Inputs: `fixtures/regions.csv` and `fixtures/regions.geojson`. Four invented
regions have stable IDs, illustrative revenue and cost in kEUR, and rectangular
longitude/latitude boundaries. Expected totals: revenue 200, cost 120; each
North/South group has revenue 100. These polygons do not describe real places.

Implemented: immutable keyed input, linked bar/scatter selection, explicit
visibility filters, JSON state save/reopen, removed-ID reconciliation, static
SVG/PDF/PNG export and 20 precompiled offline HTML states. Python supports
arbitrary subsets/multiple selections; this browser experiment offers only the
four named filters and one selected region at a time.

Remaining: geographic rendering, date-series fixtures and plots, distribution
and faceting views, generic browser picking/zoom, and arbitrary browser data
updates. The current HTML is an experiment in state/export fidelity, not a new
renderer or a general dashboard API.

```sh
python examples/v4/linked_selection.py --output out/v4-linked
# Open out/v4-linked/index.html in a browser; use Save selection.
python examples/v4/linked_selection.py --state /path/to/selection.json --output out/v4-restored
```

Use a checkout with `inklet[render]` installed for the PNG export. Output captions
and metadata identify the data as simulated. The example does not modify inputs.
Rebuilding the saved state produces the same SVG as Download current SVG.
To apply a saved state to changed data, explicitly call `rebase()`; removing IDs
fails unless `missing='drop'` is chosen, and that operation returns removed IDs.

## Engineering study

Input: `fixtures/assembly.json`. Three boxes, dimensions and centers in mm;
a supplied linear load/displacement table. Independent expected measurements:
80 × 40 mm footprint, 35 mm overall height, and a recorded sensor/support center
distance. The response is illustrative, not a mechanics solution.

Existing 3.1 foundations can draw the assembly, dimensions, response plots and a
system diagram. This fixture has numerical validation; an integrated engineering
recipe has not yet been implemented. Next add that static recipe, explicit
object/table correspondence, a section view and preserved annotation decisions.
Test component removal, changed dimensions and page resizing before counting
this reference project as complete.

## Scientific measurement

Input: `fixtures/measurement.json`. A 2 × 4 intensity grid with two labeled
regions, 0.5 um pixel spacing and explicit region IDs. Each region occupies four
pixels (1 um²); mean intensities are 2.5 and 6.5. The grid is deliberately small
so expected values can be independently checked without a numerical package.

Existing 3.1 microscopy and plotting APIs provide the foundation. This fixture
has numerical validation; the linked scientific recipe remains to be built.
Next add calibration-aware image/measurement panels, a field/mesh fixture,
supplied uncertainty bounds and region selection. Test missing correspondences,
changed calibration and preserved author edits.

## Checks and baseline

`tests/test_v4_selection.py` verifies fixture measurements, selection semantics,
array snapshots and cached/clean plot agreement. Run `tools/benchmark_v4.py` for
fresh-process cold/cached/data-edit/label-edit/resize/export measurements.
The [phase A report](../../docs/v4-foundations.md) explains baseline limitations
and the local performance budgets.

## Browser renderer study

`browser_scatter.py` compiles measured axes and keyed point geometry for two
linked scatter views. Its offline HTML draws arbitrary visible/selected subsets
with SVG, Canvas 2D or hybrid rendering. It supports direct picking, ID filtering,
page pan/zoom, a keyboard-accessible table and saved-view JSON. It does not
rescale data domains or implement arbitrary plot primitives.

```sh
python examples/v4/browser_scatter.py --count 3000 --output out/v4-browser
python examples/v4/browser_scatter.py --count 3000 --state /path/to/view.json --output out/v4-restored
```

The restore command reconstructs the vector `figure.svg`; use Open saved view
in its HTML to restore browser state. Keep the same count and source revision.
The default example uses hybrid; `BrowserScatter.to_html()` defaults to SVG.
No optional numerical or raster packages are needed for HTML/SVG generation.

See the [guide](../../docs/browser-rendering.md) and
[backend measurements](../../docs/design/browser-backends.md). Run
`tests/test_browser_scatter.py` for geometry/state checks and headless browser
regressions when Chrome or Chromium is installed.
