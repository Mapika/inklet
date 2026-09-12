"""Reusable recipes preserve live inputs, independent edits and measured layout."""
import pytest
import inklet as i
from inklet.core import DiagramError, resolve
from inklet.draw.coords import plot_area
from inklet.plot.axis import TICK_LABEL_KIND


def compile_plot(plot,width=110):
    doc=i.document(width=width);doc.add('plot',plot)
    return doc,doc.compile()


def test_copy_and_extend_keep_data_live_but_author_choices_independent():
    data=i.dataset({'x':[0,1,2],'y':[1,2,3]})
    marks=i.plot_spec().line(data.points('x','y'),key='signal',stroke='#34786b')
    a=i.plot_spec(x=(0,2),y=(0,5)).extend(marks,prefix='data-').axes()
    b=a.copy().style('data-signal',stroke='#b35e39',stroke_width=.9)
    da,first=compile_plot(a);db,second=compile_plot(b)
    svg=first.to_svg()
    assert '#34786b' in svg and '#b35e39' in second.to_svg()
    marks.style('signal',stroke='#000000')
    assert da.compile() is first and db.compile() is second
    data.update(y=[2,3,4])
    assert da.compile().to_svg()!=svg and db.compile().to_svg()!=second.to_svg()
    assert first.to_svg()==svg
    assert a.options=={'x':(0,2),'y':(0,5)}


def test_nested_plot_copies_and_failed_extension_are_independent():
    child=i.plot_spec(18,12,x=(0,1),y=(0,2)).line([(0,0),(1,1)],key='trace')
    base=i.plot_spec(x=(0,2),y=(0,4)).line([(0,1),(2,3)],key='trace')
    base.inset(child,width=None,key='detail')
    twin=base.twin_y((0,100));twin.line([(0,10),(2,80)],key='other')
    copied=base.copy();signature=copied.signature()
    child.style('trace',stroke='red');twin.style('other',stroke='blue')
    assert copied.signature()==signature
    before=base.signature()
    with pytest.raises(DiagramError,match='duplicate'): base.extend(copied)
    assert base.signature()==before
    with pytest.raises(KeyError): copied.style('absent',stroke='red')
    assert copied.signature()==signature


def test_literal_options_are_copied_and_shared_child_aliases_are_preserved():
    child=i.plot_spec().line([(0,0),(1,1)])
    source=i.plot_spec().inset(child,key='one').inset(child,key='two')
    target=source.copy()
    assert target._steps[0][2][0] is target._steps[1][2][0]
    assert target._steps[0][2][0] is not child
    target.style('one',pad=4)
    assert 'pad' not in source._steps[0][3]
    np=pytest.importorskip('numpy')
    points=np.array([[0.,0.],[1.,1.]])
    source=i.plot_spec().scatter(points,key='points');target=source.copy()
    assert not np.shares_memory(source._steps[0][2][0],target._steps[0][2][0])


def test_series_can_be_restyled_without_replacing_values_or_duplicating_keywords():
    series=i.Series('Original',[0,1,2],[1,2,3],'#34786b',[.8,1.8,2.8],[1.2,2.2,3.2])
    base=i.plot_spec(x=(0,2),y=(0,4)).series(series,key='response').axes().legend(side='bottom')
    edited=base.copy().style('response',name='Comparison',color='#b35e39')
    _,first=compile_plot(base);_,second=compile_plot(edited)
    assert 'Original' in first.to_svg() and 'Comparison' in second.to_svg()
    assert '#b35e39' in second.to_svg() and '#34786b' not in second.to_svg()
    assert series.name=='Original' and series.color=='#34786b'
    _,scatter=compile_plot(base.copy().style('response',kind='scatter',color='#b35e39',size=2))
    assert '#b35e39' in scatter.to_svg()
    _,line=compile_plot(base.copy().style('response',stroke='#123456'))
    assert '#123456' in line.to_svg()


def test_per_axis_options_override_shared_options_and_preserve_ticks():
    panel=i.panel(60,35,x=(0,2),y=(0,4))
    panel.axes(count=3,x_options={'ticks':[0,1,2],'format':lambda v: ['A','B','C'][int(v)]},
               y_options={'ticks':[0,4],'format':lambda v: 'low' if v==0 else 'high'})
    labels=[getattr(p.diagram.prim,'text',None) for p in resolve(panel.build()).values() if p.diagram.kind==TICK_LABEL_KIND]
    assert labels==['A','B','C','low','high']
    with pytest.raises(TypeError): i.panel().axes(x_options=[])


@pytest.mark.parametrize('shared',[False,True])
def test_wrapped_legend_keeps_authored_data_height_in_auto_documents(shared):
    p=i.plot_spec(x=(0,2),y=(10000,90000),height=30)
    for n in range(4): p.line([(0,20000+n*10000),(2,30000+n*10000)],name=f'Sample group {n}')
    p.axes(y='Measured response').legend(side='bottom')
    doc=i.document(width=80,share_plot_margins=shared);doc.add('plot',p)
    first=doc.compile()
    for width in (80,100,70):
        doc.configure(width=width);built=doc.compile()
        areas=[plot_area(p.diagram) for p in resolve(built.root).values() if p.diagram.kind=='document-cell']
        assert areas[0].height>=30-1e-5
        assert built.stats['layout_passes']<=24
    assert first.root.width==80


def test_failed_plot_configuration_preserves_previous_recipe():
    plot=i.plot_spec(width=40,height=30,x=(0,2))
    before=plot.signature()
    with pytest.raises(ValueError): plot.configure(width=80,height=-1,y=(0,4))
    assert plot.signature()==before


def test_preset_grid_uses_the_same_per_axis_label_measurements():
    from dataclasses import replace
    from inklet.plot.panel import GRID_KIND
    preset=replace(i.preset('scientific.general'),plot=i.PlotDefaults(grid='both'))
    p=i.plot_spec(x=(0,20),y=(0,20),height=35).axes(count=9,
        x_options={'format':lambda v:f'Observation {v:g}', 'font_size':4},
        y_options={'count':3,'format':lambda v:f'Y {v:g}'})
    doc=preset.document(width=95);doc.add('plot',p)
    built=doc.compile()
    placements=resolve(built.root).values()
    grids=[q for q in placements if q.diagram.kind==GRID_KIND]
    labels=[getattr(q.diagram.prim,'text','') for q in placements if q.diagram.kind==TICK_LABEL_KIND]
    assert len(grids)==len(labels)
    assert sum(s.startswith('Observation ') for s in labels)<9
    assert any(s.startswith('Y ') for s in labels)
