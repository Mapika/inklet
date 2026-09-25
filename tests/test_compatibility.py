"""Released-wheel API and saved-file fixtures protect migration across versions."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest
import inklet as i
from inklet.experimental.project import FigureProject
from inklet.experimental.selection import KeyedTable, SelectionState

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(__file__).with_name('fixtures')/'compatibility'
API_42=json.loads((FIXTURES/'api-4.2.json').read_text())
EXPERIMENTAL_42=[m for m in API_42['modules'] if m.startswith('inklet.experimental.')]

# ---------------------------------------------------------------------------
# PLANNED 4.3 MOVES: released experimental module -> new stable home.
# The old path stays a silent alias returning the *same* objects. Entries whose
# new module does not exist yet are skipped by the identity test; correct an
# entry here when its move lands somewhere else.
# ---------------------------------------------------------------------------
PLANNED_MOVES={
    # microscopy -> inklet.volume
    'inklet.experimental.channels':'inklet.volume',
    'inklet.experimental.contours':'inklet.volume',
    'inklet.experimental.measurements':'inklet.volume',
    'inklet.experimental.regions':'inklet.volume',
    'inklet.experimental.sections':'inklet.volume',
    'inklet.experimental.slabs':'inklet.volume',
    'inklet.experimental.tiff':'inklet.volume',
    'inklet.experimental.volume':'inklet.volume',
    # selection -> inklet.selection; temporal becomes a private module
    'inklet.experimental.selection':'inklet.selection',
    'inklet.experimental.temporal':'inklet.selection._temporal',
    # project -> inklet.project
    'inklet.experimental.project':'inklet.project',
    'inklet.experimental.project.assets':'inklet.project.assets',
    'inklet.experimental.project.identity':'inklet.project.identity',
    # layout_editor -> inklet.editor
    'inklet.experimental.layout_editor':'inklet.editor',
    # scene_viewer -> private inklet.render._viewer
    'inklet.experimental.scene_viewer':'inklet.render._viewer',
}
STABLE_NAMESPACES=('inklet.volume','inklet.selection','inklet.project','inklet.editor')
HEAVY_MODULES=('numpy','pandas','polars','PIL','skimage','scipy','tifffile','inklet.volume')


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def module_exists(name):
    try: return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError: return False


def released_names(snapshot,module):
    return [key.partition(':')[2] for key in snapshot['exports'] if key.partition(':')[0]==module]


def moved_identity_problems(moves,snapshot=API_42):
    """Released names of each old module that are not the same object at the new home."""
    problems=[]
    for old,new in moves.items():
        before,after=importlib.import_module(old),importlib.import_module(new)
        for name in released_names(snapshot,old):
            if not hasattr(after,name): problems.append(f'{old}:{name}: missing from {new}')
            elif getattr(before,name) is not getattr(after,name): problems.append(f'{old}:{name}: not the object in {new}')
    return problems


def test_released_top_level_api_retains_public_call_shapes():
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    baseline=json.loads((FIXTURES/'api-3.1.json').read_text())
    assert baseline['version']=='3.1.0'
    assert checker.differences(baseline,checker.inventory(i))==[]


@pytest.mark.parametrize('fixture',['api-3.1.json','api-4.2.json'])
def test_released_api_inventories_pass_the_release_checker(fixture):
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    text=(FIXTURES/fixture).read_text()
    assert checker.dump(json.loads(text))==text
    assert checker.check(json.loads(text))[1]==[]


def test_released_42_inventory_covers_top_level_and_every_experimental_module():
    assert API_42['version']=='4.2.0'
    assert API_42['modules'][0]=='inklet' and len(EXPERIMENTAL_42)>=30
    assert {'inklet.experimental.volume','inklet.experimental.selection','inklet.experimental.project',
            'inklet.experimental.layout_editor','inklet.experimental.scene_viewer',
            'inklet.experimental.browser.grid'}<=set(EXPERIMENTAL_42)
    assert 'inklet.experimental.volume:Volume.crop' in API_42['api']
    assert set(PLANNED_MOVES)<=set(EXPERIMENTAL_42)


@pytest.mark.parametrize('module',EXPERIMENTAL_42)
def test_released_experimental_names_import_from_old_path_with_same_call_shape(module):
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    names=released_names(API_42,module)
    exec(f'from {module} import {", ".join(names)}',{})
    keep=lambda key: key.partition(':')[0]==module
    old=dict(API_42,modules=[module],exports=[k for k in API_42['exports'] if keep(k)],
             api={k:v for k,v in API_42['api'].items() if keep(k)})
    assert checker.check(old)[1]==[]


@pytest.mark.parametrize('old,new',sorted(PLANNED_MOVES.items()))
def test_moved_experimental_objects_are_their_stable_homes(old,new):
    if not module_exists(new): pytest.skip(f'{new} does not exist yet; {old} has not moved')
    assert moved_identity_problems({old:new})==[]


def test_moved_identity_helper_reports_copies_and_missing_names(monkeypatch):
    shared,copy=object(),object()
    monkeypatch.setitem(sys.modules,'compat_old',types.SimpleNamespace(A=shared,B=copy,C=shared))
    monkeypatch.setitem(sys.modules,'compat_new',types.SimpleNamespace(A=shared,B=object()))
    snapshot=dict(exports=['compat_old:A','compat_old:B','compat_old:C'])
    assert moved_identity_problems({'compat_old':'compat_new'},snapshot)==[
        'compat_old:B: not the object in compat_new','compat_old:C: missing from compat_new']


def test_import_inklet_stays_light():
    script=('import json,sys,inklet;'
            f'print(json.dumps(sorted(m for m in sys.modules for h in {HEAVY_MODULES!r} if m==h or m.startswith(h+"."))))')
    source=str(Path(i.__file__).resolve().parents[1])
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(filter(None,[source,os.environ.get('PYTHONPATH')])))
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,env=env,check=True)
    assert json.loads(result.stdout)==[]


@pytest.mark.parametrize('name',STABLE_NAMESPACES)
def test_stable_namespaces_declare_all(name):
    if not module_exists(name): pytest.skip(f'{name} does not exist yet')
    module=importlib.import_module(name)
    assert isinstance(getattr(module,'__all__',None),(list,tuple)),f'{name} must define __all__'
    assert [n for n in module.__all__ if not hasattr(module,n)]==[]


def test_checker_reads_bare_names_as_top_level_and_reports_missing_modules():
    checker=load(ROOT/'tools/check_compatibility.py','compatibility_checker')
    shape=[dict(name='x',kind='POSITIONAL_OR_KEYWORD',required=True)]
    bare=dict(exports=['f'],api={'f':shape})
    assert checker.differences(bare,dict(modules=['inklet'],exports=['inklet:f'],api={'inklet:f':shape}))==[]
    old=dict(modules=['inklet','pkg.gone'],exports=['inklet:f','pkg.gone:G'],
             api={'inklet:f':shape,'pkg.gone:G.run':shape})
    new=dict(modules=['inklet'],exports=['inklet:f'],api={'inklet:f':shape},errors={'pkg.gone':'ImportError: x'})
    assert checker.differences(old,new)==['pkg.gone: module unavailable (ImportError: x)']
    report=checker.inventory(['inklet.experimental.volume','inklet.no_such_module'],owner='inklet')
    assert 'inklet.experimental.volume:Volume.crop' in report['api']
    assert list(report['errors'])==['inklet.no_such_module']


def test_released_fixture_bytes_match_recorded_origins():
    provenance=json.loads((FIXTURES/'provenance.json').read_text())
    assert set(provenance['releases'])=={'3.1.0','4.0.0.dev16','4.0.0rc1','4.2.0'}
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
