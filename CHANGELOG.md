# Changelog

## Unreleased

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
