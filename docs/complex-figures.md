# Complex scientific plates

The three-paper reproduction audit exercised 43 axes, thousands of prediction
trajectories and 240,000 response-map samples. Its authoring improvements are
included in the 4.0.0.dev15 development snapshot.

## Dense fields: choose the representation

```python
import inklet as i

values = [[0.1, 0.4, 0.8], [0.2, 0.6, 1.0]]
colors = i.ramp(['#f5f5dc', '#4b94df', '#f28ca7', '#ffd700'])
heat = i.linear((0, 1))
p = i.panel(60, 40)
p.matrix(values, ramp=colors, scale=heat, vector='seamless')
p.colorbar(ticks=[0, .5, 1])
```

| Mode | Representation | Tradeoff |
| --- | --- | --- |
| `raster=False` | Individual vector rectangles | Each cell is selectable; large trees and exports |
| `vector='batched'` | Exact-color compound paths | Compact and editable; viewers can show cell joins |
| `vector='seamless'` | Exact cells above opaque vector underpaint | Suppresses background-colored joins; extra paint and larger PDFs |
| `raster=True` | One pixel per sample | Smallest export; cells cannot be edited as vectors |
| `raster=True, interpolation='linear'` | Bilinearly interpolated scalar field, then color-mapped | Smooth continuous appearance; explicitly introduces intermediate display values |

Seamless mode keeps foreground cell boundaries and the outer extent unchanged.
Colors are not quantized. The underpaint only covers antialiasing cracks; it is
not interpolation. Every compound path contains at most 512 cells. The field
must use opaque colors with zero overlap. Whole-field transparency can be applied
to a containing group. At extreme zoom the discrete source cells remain visible.

For the six 200 × 200 paper maps, seamless output was approximately 13 MB and
16 seconds, compared with 47 MB and 28 seconds for the earlier overlapping-cell
workaround. PDF size increased from about 1.1 MB to 5.2 MB. These are local
measurements of complete figure generation, not universal performance budgets.

Linear interpolation requires explicit `raster=True`, uniform spacing in the
displayed coordinate system, and `samples=2` through `16` (default `4`). It
interpolates values before applying even a nonlinear color scale. Missing samples
remain missing throughout the interpolation footprint; values beyond the outer
sample centers use constant extension. It does not modify the input array.

## Place data rectangles precisely

```python
p = i.panel(60, 40).axes(x='time / s', y='response')
p.line([(0, 0), (1, 1)])
placed = p.placed('15mm', '20mm')
area = i.plot_area(placed)  # (15, 20) to (75, 60), up to floating-point rounding
```

`Panel.placed(x, y)` uses the data rectangle's top-left, independently of axis
labels or legends. Furniture is not scaled. For new grids, the existing `facets`
API owns the shared axes and avoids hand-positioning altogether:

```python
panels = [i.panel(35, 25).line([(0, n / 4), (1, 1)]) for n in range(4)]
grid = i.facets(panels, cols=2, share_x=True, share_y=True,
                x_label='time / s', y_label='response', gap=5, row_gap=8)
```

Supply panels without pre-existing axes when asking `facets` to create them.
Use `axes=False` when each panel already owns its furniture.

## Keys and labels that follow the plot

```python
p = i.panel(60, 40, x=i.log((1, 100)), y=i.log((1, 100)))
p.guide((1, 1), (100, 100), label='k_{S} = k_{T}', at=.3, offset=2,
        label_style={'size': 3, 'font_style': 'italic'},
        stroke='black', stroke_dash=(1, 1))
p.matrix(values, ramp=colors, scale=heat, vector='seamless')
p.colorbar(corner='sw', length=12, thickness=1.5, pad=2, plate=True,
           title='Response', ticks=[0, 1], tick_font_size=2)

key = i.legend([('A', 'red'), ('B', 'blue'), ('C', 'green'), ('D', 'black')],
               columns=2, order='column', col_gap=6, row_gap=2)
```

Guide angles use displayed coordinates, so logarithmic scales and non-square
panels produce the correct slope. `at` is the fraction along the displayed
segment. `offset` is signed perpendicular clearance in millimetres. The guide
label stays attached when the panel dimensions change; collision avoidance is
not implied. Draw the matrix first if the guide line must sit above it.

Inset colorbars measure their full furniture, support an optional plate/title,
and reject a key that does not fit. `corner='auto'` searches clear space using
the same bounded placement mechanism as legends. Legend order can fill across
rows or down columns, with independently measured row and column gaps.

## Review provenance, geometry and appearance separately

```python
review = i.review_figure(placed, page=i.Rect(0, 0, 90, 75),
                         rules=['OFF_CANVAS', 'TINY_TEXT'])
# Requires the render extra for PNG generation:
# review.save_bundle('out/review', reference='reference.png',
#     sources=[{'path': 'measurements.csv', 'sha256': expected_digest,
#               'url': source_url, 'license': license_url}],
#     panels={'a': placed}, reference_regions={'a': (0.1, 0.2, 0.8, 0.9)},
#     caption='Figure reproduction')
```

The bundle includes original-art SVG/PDF/PNG, a separate diagnostic overlay,
source hashes, panel data/ink rectangles and an HTML reference comparison with
a large-view toggle and panel selector. Explicit `reference_regions` register
normalized image rectangles for corresponding reference crops. Without a
registration the reference stays whole. Expected hashes are checked before writing. Reference
images are copied only into the review bundle, never into scientific exports.
The report does not certify scientific correctness or pixel identity.

The reproducible paper recipes are in `examples/paper_recreations` in the source
checkout. Run `recreate.py --review-bundle` after fetching their pinned source
data. The public gallery continues to use original Inklet compositions.
