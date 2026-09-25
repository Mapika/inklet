# Changelog

## Unreleased

- `share_plot_margins=True` shares data heights along rows only, so heights
  set per row are kept; `'all'` keeps the tallest height across the grid.
  `examples/dense_figure.py` now shares margins.
- `Panel.label_points` places labels at build time, clear of marks drawn
  after the call. Results are unchanged when nothing is drawn after.
- `PolarPanel.breakout` turns a pie drawn before or after other content,
  drawing that content again under the turned angles.
- Add `Panel.dotplot` for dot-plot matrices on band scales: circle area
  encodes one value, colour another with the `matrix` default ramps, and
  missing values draw nothing. It lines up with `dendrogram` and takes a
  `colorbar`. Add `Panel.size_key`, a key of circle areas for a dot plot or
  for a `scatter` sized with the new `inklet.plot.area_scale`.
- Add `Panel.kaplan_meier` for survival curves: steps, censor ticks and
  log-log (or linear) Greenwood bands, with an optional supplied p-value.
  Add `Panel.at_risk` for a number-at-risk table under the x axis, and the
  estimator `inklet.plot.kaplan_meier`, which returns a `SurvivalEstimate`.
- Add guide sections to `matrices.md` and `distributions.md`, catalog
  entries and `examples/dotplot_survival.py`.
- Add `inklet.forest` and `inklet.plot.forest_layout` for forest plots: a
  row per study with a square sized by weight, summary diamonds, group
  headers, a no-effect line at 1 (log) or 0, arrowheads for intervals past
  the limits and aligned text columns such as `'ci'` and `'n'`.
- Add `Panel.embedding` for UMAP or t-SNE scatters: points coloured by
  cluster in one marker batch, names at robust centres placed clear of each
  other, and optional corner axis arrows. Add
  `inklet.plot.cluster_centres`.
- Add `Panel.split_violin`: two conditions per category as the halves of
  one violin, with median and optional quartile lines.
- Add `Panel.brackets`, which stacks significance brackets for many pairs,
  shortest span lowest, and `inklet.plot.format_p` for stars or P values.
  No test is run.
- Add guide sections for the four, catalog entries and
  `examples/study_plot_types.py`.

## 4.1.0 — 2026-09-25

4.1.0 adds thirteen plot and annotation types, tightens default presentation toward journal
pages and reorganises the documentation. See the
[migration notes](docs/migration.md#from-401-to-410) for output changes.
Known issue: with Blender 4.2, the single-thread Line Art bake of large meshes
can exceed its timeout on some machines; the optional Blender tests are
affected, figure building is not.

- Add `inklet.upset` and `inklet.plot.upset_layout` for UpSet plots:
  intersection sizes as bars over a set-membership dot matrix, with optional
  set-size bars at the left. Input is a mapping of set name to members or a
  list of `(members, count)` records. `sort='size'` or `'degree'`,
  `min_size=` and `max_intersections=` choose the columns. The three panels
  share band scales, so each bar stands over its matrix column. Add a guide
  section to `bars-and-areas.md`, a catalog entry and panel f of
  `examples/more_plot_types.py`.
- On a panel with a `matrix`, an axis with no ticks (`ticks=[]`) or hidden
  ticks (`labels=False`, `tick_size=0`) no longer draws a spine; `spine=True`
  keeps it. Axes on other panels are unchanged. Panel e of
  `examples/dense_figure.py` loses its two heatmap spines.
- `PolarPanel.breakout` now turns the pie so the middle of the chosen
  slices faces the bar, first slice uppermost, when `inklet.polar` was given
  no `zero` or `winding`; explicit values are kept. `inklet.polar` defaults
  for `zero` and `winding` are now `None`, which means `"east"` and `"ccw"`
  as before. Pie labels outside the rim move clear of the breakout
  connectors and bar; any that cannot are listed under `crossing` in the
  `pie_labels` note.
- Add `PolarPanel.breakout`, which expands one or more adjacent pie slices
  into a stacked bar beside the disc, with connector lines from the rim and
  a share label per part. The `pie_labels` note now also records each
  slice's page angles and value.
- Add `Panel.ridgeline` for overlapping kernel densities per category on a
  shared x scale, with shared or per-ridge height scaling and a common
  scale-down that keeps the ridges inside the plot area.
- Add `Panel.raincloud`: per group, a half violin, a narrow box and every
  observation as seeded jitter or a swarm, horizontal or vertical.
- Add `Panel.volcano` and `inklet.plot.volcano_points` for volcano plots:
  threshold rules, up, down and non-significant colours, legend names and
  labels for the top N significant points through `label_points`.
- Add `Panel.dendrogram` and `inklet.plot.dendrogram_layout` for
  hierarchical clustering trees from a SciPy linkage matrix or a nested
  sequence, vertical or horizontal, with threshold cluster colours. On a
  band scale the leaves line up with a heatmap on the same categories.
- Make `scientific.cell` a preset for dense multi-panel pages: 6 pt text,
  5 pt ticks and keys, 8 pt letters, 0.4 pt strokes, 0.25 pt hairlines, a
  2 mm margin, 3.5 mm gaps, a 0.8× spacing scale, 4 ticks and a muted blue,
  amber, magenta and grey palette. Its checks accept 5 pt text and 0.25 pt
  (0.088 mm) strokes, the lint default, instead of 6 pt and 0.1 mm.
- Add `legend_side='inside'` to presets. Legends without `side=` or `corner=`
  are placed in clear data space, or above the data area when none fits.
  `scientific.cell` uses it.
- Add `Preset.letter_pad` (`customize(letter_pad=...)`), the distance between
  a panel letter and its panel. `scientific.cell` sets 0.5 mm.
- `matrix()` without `ramp=` now uses a default colouring: reversed magma
  over the data extent for one-sided data, and Paul Tol's blue-white-red
  (`tol-burd`) centred on zero for data across zero or on `center=`. Explicit
  ramps keep reading values as 0..1 fractions. Add the `magma` and `tol-burd`
  palettes.
- Orthogonal links route through anchored faces: an end pinned to a side
  anchor such as `in` or `out` leaves or arrives along that face's normal.
  Previously the axis came from the centre-to-centre direction, so a target
  mostly above or below the source was reached by a run along its own side
  face with the arrowhead inside the box.
- `share_plot_margins=True` shares left and right plot furniture along
  vertical grid lines instead of across the whole grid. Plots whose cells
  start on the same grid line share the largest left margin among them, and
  plots whose cells end on the same grid line share the largest right margin,
  so their data edges line up there. A wide label no longer narrows plots in
  other columns or with other spans. Plots in different columns can now have
  different data widths when their labels differ; `share_plot_margins='all'`
  keeps the whole-grid rule, and facet figures use it. Top and bottom sharing
  is unchanged. `examples/general_plots.py` gains about 3 mm of data width in
  its left column; `gallery/general-plots.png` is regenerated.
- Top and bottom legends with automatic columns may use the whole panel
  width. A key that needs more rows at the data width than at the panel width,
  including the axis furniture left of the data, is refitted to the panel
  width and left-aligned with the panel's outer edge; a key that fits the data
  width stays centred on it. This includes `legend_side='inside'` keys moved
  above a crowded plot. Explicit `columns=` or `max_width=` are unchanged.
- Link labels keep clear of arrowheads, and `inklet.connect` and `route()`
  keep a label off the link's own end shapes even when no obstacles are
  passed. When no spot beside the line is clear, as on a link a few
  millimetres long between two boxes, the label moves out from the line in
  0.25 mm steps to the nearest clear spot, usually just above or below the
  boxes and centred on the gap, instead of a full label size or more away.
  The link is flagged `FLAG_LABEL_OFF_LINK` and the new lint rule
  `LABEL_OFF_LINK` reports it as an info. Regenerate `gallery/process.png`,
  `gallery/diagram-review.png` and `gallery/diagram-labels-after.png`.
- Add `examples/dense_figure.py`, a thirteen-panel 183 mm page with the
  `scientific.cell` preset, and its gallery image `gallery/dense-figure.png`.
- Retighten `examples/general_plots.py`: the preset's 183 mm width, margin,
  gap and 7/6 pt type instead of 200 mm, 6/12 mm and 8 pt; 34 mm plots; theme
  hairlines; legends in empty corners or one row above the bars; and the
  default matrix ramp. Data and panels are unchanged. Regenerate
  `gallery/general-plots.png`, its SVG/PDF downloads and `gallery/presets.png`.
- Add value labels to `Panel.bars` (`labels=`, `label_position=`,
  `label_options=`). Labels go inside a bar or segment when they fit and past
  the bar end otherwise; stacked segments that do not fit are omitted and
  listed in the `bar_labels` note.
- Add `Panel.dumbbell` and `Panel.lollipop` for dot-and-connector plots on a
  band scale.
- Add `Panel.label_points`, which places many point labels clear of marks and
  of each other, with hairline leaders for labels moved off their point.
  Unresolved labels are listed in the `point_labels` note.
- Add `Panel.ecdf` and `inklet.plot.ecdf` for empirical cumulative
  distributions, including the complementary form and weighted counts.
- Add `PolarPanel.radar`, `PolarPanel.radar_grid` and `PolarPanel.pie` for
  radar charts and pie or donut charts with inside or outside labels.
- Document the new plot types in the bars, lines-and-points, distributions
  and polar guides, add catalog entries, and add
  `examples/new_plot_types.py` and `docs/design/capability-gaps.md`.
- Tighten default plot presentation toward journal figure pages. With
  `share_plot_margins=True` and an automatic height, top and bottom furniture
  is now shared along each row instead of across the whole grid, so a legend or
  colorbar under one row no longer adds the same space under every row; data
  areas stay equal. `scientific.general` (and `scientific.science`/`cell`) use
  7 pt text with 6 pt ticks and keys (was 8/7 pt). Ticks are 0.45 of the type
  size (was 0.55) and axis names sit 0.4 type sizes beyond the tick labels
  (was 0.5). Outside legends and colorbars sit one `xs` step from the
  furniture (was `s`), and colorbars are one type size thick (was 1.4).
  Bold panel letters are now shaped and embedded with the bold face; they
  previously exported the regular face under `font-weight="bold"`.
  Visual baselines, `gallery/plots.png`, `gallery/general-plots.png` and the
  general-plots SVG/PDF downloads are regenerated for the new defaults.

- Replace figurative prose in guides, captions, the cookbook and generated API
  descriptions with direct technical explanations. Document the writing guidance.

- Consolidate the figure gallery from 41 cards to 20 selected workflows, retain
  related recipes in the source library, and reduce overlapping plot-type cards.
  Redraw plotting guides with richer illustrative data and consistent visual
  encodings; reorganize the CSV example into paired analytical views with new
  editable downloads.

- Rework documentation content for 4.0.1: clarify current and experimental
  workflows, plot selection, export font defaults, snapshot behavior and
  opt-in shared plot margins. Expand matrix guidance, correct the heatmap
  example's row labels, and add rendered row-order, sampling and live-data
  comparisons. Extend executable guide coverage and retain historical links.

## 4.0.1 — 2026-09-14

- Separate plot statistics from mark drawing, reuse sorted samples for
  quartiles, use binary search for histogram bins, and reuse violin bandwidths.
- Share named-series colour selection between rectangular and polar plots,
  replacing quadratic name scans with linear lookup. Separate diagnostic
  metadata from scale mathematics and share outside-key positioning.
- Separate matrix validation and rendering from panel authoring, share plot
  furniture across rectangular and polar plots, and consolidate diagram-bound
  unions used by drawing, layout and plotting.
- Separate document track allocation, measured fitting and compiled snapshot
  ownership. Compiled documents export directly from retained scene state;
  authored figures and snapshots share page export settings and file dispatch.
- Reuse captured scene font fingerprints for document metadata, exposed through
  `RenderScene.font_manifest()`, while retaining export-time font validation.
- Protect the compiled placement mapping from mutation through `build()`.
- Resolve inherited paint once into immutable styles shared by sibling nodes,
  while keeping group opacity on its compositing group.

## 4.0.0 — 2026-09-14

Stable release of the bounded 4.0 scope, following RC1. Existing 3.1 authoring
APIs remain supported; `inklet.experimental` retains its opt-in status.

- Deliver dense-field PDF improvements, scientific layouts and annotations,
  reusable figure projects and consolidated scientific tutorials.
- Enforce skip-free reference acceptance, complete project/report performance
  budgets and software-browser median/worst-sample checks.
- Stop benchmark browser process groups before cleaning profiles, and retry only
  transient directory-write races without weakening performance limits.


- Verify public call-shape compatibility against the released 3.1 wheel and
  reopen archived dev16 project, layout and hidden-selection files in CI.
- Record cross-version migration evidence, including pixel-identical publication
  example exports from 3.1 and RC1 at two widths, with source/output hashes.

## 4.0.0rc1 — 2026-09-14

First release candidate for the bounded 4.0 scope. Includes the previously
unreleased RC-preparation changes after dev16. Experimental APIs remain opt-in;
3.1.0 remains the stable release.

- Declare the bounded 4.0 API, inspector, adapter and saved-file policy; add
  3.1-to-4.0 migration guidance and defer unsupported interactions beyond 4.0.
- Require every reference workflow to pass without skips in release acceptance.
- Enforce explicit project lifecycle performance budgets at two output widths,
  retaining timings and correctness checks for edit, reopen, revision and exports.

- Add reference-report rebuild and offline browser performance gates covering
  four fixtures and five software renderer/backend combinations, with real-clock
  median/worst-sample budgets and retained review artifacts.

## 4.0.0.dev16 — 2026-09-14

Sixteenth development preview: dense-field performance, reusable figure projects
and scientific documentation. Experimental APIs and schemas remain opt-in.

- Add experimental figure projects with portable SHA-256 asset manifests,
  explicit cross-content entity maps, source-native linked-view adapters,
  saved editor choices and verified reconstruction through trusted factories.
- Add complete project acceptance for edit/undo/reopen/revision/removal/resize
  and exports; expose the shared acceptance marker for all three reference reports.
- Consolidate browser/export test helpers and rename six version/round-based
  regression modules by behavior, retaining their assertions and fixtures.
- Replace the preview's duplicate tutorials with links to current capability
  guides; update the RC checklist, archive superseded studies at their existing
  URLs and exclude historical pages from normal search.

- Add runnable CSV-to-figure and project revision tutorials; consolidate current
  guides and improve documentation navigation, typography and mobile layout.
- Add labelled Blender biological examples, a hash-verified CC BY anatomy import,
  and explicit region colour bindings with reproducible sources and attribution.

- Encode horizontal-first closed rectangular contours with compact PDF rectangle
  operators, preserving rounded endpoints, signed winding and dash origins.
- Buffer PDF content without retaining one Python string per drawing operator.
- Add a reproducible dense-field benchmark for export time, size and memory.
- Preserve double precision in browser drag coordinates and exercise multiple
  viewport sizes; repair the table-adapter CI reference after test consolidation.

## 4.0.0.dev15 — 2026-09-13

Fifteenth development preview: published-figure reproduction and core speed.
Published on GitHub and PyPI, together with the separately tagged dev14 snapshot.

- Add seamless exact-color vector matrices with opaque underpaint and explicit
  scalar interpolation for smooth raster fields; fix singleton matrix extents.
- Add `Panel.placed()` for exact data-area placement and `Panel.guide()` for
  labels attached to displayed data guides, including logarithmic scales.
- Keep legend/colorbar backdrop styling separate from foreground text and outlines.
- Add independent legend column/row gaps and column-major ordering, plus
  measured inset colorbars with titles, plates and optional clear-space search.
- Add source-hash verification, panel bounds and registered panel-crop reference
  reviews to `FigureReview`; migrate three released-data paper recreations.
- Bound the optional Blender smoothing regression with an 80-face curved fixture;
  retain crease-suppression assertions without a full-brain bake timeout.

- Speed core rectangle envelopes, transformed bounds and identity composition;
  reuse theme calculations within each build without adding persistent caches.
- Remove the superseded internal compositing cache; retain context, clipping
  and paint-count tests against the compiled scene used by actual exporters.
- Add reproducible core timing/output checks and document measured speed and
  memory changes, including workloads with little overall improvement.

## 4.0.0.dev14 — 2026-09-13

Fourteenth development preview: complex scientific figure authoring.
3.1.0 remains stable; the 4.0 roadmap remains open.

- Coordinate registered page annotations with pinned placements, leaders and
  explicit failure when the bounded search cannot find clear space.
- Add `PanelSpec` minimum dimensions, automatic tracks and drawing-area aspect
  ratios; preserve fonts while rebuilding panels around axes and captions.
- Add shared anatomy lighting, registered mesh/path/marker sections and opt-in
  opaque surface sorting with path/marker occlusion. Cut surfaces remain open.
- Add opt-in graph stroke/arrow floors and exact-color batched vector matrices.
- Export numbered visual review SVGs and JSON using existing lint diagnostics.


- Add named spanning `panel_mosaic` layouts, shared-camera `anatomy_view`
  close-ups, measured `value_table` cells, automatic clear-space legends, and
  `Graph.build()` for routed networks inside static components.
- Add two original scientific gallery plates from released fly-connectome data,
  with editable vector exports, reproducible recipes and source attribution.

- Add opt-in `text(bounds="ink")` to center visible glyphs while keeping text
  editable. Correct circle/cell text and grouped legend placement in the
  dimorphism C, D and H examples.

- Add immediate `connect` for already-placed shapes, measured bounded
  `label_column` placement with leaders, and `Panel.region` for shared
  data-to-rectangle transforms. Apply these to independently audited figure
  corrections, with checks for statistics, labels, zooms and visible arrow tips.

- Add `tag` labels sized from shaped text, with separate horizontal/vertical
  padding, editable text and contrast-aware foreground colors.
- Add authored `arrow` paths with exact cubic shafts, tangent-aligned heads,
  shaft trimming, transformed-path support and automatic short-arrow heads.
- Let builtin `model` rendering share a fitted `View` with batched 3D paths
  and markers, preserving registration across independently drawn layers.
- Add immutable `Mesh.from_arrays` and optional display-only `Mesh.simplified`;
  the `three` extra includes fast-simplification, loaded only on demand.
- Accept NumPy real scalar lengths in core units without importing NumPy;
  report unsupported unit inputs explicitly.
- Apply these APIs to the connectome figure examples and document the workflow.

## 4.0.0.dev13 — 2026-09-13

Thirteenth development preview: native camera choices in the composition editor.
The original 4.0 scope remains open; this is not a release candidate.

- Add a Camera inspector for builtin native model/solid components, with orbit
  angles, roll and projection mode. Preserve explicit look-at eye/target vectors.
- Include camera edits in atomic layout transactions, undo/redo, shared instance
  reconciliation, saved choices and matching SVG/PDF reconstruction.
- Introduce composition schema 0.5, retaining readers for 0.1–0.4. Report changed
  camera kinds and unsupported replacement renderers as orphaned camera choices.
- Illustrate the camera workflow and document physical fitting limitations.
- Accept RC tags in the publishing gate, with tested prerelease/draft checks;
  update the compatibility matrix without claiming broader browser coverage.

## 4.0.0.dev12 — 2026-09-13

Twelfth development preview: a redesigned local figure workspace.
3.1.0 remains the stable release.

- Add searchable object navigation, a large canvas, focused inspector tabs,
  fixed apply/discard controls, header exports and revision feedback.
- Add fitted zoom, wheel zoom, pan tools and Space/middle-button dragging without
  changing authored geometry. Preserve object gesture coordinates across zooms.
- Add native colour pickers, exact-value fields, keyboard shortcuts and a help
  dialog; retain native text undo and adapt the workspace to smaller screens.
- Protect unapplied fields during selection and file/source actions; highlight
  pending changes and offer explicit discard. Keep schema 0.4 and Python exports.
- Review real pointer capture and mobile overflow, extend browser regressions,
  and update the illustrated editor guide.

## 4.0.0.dev11 — 2026-09-12

Eleventh development preview: unified composition layout, labels and appearance.
3.1.0 remains the stable release.

- Add supported keyed line/marker styles, text/callout appearance and module box
  styles to the local composition editor, using the same Python compiler.
- Organize controls into Layout, Labels and Styles. Apply changes across sections
  as one atomic edit with shared undo/redo, reset and saved-state reconstruction.
- Save typed named appearance decisions in schema 0.4, accepting legacy 0.1–0.3
  files. Explicit null style fields remove authored keywords for automatic styling.
- Preserve data-driven marker sizes and colours; report incompatible style targets
  after source revisions while retaining compatible label/layout edits on discard.
- Cover combined browser edits, two-width SVG/PDF agreement, inherited styles,
  text remeasurement, live data and alias reconciliation; update illustrated docs.

## 4.0.0.dev10 — 2026-09-12

Tenth development preview: reproducible named label and callout editing.
3.1.0 remains the stable release.

- Edit string module captions, text components, keyed plot titles/text/callouts
  and named composition annotations in the local layout editor.
- Expose callout text, preferred side, physical clearance and leader visibility;
  remeasure content and dependent connections through the Python compiler.
- Save typed label identities and changed fields in layout schema 0.3, accepting
  legacy 0.1/0.2 files, undo/redo, independent copies and shared definitions.
- Report removed or incompatible labels individually; explicit discard preserves
  compatible edits on the same object. Leave unedited source decisions live.
- Add browser controls, source revision and two-width SVG/PDF roundtrip checks,
  installed-package coverage and an illustrated guide and example.

## 4.0.0.dev9 — 2026-09-12

Ninth development preview: mouse movement and proportional artwork scaling.
3.1.0 remains the stable release.

- Add click/drag selection and movement, corner scale handles, containing-group
  selection, keyboard nudges and cancellable pointer gestures to LayoutEditor.
- Map gestures through nested physical coordinate units and scales. Preserve
  measured positions with folded offsets and keep the opposite scale corner fixed.
- Add explicit Composition child scale, preserving registered ports and scaling
  complete artwork. Width/height fitting retains its separate layout semantics.
- Save scale in composition-layout schema 0.2; continue loading schema 0.1 files.
- Cover geometry, ports, all four corners, undo/reopen, nested transforms,
  invalid gestures and browser/Python export agreement; update the editor guide.

## 4.0.0.dev8 — 2026-09-12

Eighth development preview: local browser layout editing with Python compilation.
3.1.0 remains the stable release.

- Add experimental LayoutEditor with a loopback browser inspector for named
  composition placements and dimensions, using the real Python compiler for
  previews and matching SVG/PDF exports.
- Add atomic edit/load/reset commands, bounded undo/redo, saved dev7 layout JSON,
  and explicit source refresh with removed-target reconciliation.
- Preserve the last successful preview/history after errors, reject stale
  revisions and exports, and keep shared nested definitions consistent.
- Add a runnable mixed-content editor, an illustrated guide, browser/HTTP tests,
  concurrent-client checks and core-only installed-package coverage.

## 4.0.0.dev7 — 2026-09-12

Seventh development preview: reproducible composition layout choices.
3.1.0 remains the stable release.

- Add Composition.layout_overrides(reference) to capture only changed child
  placements and composition page fields in versioned JSON with named paths.
- Add with_layout_overrides() to restore onto an independent recipe, retaining
  live inputs, new content and unedited source decisions.
- Preserve measured page/child/anchor expressions through saving and reopening;
  diagnose removed targets and references with explicit error/drop policies.
- Reject malformed values and contradictory edits to shared nested definitions
  before applying changes. Keep geometry validation in the document compiler.
- Extend the plot/diagram/native-3D example with saved layouts, two-width
  roundtrips, revised content, reconciliation reports and an illustrated guide.

## 4.0.0.dev6 — 2026-09-12

Sixth development preview: reusable mixed-content compositions.
3.1.0 remains the stable release.

- Add Composition.slot() and instantiate() for required named content inputs
  and replaceable defaults, with clear missing/unknown-input diagnostics.
- Add independent Composition.copy() across nested compositions, plots, modules
  and component instructions while retaining explicit live data dependencies
  and shared definitions within each copy.
- Expose nested attachment points with Composition.port(); preserve physical
  coordinates through placement, child replacement, coordinate units and top fitting.
- Add placement edits with Composition.place() and atomic dimension updates
  with configure(), retaining content and named relationships.
- Add two reusable plot/diagram/native-3D reports at two widths, an illustrated
  guide, live-data revision checks and installed-package coverage.

## 4.0.0.dev5 — 2026-09-12

Fifth development preview: shared plotting, customization and composition.
3.1.0 remains the stable release.

- Add reusable PlotSpec.copy(), extend() and style() for independent recipe
  variants, combined mark layers and preserved live data dependencies.
- Add per-axis options to Panel.axes() and PlotSpec.axes(); preset grids use
  matching label measurements. Support local Series colour/name overrides.
- Preserve authored data heights when automatic document legends wrap, without
  requiring globally shared margins. Apply plot dimension updates atomically.
- Add a five-panel plot/diagram composition at two widths, an illustrated guide,
  and regression checks for reuse, data edits, layout and customization.

- Add experimental GeoFeatures and MapView for linked GeoJSON points, routes and
  regions, with multi-part identity, topmost map picking, exact keyed joins,
  source attribution and geometry revisions. Include a four-panel transport
  recipe, two-width exports and an illustrated offline guide.

## 4.0.0.dev4 — 2026-09-12

Fourth development preview: correct closed polar geometry and make the plot
documentation visual and easier to navigate. 3.1.0 remains stable.

- Fix closed polar curves retracing the angular range and shaded bands crossing
  themselves. Complete the closing arc in sample order and retain both band
  endpoints; refresh polar previews and cover angular units and winding directions.

- Reorganize documentation around plotting, interactive documents and microscopy.
  Add a searchable visual plot gallery and six guides with 22 rendered, runnable
  examples; check plot-family coverage, gallery links and guide execution.

## 4.0.0.dev3 — 2026-09-12

Third development preview: shared scene execution, dense marker rendering,
linked compiled reports and the first reproducible plot-style editor. Install
explicitly with `python -m pip install "inklet==4.0.0.dev3"`; 3.1.0 remains stable.

- Add an offline inspector for named plot colours, marker radii and line widths,
  with bounded undo/redo and separate versioned overrides. Preserve compatible
  choices across source revisions and page widths; reject or explicitly report
  orphaned targets. Reproduce edited views through Python SVG/PDF/PNG exports.
- Prepare style commands atomically, preserve selection and view state, and
  prevent file/command/revision races. Add edited full-report visual comparisons,
  failure cases, browser/Python agreement and installed-wheel checks.

- Add opt-in compiled execution to linked browser figures, preserving keyed
  selection, filtering, saved states, revision policies and vector exports.
  Pack contiguous circle runs without reordering paint, retain native SVG for
  other marks, and intersect visibility masks with spatial candidates.
- Share the compiled viewer runtime with the linked report instead of duplicating
  GPU execution. Retain immutable records during filtering and release surfaces
  on revision replacement. Add a runnable regional report mode, complete-figure
  display comparisons and state/revision/export regressions across backends.

- Build ordered marker candidates with a reusable bitmap instead of temporary
  JavaScript result arrays and comparison sorting. Accept fully contained grid
  cells without rechecking each footprint, preserving source paint order and
  independently owned result arrays.
- Measure 250,000- and million-point index queries and browser submission.
  The million-point zoom query falls from 5.253 to 0.629 ms in the standalone
  study; tiny queries are slightly slower. Retained bitmap storage adds one bit
  per row. Add word-boundary and query-result ownership regressions.

- Cull individual packed markers with a shared spatial index of full marker
  footprints. Preserve source order, antialiasing margins and vector exports.
  Canvas paints candidates; WebGL2 fetches immutable records using compact
  row-index uploads. Report candidate counts, uploads and index storage.
- Add a 250,000-point stress recipe, brute-force and visual fidelity checks,
  and separate submission/GPU timer studies. Canvas window submission improves
  from 88.5 to 10.8 ms in the recorded workload; GPU draw time falls from 0.325
  to 0.042 ms while CPU submission rises from 0.9 to 2.2 ms. Document memory costs.

- Size compiled-viewer surfaces around the visible region with a retained pan
  margin; skip painting offscreen layers and reuse their immutable buffers on
  return. Preserve native clipping, marker order and complete vector export.
- Keep deep-zoom resolution within the existing per-surface pixel limits. In
  the five-panel RTX 5090 study, 8× zoom uses about 3.05 million backing pixels
  instead of 20 million, and median WebGL submission falls from 49.0 to 13.8 ms.
  Add normal/deep-zoom fidelity, visibility and re-entry checks with raw studies.

- Retain compiled-viewer backing surfaces across pans and small zoom changes,
  repaint only when resolution changes, and shrink after large zoom-outs.
  Read all SVG transforms before changing canvas dimensions. Preserve the
  existing pixel budgets, native compositing, vector export and error fallback.
- Report surface paints, resizes, reuse and allocated pixel counts. Add hardware
  before/after profiles and regressions for reuse, resolution growth, shrinking
  and context loss. Warm small-zoom submission falls from 47.8 ms to 0.5 ms in
  the measured five-panel RTX 5090 workload; startup and growth are excluded.

- Accelerate filled square, triangle, diamond and star marker batches in the
  compiled-scene viewer. Preserve exact polygon geometry, per-point sizes and
  colours, winding rules, paint order, clipping and vector SVG download.
- Add a five-panel interactive marker comparison and test complete composited
  screenshots against SVG at two display resolutions, including concave
  polygons. Self-intersections, open, outlined and curved markers stay native.
- Validate the five-panel viewer on an RTX 5090 Laptop GPU through WSL/D3D12.
  Publish timings and display comparisons; Canvas remains faster for this
  measured workload, so hardware availability is not presented as a speedup.

- Add `RenderScene.to_html()` for offline native-scene viewing, with instanced
  WebGL2 circle layers, Canvas fallback and native SVG artwork in paint order.
  Automatic selection avoids recognized software WebGL renderers. Report
  backend decisions, context loss, display limits and buffer uploads.
- Keep packed source buffers shared and immutable across browser view changes;
  reconstruct vector SVG from 64-bit records, including exact source indices.
- Add a complete interactive figure, shader/fallback/resource tests and native
  export comparisons. Keyed-row interaction migration and broader GPU geometry
  remain open; hardware performance is not inferred from software WebGL tests.

- Store dense vector scatter in immutable 36-byte marker records, preserving
  source order, per-point size/colour, physical strokes and native vector output.
  Series with at least 256 points use batches unless placement anchors or
  broken axes require individual nodes. Dense point handles become batch
  handles; source indices remain inspectable in buffers and SVG elements.
- Stream batches through SVG/PDF with bounded prototype caches, preserve
  geometric clipping and painted windows, and retain batch geometry on revisions.
- Check packed palettes against colour keys and inspect individual marker
  footprints for text overlaps, avoiding false collisions over empty cloud space.
- Add a 38,300-marker four-panel review, native-backend fidelity tests and
  reproducible construction/export/memory measurements, including a separate
  million-point construction test.

- Compile a shared native render scene for SVG, PDF and PNG, resolving styles,
  transforms, clipping and compositing once. Retain it across document exports.
- Reuse unchanged scene nodes and geometry across revisions; share small shapes
  and shaped labels by value, expose invalidation reasons and conservative
  redraw coverage, and report render-compilation work separately from layout.
- Reject missing image and font resources before native export; SVG no longer
  silently emits broken image links or substitutes an unavailable font file.
- Snapshot file-backed image bytes so completed figures survive source changes;
  detect updated image inputs on subsequent document compilation and reject
  exports using changed or missing font files.
- Add a complete six-panel scene/revision review and repeated-export benchmarks.
  Browser/GPU execution and finer layout invalidation remain open.

## 4.0.0.dev2 — 2026-09-08

Second development preview. Install explicitly with
`python -m pip install "inklet==4.0.0.dev2"`; 3.1.0 remains stable.

- Preserve open cubic segments through geometric clipping, using parameter
  subdivision and bounded adaptive measurement sampling in the clip frame.
- Add `window()` for nested, transformed visual clipping of all SVG/PDF/PNG
  paint, including glyphs, images, markers, filled curves and rounded corners.
  Keep window layout, painted bounds and authored child geometry distinct;
  expose inherited clip regions and visibility filtering through resolution.
- Preserve windows through document compilation/copying and account for hidden
  content in page-bound and path-crossing diagnostics.
- Reduce allocation in dense-line clipping; add an eight-panel rendering
  review, independent backend checks and reproducible clipping/line benchmarks.


- Share exact hatch-line geometry between SVG and PDF, with reusable local
  coverage resources and independent shape clips. Preserve holes, transforms,
  border styles and fill opacity without periodic tile seams or inherited
  border settings affecting the fill.
- Reuse hatch coverage across nearby shape sizes, retain explicit work limits,
  and add an illustrated review plus repeated/distinct-size export benchmarks.

- Correct PDF compositing for individual filled-and-stroked shapes, text halos
  and vector brushes: group opacity fades their combined paint once.
- Preserve palette and color-key PNG transparency in PDF, including partial
  palette alpha and file-backed images.
- Reuse subtree painted bounds and paint-count analysis within each PDF page
  export; nested transparency groups no longer remeasure the same glyphs for
  every ancestor. Keep inherited style/transform contexts separate and discard
  the caches after export.
- Add an illustrated compositing review, independent SVG/Poppler comparisons
  and a nested-group workload to the rendering benchmark and CI checks.

## 4.0.0.dev1 — 2026-09-08

First installable 4.0 development preview. This collects the linked-document,
data, map, engineering and scientific work since 3.1.0. APIs under
`inklet.experimental` and saved-state schemas may change between previews.
3.1.0 remains the stable release; the full 4.0 roadmap is not complete.

Install explicitly with `python -m pip install "inklet==4.0.0.dev1"`.
See the [preview guide](docs/development-preview.md) for examples and boundaries.

- Add immutable rectilinear nodal fields with explicit triangle interpolation,
  linear contours, normalized-vector RK4 streamlines and cell-linked selections.
  Preserve scalar/vector masks independently and report tracing termination.
- Add a complete contour/streamline report with analytic fixtures, source
  revisions, JSON replacement, saved states and two-width vector exports.
  Keep corner summaries distinct from interpolated field values.

- Add immutable triangle meshes with supplied scalar/vector face fields, units,
  source digests, geometric measurements and strict table correspondence.
  Link equal-scale plan views, triangle picking and calibrated vector arrows
  to plots, with fixed bins and explicit missing/zero-vector behavior.
- Add a mesh-field report with a native vector 3D reference, geometry/value/removal
  revisions, JSON replacement, saved states and exports at two physical widths.
  Preserve scalar colors by disabling lighting modulation in the 3D data view.

- Add calibrated label-image measurements with explicit region correspondence,
  missing-intensity semantics, immutable source snapshots and source digests.
  Link lossless reference images to pixel-accurate region selection and plots,
  including holes, disconnected regions and non-square pixel calibration.
- Add a scientific report with calibration, intensity and label revisions,
  saved-state reconstruction, JSON replacement, visible measurement methods and
  two-width exports. Improve canvas resolution for embedded vector labels.
  Preserve vector boundaries and labels over raster imagery;
  bound browser pixel/outline work without implicit approximation.

- Link native Inklet drawings to experimental browser tables with measured
  panel layouts, outlined vector assets, stable paint IDs, rectangular picking
  targets and per-item selection behavior across SVG/canvas/hybrid display.
- Add immutable axis-aligned box assemblies with explicit units, dimensions and
  zero-thickness sections. Add a linked engineering report with geometry
  revisions, preserved label offsets, supplied response curves, removed-ID
  reconciliation and reproducible exports at two physical widths.

- Add experimental entity-linked wide-table series with explicit numeric/date/UTC
  samples, missing-data gaps, sample-aware picking and facets. Add a complete
  real-map regional report with simulated monthly values, distributions, group
  comparisons, CSV replacement, saved-state reconstruction and two-width exports.
- Add optional Chrome/Chromium SVG-to-PDF conversion for browser scenes, with
  physical page sizing and vector-content checks. Document this separately from
  the native Diagram PDF backend.

- Add experimental linked empirical distributions and supplied interval views,
  including facets, explicit methods/populations, fixed reference curves during
  filtering and reproducible revised exports. Keep reference curves unpickable
  and honor per-mark colors across all browser backends.
- Fix timestamp hover formatting and expose ECDF fractions in tooltips and the
  accessible table without changing source columns.
- Improve shared numeric ticks: preserve scientific-label precision, very small
  values and narrow representable ranges; reject duplicate or out-of-domain
  positions. Add a four-panel before/after plotting-quality review.

- Add experimental calendar-date and UTC axes to linked plots, with measured
  calendar/millisecond ticks, explicit offset and precision rules, temporal bar
  widths and optional elapsed-time line gaps. Add opt-in temporal DataFrame
  columns, exact millisecond geometry and a simulated daily-batch revision
  workflow with browser/Python export parity checks.

- Add optional experimental pandas and Polars adapters for keyed tables, with
  explicit string IDs, column selection, immutable scalar snapshots and missing
  value normalization. Reject unsupported cells with column/row diagnostics.
  Add an illustrated workshop revision example with equivalent exports from
  both libraries and optional-dependency compatibility checks.

- Add experimental linked category panels for lines, bars and scatter, with
  explicit category order, empty panels, shared scales, within-category line
  adjacency and visible diagnostics for unassigned rows. Add a six-panel
  operations example with saved-state and data-revision workflows.
- Add opt-in shared plot margins to documents and nested grids. Faceted browser
  figures use them to preserve equal physical data scales despite differences
  in panel letters and labels; ordinary document layouts retain their defaults.

- Switch between named, Python-compiled data revisions in an offline browser
  document, with atomic preparation, explicit removed-ID policies, per-revision
  source credits and downloadable change reports. Dispose replaced renderers,
  guard in-flight operations and preserve strict saved-state validation. Add a
  real-map revision demo and browser/Python parity checks, including Unicode IDs.

- Add explicit experimental figure data replacement with preserved row identity,
  selected/filtered ID reconciliation, viewport policy and a revision report.
  Rebuild geometry and exports without mutating the old figure. Extend the real
  world map with a source-year cohort and user-supplied CSV replacement workflow.

- Make a real Natural Earth country/population map the main geographic example,
  with linked world/Europe views, pinned public-domain inputs and source years.
  Add country/continent search, explicit HTML attribution and exact integer
  table display; retain the invented region shapes as regression fixtures.

- Add experimental GeoJSON polygon/multipolygon joins and linked region maps,
  including holes, shared row identities, fixed color bins, missing values and
  clipped picking across SVG/canvas/hybrid modes. Preserve physical map aspect
  and reserve its measured layout area. Add regional analysis and geometry
  review examples, native browser fill checks and vector/raster export agreement.

- Extend the experimental browser runtime to linked lines, scatter and signed
  vertical/horizontal bars. Preserve missing/filter gaps, support reversed axes
  and nonzero baselines, and share clipped geometry with static SVG exports.
  Add a four-panel monthly operations example, directly restored HTML state,
  deterministic picking ties and a fix for pointer focus scrolling tall plots.

- Add an experimental offline scatter renderer with SVG, Canvas 2D and hybrid
  modes, clipped point picking, linked selection, filtering, page pan/zoom and
  saved-view reconstruction in Python. Preserve measured axes and outlined
  text, namespace live SVG IDs, and test browser geometry at pixel ratios 1/2.
  Publish the runnable example and a bounded backend timing/fidelity study.

- Start 4.0 phase A with experimental keyed tables and versioned selection
  state, explicit rebasing for changed data, three attributed reference
  fixtures and a finite offline linked-plot example with reproducible exports.
- Snapshot nested dataset array cells so external mutation cannot silently
  change values without invalidating compiled figures.
- Allow all-baseline bar series to retain axes and legends without drawing
  rectangles or aborting compilation.
- Add dependency/fitting/metadata compiler timings and fresh-process edit,
  resize and export benchmarks with explicit local regression ceilings.
- Keep documentation navigation against the left viewport edge on wide
  displays; remove the centered shell's 380 px outer gap at 2560 px width.

- Document the proposed 4.0 product and engine roadmap, delivery phases and
  acceptance criteria. Reserve animation and presentation authoring for 5.0.

## 3.1.0 — 2026-09-07

Improved plotting, rendering speed, diagram layout and illustrated documentation.
Existing 3.0 authoring APIs remain supported. Default axis rules are lighter and
legend layout is more compact, so existing figures can change visually.

### Plots and data

- Add typed CSV input with source hashes, exact integer identifiers and explicit
  errors for malformed rows, ambiguous headers and invalid numeric values.
- Measure axis font overrides before tick selection and layout. Add separate
  tick/axis-label sizes, including colorbars, and matching grid tick options.
- Fit top/bottom legends to measured space without shrinking labels. Preserve
  explicit axis, legend-font and column overrides.
- Add opt-in vector-line simplification after scale mapping with a physical
  tolerance. Preserve endpoints and global extrema, record reduction counts,
  and retain additional vertices when difficult paths reach the work limit.
  Exact vector geometry remains the default.

- Fix numeric NumPy scalar bar input and automatic bracket placement when
  endpoints map in descending order.
- Snapshot array inputs and fingerprint their complete contents so explicit
  replacements cannot collide through truncated NumPy representations.

### Rendering and layout

- Render dense raster scatter from shared marker prototypes. Preserve point
  order, opacity, clipping and physical marker sizes while keeping axes vector.
- Reuse immutable styles, measured geometry and fixed-component factories;
  improve grid-track allocation and shared plot-margin calculation.
- Invalidate parent document caches after edits to nested Cartesian or polar
  panels, including external inset children and secondary-axis marks.
- Preserve panel-letter space in nested fixed drawings and support compass
  alignment of artwork inside document cells without scaling typography.
- Include strokes, curves and text halos in PDF transparency-group bounds.
  Reuse image encoding within an export and reduce unnecessary PDF font tables.
- Fix intermittent missing strokes in Blender 4.2 vector exports by exporting
  a fresh drawing copy and using a single legacy bake thread.

### Diagrams

- Add measured module wrapping with `max_width`; account for label offsets and
  fail clearly when content cannot fit its explicit bounds.
- Reserve connector-label plates during routing and reconsider labels against
  later shafts, plates and loops. Add clearance candidates for crowded channels.
- Prune contained obstacles in dense diagrams with deterministic spatial checks.

### Documentation and validation

- Organize guides around plots, whole figures, diagrams and 3D, with research
  studies and project history in separate sections. Preserve existing page URLs.
- Add plot-selection, axes and dense-data guides, section-filtered search and
  versioned page links to avoid mixed cached navigation after deployments.
- Add 65 previews generated from guide/cookbook snippets, everyday CSV plots,
  rendering and diagram comparisons, and reproducible performance reports.
- Extend installed-wheel checks, visual regressions, mixed-content stress tests
  and Blender 4.2/4.5 CPU coverage. Benchmark results are workload-specific;
  see the linked reports rather than assuming every export becomes faster.

### Experimental research tools

The following ship under `inklet.experimental` in 3.1. They remain opt-in research
APIs: signatures and report schemas may change independently of stable APIs.

- Plan authored camera views and measured label positions with visibility,
  region, crossing and author-lock constraints; report infeasible requests.
- Control physical label movement during revision using costs and hard limits.
- Add calibrated immutable volumes, orthogonal/oblique sections, slab projections,
  linked regions, segmentation surfaces, channel composites and label contours.
- Add per-label intensity tables and explicit scalar TIFF/ImageJ/single-file
  OME-TIFF import, with calibration, coverage and source provenance.
- Include simulated and attributed real microscopy examples, measurement exports
  and separate manuscript captions. Numerical microscopy needs the `volume` extra.

## 3.0.0 — 2026-09-07

Complete Blender scene rendering, GPU jobs, vector annotations and browser-free
PNG export. Existing plotting, document and SVG/PDF APIs remain supported.

- Resolve font-family fallback lists in order when fontconfig is unavailable,
  fixing default-theme text on Windows without requiring extra fonts.
- Add macOS and Windows installed-wheel checks and pinned Blender 4.2/4.5
  CPU integration jobs. Document the 2.6 upgrade and tested support boundaries.
- Report an actionable error when legacy vector line-art baking is requested
  with Blender outside 4.2 LTS; complete-scene rendering remains separate.
- Let the installed render-wheel check use pip when uv is unavailable.

- Add packaged laboratory, product and architectural scene templates with
  validated parameters, named cameras/landmarks, portable geometry and atomic
  output creation. Preserve original template settings in scene provenance.
  Add a six-view comparison and a complex annotated laboratory cutaway with
  twelve callouts, a dimension, projected route, detail views and an analytic plot.
- Add scene labels, depth-tested arrows, true world-space length dimensions
  and angle measurements with editable vector exports. Preserve annotation
  bounds outside scene images, expose hidden-target policies, and record
  measured values and unit conversions. Add a complete four-panel example.
- Preserve declared crossing targets when copying diagrams and honour those
  declarations for routed leaders without suppressing unrelated crossings.
- Add saved camera projection and depth-tested vector paths. World points report
  frame membership and visibility; paths clip to the camera frustum and omit,
  dash or show hidden sections without rerendering the scene. Record overlay
  provenance and retain vector paths in SVG/PDF. Add a four-panel sensor example.
- Redesign the documentation with persistent navigation, a responsive figure
  gallery, source-backed recipe pages, keyboard search and copyable code.
  Add an original SVG logo, reusable brand assets and tutorial export previews.
- Default Cycles scenes to available GPU devices with CPU fallback when discovery
  finds none. Add explicit backend/device selection and actual-device provenance.
- Add cancellable render queues with bounded worker/GPU concurrency, progress
  updates and reuse of simultaneous identical requests within one Python process.
  Allow 900 seconds by default for first-use GPU kernel compilation.
- Add device discovery to the Python API and `inklet doctor --devices`, plus a
  multi-view rendering example and GPU/CPU integration validation.
- Correct projected dimension placement in the architectural example, improve
  its typography, and allow explicit stroke widths on dimension witness lines.
- Add draft/preview/final render quality, explicit denoising/adaptive sampling,
  scene inspection and a Cycles/Freestyle sketch style.
- Add eight curated showcase recipes, offline gallery filtering, source and
  export downloads, packed Blender scenes and a checksummed CC0 furniture asset.
  Draw wave packets from back to front so overlapping fills preserve foreground peaks.
- Ignore Blender's append-reuse hints when checking scene dependencies, so
  packed scenes render after their original asset libraries are removed.
- Add Cycles depth, world-normal and object-ID passes with immutable float32
  snapshots, NumPy export, physically aligned previews and named object masks.
- Select authored Blender view layers, validate every cached pass, and isolate
  pass extraction from authored compositor output nodes. Add a six-panel example.
- Render complete Blender scenes with named cameras, scene/frame selection,
  material and lighting preservation, projected landmarks and explicit data bindings.
- Cache scene pixels with source/asset hashes and render settings; embed snapshots
  and scene provenance in figure exports. Watch recorded scene dependencies.
- Add browser-free resvg PNG output with physical DPI, bounded small-layer caching,
  and a Chromium compatibility option. Review PNG defaults change to resvg.
- Add immutable linear/radial gradients, vector hatching and isolated group blend
  modes across SVG/PDF, plus explicit raster masks and dense-layer rasterization.
- Share repeated SVG images, record rendering capabilities/resources, and include
  resource bytes in PDF identities. Keep the ordinary core install lightweight.
- Add an original reusable Blender laboratory scene, mixed-rendering showcase,
  real Blender integration tests, cross-format pixel tests and v3 guides.

## 2.6.0 — 2026-09-06

- Add immutable scientific, educational and marketing presets, independent
  physical formats, validated overrides and a live document preset switch.
- Apply preset grids, legends and panel lettering during compilation while
  preserving explicit author styles and page overrides. Include resolved
  preset settings and guideline provenance in export manifests.
- Add Nature defaults backed by reviewed guidance and explicitly provisional
  Science/Cell styles pending verification of their publisher requirements.
- Allow publication profiles to use other themes and independent title sizes.
- Add a mixed-content preset example, SVG/PDF comparison gallery and guide.
- Check Nature print figures for text above 7 pt and page heights above 170 mm,
  including transformed text and automatic page heights.
- Add complete 16:9 slides, A4 worksheets and journal examples with SVG/PDF
  dimension tests and gallery previews.
- Configure Read the Docs hosting with version-correct source links, and make
  README images and links work on PyPI. Credit Mark Marosi in the MIT license.

## 2.5.0

- Prepare the standalone release tree with an MIT license, third-party notices,
  maintained examples, and explicit source-distribution contents.
- Refresh Blender's evaluated scene after baking Line Art so SVG exports retain
  every baked stroke. Invalidate earlier bake caches and verify fresh exports.
- Rework the README around installation, a runnable first figure and supported
  workflows. Add task-based guides, command-line and troubleshooting references,
  a searchable local documentation site and contributor instructions.
- Execute introductory documentation examples and validate links and site
  navigation in CI. Preserve the generated API reference and existing recipes.

- Add nested subfigures that share measurement caches and inherit page themes.
- Add measured compositions with named children, algebraic size/anchor references,
  cycle detection, branch and return routing, and editable architecture modules.
- Reserve panel-letter space during layout. Resolve deferred callouts after
  insets and brackets, considering measured marks and existing furniture.
- Add general publication presets for physical widths, typography, stroke sizes,
  export defaults and print-size diagnostics; record profiles in manifests.
- Add component/severity filters and search to review pages, plus saved-revision
  overlays and pixel differences. Handle size/DPI changes without invalid scores.
  Watch mode compares successive successful builds and preserves failed-build output.
- Rebuild the AlphaFold architecture and full proteome layout with public
  composition APIs, removing their custom renderer classes. Preserve the reviewed
  PDF appearance and existing SVG tolerance.
- Add a complete v2.5 example, regression coverage and installed-wheel checks.


- Migrate AlphaFold Figure 1e to measured module components and named ports;
  migrate the complete proteome figure to live plots, data and category filters.
- Add `derive()` for explicit transformations of live data dependencies.
- Consolidate thin-stroke warnings within named, intentionally touching artwork
  while retaining all targets; show component paths in HTML and JSON findings.
- Check unit tests, complete SVG/PDF figures, performance budgets and isolated
  wheel installations in GitHub Actions. Lock the scientific test dependencies.
- Preserve the native mesh when optional trimesh repair dependencies are absent.
- Avoid global theme changes when importing the Nature examples, and keep the
  generated API reference consistent across Python versions.
- Check repeated drawing identities with a set, avoiding quadratic placement
  work for dense scatter layers.

## 2.0.0

- Add live documents with versioned plot and component definitions, compiled
  snapshots, bounded geometry caches and deterministic drawing identities.
- Fit plots to physical pages with weighted tracks, spanning cells, shared
  furniture margins and explicit errors for unsatisfiable constraints.
- Add datasets, shared numeric scales, series with uncertainty, live category
  selections, units, data sources and file dependencies.
- Resolve inherited paint once for SVG and PDF while preserving clipping,
  transformations and group compositing.
- Add `inklet build`, `watch` and `doctor`, clickable SVG diagnostics, JSON
  findings, and export manifests with data, font and asset provenance.
- Add six complete v2 visual fixtures, performance budgets and compatibility
  comparisons for all four Nature Figure 1 reconstructions.
- Avoid repeated child-index construction in crowding diagnostics for large
  drawings, and isolate document themes throughout text and shape creation.

Existing Diagram, Panel and Figure APIs remain available. See
[the migration guide](docs/migration.md) and [v2 guide](docs/v2.md).
