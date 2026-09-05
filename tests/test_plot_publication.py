"""Regression coverage for authoring complete multi-panel scientific figures."""
import io
import math
import xml.etree.ElementTree as ET

import pytest
import inklet
from inklet.core import DiagramError, ImagePrim, TextPrim, resolve
from inklet.draw.coords import as_drawn, plot_area


def leaves(node, kind):
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind and p.diagram.prim is not None]


def test_bars_and_histograms_honour_explicit_outline_styles():
    for hist in (False, True):
        p=inklet.panel(30,20,x=(0,3),y=(0,3))
        if hist:p.hist([.5,1.5,2.5],bins=[0,1,2,3],stroke='none')
        else:p.bars([.5,1.5,2.5],[1,2,1],stroke='none')
        assert {q.style.stroke for q in leaves(p.build(),'mark')} == {'none'}
    p=inklet.panel(30,20,x=(0,3),y=(0,3))
    p.bars([1],[[1],[2]],stacked=True,stroke='red',stroke_width=.45)
    for q in leaves(p.build(),'mark'):
        assert q.style.stroke=='red'
        assert q.style.stroke_width==.45


def test_zero_box_radius_survives_theme_and_svg_export():
    f=inklet.figure(width=30)
    f.add(inklet.box(width=10,height=8,pad=0,radius=0))
    svg=ET.fromstring(f.to_svg())
    assert all(float(r.get('rx','0'))==0 for r in svg.findall('.//{http://www.w3.org/2000/svg}rect'))


def test_category_colours_follow_keys_when_a_subset_is_reordered():
    p=inklet.panel(30,20,x=['c','a'],y=(0,3))
    p.bars(['c','a'],[1,2],bar_colors={'a':'red','b':'green','c':'blue'},stroke='none')
    assert [q.style.fill for q in leaves(p.build(),'mark')]==['blue','red']
    with pytest.raises(DiagramError,match='no colour'):
        p.bars(['c'],[1],bar_colors={'a':'red'})
    with pytest.raises(DiagramError,match='single series'):
        p.bars(['c'],[[1],[2]],bar_colors=['red'])


def test_grouped_categories_keep_equal_bar_widths_and_explicit_gaps():
    scale=inklet.grouped_band({'one':['a'], 'two':['b','c']},gap=1,reverse=True)
    p=inklet.panel(40,40,x=(0,1),y=scale)
    p.bars(['a','b','c'],[.3,.5,.8],orient='h',stroke='none')
    p.axis('left')  # A category gap must not be mistaken for a numeric axis break.
    ya,yb,yc=[p.point(0,c).y for c in ['a','b','c']]
    assert ya<yb<yc
    assert yb-ya==pytest.approx(2*(yc-yb))
    assert len({round(q.bbox.height,8) for q in leaves(p.build(),'mark')})==1
    for c in ['a','b','c']:assert p.y.invert(p.y.map(c))==c
    resized=scale.with_range(0,100)
    assert resized.map('a')>resized.map('b')>resized.map('c')
    with pytest.raises(ValueError):inklet.grouped_band([['a'],[]])
    with pytest.raises(ValueError):inklet.grouped_band([['a'],['a']])


def test_stackarea_preserves_nonzero_baseline_and_builds_legend():
    p=inklet.panel(40,30,x=(2,0),y=(0,10))
    p.stackarea([2,1,0],[[1,2,3],[2,2,2]],baseline=[1,1,1],colors=['red','blue'],names=['one','two'])
    marks=leaves(p.build(),'mark')
    assert len(marks)==2
    assert marks[0].bbox.y1==pytest.approx(p.point(0,1).y)
    assert marks[1].bbox.y0==pytest.approx(p.point(0,6).y)
    assert [k.name for k in p.keys]==['one','two']
    with pytest.raises(DiagramError,match='non-negative'):
        p.stackarea([0,1],[[1,-1]])
    with pytest.raises(DiagramError):p.stackarea([0,1],[[1,float('nan')]])
    with pytest.raises(DiagramError):p.stackarea([0,1],[[1]])


@pytest.mark.parametrize('side',['left','right','top','bottom'])
def test_external_zoom_clears_furniture_preserves_type_and_targets_plot_corners(side):
    p=inklet.panel(50,40,x=(0,10),y=(0,10),clip=True);p.axes(x='Long x label',y='Long y label')
    sub=inklet.panel(22,18,x=(8,10),y=(8,10));sub.axes()
    before=as_drawn(p.build()).bbox
    sizes=[n.prim.font_size for n in sub.build().walk() if isinstance(n.prim,TextPrim)]
    p.inset(sub,side=side,width=None,pad=4,plate=False,zoom=(8,10,8,10))
    child=p.build().children[-1]
    if side=='right':assert child.bbox.x0>=before.x1+4-1e-9
    if side=='left':assert child.bbox.x1<=before.x0-4+1e-9
    if side=='top':assert child.bbox.y1<=before.y0-4+1e-9
    if side=='bottom':assert child.bbox.y0>=before.y1+4-1e-9
    assert [n.prim.font_size for n in child.walk() if isinstance(n.prim,TextPrim)]==sizes
    target=plot_area(child)
    assert target.width==pytest.approx(22)
    assert target.height==pytest.approx(18)
    ends=[]
    for n in p.build().children[-3:-1]:
        for q in resolve(n).values():
            if hasattr(q.diagram.prim,'subpaths'):
                ends.extend(q.world.apply(s.points[-1]) for s in q.diagram.prim.subpaths)
    assert len(ends)==2
    for end in ends:assert any((end-c).length<1e-8 for c in target.corners)


def test_explicit_tick_thinning_warns_and_can_be_overridden():
    p=inklet.panel(20,20,x=(0,14),y=(0,1))
    with pytest.warns(UserWarning,match='thin=False'):
        p.axis('bottom',ticks=list(range(15)))
    q=inklet.panel(20,20,x=(0,14),y=(0,1))
    q.axis('bottom',ticks=list(range(15)),thin=False)
    assert len(leaves(q.build(),'tick-label'))==15


@pytest.mark.parametrize('marker',['circle','square','diamond','triangle','star','cross','plus'])
def test_raster_scatter_keeps_data_position_and_vector_axes(marker):
    Image=pytest.importorskip('PIL.Image')
    p=inklet.panel(25.4,25.4,x=(0,10),y=(0,10),clip=True)
    p.scatter([(2,8)],size=2,color='red',marker=marker,raster=True,dpi=100,name='cells')
    p.axes()
    nodes=list(p.build().walk())
    images=[n for n in nodes if isinstance(n.prim,ImagePrim)]
    assert len(images)==1
    assert any(isinstance(n.prim,TextPrim) for n in nodes)
    im=Image.open(io.BytesIO(images[0].prim.data))
    assert im.size==(100,100)
    alpha=im.getchannel('A')
    bbox=alpha.getbbox()
    assert (bbox[0]+bbox[2])/2==pytest.approx(20,abs=2)
    assert (bbox[1]+bbox[3])/2==pytest.approx(20,abs=2)
    assert p.keys[0].name=='cells'


def test_raster_scatter_composites_group_opacity_once_and_clips_edges():
    Image=pytest.importorskip('PIL.Image')
    p=inklet.panel(25.4,25.4,x=(0,10),y=(0,10),clip=True)
    p.scatter([(5,5),(5,5),(-1,5)],size=3,color='blue',stroke='none',opacity=.5,raster=True,dpi=100)
    n=next(n for n in p.build().walk() if isinstance(n.prim,ImagePrim))
    im=Image.open(io.BytesIO(n.prim.data))
    assert im.getpixel((50,50))[3] in (127,128)
    assert n.prim.width==25.4
    assert n.prim.height==25.4
    with pytest.raises(ValueError):p.scatter([(1,1)],raster=True,dpi=0)


def test_external_inset_tracks_later_furniture_and_child_updates_without_drift():
    p = inklet.panel(50, 40, x=(0, 10), y=(0, 10), clip=True)
    sub = inklet.panel(20, 15, x=(8, 10), y=(8, 10))
    sub.line([(8,8),(10,10)])
    p.inset(sub, side='right', width=None, pad=3, plate=False, zoom=(8,10,8,10))
    first = p.build()
    first_x = first.children[-1].bbox.x0
    p.axis('right', label='Later axis label', ticks=[0,5,10])
    after = p.build()
    assert after.children[-1].bbox.x0 > first_x
    assert p.build() is after
    sub.axes(x='Zoom x', y='Zoom y')
    updated = p.build()
    assert updated is not after
    assert updated.children[-1].bbox.height > after.children[-1].bbox.height
    assert p.build() is updated
    assert any(n.kind == 'tick-label' for n in updated.children[-1].walk())


def test_external_inset_rejects_direct_and_indirect_cycles():
    a = inklet.panel(20,20)
    b = inklet.panel(20,20)
    with pytest.raises(ValueError, match='cycle'):
        a.inset(a, side='right')
    a.inset(b, side='right')
    with pytest.raises(ValueError, match='cycle'):
        b.inset(a, side='left')


def test_external_inset_rejects_cycle_through_twin_handle():
    p = inklet.panel(40, 30)
    twin = p.twin_y((0, 2))
    with pytest.raises(ValueError, match="cycle"):
        twin.inset(p, side="right")
