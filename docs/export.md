---
layout: section
title: Export and review
description: SVG, PDF and PNG from one compiled geometry, lint diagnostics, review bundles, revision comparison, the layout editor and figure projects.
groups:
  - title: Export and inspect
    cards:
      - title: Export, diagnostics and revisions
        page: export-review.md
        image: gallery/plot-engine-review.png
        text: Save SVG and PDF with embedded or outlined text, write a review bundle, and compare two revisions.
      - title: Figure viewer in HTML
        page: compiled-viewer.md
        image: gallery/compiled-scene-viewer.png
        text: An offline HTML viewer that uses the same compiled geometry, text and paint order as SVG and PDF export.
      - title: Dense figure lint report
        page: dense-figures.md
        image: gallery/dense-figure.png
        text: The dense page example prints its diagnostics with thresholds set by the scientific.cell preset.
  - title: Projects and layout editing
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
  - title: Checks and references
    cards:
      - title: Inspect diagnostics
        page: export-review.md#inspect-diagnostics
        text: Filter findings by component and severity, and locate each one in the vector view.
      - title: Diagnostic codes
        page: api.md#diagnostic-codes
        text: What each lint rule reports, from TINY_TEXT and HAIRLINE to LINK_CROSSES and KEY_MISMATCH.
      - title: Journal guidance and checks
        page: presets.md#journal-guidance-and-checks
        text: Minimum text size, stroke width and resolution per preset, and what the checks cannot verify.
      - title: Common diagnostics
        page: troubleshooting.md#common-diagnostics
        text: Typical findings and the change that resolves each one.
      - title: Build and watch from the command line
        page: cli.md
        text: inklet build writes the review bundle; watch mode rebuilds and compares on each save.
      - title: Compare revisions
        page: export-review.md#compare-revisions
        text: An opacity slider and amplified difference image between two builds of the same page size.
---
# Export and review

`doc.compile()` resolves the layout once. SVG, PDF and PNG are all written from
that compiled snapshot, so the three files have the same geometry. Text is
embedded as searchable, editable text by default; `text='outline'` converts it
to paths. Page dimensions are millimetres, and preview DPI changes only the
PNG pixel size.

```python
figure = doc.compile()
figure.save('figure.svg', 'figure.pdf')
print(figure.report())
```

`figure.lint()` returns diagnostics for the compiled page: text below the
minimum size, strokes too thin to print, overlapping or crowded labels,
content outside its panel, low contrast, colour keys that do not match their
marks, and connectors that cross shapes. `figure.report()` formats them as
text. The thresholds come from the preset, and can be passed as keywords.

`inklet.editor.LayoutEditor` opens a local browser editor for placement,
labels, styles and cameras, saved as overrides beside the Python recipe.
`inklet.project.FigureProject` bundles those choices with verified inputs so a
figure can be reopened and rebuilt later.

<!-- cards -->
