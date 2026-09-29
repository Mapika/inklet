from dataclasses import replace
import pytest
import inklet as i
from inklet.core import TextPrim
from inklet.render.bundle import component_paths


def sizes(compiled):
    return {p.diagram.prim.font_size for p in compiled.build()[1].values() if isinstance(p.diagram.prim,TextPrim)}


def test_nested_grids_share_theme_cache_data_and_letter_space():
    data=i.dataset({'x':[0,1,2],'y':[1,3,2]},name='nested data')
    panel=i.plot_spec(x=(0,2),y=(0,5)).line(data.points('x','y')).axes(x='Time',y='Response')
    group=i.subfigure(columns=2,gap=5).letters(size=3)
    group.add('response',panel,row=0,column=0,min_height=50)
    group.add('summary',i.component(i.box,'Measured summary'),row=0,column=1,min_height=50)
    doc=i.document(width=150,theme=replace(i.theme('nature'),font_size=3))
    doc.add('experiment',group)
    first=doc.compile();svg=first.to_svg()
    assert first.metadata['datasets'][0]['name']=='nested data'
    assert first is doc.compile()
    assert any('experiment / response' in p for p in component_paths(first.root).values())
    assert not any(d.code=='OFF_CANVAS' for d in first.diagnostics)
    data.update(y=[1,4,2]);second=doc.compile()
    assert second is not first and second.stats['cache_hits']>0
    assert first.to_svg()==svg
    doc.configure(width=180);third=doc.compile()
    assert sizes(third)==sizes(first)
    assert third.metadata['datasets'][0]['revision']==1


def test_nested_responsive_cells_reserve_panel_letters():
    inner=i.subfigure(height=30).letters()
    inner.add('caption',i.component(i.box,'Caption',responsive=True),min_height=15)
    outer=i.document(width=80,height=50)
    outer.add('inset',inner)
    compiled=outer.compile()
    assert not any(d.code=='OFF_CANVAS' for d in compiled.diagnostics)


def test_repeated_nested_cell_names_have_unique_stable_export_ids():
    import xml.etree.ElementTree as ET
    doc=i.document(width=180,columns=2)
    for column,name in enumerate(('left','right')):
        child=i.subfigure()
        child.add('heading',i.component(i.text,name))
        child.add('body',i.module('Body'))
        doc.add(name,child,row=0,column=column)
    # Names resembling structural paths must not collide with child IDs.
    doc.add('left--cell-heading',i.component(i.text,'Literal separator'),row=1)
    doc.add('left-0',i.component(i.text,'Literal suffix'),row=1,column=1)
    first=doc.compile();svg=first.to_svg()
    placements=first.build()[1]
    assert 'cell-left/cell-heading' in placements
    assert 'cell-right/cell-heading' in placements
    assert 'cell-left--cell-heading' in placements
    ids=[node.attrib['id'] for node in ET.fromstring(svg).iter() if 'id' in node.attrib]
    assert len(ids)==len(set(ids))
    assert all(d.code!='RULE_FAILED' for d in first.diagnostics)
    doc['left'].replace('heading',i.component(i.text,'Edited heading'))
    second=doc.compile()
    assert second.to_svg()!=svg and first.to_svg()==svg
    assert 'cell-right/cell-heading' in second.build()[1]
    assert all(target in second.build()[1] for d in second.diagnostics for target in d.targets)
    assert second.to_pdf().startswith(b'%PDF')


def test_sibling_subfigures_retain_all_dataset_provenance_after_edits():
    doc=i.document(width=100)
    cover=i.subfigure();cover.add('title',i.component(i.text,'No data here'))
    doc.add('cover',cover)
    tables=[]
    for index in range(3):
        data=i.dataset({'x':[0,1],'y':[index,index+1]},name=f'data-{index}',
                       source=i.Source('Simulated regression data',method='simulated'))
        tables.append(data)
        child=i.subfigure()
        child.add('plot',i.plot_spec(x=(0,1),y=(0,6)).line(data.points('x','y')).axes())
        doc.add(f'panel-{index}',child)
    first=doc.compile()
    assert {d['name'] for d in first.metadata['datasets']}=={d.name for d in tables}
    tables[-1].update(y=[4,5])
    second=doc.compile()
    before={d['name']:d for d in first.metadata['datasets']}
    after={d['name']:d for d in second.metadata['datasets']}
    for index in range(3):
        name=f'data-{index}'
        assert after[name]['revision']==int(index==2)
        assert (before[name]['data_sha256']!=after[name]['data_sha256'])==(index==2)
        assert after[name]['source']['method']=='simulated'


def test_lettered_modules_preserve_named_connection_ports():
    doc=i.document(width=100,height=40,columns=2).letters()
    doc.add('input',i.module('Input'),row=0,column=0)
    doc.add('output',i.module('Output'),row=0,column=1)
    doc.link('input:out','output:in')
    assert not any(d.code=='RULE_FAILED' for d in doc.compile().diagnostics)


def test_direct_module_constructor_is_validated_and_cache_stable():
    module=i.ModuleSpec('Direct constructor',min_width='30mm')
    doc=i.document();doc.add('module',module)
    first=doc.compile()
    assert doc.compile() is first
    with pytest.raises(ValueError,match='positive'):i.ModuleSpec('Invalid',min_width=-1)


def test_nested_cycles_and_impossible_tracks_report_layout_error():
    group=i.subfigure();group.add('self',group)
    doc=i.document();doc.add('outer',group)
    with pytest.raises(i.DiagramError,match='cyclic'):doc.compile()
    group=i.subfigure(columns=2)
    group.add('a',i.module('A'),row=0,column=0,min_width=50)
    group.add('b',i.module('B'),row=0,column=1,min_width=50)
    doc=i.document(width=80);doc.add('outer',group)
    with pytest.raises(i.LayoutError,match='width requires'):doc.compile()


def architecture():
    art=i.composition(130,55)
    art.add('input',i.module('Input'),x=5,y=15)
    x,_=art.point('input','out')
    art.add('model',i.module('Model'),x=x+12,y=15)
    x,_=art.point('model','out')
    art.add('output',i.module('Output'),x=x+12,y=15)
    art.link('input:out','model:in')
    art.link('model:out','output:in')
    art.link('output:s','input:s',route='orthogonal')
    return art


def test_modules_ports_routes_and_label_edits_move_dependants():
    art=architecture();doc=i.document(width=150,height=65);doc.add('architecture',art)
    first=doc.compile();old=first.to_svg()
    def position(compiled,name):
        return next(p.bbox.x0 for p in compiled.build()[1].values() if p.diagram.name==name)
    art['model'].configure('A longer module label')
    changed=doc.compile()
    assert position(changed,'output')>position(first,'output')
    assert sizes(changed)==sizes(first) and first.to_svg()==old
    assert changed.stats['cache_hits']>0


def test_composition_rejects_reference_cycles_and_nonfinite_coordinates():
    scene=i.composition(80,40)
    x,_=scene.point('b','out');scene.add('a',i.module('A'),x=x)
    x,_=scene.point('a','out');scene.add('b',i.module('B'),x=x)
    doc=i.document();doc.add('scene',scene)
    with pytest.raises(i.LayoutError,match='cyclic layout'):doc.compile()
    scene=i.composition(80,40);scene.add('label',i.component(i.text,'Text'),x=float('nan'))
    doc.replace('scene',scene)
    with pytest.raises(i.LayoutError,match='finite'):doc.compile()


def test_composition_size_expressions_and_constraints():
    art=i.composition(100,40)
    art.add('plot',i.plot_spec(x=(0,1),y=(0,1)).line([(0,0),(1,1)]),
            x=5,y=5,anchor='area-nw',width=art.page_width-10,height=30)
    art.constrain(art.page_width,minimum=60,message='need 60 units')
    doc=i.document(width=120,height=50,margin=0);doc.add('art',art)
    first=doc.compile()
    doc.configure(width=50)
    with pytest.raises(i.LayoutError,match='need 60'):doc.compile()
    assert first.root.width==120


def test_composition_waypoints_use_the_declared_coordinate_unit():
    art=i.composition(100,60,unit=.5)
    art.add('a',i.module('A',min_width=10,min_height=8),x=5,y=20)
    art.add('b',i.module('B',min_width=10,min_height=8),x=55,y=20)
    art.link('b:s','a:s',route='orthogonal',waypoints=[(65,50),(15,50)])
    doc=i.document(width=50,height=30,margin=0);doc.add('art',art)
    compiled=doc.compile()
    assert not any(d.code=='OFF_CANVAS' for d in compiled.diagnostics)


def test_publication_checks_use_final_physical_size_and_export_defaults(tmp_path,monkeypatch):
    profile=i.publication('single-column',min_font_pt=7,min_stroke_mm=.15,dpi=240,text='outline')
    doc=profile.document(height=35)
    doc.add('small',i.component(i.text,'Small',size=i.pt(6)))
    compiled=doc.compile()
    assert compiled.root.width==89
    assert any(d.code=='TINY_TEXT' and '7.0pt' in d.message for d in compiled.diagnostics)
    assert compiled.metadata['publication']['dpi']==240
    assert '<text' not in compiled.to_svg()
    assert '<text' in compiled.to_svg(text='embed')
    import inklet.render.bundle as bundle
    monkeypatch.setattr(bundle,'export_bundle',lambda figure,path,**kw:kw)
    assert compiled.export(tmp_path)==dict(dpi=240,text='outline')
    assert compiled.export(tmp_path,dpi=100)['dpi']==100
    assert profile.document(width=100).width==100
    with pytest.raises(ValueError):i.publication('unknown')
    with pytest.raises(ValueError):i.publication(dpi=float('nan'))


def test_deferred_brackets_and_callouts_see_late_marks():
    data=i.dataset({'x':[0,1],'y':[2,3]})
    plot=i.plot_spec(x=(-.5,1.5),y=(0,8))
    plot.bracket(0,1,'*').annotate(1,3,'Peak')
    plot.bars(data.column('x'),data.column('y')).axes()
    doc=i.document(width=100,height=70);doc.add('bars',plot)
    first=doc.compile();old=first.to_svg()
    data.update(y=[4,6]);changed=doc.compile()
    assert changed.to_svg()!=old and first.to_svg()==old
    assert not any(d.code=='RULE_FAILED' for d in changed.diagnostics)
    def bracket_top(compiled):
        return min(p.bbox.y0 for p in compiled.build()[1].values() if p.diagram.kind=='bracket')
    assert bracket_top(changed)<bracket_top(first)


def test_callout_avoids_an_inset_declared_later_in_the_recipe():
    from inklet.document.compiler import BuildContext
    def overlap(avoid):
        plot=i.plot_spec(80,50,x=(0,10),y=(0,10)).annotate(6.2,8,'A callout',side='e',avoid_marks=avoid)
        plot.inset(i.plot_spec(20,15,x=(0,1),y=(0,1)).line([(0,0),(1,1)]),corner='ne',width=None)
        nodes=i.resolve(BuildContext(i.theme('nature'),{}).build(plot)).values()
        boxes={p.diagram.kind:p.bbox for p in nodes if p.diagram.kind in ('annotation-label','frame')}
        a,b=boxes['annotation-label'],boxes['frame']
        return max(0,min(a.x1,b.x1)-max(a.x0,b.x0))*max(0,min(a.y1,b.y1)-max(a.y0,b.y0))
    assert overlap(False)>0
    assert overlap(True)==0


def test_composition_callouts_reflow_after_module_edits():
    art=architecture().annotate('model','Shared features',size=2)
    doc=i.document(width=150,height=65);doc.add('art',art)
    first=doc.compile();old=first.to_svg()
    art['model'].configure('Updated model')
    changed=doc.compile()
    assert 'Shared features' in changed.to_svg()
    assert not any(d.code=='RULE_FAILED' for d in changed.diagnostics)
    assert changed.to_svg()!=old and first.to_svg()==old


def _stacked(share=False):
    group=i.subfigure(columns=1,row_gap=1,share_plot_margins=share)
    group.add('key',i.text('male'),row=0)
    for k,height in enumerate([10,6,14]):
        p=i.plot_spec(height=height,x=(0,1),y=['a','b']).bars(['a','b'],[.4,.8],orient='h')
        if k==2: p.axis('bottom',label='share')
        group.add(f'p{k}',p,row=k+1)
    return group


def _tracks(group,height):
    from inklet.document.compiler import BuildContext
    result=group._layout(BuildContext(i.theme('nature'),{}),45,height)
    return result.page_height,{name:box.height for name,box in result.boxes.items()}


@pytest.mark.parametrize('share',[False,True])
def test_nested_grid_at_its_natural_height_keeps_its_rows(share):
    group=_stacked(share)
    page,natural=_tracks(group,None)
    assert natural['p0']==pytest.approx(10) and natural['p1']==pytest.approx(6)
    assert _tracks(group,page)[1]==pytest.approx(natural)


@pytest.mark.parametrize('share',[False,True])
def test_fixed_height_surplus_grows_plots_by_data_height_not_text(share):
    group=_stacked(share)
    page,natural=_tracks(group,None)
    _,grown=_tracks(group,page+20)
    assert grown['key']==pytest.approx(natural['key'])
    # Stacked plots keep one scale: every data height grows by the same factor.
    factors=[(grown[n]-natural[n])/h for n,h in [('p0',10),('p1',6),('p2',14)]]
    assert factors==pytest.approx([factors[0]]*3)
    assert sum(grown.values())==pytest.approx(sum(natural.values())+20)


def test_parent_row_taller_than_nested_grid_keeps_nested_proportions():
    doc=i.preset('scientific.cell').document(columns=12)
    doc.add('stack',_stacked(True),row=0,column=0,colspan=3)
    doc.add('tall',i.plot_spec(height=90,x=(0,1),y=(0,1)).axes(),row=0,column=3,colspan=9)
    positions=doc.compile().build()[1]
    heights={n:positions[f'cell-stack/cell-{n}'].bbox.height for n in ('key','p0','p1')}
    assert heights['key']<5
    assert heights['p0']/heights['p1']==pytest.approx(10/6,rel=.02)


def test_fixed_height_too_small_shrinks_plots_but_not_fixed_artwork():
    group=_stacked()
    page,natural=_tracks(group,None)
    _,shrunk=_tracks(group,page-8)
    assert shrunk['key']==pytest.approx(natural['key'])
    assert all(shrunk[n]<natural[n] for n in ('p0','p2'))


def test_grow_false_row_keeps_natural_height_under_a_fixed_page():
    group=_stacked()
    group._cells[1]=replace(group._cells[1],grow=False)
    page,natural=_tracks(group,None)
    _,grown=_tracks(group,page+20)
    assert grown['p0']==pytest.approx(natural['p0'])
    assert grown['p2']>natural['p2']


def test_unstretched_subfigure_keeps_natural_rows_and_follows_cell_align():
    from inklet.draw.coords import plot_area
    def page(stretch):
        doc=i.preset('scientific.cell').document(columns=12)
        group=_stacked(True); group.stretch=stretch
        doc.add('stack',group,row=0,column=0,colspan=3,align='n')
        doc.add('tall',i.plot_spec(height=90,x=(0,1),y=(0,1)).axes(),row=0,column=3,colspan=9)
        compiled=doc.compile()
        positions=compiled.build()[1]
        data={n:plot_area(positions[f'cell-stack/cell-{n}'].diagram).height for n in ('p0','p1','p2')}
        return compiled.metadata['cells']['stack'],positions['cell-stack/cell-key'].bbox,data
    cell,key,natural=page(False)
    assert [natural[n] for n in ('p0','p1','p2')]==pytest.approx([10,6,14],abs=.05)
    assert key.y0==pytest.approx(cell['y'],abs=1)
    _,_,stretched=page(True)
    assert stretched['p0']>natural['p0']+5


def test_plot_authored_at_the_minimum_data_height_fits_in_a_nested_grid():
    group=i.subfigure(row_gap=1)
    for k in range(3):
        group.add(f'p{k}',i.plot_spec(height=5,x=(0,1),y=['a']).bars(['a'],[.5],orient='h'),row=k)
    doc=i.document(width=120,columns=3)
    doc.add('stack',group,row=0,column=0)
    doc.add('tall',i.plot_spec(height=60,x=(0,1),y=(0,1)).axes(),row=0,column=1,colspan=2)
    doc.compile()
