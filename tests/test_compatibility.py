"""Released-wheel API and saved-file fixtures protect migration across versions."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import inklet as i
from inklet.experimental.project import FigureProject
from inklet.experimental.selection import KeyedTable, SelectionState

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(__file__).with_name('fixtures')/'compatibility'


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_released_top_level_api_retains_public_call_shapes():
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    baseline=json.loads((FIXTURES/'api-3.1.json').read_text())
    assert baseline['version']=='3.1.0'
    assert checker.differences(baseline,checker.inventory(i))==[]


def test_released_fixture_bytes_match_recorded_origins():
    provenance=json.loads((FIXTURES/'provenance.json').read_text())
    assert set(provenance['releases'])=={'3.1.0','4.0.0.dev16','4.0.0rc1'}
    for name,digest in provenance['files'].items():
        assert hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest()==digest,name


def test_dev16_project_reopens_with_original_choices_and_export():
    recipe=load(FIXTURES/'recipe.py','compatibility_recipe')
    bundle=FIXTURES/'dev16-project'
    metadata=json.loads((bundle/'.inklet/project.json').read_text())
    assert metadata['inklet_version']=='4.0.0.dev16'
    # Strict comparison includes the captured source SVG hash. Release CI pins
    # the fonts and renderers; other environments may need reviewed reconstruction.
    project=FigureProject.open(bundle,recipe.composition)
    assert project.selected==('a',)
    assert project.editor.figure.to_svg()==(bundle/'.inklet/figure.svg').read_text()
    assert project.editor.overrides()['targets']['/left']['placement']['x']==14
    assert project.identities.targets(project.selected)['rows']==('sample-7',)


def test_dev16_layout_and_hidden_selection_survive_reordered_data():
    recipe=load(FIXTURES/'recipe.py','compatibility_recipe')
    base=recipe.composition(FIXTURES/'dev16-project')
    saved=json.loads((FIXTURES/'layout.json').read_text())
    restored,report=base.with_layout_overrides(saved)
    assert not report['orphaned_targets']
    assert restored.layout_overrides(base)['targets']['/left']['placement']['x']==14
    state=SelectionState.from_json((FIXTURES/'selection.json').read_text())
    original=KeyedTable('measurements',dict(id=['sample-7','sample-9'],value=[2,4]))
    state.validate(original)
    assert state.selected_ids==('sample-7',) and state.visible_ids==('sample-9',)
    reordered=KeyedTable('measurements',dict(id=['sample-9','sample-7'],value=[4,2]))
    with pytest.raises(ValueError,match='explicitly rebase'): state.validate(reordered)
    rebased=state.rebase(reordered).state
    assert rebased.selected_ids==state.selected_ids and rebased.visible_ids==state.visible_ids


@pytest.mark.parametrize('change',['remove_export','remove_callable','remove_parameter','required','positional_order','keyword_only','new_required','optional'])
def test_call_shape_gate_distinguishes_additions_from_breaks(change):
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    old=dict(exports=['sample'],api={'sample':[
        dict(name='first',kind='POSITIONAL_OR_KEYWORD',required=True),
        dict(name='second',kind='POSITIONAL_OR_KEYWORD',required=False)]})
    new=json.loads(json.dumps(old))
    if change=='remove_export': new['exports']=[]
    elif change=='remove_callable': new['api']={}
    elif change=='remove_parameter': new['api']['sample'].pop()
    elif change=='required': new['api']['sample'][1]['required']=True
    elif change=='positional_order': new['api']['sample'].reverse()
    elif change=='keyword_only': new['api']['sample'][0]['kind']='KEYWORD_ONLY'
    else: new['api']['sample'].append(dict(name='option',kind='KEYWORD_ONLY',required=change=='new_required'))
    assert bool(checker.differences(old,new)) is (change!='optional')
