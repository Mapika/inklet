"""Physical line-reduction error and measured axis typography."""
import math
import random

import pytest
import inklet as i
from inklet.core import PathPrim, TextPrim, Vec2, resolve
from inklet.draw.coords import as_drawn
from inklet.plot.axis import TICK_LABEL_KIND, AXIS_LABEL_KIND
from inklet.plot.simplify import simplify_points


def distance(point,a,b):
    dx,dy=b.x-a.x,b.y-a.y
    length=dx*dx+dy*dy
    t=0 if length==0 else min(1,max(0,((point.x-a.x)*dx+(point.y-a.y)*dy)/length))
    return math.hypot(point.x-a.x-t*dx,point.y-a.y-t*dy)


@pytest.mark.parametrize('case',['wave','spike','loops','duplicates','noise'])
def test_simplification_bounds_error_and_preserves_endpoints_extrema(case):
    rng=random.Random(34)
    points=[]
    for k in range(2200):
        if case=='wave': p=Vec2(k/20,math.sin(k/70)*10)
        elif case=='spike':p=Vec2(k/20,20 if k==1077 else 0)
        elif case=='loops':p=Vec2(math.cos(k/30)*10,math.sin(k/30)*10)
        elif case=='duplicates':p=Vec2(0,0)
        else:p=Vec2(k/20,rng.uniform(-3,3))
        points.append(p)
    original=tuple(points);reduced=simplify_points(original,.025)
    assert original[0]==reduced[0] and original[-1]==reduced[-1]
    for attr in ('x','y'):
        assert min(getattr(p,attr) for p in original)==min(getattr(p,attr) for p in reduced)
        assert max(getattr(p,attr) for p in original)==max(getattr(p,attr) for p in reduced)
    # Match the retained subsequence, including repeated vertices; check every
    # original vertex against the segment that actually replaces its run.
    index=0
    for end in reduced[1:]:
        start=index
        while index<len(original)-1 and (index==start or original[index]!=end):index+=1
        assert max(distance(p,original[start],end) for p in original[start:index+1]) <= .025+1e-8
    assert reduced==simplify_points(original,.025)
    if case in ('wave','spike'):assert len(reduced)<len(original)/10


def test_zero_tolerance_is_exact_and_adversarial_work_retains_detail():
    points=tuple(Vec2(k,(-1)**k) for k in range(5000))
    assert simplify_points(points,0) is points
    assert simplify_points(points,.001)==points


@pytest.mark.parametrize('options',[{'simplify':-1},{'simplify':True},{'simplify':float('nan')},
    {'simplify':float('inf')},{'simplify':.1,'smooth':.5},{'simplify':.1,'closed':True}])
def test_line_rejects_invalid_or_incompatible_reduction(options):
    with pytest.raises(ValueError):i.panel(40,30).line([(0,0),(1,1)],**options)


def test_log_scale_reduction_uses_physical_coordinates_and_records_counts():
    points=[(10**(k/1000),math.sin(k/130)) for k in range(3001)]
    p=i.panel(80,30,x=i.log((1,1000)),y=(-1,1))
    p.line(points,simplify='0.02mm')
    notes=[n.notes['line_simplification'] for n in p.build().walk() if 'line_simplification' in n.notes]
    assert notes and notes[0]['input_points']==3001 and notes[0]['output_points']<300
    drawn=next(place for place in resolve(as_drawn(p.build())).values()
               if isinstance(place.diagram.prim,PathPrim))
    vertices=[drawn.world.apply(q) for q in drawn.diagram.prim.subpaths[0].points]
    for original in p.map(points):
        assert min(distance(original,a,b) for a,b in zip(vertices,vertices[1:])) <= .02+1e-8
    with pytest.raises(ValueError,match='finite'):
        i.panel(40,30).line([(0,0),(1,float('nan'))],simplify=.01)


def labels(node,kind):
    return [p for p in resolve(as_drawn(node)).values()
            if p.diagram.kind==kind and isinstance(p.diagram.prim,TextPrim)]


def test_axis_sizes_are_measured_independently_and_thinned_at_the_drawn_size():
    scale=i.linear((1000,9000),(0,42))
    small=i.axis(scale,label='Response',font_size=2)
    large=i.axis(scale,label='Response',tick_font_size=5,label_font_size=6)
    ticks=labels(large,TICK_LABEL_KIND)
    assert len(ticks)<len(labels(small,TICK_LABEL_KIND))
    assert all(p.diagram.prim.font_size==5 for p in ticks)
    assert labels(large,AXIS_LABEL_KIND)[0].diagram.prim.font_size==6
    for a,b in zip(ticks,ticks[1:]):assert a.bbox.overlap(b.bbox) is None
    name=labels(large,AXIS_LABEL_KIND)[0]
    assert all(name.bbox.overlap(p.bbox) is None for p in ticks)


def test_axis_font_face_matches_independently_shaped_text():
    node=i.axis(i.band(['Wide label']),length=45,thin=False,
                font_family='DejaVu Sans',font_weight='bold',font_style='italic',font_size=4)
    actual=labels(node,TICK_LABEL_KIND)[0]
    expected=i.text('Wide label',font='DejaVu Sans',weight='bold italic',size=4,features={'tnum':True},markup=False)
    assert actual.bbox.width==pytest.approx(expected.width)
    assert actual.bbox.height==pytest.approx(expected.height)


def test_grid_positions_follow_custom_axis_thinning():
    p=i.panel(42,30,x=(1000,9000),y=(0,1))
    options=dict(font_size=5,count=8)
    p.grid(y=False,x_options=options).axis('bottom',**options)
    places=resolve(p.build())
    xs=sorted(place.bbox.center.x for place in places.values() if place.diagram.kind=='gridline')
    ticks=sorted(place.bbox.center.x for place in places.values() if place.diagram.kind=='tick')
    assert xs==pytest.approx(ticks)


def test_colorbar_uses_measured_tick_and_label_sizes():
    node=i.colorbar(i.ramp(['#ffffff','#176b9b']),length=40,label='Intensity',
                    tick_font_size=4,label_font_size=5)
    assert {p.diagram.prim.font_size for p in labels(node,TICK_LABEL_KIND)}=={4}
    assert {p.diagram.prim.font_size for p in labels(node,AXIS_LABEL_KIND)}=={5}


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True])
def test_axis_rejects_invalid_font_sizes(value):
    with pytest.raises(ValueError,match='font sizes'):i.axis(i.linear((0,1)),tick_font_size=value)


def test_live_line_reduction_recomputes_at_the_resized_physical_scale():
    points=[(k/1000,math.sin(k/50)) for k in range(5001)]
    p=i.plot_spec(height=30,x=(0,5),y=(-1.1,1.1)).line(points,simplify=.05)
    doc=i.document(width=50);doc.add('signal',p)
    first=doc.compile();svg=first.to_svg()
    def count(compiled):
        return next(n.notes['line_simplification']['output_points'] for n in compiled.root.walk()
                    if 'line_simplification' in n.notes)
    doc.configure(width=180);second=doc.compile()
    assert count(second)>count(first)
    assert first.to_svg()==svg


def test_simplification_does_not_overflow_squared_large_coordinates():
    points=tuple(Vec2(x*1e200,y*1e200) for x,y in [(0,0),(1,.1),(2,.5),(3,3)])
    assert simplify_points(points,1e197)==points
