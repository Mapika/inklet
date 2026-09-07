# Oblique microscopy sections

The 3.1 development preview can sample an arbitrarily oriented physical plane
through calibrated microscopy and segmentation arrays. The same `Plane` defines
the output pixels, scale bar, projected annotations and rectangle in a 3D scene.
This capability is experimental and is not included in stable 3.0 on PyPI.

From a development checkout:

```sh
python -m pip install -e '.[volume,render]'
```

## Define one physical sampling grid

```python
import numpy as np
import inklet as i
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane

z, y, x = np.indices((9, 11, 13))
raw = Volume((20*x + 7*y + z).astype('uint16'),
             spacing_zyx=(0.4, 0.2, 0.3), unit='um',
             origin_xyz=(10, 20, 30), source_id='example:intensity')
labels = Volume(np.where(x >= 5, 7, 0).astype('uint16'),
                raw.spacing_zyx, raw.unit, raw.origin_xyz, 'example:labels')
plane = Plane(centre_xyz=raw.world((4, 5, 6)),
              right_xyz=(1, 0, 1), up_xyz=(0, 1, 0),
              shape_yx=(9, 15), spacing_yx=(0.15, 0.15), unit='um')
image_section = raw.reslice(plane, kind='intensity')
label_section = labels.reslice(plane, kind='labels')
assert np.array_equal(image_section.valid, label_section.valid)
assert set(np.unique(label_section.data)) <= {0, 7}
```

`centre_xyz` is the centre of the entire output grid in world coordinates.
Right and up are normalized physical XYZ directions; they must be nonzero and
orthogonal. Inklet rejects a sheared basis. Plane and volume units must match
explicitly. The source origin and anisotropic spacing determine which source
voxels contribute; directions are not specified in voxel-index coordinates.

`shape_yx` gives rows and columns. `spacing_yx` gives physical row and column
spacing. Output row 0 is at the **top**, with rows proceeding opposite the up
direction. Column 0 is at the left. Integer pixel indices identify centres;
outer edges extend another half pixel. A plane has zero thickness: this is a
point-sampled section, not a slab average or maximum-intensity projection.

## Keep images, labels and annotations aligned

```python
picture = image_section.diagram(width=90, window=(0, 350))
key = plane.scalebar(0.5, width=90)
centre_on_page = plane.project(plane.centre_xyz, width=90)
assert (centre_on_page.x, centre_on_page.y) == (0, 0)
doc = i.document(width=105, margin=5)
doc.add('section', i.vstack([picture, key], gap=3))
figure = doc.compile()
```

Page widths are in millimetres; scale-bar lengths are in the plane's physical
unit. Scale image and key together if resizing later. `plane.world(row, column)`
returns a physical XYZ position. `plane.project()` returns image-centred page
millimetres with +y downward and rejects points off the plane or outside its
rectangle. It does not establish whether a source volume covers that point.

`plane.corners` returns four physical pixel-edge corners. Connect them with
`rendered.path3d()` to show the same rectangle over a saved-camera 3D render.
That path can use depth-tested solid and dashed segments. It marks the sampling
plane; it does not cut away geometry or insert a textured surface into Blender.

## Interpolation and source coverage

- `kind='intensity'` uses trilinear interpolation and returns floating-point
  values, including when the source image contains integers. It does not round
  interpolated intensities back to the source integer type.
- `kind='labels'` requires an integer or boolean volume and selects the nearest
  source voxel. Half-index ties choose the upper index. Direct integer indexing
  preserves large IDs, including `uint64` values beyond floating-point precision.
- Samples inside the outer voxel edges hold the nearest edge-centre value when
  necessary. Samples outside those physical edges are invalid. Their stored
  value is zero, but the separate boolean `section.valid` mask distinguishes
  missing coverage from a measured zero or background label.

The intensity sampler uses SciPy's
[`map_coordinates`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.map_coordinates.html)
with order 1 and no spline prefilter. Label sampling is separate so interpolation
cannot invent IDs. Nearest-neighbour resampling is also an established image
sampling operation in [ITK](https://docs.itk.org/projects/doxygen/en/stable/classitk_1_1NearestNeighborInterpolateImageFunction.html).

The section data and validity arrays are immutable snapshots. Its RGBA image
has transparent invalid pixels. Place it over a visible backing to distinguish
missing coverage in the figure. Reuse one intensity window across comparisons.
Resampling does not increase acquisition resolution, and this API does not apply
an anti-aliasing filter when choosing a coarser output grid.

## Measure the sampled section

```python
area = label_section.measure(7)
assert abs(area['area'] - area['sampled_pixels'] * 0.15 * 0.15) < 1e-12
assert area['area_unit'] == 'um^2'
```

Area is the number of **valid output pixel centres** assigned to the label,
multiplied by output pixel area. An absent label has zero sampled area. Label 0
can measure background, but invalid samples are always excluded. Results depend
on output spacing and plane position; they are not exact intersections of a
surface, volumetric measurements or independent biological replicates.

`section.report()` records source calibration, plane geometry, interpolation,
boundary handling and valid coverage. Save it with the figure. The
[real oblique-section example](oblique-biology.md) includes shared plane outlines,
matching microscopy and label panels, area comparisons and intensity profiles.
