---
layout: section
title: Experimental features
description: Opt-in APIs for interactive documents, layout editing, microscopy volumes and figure planning.
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
  - title: Layout editing and projects
    cards:
      - title: Local layout editor
        page: layout-editor.md
        image: assets/guides/editor-studio.png
        text: Move named objects, edit labels and styles, and set a camera, then review the recompiled figure.
      - title: Save layout choices
        page: layout-overrides.md
        image: assets/guides/layout-restored.png
        text: Store placement and size edits apart from the recipe and restore them after the data change.
      - title: Figure projects
        page: project-workflows.md
        image: assets/guides/project-workflow.png
        text: Keep input hashes, provenance, object IDs and editor choices together.
  - title: Microscopy
    text: Calibrated volumes keep voxel spacing and origin attached to image and segmentation arrays. Install the volume extra.
    cards:
      - title: Calibrated volumes
        page: calibrated-volumes.md
        image: assets/guides/calibrated-volumes-3.png
        text: Crops, slices, scale bars, measured volumes and surfaces in physical coordinates.
      - title: Oblique sections
        page: oblique-sections.md
        image: assets/guides/oblique-sections-2.png
        text: Sample an arbitrarily oriented plane with its own scale bar and 3D outline.
      - title: Slab projections and regions
        page: slabs-and-regions.md
        image: assets/guides/slabs-and-regions-1.png
        text: Finite-thickness projections and one box region shared by every view.
      - title: Channels and contours
        page: channels-and-contours.md
        image: assets/guides/channels-and-contours-1.png
        text: Channel composites and exact vector contours of segmentation labels.
  - title: Microscopy examples
    text: Complete figures from public microscopy data.
    cards:
      - title: Real microscopy and organelles
        page: real-biology.md
        image: gallery/real-biology.png
        text: FIB-SEM sections, organelle surfaces and volume charts from one HeLa crop.
      - title: Shared oblique planes
        page: oblique-biology.md
        image: gallery/oblique-biology.png
        text: Two physical planes shown in a 3D scene, as sections and as measurements.
      - title: Linked slab regions
        page: slab-biology.md
        image: gallery/slab-biology.png
        text: Slab projections and one region box across nine panels.
      - title: Fluorescence channels
        page: fluorescence-biology.md
        image: gallery/fluorescence-biology.png
        text: Two-channel fluorescence with composites, contours, profiles and areas.
      - title: Labels to intensity plots
        page: label-intensities.md
        image: gallery/label-intensities.png
        text: Segmentation labels, region zooms and per-label intensity statistics.
  - title: More previews
    cards:
      - title: Choose an interactive workflow
        page: interactive-documents.md
        text: Compare the viewer, the linked-plot documents and the editors, and what each one saves.
      - title: Per-label intensities
        page: label-measurements.md
        text: measure_labels returns per-label intensity statistics from calibrated volumes.
      - title: TIFF import
        page: microscopy-tiff.md
        text: Read microscopy TIFF files into calibrated Volume objects.
      - title: Research preview
        page: research-preview.md
        text: Choose scene views and label positions together, and keep an author's earlier choices during revision.
---
# Experimental features

These APIs are included in the stable package, mostly under
`inklet.experimental`, but you opt in to each one. Their signatures, report
schemas and saved-file formats may change between releases. See the
[support and saved-file policy](compatibility.md#api-and-saved-file-policy)
before relying on a saved state format.

<!-- cards -->
