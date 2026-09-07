"""World measurements, visibility policies and registered vector annotations."""
import math

import pytest
import inklet as i
from inklet.core import PathPrim, resolve
from inklet.render.resources import rendering_manifest
from test_scene_projection import snapshot


def record(layer):
    return layer.notes['scene_annotation']


def test_labels_omit_hidden_targets_and_dash_their_leaders():
    scene = snapshot()
    omitted = scene.annotate3d((0, 0, -3), 'Buried')
    assert not omitted.children and omitted.width == 100
    shown = scene.annotate3d((0, 0, -3), 'Buried', hidden='dash', clear=10)
    assert record(shown)['visible'] is False and record(shown)['shown']
    assert 'stroke-dasharray="1,1"' in i.to_svg(shown)
    assert shown.anchor_point('target') == i.Vec2(0, 0)
    assert scene.metadata['cache_key'] == 'fixture'
    assert 'target' not in scene.diagram.anchors


def test_out_of_frame_labels_are_omitted_even_with_show():
    layer = snapshot(depth=False).annotate3d((3, 0, -1), 'Outside', hidden='show')
    assert not layer.children
    assert not record(layer)['in_frame']


def test_label_extents_expand_layout_and_origin_registration_survives():
    scene = snapshot()
    layer = scene.annotate3d((1.9, 0, -1), 'Outside the image', side='e', clear=5)
    assert layer.bbox.x1 > 70
    assert layer.bbox.x0 == -50
    assert layer.anchor_point('origin') == i.Vec2(0, 0)
    art = i.overlay([scene.diagram.anchor('origin', i.Vec2(0, 0)), layer], align='origin')
    placements = resolve(art)
    assert placements[layer.id].point('origin') == placements[scene.diagram.id].point('origin')


@pytest.mark.parametrize('method,args', [
    ('annotate3d', ((0,0,-1), 'Label')),
    ('dimension3d', ((0,0,-1), (1,0,-1))),
    ('arrow3d', ((0,0,-1), (1,0,-1))),
    ('angle3d', ((1,0,-1), (0,0,-1), (0,1,-1))),
])
def test_annotation_exports_need_no_blender_or_depth_in_show_mode(method, args):
    scene = snapshot(depth=False)
    with pytest.raises(ValueError, match='depth'):
        getattr(scene, method)(*args)
    layer = getattr(scene, method)(*args, hidden='show')
    svg = i.to_svg(layer)
    assert '<image' not in svg
    assert i.to_pdf(layer).startswith(b'%PDF')
    assert record(layer)['source_cache_key'] == 'fixture'
    assert rendering_manifest(layer)['scene_annotations'][0]['type'] == record(layer)['type']


def test_dimension_measures_world_distance_instead_of_projected_length():
    scene = snapshot(perspective=True)
    layer = scene.dimension3d((0,0,-1), (1,0,-2), scale=100, unit='mm', hidden='show')
    assert record(layer)['distance'] == pytest.approx(math.sqrt(2))
    assert record(layer)['value'] == pytest.approx(100*math.sqrt(2))
    assert '141.421 mm' in i.to_svg(layer)
    assert layer.anchor_point('end').x == pytest.approx(12.5)


def test_dimension_visibility_is_endpoint_policy_and_text_override_is_preserved():
    scene = snapshot()
    a, b = (-1,0,-3), (0,0,-3)
    assert not scene.dimension3d(a,b).children
    layer = scene.dimension3d(a,b,'Custom',hidden='dash')
    assert record(layer)['visible'] == [True, False]
    assert 'Custom' in i.to_svg(layer)
    assert 'stroke-dasharray' in i.to_svg(layer)
    assert '0 mm' in i.to_svg(scene.dimension3d((0,0,-1),(.0001,0,-1),unit='mm',precision=3))


def test_arrow_head_uses_real_tip_visibility_and_never_a_frame_intersection():
    scene = snapshot()
    assert record(scene.arrow3d((-1,0,-3),(0,0,-3),hidden='dash'))['head_shown'] is False
    assert record(scene.arrow3d((-1,0,-3),(0,0,-3),hidden='show'))['head_shown'] is True
    assert record(scene.arrow3d((-1,0,-1),(3,0,-1)))['head_shown'] is False
    # Starting on the camera plane is safe: only the clipped shaft is projected.
    layer = snapshot(perspective=True).arrow3d((-.1,0,0),(1,0,-1))
    assert record(layer)['head_shown'] is True


def test_arrow_head_size_is_in_page_units_and_vector_style_is_preserved():
    scene = snapshot(perspective=True)
    for depth in (1,2):
        layer = scene.arrow3d((-1,1,-depth),(1,1,-depth),hidden='show',head_size=2,stroke='#123456')
        head = next(n for n in layer.walk() if n.kind == 'arrowhead')
        assert head.bbox.width == pytest.approx(2)
        assert head.style.fill == '#123456'
    assert not any(n.kind=='arrowhead' for n in scene.arrow3d((-1,0,-1),(1,0,-1),head='none').walk())


def test_angle_uses_world_plane_and_true_angle_under_foreshortening():
    scene = snapshot(perspective=True)
    # The 3D arms are perpendicular but their projections have a 45-degree angle.
    layer = scene.angle3d((1,0,-2), (0,0,-3), (1,1,-4), radius=.4, hidden='show')
    assert record(layer)['degrees'] == pytest.approx(90)
    assert '90.0°' in i.to_svg(layer)
    arc = layer.children[0]
    vertices = [p for n in arc.walk() if isinstance(n.prim,PathPrim)
                for sub in n.prim.subpaths for p in sub.points]
    assert len(vertices) > 30
    assert record(layer)['radius'] == .4


@pytest.mark.parametrize('method,args,options', [
    ('annotate3d', ((0,0,-3),'Hidden'), dict(side='bad')),
    ('annotate3d', ((0,0,-1),'Label'), dict(clear=-1)),
    ('dimension3d', ((0,0,-1),(1,0,-1)), dict(scale=0)),
    ('dimension3d', ((0,0,-1),(1,0,-1)), dict(precision=True)),
    ('dimension3d', ((0,0,-1),(0,0,-2)), {}),
    ('dimension3d', ((0,0,-1),(1,0,-1)), dict(offset=float('nan'))),
    ('arrow3d', ((0,0,-1),(1,0,-1)), dict(head_size=0)),
    ('arrow3d', ((0,0,-1),(1,0,-1)), dict(head='bad')),
    ('arrow3d', ((0,0,-1),(0,0,-1)), {}),
    ('angle3d', ((1,0,-1),(0,0,-1),(-1,0,-1)), {}),
    ('angle3d', ((0,0,-1),(0,0,-1),(0,1,-1)), {}),
    ('angle3d', ((1,0,-1),(0,0,-1),(0,1,-1)), dict(radius=-1)),
])
def test_invalid_measurements_and_options_raise(method,args,options):
    with pytest.raises(ValueError):
        getattr(snapshot(),method)(*args,**options)


def test_copy_preserves_internal_and_external_crossing_targets():
    from inklet.diagnostics.cross import declared_crossings
    shape = i.box('Inside')
    external = i.box('External')
    stroke = i.polyline([(-20,0),(20,0)])
    i.crossing(stroke, shape, external)
    copied = i.Diagram(children=(shape,stroke)).copy()
    assert declared_crossings(copied.children[1]) == (copied.children[0].id, external.id)
    assert declared_crossings(stroke) == (shape.id,external.id)


def test_scene_leaders_keep_intentional_crossings_after_document_compilation():
    from dataclasses import replace
    from inklet.diagnostics.cross import declared_crossings
    scene = replace(snapshot(),diagram=i.box('',width=100,height=100).anchor('origin',i.Vec2(0,0)))
    label = scene.annotate3d((0,0,-1),'Outside',side='e',clear=55)
    art = i.overlay([scene.diagram,label],align='origin')
    doc = i.document(width=180)
    doc.add('scene',art)
    compiled = doc.compile()
    assert not any(d.code=='LINK_CROSSES' for d in compiled.diagnostics)
    copied = art.copy()
    assert any(declared_crossings(n) for n in copied.walk())


def test_routed_crossing_exemption_does_not_hide_unrelated_shapes():
    from inklet.links import link, route
    carrier = i.spacer(80,30).anchor('a',i.Vec2(-35,0)).anchor('b',i.Vec2(35,0))
    named = i.box('',width=10,height=10).translated(-15,0).named('Allowed')
    other = i.box('',width=10,height=10).translated(15,0).named('Unrelated')
    shaft = route(link(carrier.at('a'),carrier.at('b')),resolve(carrier))
    root = i.Diagram(children=(carrier,named,other,shaft))
    before = [d for d in i.lint(root) if d.code=='LINK_CROSSES']
    assert len(before)==2
    i.crossing(shaft,named)
    after = [d for d in i.lint(root.copy()) if d.code=='LINK_CROSSES']
    assert len(after)==1 and 'Unrelated' in after[0].message


def test_guide_examples_execute_from_a_saved_snapshot(tmp_path, monkeypatch):
    from pathlib import Path
    import re
    guide = Path(__file__).resolve().parents[1]/'docs/scene-annotations.md'
    blocks = re.findall(r'^```python\n(.*?)^```',guide.read_text(),re.M|re.S)
    scene = snapshot()
    # Camera looking along -world Z would collapse the guide's vertical dimension.
    scene.metadata['projection']['world_to_camera'] = [[1,0,0,0],[0,0,1,-1.5],[0,1,0,-5],[0,0,0,1]]
    monkeypatch.setattr(i,'render_blend',lambda *a,**kw:scene)
    monkeypatch.chdir(tmp_path)
    namespace = {}
    for code in blocks:
        exec(code,namespace)
    assert (tmp_path/'annotated.svg').is_file()
    assert (tmp_path/'annotated.pdf').read_bytes().startswith(b'%PDF')
    assert record(namespace['length'])['value'] == pytest.approx(240)
