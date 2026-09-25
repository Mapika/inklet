---
layout: section
title: Experimental features
description: Opt-in APIs for linked interactive documents, fields, engineering reports and figure planning.
groups:
  - title: Interactive documents
    text: Offline HTML pages whose plots share selections, filters and saved views, reconstructable in Python.
    cards:
      - title: Linked plots
        page: linked-plots.md
        image: assets/v4/linked-dashboard.png
        text: Lines, bars and scatter that share a selection through stable row IDs.
      - title: Category panels
        page: linked-facets.md
        image: assets/v4/faceted-operations.png
        text: One panel per category with shared scales and a shared selection.
      - title: Region maps
        page: linked-maps.md
        image: assets/v4/world-population.png
        text: Regional maps joined to values through explicit geometry keys and bins.
      - title: Points, routes and regions
        page: geographic-features.md
        image: assets/v4/transport-map.png
        text: Mixed GeoJSON features linked to bars and histories.
      - title: Dates and time series
        page: time-series.md
        image: assets/v4/time-series.png
        text: Calendar dates and UTC times on linked axes.
      - title: Distributions and intervals
        page: statistical-views.md
        image: assets/v4/statistical-views.png
        text: Empirical distributions and supplied intervals with stated methods.
      - title: pandas and Polars inputs
        page: table-inputs.md
        image: assets/v4/table-inputs.png
        text: Data frames as sources for linked panels.
      - title: Replace source data
        page: data-revisions.md
        image: assets/v4/world-population-revisions.png
        text: Swap the data behind a figure with an explicit policy for missing IDs and a revision report.
      - title: Edit plot appearance
        page: visual-editing.md
        image: assets/v4/visual-overrides.png
        text: Source-bound colour and marker overrides with undo and Python reconstruction.
  - title: Complete reports
    cards:
      - title: Regional report
        page: regional-report.md
        image: assets/v4/regional-report.png
        text: European country boundaries linked to monthly rates, a distribution and category comparisons.
      - title: World map
        page: world-map.md
        image: assets/v4/world-population-2019.png
        text: Real country geometry and population estimates in linked world and Europe views.
      - title: Engineering report
        page: engineering-report.md
        image: assets/v4/engineering-report.png
        text: Plan, section, system diagram and component response curves with a shared selection.
      - title: Image measurements
        page: scientific-report.md
        image: assets/v4/scientific-report.png
        text: A calibrated intensity image and label map above region measurements.
      - title: Mesh fields
        page: mesh-fields.md
        image: assets/v4/mesh-fields.png
        text: Scalar face colours and vector arrows on a 3D surface, linked to a scatter plot.
      - title: Contours and streamlines
        page: contours-streamlines.md
        image: assets/v4/contours-streamlines.png
        text: Scalar contours, streamlines and cell means linked to a scatter plot.
  - title: More previews
    cards:
      - title: Choose an interactive workflow
        page: interactive-documents.md
        text: Compare the viewer, the linked-plot documents and the editors, and what each one saves.
      - title: Research preview
        page: research-preview.md
        text: Choose scene views and label positions together, and keep an author's earlier choices during revision.
---
# Experimental features

These APIs are included in the stable package under `inklet.experimental`, but
you opt in to each one. Their signatures, report schemas and saved-file formats
may change between releases. See the
[support and saved-file policy](compatibility.md#api-and-saved-file-policy)
before relying on a saved state format.

Still experimental in 4.3: linked browser documents (`inklet.experimental.browser`),
mesh and grid fields (`fields`, `grid`), engineering drawings (`engineering`),
image measurement (`measurement`) and the figure planner (`figure_planner`,
`planner_geometry`).

Graduated in 4.3, and covered by the stable compatibility policy:

| Now stable | Was | Guides |
| --- | --- | --- |
| `inklet.volume` | `inklet.experimental.volume`, `sections`, `slabs`, `regions`, `channels`, `contours`, `measurements`, `tiff` | [Microscopy volumes](volumes.md) |
| `inklet.selection` | `inklet.experimental.selection` | [Live data and categories](data.md), [pandas and Polars inputs](table-inputs.md) |
| `inklet.project` | `inklet.experimental.project` | [Figure projects](project-workflows.md) |
| `inklet.editor` | `inklet.experimental.layout_editor` | [Local layout editor](layout-editor.md), [Save layout choices](layout-overrides.md) |

The old paths still work and return the same objects; see
[migration](migration.md#from-42-to-43). The compiled scene viewer runtime is
now private; open it with `RenderScene.to_html()` ([figure viewer](compiled-viewer.md)).

<!-- cards -->
