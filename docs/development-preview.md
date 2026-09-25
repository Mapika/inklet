# Inklet 4.0

<span id="install-the-40-release-candidate"></span>

<span id="install-the-40-development-preview"></span>

**4.0.1 is the stable release** on GitHub and PyPI. It includes scientific
figure authoring, compact dense-field PDFs and reproducible interactive workflows
within the [documented support scope](compatibility.md#api-and-saved-file-policy).
Experimental imports retain their opt-in status. This page keeps its historical
URL so links from the development previews continue to work.

```sh
python -m pip install "inklet==4.0.1"
# Optional rendering and table integrations:
python -m pip install "inklet[render,pandas,polars]==4.0.1"
```

Python 3.11 or later and an installed font are required. See
[installation](installation.md) and the [support matrix](compatibility.md).
An ordinary upgrade selects stable 4.0.1. Exact pins preserve the package version
used by an archived recipe.

To reproduce this release from a checkout:

```sh
git clone --branch v4.0.1 https://github.com/Mapika/inklet.git
cd inklet
python -m pip install -e ".[render]"
```

## Current guides

Use the capability guides for current behavior. Release-by-release changes live
in the [changelog](../CHANGELOG.md), rather than duplicated installation tutorials.

| Workflow | Guide |
| --- | --- |
| Linked plots, maps and supplied measurements | [Interactive documents](interactive-documents.md) |
| Named reusable figure content | [Compositions](composition-recipes.md) |
| Visual labels, layout, styles and native cameras | [Local editor](layout-editor.md) |
| Saved override format and reconciliation | [Saved layouts](layout-overrides.md) |
| Verified inputs and shared entity IDs (introduced in dev16) | [Figure projects](project-workflows.md) |
| Dense scientific figure authoring | [Scientific authoring](scientific-authoring.md), [complex plates](complex-figures.md) |
| Performance measurements | [Rendering engine](rendering-engine.md) |

## Compatibility

APIs under `inklet.experimental`, including figure projects and linked documents,
remain opt-in. Keep source data, the recipe and the exact package version with
saved states. Reconcile input revisions explicitly; a state file is not a Python
program or a substitute for its source assets.

Standalone linked HTML embeds its supported operations and data. The composition
editor requires a local Python session. Native camera controls do not imply
standalone 3D orbiting, depth-aware picking or Blender camera editing.

See the [4.0 release checklist](roadmap.md) for the support scope and release gates and the
[historical studies](development.md#earlier-releases-and-studies) for earlier prototypes.
