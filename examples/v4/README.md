# 4.0 reference projects

These are development fixtures and interaction experiments for the
[roadmap](../../docs/roadmap.md). The complete regional report now covers the
bounded analyst workflow and a box-based engineering workflow are implemented;
the broader engineering and scientific workflows remain open.
The small fixtures under `fixtures/` are original simulated MIT material by Mark Marosi;
see [the manifest](fixtures/manifest.json). No external downloads are needed.

## Complete regional report

`regional_report.py` combines real Natural Earth country boundaries with 18
simulated country rows, twelve monthly samples, an ECDF and three group panels.
Country selection reaches all related marks. The offline revision corrects
Hungary's December value and removes Estonia with explicit ID reconciliation.

```sh
python examples/v4/regional_report.py --render --output out/regional-report
python examples/v4/regional_report.py --state /path/to/view.json --render --output out/regional-reopened
python examples/v4/regional_report.py --revised --rebase-state /path/to/view.json --missing drop --render --output out/regional-revised
```

Outputs include offline HTML, exact-viewport SVG/state, full-page exports at
210/160 mm, an editable CSV template, a revision report and provenance. Omit
`--render` to skip optional PNG/PDF conversion. Use `--csv` to replace the input
in Python. See the [illustrated workflow](../../docs/regional-report.md) for
sample identity, filtering and export contracts.

## Original regional fixture

Inputs: `fixtures/regions.csv` and `fixtures/regions.geojson`. Four invented
regions have stable IDs, illustrative revenue and cost in kEUR, and rectangular
longitude/latitude boundaries. Expected totals: revenue 200, cost 120; each
North/South group has revenue 100. These polygons do not describe real places.

Implemented: immutable keyed input, linked bar/scatter selection, explicit
visibility filters, JSON state save/reopen, removed-ID reconciliation, static
SVG/PDF/PNG export and 20 precompiled offline HTML states. Python supports
arbitrary subsets/multiple selections; this browser experiment offers only the
four named filters and one selected region at a time.

The [regional map example](../../docs/linked-maps.md) now supplies geographic
polygon rendering, arbitrary ID filters and direct picking.

The later browser examples below provide category panels, direct picking,
page zoom, compiled data revisions, calendar/UTC axes, fixed-reference ECDFs
and supplied intervals. Recomputed summaries and arbitrary browser data uploads
remain outstanding. This original
finite-state HTML remains an experiment in selection/export fidelity.

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

`engineering_report.py` now connects a dimensioned XY plan, a Y = 0 section,
an authored system diagram and supplied component response curves. It uses
native Inklet drawings with explicit table IDs and rectangular picking targets.
Geometry revisions resize components or remove the support, preserve label
offsets, and reconcile saved selections. Responses remain supplied values.

```sh
python examples/v4/engineering_report.py --render --output out/engineering
python examples/v4/engineering_report.py --state /path/to/view.json --render --output out/engineering-reopened
python examples/v4/engineering_report.py --revision removed --rebase-state /path/to/view.json --missing drop --render --output out/engineering-removed
```

The output includes state, label offsets, geometry and revision reports plus
210/170 mm SVG/PDF/PNG exports. See the [illustrated guide](../../docs/engineering-report.md).
This bounded box workflow starts Phase C; arbitrary mesh sections, camera
interaction and general editing/layout constraints remain open.

## Scientific measurement

Input: `fixtures/measurement.json`. A 2 × 4 intensity grid with two labeled
regions, 0.5 um pixel spacing and explicit region IDs. Each region occupies four
pixels (1 um²); mean intensities are 2.5 and 6.5. The grid is deliberately small
so expected values can be independently checked without a numerical package.

`scientific_report.py` now links a larger original simulated label image to
regional means/ranges and area comparisons. `LabelImage` verifies the small
fixture's exact measurements. The browser uses source-pixel picking, including
holes and disconnected regions, while maintaining the image as reference
context during filtering.

```sh
python examples/v4/scientific_report.py --render --output out/scientific
python examples/v4/scientific_report.py --state /path/to/view.json --render --output out/scientific-reopened
python examples/v4/scientific_report.py --revision calibrated --rebase-state /path/to/view.json --render --output out/scientific-calibrated
```

The output includes input/calibration, measurement and revision reports and
210/170 mm exports. Calibration, intensity and label revisions have separate
semantics. See the [illustrated guide](../../docs/scientific-report.md). The
bounded label-image workflow is implemented; volume/mesh and field interaction,
external microscopy import into the linked model, and general editing remain open.

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

The restore command reconstructs the vector `figure.svg` and opens its HTML
with the saved state already applied. Keep the same count and source revision.
The default example uses hybrid; `BrowserScatter.to_html()` defaults to SVG.
No optional numerical or raster packages are needed for HTML/SVG generation.

See the [guide](../../docs/browser-rendering.md) and
[backend measurements](../../docs/design/browser-backends.md). Run
`tests/test_browser_scatter.py` for geometry/state checks and headless browser
regressions when Chrome or Chromium is installed.

## Linked monthly operations

`linked_dashboard.py` builds four linked line, scatter and signed bar panels
from twelve original simulated monthly rows. Missing revenue breaks the line;
zero-margin bars disappear while their row identity remains in the table.
Horizontal bars reverse the month axis. Selection, filtering and page navigation
work with SVG, Canvas 2D and hybrid display; exports remain vector geometry.

```sh
python examples/v4/linked_dashboard.py --output out/v4-dashboard
python examples/v4/linked_dashboard.py --state /path/to/view.json --output out/v4-restored
```

The restored HTML applies the saved state on opening. The
[guide](../../docs/linked-plots.md) documents endpoint selection, filtering gaps,
bar widths/baselines, clipping and current scope. `tests/test_browser_figure.py`
checks mixed geometry against an independent exhaustive picker and Python SVG.

## Regional maps and geometry review

`regional_analysis.py` joins the original region GeoJSON and CSV by string IDs.
Two maps, revenue bars and a scatter panel share selection/filter state. Fixed
color bins retain their legends when filtering. `region_shapes.py` exercises
holes, concave boundaries, multipolygon islands and overlapping features.
Both examples use a flat longitude/latitude view with equal physical degree
scales; these invented regions do not support geographic measurement claims.

```sh
python examples/v4/regional_analysis.py --output out/v4-regions
python examples/v4/regional_analysis.py --group North --output out/v4-north
python examples/v4/regional_analysis.py --state /path/to/view.json --output out/v4-restored
python examples/v4/region_shapes.py --output out/v4-region-shapes
```

The [guide](../../docs/linked-maps.md) documents the supported GeoJSON subset,
strict joins, missing values, source-order picking and static reconstruction.
`tests/test_browser_regions.py` checks geometry validation, native browser fill
agreement and Python/browser vector and raster agreement.

## Real world population map

`world_population.py` uses real Natural Earth country boundaries and population
estimates with linked world/Europe views. Hungary starts selected; search accepts
country names and continents. The historical source snapshot is mostly dated
2019, with each row's year retained. Nothing is simulated in these map inputs.

```sh
python examples/v4/world_population.py --output out/v4-world
python examples/v4/world_population.py --state /path/to/view.json --output out/v4-restored
python tools/prepare_world_map.py --check
```

The first two commands work offline. The last verifies prepared inputs against
a checksum-pinned source download. See [the real map guide](../../docs/world-map.md),
[source manifest](data/world-map-source.json) and
[third-party notice](../../THIRD_PARTY_NOTICES.md) for attribution and transformations.

## Revised data and saved views

The same real map recipe can replace its table with a source-year cohort or a
supplied population CSV. It writes revised HTML/SVG, a saved view, the effective
CSV and `revision.json`. Geometry is explicitly restricted to the requested
country IDs; new IDs without pinned source geometry fail.

```sh
python examples/v4/world_population.py --year 2019 --output out/v4-revision
python examples/v4/world_population.py --year 2019 --rebase-state /path/to/original-view.json --missing drop --output out/v4-revision
python examples/v4/world_population.py --year 2019 --state out/v4-revision/view.json --output out/v4-restored
python examples/v4/world_population.py --csv /path/to/population.csv --rebase-state /path/to/original-view.json --output out/v4-csv
python examples/v4/world_population.py --switchable --output out/v4-switchable
python examples/v4/world_population.py --switchable --year 2019 --state /path/to/cohort-view.json --output out/v4-restored
```

See [Replace figure data](../../docs/data-revisions.md) for schema, identity,
filter and viewport rules. `tests/test_browser_revision.py` covers changed rows,
order/layout changes, explicit drop reports, CSV provenance, strict saved-state
validation and browser/Python export agreement.

`--switchable` embeds the original 176-country map and the 169-country source-year
2019 cohort in one offline HTML page. Browser replacement transfers the current
selection/filter under explicit missing-ID and viewport policies and exports a
revision report. Values for retained countries are unchanged. Search for `TWN`,
select it and clear the search before trying the 2019 cohort: the default policy
rejects its removal, while `drop` reports the discarded selection. Switching back
adds the country again without restoring that discarded selection.

To reopen a saved view, select its exact initial revision with `--year 2019` or
omit `--year` for the original. The switchable recipe rejects supplied CSV files
and years other than 2019; the Python API can embed other precompiled revisions.

## Linked category panels

`faceted_operations.py` builds six panels from 36 original simulated monthly
rows: revenue lines and signed profit bars for North, South and West. These are
invented business categories and values, released as MIT material by Mark Marosi.
The source interleaves categories; lines connect observations within each category
and preserve North's missing June revenue. Both measures share row selection.

```sh
python examples/v4/faceted_operations.py --output out/v4-facets
python examples/v4/faceted_operations.py --state /path/to/view.json --output out/v4-restored
python examples/v4/faceted_operations.py --without-west --state /path/to/revised-view.json --output out/v4-restored
```

The offline HTML embeds a second revision that removes West's rows without
changing retained values. Its empty West panels keep their axes and labels.
`--without-west` selects this revision on opening, allowing exact saved-state
reconstruction. The script writes `index.html`, `figure.svg` and `view.json`.
The [facet guide](../../docs/linked-facets.md) explains explicit category order,
unassigned rows, empty panels, source-order line adjacency and filtering.

## pandas and Polars tables

`table_inputs.py` imports original simulated workshop observations through either
optional DataFrame library and builds four linked panels. Both paths retain the
same IDs, missing-value gap and scalar digest. The browser can apply a correction
and row removal; saved state reconstructs the same SVG through either adapter.

```sh
python -m pip install -e '.[pandas,polars]'
python examples/v4/table_inputs.py --backend pandas --output out/v4-tables
python examples/v4/table_inputs.py --backend polars --output out/v4-polars
python examples/v4/table_inputs.py --backend polars --revised --state /path/to/view.json --output out/v4-restored
```

Use `--revised` only for states saved with the corrected revision active.

## Linked time series

`time_series.py` connects simulated daily batch counts on a calendar-date axis
with processing duration at offset-aware collection times. UTC conversion is
explicit. An elapsed-time threshold leaves a gap at an absent day; a null value
breaks both incident segments. A compiled revision restores both observations.

```sh
python examples/v4/time_series.py --output out/v4-time
python examples/v4/time_series.py --backend pandas --output out/v4-time-pandas
python examples/v4/time_series.py --backend polars --revised --state /path/to/view.json --output out/v4-time-restored
```

The default native path needs no DataFrame dependencies. Use `--revised` only
for states saved while the Restored revision was active.

## Linked statistics

`statistical_views.py` builds two faceted reference ECDFs and supplied interval
panels from original simulated cycle-time data. Filtering hides observations
without silently changing the reference population or supplied interval meaning.
A named revision corrects one estimate and removes a batch, rebuilding both views.

```sh
python examples/v4/statistical_views.py --output out/v4-statistics
python examples/v4/statistical_views.py --revised --state /path/to/view.json --output out/v4-statistics-restored
```

The source is MIT material by Mark Marosi. Ranges are illustrative, not confidence
intervals. Methods and populations are disclosed in the browser and scene payload.


### Mixed geographic features (development checkout)

`transport_map.py --render` builds an original, invented transport fixture with
point/multipoint, line/multiline and polygon/multipolygon features linked to
supplied activity values. All coordinates and values in `fixtures/transport.geojson`
and the recipe are original illustrative material under the repository's MIT
license. They do not represent real locations or measured traffic. The report
includes rerouted/removed geometry alternatives, explicit state reconciliation,
source attribution and SVG/PDF/PNG exports at two widths.
