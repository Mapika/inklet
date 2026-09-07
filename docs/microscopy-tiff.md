# Importing microscopy TIFF files

`inklet.experimental.tiff.read_tiff` reads local scalar microscopy channels into
immutable, calibrated `Volume` objects. Install the development branch's
[volume extra](calibrated-volumes.md), which includes `tifffile`. This is a
research API, outside stable 3.0.

```python
from inklet.experimental.tiff import read_tiff

# Run with your local acquisition and its documented calibration.
image = read_tiff('acquisition.ome.tif',
    spacing_zyx=(.5, .1, .1), unit='um', origin_xyz=(0, 0, 0),
    source_id='experiment-17 / field-2', time_index=3,
    channel_names=['DNA', 'Actin'])
channels = image.channels
provenance = image.report()
```

For an executable real-data workflow, run the [label intensity example](label-intensities.md).
Its source helper verifies the downloaded file against a pinned SHA-256 before
calling this importer. The core importer performs no downloads.

## Explicit acquisition choices

`read_tiff(path, *, spacing_zyx, unit, source_id, channel_names=None,
origin_xyz=(0, 0, 0), series=0, time_index=None, axes=None)` supports single-file
TIFF, ImageJ TIFF and single-file OME-TIFF series with scalar `T,C,Z,Y,X` axes.
The underlying [tifffile reader](https://github.com/cgohlke/tifffile) supplies the
series axes and decoded array. Each channel becomes a ZYX volume.

- **Calibration is required.** Provide ZYX spacing and a supported physical unit
  (`m`, `mm`, `um`, `nm`). XYZ origin is the first voxel's centre. The default
  zero origin is a local coordinate convention, not an inferred microscope stage
  position. TIFF resolution tags and OME calibration are not automatically used.
- **Time is explicit.** If the decoded series has a `T` axis, provide
  `time_index`, even if that axis has length one. A time index on a series
  without `T` is an error. A singleton time axis squeezed away by tifffile is
  absent from the decoded axes and is recorded that way.
- **Axes are checked.** Unknown axes such as generic `Q` or `I` stacks are
  rejected. Supply `axes='ZYX'`, for example, only when acquisition information
  establishes the correct interpretation. An override names each decoded array
  dimension once; it does not reshape or repair inconsistent metadata.
- **Channels have identities.** Provide unique names in decoded channel order;
  otherwise receive `channel-0`, `channel-1`, etc. Names are caller declarations,
  not inferred stains or wavelengths. The volume source ID includes series,
  time point and channel index as well as the name.

Missing Z or C axes become singleton dimensions. A 2D image therefore still
requires explicit Z spacing to create a volume; avoid interpreting this chosen
thickness as an observed three-dimensional structure. `series` defaults to 0;
select another series explicitly for multi-series files.

## Scope and provenance

The importer hashes the file and eagerly decodes the selected series, including
all its time points, before selecting the requested time. Plan memory for both
decoded data and immutable channel copies. It is not a lazy reader for very large
acquisitions. Compressed TIFF codecs beyond the reader's built-in codecs can
require a separately installed codec package; decoder errors propagate.

RGB photometric samples, unsupported axes, detected missing image pages, and
OME references to other files are rejected. Multi-file OME acquisitions,
pyramidal level selection, stage-position mapping and automatic metadata
calibration are outside this preview. There is no missing-plane filling policy.

`image.channels` returns a fresh name-to-volume mapping. `image.report()` returns
a fresh JSON-compatible record containing the file's basename and SHA-256,
reader version, selected series/time, native and declared axes, override flag,
original shape, channel identities and supplied calibration. The hash identifies
the bytes read; it is not verification against a trusted source unless the caller
also checks an expected hash. No absolute local path is included in the report.
