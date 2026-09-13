import hashlib
import io
import json

import pytest
import inklet as i
from inklet.core import PathPrim, Rect
from inklet.plot.raster import interpolate_matrix


def test_seamless_keeps_exact_foreground_cells_and_outer_bounds():
    ramp=i.ramp(['#284b63','#f2c14e'])
    kwargs=dict(ramp=ramp,x=[0,1,5],y=[0,3],scale=i.linear((0,1)))
    plain=i.panel(40,30,x=(-1,6),y=(-2,5)).matrix([[0,.4,1],[1,.2,0]],vector='batched',**kwargs).build()
    smooth=i.panel(40,30,x=(-1,6),y=(-2,5)).matrix([[0,.4,1],[1,.2,0]],vector='seamless',**kwargs).build()
    assert plain.bbox==smooth.bbox
    shapes=lambda d:[n.prim for n in d.walk() if n.kind=='mark']
    assert shapes(plain)==shapes(smooth)
    assert any(n.kind=='matrix-underpaint' for n in smooth.walk())
    assert all(len(n.prim.subpaths)<=512 for n in smooth.walk() if isinstance(n.prim,PathPrim))
    assert '<image' not in i.to_svg(smooth)
    with pytest.raises(ValueError,match='opaque'):
        i.panel(20,20).matrix([[0,1]],ramp=ramp,vector='seamless',opacity=.5)


def test_seamless_uniform_field_has_no_white_grid_pixels():
    Image=pytest.importorskip('PIL.Image')
    pytest.importorskip('resvg_py')
    p=i.panel(31.7,23.1).matrix([[.5]*23 for _ in range(19)],
                                ramp=i.ramp(['#204060','#204060']),vector='seamless')
    img=Image.open(io.BytesIO(i.to_png(p.build(),dpi=137,background='white'))).convert('RGB')
    pixels=[img.getpixel((x,y)) for y in range(3,img.height-3) for x in range(3,img.width-3)]
    assert max(max(abs(c-t) for c,t in zip(rgb,(32,64,96))) for rgb in pixels)<=1


def test_scalar_interpolation_precedes_color_mapping_and_preserves_missing():
    grid,x,y=interpolate_matrix([[0,10],[20,30]],[-1,1],[-1,1],2)
    assert grid[0]==[0,2.5,7.5,10]
    assert grid[1]==[5,7.5,12.5,15]
    assert x==y==[-1.5,-.5,.5,1.5]
    missing,_,_=interpolate_matrix([[None,10],[20,30]],[-1,1],[-1,1],2)
    assert missing[0][0] is None and missing[-1][-1]==30
    with pytest.raises(ValueError,match='evenly'):
        interpolate_matrix([[1,2,3]],[-2,0,1],[1],2)
    with pytest.raises(ValueError,match='raster=True'):
        i.panel(10,10).matrix([[0,1]],ramp=i.ramp(['black','white']),interpolation='linear')
    p=i.panel(10,10).matrix([[0,1]],ramp=i.ramp(['black','white']),interpolation='linear',raster=True)
    assert '<image' in i.to_svg(p.build())


def test_placement_ignores_asymmetric_furniture():
    p=i.panel(30,20).axes(y='A long label').line([(0,0),(1,1)],name='series').legend(side='right')
    original=p.build()
    placed=p.placed('12mm','17mm')
    assert i.plot_area(placed)==Rect(12,17,42,37)
    assert p.build() is original


def test_guide_uses_displayed_log_angle_and_rejects_invalid_positions():
    p=i.panel(60,30,x=i.log((1,100)),y=i.log((1,100)))
    p.guide((1,1),(100,100),label='guide',offset=0,label_style={'size':2})
    label=p._over[-1]
    assert label.bbox.center.x==pytest.approx(0)
    assert label.bbox.center.y==pytest.approx(0)
    # Displayed slope is -30/60, not a 45-degree data-space guess.
    assert label.transform.b/label.transform.a==pytest.approx(-.5)
    with pytest.raises(ValueError):p.guide((1,1),(1,1))
    with pytest.raises(ValueError):p.guide((1,1),(100,100),at=2)


def test_column_major_legend_and_independent_gaps():
    entries=[(str(n),'black') for n in range(5)]
    a=i.legend(entries,columns=2,order='column',col_gap=5,row_gap=2)
    b=i.legend(entries,columns=2,order='column',col_gap=10,row_gap=2)
    assert b.width-a.width==pytest.approx(5)
    text={p.diagram.prim.text:p.bbox.center for p in i.resolve(a).values()
          if getattr(p.diagram.prim,'text',None) in {'0','1','2','3','4'}}
    assert text['0'].y==pytest.approx(text['3'].y)
    assert text['1'].y==pytest.approx(text['4'].y)
    assert text['2'].y>text['1'].y
    with pytest.raises(ValueError):i.legend(entries,order='unknown')


def test_inset_colorbar_stays_inside_plot():
    p=i.panel(60,40).matrix([[0,1]],ramp=i.ramp(['black','white']))
    p.colorbar(corner='sw',length=10,thickness=1,pad=2,plate=True,ticks=[0,1])
    box=p._over[-1].bbox
    assert box.x0>=p.area.x0 and box.x1<=p.area.x1
    assert box.y0>=p.area.y0 and box.y1<=p.area.y1
    with pytest.raises(ValueError,match='does not fit'):
        p.colorbar(corner='sw',length=100)


def test_colorbar_plate_does_not_repaint_its_text_or_cover_the_gradient():
    p=i.panel(60,40).colorbar(source=i.ramp(['black','white']),corner='sw',
                             length=12,title='Key',plate=True,ticks=[0,1])
    resolved=i.resolve(p.build())
    for item in resolved.values():
        if item.diagram.kind in ('label','tick-label'):
            assert item.style.fill!='#ffffff'
        if item.diagram.kind=='spine':
            assert item.style.fill=='none'
    assert any(n.diagram.kind=='colorband' for n in resolved.values())


@pytest.mark.parametrize('mode',[{'raster':False,'overlap':0},{'raster':True},{'vector':'seamless'}])
def test_single_cell_uses_panel_extent_or_explicit_edges(mode):
    ramp=i.ramp(['black','white'])
    p=i.panel(20,10).matrix([[.5]],ramp=ramp,**mode)
    assert p.build().width==pytest.approx(20)
    assert p.build().height==pytest.approx(10)
    q=i.panel(20,10,x=(0,10),y=(0,10)).matrix([[.5]],ramp=ramp,x=[2,4],y=[3,7],**mode)
    assert q.build().width==pytest.approx(4)
    assert q.build().height==pytest.approx(4)


def test_review_bundle_verifies_sources_and_keeps_reference_separate(tmp_path):
    pytest.importorskip('resvg_py')
    source=tmp_path/'data.csv';source.write_text('x,y\n0,1\n')
    panel=i.panel(20,20).line([(0,0),(1,1)]).placed(5,6)
    review=i.review_figure(panel,rules=[])
    reference=tmp_path/'original.png';reference.write_bytes(i.to_png(panel))
    result=review.save_bundle(tmp_path/'bundle',reference=reference,
        sources=[{'path':source,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],
        panels={'a':panel},reference_regions={'a':(0,0,1,1)},caption='<reference>')
    manifest=json.loads(result['manifest'].read_text())
    assert manifest['panels']['a']['data']==[5,6,25,26]
    assert manifest['embedded_images']==0 and manifest['reference']['file']=='reference.png'
    assert (tmp_path/'bundle/reference.png').read_bytes()==reference.read_bytes()
    assert '&lt;reference&gt;' in result['review'].read_text()
    assert manifest['reference_regions']=={'a':[0,0,1,1]}
    assert 'focusPanel' in result['review'].read_text()
    with pytest.raises(ValueError,match='reference regions'):
        review.save_bundle(tmp_path/'bad-region',reference=reference,panels={'a':panel},
                           reference_regions={'a':[-1,0,1,1]})
    with pytest.raises(ValueError,match='hash mismatch'):
        review.save_bundle(tmp_path/'bad',sources=[{'path':source,'sha256':'wrong'}])
    assert not (tmp_path/'bad').exists()
