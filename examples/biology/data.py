"""Fetch a small, hash-locked public N5 pyramid level, then read it locally."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

LOCK=Path(__file__).with_name('organelle.lock.json')


def fetch(root):
    """Download the recorded objects atomically; never accept changed bytes."""
    root=Path(root);record=json.loads(LOCK.read_text())
    def one(entry):
        path=Path(entry['path'])
        if path.is_absolute() or '..' in path.parts:raise ValueError('Invalid locked asset path')
        if entry.get('missing'):
            if (root/path).exists():raise ValueError('Unexpected data in an absent source chunk: '+entry['path'])
            return
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
        def valid(b):return len(b)==entry['size'] and hashlib.sha256(b).hexdigest()==entry['sha256']
        if dest.exists() and valid(dest.read_bytes()):return
        with urllib.request.urlopen(record['base_url']+entry['path'],timeout=90) as response:
            data=response.read(entry['size']+1)
        if not valid(data):raise ValueError('Source size/hash changed: '+entry['path'])
        stage=dest.with_name(dest.name+'.part');stage.write_bytes(data);stage.replace(dest)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(one,record['files']))
    return record


def load(root):
    """N5 reading is an example dependency, separate from Inklet's volume API."""
    import warnings
    import zarr
    root=Path(root)
    paths=('em/fibsem-uint16','labels/mito_seg','labels/nucleus_seg','labels/er_seg')
    # Zarr 2's N5 reader is pinned for this archived example. Its deprecation
    # concerns a future major version; it does not change the stored data.
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='.*N5Store is deprecated.*',category=FutureWarning)
        store=zarr.N5Store(str(root))
        arrays={p.split('/')[-1]:zarr.open_array(store,path=p+'/s4',mode='r')[:] for p in paths}
    transforms=[json.loads((root/p/'s4/attributes.json').read_text())['transform'] for p in paths]
    for transform in transforms:
        if transform['axes']!=['z','y','x'] or transform['units']!=['nm']*3:
            raise ValueError('Unexpected source coordinate convention')
        if transform['scale']!=transforms[0]['scale'] or transform['translate']!=transforms[0]['translate']:
            raise ValueError('Image and segmentation grids do not coincide')
    if len({a.shape for a in arrays.values()})!=1:raise ValueError('Image and segmentation shapes differ')
    return arrays,transforms[0]
