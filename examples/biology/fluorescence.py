"""Read the hash-locked, calibrated two-channel Allen Institute example."""
from pathlib import Path

from inklet.experimental.volume import Volume
from .data import fetch

LOCK=Path(__file__).with_name('cells3d.lock.json')


def load(root):
    """Verify before reading; keep network access in the example, outside Inklet."""
    import tifffile
    record=fetch(root,lock_path=LOCK)
    with tifffile.TiffFile(Path(root)/record['files'][0]['path']) as source:
        if source.series[0].axes!=record['axes']:
            raise ValueError('Unexpected fluorescence TIFF axes')
        array=source.asarray()
    if list(array.shape)!=record['shape'] or str(array.dtype)!=record['dtype']:
        raise ValueError('Unexpected fluorescence source shape or dtype')
    if record['axes']!='ZCYX' or len(record['channels'])!=array.shape[1]:
        raise ValueError('Unexpected fluorescence source channel axes')
    volumes={name:Volume(array[:,index],tuple(record['spacing_zyx']),record['unit'],
        tuple(record['origin_xyz']),f'Allen Institute / cells3d / channel {index} / {name}')
        for index,name in enumerate(record['channels'])}
    return volumes,record
