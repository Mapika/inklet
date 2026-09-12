"""Composition inputs, authoring isolation and nested physical attachment points."""
import pytest
import inklet as i
from inklet.document.spec import fingerprint
from inklet.draw.coords import plot_area


def compile_recipe(recipe, width=120, height=65):
    doc=i.document(width=width,height=height,margin=0)
    doc.add('recipe',recipe)
    return doc,doc.compile()


def placed(figure,name):
    return next(p for p in figure.build()[1].values() if p.diagram.name==name)


def template():
    recipe=i.composition(120,65)
    recipe.slot('plot',x=12,y=8,anchor='area-nw',width=recipe.page_width-24,height=30)
    recipe.add('caption',i.module('Response',min_width=25,pad=2),x=12,y=50)
    recipe.port('output','caption:out')
    return recipe


def test_required_inputs_fail_clearly_without_mutating_template():
    recipe=template();before=recipe.signature()
    with pytest.raises(i.LayoutError,match='missing composition inputs: plot'):recipe.instantiate()
    with pytest.raises(i.LayoutError,match='unknown composition inputs: typo'):recipe.instantiate(typo=i.module('X'))
    with pytest.raises(i.LayoutError,match="unbound composition slot 'plot'"):compile_recipe(recipe)
    assert recipe.signature()==before


def test_instances_isolate_authored_content_and_retain_live_data():
    data=i.dataset({'x':[0,1,2],'y':[1,2,3]})
    plot=i.plot_spec(x=(0,2),y=(0,5)).line(data.points('x','y'),key='trace',stroke='#34786b').axes()
    recipe=template();a=recipe.instantiate(plot=plot);b=recipe.instantiate(plot=plot)
    b['plot'].style('trace',stroke='#aa5b36');b['caption'].configure('Independent caption')
    da,first=compile_recipe(a);db,second=compile_recipe(b);old=first.to_svg()
    assert '#34786b' in old and '#aa5b36' in second.to_svg()
    plot.style('trace',stroke='#000000');recipe['caption'].configure('Template edit')
    assert da.compile() is first and db.compile() is second
    data.update(y=[2,3,4])
    changed=da.compile()
    assert changed.to_svg()!=old and db.compile().to_svg()!=second.to_svg()
    assert first.to_svg()==old and da.compile() is changed
    # A fresh compiler agrees with the incremental result.
    _,fresh=compile_recipe(a)
    assert changed.to_svg()==fresh.to_svg()


def test_copy_preserves_aliases_nested_recipes_and_external_dependencies():
    inner=i.composition(40,20);shared=i.module('Same')
    inner.add('left',shared);inner.add('right',shared,x=22)
    outer=i.composition(120,50);outer.add('inner',inner)
    outer.add('label',i.component(i.text,'Original',font_size=3))
    diagram=i.text('Static');outer.add('static',diagram)
    copied=outer.copy()
    assert copied['inner'] is not inner
    assert copied['inner']['left'] is copied['inner']['right']
    assert copied['inner']['left'] is not shared and copied['static'] is diagram
    copied['label'].configure('Changed')
    assert outer['label'].args==('Original',)
    # Cycles are preserved so the normal dependency diagnostic still handles them.
    outer.add('self',outer)
    cyclic=outer.copy()
    assert cyclic['self'] is cyclic
    with pytest.raises(i.DiagramError,match='cyclic'):fingerprint(cyclic)


def test_nested_ports_follow_replacement_placement_units_and_top_fit():
    inner=i.composition(80,40,unit=.5,fit_top=True)
    inner.add('source',i.module('Source',min_width=20,min_height=12,pad=1),x=10,y=-10)
    inner.port('entry','source:in').port('exit','source:out')
    outer=i.composition(120,65)
    outer.add('group',inner,x=15,y=10)
    x,y=outer.point('group','exit')
    outer.add('sink',i.module('Sink'),x=x+10,y=y,anchor='in')
    outer.link('group:exit','sink:in')
    doc,first=compile_recipe(outer)
    assert placed(first,'sink').bbox.x0==pytest.approx(50)
    assert placed(first,'sink').bbox.center.y==pytest.approx(16)
    inner.replace('source',i.module('A longer source label',min_width=40,pad=1))
    second=doc.compile()
    assert placed(second,'sink').bbox.x0>placed(first,'sink').bbox.x0
    outer.place('group',x=25)
    third=doc.compile()
    assert placed(third,'sink').bbox.x0==pytest.approx(placed(second,'sink').bbox.x0+10)
    assert first is not second and second is not third


def test_port_changes_invalidate_cache_and_reject_invalid_targets():
    recipe=i.composition(100,40);recipe.add('a',i.module('A'),x=10,y=10)
    recipe.port('connection','a:in');doc,first=compile_recipe(recipe)
    recipe.port('connection','a:out');second=doc.compile()
    assert first is not second
    for target in ('absent:out','a:',':in','a:in:extra',None):
        with pytest.raises((ValueError,i.LayoutError)):recipe.port('connection',target)
    with pytest.raises(ValueError):recipe.port('', 'a')
    recipe.port('bad','a:nonexistent')
    with pytest.raises(i.DiagramError,match='nonexistent'):doc.compile()


def test_placement_and_dimension_failures_leave_prior_recipe_intact():
    recipe=template();before=recipe.signature()
    with pytest.raises(ValueError):recipe.configure(width=200,height=-1)
    with pytest.raises(TypeError):recipe.place('plot',x=20,widht=10)
    with pytest.raises(KeyError):recipe.place('missing',x=1)
    assert recipe.signature()==before
    recipe.configure(width=150,unit=.5).place('plot',width=80)
    assert recipe.width==150 and recipe.unit==.5


@pytest.mark.parametrize('width',[150,120,90])
def test_resized_slot_preserves_plot_data_height(width):
    plot=i.plot_spec(x=(0,2),y=(0,5)).line([(0,1),(1,2),(2,4)]).axes()
    recipe=template().instantiate(plot=plot)
    _,figure=compile_recipe(recipe,width=width)
    panel=next(p.diagram for p in figure.build()[1].values() if p.diagram.kind=='panel')
    assert plot_area(panel).height==pytest.approx(30)
    assert plot_area(panel).width==pytest.approx(width-24)


def test_mixed_report_example_keeps_content_and_data_relationships_at_two_widths():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'examples/composition_recipes.py'
    spec=importlib.util.spec_from_file_location('composition_example',path)
    example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)
    reports,data=example.make_reports()
    originals=[]
    for report in reports:
        doc,wide=compile_recipe(report,width=180,height=110)
        doc.configure(width=150);narrow=doc.compile()
        assert wide.root.width==180 and narrow.root.width==150
        assert narrow.to_pdf().startswith(b'%PDF')
        assert 'Illustrative model' in wide.to_svg() or 'Alternative geometry' in wide.to_svg()
        assert narrow.metadata['datasets'][0]['name']=='illustrative-response'
        originals.append((doc,narrow,narrow.to_svg()))
    data.update(y=[1.4,2.5,3.2,3.6,4.4])
    for doc,old,svg in originals:
        new=doc.compile()
        assert new.to_svg()!=svg and old.to_svg()==svg and doc.compile() is new
    assert reports[0]['workflow']['model'].label=='Model'
    assert reports[1]['workflow']['model'].label=='Revised model'
