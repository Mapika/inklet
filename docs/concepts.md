# The authoring model

Inklet separates a figure's editable definition from its compiled drawing.
Use the live document API for figures you expect to resize or revise. Use the
direct drawing API when you need explicit, fixed geometry.

| Object | Purpose | When it changes |
|---|---|---|
| `Dataset` | Named, equal-length data columns with optional units and source | `update()` validates and increments its revision |
| `PlotSpec` | Deferred plot instructions, data references and scales | Drawing methods append; `replace`, `remove`, `configure` revise |
| `ComponentSpec` | A factory and explicit arguments for a drawing | `configure()` revises arguments |
| `Composition` | Named children positioned using measured expressions | Edit children, constraints or connections |
| `Document` | Physical page, theme and named layout cells | Edit definitions, replace cells or configure the page |
| `CompiledFigure` | Resolved snapshot, diagnostics, metadata and exports | A new compilation creates a new snapshot |
| `Diagram` | A concrete drawing tree with geometry and anchors | Transform, style or copy it for direct composition |
| `Panel` / `Figure` | Direct plot construction / page assembly | Build explicitly; document placement keeps their authored size |

![A complete figure combining dense points, images, diagrams and measured layout](../gallery/engine-review.png)

The [engine review recipe](rendering-engine.md) compiles plots, images and fixed diagrams into one document.

## Choose an authoring workflow

Start with a live `Document` and `PlotSpec` when data, page dimensions or shared
styling will change. Wrap factories in `component()` so Inklet can measure
those drawings under the final theme. A `Composition` adds named objects and
relationships: keep a label beside a plot, attach a connector to a module, or
reuse the same arrangement with new inputs.

Use direct `Panel`, `Figure` and `Diagram` construction for precise authored
geometry or a self-contained drawing. They also fit inside live documents, but
a prebuilt drawing retains its authored size and measured text. Enlarging the
finished artwork scales its strokes and type; rebuilding a plot at a different
size preserves their physical sizes.

| Decision | Guide |
| --- | --- |
| Record live data and deferred plot marks | [First figure](quickstart.md), [live data](data.md) |
| Allocate page cells and nested panels | [Panel layout](layout.md) |
| Name reusable content and express measured relationships | [Reusable compositions](composition-recipes.md) |
| Place drawing primitives at explicit coordinates | [Direct drawing cookbook](cookbook.md) |
| Save reviewed layout choices or package a study | [Saved layout choices](layout-overrides.md), [figure projects](project-workflows.md) |

These approaches share drawing geometry and exports. Choose the one that makes
future edits explicit, and combine them where a figure needs both live plots
and fixed illustrations.

## Compilation

`doc.compile()` evaluates explicit dependencies, measures labels and plot
furniture, allocates cells, places drawings, routes connections and resolves
paint. SVG and PDF consume that same resolved result. Diagnostics inspect the
finished page, including final transforms.

An unchanged document returns its cached snapshot. When one dependency changes,
unaffected components can reuse geometry. Different widths and heights can
require additional builds while plot furniture settles. The
[stress test](stress20.md) shows why a cached page is much faster than rebuilding
a dense scatter plot.

Make edits to the authoring objects and compile again. A compiled snapshot
retains the drawing, fonts and data revisions from its compilation; exporting
it after a dataset update still exports the earlier figure.

`compiled.build()` returns the retained drawing and a read-only mapping of
resolved placements. The mapping is for inspection. Copying it does not create
an editable layout or update the drawing. Use the document's named cells,
composition constraints or [saved layout choices](layout-overrides.md) to revise
placement. Do not mutate the retained drawing tree.

## Explicit dependencies

Ordinary lists and dictionaries are snapshotted when recorded. Mutating the
original list does not update a recipe. Use a `Dataset` reference, another live
spec or a `FileRef` for inputs that should invalidate caches.

Factories must be deterministic for their arguments. Changes hidden in a
closure or module-global variable are not tracked. Pass those values explicitly
through `component()` or through `derive()` dependencies.

## Physical units

Numeric lengths are millimetres, including `text(size=...)`, line widths, gaps,
component dimensions and the default composition coordinate system. Many
dimension arguments also accept strings such as `'89mm'` or `'2in'`; use
`i.pt()` to convert point sizes explicitly.

```python
import inklet as i

label = i.text('Measured type', size=i.pt(8))
assert abs(i.pt(8) - 8 * 25.4 / 72) < 1e-9
```

Publication profile fields ending in `_pt` take points: `font_pt=8` is already
8-point type. Plot x/y values use data coordinates and are mapped by scales.
Ordinary drawing coordinates have positive y downward; a normal Cartesian
plot maps increasing y upward.

## Themes and publication profiles

A theme supplies fonts, colours, spacing and stroke defaults. A publication
profile combines a theme with a physical page width, export settings and print
thresholds. Its name is a general preset, not a journal's current specification.

```python
from dataclasses import replace

profile = i.publication('double-column', width=180, font_pt=8, dpi=300)
doc = profile.document(theme=replace(profile.theme, palette=('#176b9b', '#198c83')))
doc.add('label', i.component(i.text, 'Theme applied during compilation'))
assert doc.compile().metadata['publication']['width'] == 180
```

Deferred factories run under the document's theme. A diagram made before it is
added has already measured its text; use `component()` when theme-dependent
measurement should happen at compile time. Nested subfigures inherit the parent
theme.

## Geometry and reuse

A `Diagram` has an envelope for spacing, a trace for boundary intersections,
and named anchors for connections. Combinators preserve child handles by
wrapping drawings in a parent. A direct drawing tree cannot place the same
diagram identity twice; use `.copy()`. Document cells automatically copy their
built content before placement.

Read the [cookbook](cookbook.md) for direct drawing recipes or the
[compilation contract](design/v2.md) for implementation details.

## Identity and saved decisions

Give revisable content stable names: dataset columns identify values,
composition paths identify placed objects, and explicit plot instruction keys
identify editable marks and labels. Keep those names attached to the same
meaning when replacing inputs. A displayed caption or a row's current position
is not a durable identity.

A [figure project](project-workflows.md) (`inklet.project`) connects local row,
drawing and image/mesh IDs through explicit entity mappings. Its asset manifest
records the files and provenance needed to reconstruct a study. Saved choices
supplement your Python recipe; they do not serialize arbitrary Python code.

Use [interactive documents](interactive-documents.md) to distinguish offline
view state, linked plot style overrides and the local composition editor's
layout choices. Those saved files serve different workflows and are not
interchangeable.
