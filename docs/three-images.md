# 3D and image panels

The built-in 3D renderer produces vector artwork from generated solids or
meshes. It does not require a network connection, GPU, Blender or the optional
`three` extra. Images and raster effects use the `images` extra.

For complete `.blend` files with authored materials, lights and cameras, see
[Blender scenes in v3](blender-scenes.md).

## Start with a solid

```python
import inklet as i

doc = i.document(width=100)
doc.add('part', i.component(i.solid, 'cube', width=45,
                            view='three-quarter', style='shaded'), min_height=55)
figure = doc.compile()
figure.save('part.svg', 'part.pdf')
assert not any(d.severity == 'error' for d in figure.diagnostics)
```

`width` and `height` control the drawing size on the page. `view=(azimuth,
elevation)` sets the camera angles. Styles include `lineart`, `shaded`, `solid`,
`toon` and `wireframe`; crease and hidden-line options control edge detail.

## Assemble multiple parts

```python
from inklet.three import build

parts = [
    ('base', build('box', size_x=2, size_y=2, size_z=.2),
     {'at': (0, 0, -.5), 'color': '#a9c4d4'}),
    ('sample', build('sphere', radius=.6, subdivisions=2),
     {'at': (0, 0, .5), 'color': '#198c83'}),
]
scene = i.component(i.scene, parts, width=55, view=(35, 25),
                    style='shaded', order='exact')
doc.replace('part', scene)
assert doc.compile().to_svg() != figure.to_svg()
```

Each part may have a local position, rotation, scale and colour. `order='exact'`
resolves depth across part faces and is useful when objects intersect or their
silhouettes overlap. More detailed geometry costs more to process.

## Load a mesh

For a mesh file, create `i.component(i.model, i.FileRef('sample.stl'), width=55,
style='shaded')`. This fragment requires your own file. `FileRef` makes file
content part of the component's dependency key.

The native parsers support OBJ, STL and PLY. Installing `three` adds formats
through Trimesh and optional winding repair. Consistent face winding matters
for visibility and shading. Use `repair=True` when appropriate and inspect
the result. Original mesh units and transforms must agree across scene parts.

You can construct `Mesh` objects directly for calculated surfaces; see
`surface()` in the [twenty-panel figure](../examples/stress20.py). For labels
attached to 3D positions, see `anchor3d`, dimensions and callouts in the
[3D showcase](../figures/showcase_part.py).

## Add an image

With your own image file, use
`i.component(i.asset, i.FileRef('micrograph.png'), width=45)`. The factory runs
under the document theme. Asset options support cutouts, silhouettes, line art
and colour harmonisation; optional processing tools have their own dependency
requirements. See `asset()` in [the API reference](api.md).

Image sidecars use the `.inklet.json` suffix and can retain anchors and
attribution. Keep the image and sidecar together. See [migration](migration.md)
for old sidecar names and cache environment variables.

## Print size and reproducibility

Effective image resolution depends on source pixels and final physical width:
`dpi = pixels / (width_mm / 25.4)`. A 600-pixel image at 50 mm is about 305 dpi.
Increasing preview DPI does not add detail to the source image.

Dense scatter and heatmap rasterization is controlled separately by plotting
methods. All other vector elements remain editable in SVG and scalable in PDF.
Check the final file size and visual result; detailed vector 3D can be large.

The [example gallery](examples.md) includes self-contained figures as well as
asset-backed examples. Asset-backed examples need the files named in their
source scripts; the entire gallery is not part of the installed wheel.
