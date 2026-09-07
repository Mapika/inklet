"""Independent numerical and coordinate contracts for oblique microscopy."""
import io
import json
import math
from pathlib import Path
import re

import pytest

np = pytest.importorskip('numpy')
pytest.importorskip('scipy')
from PIL import Image
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane


def test_oblique_interpolation_reproduces_an_affine_world_field():
    z,y,x = np.indices((5,7,9))
    data = 2*(10+5*x)-3*(20+3*y)+.5*(30+2*z)
    volume = Volume(data,(2,3,5),'um',(10,20,30),'affine field')
    plane = Plane((30,29,34),(1,2,0),(-2,1,3),(3,5),(.3,.4),'um')
    section = volume.reslice(plane,kind='intensity')
    assert section.valid.all()
    for row,column in np.ndindex(plane.shape_yx):
        wx,wy,wz = plane.world(row,column)
        assert section.data[row,column] == pytest.approx(2*wx-3*wy+.5*wz,abs=1e-12)
    json.dumps(section.report(),allow_nan=False)


@pytest.mark.parametrize('axis,index', [('x',3),('y',2),('z',1)])
def test_axis_aligned_planes_match_original_slice_pixels_and_projection(axis,index):
    volume = Volume(np.arange(120).reshape(4,5,6),(2,3,5),'um',(10,20,30),'ramp')
    old = volume.slice(axis,index)
    right = tuple(int(a==old.axes[0]) for a in 'xyz')
    up = tuple(int(a==old.axes[1]) for a in 'xyz')
    shape = tuple(volume.data.shape['zyx'.index(a)] for a in old.axes[::-1])
    spacing = tuple(volume.spacing_zyx['zyx'.index(a)] for a in old.axes[::-1])
    centre = [(n-1)/2 for n in volume.data.shape];centre['zyx'.index(axis)] = index
    plane = Plane(volume.world(centre),right,up,shape,spacing,'um')
    section = volume.reslice(plane,kind='labels')
    expected = np.flipud(np.take(volume.data,index,axis='zyx'.index(axis)))
    assert np.array_equal(section.data,expected)
    assert section.valid.all()
    assert plane.extent == old.extent
    pixels = np.array(Image.open(io.BytesIO(section.diagram(width=80,window=(0,255)).prim.data)))
    assert np.array_equal(pixels[:,:,0],expected)
    for row,column in np.ndindex(shape):
        at = plane.world(row,column)
        p,q = plane.project(at,width=80),old.project(at,width=80)
        assert (p.x,p.y) == pytest.approx((q.x,q.y))


def test_integer_intensities_interpolate_without_rounding_and_large_labels_remain_exact():
    intensity = Volume(np.array([[[0,1]]],dtype='uint8'),(1,1,1),'um',source_id='intensity')
    plane = Plane((.5,0,0),(1,0,0),(0,1,0),(1,3),(1,.5),'um')
    assert intensity.reslice(plane,kind='intensity').data[0].tolist() == [0,.5,1]
    labels = Volume(np.array([[[2**63+1,2**63+3]]],dtype='uint64'),(1,1,1),'um',source_id='IDs')
    section = labels.reslice(plane,kind='labels')
    assert section.data.dtype == np.uint64
    assert section.data[0].tolist() == [2**63+1,2**63+3,2**63+3]
    assert section.measure(2**63+3)['area'] == 1


def test_missing_samples_are_transparent_and_excluded_from_background_area():
    volume = Volume(np.zeros((1,2,2),dtype='uint8'),(1,1,1),'um',source_id='background')
    plane = Plane((.5,.5,0),(1,0,0),(0,1,0),(4,4),(1,1),'um')
    section = volume.reslice(plane,kind='labels')
    assert section.valid.sum() == 4
    assert section.data.sum() == 0
    measured = section.measure(0)
    assert measured['sampled_pixels'] == 4 and measured['area'] == 4
    assert measured['valid_area'] == 4
    pixels = np.array(Image.open(io.BytesIO(section.diagram(width=80,window=(0,1)).prim.data)))
    assert np.array_equal(pixels[:,:,3]>0,section.valid)
    with pytest.raises(ValueError):section.valid.setflags(write=True)
    with pytest.raises(ValueError):section.data.setflags(write=True)


def test_edge_hold_stops_at_physical_voxel_edges_for_both_sampling_kinds():
    volume = Volume(np.array([[[7,19]]],dtype='uint16'),(1,1,1),'um',source_id='edges')
    plane = Plane((.5,0,0),(1,0,0),(0,1,0),(1,7),(1,.5),'um')
    for kind in ('intensity','labels'):
        section = volume.reslice(plane,kind=kind)
        assert section.valid[0].tolist() == [False,True,True,True,True,True,False]
        assert section.data[0,1] == 7 and section.data[0,-2] == 19
        assert section.data[0,0] == section.data[0,-1] == 0


@pytest.mark.parametrize('factor',[1e-12,1,1e8])
def test_plane_projection_corners_and_scale_bar_use_physical_units(factor):
    plane = Plane((2*factor,3*factor,4*factor),(0,2,0),(0,0,3),(4,6),(factor,2*factor),'um')
    assert plane.normal_xyz == (1,0,0)
    assert plane.extent == (12*factor,4*factor)
    for corner,expected in zip(plane.corners,[(-60,-20),(60,-20),(60,20),(-60,20)]):
        point = plane.project(corner,width=120)
        assert (point.x,point.y) == pytest.approx(expected)
    assert plane.scalebar(3*factor,width=120).children[0].width == pytest.approx(30)
    with pytest.raises(ValueError,match='plane'):
        plane.project((3*factor,3*factor,4*factor),width=120)
    with pytest.raises(ValueError,match='extent'):
        plane.project(plane.world(100,100),width=120)


@pytest.mark.parametrize('change',[
    dict(right_xyz=(0,0,0)),dict(up_xyz=(1,1,0)),dict(centre_xyz=(0,math.nan,0)),
    dict(shape_yx=(0,1)),dict(shape_yx=(True,2)),dict(shape_yx=(2,)),
    dict(spacing_yx=(1,-1)),dict(spacing_yx=(1,)),dict(unit='px')])
def test_invalid_plane_metadata_is_rejected(change):
    args=dict(centre_xyz=(0,0,0),right_xyz=(1,0,0),up_xyz=(0,1,0),shape_yx=(2,2),spacing_yx=(1,1),unit='um')
    with pytest.raises(ValueError):Plane(**(args|change))


def test_invalid_resampling_requests_fail_before_sampling():
    volume = Volume(np.ones((2,2,2)),(1,1,1),'um',source_id='float')
    plane = Plane((0,0,0),(1,0,0),(0,1,0),(2,2),(1,1),'um')
    with pytest.raises(ValueError,match='integer'):volume.reslice(plane,kind='labels')
    with pytest.raises(ValueError,match='kind'):volume.reslice(plane,kind='cubic')
    other = Plane((0,0,0),(1,0,0),(0,1,0),(2,2),(1,1),'nm')
    with pytest.raises(ValueError,match='unit'):volume.reslice(other,kind='intensity')
    section = volume.reslice(plane,kind='intensity')
    with pytest.raises(ValueError,match='label'):section.measure(1)
    with pytest.raises(ValueError,match='window'):section.diagram(width=80,window=(1,1))


def test_cropping_preserves_sampling_at_shared_world_points():
    volume = Volume(np.arange(6**3).reshape((6,)*3),(2,3,5),'um',(10,20,30),'crop')
    plane = Plane(volume.world((2.2,2.3,2.4)),(1,0,1),(0,1,0),(3,4),(.2,.3),'um')
    cropped = volume.crop((1,1,1),(5,5,5))
    for kind in ('intensity','labels'):
        a,b = volume.reslice(plane,kind=kind),cropped.reslice(plane,kind=kind)
        assert a.valid.all() and b.valid.all()
        assert a.data == pytest.approx(b.data)


def test_documented_oblique_workflow_compiles_and_preserves_label_identity():
    path=Path(__file__).resolve().parents[1]/'docs/oblique-sections.md'
    namespace={}
    for source in re.findall(r'```python\n(.*?)```',path.read_text(),flags=re.S):
        exec(compile(source,str(path),'exec'),namespace)
    assert namespace['area']['area']>0
    assert not any(d.severity=='error' for d in namespace['figure'].diagnostics)
