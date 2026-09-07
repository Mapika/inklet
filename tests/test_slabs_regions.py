"""Numerical contracts for finite slabs and linked physical regions."""
import io
import json
import math
from pathlib import Path
import re

import pytest
np=pytest.importorskip('numpy')
pytest.importorskip('scipy')
from PIL import Image
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane
from inklet.experimental.regions import BoxRegion
from inklet.experimental.slabs import Slab, SlabProjection


def xy(centre=(1,1,1),shape=(3,3),spacing=(1,1),unit='um'):
    return Plane(centre,(1,0,0),(0,1,0),shape,spacing,unit)


@pytest.mark.parametrize('reduction,expected',[('mean',-4),('max',-2),('min',-6)])
def test_midpoint_slabs_match_known_signed_stack_reductions(reduction,expected):
    data=np.broadcast_to(np.array([-6,-4,-2])[:,None,None],(3,3,3))
    volume=Volume(data,(1,1,1),'um',source_id='signed')
    projected=volume.project_slab(Slab(xy(),3,3),reduction=reduction)
    assert projected.data == pytest.approx(expected)
    assert np.all(projected.counts==3)
    assert np.all(projected.coverage==1)
    assert projected.report()['complete_pixels']==9
    for array in (projected.data,projected.counts,projected.coverage,projected.valid):
        with pytest.raises(ValueError):array.setflags(write=True)
    json.dumps(projected.report(),allow_nan=False)


def test_oblique_affine_mean_and_extrema_have_analytic_physical_values():
    z,y,x=np.indices((9,9,9))
    volume=Volume(2*(10+3*x)-(20+2*y)+4*(30+z),(1,2,3),'um',(10,20,30),'affine')
    plane=Plane(volume.world((4,4,4)),(1,1,0),(-1,1,2),(3,4),(.2,.3),'um')
    slab=Slab(plane,2.4,8)
    slope=sum(a*b for a,b in zip((2,-1,4),plane.normal_xyz))
    half=2.4*(.5-.5/8)
    for reduction,extra in [('mean',0),('max',abs(slope)*half),('min',-abs(slope)*half)]:
        result=volume.project_slab(slab,reduction=reduction)
        for row,col in np.ndindex(plane.shape_yx):
            wx,wy,wz=plane.world(row,col)
            assert result.data[row,col]==pytest.approx(2*wx-wy+4*wz+extra)
        assert result.valid.all()


def test_partial_coverage_is_not_zero_padding_and_empty_pixels_are_transparent():
    volume=Volume(np.full((1,2,2),12,dtype='uint8'),(1,1,1),'um',source_id='thin')
    slab=Slab(xy((.5,.5,0),(4,4)),3,3)
    result=volume.project_slab(slab,reduction='mean')
    assert result.valid.sum()==4
    assert np.all(result.data[result.valid]==12)
    assert np.all(result.counts[result.valid]==1)
    assert np.all(result.coverage[result.valid]==1/3)
    assert np.all(result.data[~result.valid]==0)
    rgba=np.array(Image.open(io.BytesIO(result.diagram(width=40,window=(0,24)).prim.data)))
    assert np.array_equal(rgba[:,:,3]>0,result.valid)
    assert result.report()['count_histogram']==[{'count':0,'pixels':12},{'count':1,'pixels':4}]


def test_region_membership_is_world_based_half_open_and_preserves_large_label_ids():
    label=2**63+3
    volume=Volume(np.full((4,5,6),label,dtype='uint64'),(2,3,5),'um',(10,20,30),'labels')
    region=BoxRegion('ROI-1',(15,23,32),(25,29,36),'um')
    measured=region.measure(volume,label=label)
    assert measured['voxel_count']==8 and measured['volume']==240
    assert measured['available_voxel_count']==8
    cropped=volume.crop((1,1,1),(4,4,5))
    assert region.measure(cropped,label=label)['voxel_count']==8
    assert region.measure(volume,label=label+1)['voxel_count']==0
    outside=BoxRegion('outside',(100,100,100),(101,101,101),'um')
    assert outside.measure(volume,label=0)['available_voxel_count']==0
    plane=xy((20,26,32),(5,5),(3,5))
    mask=region.mask(plane)
    assert mask.sum()==4
    for row,col in np.ndindex(plane.shape_yx):
        point=plane.world(row,col)
        assert mask[row,col]==all(a<=p<b for a,p,b in zip(region.lower_xyz,point,region.upper_xyz))
    with pytest.raises(ValueError):mask.setflags(write=True)
    assert region.outline(plane,width=40).notes['selection']['selection_id']=='ROI-1'


def test_region_restricts_each_depth_sample_not_only_central_plane():
    volume=Volume(np.broadcast_to(np.array([2,4,9])[:,None,None],(3,3,3)),(1,1,1),'um',source_id='depth')
    region=BoxRegion('upper',(-1,-1,1.5),(3,3,2.5),'um')
    slab=Slab(xy(),3,3)
    assert not region.mask(slab.plane).any()
    result=volume.project_slab(slab,reduction='mean',region=region)
    assert np.all(result.data==9) and np.all(result.counts==1)
    assert result.report()['selection']==region.report()


def test_plane_box_intersection_clips_oblique_polygon_and_empty_cases():
    region=BoxRegion('cube',(-1,-1,-1),(1,1,1),'um')
    plane=Plane((0,0,0),(1,-1,0),(1,1,-2),(8,8),(1,1),'um')
    points=region.intersection(plane)
    assert len(points)==6
    for point in points:
        assert sum(point)==pytest.approx(0,abs=1e-14)
        assert max(abs(v) for v in point)==pytest.approx(1)
        plane.project(point,width=80)
    tiny=xy((0,0,0),(1,1),(.2,.2))
    assert region.intersection(tiny)==tiny.corners
    disjoint=xy((0,0,2))
    assert region.intersection(disjoint)==()
    outline=region.outline(disjoint,width=60)
    assert outline.width==60 and outline.height==60
    assert len(region.edges)==12


@pytest.mark.parametrize('factor',[1e-9,1,1e9])
def test_linked_region_selection_survives_unit_scale_and_output_resolution(factor):
    region=BoxRegion('fixed',tuple(-factor for _ in range(3)),tuple(factor for _ in range(3)),'um')
    for n,step in ((4,factor),(8,factor/2)):
        plane=xy((0,0,0),(n,n),(step,step))
        assert region.mask(plane).sum()==(n//2)**2
        assert region.mask(plane).sum()*step**2==pytest.approx(4*factor**2,abs=0)
        projected=[plane.project(p,width=80) for p in region.intersection(plane)]
        assert sorted((round(p.x,8),round(p.y,8)) for p in projected)==[(-20,-20),(-20,20),(20,-20),(20,20)]


@pytest.mark.parametrize('thickness,samples',[(0,1),(-1,2),(math.inf,1),(1,0),(1,True),(1,2.5)])
def test_invalid_slab_sampling_is_rejected(thickness,samples):
    with pytest.raises(ValueError):Slab(xy(),thickness,samples)


@pytest.mark.parametrize('args',[
    ('',(-1,-1,-1),(1,1,1),'um'),('r',(0,0,0),(0,1,1),'um'),
    ('r',(0,0,0),(1,1,math.nan),'um'),('r',(0,0,0),(1,1,1),'px')])
def test_invalid_regions_are_rejected(args):
    with pytest.raises(ValueError):BoxRegion(*args)


def test_projection_contracts_reject_invalid_inputs():
    volume=Volume(np.ones((3,3,3)),(1,1,1),'um',source_id='input')
    slab=Slab(xy(),1,1)
    with pytest.raises(ValueError,match='reduction'):volume.project_slab(slab,reduction='labels')
    wrong=BoxRegion('wrong',(0,0,0),(1,1,1),'nm')
    with pytest.raises(ValueError,match='unit'):volume.project_slab(slab,reduction='max',region=wrong)
    with pytest.raises(ValueError,match='unit'):wrong.mask(xy())
    with pytest.raises(ValueError,match='unit'):wrong.measure(volume,label=1)
    with pytest.raises(ValueError,match='counts'):SlabProjection(slab,volume,'mean',np.ones((3,3)),np.full((3,3),2))
    with pytest.raises(ValueError,match='integer'):BoxRegion('r',(0,0,0),(1,1,1),'um').measure(volume,label=1)


def test_documented_slab_and_selection_workflow():
    path=Path(__file__).resolve().parents[1]/'docs/slabs-and-regions.md'
    namespace={}
    for source in re.findall(r'```python\n(.*?)```',path.read_text(),flags=re.S):
        exec(compile(source,str(path),'exec'),namespace)
    assert namespace['measurement']['voxel_count']>0
    assert not any(d.severity=='error' for d in namespace['figure'].diagnostics)


def test_oblique_partial_depth_means_use_each_pixels_own_denominator():
    volume=Volume(np.broadcast_to(np.array([10,30])[:,None,None],(2,3,7)),
                  (1,1,1),'um',source_id='partial-depth oracle')
    plane=Plane((3,1,.5),(1,0,1),(0,1,0),(1,3),(1,math.sqrt(2)),'um')
    result=volume.project_slab(Slab(plane,3*math.sqrt(2),3),reduction='mean')
    # Retained z coordinates: (-.5,.5), (-.5,.5,1.5), (.5,1.5).
    # Edge holding yields intensities (10,20), (10,20,30), (20,30).
    np.testing.assert_array_equal(result.counts,[[2,3,2]])
    np.testing.assert_allclose(result.data,[[15,20,25]])
