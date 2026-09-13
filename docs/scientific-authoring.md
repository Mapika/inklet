# Complex scientific illustrations

Use measured labels and authored arrows for explanatory diagrams, and fit one
camera for every anatomical layer that must stay registered. Meshes, paths and
markers then compose as ordinary Inklet diagrams.

## Labels that fit the text

```python
import inklet as i

label = i.tag("CB intrinsic", size="8pt", font="Arimo",
              fill="#86a9c6", color="white",
              pad=("1mm", "0.4mm"), radius="0.4mm")
```

`tag` shapes the text first and sizes its background from the measured extent.
`pad` is horizontal/vertical padding, or one value for both. Neither a long
label nor a different font stretches the glyphs. Multiline text and markup
work, and a pre-styled Diagram can replace the string. Use `align_to(label,
"nw")` to place the top-left corner explicitly; use stacks and grids when
labels should determine the layout.

Existing `box(text(...))` and `frame(...)` remain useful for more general
containers. `tag` supplies compact defaults and scopes the background color
separately from the text. Omit `color` to choose dark or light text by contrast.

## Smooth pathways and arrows

```python
pathway = i.arrow([(0, 20), (3, 10), (12, 6), (19, 8)],
                  smooth=0.55, color="#66a486",
                  stroke_width="0.5mm", head_length="2mm")
```

The shaft is an actual cubic spline. Arrowheads follow its endpoint tangents;
the shaft stops beneath each filled head. Short arrows shrink the head instead
of drawing a triangle longer than the pathway. `smooth=0` gives a polyline,
`both=True` adds a start head, and `head="open"` gives an open arrowhead.

A single open `path` or `curve` Diagram can be passed instead of waypoints.
Its controls and placement are preserved, including a transformed path. Use
`i.as_drawn(pathway)` to restore authored coordinates; the default result is
centered for layout, like `curve`. `start` and `end` anchors refer to the tips.
Use `link` when arrows should route around obstacles or attach to node outlines.

## One camera for surfaces, paths and points

```python
from inklet.three import Camera, Mesh

# vertices and triangles are source arrays; neuron_runs and synapses are XYZ.
mesh = Mesh.from_arrays(vertices, triangles, name="neuropil")
view = Camera.named("three-quarter").frame(mesh, width=45, height=35)

surface = i.model(mesh, view=view, style="solid", shading="smooth",
                  color="#c5c2bc", opacity=0.45)
neurons = view.paths(neuron_runs, color="#668fb8", stroke_width=0.15,
                     depth_cue=0.35)
sites = view.markers(synapses, color="#e4b83e", radius=0.18,
                     depth_cue=0.15)
combined = i.drawn([surface, neurons, sites])
```

A fitted `View` supplies the same scale, origin, orientation and projection to
all three layers. Do not supply `width` or `height` again to `model(view=view)`;
that would imply a second fit. Point radii and path widths are page lengths,
independent of source coordinate units. `Mesh.from_arrays` copies the source
arrays into immutable geometry and accepts NumPy without requiring it for
basic model drawing.

`View.paths` and `View.markers` are also available as `paths3d(view, ...)` and
`points3d(view, ...)` from `inklet.three`. Markers support circle, square and
diamond shapes. Depth cue fades farther items toward `paper`, within the
supplied collection, and batches marks into depth bands for efficient export.

These are **X-ray overlays**: they do not hide neurons behind a neuropil's
surface. The sampled depths order paths/markers within one call, not across
separate layers. Draw translucent tissue first when internal anatomy should
remain visible. For surface-occluded overlays, use the rendered-scene depth
workflow described in [Vector paths in scenes](scene-paths.md).

Fitted `View` rendering currently uses the builtin backend. Width fitting is
preserved for existing `Camera`/preset calls, and regular `model` exports remain
vectors. Overlays reject points behind the near plane; they do not silently
project those points into the frame.

## Detailed source meshes at practical display sizes

```python
# Install inklet[three] for optional quadric-error simplification.
display_mesh = mesh.simplified(6000)
surface = i.model(display_mesh, view=view, style="solid",
                  shading="smooth", color="#c5c2bc", opacity=0.45)
```

Fit the camera to the original mesh, then draw the reduced copy in that view.
This retains registration with original neuron and synapse coordinates.
`target_faces` is a target, not a hard limit. Simplification can change local
shape and topology; use the original mesh for measurements. Different named
parts must be simplified separately so their group boundaries are not lost.
Meshes already below the target do not load the optional simplifier.

## Panel review

For isolated letters or values inside circles and cells, use
`i.text("d", size=3, bounds="ink")`. Its visible glyph bounds are centered at
the origin, so translating it to a node center aligns the drawn letters rather
than the font's full ascent/descent box. The SVG/PDF still contains editable
text. The default `bounds="font"` retains baseline-friendly spacing for prose
and table columns. Leading/trailing whitespace has no ink extent; an entirely
blank label falls back to font bounds. Text link traces still use font metrics.

Keep legend swatches and labels in one measured `legend`/`vstack` composition,
then position that composition in a clear region. When putting a legend inside
a white box, set `text_fill` explicitly so labels do not inherit its fill.

Check each panel at its final output size, not only zoomed in:

- Are labels measured at the actual font size, and are arrows tangent to curves?
- Do overview anatomy, enlarged regions, and locator boxes use consistent coordinates?
- Are lines, point clouds and surfaces distinguishable without heavy outlines?
- Do legend marks use the same colors, shapes and sizes as the plotted marks?
- Do percentage labels, counts and width keys describe the arrays actually drawn?
- Are reconstructed values or unavailable analyses clearly identified?

The working connectome example lives in `examples/inspo/`. Its generated
`out/inspo-native/panel-review.md` records the review of all 30 panels, including
remaining source-data limitations. No reference screenshots are used by the
figure builder.

## Connect shapes that are already placed

`connect` exposes Inklet's existing boundary-aware router without requiring a
Figure or a placement dictionary. The result contains only the edge, in the
same coordinates as the nodes. Draw it underneath them:

```python
left = i.tag("source", size=3, fill="#ddd").translated(10, 10)
right = i.tag("target", size=3, fill="#eee").translated(45, 15)
edge = i.connect(left, right, offset=4, standoff=.5,
                 arrow_size=2, stroke="#555", stroke_width=.3)
art = i.Diagram(children=(edge, left, right))
```

The head stops at the actual node boundary. Opposing edges with the same
positive `offset` bow to opposite sides. Use `within=scene` when endpoints
inherit transforms from a containing scene. Recompute after moving the nodes;
use `Figure.link` when placement has not yet been decided. This convenience
function does not promise to avoid unrelated nodes; use the existing scene
routing/obstacle facilities for that.

## A column of labels with retained data anchors

`label_column` measures the supplied Diagrams and distributes them inside a
vertical interval. It preserves point order, gives every label a leader, and
raises if the interval cannot fit the labels at their requested size.

```python
labels = [i.tag(str(k), size=3, pad=.4, fill="white")
          for k in (102, 103, 116)]
column = i.label_column(labels, [(10, 12), (11, 12.5), (12, 20)],
                        x=25, bounds=(5, 35), gap=1)
```

The bounded isotonic fit minimizes squared vertical displacement subject to
measured heights and clearances. It handles label collisions inside its own
column; other content must be kept outside that column. Both this API and
`connect` return absolute drawing coordinates. Their labels remain editable.
`notes['label_column']` records original targets and final label boxes in
input order for validation.

## Share transforms with selection boxes

`Panel.region(x0, y0, x1, y1)` maps a data rectangle through the same scales as
`Panel.point` and returns a normalized `Rect`. This removes separate arithmetic
for bar endpoints, matrix selections, and zoom indicators:

```python
matrix_frame = i.panel(60, 45, x=(0, 311), y=(311, 0))
selection = matrix_frame.region(70, 70, 120, 120)
```

The matrix slice `[70:120, 70:120]` uses these cell edges. Use `cid + .5` for a
cell-center label. The rectangle is in panel coordinates, so apply the same
placement as the panel. Reversed and logarithmic scales are supported; regions
are not silently clipped. For a complete inset with axes and connectors, use
the existing `inset` API.

## Build an entire scientific plate

Use `panel_mosaic` for named, spanning panels. Supply factories that accept a
physical drawing width and height; Inklet rebuilds their drawing regions to
allow for axes and legends. It preserves font sizes and stroke widths.

```python
import inklet as i


def response(width, height):
    return (i.panel(width, height)
            .line([(0, 0), (.3, .7), (1, 1)], name="response")
            .axes(x="input", y="output")
            .legend(corner="auto", font_size=2.5))

figure = i.panel_mosaic(
    ["A A B", "C D B"],
    {"A": response, "B": response,
     "C": i.value_table([[12, 18], [21, None]], headers=["left", "right"]),
     "D": i.tag("measured annotation")},
    width=180, height=110, gap=4,
    titles={"A": "Response", "B": "Comparison"},
)
i.save_svg(figure, "figure.svg", text="embed")
```

Repeated names must form rectangles. `.` reserves an empty cell. Optional
`row_weights` and `column_weights` distribute space. Panel letters and titles
have a reserved band; they cannot overlap the plots. A static component that
cannot fit raises an error rather than shrinking its text. Factories should be
pure: fitting can call them up to twelve times. The result includes panel boxes
and build counts in `notes['panel_mosaic']` and applies the active figure theme.
Layout fitting uses measured envelopes; exceptionally thick paint can extend
beyond them. For live bindings and later layout edits, use
[Composition](composition-recipes.md).

## Author anatomy without manual camera arithmetic

`anatomy_view` owns a fitted camera and a physical viewport. Add named layers
in common source coordinates, then make close-ups from the same camera:

```python
# brain_mesh, left_lobe_mesh and arbors are your registered source geometry.
overview = i.anatomy_view(brain_mesh, width=70, height=50, camera="front")
overview.surface("brain", brain_mesh, color="#cbd3d5", opacity=.4)
overview.paths("arbors", arbors, color="#087f8c", stroke_width=.2)

# A complete detail with a correctly registered locator and connectors.
figure = overview.inset(left_lobe_mesh, width=25, height=25, side="bottom")

# Or build the detail separately and use the exact locator rectangle.
detail = overview.zoom(left_lobe_mesh, width=25, height=25, layers=["arbors"])
detail.style("arbors", stroke_width=.3)
locator = overview.window(detail)
```

Meshes, paths and markers must already share coordinates. An oriented `View`
can replace the camera preset. `window` accounts for the detail's full aspect
ratio and padding. Layer colors and stroke widths stay independent of zoom.
The native surfaces use vector shading; paths remain X-ray overlays, and
separate meshes are painted in layer order. This builder does not infer
registration, segment anatomy, or provide mutual surface occlusion.

## Tables, legends and nested networks

`value_table` measures each column from its widest value and header. It centers
visible glyphs in each cell while retaining editable text; `None` displays an
em dash. Set `font_size`, `pad`, `min_cell_width`, `min_cell_height`, `fill`, and
`header_fill` to match the page. Anchors such as `cell-0-1` and `header-1` allow
connections to attach to the measured cells.

`Panel.legend(corner="auto")` searches existing plot geometry for a clear
position. It tests corners and a deterministic grid, then raises if none fit.
It never makes a key smaller or silently covers a curve. External legends
remain available through `side="bottom"` and other sides. The general
`place_in_clear_space(item, within=Rect(...), avoid=[...])` also handles callouts:
it includes the item's painted bounds and resolves transformed obstacles.
This is a conservative geometry test, not image segmentation or a proof that
no position anywhere is possible.

Use `Graph.build()` when a network belongs inside a mosaic or another static
component. It includes routed connections as well as nodes:

```python
network = i.graph(
    {"input": i.tag("input"), "output": i.tag("output")},
    [("input", "output")], direction="right",
).build()
```

The existing `.diagram` property contains the laid-out nodes. `add_to(figure)`
is still appropriate when routing must wait until a Figure has placed them.

See the [original scientific gallery](scientific-gallery.md) for complete,
reproducible figures made with these components and real released fly anatomy.

## Coordinating a dense page in dev14

`PanelSpec` adds minimum outer sizes and an optional drawing-area aspect ratio
for panel factories. Automatic row/column weights also measure static content
and actual headers. Factories rebuild around axes and captions; font sizes stay
fixed. Impossible size requests raise an error.

```python
page = i.panel_mosaic(
    ['A B', 'C B'],
    {'A': anatomy_factory, 'B': i.PanelSpec(matrix_factory, aspect=1,
                                          min_width=65),
     'C': network_factory},
    width=190, height=130, column_weights='auto',
)
```

Register movable content after laying out the page. `FigureAnnotation` accepts
a label, legend or inset; `within` bounds its complete footprint, `target` adds
a leader, and `at` pins its center. `positions` supplies explicit candidates.
`place_annotations` chooses placements together and records them in
`notes['annotations']`. Targets can be original Diagram handles or anchors.

```python
page = i.place_annotations(page, {
    'source': i.FigureAnnotation(i.tag('source'), target=source_node,
                                within=i.Rect(0, 110, 100, 130)),
    'key': i.FigureAnnotation(legend, at=(155, 120)),
})
```

Only registered annotations move. Existing content stays fixed. Filled obstacles
use conservative bounds; use `avoid=[data_marks]` to exclude enclosing backgrounds.
The deterministic beam search reports failure rather than covering data, but
failure is not proof that no continuous placement exists. Increase `beam`, supply
candidate positions or enlarge the regions when appropriate.

## Sections, visibility and lighting

Call `anatomy.lighting(direction=..., levels=16, smooth=80)` after adding surfaces
to give them a shared smooth-lighting treatment. `anatomy.cut((1, 0, 0), offset=0)`
returns an independent view retaining points with `x >= 0`. Meshes, arbors and
markers use the same source-coordinate plane and unchanged camera. Cuts remain
open; no interior tissue or cap geometry is invented.

`build(depth='occluded')` jointly sorts filled opaque surfaces and removes covered
path portions and markers. Surfaces must share styles except `color`; use
`cull=False`, no per-face `colors`, and `solid`, `shaded` or `toon`. The default
`depth='layers'` retains explicit layer order and X-ray overlays, including
translucent surfaces. Choose the mode according to the figure's scientific claim.

## Dense vectors, networks and review

`panel.matrix(values, ramp=..., vector='batched')` groups cells with exactly equal
rendered colors into bounded compound paths. It preserves cell geometry, missing
values and colorbar validation without raster images or extra color quantization.
Individual cells no longer have separate nodes. Batching requires zero overlap;
some antialiased viewers may show joins between cells.

`graph.build(min_arrow_size=1.1, min_stroke_width=.15)` applies physical millimeter
floors without mutating the graph's authored edge styles. If stroke width encodes
a measurement, describe the floor in the legend; the displayed encoding changes.

`i.review_figure(page).save('out/review')` exports an editable SVG with numbered
findings and a matching JSON report. It runs Inklet's existing diagnostic rules;
it does not assess scientific validity. `max_highlights` limits visual clutter
while the JSON retains all findings. These are review artifacts, not a new editor.

Run `python examples/scientific_layout.py` for a complete small fixture combining
these APIs, native SVG/PDF/PNG exports and placement/review reports. The anatomical
shapes in this API fixture are synthetic spheres. The
[scientific gallery](scientific-gallery.md) uses released fly-connectome data,
including a 311 × 311 matrix rendered with batched vector paths.
