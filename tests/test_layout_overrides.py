"""Saved author decisions follow named content and retain measured relationships."""
import json

import pytest
import inklet as i


def source():
    data=i.dataset({'x':[0,1,2],'y':[1,2,3]})
    plot=i.plot_spec(x=(0,2),y=(0,5)).line(data.points('x','y'),stroke='#34786b',key='trace').axes()
    group=i.composition(70,20)
    group.add('a',i.module('Input'),x=5,y=4)
    x,y=group.point('a','out')
    group.add('b',i.module('Output'),x=x+12,y=y,anchor='in')
    group.link('a:out','b:in').port('exit','b:out')
    recipe=i.composition(130,80)
    recipe.add('plot',plot,x=13,y=8,anchor='area-nw',width=recipe.page_width-26,height=30)
    recipe.add('flow',group,x=5,y=55)
    return recipe,data


def compile_recipe(recipe,width=130):
    doc=i.document(width=width,height=85,margin=0);doc.add('report',recipe)
    return doc,doc.compile()


def test_json_roundtrip_records_only_edits_and_retains_live_data():
    base,data=source();edited=base.copy()
    edited.place('plot',width=edited.page_width-35,height=35)
    edited['flow'].place('a',x=10).configure(width=90)
    saved=json.loads(json.dumps(edited.layout_overrides(base),allow_nan=False))
    assert set(saved['targets'])=={'/plot','/flow','/flow/a'}
    assert saved['targets']['/flow']=={'page':{'width':90}}
    assert saved['targets']['/plot']['placement']['width']=={'op':'-','args':[{'op':'page','args':['width']},35]}
    restored,report=base.with_layout_overrides(saved)
    assert report=={'orphaned_targets':[],'missing_policy':'error'}
    doc,first=compile_recipe(restored);_,expected=compile_recipe(edited)
    assert first.to_svg()==expected.to_svg()
    before=first.to_svg();saved['targets']['/plot']['placement']['height']=90
    assert doc.compile() is first
    data.update(y=[2,3,4])
    assert doc.compile().to_svg()!=before and first.to_svg()==before
    assert base.layout_overrides(base)['targets']=={}


def test_unedited_source_choices_and_new_content_survive_reapplication():
    base,_=source();edited=base.copy().place('plot',x=18)
    saved=edited.layout_overrides(base)
    revised=base.copy().place('plot',height=40)
    revised['plot'].style('trace',stroke='#aa5b36')
    revised['flow']['a'].configure('New input')
    revised.add('new',i.component(i.text,'Additional content'),x=90,y=65)
    applied,_=revised.with_layout_overrides(saved)
    _,result=compile_recipe(applied)
    assert '#aa5b36' in result.to_svg() and 'Additional content' in result.to_svg()
    assert applied._parts[0].height==40 and applied._parts[0].x==18
    assert applied['flow']['a'].label=='New input'
    assert revised._parts[0].x==13


def test_removed_nested_target_has_explicit_drop_report_and_no_mutation():
    base,_=source();edited=base.copy();edited['flow'].place('a',x=11)
    state=edited.layout_overrides(base)
    revised=base.copy();revised.replace('flow',i.module('Replacement'))
    before=revised.signature()
    with pytest.raises(i.LayoutError,match='orphaned layout targets: /flow/a'):
        revised.with_layout_overrides(state)
    result,report=revised.with_layout_overrides(state,missing='drop')
    assert report['orphaned_targets']==['/flow/a']
    assert revised.signature()==before and result['flow'].label=='Replacement'


def test_removed_expression_reference_or_incompatible_page_is_orphaned():
    base,_=source()
    edited=base.copy();x,y=edited.point('flow','exit');edited.place('plot',x=x+1)
    state=edited.layout_overrides(base)
    del base._parts[1]
    with pytest.raises(i.LayoutError,match='/plot'):base.with_layout_overrides(state)
    _,report=base.with_layout_overrides(state,missing='drop')
    assert report['orphaned_targets']==['/plot']
    state['targets']={'/plot':{'page':{'width':150}}}
    with pytest.raises(i.LayoutError,match='/plot'):base.with_layout_overrides(state)


@pytest.mark.parametrize('entry',[
    {'placement':{'height':-1}}, {'placement':{'x':float('nan')}},
    {'placement':{'x':True}}, {'placement':{'anchor':''}},
    {'placement':{'widht':20}}, {'page':{'fit_top':1}},
    {'page':{'unit':0}}, {'page':{'height':float('inf')}},
    {'placement':{'x':{'op':'execute','args':['bad']}}},
    {'placement':{'x':{'op':'+','args':[1]}}},
    {'placement':{'x':{'op':'measure','args':['../x','width']}}},
    {'placement':{}}, {'unexpected':{}}, {},
])
def test_invalid_saved_values_fail_atomically_even_with_drop(entry):
    recipe,_=source();before=recipe.signature()
    state={'schema':'inklet.composition-layout/0.1','targets':{'/absent':entry}}
    with pytest.raises(ValueError):recipe.with_layout_overrides(state,missing='drop')
    assert recipe.signature()==before


def test_schema_paths_expression_depth_and_capture_topology_are_validated():
    base,_=source();state=base.layout_overrides(base)
    state['schema']='unknown'
    with pytest.raises(ValueError):base.with_layout_overrides(state)
    state['schema']='inklet.composition-layout/0.1'
    for path in ('plot','/../plot','/plot/','//plot'):
        state['targets']={path:{'placement':{'x':1}}}
        with pytest.raises(ValueError):base.with_layout_overrides(state)
    expression=1
    for _ in range(34):expression={'op':'+','args':[expression,1]}
    state['targets']={'/plot':{'placement':{'x':expression}}}
    with pytest.raises(ValueError,match='32'):base.with_layout_overrides(state)
    different=base.copy();different.add('extra',i.module('Extra'))
    with pytest.raises(i.LayoutError,match='matching'):different.layout_overrides(base)
    with pytest.raises(ValueError,match='missing policy'):base.with_layout_overrides({},missing='ignore')


def test_shared_nested_definitions_reject_conflicting_edits_in_any_order():
    base,_=source();base.add('alias',base['flow'],x=80,y=55)
    edited=base.copy();edited['flow'].place('a',x=12)
    state=edited.layout_overrides(base)
    restored,_=base.with_layout_overrides(state)
    assert restored['flow'] is restored['alias']
    assert restored['flow']._parts[0].x==12
    state['targets']['/alias/a']['placement']['x']=13
    for targets in (state['targets'],dict(reversed(list(state['targets'].items())))):
        with pytest.raises(i.LayoutError,match='conflicting'):
            base.with_layout_overrides({**state,'targets':targets})


def test_layout_cycles_and_unavailable_anchors_are_diagnosed_at_compile():
    base,_=source();edited=base.copy();edited.place('plot',anchor='missing')
    applied,_=base.with_layout_overrides(edited.layout_overrides(base))
    with pytest.raises(i.DiagramError,match='missing'):compile_recipe(applied)
    base.add('self',base)
    with pytest.raises(i.LayoutError,match='cyclic'):base.layout_overrides(base)


@pytest.mark.parametrize('width',[150,130,100])
def test_saved_measured_expressions_recompute_after_page_resize(width):
    base,_=source();edited=base.copy().place('plot',width=base.page_width-30)
    restored,_=base.with_layout_overrides(json.loads(json.dumps(edited.layout_overrides(base))))
    _,actual=compile_recipe(restored,width);_,expected=compile_recipe(edited,width)
    assert actual.to_svg()==expected.to_svg()


def test_dimension_strings_are_normalized_and_mixed_content_reopens_identically():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'examples/composition_recipes.py'
    spec=importlib.util.spec_from_file_location('composition_example',path)
    example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)
    reports,data=example.make_reports();base=reports[0]
    edited=base.copy().place('chart',height='35mm',width=base.page_width*.5-20)
    edited.place('object',x=base.page_width*.76).place('workflow',y=80)
    state=json.loads(json.dumps(edited.layout_overrides(base)))
    assert state['targets']['/chart']['placement']['height']==35
    reopened,_=base.with_layout_overrides(state)
    for width in (180,150):
        _,actual=compile_recipe(reopened,width);_,expected=compile_recipe(edited,width)
        assert actual.to_svg()==expected.to_svg()
        assert actual.to_pdf()==expected.to_pdf()
    revised=base.copy();revised.replace('object',i.component(i.solid,'sphere',width=28,style='toon'))
    revised['workflow']['model'].configure('Revised model')
    applied,_=revised.with_layout_overrides(state)
    _,figure=compile_recipe(applied,150)
    assert 'Revised model' in figure.to_svg()
    assert applied['object'].args==('sphere',)
    assert applied._parts[1].height==35


def test_all_measured_operations_page_settings_and_optional_resets_roundtrip():
    base,_=source();edited=base.copy().configure(width=150,height=90,unit=.5,fit_top=True)
    group=edited['flow']
    x,y=group.point('a','out')
    group.place('b',x=x+group.measure('a','width')/2-3,y=-(-y),width=None,height=None)
    edited.place('flow',anchor='nw',width=90,height=25)
    state=json.loads(json.dumps(edited.layout_overrides(base)))
    restored,_=base.with_layout_overrides(state)
    assert restored.width==150 and restored.height==90 and restored.unit==.5 and restored.fit_top
    _,actual=compile_recipe(restored);_,expected=compile_recipe(edited)
    assert actual.to_svg()==expected.to_svg()
    original=base.copy().place('flow',width=90,anchor='nw')
    variant=original.copy().place('flow',width=None,anchor=None)
    reset,_=original.with_layout_overrides(variant.layout_overrides(original))
    assert reset._parts[1].width is None and reset._parts[1].anchor is None
