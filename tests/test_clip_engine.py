"""Clipping geometry and rendered coverage, independently sampled in SVG/PDF."""
import math
import pytest

import inklet as i
from inklet.core import Affine, Diagram, Envelope, PathPrim, Rect, RectPrim, Style, Subpath, Vec2, flatten
from inklet.draw.bezier_clip import roots
from inklet.links.curves import at
from test_hatch_engine import previews, pixel


def cubic(controls):
    # Deliberately sparse measurement data must not hide a curve excursion.
    controls = tuple(Vec2(*p) for p in controls)
    return Diagram(prim=PathPrim((Subpath((controls[0], controls[-1]), curves=(controls,)),)),
                   style=Style(stroke='blue', stroke_width=.4, fill='none'))


@pytest.mark.parametrize('transform', [Affine(), Affine.rotation(31) @ Affine.scaling(2,.7),
                                      Affine(a=-1,b=.3,c=.4,d=1.2,e=8,f=-4)])
def test_clipped_cubic_retains_exact_subcurve_under_transforms(transform):
    node=cubic(((-12,0),(-4,18),(4,-18),(12,0))).placed(transform)
    region=Rect(-5,-5,5,5)
    cut=i.clip(node,region)
    items=flatten(cut)
    assert items
    for item in items:
        for sub in item.prim.subpaths:
            assert sub.curves
            for curve in sub.curves:
                for k in range(101):
                    p=item.world.apply(at(curve,k/100))
                    assert -5-1e-8 <= p.x <= 5+1e-8
                    assert -5-1e-8 <= p.y <= 5+1e-8
    assert 'C ' in i.to_svg(cut, compact=False) or 'c' in i.to_svg(cut)
    assert b' c\n' in i.to_pdf(cut, compress=False)


def test_curve_excursion_is_not_rejected_by_sparse_envelope():
    node=cubic(((0,0),(0,20),(10,20),(10,0)))
    cut=i.clip(node,Rect(-1,10,11,16))
    assert not cut.is_empty
    subs=flatten(cut)[0].prim.subpaths
    assert len(subs)==1 and subs[0].curves
    assert max(p.y for p in subs[0].points)==pytest.approx(15,abs=1e-4)


def test_three_boundary_crossings_remain_separate_runs():
    # x(t)=(t-.2)(t-.5)(t-.8), represented in Bernstein form.
    node=cubic(((-.08,0),(.14,1/3),(-.14,2/3),(.08,1)))
    cut=i.clip(node,Rect(0,-1,1,2))
    subs=flatten(cut)[0].prim.subpaths
    assert len(subs)==2
    for sub, expected in zip(subs, ((.2,.5),(.8,1))):
        assert (sub.points[0].y,sub.points[-1].y)==pytest.approx(expected)


@pytest.mark.parametrize('values,expected', [((-.08,.14,-.14,.08),(.2,.5,.8)),
    ((1,1,1,1),()), ((0,0,0,0),()), ((-.5,-1/6,1/6,.5),(.5,)),
    ((.25,-1/12,-1/12,.25),(.5,)), ((0,1/3,2/3,1),(0,))])
def test_boundary_roots_include_tangencies_and_degenerate_cubics(values,expected):
    assert roots(values)==pytest.approx(expected,abs=1e-7)


@pytest.mark.parametrize('region',[Rect(0,0,0,1),[(0,0),(1,1),(2,2)],
                                  [(0,0),(1,0),(float('nan'),1)]])
def test_invalid_windows_fail_before_export(region):
    with pytest.raises(ValueError):i.window([],region)


def test_windows_reserve_layout_and_preserve_handles_with_resolved_visibility():
    child=i.marker('circle',8).translated(6,0)
    window=i.window(child,Rect(-5,-5,5,5)).rotated(30)
    assert child in list(window.walk())
    item=flatten(window)[0]
    placement=i.resolve(window)[child.id]
    inside=Affine.rotation(30).apply(Vec2(4,0));outside=Affine.rotation(30).apply(Vec2(7,0))
    for resolved in (item,placement):
        assert resolved.visible_at(inside)
        assert not resolved.visible_at(outside)
    assert i.window([],Rect(-5,-3,5,3)).bbox==Rect(-5,-3,5,3)
    assert i.window([],Rect(-5,-3,5,3)).local_trace.hits(Vec2(0,0),Vec2(1,0))==(-5.,5.)


def surround(node):
    return Diagram(children=(node,), envelope_override=Envelope.from_rect(Rect(-15,-12,15,12)))


@pytest.mark.parametrize('transform',[Affine(),Affine.rotation(24) @ Affine.scaling(1.2,.8),
                                      Affine(a=-1,b=.2,c=.3,d=1,e=0,f=0)])
@pytest.mark.parametrize('content',['marker','text','image','rounded','hole'])
def test_window_clips_complete_paints_in_both_backends(content,transform,tmp_path):
    if content=='marker':
        node=i.marker('circle',20,fill='blue',stroke='none')
    elif content=='text':
        node=i.text('MMMMMMMM',size=12,fill='blue',halo=1,halo_color='red')
    elif content=='image':
        from PIL import Image
        image=tmp_path/'blue.png';Image.new('RGB',(20,20),'blue').save(image)
        node=i.asset(image,width=20,cutout=None)
    elif content=='rounded':
        node=Diagram(prim=RectPrim(20,16,4),style=Style(fill='blue',stroke='red',stroke_width=3))
    else:
        outer=Rect(-10,-8,10,8).corners;inner=Rect(-2,-2,2,2).corners
        node=Diagram(prim=PathPrim((Subpath(outer,True),Subpath(inner,True)),True,'evenodd'),
                     style=Style(fill='blue',stroke='none'))
    scene=surround(i.window(node,Rect(-5,-5,5,5)).placed(transform))
    for image in previews(scene,tmp_path):
        for p in (Vec2(7,0),Vec2(-7,0),Vec2(0,7),Vec2(0,-7)):
            assert image.getpixel(pixel(scene,transform.apply(p)))==(255,255,255)
        if content!='text':
            expected=(255,255,255) if content=='hole' else (0,0,255)
            assert image.getpixel(pixel(scene,transform.apply(Vec2(0,0))))==expected


def test_nested_convex_windows_and_opacity_do_not_leak_into_siblings(tmp_path):
    shape=Diagram(prim=RectPrim(24,20),style=Style(fill='blue',stroke='none'))
    triangle=[(-6,-6),(6,-6),(0,6)]
    crop=i.window(i.window(shape,Rect(-4,-4,4,4)),triangle,opacity=.5)
    sibling=Diagram(prim=RectPrim(2,2),style=Style(fill='red',stroke='none')).translated(9,0)
    scene=surround(Diagram(children=(crop,sibling)))
    for image in previews(scene,tmp_path):
        for p,expected in [(Vec2(0,0),(128,128,255)),(Vec2(3,3),(255,255,255)),
                           (Vec2(0,-5),(255,255,255)),(Vec2(9,0),(255,0,0))]:
            assert max(abs(a-b) for a,b in zip(image.getpixel(pixel(scene,p)),expected))<=2


def test_window_painted_bounds_agree_with_cached_analysis():
    from inklet.render.bounds import painted_bounds
    from inklet.render.analysis import CompositingAnalysis
    node=i.window(Diagram(prim=RectPrim(100,100),style=Style(fill='blue')),Rect(-4,-3,4,3))
    assert painted_bounds(node,Affine(),Style())==Rect(-4,-3,4,3)
    assert CompositingAnalysis().bounds(node,Affine(),Style())==Rect(-4,-3,4,3)

@pytest.mark.parametrize('rule',['evenodd','nonzero'])
@pytest.mark.parametrize('same_winding',[True,False])
def test_geometric_ring_clipping_matches_visual_window(rule,same_winding,tmp_path):
    outer=Rect(-10,-8,10,8).corners
    inner=Rect(-4,-4,4,4).corners
    if not same_winding:inner=inner[::-1]
    shape=Diagram(prim=PathPrim((Subpath(outer,True),Subpath(inner,True)),True,rule),
                  style=Style(fill='blue',stroke='none'))
    region=Rect(-2,-6,8,6)
    geo=previews(surround(i.clip(shape,region)),tmp_path)
    visual=previews(surround(i.window(shape,region)),tmp_path)
    for a,b in zip(geo,visual):
        for x in (-1,0,2,5,7):
            for y in (-5,-3,0,3,5):
                xy=pixel(surround(i.window(shape,region)),Vec2(x,y))
                assert a.getpixel(xy)==b.getpixel(xy)


def test_open_cubic_matches_original_parameterization():
    node=cubic(((-1,0),(-1/3,3),(1/3,-3),(1,0)))
    original=node.prim.subpaths[0].curves[0]
    cut=i.clip(node,Rect(-.4,-10,.6,10))
    for item in flatten(cut):
        for sub in item.prim.subpaths:
            for curve in sub.curves:
                for k in range(101):
                    p=at(curve,k/100)
                    reference=at(original,(p.x+1)/2)
                    assert (p-reference).length<1e-12


def test_dense_segment_optimization_matches_scalar_reference():
    import random
    from inklet.draw.clip import _region,_segment,clip_polyline
    rng=random.Random(8193)
    edges,_=_region([(-4,-2),(3,-5),(6,2),(-1,7)])
    for _ in range(2000):
        a,b=(Vec2(rng.uniform(-10,10),rng.uniform(-10,10)) for _ in range(2))
        reference=_segment(a,b,edges)
        result=clip_polyline((a,b),edges)
        if reference is None:assert result==[]
        else:
            assert len(result)==1
            for actual,expected in zip(result[0],reference):assert (actual-expected).length<1e-12


def test_compiled_document_retains_windows_and_checks_visible_bounds():
    node=i.window(i.text('A very long title extending beyond the page',size=10),Rect(-10,-5,10,5))
    assert node.copy().clip_region==node.clip_region
    doc=i.document(width=40);doc.add('crop',node)
    compiled=doc.compile()
    assert any(n.clip_region for n in compiled.root.walk())
    assert 'clipPath' in compiled.to_svg()
    assert b'W\nn' in i.to_pdf(compiled.root,compress=False)
    assert not any(d.code=='OFF_CANVAS' for d in compiled.diagnostics)


def test_lint_does_not_report_hidden_stroke_crossings():
    # Use the public linter for the full drawing; a hidden stroke over the
    # separate word must not be reported as a visible crossing.
    stroke=i.polyline([(-20,0),(20,0)],stroke='black',stroke_width=.3)
    cropped=i.window(stroke,Rect(-5,-5,5,5))
    label=i.text('word',size=3).translated(14,0)
    doc=i.document(width=70);doc.add('scene',Diagram(children=(cropped,label)))
    compiled=doc.compile()
    assert not any(d.code=='PATH_CROSSES' for d in compiled.diagnostics)


def test_lint_trace_retains_coincident_window_and_shape_boundaries():
    from inklet.diagnostics.rules import Item, _outline
    shape=Diagram(prim=RectPrim(10,10))
    item=Item(shape.id,shape,shape.prim,Affine(),Style(),Rect(-5,-5,5,5),1,0,
              clip_regions=(Rect(-5,-5,5,5).corners,))
    assert _outline(item).hits(Vec2(0,0),Vec2(1,0))==(-5.,5.)


def test_collapsed_window_is_not_visible_or_a_lint_error():
    node=i.window(i.marker('circle',4),Rect(-5,-5,5,5)).placed(Affine.scaling(0,1))
    assert not flatten(node)[0].visible_at(Vec2(0,0))
    doc=i.document(width=40);doc.add('collapsed',surround(node))
    compiled=doc.compile()
    assert not any(d.code=='OFF_CANVAS' for d in compiled.diagnostics)
