"""Calibrated microscopy volumes, sections, slabs, channels and measurements.

Install ``inklet[volume]`` for the numerical dependencies. Importing this
package stays light: numpy, scipy, scikit-image, Pillow and tifffile load
only when an operation needs them.

Arrays are Z,Y,X; world coordinates are X,Y,Z in an explicit physical unit.
These names were previously available from ``inklet.experimental.volume``,
``sections``, ``slabs``, ``regions``, ``channels``, ``contours``,
``measurements`` and ``tiff``; those paths still work and return the same
objects.
"""
from ._volume import Slice, Volume
from ._sections import Plane, SampledSection, reslice
from ._regions import BoxRegion
from ._slabs import Slab, SlabProjection, project_slab
from ._channels import Channel, Composite
from ._contours import LabelContour
from ._measurements import LabelMeasurements, measure_labels
from ._tiff import TiffImage, read_tiff

__all__ = [
    'Volume', 'Slice',
    'Plane', 'SampledSection', 'reslice',
    'Slab', 'SlabProjection', 'project_slab',
    'BoxRegion',
    'Channel', 'Composite',
    'LabelContour',
    'LabelMeasurements', 'measure_labels',
    'TiffImage', 'read_tiff',
]
