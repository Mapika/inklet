"""Contracts for reusable complex-figure authoring components."""
import math
import pytest
import inklet as i
from inklet.core import DiagramError, TextPrim, Rect
from inklet.three import Camera
from inklet.three.solids import cube


def test_mosaic_rectangular_spans_and_rebuild_preserve_font_size():
    calls=[]
    def chart(w,h):
        calls.append((w,h))
        return i.panel(w,h,x=(0,1),y=(0,100)).line([(0,20),(1,80)]).axes(x='time',y='long axis title')
    result=i.panel_mosaic(['A A B','C D B'],{'A':chart,'B':i.tag('key'),'C':i.tag('counts'),'D':i.tag('anatomy')},width=140,height=90)
    records=result.notes['panel_mosaic']
    assert records['A']['builds']>1
    assert records['B']['slot'][3] == 86
    for row in records.values():
        a,b=row['slot'],row['content']
        assert a[0]<=b[0]<=b[2]<=a[2]+1e-6 and a[1]<=b[1]<=b[3]<=a[3]+1e-6
    assert result.width==140 and result.height==90
    assert len(calls)>1
    # Factory dimensions change; fixed title typography does not scale.
    labels=[p for p in i.resolve(result).values() if isinstance(p.diagram.prim,TextPrim) and p.diagram.prim.text=='long axis title']
    assert len(labels)==1
    assert abs(labels[0].world.determinant)==pytest.approx(1)


@pytest.mark.parametrize('layout,items',[(['A B','B A'],{'A':i.text('a'),'B':i.text('b')}),(['A'],{}),(['.'],{})])
def test_mosaic_rejects_ambiguous_layouts(layout,items):
    with pytest.raises(ValueError):i.panel_mosaic(layout,items,width=100,height=60)


def test_mosaic_does_not_shrink_oversize_static_type():
    with pytest.raises(DiagramError,match='factory'):
        i.panel_mosaic(['A'],{'A':i.text('wide label',size=20)},width=20,height=30)


def test_value_table_centers_glyphs_and_preserves_explicit_missing_values():
    table=i.value_table([[1,125.75],[None,2]],headers=['left','long header'],font_size=3,min_cell_width=8,min_cell_height=5)
    assert table.anchor_point('header-0').x==table.anchor_point('cell-1-0').x
    assert table.anchor_point('cell-0-0').y==table.anchor_point('cell-0-1').y
    texts=[v for v in i.resolve(table).values() if isinstance(v.diagram.prim,TextPrim)]
    assert any(v.diagram.prim.text=='—' for v in texts)
    for placed in texts:
        assert any((placed.bbox.center-table.anchor_point(key)).length<1e-8 for key in table.notes['value_table'])
    assert '<text' in i.to_svg(table,text='embed')
    with pytest.raises(ValueError):i.value_table([[1,2]],headers=['one'])
    with pytest.raises(ValueError):i.value_table([[1],[1,2]])


def test_clear_space_uses_segments_not_a_line_bounding_box():
    # A diagonal's bounding box fills the region, but the two corners are free.
    line=i.as_drawn(i.polyline([(0,0),(40,30)],stroke='black',stroke_width=.5))
    key=i.tag('legend',size=2)
    result=i.place_in_clear_space(key,within=Rect(0,0,40,30),avoid=[line],pad=1)
    assert result.bbox.x1==pytest.approx(39)
    assert result.bbox.y0==pytest.approx(1)


def test_clear_space_sees_transformed_filled_shapes_and_does_not_silently_overlap():
    obstacle=i.box('',width=30,height=30,fill='red').translated(15,15)
    with pytest.raises(DiagramError,match='no clear'):
        i.place_in_clear_space(i.tag('key'),within=Rect(0,0,30,30),avoid=[obstacle],pad=0)
    with pytest.raises(DiagramError,match='larger'):
        i.place_in_clear_space(i.text('wide',size=20),within=Rect(0,0,5,5))


def test_panel_automatic_legend_integrates_with_named_series():
    panel=i.panel(60,40).line([(0,0),(1,1)],name='response')
    panel.legend(corner='auto',font_size=2)
    assert any('clear_space' in p.diagram.notes for p in i.resolve(panel.build()).values())


def test_anatomy_zoom_keeps_projection_and_locator_aspect_padding():
    context=i.anatomy_view(cube(2),width=50,height=30,camera='front')
    context.surface('tissue',cube(2),opacity=.3).paths('arbor',[[(-.2,0,0),(.4,0,.1)]],color='red')
    detail=context.zoom([(-.2,0,0),(.4,0,.1)],width=20,height=16,layers=['arbor'])
    window=context.window(detail)
    ratio=context.view.scale/detail.view.scale
    assert window.width==pytest.approx(detail.width*ratio)
    assert window.height==pytest.approx(detail.height*ratio)
    point=i.Vec3(.1,0,.05)
    a=context.view.project(point).point;b=detail.view.project(point).point
    mapped=b*ratio+context.view.offset-detail.view.offset*ratio
    assert (a-mapped).length<1e-8
    assert detail.build().notes['anatomy_view']['layers']==['arbor']
    assert context.build().notes['anatomy_view']['layers']==['tissue','arbor']
    svg=i.to_svg(context.inset([(-.2,0,0),(.4,0,.1)],width=20,height=16,side='right'),text='embed')
    assert '<image' not in svg
    with pytest.raises(ValueError,match='unknown'):context.zoom(cube(),width=10,height=10,layers=['absent'])
    with pytest.raises(ValueError,match='camera'):context.surface('bad',cube(),width=10)


def test_anatomy_rejects_incompatible_locator_and_bad_viewport():
    a=i.anatomy_view(cube(),width=20,height=20)
    b=i.anatomy_view(cube(),width=20,height=20,camera='top')
    with pytest.raises(ValueError,match='camera'):a.window(b)
    with pytest.raises(ValueError):i.anatomy_view(cube(),width=math.inf,height=20)
    with pytest.raises(ValueError):i.anatomy_view(cube(),width=2,height=2,pad=2)


def test_clear_space_respects_item_stroke_and_does_not_mutate_input():
    from inklet.render.bounds import painted_bounds
    thick=i.box('',width=10,height=10,stroke='black',stroke_width=4,stroke_linejoin='round')
    result=i.place_in_clear_space(thick,within=Rect(0,0,20,20),pad=0)
    placed=next(p for p in i.resolve(result).values() if p.diagram is result)
    ink=painted_bounds(result,placed.world,placed.style)
    assert 0<=ink.x0<=ink.x1<=20 and 0<=ink.y0<=ink.y1<=20
    assert 'clear_space' not in thick.notes
    again=i.place_in_clear_space(result,within=Rect(0,0,20,20),pad=0,clearance=2)
    assert result.notes['clear_space']['clearance']==.5
    assert again.notes['clear_space']['clearance']==2


def test_anatomy_single_named_layer_and_independent_restyle():
    source=i.anatomy_view(cube(),width=20,height=20).surface('brain',cube(),opacity=.3)
    detail=source.zoom(cube(),width=10,height=10,layers='brain').style('brain',opacity=.8)
    assert source._layers[0][3]['opacity']==.3
    assert detail._layers[0][3]['opacity']==.8


def test_graph_build_contains_routed_edges_for_nested_components():
    graph=i.graph({'a':i.tag('source'),'b':i.tag('target')},[('a','b')],direction='right')
    built=graph.build()
    assert built.width>=graph.diagram.width
    kinds=[n.kind for n in built.walk()]
    assert any('shaft' in k or 'link' in k for k in kinds)
    assert len([n for n in built.walk() if isinstance(n.prim,TextPrim)])==2


def test_mosaic_direct_export_applies_axis_and_colorbar_theme():
    def plot(w,h):
        return i.panel(w,h).matrix([[0,1],[.5,.2]],ramp=i.ramp(['white','teal']),scale=i.linear((0,1)),raster=False).axes().colorbar()
    node=i.panel_mosaic(['A'],{'A':plot},width=100,height=70)
    placed=i.resolve(node)
    spines=[p for p in placed.values() if p.diagram.kind=='spine']
    assert spines and all(p.style.stroke not in (None,'none') for p in spines)


def test_mosaic_reallocates_tracks_to_minimums_without_changing_page():
    result=i.panel_mosaic(['A B C'],{'A':i.PanelSpec(i.tag('A'),min_width=60),'B':i.tag('B'),'C':i.tag('C')},width=120,height=40,gap=2,margin=2)
    slots=result.notes['panel_mosaic']
    assert slots['A']['slot'][2]-slots['A']['slot'][0]>=60-1e-6
    assert result.width==120
    with pytest.raises(DiagramError,match='minimum'):
        i.panel_mosaic(['A B'],{'A':i.PanelSpec(i.tag('A'),min_width=90),'B':i.PanelSpec(i.tag('B'),min_width=90)},width=120,height=40)


def test_mosaic_square_data_area_survives_axes_and_asymmetric_slot():
    result=i.panel_mosaic(['A'],{'A':i.PanelSpec(lambda w,h:i.panel(w,h).axes(x='x',y='long y title'),aspect=1,align='start')},width=60,height=110)
    record=result.notes['panel_mosaic']['A']
    assert record['drawing_size'][0]==pytest.approx(record['drawing_size'][1])
    assert record['content'][3]<90


def test_auto_tracks_do_not_reserve_absent_headers():
    art=i.panel_mosaic(['A'],{'A':i.Diagram(envelope_override=i.Envelope.from_rect(i.Rect(0,0,8,8)))},width=10,height=10,margin=0,gap=0,letters=False,row_weights='auto')
    assert art.height==10
