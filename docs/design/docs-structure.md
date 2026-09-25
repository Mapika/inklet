# Documentation structure

This note records the September 2026 audit of `docs/` and the navigation that
replaced the earlier sidebar. The earlier navigation listed about 110 pages in
eleven top-level groups. Engine studies, release gates, research previews and
worked examples were listed next to the user guides, while the dense figure
page, measured layout and the newer plot types had no entry of their own.

## Principles

- The sidebar holds pages that a figure author reads to do something. Engine
  measurements, release process, design notes and before/after reviews move to
  a single [development notes](../development.md) index.
- Every top-level section except *Get started* and *Reference* opens with an
  overview page of image cards. *Plots* uses the plot-type gallery for this, and
  *Gallery* uses the figure gallery.
- No Markdown file is renamed or deleted, because Read the Docs URLs and
  external links depend on them. Pages that leave the sidebar stay built and
  searchable. `extra.unlisted` in `mkdocs.yml` assigns each of them to the
  section that the sidebar opens and that search reports.
- Worked examples of an experimental API stay together under *Experimental*.
  Its overview links to every one of them.

## New navigation

| Section | Pages in sidebar | Overview page | Pages reached from the overview only |
| --- | ---: | --- | ---: |
| Overview | 1 | `index.md` (home template) | 0 |
| Get started | 4 | none, the pages form one sequence | 0 |
| Plots | 13 | `plot-types.md` (plot gallery) | 0 |
| Figures and layout | 7 | `figures.md` (new) | 0 |
| Diagrams | 3 | `diagrams-overview.md` (new) | 1 |
| 3D and images | 7 | `three-d.md` (new) | 2 |
| Export and review | 3 | `export.md` (new) | 0 |
| Gallery | 5 | `examples.md` (figure gallery) | 11 |
| Reference | 6 | none, the pages are self-describing | 0 |
| Experimental | 11 | `experimental.md` (new) | 21 |
| Development | 3 | `development.md` (new) | 17 |

The nine user-facing sections list 49 pages. *Experimental* and *Development*
sit below a separate sidebar label and add 14 more.

## Audit

Columns: lines of Markdown, the number of other pages that link to the file
(inbound), the category, and what happens to the page.

Categories: **guide** (core user guide), **how-to** (task recipe or tutorial),
**ref** (reference), **show** (showcase or gallery), **exp** (experimental or
preview API), **int** (internal: history, engine study, design, release
process, research study, before/after review).

### Get started

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| index.md | 44 | 0 | guide | Keep as home. Rewritten task table; home template now features the dense figure, the new plot types and measured layout. |
| installation.md | 154 | 17 | guide | Keep in *Get started*. |
| quickstart.md | 128 | 7 | how-to | Keep in *Get started*. |
| csv-figure.md | 125 | 5 | how-to | Keep in *Get started*. |
| concepts.md | 147 | 6 | guide | Keep in *Get started*. |

### Plots

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| plot-types.md | 28 | 10 | show | Keep as the *Plots* overview. The gallery is now grouped by family with a heading, guide link and summary per family. |
| plotting.md | 142 | 3 | guide | Keep. |
| lines-and-points.md | 257 | 1 | guide | Keep; renamed in nav only. Body untouched (concurrent edits). |
| bars-and-areas.md | 240 | 1 | guide | Keep. Body untouched (concurrent edits). |
| distributions.md | 245 | 1 | guide | Keep. Body untouched (concurrent edits). |
| uncertainty.md | 129 | 1 | guide | Keep. |
| matrices.md | 254 | 3 | guide | Keep; nav label now mentions dendrograms. Body untouched. |
| polar-plots.md | 164 | 1 | guide | Keep; nav label now mentions radar and pie. Body untouched. |
| axes-and-scales.md | 88 | 11 | guide | Keep. |
| data.md | 172 | 13 | guide | Keep. |
| dense-data.md | 74 | 7 | guide | Keep. |
| plot-recipes.md | 147 | 6 | how-to | Keep. |
| publication-plots.md | 103 | 4 | how-to | Keep; nav label "Insets and shared categories" says what it covers. |

### Figures and layout

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| figures.md | new | – | guide | New section overview with cards. |
| dense-figures.md | new | – | show | New page for `examples/dense_figure.py`: panel-by-panel list of the calls, the grid, the preset and the lint result. Previously the figure was only an image at the end of `presets.md#dense-pages`. |
| layout.md | 137 | 17 | guide | Keep, nav label "Panel layout in millimetres". Body untouched (concurrent edits). |
| presets.md | 233 | 1 | guide | Moved here from the old *Whole figures* list; linked from Reference overview text. |
| composition-recipes.md | 171 | 10 | how-to | Keep. |
| complex-figures.md | 117 | 3 | how-to | Keep. |
| scientific-authoring.md | 361 | 3 | how-to | Keep. |
| project-workflows.md | 189 | 11 | exp | Move to *Experimental*; the home page already tagged it experimental. |
| layout-overrides.md | 193 | 6 | exp | Move to *Experimental* (opt-in API). |
| layout-editor.md | 340 | 7 | exp | Move to *Experimental* (opt-in API). |

### Diagrams

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| diagrams-overview.md | new | – | guide | New overview, including where diagrams and plots share a page. |
| diagrams.md | 103 | 5 | guide | Keep. |
| diagram-components.md | 29 | 1 | ref | Keep. |
| diagram-engine.md | 135 | 1 | int | Out of sidebar: a before/after engine review. Still the target of the gallery card; linked from the Diagrams overview and development notes. |

### 3D and images

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| three-d.md | new | – | guide | New overview with cards. |
| three-images.md | 96 | 5 | guide | Keep. |
| blender-scenes.md | 302 | 11 | guide | Keep. |
| scene-annotations.md | 140 | 5 | guide | Keep. |
| scene-paths.md | 125 | 6 | guide | Keep. |
| scene-templates.md | 123 | 4 | guide | Keep. |
| render-jobs.md | 138 | 10 | guide | Keep. |
| scientific-scenes.md | 95 | 3 | how-to | Out of sidebar, card on the 3D overview and in the figure gallery. |
| open-anatomy.md | 130 | 3 | how-to | Out of sidebar, card on the 3D overview. |
| complex-scene.md | 59 | 4 | show | Out of sidebar, in the figure gallery; section *Gallery*. |

### Export and review

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| export.md | new | – | guide | New overview: vector export, diagnostics and lint, review bundles, revision comparison, viewer. |
| export-review.md | 154 | 9 | guide | Moved out of *Whole figures* into its own section. |
| compiled-viewer.md | 303 | 11 | guide | Moved from *Interactive documents*: it is a stable viewer for compiled figures. |

### Gallery

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| examples.md | 18 | 14 | show | Keep as the *Gallery* overview. |
| scientific-gallery.md | 106 | 3 | show | Keep. |
| showcase.md | 62 | 11 | show | Keep; now lists its eight recipe pages. |
| stress20.md | 77 | 7 | show | Keep. |
| example-library.md | 123 | 1 | show | Keep. |
| general-plots.md | 82 | 3 | show | Out of sidebar; figure gallery card. |
| biology-panels.md | 72 | 2 | show | Out of sidebar (was under Microscopy, but it is a plot figure); figure gallery card. |
| recipes/*.md (8) | 26–28 | 0–1 | show | Out of sidebar; figure gallery cards and the list in `showcase.md`. |

### Reference

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| api.md | 1377 | 11 | ref | Keep (generated). |
| cli.md | 99 | 4 | ref | Keep. |
| cookbook.md | 2860 | 2 | ref | Moved from *Examples*: a lookup of direct-drawing recipes. |
| compatibility.md | 152 | 11 | ref | Keep. |
| migration.md | 287 | 6 | ref | Keep. |
| troubleshooting.md | 95 | 4 | ref | Keep. |

### Experimental

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| experimental.md | new | – | exp | New overview linking every experimental guide and worked example. |
| interactive-documents.md | 83 | 3 | exp | Keep in sidebar. |
| linked-plots.md | 121 | 7 | exp | Keep in sidebar. |
| linked-facets.md | 135 | 4 | exp | Keep in sidebar. Body untouched (concurrent edits). |
| linked-maps.md | 172 | 6 | exp | Keep in sidebar. |
| data-revisions.md | 221 | 9 | exp | Keep in sidebar. |
| project-workflows.md, layout-overrides.md, layout-editor.md | | | exp | See *Figures and layout*. |
| calibrated-volumes.md | 111 | 6 | exp | Keep in sidebar as the microscopy entry point. |
| research-preview.md | 236 | 5 | exp | Keep in sidebar. |
| table-inputs.md | 143 | 6 | exp | Out of sidebar; overview card. |
| time-series.md | 162 | 5 | exp | Out of sidebar; overview card. |
| statistical-views.md | 131 | 3 | exp | Out of sidebar; overview card. |
| geographic-features.md | 116 | 2 | exp | Out of sidebar; overview card. |
| visual-editing.md | 107 | 4 | exp | Out of sidebar; overview card. |
| regional-report.md, world-map.md, engineering-report.md, scientific-report.md, mesh-fields.md, contours-streamlines.md | 95–186 | 1–5 | exp | Out of sidebar; overview cards under "Complete reports". |
| oblique-sections.md, slabs-and-regions.md, channels-and-contours.md, label-measurements.md, microscopy-tiff.md | 76–134 | 1–3 | exp | Out of sidebar; overview cards under "Microscopy". |
| real-biology.md, oblique-biology.md, slab-biology.md, fluorescence-biology.md, label-intensities.md | 77–115 | 2–7 | exp | Out of sidebar; overview cards under "Microscopy examples". |

### Development (internal)

| Page | Lines | In | Class | Action |
| --- | ---: | ---: | --- | --- |
| development.md | new | – | int | New index of internal material; absorbs the table from `history.md`. |
| history.md | 36 | 3 | int | Retired into `development.md`; kept with a pointer note, out of sidebar. |
| development-preview.md | 59 | 22 | int | Out of sidebar: 4.0 release notes at a historical URL. |
| roadmap.md | 82 | 11 | int | Out of sidebar. |
| acceptance.md | 108 | 4 | int | Out of sidebar; still indexed by search. |
| release-checks.md | 155 | 4 | int | Out of sidebar. |
| brand.md | 27 | 0 | int | Out of sidebar; linked from the footer. |
| rendering-engine.md | 223 | 5 | int | Out of sidebar (engine study). |
| plot-quality.md | 52 | 2 | int | Out of sidebar (before/after review). |
| compositing.md, hatching.md, clipping.md | 109–117 | 3 | int | Out of sidebar (engine studies). |
| compiled-scenes.md | 155 | 2 | int | Out of sidebar (development revision record). |
| marker-batches.md, marker-culling.md | 134–176 | 1–4 | int | Out of sidebar (engine studies). |
| design/v2.md | 84 | 5 | int | Out of sidebar (design contract). |
| design/capability-gaps.md | 143 | 0 | int | Out of sidebar (design note). Body untouched (concurrent edits). |
| design/docs-structure.md | new | – | int | This page. |
| v2.md, v2.5.md, v3.md, v4-foundations.md, browser-rendering.md, plotting-engine.md, research-study.md, research-revision.md, design/v4.md, design/browser-backends.md, design/page_grid.md | 105–237 | 1–5 | int | Already archived and out of sidebar; unchanged, excluded from search. |

## Overlaps

| Pages | Overlap | Resolution |
| --- | --- | --- |
| `history.md`, new `development.md` | Both index internal material. | `development.md` holds the full list, `history.md` points to it. |
| `presets.md#dense-pages`, new `dense-figures.md` | Both describe the dense page. | `presets.md` keeps the settings table; `dense-figures.md` explains the figure and links back. |
| `examples.md`, `showcase.md`, `scientific-gallery.md`, `example-library.md` | Four gallery-like pages. | `examples.md` is the one gallery; the others are detail pages below it. |
| `diagram-engine.md`, `diagrams.md` | Both show measured modules and routing. | `diagrams.md` is the guide; the review leaves the sidebar. |
| `compiled-scenes.md`, `compiled-viewer.md` | Same feature; one is its dev record. | Viewer in *Export and review*; record in development notes. |
| `dense-data.md`, `marker-batches.md`, `marker-culling.md`, `rendering-engine.md` | Guide versus measurements. | Guide stays; measurements in development notes. |
| `interactive-documents.md`, `experimental.md` | Both route to experimental pages. | `interactive-documents.md` chooses between viewer, editor and report workflows; `experimental.md` lists every experimental page. |
| `*-biology.md` versus microscopy guides | Example versus API guide pairs. | Kept separate, grouped on the Experimental overview. |
