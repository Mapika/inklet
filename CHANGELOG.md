# Changelog

## 3.1.0.dev11 — development preview (unreleased)

- Reserve connector-label plates during placement and reconsider labels against
  later shafts and relocated loops. Try additional local clearance when closely
  spaced channels leave no room directly beside a line.
- Add `module(..., max_width=...)` for measured text wrapping. Include label
  offsets in module dimensions; fail clearly when content cannot fit its limits.
- Prune contained routing obstacles with a spatial sweep, including diagrams
  above the previous 200-obstacle cutoff. Preserve deterministic duplicate ties.
- Add an architecture review, before/after label specimens and reproducible
  dense-graph benchmarks, with external captions and CI checks.

## 3.1.0.dev10 — development preview (unreleased)

- Render dense raster scatter directly from shared marker prototypes, preserving
  input order, opacity, clipping, physical marker sizes and vector axes.
- Reuse immutable styles and measured geometry; avoid rebuilding fixed component
  factories during layout passes and page resizes. Solve ordinary grid tracks
  directly and share plot margins without pairwise cell scans.
- Reserve panel-letter space for fixed drawings inside nested grids. Add compass
  cell alignment (`align='nw'`, etc.) without scaling artwork or typography.
- Include strokes, curves and text halos in PDF transparency-group bounds so
  compositing cannot clip ink to its narrower layout envelope.
- Avoid repeated image encoding/hashing within an export and skip unused shaping
  tables when embedding already-shaped PDF glyphs. Keep SVG font shaping intact.
- Add fresh-process rendering benchmarks, a four-panel review figure and a
  before/after PDF comparison, with external captions and reproducible recipes.

## 3.1.0.dev9 — development preview (unreleased)

- Refine plot appearance with lighter default axes and top/bottom legends that
  fit their columns to measured space without shrinking labels. Measure explicit
  legend font sizes before layout; preserve explicit axis and column overrides.
- Add typed local CSV input with source hashes, exact integer identifiers and
  clear errors for malformed rows, ambiguous headers and invalid numeric values.
- Add a six-panel general plotting example spanning machine learning, engineering
  and business, with simulated CSV inputs, a styling comparison and external captions.
- Rebalance the gallery and development overview across plotting, diagrams,
  architecture and scientific applications.

## 3.1.0.dev8 — research preview (unreleased)

- Add per-label native and sampled intensity tables with explicit coverage,
  physical region selection, exact label identities and CSV/JSON exports.
- Add local scalar TIFF, ImageJ and single-file OME-TIFF import with explicit
  calibration, channel identities, time selection and hashed source provenance.
- Add a six-panel real microscopy example linking contours to intensity means,
  within-component spread, section comparisons and native region fractions.
  Keep manuscript prose in separate LaTeX/text captions and export panel artwork
  without embedded titles or descriptions.

## 3.1.0.dev7 — research preview (unreleased)

- Add registered microscopy channel composites with explicit display windows,
  weights, additive RGB clipping reports and missing-channel coverage policies.
- Add exact vector label-pixel boundaries, preserving integer IDs, holes and
  disconnected regions while distinguishing observed edges from coverage limits.
- Add a nine-panel real fluorescence example using hash-locked Allen Institute
  data, with calibrated zooms, generated-label provenance, profiles and measurements.

## 3.1.0.dev6 — research preview (unreleased)

- Add physical slab mean, minimum and maximum intensity projections with streaming
  reduction, per-pixel contributing counts and explicit missing-data handling.
- Link stable box regions across oblique sections, depth-restricted projections,
  3D outlines and source-grid measurements preserving exact integer label IDs.
- Add a nine-panel real COSEM figure with coverage maps, ROI depth profiles,
  numerical evidence and executable documentation.

## 3.1.0.dev5 — research preview (unreleased)

- Add explicit physical oblique section planes shared by microscopy, label masks
  and saved-camera 3D annotations. Preserve anisotropic source calibration.
- Use floating-point trilinear intensity sampling and exact nearest-neighbour
  integer label sampling, with immutable results and separate coverage masks.
- Add vector scale bars, world/page projection, transparent missing coverage and
  sampled label-area measurements with recorded interpolation conventions.
- Add a seven-panel real COSEM example with two section planes, matching masks,
  cross-sectional area comparisons and marked intensity profiles. Keep plane
  corners inside the rendered frame and retain source and sampling evidence.

## 3.1.0.dev4 — research preview (unreleased)

- Add an optional calibrated volume API for immutable ZYX arrays, physical XYZ
  coordinates, crops, orthogonal slices, vector scale bars and label measurements.
- Extract calibrated segmentation surfaces with explicit consent for artificial
  boundary caps. Keep display subsampling separate from voxel-count measurements.
- Add a six-panel real COSEM microscopy example with GPU-rendered organelles,
  source-ID callouts, matching sections and volume charts. Record source hashes,
  calibration, overlapping masks, boundary flags and rendering evidence.
- Document the experimental API, executable recipe and CC BY 4.0 data attribution.
- Fix intermittent missing strokes in Blender 4.2 SVG exports by exporting a
  fresh copy of the baked drawing and using a single legacy bake thread.
  Exercise export integrity under constrained CPU allocations and in CI.

## 3.1.0.dev3 — research preview (unreleased)

- Add optional physical label-displacement costs and hard per-label movement
  limits during figure revision, including page and stacked-panel changes.
- Report every objective term, prior page positions and movement constraints
  in experimental figure-plan schema 0.3.
- Add a controlled page-revision study and a six-panel biology example with
  4,500 synthetic cells, shared expression data, area-scaled marker fractions,
  distributions, annotated mean shifts and gene correlations.

## 3.1.0.dev2 — research preview (unreleased)

- Add author-supplied surface regions with minimum visible-sample fractions and
  projected extents, evaluated at each candidate image size.
- Add optional crossing penalties with bounded, deterministic label moves and
  swaps that preserve visibility requirements and author locks. Report the
  distinction between exact linear assignment and local crossing refinement.
- Record label positions and physical displacement during revisions.
- Add a reproducible four-scene, three-width study comparing point constraints,
  region constraints and crossing-aware planning, including infeasible cases.

## 3.1.0.dev1 — research preview (unreleased)

- Add an opt-in experimental planner for camera subsets, measured vector labels
  and page sizes, with explicit visibility constraints and infeasibility reports.
- Preserve stable target identities, required views and author label-slot locks;
  penalize changed choices when revising a previous plan.
- Add explicit immutable length conversion for shared dimension/caption values.
- Add a procedural laboratory comparison with independent and joint baselines,
  a geometry/page revision, recorded failures and reproducible JSON evidence.


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
