# Inklet 4.0 scope and release gates

<span id="roadmap-to-inklet-40"></span>

**4.2.0 is the current stable release.** 4.0.0 released the scope frozen
during RC1; 4.1.0 and 4.2.0 add plot types within it. These gates continue to apply to
later releases; experimental namespaces retain their documented opt-in status.

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

## Release acceptance checklist

| Gate | Current evidence | Remaining release work |
| --- | --- | --- |
| Three reference workflows | Regional, engineering and calibrated-image reports have revision/browser/export tests; the mixed project adds bundling and editor reopen | Skip-free `tools/acceptance.py` gate implemented; review the exact candidate's results, including supported failure cases |
| Cross-content identity | Explicit local-to-entity mappings, canonical table joins, mapped drawings/images/fields and composition paths | Adapter subset declared in compatibility; verify exact candidate results |
| Reusable assets | Explicit source/license/unit inventory, copied files verified by SHA-256, trusted-factory reopening | Schema policy documented; experimental imports remain opt-in |
| Reproducible authoring | Layout, text, style and native-camera overrides; old schemas load; source revisions report conflicts | Supported controls and 3.1-to-4.0 migration documented; review candidate exports |
| Render/cache correctness | Numerical and adversarial contracts, clean/cached comparisons, independent PDF and complete-figure visual checks | Require green results on the exact candidate; review any visual changes explicitly |
| Offline interaction and accessibility | Chromium integration, keyboard controls and data-table alternatives | Linux Chromium target and keyboard/data-table evidence declared; review exact candidate results; other browsers remain unverified |
| Performance | Cold/cached/edit/resize/export benchmarks, native budgets, dense-field measurements | Project, reference-report and software-browser budgets implemented; review exact candidate measurements without relaxing thresholds |
| Distribution | Linux/macOS/Windows wheel checks, two Blender CPU versions, optional dependency checks | Complete candidate CI, sdist-to-wheel rebuild, isolated installs, exact artifact checksums and docs verification |

The [acceptance guide](acceptance.md) maps workflows to commands and failure
oracles. [Release checks](release-checks.md) and [compatibility](compatibility.md)
define the distribution procedure and supported environments.

## Frozen scope

The [API and saved-file policy](compatibility.md#api-and-saved-file-policy)
now declares the bounded 4.0 support scope. Individual axis-label editing,
camera dragging, depth-aware browser 3D picking, interactive volumes, additional
projections and broader GPU primitives are deferred beyond 4.0. Native camera
inspector edits are included. Experimental APIs retain their opt-in namespace.

Full serialized Python projects and arbitrary geometry constraints are not implied
by reusable manifests. Projects reopen through an explicitly supplied trusted
recipe. Mapped image/mesh picking retains its source adapter's geometry limits.

## Maintenance release requirements

1. Keep the shared acceptance suite and all declared performance budgets green.
2. Review candidate migration reports, saved-file compatibility and browser evidence.
   RC1 has a [recorded cross-version review](migration.md#recorded-migration-checks);
   archived 3.1 API and dev16 saved-file contracts now run in CI.
3. Fix regressions within the supported scope; use a new package version for changed release files.
4. Run the full release checks on the final commit and publish the exact verified artifacts.

Each release, such as [4.2.0](https://github.com/Mapika/inklet/releases/tag/v4.2.0),
links to its exact-commit validation. Distribution checks include source-archive rebuilding,
isolated wheel installs and matching GitHub/PyPI archive checksums. A passing
prerelease does not automatically publish or designate a stable release.

## After 4.0

Animation, timelines, transitions, camera paths, video/GIF and presentation
authoring remain the **5.0 direction**. Existing presentation styling presets
continue to work. Earlier proposals and measurements are preserved in
[development history](development.md#earlier-releases-and-studies); they are not additional release checklists.
