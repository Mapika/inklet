from dataclasses import replace
import pytest
import inklet as i
from inklet.core import DiagramError
from inklet.draw.coords import plot_area


def test_late_data_axes_legend_and_inset_changes_rebuild_snapshot():
    data=i.dataset({'x':[0,1,2],'y':[1,2,3]},units={'x':'s','y':'mV'})
    scale=i.shared_scale(data.column('y'))
    child=i.plot_spec(18,16,x=(0,2),y=scale).line(data.points('x','y')).axes()
    p=i.plot_spec(x=(0,2),y=scale)
    p.legend(side='bottom',key='key').inset(child,side='right',width=None,plate=False)
    p.axes(x='Time / s',y='Signal / mV',key='axes')
    p.line(data.points('x','y'),name='Signal',key='signal')
    d=i.document(width=150);d.add('main',p,min_height=60)
    first=d.compile();svg=first.to_svg()
    assert d.compile() is first
    data.update(y=[1,2,8])
    child.title('Inset title')
    p.replace('axes',x='Elapsed time / s',y='Measured signal / mV')
    second=d.compile()
    assert second is not first and second.to_svg()!=svg
    assert first.to_svg()==svg
    assert 'Elapsed time' in second.to_svg() and 'Inset title' in second.to_svg()
    assert second.metadata['datasets'][0]['revision']==1


def test_document_rebuilds_theme_geometry_and_restores_context():
    original=i.current_theme()
    spec=i.component(i.box,'A label')
    d=i.document(width=100,theme=replace(original,font_size=3))
    d.add('label',spec,min_height=40)
    a=d.compile();d.theme=replace(original,font_size=5);b=d.compile()
    assert a.to_svg()!=b.to_svg()
    from inklet.core.prims import TextPrim
    assert {p.diagram.prim.font_size for p in a.build()[1].values() if isinstance(p.diagram.prim,TextPrim)}=={3}
    assert {p.diagram.prim.font_size for p in b.build()[1].values() if isinstance(p.diagram.prim,TextPrim)}=={5}
    assert i.current_theme() is original


def test_width_changes_preserve_text_sizes_and_align_plot_areas():
    p=i.plot_spec(x=(0,10),y=(0,10)).line([(0,0),(10,10)]).axes(x='Time',y='Signal')
    q=i.plot_spec(x=(0,10),y=(0,10)).line([(0,0),(10,10)]).axes(x='Time',y='Longer label')
    d=i.document(width=120,columns=1)
    d.add('a',p,row=0,min_height=45);d.add('b',q,row=1,min_height=45)
    a=d.compile()
    root,positions=a.build()
    regions=[plot_area(positions[a.metadata['cells'][n]['node_id']].diagram).transform(
        positions[a.metadata['cells'][n]['node_id']].world @ positions[a.metadata['cells'][n]['node_id']].diagram.transform.inverse()) for n in ('a','b')]
    assert regions[0].x0==pytest.approx(regions[1].x0)
    d.width=90;b=d.compile()
    from inklet.core.prims import TextPrim
    sizes=lambda c:sorted({p.diagram.prim.font_size for p in c.build()[1].values() if isinstance(p.diagram.prim,TextPrim)})
    assert sizes(a)==sizes(b)
    assert b.root.width==90


def test_spans_overlaps_minima_and_links():
    d=i.document(width=100,height=70,columns=[1,2])
    a=i.component(i.database,'Input')
    b=i.component(i.feature_matrix,[[0,1],[1,0]],cell=5)
    d.add('a',a,row=0,column=0,min_height=25)
    d.add('b',b,row=0,column=1,min_height=25)
    d.add('caption',i.component(i.text,'Caption'),row=1,colspan=2,min_height=10)
    d.link('a:output','b:row-0',label='features')
    built=d.compile()
    assert built.cells['caption'].width==92
    assert built.root.height==70
    assert 'features' in built.to_svg()
    with pytest.raises(i.LayoutError,match='overlap'):
        d.add('overlap',a,row=0)
    d.width=30
    with pytest.raises(i.LayoutError,match='requires at least'):d.compile()


def test_dependency_cycles_and_failed_compilation_are_recoverable():
    a=i.plot_spec().line([(0,0),(1,1)])
    b=i.plot_spec().line([(0,0),(1,1)])
    a.inset(b,key='child');b.inset(a,key='child')
    d=i.document();d.add('main',a,min_height=60)
    with pytest.raises(DiagramError,match='cyclic'):d.compile()
    b.remove('child')
    assert d.compile().root.width==180


def test_categories_keep_metadata_through_deferred_calls():
    cats=i.categories({'a':'red','b':'blue'},labels={'a':'Alpha','b':'Beta'},groups={'One':['a'],'Two':['b']})
    p=i.plot_spec(x=(0,5),y=cats.scale(reverse=True))
    p.legend(side='right').group_labels(cats,side='left').axes()
    p.bars(['a','b'],[2,4],orient='h',bar_colors=cats)
    d=i.document(width=130);d.add('main',p,min_height=45)
    svg=d.compile().to_svg()
    assert all(label in svg for label in ['Alpha','Beta','One','Two'])


def test_twin_axes_remain_live_and_rebuild_with_parent():
    p=i.plot_spec(x=(0,1),y=(0,10)).line([(0,1),(1,5)],name='Signal').axes()
    twin=p.twin_y((0,100),label='Efficiency',color='#247')
    twin.line([(0,20),(1,70)],name='Efficiency',key='line')
    p.legend(side='bottom')
    d=i.document(width=110);d.add('main',p)
    a=d.compile();twin.replace('line',[(0,30),(1,90)],name='Efficiency')
    assert a.to_svg()!=d.compile().to_svg()


def test_live_category_selection_rebuilds_axes_keys_and_groups():
    definition=i.categories({'a':'#246','b':'#975','c':'#579'},
                            labels={'a':'Alpha','b':'Beta','c':'Gamma'},
                            groups={'First':['a','b'],'Second':['c']})
    encoding=i.CategoryEncoding(definition)
    data=i.dataset({'category':['a','b','c'],'value':[2,3,4]})
    p=i.plot_spec(x=(0,5),y=encoding.scale(reverse=True))
    p.legend(side='right').group_labels(encoding,side='left').axes()
    p.bars(data.column('category'),data.column('value'),orient='h',bar_colors=encoding)
    d=i.document(width=130);d.add('main',p,min_height=60)
    first=d.compile()
    data.update(category=['c'],value=[4]);encoding.select(['c'])
    second=d.compile()
    assert 'Alpha' in first.to_svg() and 'Alpha' not in second.to_svg()
    assert 'First' not in second.to_svg() and 'Second' in second.to_svg()


def test_unchanged_component_factory_is_reused_after_other_cell_edit():
    calls=[]
    def factory(label):
        calls.append(label)
        return i.box(label)
    a=i.component(factory,'A');b=i.component(factory,'B')
    d=i.document(width=100,columns=2,height=45)
    d.add('a',a,row=0);d.add('b',b,row=0,column=1)
    d.compile();count=calls.count('B');a.configure('Updated A')
    d.compile()
    assert calls.count('B')==count


def test_repeated_components_have_independent_ids_and_deterministic_exports():
    def build():
        shared=i.component(i.database,'Shared')
        d=i.document(width=100,columns=2,height=35)
        d.add('left',shared,row=0);d.add('right',shared,row=0,column=1)
        d.link('left:output','right:input')
        return d.compile()
    a=build()
    i.box('Unrelated allocation')
    b=build()
    assert a.to_svg()==b.to_svg()
    assert a.to_pdf()==b.to_pdf()
    assert a.metadata['cells']['left']['node_id']!=a.metadata['cells']['right']['node_id']


def test_overlapping_span_constraints_share_available_track_space():
    from inklet.document.compiler import _tracks
    tracks=_tracks(3,(1,1,1),[(0,1,10,'a'),(1,1,10,'b'),(2,1,10,'c'),
                              (0,2,100,'left-span'),(1,2,100,'right-span')],110,0,'width')
    assert sum(tracks)==pytest.approx(110,abs=1e-5)
    assert sum(tracks[:2])>=100-1e-5 and sum(tracks[1:])>=100-1e-5


def test_file_dependency_rebuilds_factory_when_contents_change(tmp_path):
    path=tmp_path/'label.txt';path.write_text('Before')
    node=i.component(lambda path:i.text(path.read_text()),i.FileRef(path))
    d=i.document(width=80);d.add('text',node)
    a=d.compile();path.write_text('After')
    assert 'After' in d.compile().to_svg() and 'Before' in a.to_svg()


def test_document_output_is_independent_of_global_theme():
    original=i.current_theme()
    def build():
        d=i.document(width=100,theme=replace(original,font_size=3))
        d.add('label',i.component(i.box,'Label'),min_height=40)
        return d.compile().to_svg()
    try:
        i.use_theme(replace(original,font_size=2))
        first=build()
        i.use_theme(replace(original,font_size=6))
        assert build()==first
    finally:i.use_theme(original)
