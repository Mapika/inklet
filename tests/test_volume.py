"""Physical coordinate, surface and image contracts for experimental microscopy."""
from collections import Counter
import io
import json
import math
from pathlib import Path
import re
import pytest

np=pytest.importorskip('numpy')
pytest.importorskip('skimage')
from PIL import Image
from inklet.experimental.volume import Volume, Slice


def volume(data=None):
    if data is None:
        data=np.zeros((6,7,8),dtype='uint16');data[1:4,2:5,3:7]=9
    return Volume(data,(2,3,5),'um',origin_xyz=(10,20,30),source_id='fixture:segmentation')


def test_voxel_counts_centres_units_and_snapshot_are_independent_of_source_edits():
    data=np.ones((2,3,4),dtype='uint8');v=volume(data);data[:]=0
    record=v.measure(1)
    assert record['voxel_count']==24 and record['volume']==720
    assert record['centroid_xyz']==[17.5,23.,31.]
    assert record['touches_boundary'] is True
    with pytest.raises(ValueError):v.data.setflags(write=True)
    assert v.report()['bounds_xyz']==[[7.5,18.5,29.],[27.5,27.5,33.]]
    json.dumps(v.report(),allow_nan=False)


@pytest.mark.parametrize('axis,index,axes,extent',[
    ('z',2,('x','y'),(40,21)),('y',3,('x','z'),(40,12)),('x',4,('y','z'),(21,12))])
def test_orthogonal_slices_keep_anisotropic_extent_and_world_projection(axis,index,axes,extent):
    v=volume();section=v.slice(axis,index)
    assert section.axes==axes and section.extent==extent
    point=[2,3,4];point['zyx'.index(axis)]=index
    at=section.project(v.world(point),width=80)
    # Independent calculation from voxel centres and the physical field edges.
    coordinates=dict(zip('xyz',reversed(point)));counts=dict(zip('xyz',reversed(v.data.shape)))
    expected=[(coordinates[a]+.5-counts[a]/2)*v.spacing_zyx['zyx'.index(a)]*80/extent[0] for a in axes]
    assert (at.x,at.y)==pytest.approx((expected[0],-expected[1]))
    diagram=section.diagram(width=80,window=(0,10))
    assert diagram.height==pytest.approx(80*extent[1]/extent[0])
    assert section.scalebar(10,width=80).children[0].width==pytest.approx(800/extent[0])
    other=list(v.world(point));other['xyz'.index(axis)]+=10
    with pytest.raises(ValueError,match='slab'):section.project(other,width=80)


def test_slice_pixels_match_projected_voxel_centres_without_an_implicit_flip():
    data=np.arange(24,dtype='uint8').reshape(2,3,4)
    v=Volume(data,(1,1,1),'um',source_id='ramp')
    for axis,index in (('x',2),('y',1),('z',0)):
        section=v.slice(axis,index);diagram=section.diagram(width=40,window=(0,255))
        pixels=np.array(Image.open(io.BytesIO(diagram.prim.data)))
        for z,y,x in np.ndindex(data.shape):
            if (z,y,x)['zyx'.index(axis)]!=index:continue
            p=section.project(v.world((z,y,x)),width=40)
            col=int((p.x+diagram.width/2)/diagram.width*pixels.shape[1])
            row=int((p.y+diagram.height/2)/diagram.height*pixels.shape[0])
            assert pixels[row,col]==data[z,y,x]


def test_surface_coordinates_winding_and_closed_edges():
    v=volume();m=v.surface(9)
    vertices=np.array([(p.x,p.y,p.z) for p in m.vertices])
    assert vertices.min(0)==pytest.approx([22.5,24.5,31.])
    assert vertices.max(0)==pytest.approx([42.5,33.5,37.])
    signed=sum(m.vertices[a].dot(m.vertices[b].cross(m.vertices[c])) for a,b,c in m.faces)/6
    assert signed>0
    edges=Counter(tuple(sorted((a,b))) for f in m.faces for a,b in zip(f,(f[1],f[2],f[0])))
    assert set(edges.values())=={2}


def test_clipped_surfaces_require_opt_in_and_stride_keeps_background_at_edges():
    v=volume(np.ones((6,7,8),dtype='uint8'))
    with pytest.raises(ValueError,match='boundary'):v.surface(1)
    for step in (1,2,3):
        m=v.surface(1,allow_clipped=True,step_size=step)
        edges=Counter(tuple(sorted((a,b))) for f in m.faces for a,b in zip(f,(f[1],f[2],f[0])))
        assert set(edges.values())=={2}
    assert v.measure(1)['voxel_count']==336


@pytest.mark.parametrize('change',[dict(spacing_zyx=(1,0,1)),dict(spacing_zyx=(1,2)),
    dict(unit='pixels'),dict(source_id=''),dict(origin_xyz=(0,0,math.nan)),
    dict(data=np.zeros((2,2))),dict(data=np.full((2,2,2),math.inf)),dict(data=np.zeros((0,2,2)))])
def test_invalid_volume_metadata(change):
    options=dict(data=np.ones((2,2,2)),spacing_zyx=(1,1,1),unit='um',source_id='test')|change
    with pytest.raises(ValueError):Volume(**options)


def test_invalid_measurements_and_slice_requests_fail_explicitly():
    v=volume()
    for label in (0,-1,True,1.,100):
        with pytest.raises(ValueError):v.measure(label)
    with pytest.raises(ValueError):volume(np.ones((2,2,2))).measure(1)
    for axis,index in (('q',0),('x',99),('y',True)):
        with pytest.raises(ValueError):Slice(v,axis,index)
    section=v.slice('z',0)
    with pytest.raises(ValueError):section.diagram(width=80,window=(1,1))
    with pytest.raises(ValueError):section.scalebar(100,width=80)
    with pytest.raises(ValueError):v.surface(9,step_size=0)


def test_crop_keeps_world_coordinates_and_detects_new_truncation():
    v=volume();cropped=v.crop((2,1,2),(5,6,8))
    assert cropped.world((0,0,0))==v.world((2,1,2))
    assert cropped.world((1,2,3))==v.world((3,3,5))
    assert cropped.measure(9)['touches_boundary'] and not v.measure(9)['touches_boundary']
    assert cropped.measure(9)['voxel_count']==24
    with pytest.raises(ValueError):v.crop((0,0,0),(8,8,8))
    with pytest.raises(ValueError):v.crop((0,0,0),(0,2,2))


@pytest.mark.parametrize('factor',[1e-15,1,1e9])
def test_slice_slab_tolerance_scales_with_physical_units(factor):
    v=Volume(np.zeros((3,3,3)),(factor,)*3,'m',source_id='unit-test')
    with pytest.raises(ValueError,match='slab'):
        v.slice('z',0).project(v.world((2,1,1)),width=30)
    assert v.slice('z',0).project(v.world((0,1,1)),width=30).x==pytest.approx(0)


def test_documented_volume_workflow_compiles_with_calibrated_measurements():
    page=Path(__file__).resolve().parents[1]/'docs/calibrated-volumes.md'
    namespace={}
    for source in re.findall(r'```python\n(.*?)```',page.read_text(),flags=re.S):
        exec(compile(source,str(page),'exec'),namespace)
    assert namespace['measured']['volume']==pytest.approx(.96)
    assert namespace['mesh'].faces
    assert not any(d.severity=='error' for d in namespace['figure'].diagnostics)
