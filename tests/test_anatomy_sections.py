import pytest
import inklet as i
from inklet.three.solids import cube
from inklet.three.section import SurfaceVisibility


def test_section_keeps_triangle_groups_and_registered_path_intersections():
    mesh=cube(2).grouped('tissue');cut=mesh.clipped((1,0,0),0)
    assert cut.faces and all(p.x>=0 for p in cut.vertices)
    assert set(cut.groups)=={'tissue'} and any(p.x<0 for p in mesh.vertices)
    a=i.anatomy_view(mesh,width=40,height=30).surface('tissue',mesh).paths('arbor',[[(-2,0,0),(2,0,0)]]).markers('sites',[(-1,0,0),(1,0,0)])
    section=a.cut((1,0,0))
    assert section.view==a.view
    assert section._layers[1][2][0][0].x==0
    assert len(section._layers[2][2])==1
    assert a._layers[1][2][0][0].x==-2
    assert '<image' not in i.to_svg(section.build(),text='embed')


def test_opaque_visibility_splits_a_path_at_surface_piercing():
    # Explicit camera facing +z. A path crosses a frontal triangle at z=0.
    from inklet.three import View,Vec3
    view=View(Vec3(0,0,-10),Vec3(1,0,0),Vec3(0,-1,0),Vec3(0,0,1))
    mesh=i.Mesh.from_arrays([(-5,-5,0),(5,-5,0),(0,5,0)],[(0,1,2)])
    visibility=SurfaceVisibility(mesh,view)
    runs=visibility.paths([(Vec3(-1,0,-1),Vec3(1,0,1))])
    assert runs and runs[-1][1].z==pytest.approx(0)
    assert visibility.visible_point(Vec3(0,0,-1))
    assert not visibility.visible_point(Vec3(0,0,1))


def test_occluded_anatomy_requires_shared_opaque_surface_styles():
    a=i.anatomy_view(cube(),width=30,height=30).surface('one',cube(),opacity=.4)
    with pytest.raises(ValueError,match='opaque'):a.build(depth='occluded')
    a.style('one',opacity=1).lighting(levels=12)
    assert a.build(depth='occluded').notes['anatomy_view']['depth']=='occluded'
    with pytest.raises(ValueError):a.lighting(direction=(0,0,0))


@pytest.mark.parametrize('style',[{'style':'wireframe'},{'style':'lineart'},{'cull':True},{'colors':{'x':'red'}}])
def test_occluded_anatomy_rejects_incompatible_surface_treatments(style):
    a=i.anatomy_view(cube(),width=30,height=30).surface('tissue',cube(),**style)
    with pytest.raises(ValueError,match='filled surfaces'):a.build(depth='occluded')
