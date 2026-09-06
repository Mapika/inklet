"""Projection, clipping and occlusion without Blender or NumPy."""
import math
from pathlib import Path
import re
import struct

import pytest
import inklet as i
from inklet.core import PathPrim


def snapshot(*, perspective=False, depth=True, width=100):
    values = [2. if 30 <= x < 70 and 30 <= y < 70 else 1e10
              for y in range(100) for x in range(100)]
    passes = {'depth': i.ScenePass('depth', (100, 100), 1, width, width,
                                  struct.pack('<10000f', *values))} if depth else {}
    metadata = dict(width_mm=width, height_mm=width, pixels=[100, 100], cache_key='fixture',
        projection=dict(type='PERSP' if perspective else 'ORTHO',
            world_to_camera=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
            bounds=[-2,2,-2,2], near=.1, far=20))
    return i.SceneRender(i.spacer(width,width), metadata, False, passes)


def paths(layer):
    return [child.prim for child in layer.children if isinstance(child.prim, PathPrim)]


def test_projection_preserves_units_orientation_and_visibility():
    result = snapshot()
    assert result.project((0,0,-3)).point == i.Vec2(0,0)
    assert result.project((0,0,-3)).visible is False
    assert result.project((0,0,-1)).visible is True
    assert result.project((1,1,-3)).point == i.Vec2(25,-25)
    assert result.project((3,0,-1)).in_frame is False
    assert result.project((0,0,1)).visible is False
    assert snapshot(depth=False).project((0,0,-1)).visible is None


def test_perspective_division_and_axial_depth():
    result = snapshot(perspective=True)
    point = result.project((2,2,-2))
    assert point.point == i.Vec2(25,-25)
    assert point.depth == pytest.approx(2)
    with pytest.raises(ValueError, match='camera plane'):result.project((0,0,0))


def test_path_clips_to_frame_and_splits_around_depth_occluder():
    layer = snapshot().path3d([(-3,0,-3),(3,0,-3)], stroke='red', stroke_width=.4)
    assert layer.width == 100 and layer.height == 100
    runs = paths(layer)[0].subpaths
    assert len(runs) == 2
    assert runs[0].points[0] == i.Vec2(-50,0)
    assert runs[0].points[-1] == i.Vec2(-20,0)
    assert runs[1].points[0] == i.Vec2(20,0)
    assert runs[1].points[-1] == i.Vec2(50,0)
    assert layer.notes['scene_overlay']['hidden_runs'] == 1
    assert '<image' not in i.to_svg(layer)


def test_hidden_dashes_stay_vector_and_keep_physical_alignment():
    layer = snapshot().path3d([(-2,0,-3),(2,0,-3)], hidden='dash', stroke='red')
    assert len(layer.children) == 2
    assert layer.children[0].style.stroke_dash == (1.,1.)
    assert layer.children[1].style.stroke_dash is None
    svg = i.to_svg(layer)
    assert 'stroke-dasharray' in svg and '<image' not in svg
    assert i.to_pdf(layer).startswith(b'%PDF')


def test_show_does_not_require_depth_and_clips_near_plane():
    result = snapshot(perspective=True, depth=False)
    layer = result.path3d([(-.1,0,1),(.1,0,-3)], hidden='show')
    assert len(paths(layer)) == 1
    assert all(math.isfinite(p.x) for path in paths(layer) for sub in path.subpaths for p in sub.points)
    with pytest.raises(ValueError, match='depth'):result.path3d([(0,0,-1),(1,0,-1)])


def test_visibility_interpolation_is_perspective_correct():
    # Projected endpoints are x=-25 and x=25, but world-space midpoint x=1.25
    # would give x=12.5: screen midpoints must use reciprocal camera distance.
    result = snapshot(perspective=True)
    layer = result.path3d([(-1,0,-1),(4,0,-4)])
    runs = paths(layer)[0].subpaths
    # The near end is visible inside the central occluder; the far end is hidden.
    assert runs[0].points[0].x == pytest.approx(-25)
    assert runs[0].points[-1].x == pytest.approx(8, abs=.6)
    assert runs[-1].points[-1].x == pytest.approx(25)


@pytest.mark.parametrize('options', [dict(hidden='bad'),dict(step_px=0),dict(step_px=float('nan')),
    dict(depth_bias=-1),dict(max_samples=1),dict(max_samples=True)])
def test_invalid_controls_are_rejected(options):
    with pytest.raises(ValueError):snapshot().path3d([(0,0,-1),(1,0,-1)], **options)


def test_budget_empty_path_and_invalid_coordinates():
    with pytest.raises(ValueError, match='max_samples'):
        snapshot().path3d([(-2,0,-3),(2,0,-3)], max_samples=10)
    with pytest.raises(ValueError, match='max_samples'):
        snapshot().path3d([(-2,0,-3),(2,0,-3)], step_px=5e-324)
    with pytest.raises(ValueError):snapshot().path3d([(0,0,-1)])
    with pytest.raises(ValueError):snapshot().project((float('nan'),0,0))
    with pytest.raises(ValueError):snapshot().project('123')
    layer = snapshot().path3d([(0,0,1),(1,0,1)])
    assert not layer.children and layer.width == 100


def test_guide_runs_from_a_saved_scene_snapshot(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1]/'docs/scene-paths.md'
    blocks = re.findall(r'^```python\n(.*?)^```', source.read_text(), re.M|re.S)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(i, 'render_blend', lambda *args, **kwargs: snapshot(width=kwargs['width']))
    namespace = {}
    for block in blocks:
        exec(block, namespace)
    assert (tmp_path/'route.svg').is_file()
    assert (tmp_path/'route.pdf').read_bytes().startswith(b'%PDF')
    assert namespace['scene'].diagram.anchor_point('probe') == namespace['point'].point
