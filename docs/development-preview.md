# Install the 4.0 development preview

**4.0.0.dev16** is the published preview on GitHub and PyPI. **3.1.0** remains
the stable release. This preview adds dense-field PDF improvements and reusable
figure projects with verified assets, saved edits and cross-content identities.

```sh
python -m pip install "inklet==4.0.0.dev16"
# Optional rendering and table integrations:
python -m pip install "inklet[render,pandas,polars]==4.0.0.dev16"
```

Python 3.11 or later and an installed font are required. See
[installation](installation.md) and the [support matrix](compatibility.md).
Exact version pins opt into a preview; ordinary upgrades prefer stable releases.

To reproduce this preview from a checkout:

```sh
git clone --branch v4.0.0.dev16 https://github.com/Mapika/inklet.git
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
| Verified inputs and shared entity IDs (dev16) | [Figure projects](project-workflows.md) |
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

See the [RC checklist](roadmap.md) for outstanding release work and the
[historical studies](history.md) for earlier prototypes.
