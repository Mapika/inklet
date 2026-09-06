# Inklet documentation

Inklet builds scientific figures from Python. A figure can contain plots,
measured diagrams, images and native 3D artwork, with shared typography and
physical SVG/PDF dimensions.

## Start here

1. [Install Inklet](installation.md) and check fonts and optional renderers.
2. [Build your first figure](quickstart.md), edit its data and export a review.
3. Read [the authoring model](concepts.md) to understand definitions, snapshots,
   units and caching.

## Build a figure

| You want to… | Read |
|---|---|
| Apply scientific, educational or branded styling | [Presets](presets.md) |
| Arrange panels, labels and spanning rows | [Page layout](layout.md) |
| Choose scales, draw marks and add insets | [Plotting](plotting.md) |
| Share data, colours, units and provenance | [Live data](data.md) |
| Draw measured architecture and connected components | [Diagrams](diagrams.md) |
| Add a mesh, generated solid or image | [3D and images](three-images.md) |
| Save, inspect or compare a finished figure | [Export and review](export-review.md) |
| Build from a script or watch files | [Command-line reference](cli.md) |
| Resolve an error or diagnostic | [Troubleshooting](troubleshooting.md) |

## Examples and reference

[The example gallery](examples.md) connects complete figures to their source
scripts. Start with the small examples before running the
[twenty-panel stress test](stress20.md).

- [API reference](api.md): generated signatures, public methods and diagnostic codes.
- [Cookbook](cookbook.md): tested recipes for the direct drawing API.
- [Publication plot controls](publication-plots.md): categorical colours,
  external insets and raster scatter details.
- [Diagram components](diagram-components.md): matrices, sequences and databases.

## Existing users and contributors

The guides describe Inklet 2.6, including [presets and physical formats](presets.md).
The direct drawing API is still supported.
[Migration](migration.md) covers both the old package name and moving to live
documents. [V2](v2.md) and [v2.5](v2.5.md) document their respective additions.

For development, see [contributing](../CONTRIBUTING.md),
[release checks](release-checks.md), [the compilation contract](design/v2.md)
and [the changelog](../CHANGELOG.md). The older
[page-grid design study](design/page_grid.md) describes a pre-v2 decision,
not the current document API.

The [v3 development build](v3.md) adds complete [Blender scenes](blender-scenes.md),
browser-free PNG export and vector gradients, hatching and blending.
