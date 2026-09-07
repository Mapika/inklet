"""Revisions must preserve identity without accepting stale scene state."""
import csv
import html
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import BrowserFigure, BrowserScatter, LineView, ScatterView
from inklet.experimental.selection import KeyedTable, SelectionState

ROOT=Path(__file__).resolve().parents[1]


def make_scene():
    table=KeyedTable('series',dict(id=['a','b','c'],x=[0,1,2],y=[1,2,3]))
    return BrowserFigure(table,[LineView('line','x','y',(0,4),(0,8)),
                               ScatterView('points','x','y',(0,4),(0,8))])


def test_replacement_recompiles_geometry_and_reports_changes_without_mutation():
    original=make_scene();snapshot=original.payload();old_svg=original.to_svg()
    state=original.state(SelectionState.for_table(original.table,selected=['a'],visible=['b','c']))
    replacement=KeyedTable('series',dict(id=['c','a','d'],x=[2,0,3],y=[3,7,4]))
    with pytest.raises(ValueError,match='removed selected or filtered'):
        original.replace_data(replacement,state=state)
    result=original.replace_data(replacement,state=state,missing='drop')
    report=result.report();selection,viewport=result.figure.validate_state(result.state())
    assert report['removed_ids']==['b'] and report['added_ids']==['d'] and report['changed_ids']==['a']
    assert report['order_changed'] and report['removed_visible']==['b'] and report['removed_selected']==[]
    assert selection.selected_ids==('a',) and selection.visible_ids==('c',)  # retain hidden selection
    assert [m['ids'] for m in result.figure.payload()['layers'][0]['marks']]==[['c','a'],['a','d']]
    assert result.figure.payload()['layers'][1]['points'][1]!=snapshot['layers'][1]['points'][0]
    assert original.payload()==snapshot and original.to_svg()==old_svg
    assert report['previous_scene_digest']==state['scene_digest']
    assert report['scene_digest']==result.state()['scene_digest']
    with pytest.raises(ValueError,match='different scene revision'):result.figure.validate_state(state)
    with pytest.raises(ValueError,match='different scene revision'):original.validate_state(result.state())
    # Mutating returned JSON cannot alter the stored result.
    result.state()['selection']['selected_ids'].clear();result.report()['removed_ids'].clear()
    assert result.state()['selection']['selected_ids']==['a'] and result.report()['removed_ids']==['b']


@pytest.mark.parametrize('visible,expected',[(None,None),([],[]),(['a'],['a'])])
def test_added_rows_respect_all_empty_and_explicit_visibility(visible,expected):
    scene=make_scene();data=KeyedTable('series',dict(id=['a','d'],x=[0,3],y=[1,4]))
    state=scene.state(SelectionState.for_table(scene.table,selected=['c'],visible=visible))
    with pytest.raises(ValueError,match='removed selected'):scene.replace_data(data,state=state)
    result=scene.replace_data(data,state=state,missing='drop')
    assert result.state()['selection']['visible_ids']==expected
    assert result.state()['selection']['selected_ids']==[] and result.report()['removed_selected']==['c']


def test_layout_changes_reset_viewport_unless_explicitly_preserved():
    scene=make_scene();state=scene.state(viewport=[10,12,60,25])
    result=scene.replace_data(scene.table,state=state,width=110,columns=1)
    p=result.figure.payload()
    assert result.state()['viewport']==[0,0,p['width'],p['height']]
    assert result.report()['changed_ids']==[] and result.report()['data_digest']==scene.table.digest
    assert result.report()['scene_digest']!=state['scene_digest']
    result=scene.replace_data(scene.table,state=state,width=110,columns=1,viewport='preserve')
    assert result.state()['viewport']==state['viewport']
    huge=scene.state(viewport=[0,0,scene.payload()['width']*100,50])
    with pytest.raises(ValueError,match='preview limits'):
        scene.replace_data(scene.table,state=huge,width=110,viewport='preserve')


def test_replacement_rejects_wrong_source_key_table_and_invalid_views():
    scene=make_scene();state=scene.state();snapshot=scene.payload()
    with pytest.raises(ValueError,match='different scene'):scene.replace_data(scene.table,state=dict(state,scene_digest='wrong'))
    with pytest.raises(ValueError,match='key column'):
        scene.replace_data(KeyedTable('series',dict(key=['a'],x=[0],y=[1]),key='key'))
    with pytest.raises(ValueError,match='different table'):
        scene.replace_data(KeyedTable('unrelated',scene.table.columns))
    with pytest.raises(ValueError,match='unknown column'):
        scene.replace_data(KeyedTable('series',dict(id=['a'],x=[0])))
    with pytest.raises(ValueError,match='viewport'):scene.replace_data(scene.table,viewport='auto')
    with pytest.raises(ValueError,match='missing'):scene.replace_data(scene.table,missing='ignore')
    assert scene.payload()==snapshot and scene.state()==state


def test_schema_and_json_type_changes_are_reported_and_legacy_entry_point_works():
    table=KeyedTable('series',dict(id=['a'],x=[1],y=[2],flag=[True]))
    scene=BrowserScatter(table,[ScatterView('p','x','y',(0,2),(0,4))])
    data=KeyedTable('series',dict(id=['a'],x=[1],y=[2],flag=[1]))
    assert scene.replace_data(data).report()['changed_ids']==['a']
    data=KeyedTable('series',dict(id=['a'],x=[1],y=[2],label=['new']))
    result=scene.replace_data(data)
    assert result.report()['added_columns']==['label'] and result.report()['removed_columns']==['flag']
    assert result.report()['changed_ids']==['a']
    assert result.figure.payload()['schema']=='inklet.browser-figure/0.1'


def test_map_geometry_join_is_still_explicit():
    recipe=runpy.run_path(str(ROOT/'examples/v4/world_population.py'));scene=recipe['make_scene']()
    data=KeyedTable(scene.table.name,scene.table.subset(['HUN','FRA']))
    with pytest.raises(ValueError,match='region/table ID mismatch'):scene.replace_data(data)
    result=scene.replace_data(data,views=recipe['make_views'](data))
    assert set(result.figure.payload()['row_ids'])=={'HUN','FRA'}
    assert {key for layer in result.figure.payload()['layers'] for mark in layer['marks'] for key in mark['ids']}=={'HUN','FRA'}


def run_example(*args):
    return subprocess.run([sys.executable,str(ROOT/'examples/v4/world_population.py'),*map(str,args)],
                          cwd=ROOT,capture_output=True,text=True,timeout=30)


def test_real_map_rebase_drop_report_and_reconstruction(tmp_path):
    recipe=runpy.run_path(str(ROOT/'examples/v4/world_population.py'));scene=recipe['make_scene']()
    old=scene.state(SelectionState.for_table(scene.table,selected=['HUN','TWN'],visible=['FRA','TWN']),viewport=[5,10,100,80])
    state=tmp_path/'old.json';state.write_text(json.dumps(old))
    output=tmp_path/'revised'
    failed=run_example('--year',2019,'--rebase-state',state,'--output',output)
    assert failed.returncode!=0 and not output.exists()
    success=run_example('--year',2019,'--rebase-state',state,'--missing','drop','--output',output)
    assert success.returncode==0,success.stderr
    report=json.loads((output/'revision.json').read_text());current=json.loads((output/'view.json').read_text())
    assert report['removed_ids']==['ATF','CYN','ERI','FLK','SAH','SOL','TWN']
    assert report['removed_selected']==report['removed_visible']==['TWN']
    assert report['changed_ids']==[] and report['source']['year']==2019
    assert current['selection']['selected_ids']==['HUN'] and current['selection']['visible_ids']==['FRA']
    with (output/'population.csv').open() as stream: rows=list(csv.DictReader(stream))
    assert len(rows)==169 and all(float(row['population_year'])==2019 for row in rows)
    restored=tmp_path/'restored'
    result=run_example('--year',2019,'--state',output/'view.json','--output',restored)
    assert result.returncode==0,result.stderr
    assert (restored/'figure.svg').read_bytes()==(output/'figure.svg').read_bytes()
    # Reopening without the matching source revision must still fail.
    assert run_example('--state',output/'view.json','--output',tmp_path/'wrong').returncode!=0


def test_csv_replacement_derives_values_and_identifies_supplied_source(tmp_path):
    path=tmp_path/'population.csv'
    path.write_text('id,country,continent,population,population_year,population_millions\nHUN,Hungary,Europe,1000000,2020,999\n')
    output=tmp_path/'result';result=run_example('--csv',path,'--output',output)
    assert result.returncode==0,result.stderr
    page=(output/'index.html').read_text();report=json.loads((output/'revision.json').read_text())
    payload=json.loads(re.search(r'id="scene">(.*?)</script>',page,re.S)[1])
    assert payload['columns']['population_millions']==[1.0]
    assert report['changed_ids']==['HUN'] and report['source']['kind']=='user-supplied CSV'
    assert 'supplied CSV population.csv' in page and 'mostly 2019' not in page
    # Restoring a target without Hungary must not first rebase the recipe's
    # default Hungary selection. The supplied target state is authoritative.
    path.write_text('id,country,continent,population,population_year\nFRA,France,Europe,67059887,2019\n')
    target=tmp_path/'france'
    assert run_example('--csv',path,'--missing','drop','--output',target).returncode==0
    assert run_example('--csv',path,'--state',target/'view.json','--output',tmp_path/'france-restored').returncode==0
    path.write_text('id,country,continent,population,population_year\nNEW,Unknown,Europe,5,2019\n')
    assert run_example('--csv',path,'--output',tmp_path/'bad').returncode!=0


@pytest.mark.parametrize('dpr',[1,2])
def test_browser_revised_state_rejects_old_scene_and_keeps_exports(tmp_path,dpr):
    browser=next((p for n in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(n))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    recipe=runpy.run_path(str(ROOT/'examples/v4/world_population.py'));scene=recipe['make_scene']()
    data=KeyedTable(scene.table.name,scene.table.subset(['HUN','FRA']))
    result=scene.replace_data(data,state=scene.state(SelectionState.for_table(scene.table,selected=['HUN'])),views=recipe['make_views'](data))
    checks='''
    (async()=>{await inklet.ready;const before=JSON.stringify(inklet.state());
      let rejected=false;try{inklet.loadState(OLD_STATE);}catch(e){rejected=true;}
      if(!rejected||JSON.stringify(inklet.state())!==before)throw Error('stale state changed revision');
      const exports=[];
      for(const backend of ['svg','canvas','hybrid']){
        inklet.setBackend(backend);
        if(!inklet.selected.has('HUN')||inklet.rowSet.size!==2)throw Error('revision lost rows/selection');
        exports.push(inklet.exportSVG());
      }
      return {exports};
    })().then(r=>document.body.dataset.revisionTest=JSON.stringify(r))
      .catch(e=>document.body.dataset.revisionTest=JSON.stringify({error:e.message}));
    '''.replace('OLD_STATE',json.dumps(scene.state()))
    page=result.figure.to_html(state=result.state(),search_columns=('country',))
    path=tmp_path/'index.html';path.write_text(page.replace('</html>','<script>'+checks+'</script></html>'))
    process=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',path.as_uri()],
        capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stderr[-2000:]
    match=re.search(r'data-revision-test="([^"]*)"',process.stdout);assert match,process.stdout[-3000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    # Compare actual vector path geometry and styles, independent of XML formatting/IDs.
    def paths(svg):
        result=[]
        for e in ET.fromstring(svg).iter():
            if e.tag.endswith('}path') and e.get('fill-rule')=='evenodd':
                attrs=dict(e.attrib);attrs['stroke-width']=float(attrs['stroke-width'])
                result.append(attrs)
        return result
    expected=paths(result.figure.to_svg(result.state()))
    assert expected and all(paths(svg)==expected for svg in report['exports'])
