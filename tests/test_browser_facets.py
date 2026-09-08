"""Facets retain explicit categories, global row identity and source-order breaks."""
from dataclasses import FrozenInstanceError
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import (
    BarView, BrowserFigure, FacetView, GeoRegions, LineView, RegionView, RevisionOption, ScatterView,
)
from inklet.experimental.selection import KeyedTable, SelectionState


def table():
    return KeyedTable('facets', dict(
        id=list('abcdefghijkl'), x=[0, 0, 1, 1, 2, 2, 3, 4, 3, 4, 1, 2],
        y=[1, 2, 3, -1, None, 2, -2, 2, None, 1, 1, 1],
        group=['north', 'south', 'north', 'south', 'north', 'south',
               'north', 'north', 'south', 'south', 'other', None],
    ))


def facet(kind=LineView, name='trend', **kwargs):
    return FacetView(kind(name, 'x', 'y', (-1, 5), (-3, 4)), 'group',
                     ('south', 'north', 'empty'), ('South', 'North', 'No observations'), **kwargs)


def scene():
    return BrowserFigure(table(), [facet(), facet(BarView, 'bars')], width=240, columns=3)


def ids(layer):
    return [p[0] for p in layer['points']]


def test_explicit_order_membership_missing_values_and_global_identity():
    figure=scene(); p=figure.payload(); layers=p['layers']
    assert [layer['name'] for layer in layers]==[
        f'{name}__facet_{index}' for name in ('trend', 'bars') for index in range(3)]
    assert p['row_ids']==list(table().row_ids)
    assert p['columns']=={k:list(v) for k,v in table().columns.items()}
    assert p['data_digest']==table().digest
    assert p['facet_groups']==[
        dict(name=name, column='group', values=['south', 'north', 'empty'], unassigned_ids=['k', 'l'])
        for name in ('trend', 'bars')]
    for group in (layers[:3], layers[3:]):
        assert [ids(layer) for layer in group]==[list('bdfj'), list('acgh'), []]
        assert [layer['missing'] for layer in group]==[1, 1, 0]
        assert [layer['facet'] for layer in group]==[
            dict(column='group', value=v, label=label)
            for v,label in zip(('south','north','empty'), ('South','North','No observations'))]
        assert all(layer['color']=='#34786b' for layer in group)
    assert [m['ids'] for m in layers[0]['marks']]==[['b','d'], ['d','f']]
    assert [m['ids'] for m in layers[1]['marks']]==[['a','c'], ['g','h']]
    assert layers[2]['marks']==layers[5]['marks']==[]
    # Unassigned rows remain valid global selections, including a null category.
    selection,_=figure.validate_state(figure.state(SelectionState.for_table(figure.table, selected=['k','l'])))
    assert selection.selected_ids==('k','l')


def test_shared_domains_give_equal_physical_scales_and_empty_panels():
    p=scene().payload()
    widths=[layer['clip'][2] for layer in p['layers']]
    heights=[layer['clip'][3] for layer in p['layers']]
    assert widths==pytest.approx([widths[0]]*6, abs=1e-6)
    assert heights==pytest.approx([heights[0]]*6, abs=1e-6)
    assert min(widths)>0 and min(heights)>0
    # Independently project source coordinates into each panel's measured box.
    rows={key:(x,y) for key,x,y in zip(table().row_ids,table().columns['x'],table().columns['y'])}
    for layer in p['layers']:
        left,top,width,height=layer['clip']
        for key,x,y in layer['points']:
            sx,sy=rows[key]
            assert x==pytest.approx(left+(sx+1)/6*width,abs=1e-6)
            assert y==pytest.approx(top+(4-sy)/7*height,abs=1e-6)


def test_facet_snapshot_default_labels_and_definition_limits():
    values=['south','north']; labels=['South','North']
    definition=FacetView(ScatterView('points','x','y',(-1,5),(-3,4)), 'group', values, labels)
    values.append('empty'); labels[0]='Changed'
    assert definition.values==('south','north') and definition.labels==('South','North')
    assert definition.name=='points'
    with pytest.raises(FrozenInstanceError): definition.column='other'
    default=FacetView(definition.view,'group',('south','north'))
    assert default.labels==default.values
    categories=tuple(f'category-{i}' for i in range(12))
    twelve=FacetView(definition.view,'group',categories)
    assert len(BrowserFigure(table(),[twelve]).payload()['layers'])==12
    with pytest.raises(ValueError): BrowserFigure(table(),[twelve, ScatterView('extra','x','y',(-1,5),(-3,4))])
    with pytest.raises(ValueError): BrowserFigure(table(),[facet(ScatterView,f'p{i}') for i in range(5)])
    # Normal plots must not acquire category metadata or change names.
    plain=BrowserFigure(table(),[definition.view]).payload()
    assert 'facet_groups' not in plain and 'facet' not in plain['layers'][0]
    assert plain['layers'][0]['name']=='points'


@pytest.mark.parametrize('kwargs', [
    {'column':''}, {'column':1}, {'values':()}, {'values':('a','a')},
    {'values':('a','')}, {'values':('a',None)}, {'values':'north'},
    {'values':tuple(str(i) for i in range(13))}, {'labels':('Only one',)},
    {'labels':('North','','Empty')}, {'labels':('North',None,'Empty')},
    {'view':object()},
])
def test_invalid_facet_definition(kwargs):
    args=dict(view=LineView('trend','x','y',(-1,5),(-3,4)), column='group',
              values=('north','south','empty'))
    args.update(kwargs)
    with pytest.raises((ValueError,TypeError)): FacetView(**args)


@pytest.mark.parametrize('value',[1, True, 1.5])
def test_non_string_categories_rejected(value):
    data=KeyedTable('facets',dict(id=['a'],x=[0],y=[1],group=[value]))
    with pytest.raises(ValueError): BrowserFigure(data,[facet()])


def test_missing_category_column_and_expanded_name_collisions_rejected():
    data=KeyedTable('facets',dict(id=['a'],x=[0],y=[1]))
    with pytest.raises(ValueError): BrowserFigure(data,[facet()])
    with pytest.raises(ValueError): BrowserFigure(table(),[facet(), facet(BarView)])
    with pytest.raises(ValueError):
        BrowserFigure(table(),[facet(), ScatterView('trend__facet_0','x','y',(-1,5),(-3,4))])


def test_scatter_facets_default_two_columns_and_region_rejection():
    layers=BrowserFigure(table(),[facet(ScatterView,'points')]).payload()['layers']
    assert [ids(layer) for layer in layers]==[list('bdfj'),list('acgh'),[]]
    assert all('marks' not in layer and layer['radius']==.45 for layer in layers)
    # The default wraps expanded panels at two columns, including an empty one.
    assert layers[0]['clip'][1]==layers[1]['clip'][1]
    assert layers[2]['clip'][1]>layers[0]['clip'][1]
    assert layers[2]['clip'][0]==layers[0]['clip'][0]
    regions=GeoRegions.from_geojson(dict(type='FeatureCollection',features=[
        dict(type='Feature',id='a',geometry=dict(type='Polygon',coordinates=[
            [[0,0],[1,0],[1,1],[0,1],[0,0]]]))]))
    with pytest.raises((ValueError,TypeError)):
        FacetView(RegionView('map',regions,(-1,-1,2,2)),'group',('north',))


def test_category_names_and_labels_are_not_interpreted_as_html():
    dangerous='</script><script>window.injected=true</script>'
    data=KeyedTable('facets',dict(id=['a'],x=[0],y=[1],group=[dangerous]))
    view=FacetView(ScatterView('points','x','y',(-1,1),(0,2)),'group',(dangerous,))
    figure=BrowserFigure(data,[view])
    assert ids(figure.payload()['layers'][0])==['a']
    assert figure.payload()['layers'][0]['facet']['label']==dangerous
    assert '<script>window.injected=true</script>' not in figure.to_html()


def test_replacement_rebuilds_membership_but_preserves_hidden_selected_ids():
    original=scene(); snapshot=original.payload()
    columns={k:list(v) for k,v in original.table.columns.items()}
    columns['group'][0]='south'; columns['group'][1]='other'
    revised=KeyedTable('facets',columns)
    state=original.state(SelectionState.for_table(original.table,selected=['a','b','l'],visible=['a','c']))
    result=original.replace_data(revised,state=state)
    assert original.payload()==snapshot
    assert result.report()['changed_ids']==['a','b']
    assert result.state()['selection']['selected_ids']==['a','b','l']
    assert result.state()['selection']['visible_ids']==['a','c']
    layers=result.figure.payload()['layers']
    assert ids(layers[0])==list('adfj') and ids(layers[1])==list('cgh')
    assert layers[2]['marks']==[] and layers[5]['marks']==[]
    assert result.figure.payload()['facet_groups'][0]['unassigned_ids']==['b','k','l']
    with pytest.raises(ValueError): result.figure.validate_state(state)


CHECKS=r'''
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);}, exports=[];
 ok(!document.getElementById('facet-status').hidden&&JSON.parse(document.getElementById('facet-rows').textContent).every(group=>group.unassigned_ids.join('')==='kl'),'initial unassigned category diagnostics');
 let queries=0;
 function oracle(r,x,y){
  let best=null,score=Infinity;
  for(const [layerIndex,l] of r.scene.layers.entries()){
   const b=l.clip;if(x<b[0]||x>b[0]+b[2]||y<b[1]||y>b[1]+b[3])continue;
   for(const m of l.marks){
    if(!m.ids.every(id=>r.visible===null||r.visible.has(id)))continue;
    const g=m.geometry;let d,id=m.ids[0],limit=.15;
    if(m.kind==='rect')d=Math.hypot(x-Math.min(Math.max(x,g[0]),g[0]+g[2]),y-Math.min(Math.max(y,g[1]),g[1]+g[3]));
    else{
     const dx=g[2]-g[0],dy=g[3]-g[1],den=dx*dx+dy*dy;
     const t=den?Math.max(0,Math.min(1,((x-g[0])*dx+(y-g[1])*dy)/den)):1;
     d=Math.hypot(x-g[0]-t*dx,y-g[1]-t*dy);id=m.ids[t<.5-1e-12?0:1];limit+=m.width/2;
    }
    if(d<=limit&&(d<score-1e-10||Math.abs(d-score)<1e-10)){score=d;best={id,layerIndex};}
   }
  }return best;
 }
 for(const backend of ['svg','canvas','hybrid']){
  const r=inklet;r.setBackend(backend);
  for(const visible of [null,['a','c','d','f','g','h'],[]]){
   r.setVisible(visible);r.select(['a','b','l']);
   const positions=[];
   for(const l of r.scene.layers)for(const m of l.marks){
    const g=m.geometry;
    positions.push([g[0],g[1]],m.kind==='rect'?[g[0]+g[2]/2,g[1]+g[3]/2]:[(g[0]+g[2])/2,(g[1]+g[3])/2]);
   }
   for(let n=0;n<350;n++)positions.push([(n*37.317)%r.scene.width,(n*17.219)%r.scene.height]);
   for(const [x,y] of positions){
    const want=oracle(r,x,y),got=r.pick(x,y,.15);queries++;
    ok((want?.id??null)===(got?.id??null)&&(want?.layerIndex??null)===(got?.layerIndex??null),'facet pick mismatch '+JSON.stringify({x,y,want,got:got&&{id:got.id,layerIndex:got.layerIndex}}));
   }
   r.setViewport([5,8,r.scene.width/1.3,r.scene.height/1.3]);
   const state=r.state();r.select([]);r.loadState(state);
   ok(r.selected.has('l'),'unassigned row selection lost');
   exports.push({state,svg:r.exportSVG()});
  }
 }
 inklet.setVisible(['a','c']);inklet.select(['a','b','l']);
 await inkletDocument.switchRevision(1);
 ok(inklet.selected.has('a')&&inklet.selected.has('b')&&inklet.selected.has('l'),'revision lost global selection');
 ok(inklet.scene.layers[0].points.map(p=>p[0]).join('')==='adfj','replacement did not move facet membership');
 ok(inklet.scene.layers[2].marks.length===0,'empty facet removed or populated');
 ok(!document.getElementById('facet-status').hidden&&JSON.parse(document.getElementById('facet-rows').textContent).every(group=>group.unassigned_ids.join('')==='bkl'),'revision did not refresh unassigned category diagnostics');
 return {queries,exports,revised:{state:inklet.state(),svg:inklet.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def geometry(svg):
    root=ET.fromstring(svg); result=[]
    for group in (root[1],root[-1]):
        for element in group.iter():
            tag=element.tag.rsplit('}',1)[-1]
            if tag not in ('line','rect') or ('fill' not in element.attrib and 'stroke' not in element.attrib): continue
            attrs={}
            for key,value in element.attrib.items():
                try: attrs[key]=float(value)
                except ValueError: attrs[key]=value
            result.append((tag,attrs))
    return root.attrib['viewBox'].split(),result


@pytest.mark.parametrize('dpr',[1,2])
def test_faceted_browser_picking_export_and_revision_switch(tmp_path,dpr):
    browser=next((p for n in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(n))),None)
    if browser is None: pytest.skip('Chrome/Chromium not installed')
    original=scene(); columns={k:list(v) for k,v in original.table.columns.items()}
    columns['group'][0]='south'; columns['group'][1]='other'
    revised=original.replace_data(KeyedTable('facets',columns)).figure
    page=tmp_path/'index.html'
    page.write_text(original.to_html(revisions=[RevisionOption('Reclassified',revised,'Explicit category revision')])
                    .replace('</html>','<script>'+CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1])); assert 'error' not in report,report
    assert report['queries']>3000
    for exported in report['exports']:
        assert geometry(original.to_svg(exported['state']))==geometry(exported['svg'])
    assert geometry(revised.to_svg(report['revised']['state']))==geometry(report['revised']['svg'])
