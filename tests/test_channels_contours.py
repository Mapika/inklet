"""Display arithmetic, registration and exact label boundary contracts."""
import io
import json
import math
from pathlib import Path
import re

import pytest
np=pytest.importorskip('numpy')
pytest.importorskip('scipy')
from PIL import Image
import inklet as i
from inklet.core import PathPrim, flatten
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane,SampledSection
from inklet.experimental.slabs import Slab
from inklet.experimental.channels import Channel,Composite


def section(data, *, valid=None,kind='intensity',spacing=(1,1),centre=(0,0,0)):
    data=np.asarray(data)
    plane=Plane(centre,(1,0,0),(0,1,0),data.shape,spacing,'um')
    volume=Volume(data[None],(1,*spacing),'um',source_id='test')
    return SampledSection(plane,volume,kind,data,np.ones(data.shape,dtype=bool) if valid is None else valid)


def test_additive_channel_windowing_weight_and_clipping_are_explicit():
    a=Channel('a',section([[0,5,10,20]]),'red',(0,10))
    b=Channel('b',section([[5,10,20,20]]),'#f00',(0,10),.5)
    merged=Composite((a,b),coverage='intersection')
    assert merged.rgba[0].tolist()==[[64,0,0,255],[255,0,0,255],[255,0,0,255],[255,0,0,255]]
    assert merged.report()['rgb_clipped_pixels']==2
    assert a.report()['above_window']==1 and b.report()['above_window']==2
    assert np.array_equal(merged.rgba,Composite((b,a),coverage='intersection').rgba)
    assert a.sampled.data[0,-1]==20
    rgba=np.array(Image.open(io.BytesIO(merged.diagram(width=40).prim.data)))
    np.testing.assert_array_equal(rgba,merged.rgba)
    json.dumps(merged.report(),allow_nan=False)
    for array in (merged.rgba,merged.valid,merged.channel_counts):
        with pytest.raises(ValueError):array.setflags(write=True)


def test_missing_channel_policy_never_treats_unavailable_data_as_measured_black():
    a=Channel('a',section([[1,1,1]],valid=np.array([[True,True,False]])),'red',(0,1))
    b=Channel('b',section([[1,1,1]],valid=np.array([[True,False,False]])),'blue',(0,1))
    strict=Composite((a,b),coverage='intersection')
    union=Composite((a,b),coverage='union')
    assert strict.rgba[0].tolist()==[[255,0,255,255],[0,0,0,0],[0,0,0,0]]
    assert union.rgba[0].tolist()==[[255,0,255,255],[255,0,0,255],[0,0,0,0]]
    assert union.channel_counts.tolist()==[[2,1,0]]
    assert strict.report()['partial_pixels']==1 and union.report()['valid_pixels']==2
    assert b.report()['valid_pixels']==1


@pytest.mark.parametrize('change',[
    dict(name=''),dict(color='not-a-color'),dict(window=(1,1)),dict(window=(0,math.inf)),
    dict(window=(0,1,2)),dict(weight=0),dict(weight=2),dict(weight=math.nan)])
def test_invalid_channel_display_metadata_is_rejected(change):
    args=dict(name='signal',sampled=section([[1]]),color='red',window=(0,2))
    with pytest.raises(ValueError):Channel(**(args|change))


def test_composites_reject_registration_mismatch_and_label_images():
    s=section([[1,2],[3,4]])
    a=Channel('a',s,'red',(0,4))
    shifted=Channel('b',section([[1,2],[3,4]],centre=(.1,0,0)),'blue',(0,4))
    with pytest.raises(ValueError,match='geometry'):Composite((a,shifted),coverage='union')
    with pytest.raises(ValueError,match='unique'):Composite((a,a),coverage='union')
    with pytest.raises(ValueError,match='coverage'):Composite((a,),coverage='auto')
    with pytest.raises(ValueError,match='at least'):Composite((),coverage='union')
    with pytest.raises(ValueError,match='label'):Channel('labels',section([[1]],kind='labels'),'red',(0,2))
    slab=Slab(s.plane,1,3)
    p=Channel('b',s.volume.project_slab(slab,reduction='max'),'blue',(0,4))
    with pytest.raises(ValueError,match='geometry'):Composite((a,p),coverage='union')
    q=Channel('c',s.volume.project_slab(Slab(s.plane,2,3),reduction='max'),'blue',(0,4))
    with pytest.raises(ValueError,match='geometry'):Composite((p,q),coverage='union')
    assert Composite((p,),coverage='intersection').rgba.shape==(2,2,4)


def test_single_pixel_contour_has_exact_edges_and_calibrated_lengths():
    data=np.zeros((3,3),dtype='uint64');data[1,1]=2**63+3
    contour=section(data,kind='labels',spacing=(2,3)).contours(2**63+3)
    r=contour.report()
    assert r['observed_length']==10 and r['coverage_length']==0
    assert r['area']['area']==6 and r['label']==2**63+3
    segments=contour.world_segments()
    assert len(segments)==4
    assert {p for pair in segments for p in pair}=={(-1.5,-1.,0.),(-1.5,1.,0.),(1.5,-1.,0.),(1.5,1.,0.)}
    diagram=contour.diagram(width=90,stroke='red')
    prims=[item.prim for item in flatten(diagram) if isinstance(item.prim,PathPrim)]
    assert len(prims)==1 and len(prims[0].subpaths)==4
    svg=i.to_svg(diagram)
    assert '<image' not in svg and '<path' in svg
    assert i.to_pdf(diagram).startswith(b'%PDF')
    assert data[1,1]==2**63+3


def test_holes_diagonal_contacts_and_absent_ids_retain_pixel_edge_geometry():
    data=np.zeros((5,5),dtype='uint8');data[1:4,1:4]=7;data[2,2]=0
    contour=section(data,kind='labels').contours(7)
    assert contour.report()['area']['area']==8
    assert contour.report()['observed_length']==16
    assert contour.report()['coverage_segments']==0
    data[:]=0;data[1,1]=7;data[2,2]=7
    diagonal=section(data,kind='labels').contours(7)
    assert diagonal.report()['observed_length']==8
    absent=section(data,kind='labels').contours(19)
    assert absent.observed_yx==absent.coverage_yx==()
    assert absent.report()['area']['area']==0
    assert absent.diagram(width=50,stroke='red').width==50


def test_coverage_edges_are_separate_at_invalid_pixels_and_image_extent():
    valid=np.array([[True,True,False],[True,True,False]])
    contour=section(np.ones((2,3),dtype='uint8'),kind='labels',valid=valid).contours(1)
    assert contour.observed_yx==()
    assert contour.report()['coverage_length']==8
    assert contour.world_segments()==()
    assert len(contour.world_segments(include_coverage=True))==4
    omitted=contour.diagram(width=30,stroke='red')
    dashed=contour.diagram(width=30,stroke='red',coverage='dash')
    assert not any(isinstance(p.prim,PathPrim) for p in flatten(omitted))
    assert 'stroke-dasharray' in i.to_svg(dashed)
    background=section(np.zeros((2,3),dtype='uint8'),kind='labels',valid=valid).contours(0)
    assert background.report()['area']['sampled_pixels']==4
    assert background.report()['coverage_length']==8


@pytest.mark.parametrize('factor',[1e-9,1,1e9])
def test_contour_page_coordinates_survive_physical_unit_scaling(factor):
    data=np.zeros((3,3),dtype='uint8');data[1,1]=1
    c=section(data,kind='labels',spacing=(2*factor,3*factor)).contours(1)
    assert c.report()['observed_length']==pytest.approx(10*factor,abs=0)
    points=[c.section.plane.project(p,width=90) for edge in c.world_segments() for p in edge]
    assert {(round(p.x,8),round(p.y,8)) for p in points}=={(-15,-10),(-15,10),(15,-10),(15,10)}


def test_contour_validation():
    with pytest.raises(ValueError,match='label'):section([[1]]).contours(1)
    s=section([[1]],kind='labels')
    for label in (-1,True,1.5):
        with pytest.raises(ValueError):s.contours(label)
    with pytest.raises(ValueError,match='coverage'):s.contours(1).diagram(width=20,stroke='red',coverage='close')


def test_documented_channels_and_contours_workflow():
    path=Path(__file__).resolve().parents[1]/'docs/channels-and-contours.md'
    namespace={}
    for source in re.findall(r'```python\n(.*?)```',path.read_text(),flags=re.S):
        exec(compile(source,str(path),'exec'),namespace)
    assert namespace['contour'].report()['area']['area']>0
    assert not any(d.severity=='error' for d in namespace['figure'].diagnostics)


def test_offcentre_contour_stays_registered_with_an_oblique_image():
    data=np.zeros((5,7),dtype='uint8');data[1,5]=3
    plane=Plane((10,20,30),(1,1,0),(-1,1,2),(5,7),(2,3),'um')
    source=Volume(data[None],(1,2,3),'um',source_id='off-centre')
    contour=SampledSection(plane,source,'labels',data,np.ones(data.shape,dtype=bool)).contours(3)
    width=84
    diagram=i.overlay([contour.section.diagram(width=width,window=(0,3)),
                       contour.diagram(width=width,stroke='red')],align='origin')
    # The image's drawn origin survives overlay; compare vectors in that frame.
    origin=diagram.transform.apply(diagram.anchors['origin'])
    points=[]
    for item in flatten(diagram):
        if isinstance(item.prim,PathPrim):
            points.extend(item.world.apply(p)-origin for sub in item.prim.subpaths for p in sub.points)
    expected=[plane.project(p,width=width) for edge in contour.world_segments() for p in edge]
    np.testing.assert_allclose([(p.x,p.y) for p in points],[(p.x,p.y) for p in expected],atol=1e-12)
