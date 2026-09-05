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

Do not modify the internal tree of a compiled snapshot. Make edits to the
authoring objects and compile again.

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
