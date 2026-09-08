# Compiled-scene browser viewer

This unreleased increment adds `RenderScene.to_html()`: an offline viewer for
ordinary native figures, using the same compiled geometry, text, transforms,
clipping and paint order as SVG/PDF export.

![The compiled-scene viewer displaying a four-panel figure with a dense point cloud, bubble plot, marker comparison and cropped triangular markers](../gallery/compiled-scene-viewer.png)

[Open the interactive figure](assets/research-preview/compiled-scene-viewer.html) ·
[Complete Python recipe](../examples/compiled_scene_viewer.py) ·
[Figure caption](assets/research-preview/dense-scatter-caption.tex)

The example has 38,300 vector markers. Its 30,000 filled circles use the browser
buffer path; the other markers in this figure have outlines and use native SVG.
All inputs are simulated. Titles and controls belong to the viewer page;
the exported figure contains no added title or description.

## Filled marker shapes

![Five panels comparing filled circle, square, triangle, diamond and star markers](../gallery/compiled-marker-shapes.png)

[Open the five-panel figure](assets/research-preview/compiled-marker-shapes.html) ·
[Complete Python recipe](../examples/compiled_marker_shapes.py) ·
[Figure caption](assets/research-preview/compiled-marker-shapes-caption.tex)

This figure has 12,500 simulated observations. Every data layer can use WebGL2,
including concave stars. Each panel preserves per-point sizes, two overlapping
colours, transparency and clipping. The panel order is circle, square, triangle,
diamond and star; axes and panel letters stay native SVG.

## Export an existing compiled scene

```python
from pathlib import Path
import inklet as i

p = i.panel(80, 50, x=(0, 1), y=(0, 1))
p.scatter([((k * 0.61803398875) % 1, (k * 0.41421356237) % 1)
           for k in range(10_000)],
          size=0.5, color="#245b8a", fill_opacity=0.3, stroke="none")
p.axes(x="Coordinate x", y="Coordinate y")
f = i.figure(width=100)
f.add(p.build())
scene = i.compile_scene(f.build()[0])
Path("figure.html").write_text(scene.to_html(), encoding="utf-8")
```

A compiled document already supplies `compiled.scene`. The HTML contains its
runtime, marker buffers, outlined text and image resources; no server, CDN or
JavaScript package installation is required. Native SVG, PDF and PNG export
continue to use that same snapshot.

This viewer handles native compiled figures. The existing
[linked-plot viewer](linked-plots.md) supplies keyed-row filtering, selection
and data revision controls. Those interactions have not yet been migrated to
this compiled-scene viewer.

## Rendering modes and fallback

| Mode | Behaviour |
| --- | --- |
| `auto` (default) | Try WebGL2; use Canvas for unavailable contexts or recognized software renderers. |
| `webgl2` | Try WebGL2 even on software implementations; fall back if initialization or drawing fails. |
| `canvas` | Draw eligible filled markers with Canvas 2D. |
| `svg` | Draw every marker as native vector elements. |

The GPU path supports packed circles, squares, triangles, diamonds and stars
with literal colours, per-point sizes and fill opacity, without visible outlines.
It also accepts a single simple closed polygon with 3–16 vertices, preserving nonzero
and even-odd fill rules. Open markers, rounded rectangles, curved or compound
paths, self-intersections, larger polygons, outlines and unsupported paint remain SVG. Text, curves, maps, images,
hatching, diagram content and native 3D projections keep their existing SVG
representation. This does not introduce live 3D camera manipulation.

The viewer reports the actual backend per layer, fallback reasons, optional
browser-reported renderer identity, buffer uploads and WebGL draw submissions through
`inkletScene.report()`. Browser privacy settings can hide renderer identity;
context availability alone does not prove that a physical GPU is being used.

At most eight WebGL contexts are allocated per viewer. Additional eligible
layers use Canvas. Each backing surface is capped at four million pixels and
4,096 pixels per dimension, or the lower WebGL limit. The status reports when
zoom requires reduced display resolution. Context loss switches the affected
layer to Canvas; choosing a renderer again can retry initialization.

## Fidelity and resource ownership

A browser surface occupies the marker's original position in the SVG tree via
[`foreignObject`](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/foreignObject).
The native ancestors continue to apply clipping, rotation, scaling, group
opacity and compositing. This keeps foreground annotations above the data and
preserves the order of overlapping layers.

WebGL uses [instanced triangles](https://developer.mozilla.org/en-US/docs/Web/API/WebGL2RenderingContext/drawArraysInstanced)
with distance-based circle or polygon coverage and premultiplied-alpha blending.
Polygon coverage uses the original vertices and winding rule, including concave
shapes; it needs neither a texture atlas nor per-point triangulation. Canvas paints
markers separately in source order. Display antialiasing differs between these
backends. Device-pixel scaling follows the SVG screen transform.

Original records remain 64-bit in the browser, and repeated placements share a
serialized source buffer. Only GPU attributes use 32-bit floats. View changes
redraw existing buffers without uploading geometry again. `dispose()` removes
DOM surfaces, observers, callbacks and GPU resources owned by the viewer.

**Download vector SVG** rebuilds marker shapes from the original records, retains
source indices without JavaScript integer rounding, and preserves native text,
clips and paint. It does not embed the GPU or Canvas image. The exported
viewport follows the current pan/zoom; PDF export remains in Python.

## Validation and measurements

Automated Chrome checks exercise forced WebGL2, Canvas and SVG, device-pixel
ratios 1 and 2, unavailable contexts, context loss, disposal, repeated instances,
invalid viewports, marker order and vector export. GPU alpha coverage is checked
against independent Canvas painting. Complete WebGL2 and Canvas screenshots
also agree with SVG under rotated clipping and group opacity; these checks
guard against browser layout rounding displacing the surface.
Exported vectors are rasterized separately
and compared with native Python SVG, including rotated clipping and group alpha.

The complete example's browser-exported SVG differs from its native reference
by less than 0.0003 mean RGB units on a 0–255 scale at 1,122 × 845 pixels.
That measures vector reconstruction, not GPU display equivalence.

The original circle-only study used **ANGLE/SwiftShader**, a software WebGL renderer.
Forced WebGL2 has lower JavaScript submission cost in the recorded study but
slower completed frames than Canvas. This is why automatic mode avoids known
software WebGL renderers. These results do not establish hardware-GPU speed or
cross-browser fidelity.

[Raw browser study](assets/research-preview/compiled-viewer-study.json) ·
[Export comparison](assets/research-preview/compiled-viewer-export.json) ·
[Composited display comparison](assets/research-preview/compiled-viewer-display.json) ·
[Measurement script](../tools/benchmark_scene_viewer.js)

The study reports seven warm viewport changes, synchronous submission time,
time through two animation-frame callbacks, renderer identity and uploaded
bytes. It does not isolate GPU execution time. No marker buffers were uploaded
during the measured view changes. To reproduce:

```bash
python examples/compiled_scene_viewer.py --output out/compiled-scene-viewer
agent-browser open file://$PWD/out/compiled-scene-viewer/index.html
agent-browser eval --stdin < tools/benchmark_scene_viewer.js
```

## Hardware marker study

The five-panel example also runs on an **NVIDIA GeForce RTX 5090 Laptop GPU**,
reported by Chrome as ANGLE → D3D12 → OpenGL 4.6 under WSL. All five layers use
WebGL2 in automatic mode. The comparison uses 12,500 markers, a 1,392 × 750
pixel stage and device-pixel ratio 1. A composited hardware screenshot differs
from SVG mode by at most 1.15 mean RGB units on the 0–255 scale; dense marker
edges use different antialiasing. The downloadable SVG remains vector.

Seven warm viewport changes, measured after the test suite completed:

| Backend | Median synchronous submission | Median time through two frame callbacks | New uploads |
| --- | ---: | ---: | ---: |
| WebGL2 on RTX 5090 | 47.1 ms | 52.5 ms | 0 bytes |
| Canvas | 8.5 ms | 37.3 ms | 0 bytes |

The frame-callback measurement does not isolate GPU execution time.
This workload is **slower with WebGL2 than Canvas** on this machine. Hardware
availability is not a performance result. Five independent contexts, surface
compositing and driver synchronization are candidates for profiling; the study
does not isolate their individual costs. The next performance work should
measure shared-context rendering before expanding the number of GPU layers.

[Hardware samples and renderer report](assets/research-preview/compiled-markers-hardware.json) ·
[Hardware display comparison](assets/research-preview/compiled-markers-display.json)

The browser was launched with `--use-gl=angle --use-angle=gl
--ignore-gpu-blocklist`, and process-local `GALLIUM_DRIVER=d3d12` and
`MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`. These are test-environment settings,
not requirements for exported figures. WSL's OpenGL path is described in
[Microsoft's GPU selection guide](https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg)
and the [Mesa D3D12 documentation](https://docs.mesa3d.org/drivers/d3d12.html).

## Next work

Other-browser measurements, accelerated outlines, indexed picking, partial
buffer updates and migration of keyed-row interactions remain open. Packed maps and meshes are later consumers of the same scene;
this increment does not claim their GPU performance.
