---
layout: section
title: Development notes
description: Release process, engine measurements, design notes and earlier release guides.
groups:
  - title: Releases and process
    cards:
      - title: Inklet 4.0
        page: development-preview.md
        text: What the 4.0 release includes, kept at its preview-era URL.
      - title: Roadmap and release gates
        page: roadmap.md
        text: The 4.0 scope and the gates that still apply to maintenance releases.
      - title: Release checks
        page: release-checks.md
        text: CI workflow, documentation hosting and package publication.
      - title: Acceptance workflows
        page: acceptance.md
        text: The end-to-end suite that runs complete user workflows.
      - title: Logo and brand assets
        page: brand.md
        text: The Inklet logo and icon as SVG, with usage notes.
  - title: Engine studies
    text: Measurements recorded at named development revisions. They are not current performance budgets.
    cards:
      - title: Rendering and layout review
        page: rendering-engine.md
        text: Engine measurements across development revisions.
      - title: Shared plotting quality
        page: plot-quality.md
        text: Before and after comparison of the shared plot defaults.
      - title: Diagram engine review
        page: diagram-engine.md
        text: Module wrapping, connector labels and dense routing measurements.
      - title: Transparency and compositing
        page: compositing.md
        text: Group opacity and blending in SVG and PDF.
      - title: Vector hatching
        page: hatching.md
        text: Reusable hatch patterns and their PDF output.
      - title: Curves and painted windows
        page: clipping.md
        text: clip() versus window(), and what each crops.
      - title: Shared compiled scenes
        page: compiled-scenes.md
        text: The revision that introduced compiled scenes for the viewer.
      - title: Packed markers
        page: marker-batches.md
        text: Immutable marker records for dense vector scatter.
      - title: Spatial marker culling
        page: marker-culling.md
        text: Spatial index for markers in the browser viewer, with hardware measurements.
  - title: Design notes
    cards:
      - title: Compilation contract
        page: design/v2.md
        text: What the compiler keeps from the direct drawing API and what it evaluates.
      - title: Plot capability gaps
        page: design/capability-gaps.md
        text: Plot types that dense journal figures needed, and their status.
      - title: Documentation structure
        page: design/docs-structure.md
        text: Audit of every documentation page and the navigation built from it.
---
# Development notes

Material for contributors and for readers following Inklet's development. For
supported behaviour, use the guides; each page below links to the current
guide where one exists. The [contributing guide](../CONTRIBUTING.md) and the
[changelog](../CHANGELOG.md) are in the repository.

<!-- cards -->

## Earlier releases and studies

These pages keep earlier release notes, prototype decisions and benchmark
results at their original URLs, so existing links and anchors still work.
They are excluded from documentation search.

| Historical material | Current guide |
| --- | --- |
| [Inklet v2](v2.md) | [The authoring model](concepts.md) |
| [Inklet 2.5](v2.5.md) | [Panel layout](layout.md) |
| [Rendering in v3](v3.md) | [Meshes and images](three-images.md) |
| [4.0 foundations: selection and engine checks](v4-foundations.md) | [Source revisions and identity](data-revisions.md) |
| [Offline browser rendering](browser-rendering.md) | [Figure viewer in HTML](compiled-viewer.md) |
| [Plot rendering review](plotting-engine.md) | [Shared plotting quality](plot-quality.md) |
| [Research preview: regions and crossings](research-study.md) | [Research preview and availability](research-preview.md) |
| [Controlling label movement during revision](research-revision.md) | [Research preview and availability](research-preview.md) |
| [Proposed 4.0 engine plan](design/v4.md) | [Current roadmap and release gates](roadmap.md) |
| [Browser backend decision: scatter preview](design/browser-backends.md) | [Figure viewer in HTML](compiled-viewer.md) |
| [The page-grid combinator: measured, and declined](design/page_grid.md) | [Panel layout](layout.md) |
