---
layout: section
title: Figures and layout
description: Build whole figure pages in millimetres, from a two-panel figure to a thirteen-panel journal page.
groups:
  - title: Whole pages
    text: A document has a physical page width. Plots, diagrams, images and 3D panels are placed in its cells.
    cards:
      - title: Dense figure pages
        page: dense-figures.md
        image: gallery/dense-figure.png
        text: Thirteen panels on one 183 mm page with the scientific.cell preset, and the calls behind each panel.
      - title: Rebuild a journal figure
        page: journal-figure.md
        image: gallery/journal-figure.png
        text: A published Cell figure page rebuilt step by step, from the grid and preset to lint and export.
      - title: Panel layout in millimetres
        page: layout.md
        image: assets/guides/layout-3.png
        text: Rows, columns, spans, nested subfigures and panel letters on a page of fixed width.
      - title: Presets and journal styles
        page: presets.md
        image: gallery/presets.png
        text: Type sizes, strokes, palettes and page formats for journals, slides and posters.
      - title: Reusable compositions
        page: composition-recipes.md
        image: assets/guides/composition-recipes.png
        text: Named slots and measured placement, instantiated with different plots or diagrams.
  - title: Scientific plates
    text: Larger figures that combine anatomy, diagrams, microscopy and plots.
    cards:
      - title: Scientific figure gallery
        page: scientific-gallery.md
        image: assets/scientific/olfactory.png
        text: Fly-brain plates with anatomy renders, projection routes, arbors and connectivity networks.
      - title: Coordinated biology figure
        page: biology-panels.md
        image: gallery/biology-panels.png
        text: Six panels from 4,500 synthetic cells and 60 genes, derived from one set of measurements.
      - title: Twenty-panel figure
        page: stress20.md
        image: gallery/stress20.png
        text: A 360 × 440 mm plate with 3D, diagrams, 30,000 points and twenty nested subfigures.
  - title: Techniques for scientific plates
    cards:
      - title: Complex scientific plates
        page: complex-figures.md
        text: Dense fields, exact data rectangles, keys that follow the plot, and separate review of provenance and geometry.
      - title: Scientific illustrations
        page: scientific-authoring.md
        text: Measured labels, authored arrows and one camera fitted to every registered anatomical layer.
      - title: Insets and shared categories
        page: publication-plots.md
        text: Grouped categories that stay aligned across panels, external insets and dense scatter.
  - title: Revise and edit
    cards:
      - title: Export and review
        page: export.md
        text: Save SVG, PDF and PNG from one compiled snapshot and check it with lint diagnostics.
      - title: Figure projects
        page: project-workflows.md
        text: Keep source files, layout edits and object IDs together while the data change.
        tag: Experimental
      - title: Save layout choices
        page: layout-overrides.md
        text: Store placement and size edits separately from the recipe and restore them after a data change.
        tag: Experimental
      - title: Local layout editor
        page: layout-editor.md
        text: Arrange named content in a local browser editor and review the compiled figure.
        tag: Experimental
---
# Figures and layout

An Inklet figure is a page with a physical width, such as 89 mm for a single
journal column or 183 mm for a double column. Cells on that page hold plots,
diagrams, images and 3D scenes. Before each plot's data area is placed, Inklet
measures its axis labels, tick labels and legend with the embedded font, so
the text keeps its point size when the page is resized.

<!-- cards -->

## Where to start

For a first page, follow the [first figure tutorial](quickstart.md). For
many small panels, start from [dense figure pages](dense-figures.md) and the
`scientific.cell` preset. For a layout that is reused with different content,
use [reusable compositions](composition-recipes.md).
