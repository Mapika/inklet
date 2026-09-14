# Roadmap to Inklet 4.0

This is the current release checklist, updated during **4.0.0.dev16** development.
Dev14, dev15 and dev16 are published previews; 3.1.0 remains stable. A development
release does not establish the compatibility guarantees of an RC.

## Product scope

4.0 connects plots, maps, diagrams, images and native 3D in reproducible Python
figures and supported interactive documents. Authors should be able to select
related content, edit named choices, save, reopen, replace inputs, resize and
export without losing those choices or their meaning.

The release includes ordinary table-to-plot workflows, offline linked HTML,
bounded technical/scientific adapters, a local composition editor, reusable
compositions and source manifests. Rendering and numerical limitations must be
explicit. Inklet does not become a CAD modeller or statistical inference engine.

## Implemented foundations

- Native SVG/PDF/PNG, measured layout, clipping, scientific annotations, exact-color
  vector matrices, field rendering and shared-camera anatomical illustrations.
- Keyed tables, optional pandas/Polars adapters, facets, UTC/calendar axes, missing
  values, supplied intervals, linked maps and explicit data revisions.
- Standalone linked selections with data-table alternatives and static reconstruction.
- Named compositions and ports; saved labels, layout, styles and native cameras;
  undo/redo, orphan reporting and a Python-backed editor.
- Dev16 project bundles with verified asset manifests, explicit entity mappings,
  source-native image/drawing/field selection adapters and project reconstruction.
  These are experimental contracts; see [figure projects](project-workflows.md).

## RC acceptance checklist

| Gate | Current evidence | Remaining release work |
| --- | --- | --- |
| Three reference workflows | Regional, engineering and calibrated-image reports have revision/browser/export tests; the mixed project adds bundling and editor reopen | Keep one executable acceptance entry point; review the exact candidate's results, including supported failure cases |
| Cross-content identity | Explicit local-to-entity mappings, canonical table joins, mapped drawings/images/fields and composition paths | Confirm the declared adapter subset; do not infer identity from display text or row position |
| Reusable assets | Explicit source/license/unit inventory, copied files verified by SHA-256, trusted-factory reopening | Document project/schema compatibility before promising stable saved files |
| Reproducible authoring | Layout, text, style and native-camera overrides; old schemas load; source revisions report conflicts | Freeze the supported controls and upgrade policy; add 3.1-to-4.0 migration guidance |
| Render/cache correctness | Numerical and adversarial contracts, clean/cached comparisons, independent PDF and complete-figure visual checks | Require green results on the exact candidate; review any visual changes explicitly |
| Offline interaction and accessibility | Chromium integration, keyboard controls and data-table alternatives | Publish the supported-browser claim and its acceptance evidence; other browsers remain unverified |
| Performance | Cold/cached/edit/resize/export benchmarks, native budgets, dense-field measurements | Apply declared budgets to supported complete editing/interaction workflows; do not silently relax thresholds |
| Distribution | Linux/macOS/Windows wheel checks, two Blender CPU versions, optional dependency checks | Complete candidate CI, sdist-to-wheel rebuild, isolated installs, exact artifact checksums and docs verification |

The [acceptance guide](acceptance.md) maps workflows to commands and failure
oracles. [Release checks](release-checks.md) and [compatibility](compatibility.md)
define the distribution procedure and supported environments.

## Scope decisions before RC

Freeze a bounded support statement before stabilizing APIs. Individual axis-label
editing, camera dragging, depth-aware browser 3D picking, interactive volumes,
additional projections and broader GPU primitives remain open. Decide explicitly
which belong in 4.0 and which move to later 4.x. The current native camera
inspector is implemented; it is no longer an upcoming feature.

Full serialized Python projects and arbitrary geometry constraints are not implied
by reusable manifests. Projects reopen through an explicitly supplied trusted
recipe. Mapped image/mesh picking retains its source adapter's geometry limits.

## Development order

1. Complete and review the shared project acceptance workflows and documentation.
2. Settle remaining support decisions, public API stability and saved-state policy.
3. Finish migration guidance and the supported browser/performance matrix.
4. Freeze RC1, run the full release checks and publish the validated artifacts.

## After 4.0

Animation, timelines, transitions, camera paths, video/GIF and presentation
authoring remain the **5.0 direction**. Existing presentation styling presets
continue to work. Earlier proposals and measurements are preserved in
[development history](history.md); they are not additional release checklists.
