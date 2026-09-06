# Changelog

## 3.0.0 (development)

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
