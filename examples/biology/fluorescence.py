"""Read the hash-locked, calibrated two-channel Allen Institute example."""
from pathlib import Path

from inklet.experimental.tiff import read_tiff
from .data import fetch

LOCK=Path(__file__).with_name('cells3d.lock.json')


def load(root):
    """Verify before reading; keep network access in the example, outside Inklet."""
    record=fetch(root,lock_path=LOCK)
    image=read_tiff(Path(root)/record['files'][0]['path'],
        spacing_zyx=record['spacing_zyx'],unit=record['unit'],origin_xyz=record['origin_xyz'],
        channel_names=record['channels'],source_id='Allen Institute / cells3d')
    report=image.report()
    if report['native_axes']!=record['axes']:
        raise ValueError('Unexpected fluorescence TIFF axes')
    if report['source_shape']!=record['shape'] or any(str(v.data.dtype)!=record['dtype'] for v in image.volumes):
        raise ValueError('Unexpected fluorescence source shape or dtype')
    return image.channels,dict(record,tiff_import=report)
