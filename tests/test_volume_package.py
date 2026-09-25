"""The stable inklet.volume package and its inklet.experimental compatibility paths."""
import importlib
import subprocess
import sys
import warnings

import pytest

import inklet.volume as volume

OLD_PATHS = {
    'volume': ['Volume', 'Slice'],
    'sections': ['Plane', 'SampledSection', 'reslice'],
    'slabs': ['Slab', 'SlabProjection', 'project_slab'],
    'regions': ['BoxRegion'],
    'channels': ['Channel', 'Composite'],
    'contours': ['LabelContour'],
    'measurements': ['LabelMeasurements', 'measure_labels'],
    'tiff': ['TiffImage', 'read_tiff'],
}

# Names other code imported from the old modules, including private helpers
# and names the 4.2 modules merely imported.
OLD_EXTRAS = {
    'volume': ['_numpy', '_positive', '_UNITS', '_vector', 'ImagePrim', 'i', 'io', 'math', 'dataclass'],
    'sections': ['Volume', '_numpy', '_positive', '_UNITS', '_snapshot', '_vector', 'ImagePrim'],
    'slabs': ['Volume', 'Plane', 'SampledSection', 'BoxRegion', '_snapshot', '_validate', 'replace'],
    'regions': ['Volume', 'Plane', '_snapshot', '_UNITS', 'itertools'],
    'channels': ['SampledSection', 'SlabProjection', '_geometry', '_snapshot', 'parse_color', 'to_hex'],
    'contours': ['SampledSection', '_runs', 'PathPrim', 'Subpath', 'Vec2', 'field'],
    'measurements': ['Volume', 'SampledSection', 'BoxRegion', '_region', 'Mapping', 'csv', 'json'],
    'tiff': ['Volume', '_numpy', 'ET', 'Path', 'hashlib', 'json'],
}


def test_all_lists_every_moved_public_name():
    moved = sorted(name for names in OLD_PATHS.values() for name in names)
    assert sorted(volume.__all__) == moved
    assert len(set(volume.__all__)) == len(volume.__all__)
    namespace = {}
    exec('from inklet.volume import *', namespace)
    assert sorted(k for k in namespace if not k.startswith('__')) == moved


@pytest.mark.parametrize('module', sorted(OLD_PATHS))
def test_old_paths_return_the_same_objects(module):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        old = importlib.import_module(f'inklet.experimental.{module}')
    new = importlib.import_module(f'inklet.volume._{module}')
    for name in OLD_PATHS[module]:
        assert getattr(old, name) is getattr(volume, name)
    for name in OLD_EXTRAS[module]:
        assert getattr(old, name) is getattr(new, name)
    assert 'inklet.volume' in old.__doc__


def test_methods_use_the_stable_home():
    plane = volume.Plane((0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 2), (1, 1), 'um')
    region = volume.BoxRegion('box', (-1, -1, -1), (1, 1, 1), 'um')
    assert volume.Slab(plane, 1, 2).report()['schema'] == 'inklet.slab/0.1'
    assert region.report()['schema'] == 'inklet.box-region/0.1'


def test_importing_inklet_stays_light():
    code = ('import sys, inklet\n'
            'assert "inklet.volume" not in sys.modules\n'
            'import inklet.volume\n'
            'heavy = {"numpy", "scipy", "skimage", "tifffile", "PIL"} & set(sys.modules)\n'
            'assert not heavy, heavy\n')
    subprocess.run([sys.executable, '-c', code], check=True)
