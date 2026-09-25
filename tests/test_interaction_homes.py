"""The 4.3 interaction homes and the experimental paths that still reach them.

`inklet.selection`, `inklet.project`, `inklet.editor` and the private
`inklet.render._viewer` graduated from `inklet.experimental`. Every name the
4.2.0 modules exposed stays importable from the old path as the same object,
without a warning, and the package itself never imports those shims.
"""
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import warnings
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: The 4.2.0 namespace of each moved module, collected from
#: `git show v4.2.0:src/inklet/experimental/...` (dunder names excluded).
RELEASED = {
    'selection': ('inklet.selection', [
        'KeyedTable', 'Mapping', 'MappingProxyType', 'RebasedSelection', 'SCHEMA',
        'SelectionState', '_ids', '_name', 'annotations', 'dataclass', 'hashlib',
        'json', 'math']),
    'temporal': ('inklet.selection._temporal', [
        'date', 'datetime', 're', 'time_milliseconds', 'time_seconds', 'time_value',
        'timezone']),
    '_table_adapters': ('inklet.selection._table_adapters', [
        'Mapping', 'Set', '_headers', '_scalar', '_time_columns', '_time_scalar',
        'math', 'pandas_columns', 'polars_columns']),
    'project': ('inklet.project', [
        'Asset', 'AssetManifest', 'EntityMap', 'FigureProject', 'LayoutEditor',
        'Path', 'SCHEMA', '_name', '_targets', 'hashlib', 'json', 'os', 'shutil',
        'tempfile']),
    'project.assets': ('inklet.project.assets', [
        'Asset', 'AssetManifest', 'Path', 'PurePosixPath', 'asdict', 'dataclass',
        'digest', 'file_at', 'hashlib', 'name', 're', 'relative_path']),
    'project.identity': ('inklet.project.identity', [
        'EntityMap', 'KeyedTable', 'Mapping', 'MappingProxyType', 'SelectionState',
        '_ids', 'dataclass', 'name']),
    'layout_editor': ('inklet.editor', [
        'BaseHTTPRequestHandler', 'Composition', 'ET', 'LayoutEditor', 'Path',
        'SCHEMA', 'ThreadingHTTPServer', '_EDITORS', '_expression', '_placement',
        '_targets', 'annotations', 'copy', 'document', 'json', 'math', 'parse_qs',
        'secrets', 'threading', 'urlsplit']),
    'scene_viewer': ('inklet.render._viewer', [
        'EllipsePrim', 'Path', 'PathPrim', 'RectPrim', '_marker_geometry',
        '_render_svg', '_simple_polygon', 'base64', 'html', 'json', 'math',
        'parse_color', 're', 'to_html']),
}

EDITOR_ASSETS = ('gestures.js', 'page.html', 'workspace.css', 'workspace.js')
VIEWER_ASSETS = ('controls.js', 'page.html', 'runtime.js', 'spatial.js')


@pytest.mark.parametrize('old', sorted(RELEASED))
def test_every_released_name_is_the_same_object_at_its_new_home(old):
    new, names = RELEASED[old]
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        shim = importlib.import_module('inklet.experimental.' + old)
    home = importlib.import_module(new)
    for name in names:
        assert getattr(shim, name) is getattr(home, name), f'{old}.{name}'


def test_new_public_surfaces():
    import inklet.editor
    import inklet.project
    import inklet.selection
    import inklet.experimental.project as old_project
    assert inklet.selection.__all__ == ['KeyedTable', 'SelectionState', 'RebasedSelection']
    assert inklet.editor.__all__ == ['LayoutEditor']
    assert 'LayoutEditor' not in inklet.project.__all__
    assert {'Asset', 'AssetManifest', 'EntityMap', 'FigureProject', 'ExportDriftWarning'} <= set(inklet.project.__all__)
    assert issubclass(inklet.project.ExportDriftWarning, UserWarning)
    assert old_project.__all__ == ['Asset', 'AssetManifest', 'EntityMap', 'FigureProject']
    assert old_project.assets.__name__ == 'inklet.experimental.project.assets'
    for name in old_project.__all__:
        assert getattr(old_project, name) is getattr(inklet.project, name)


def test_saved_schema_ids_are_unchanged():
    import inklet.project
    from inklet.project import AssetManifest, EntityMap
    from inklet.selection import SCHEMA
    assert SCHEMA == 'inklet.selection/0.1'
    assert inklet.project.SCHEMA == 'inklet.figure-project/0.1'
    assert AssetManifest().to_dict()['schema'] == 'inklet.assets/0.1'
    assert EntityMap().to_dict()['schema'] == 'inklet.entities/0.1'


def test_the_package_never_imports_the_compatibility_shims():
    shims = ['inklet.experimental.' + old for old in RELEASED]
    code = (
        'import sys, inklet, inklet.selection, inklet.project, inklet.editor\n'
        'import inklet.render._viewer\n'
        'from inklet.selection import KeyedTable\n'
        'import inklet.experimental.browser, inklet.experimental.browser.compiled\n'
        'import inklet.experimental.fields, inklet.experimental.grid\n'
        'import inklet.experimental.measurement, inklet.experimental.engineering\n'
        'import inklet.experimental.figure_planner\n'
        'KeyedTable("t", {"id": ["a"]})\n'
        f'print(sorted(set({shims!r}) & set(sys.modules)))\n')
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    out = subprocess.run([sys.executable, '-c', code], env=env, check=True,
                         capture_output=True, text=True).stdout
    assert out.strip() == '[]'


def test_the_source_tree_holds_the_assets_the_modules_read():
    import inklet.editor
    import inklet.render._viewer
    for name in EDITOR_ASSETS:
        assert (Path(inklet.editor.__file__).parent / name).is_file()
    for name in VIEWER_ASSETS:
        assert (Path(inklet.render._viewer.__file__).parent / name).is_file()


@pytest.fixture(scope='module')
def wheel(tmp_path_factory):
    supplied = os.environ.get('INKLET_WHEEL')
    if supplied:
        return Path(supplied)
    uv = shutil.which('uv')
    if uv is None:
        pytest.skip('building a wheel needs uv; set INKLET_WHEEL to check a built one')
    out = tmp_path_factory.mktemp('dist')
    subprocess.run([uv, 'build', '--wheel', '--out-dir', str(out), str(ROOT)],
                   check=True, capture_output=True)
    return next(out.glob('inklet-*.whl'))


def test_the_wheel_contains_the_editor_and_viewer_assets(wheel):
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    for name in ('__init__.py', *EDITOR_ASSETS):
        assert f'inklet/editor/{name}' in names
    for name in ('__init__.py', *VIEWER_ASSETS):
        assert f'inklet/render/_viewer/{name}' in names
    for name in ('selection/__init__.py', 'selection/_temporal.py',
                 'selection/_table_adapters.py', 'project/__init__.py',
                 'project/assets.py', 'project/identity.py',
                 'experimental/selection.py', 'experimental/temporal.py',
                 'experimental/_table_adapters.py', 'experimental/layout_editor.py',
                 'experimental/scene_viewer.py', 'experimental/project/__init__.py'):
        assert f'inklet/{name}' in names
    assert not any(n.startswith('inklet/grid') for n in names)
