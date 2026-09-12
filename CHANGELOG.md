# Changelog

## Unreleased

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
