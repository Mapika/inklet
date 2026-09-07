# Per-label intensity measurements

The development branch adds `measure_labels` under `inklet.experimental.measurements`.
Install the [volume extra](calibrated-volumes.md) from a development checkout.
This API and its report schema are a research preview, outside stable 3.0.

Measure original channel values on a native voxel grid or on one sampled plane.
The returned table supplies plots, CSV exports and JSON provenance. Display
windows, channel colors and composite clipping do not enter the calculation.
See the [real microscopy example](label-intensities.md) for a complete figure.

![Per-label microscopy intensities linked to images and segmentation](../gallery/label-intensities.png)

The [complete microscopy intensity example](label-intensities.md) connects measured label tables to plots. Its recipe and data attribution are included there.

## A complete example

```python
import numpy as np
from inklet.experimental.volume import Volume
from inklet.experimental.measurements import measure_labels

labels = Volume(np.array([[[17, 17, 0]]], dtype='uint64'),
                (2, 3, 4), 'um', source_id='illustrative labels')
signal = Volume(np.array([[[2., 6., 99.]]]),
                (2, 3, 4), 'um', source_id='illustrative signal')
table = measure_labels(labels, {'Signal': signal}, label_ids=[17, 42])
row = table.rows[0]
assert row['mean'] == 4 and row['std'] == 2
assert row['count'] == 2 and row['measure'] == 48
assert row['sum'] == 8 and row['integral'] == 192
assert table.rows[1]['mean'] is None  # requested ID 42 is absent
csv_text = table.to_csv()
json_text = table.to_json()
```

## Geometry and selection

`measure_labels(labels, channels, *, label_ids=None, region=None,
coverage='intersection')` accepts a nonempty mapping of channel names to data:

- An integer `Volume` of labels and channel `Volume` objects with exactly equal
  shapes, spacing, origins and units. Measurements use original voxel values.
- A label `SampledSection` and intensity sections sharing exactly the same
  `Plane`. Measurements use the sampled floating-point values, with label and
  channel validity masks. Nearest-neighbour labels and interpolated intensities
  remain separate operations, recorded in the report.

Matching geometry does not verify image registration. Resample differing source
volumes onto an explicitly shared plane before measuring them together.
Slab projections, RGB composites and label sections used as intensity channels
are rejected. A projected slab has no single label-bearing depth.

By default, all positive IDs present in the selected label domain are measured
in increasing order. Supply unique nonnegative Python integers in `label_ids`
to choose IDs, preserve a particular order, include background 0, or retain
absent IDs as empty rows. Negative selected IDs are rejected. Large `uint64`
identities are never converted through floating point or used to allocate an
array indexed by the largest ID.

An optional `BoxRegion` selects native voxel or output pixel **centres** using
lower-inclusive, upper-exclusive physical bounds. Selected voxels/pixels count
with their whole element volume/area; boundary elements are not fractionally
clipped. Regions must use the same units. Section area and native volume are
different measures and cannot be substituted for each other.

## Missing samples and table fields

`coverage='intersection'` uses only samples available in every channel. This
provides matching measurement support across channels. `'per-channel'` uses each
channel's own available samples; means can then describe different subsets.
Neither policy fills unavailable intensities with measured zeros.

Each row records one label and one channel:

| Field | Meaning |
| --- | --- |
| `label`, `label_id` | Integer identity and its exact decimal string |
| `selected_count` | Valid label samples after region selection, before channel coverage |
| `count`, `excluded_count` | Contributing samples and selected samples excluded by coverage |
| `coverage_fraction` | `count / selected_count`; null if there are no selected label samples |
| `mean`, `std` | Arithmetic mean and population standard deviation (`ddof=0`) |
| `minimum`, `maximum`, `sum` | Extrema and sum of contributing intensity values |
| `measure`, `measure_unit` | Contributing count × voxel volume (`um^3`, etc.) or pixel area (`um^2`, etc.) |
| `integral` | Intensity sum × element volume or area |

A row with zero contributing samples has null mean, spread and extrema, and
zero sum, measure and integral. This distinguishes no data from a measured zero.
`report()` and `rows` return fresh copies. `to_json()` includes channel/source
geometry, selection and statistics conventions; `to_csv()` writes a long-form
table. When opening CSV in a spreadsheet, import `label_id` as **text** to avoid
rounding large IDs. JSON consumers should also use `label_id` where their numeric
type cannot represent the integer exactly.

Intensity statistics use float64, including sums of integer-valued intensities;
they are not arbitrary-precision integer sums. Overflow is rejected. Population
SD describes sample spread, not a confidence interval, biological replication,
or an uncertainty estimate. The [ImageJ measurement definitions](https://imagej.net/ij/docs/menus/analyze)
also distinguish mean intensity, intensity sums and area-scaled integrated
density. Inklet's `integral` uses the explicit physical element measure and
unmodified source intensity; it does not infer intensity calibration, background
correction, object completeness or colocalization. Retain segmentation methods
and boundary flags alongside the table, as the example does.
