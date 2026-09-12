"""Mixed geographic feature identities, projection, picking and reconstruction."""
import copy
import html
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from inklet.experimental.browser import BrowserFigure, GeoFeatures, MapView, ScatterView, RevisionOption
from inklet.experimental.selection import KeyedTable, SelectionState
from test_browser_switching import mark_geometry
from test_browser_regions import marks as polygon_geometry

FIXTURE = Path(__file__).resolve().parents[1]/'examples/v4/fixtures/transport.geojson'


def source(): return json.loads(FIXTURE.read_text())


def figure(width=190, revised=False):
    raw = source()
    if revised: raw['features'][2]['geometry']['coordinates'][1][1] = .5
    geo = GeoFeatures.from_geojson(raw, source_name='Original fixture', attribution='Illustrative MIT data')
    table = KeyedTable('transport', dict(id=geo.feature_ids, position=list(range(6)), value=[None,2,3,4,5,6]))
    return BrowserFigure(table, [MapView('map',geo,(-1,-1,11,6),value='value',breaks=(3,5),
        colors=('#8aada3','#658fad','#ae7650')), ScatterView('values','position','value',(-1,6),(0,7))],width=width)


def test_mixed_geometry_snapshot_projection_and_whole_feature_filtering():
    raw = source(); geo = GeoFeatures.from_geojson(raw); digest = geo.digest
    raw['features'][-1]['geometry']['coordinates'][0][0] = 90
    assert geo.digest == digest and geo.features[-1][2][0] == (1,1)
    assert GeoFeatures.read(FIXTURE).digest == digest
    with pytest.raises(AttributeError): geo.features = ()
    f = figure(); layer = f.payload()['layers'][0]
    assert layer['clip'][2]/12 == pytest.approx(layer['clip'][3]/7, abs=1e-6)
    assert layer['geography']['geometry_types'] == ['LineString','MultiLineString','MultiPoint','MultiPolygon','Point','Polygon']
    assert layer['geography']['attribution'] == 'Illustrative MIT data'
    assert [m['kind'] for m in layer['marks']] == ['polygon']*3+['line']*4+['circle']*3
    assert all(m['ids']==['main-route','main-route'] for m in layer['marks'][3:5])
    assert layer['marks'][0]['color'] == '#d4d9d6'
    state = f.state(SelectionState.for_table(f.table, selected=['branches'],visible=['branches']))
    _, marks = mark_geometry(f.to_svg(state))
    assert sum(tag=='line' for tag,_ in marks) == 4 # two segments and two highlights
    assert not polygon_geometry(f.to_svg(state))
    revised = figure(160,True)
    transition = f.replace_data(revised.table, views=revised._views, width=160, state=state)
    assert transition.state()['selection']['selected_ids'] == ['branches']
    assert transition.report()['previous_scene_digest'] != transition.report()['scene_digest']
    assert f.payload()['layers'][0]['geometry_digest'] != revised.payload()['layers'][0]['geometry_digest']
    with pytest.raises(ValueError,match='revision'): revised.to_svg(state)


@pytest.mark.parametrize('kind,coords', [('Point',[True,0]),('Point',[181,0]),('Point',[0,float('nan')]),
    ('Point',[0,0,0]),('MultiPoint',[]),('LineString',[[0,0]]),('LineString',[[0,0],[0,0]]),
    ('LineString',[[179,0],[-179,1]]),('MultiLineString',[[]]),('GeometryCollection',[]),
    ('Polygon',[[[0,0],[1,1],[2,2],[0,0]]]),('MultiPolygon',[])])
def test_invalid_geometry_is_rejected(kind,coords):
    with pytest.raises(ValueError): GeoFeatures((('bad',kind,coords),))


@pytest.mark.parametrize('case',['duplicate','id','null','crs','feature-crs','geometry-crs','empty'])
def test_geojson_structure(case):
    raw=source()
    if case=='duplicate': raw['features'].append(copy.deepcopy(raw['features'][0]))
    elif case=='id': raw['features'][0]['id']=1
    elif case=='null': raw['features'][0]['geometry']=None
    elif case=='crs': raw['crs']={}
    elif case=='feature-crs': raw['features'][0]['crs']={}
    elif case=='geometry-crs': raw['features'][0]['geometry']['crs']={}
    else: raw['features']=[]
    with pytest.raises(ValueError): GeoFeatures.from_geojson(raw)


@pytest.mark.parametrize('changes',[{'radius_mm':True},{'line_width_mm':0},{'extent':(1,1,0,0)},
    {'breaks':(1,1),'value':'value'},{'colors':('red',)}, {'name':'bad name'}])
def test_map_style_validation(changes):
    args=dict(name='map',features=GeoFeatures.read(FIXTURE),extent=(0,0,10,5));args.update(changes)
    with pytest.raises(ValueError): MapView(**args)


def test_exact_join_and_numeric_values():
    view=MapView('map',GeoFeatures.read(FIXTURE),(0,0,10,5),value='value')
    with pytest.raises(ValueError,match='ID mismatch'):
        BrowserFigure(KeyedTable('bad',dict(id=['missing'],value=[1])),[view])
    with pytest.raises(ValueError,match='numeric'):
        BrowserFigure(KeyedTable('bad',dict(id=view.features.feature_ids,value=['x']*6)),[view])


CHECKS = r'''
<script>
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);};
 const query=(x,y)=>{const l=inklet.scene.layers[0],b=l.clip,e=l.extent;
   return inklet.pick(b[0]+(x-e[0])/(e[2]-e[0])*b[2],b[1]+(e[3]-y)/(e[3]-e[1])*b[3],0)?.id??null;};
 ok(query(4,1)==='terminal'&&query(4.05,1)==='terminal','topmost point identity');
 const terminal=inklet.scene.layers[0].marks.find(m=>m.kind==='circle'&&m.ids[0]==='terminal').geometry;
 for(let k=0;k<24;k++){
   const a=k*Math.PI/12;
   ok(inklet.pick(terminal[0]+.95*terminal[2]*Math.cos(a),terminal[1]+.95*terminal[2]*Math.sin(a),0)?.id==='terminal','marker edge lost across spatial-index cells');
 }
 ok(query(2,1)==='main-route'&&query(6,1)==='main-route','route endpoint identity');
 ok(query(2,4)==='branches'&&query(6,4)==='branches','disjoint route parts');
 ok(query(4,4)=== 'district','route parts were bridged');
 ok(query(1,1)==='stops'&&query(7,1)==='stops','multipoint identity');
 ok(query(4,2.5)===null,'polygon hole');
 ok(query(9.5,.5)==='islands'&&query(9.5,2.5)==='islands','multipolygon identity');
 ok(!document.getElementById('geography-status').hidden,'missing map provenance');
 const exports=[{index:0,state:inklet.state(),svg:inklet.exportSVG()}];
 inklet.select(['branches']);inklet.setVisible(['branches']);await inklet.render();
 ok(query(4,1)===null&&query(2,4)==='branches','whole feature filtering');
 exports.push({index:0,state:inklet.state(),svg:inklet.exportSVG()});
 await inkletDocument.switchRevision(1);
 ok(inklet.selected.has('branches'),'revision lost selection');
 ok(document.getElementById('geography-report').textContent.includes('Illustrative MIT data'),'revision lost provenance');
 exports.push({index:1,state:inklet.state(),svg:inklet.exportSVG()});
 return exports;
})().then(exports=>document.body.dataset.geoTest=JSON.stringify({exports})).catch(e=>document.body.dataset.geoTest=JSON.stringify({error:e.stack}));
</script>
'''


@pytest.mark.parametrize('renderer,backend',[('classic','svg'),('classic','canvas'),('classic','hybrid'),
    ('compiled','svg'),('compiled','canvas'),('compiled','webgl2')])
def test_geographic_picking_revisions_and_static_export(tmp_path,renderer,backend):
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome: pytest.skip('Chrome/Chromium not installed')
    original,revised=figure(),figure(160,True)
    page=original.to_html(renderer=renderer,backend=backend,revisions=[RevisionOption('Revised',revised,'Same fixture')])
    path=tmp_path/'index.html';path.write_text(page.replace('</html>',CHECKS+'</html>'))
    result=subprocess.run([chrome,'--headless','--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle',
        '--use-angle=swiftshader','--dump-dom','--virtual-time-budget=8000',f'--user-data-dir={tmp_path}/profile',path.as_uri()],
        capture_output=True,text=True,timeout=40)
    match=re.search(r'data-geo-test="([^"]+)"',result.stdout)
    assert match,result.stderr[-1500:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    for export in report['exports']:
        expected=(original,revised)[export['index']].to_svg(export['state'])
        assert mark_geometry(export['svg']) == mark_geometry(expected)
        assert polygon_geometry(export['svg']) == polygon_geometry(expected)


def test_complete_transport_workflow_rebases_removed_geometry_and_resizing():
    import runpy
    recipe = runpy.run_path(str(FIXTURE.parents[1]/'transport_map.py'))
    original = recipe['make_scene']()
    rerouted = recipe['make_scene']('rerouted')
    removed = recipe['make_scene']('removed')
    before = original.to_svg()
    state = original.state(SelectionState.for_table(original.table,selected=['branches','main-route'],visible=['branches','main-route']))
    with pytest.raises(ValueError,match='removed'):
        original.replace_data(removed.table,views=removed._views,state=state)
    transfer = original.replace_data(removed.table,views=removed._views,state=state,missing='drop')
    assert transfer.report()['removed_selected'] == ['branches']
    assert transfer.state()['selection']['selected_ids'] == ['main-route']
    assert transfer.state()['selection']['visible_ids'] == ['main-route']
    route = original.replace_data(rerouted.table,views=rerouted._views,state=state)
    assert route.report()['changed_ids'] == []
    assert route.report()['previous_scene_digest'] != route.report()['scene_digest']
    for width in (170,210):
        resized = route.figure.replace_data(route.figure.table,state=route.state(),width=width)
        assert resized.state()['selection']['selected_ids'] == ['branches','main-route']
        assert resized.figure.to_svg(resized.state()) == resized.figure.to_svg(json.loads(json.dumps(resized.state())))
    assert original.to_svg() == before
