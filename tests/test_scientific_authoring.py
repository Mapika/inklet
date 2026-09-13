"""Geometry contracts behind compact labels, curved arrows and shared 3D views."""
import math
from dataclasses import replace
import pytest
import inklet as i
from inklet.core import PathPrim, Vec2
from inklet.three import Camera, Mesh, MeshError, Vec3, view_of
from inklet.three.solids import cube, sphere


def test_tag_measures_glyphs_instead_of_counting_characters():
    narrow=i.tag('iiii',size=3,pad=(1,.5))
    wide=i.tag('WWWW',size=3,pad=(1,.5))
    assert wide.bbox.width > narrow.bbox.width*1.5
    for node in [narrow,wide]:
        assert node.bbox.width == pytest.approx(node.notes['tag']['text_width']+2)
        assert node.bbox.height == pytest.approx(node.notes['tag']['text_height']+1)


def test_tag_keeps_multiline_and_markup_text_editable():
    tag=i.tag('**ALPN**\nprojection neurons',size=3,pad=('1mm','0.5mm'))
    svg=i.to_svg(tag,text='embed')
    assert '<text' in svg and 'projection neurons' in svg
    assert '<image' not in svg
    assert tag.scaled(2).bbox.width == pytest.approx(tag.bbox.width*2)


@pytest.mark.parametrize('pad',[-1,(1,-1),(1,2,3),float('nan')])
def test_tag_rejects_invalid_padding(pad):
    with pytest.raises(ValueError):i.tag('AL',pad=pad)


def test_tag_does_not_silently_restyle_a_diagram():
    with pytest.raises(ValueError,match='style the Diagram'):i.tag(i.text('AL'),size=3)


def test_arrow_head_follows_exact_cubic_tangent_and_shaft_stops_short():
    path=i.as_drawn(i.path(curves=[[(0,0),(10,0),(10,0),(10,10)]]))
    arrow=i.arrow(path,head_length=2,head_width=1)
    shaft,head=arrow.children
    triangle=head.prim.subpaths[0].points
    assert triangle[0] == Vec2(10,10)
    midpoint=(triangle[1]+triangle[2])*.5
    assert midpoint == Vec2(10,8)
    sub=shaft.prim.subpaths[0]
    assert sub.curves and sub.points[-1].y < 8.1
    assert sub.points[-1].y > 7.8
    assert i.to_svg(arrow).count('C') > 0


def test_arrow_preserves_authored_tip_coordinates_after_layout():
    arrow=i.arrow([(100,20),(110,15),(120,20)],both=True)
    drawn=i.as_drawn(arrow)
    assert drawn.transform.apply(drawn.anchor_point('start')) == Vec2(100,20)
    assert drawn.transform.apply(drawn.anchor_point('end')) == Vec2(120,20)
    assert arrow.bbox.center.x == pytest.approx(0)
    assert arrow.notes['arrow']['both']


def test_arrow_handles_repeated_waypoints_and_short_paths():
    node=i.arrow([(0,0),(0,0),(.5,0)],head_length=10,both=True,smooth=0)
    assert node.notes['arrow']['head_length'] <= .1
    shaft=node.children[0].prim.subpaths[0]
    assert shaft.points[-1].x > shaft.points[0].x


@pytest.mark.parametrize('points',[[],[(0,0)],[(0,0),(0,0)],[(0,0),(math.nan,0)]])
def test_arrow_rejects_degenerate_data(points):
    with pytest.raises(ValueError):i.arrow(points)


def test_arrow_rejects_closed_paths():
    with pytest.raises(ValueError,match='open'):i.arrow(i.polygon([(0,0),(1,0),(0,1)]))


def test_mesh_from_arrays_copies_data_and_rejects_fractional_indices():
    vertices=[[0,0,0],[1,0,0],[0,1,0]]
    mesh=Mesh.from_arrays(vertices,[(0,1,2)])
    vertices[0][0]=20
    assert mesh.vertices[0] == Vec3()
    with pytest.raises(MeshError,match='integers'):Mesh.from_arrays(vertices,[(0.,1.,2.)])
    with pytest.raises(MeshError,match='finite'):Mesh.from_arrays([(0,0,math.inf)],[])


def test_common_view_does_not_refit_or_recenter_a_smaller_mesh():
    large=cube(2)
    view=Camera.named('front').frame(large,width=40)
    small=Mesh(tuple(v*.25+Vec3(.5,0,0) for v in large.vertices),large.faces)
    model=i.model(small,view=view,style='solid')
    assert view_of(model) is view
    assert model.bbox.width == pytest.approx(10)
    assert model.bbox.center.x == pytest.approx(10)
    marker=view.markers([Vec3(.5,0,0)],radius=1)
    assert marker.bbox.center.x == pytest.approx(model.bbox.center.x)
    with pytest.raises(MeshError,match='omit width'):i.model(small,view=view,width=20)


def test_shared_view_paths_project_positions_and_fade_with_depth():
    view=Camera.named('front').frame(cube(2),width=40)
    lines=[[(0,-.5,0),(1,-.5,0)],[(0,.5,0),(1,.5,0)]]
    node=view.paths(lines,depth_cue=.5,levels=2)
    far,near=node.children
    assert far.style.stroke != near.style.stroke
    for child in node.children:
        points=child.prim.subpaths[0].points
        assert points[0].x == pytest.approx(0)
        assert points[-1].x == pytest.approx(20)
    assert node.notes['projection']['occlusion']=='xray'


def test_shared_view_overlays_validate_data_and_sizes():
    view=Camera.named('front').frame(cube(2),width=40)
    with pytest.raises(MeshError):view.paths([[(0,0,0),(0,math.nan,0)]])
    with pytest.raises(ValueError):view.markers([(0,0,0)],radius=-1)
    with pytest.raises(ValueError):view.paths([],levels=2.5)
    with pytest.raises(ValueError):view.paths([],depth_cue=1.1)
    assert not view.paths([]).children


def test_simplification_is_optional_immutable_and_preserves_extent_approximately():
    pytest.importorskip('fast_simplification')
    original=sphere(subdivisions=3)
    reduced=original.simplified(100)
    assert len(reduced.faces) < len(original.faces)
    assert len(original.faces)>100
    assert reduced.radius == pytest.approx(original.radius,rel=.12)
    assert original.simplified(len(original.faces)) is original
    with pytest.raises(MeshError):original.simplified(0)
    with pytest.raises(MeshError,match='part by part'):
        replace(original,groups=tuple('a' if k%2 else 'b' for k in range(len(original.faces)))).simplified(100)


def test_numpy_scalar_lengths_and_array_paths_work_without_manual_conversion():
    np=pytest.importorskip('numpy')
    assert i.mm(np.int64(4)) == 4
    assert i.mm(np.float32(2.5)) == 2.5
    node=i.arrow(np.array([[0,0],[10,3],[20,0]],dtype=np.int64))
    assert node.notes['arrow']['original_length']>20
    assert i.tag('AL',pad=np.int64(1)).bbox.width>2


def test_connect_clips_placed_nodes_and_keeps_opposing_bows_separate():
    from inklet.links import link_flags
    a=i.box('A',pad=2).translated(10,20)
    b=i.box('B',pad=2).translated(45,20)
    forward=i.connect(a,b,offset=5,arrow_size=2,standoff=.5)
    reverse=i.connect(b,a,offset=5,arrow_size=2,standoff=.5)
    assert not link_flags(forward)
    assert forward.anchor_point('start').x > a.bbox.center.x
    assert forward.anchor_point('end').x < b.bbox.center.x
    # Neither head can be hidden by a destination rectangle.
    for edge,node in [(forward,b),(reverse,a)]:
        tip=edge.anchor_point('end');box=node.bbox
        assert not (box.x0 < tip.x < box.x1 and box.y0 < tip.y < box.y1)
    assert forward.bbox.center.y != pytest.approx(reverse.bbox.center.y)


def test_connect_resolves_parent_transforms_and_requires_scene_membership():
    a=i.box('a');b=i.box('b').translated(30,0)
    scene=i.Diagram(children=(a,b)).translated(100,50)
    edge=i.connect(a,b,within=scene)
    assert edge.anchor_point('start').x > 100
    assert edge.anchor_point('end').y == pytest.approx(50)
    with pytest.raises(ValueError,match='belong'):i.connect(a,b,within=a)


def test_label_column_keeps_anchors_and_measured_clearances_with_crowded_targets():
    labels=[i.tag(s,size=3,pad=.4) for s in ['102','103','116\ncluster','79']]
    targets=[(0,12),(0,12.1),(0,13),(0,2)]
    node=i.label_column(labels,targets,x=15,bounds=(0,35),gap=1.5)
    notes=node.notes['label_column']
    assert [v['target'] for v in notes] == targets
    boxes=sorted((v['box'] for v in notes),key=lambda b:b[1])
    assert boxes[0][1] >= 0 and boxes[-1][3] <= 35
    assert all(b[1]-a[3] >= 1.5-1e-9 for a,b in zip(boxes,boxes[1:]))
    assert [v['box'][2]-v['box'][0] for v in notes] == pytest.approx([v.bbox.width for v in labels])
    assert all(v['box'][0] == pytest.approx(15) for v in notes)


def test_label_column_rejects_overfull_and_invalid_inputs():
    labels=[i.text('large',size=10)]*3
    with pytest.raises(ValueError,match='do not fit'):i.label_column(labels,[(0,0)]*3,x=10,bounds=(0,5))
    with pytest.raises(ValueError,match='one target'):i.label_column(labels,[],x=10,bounds=(0,50))
    with pytest.raises(ValueError,match='finite'):i.label_column([labels[0]],[(0,math.nan)],x=10,bounds=(0,50))


def test_panel_region_uses_same_log_reversed_transform_as_marks():
    p=i.panel(100,50,x=i.log((1,1000)),y=(10,0))
    region=p.region(10,2,100,8)
    a,b=p.point(10,2),p.point(100,8)
    assert (region.x0,region.x1) == pytest.approx((a.x,b.x))
    assert (region.y0,region.y1) == pytest.approx((a.y,b.y))
    assert region.width == pytest.approx(100/3)
    assert p.region(100,8,10,2) == region


@pytest.mark.parametrize('content',['s','i','d','159.6','.55','scale\nweights'])
def test_ink_bounds_center_actual_glyphs_without_outlining_live_text(content):
    from inklet.typeset.outline import text_to_paths
    from inklet.core import Envelope, TextPrim
    node=i.text(content,size=15,font='Arimo',bounds='ink').translated(40,30)
    text_nodes=[v for v in i.resolve(node).values() if isinstance(v.diagram.prim,TextPrim)]
    assert len(text_nodes)==1
    placed=text_nodes[0]
    actual=Envelope.union_all(path.envelope() for path,_ in text_to_paths(placed.diagram.prim)).transform(placed.world).bbox()
    assert (actual.center.x,actual.center.y) == pytest.approx((40,30))
    assert node.bbox == actual
    assert '<text' in i.to_svg(node,text='embed')


def test_ink_bounds_handle_halos_blank_text_and_invalid_modes():
    plain=i.text('d',bounds='ink')
    halo=i.text('d',bounds='ink',halo=.4)
    assert halo.bbox.width == pytest.approx(plain.bbox.width+.4)
    assert halo.bbox.height == pytest.approx(plain.bbox.height+.4)
    assert i.text('   ',bounds='ink').bbox == i.text('   ').bbox
    with pytest.raises(ValueError,match='bounds'):i.text('d',bounds='optical')
