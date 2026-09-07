"""GeoJSON contracts, native path oracle and region/static export agreement."""
import copy
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from inklet.experimental.browser import BrowserFigure, GeoRegions, RegionView
from inklet.experimental.selection import KeyedTable, SelectionState

FIXTURE=Path(__file__).resolve().parents[1]/'examples/v4/fixtures/region-shapes.geojson'


def source():return json.loads(FIXTURE.read_text())


def scene(width=190,extent=(-.2,-.2,8.2,6.2)):
    regions=GeoRegions.from_geojson(source())
    table=KeyedTable('regions',dict(code=regions.feature_ids,value=[None,20,40,60]),key='code')
    return BrowserFigure(table,[RegionView('map',regions,extent,value='value',breaks=(20,40,60),
        colors=('#eeeeee','#aacccc','#559999','#225555'),value_label='Value / a.u.')],width=width)


def test_region_snapshot_rings_join_and_explicit_color_bins():
    raw=source();regions=GeoRegions.from_geojson(raw);digest=regions.digest
    raw['features'][0]['geometry']['coordinates'][0][0][0]=99
    assert regions.features[0][1][0][0][0]==(0,0) and regions.digest==digest
    with pytest.raises(AttributeError):regions.features=()
    s=scene();layer=s.payload()['layers'][0]
    assert [m['ids'][0] for m in layer['marks']]==['reserve','east','islands','islands','overlap']
    assert [m['color'] for m in layer['marks']]==['#d4d9d6','#aacccc','#559999','#559999','#225555']
    assert layer['legend'][-1]==['Missing','#d4d9d6']
    assert len(layer['marks'][0]['geometry'])==2
    assert s.payload()['key']=='code'
    # Both fitted physical axes use the same degree scale.
    assert layer['clip'][2]/8.4==pytest.approx(layer['clip'][3]/6.4,abs=1e-6)
    other=scene(150);assert other.payload()['scene_digest']!=s.payload()['scene_digest']
    selection=SelectionState.for_table(s.table,selected=['islands'],visible=['islands'])
    svg=s.to_svg(s.state(selection));root=ET.fromstring(svg)
    assert len([e for e in root[1].iter() if e.attrib.get('fill-rule')=='evenodd'])==2
    assert len([e for e in root[-1].iter() if e.attrib.get('fill-rule')=='evenodd'])==2
    with pytest.raises(ValueError,match='revision'):other.to_svg(s.state(selection))


@pytest.mark.parametrize('case',['duplicate','missing_id','numeric_id','open','short','collinear','altitude',
                                 'boolean','range','antimeridian','null','point','crs','empty'])
def test_invalid_or_unsupported_geojson_fails(case):
    raw=source();feature=raw['features'][0];ring=feature['geometry']['coordinates'][0]
    if case=='duplicate':raw['features'].append(copy.deepcopy(feature))
    elif case=='missing_id':del feature['id']
    elif case=='numeric_id':feature['id']=1
    elif case=='open':ring.pop()
    elif case=='short':feature['geometry']['coordinates']=[[[0,0],[1,1],[0,0]]]
    elif case=='collinear':feature['geometry']['coordinates']=[[[0,0],[1,1],[2,2],[0,0]]]
    elif case=='altitude':ring[1].append(0)
    elif case=='boolean':ring[1][0]=True
    elif case=='range':ring[1][0]=181
    elif case=='antimeridian':feature['geometry']['coordinates']=[[[179,0],[-179,0],[-179,1],[179,1],[179,0]]]
    elif case=='null':feature['geometry']=None
    elif case=='point':feature['geometry']={'type':'Point','coordinates':[0,0]}
    elif case=='crs':raw['crs']={'type':'name','properties':{'name':'EPSG:3857'}}
    elif case=='empty':raw['features']=[]
    with pytest.raises(ValueError):GeoRegions.from_geojson(raw)


def test_join_mismatches_numeric_values_and_geometry_revisions():
    regions=GeoRegions.from_geojson(source())
    view=RegionView('map',regions,(-1,-1,9,7),value='value')
    with pytest.raises(ValueError,match='ID mismatch'):
        BrowserFigure(KeyedTable('bad',dict(id=['unmatched'],value=[1])),[view])
    with pytest.raises(ValueError,match='numeric'):
        BrowserFigure(KeyedTable('bad',dict(id=regions.feature_ids,value=['one']*4)),[view])
    changed=source();changed['features'][0]['geometry']['coordinates'][1][1][0]=2.8
    assert GeoRegions.from_geojson(changed).digest!=regions.digest


@pytest.mark.parametrize('kwargs',[{'extent':(1,0,0,1)},{'breaks':(1,1)},
    {'breaks':(1,),'colors':('#fff',)},{'colors':('url(bad)',)}, {'value':None,'breaks':(1,)}])
def test_bad_region_view_options(kwargs):
    args=dict(extent=(0,0,8,6),value='value');args.update(kwargs)
    with pytest.raises(ValueError):RegionView('map',GeoRegions.from_geojson(source()),**args)


CHECKS=r'''
(async()=>{
 await inklet.ready;const r=inklet,ok=(c,m)=>{if(!c)throw Error(m);};
 ok(document.getElementById('headers').children.length===3,'custom key repeated in data table');
 const layer=r.scene.layers[0],b=layer.clip,e=layer.extent;
 const point=(x,y)=>[b[0]+(x-e[0])/(e[2]-e[0])*b[2],b[1]+(e[3]-y)/(e[3]-e[1])*b[3]];
 const query=(x,y)=>r.pick(...point(x,y),0)?.id??null;
 const ctx=document.createElement('canvas').getContext('2d');
 // Native Canvas point-in-path is independent of our JS ray crossing and hash.
 const paths=layer.marks.map(m=>new Path2D(m.geometry.map(r=>'M '+r.map(p=>p.join(' ')).join(' L ')+' Z').join(' ')));
 let queries=0;const exports=[];
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);r.select(['islands']);
  ok(query(1.2,2)===null,'hole interior filled');
  ok(query(2,2)==='islands'&&query(.5,5.5)==='islands','multipolygon identity lost');
  ok(query(6,3)===null,'concave exterior filled');
  ok(query(4,.75)==='overlap','overlap paint order');
  const outer=layer.marks[0].geometry[0],hole=layer.marks[0].geometry[1];
  ok(r.pick(outer[1][0],(outer[1][1]+outer[2][1])/2,0)?.id==='east','shared boundary paint order');
  ok(r.pick(hole[0][0],(hole[0][1]+hole[3][1])/2,0)?.id==='reserve','hole boundary not included');
  ok(r.pick(b[0]-.1,b[1]+b[3]/2,5)===null,'picked outside clip');
  for(const visible of [null,['reserve','east'],[]]){
   r.setVisible(visible);
   for(let n=0;n<900;n++){
    const x=b[0]+((n*17.317)%b[2]),y=b[1]+((n*7.419)%b[3]);
    let expected=null;
    for(let j=0;j<paths.length;j++)if((visible===null||visible.includes(layer.marks[j].ids[0]))&&ctx.isPointInPath(paths[j],x,y,'evenodd'))expected=layer.marks[j].ids[0];
    const got=r.pick(x,y,0)?.id??null;queries++;ok(got===expected,'native fill oracle mismatch '+JSON.stringify({x,y,got,expected}));
   }
   const state=r.state();r.select([]);r.loadState(state);
   ok(r.selected.has('islands'),'filtered selection lost');
   exports.push({state,svg:r.exportSVG()});
  }
 }
 r.setVisible(null);r.setViewport([5,3,r.scene.width/1.5,r.scene.height/1.5]);
 const saved=r.state();r.select([]);r.loadState(saved);exports.push({state:saved,svg:r.exportSVG()});
 return {queries,exports};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def marks(svg):
    root=ET.fromstring(svg);result=[]
    for group in (root[1],root[-1]):
        for e in group.iter():
            if e.attrib.get('fill-rule')!='evenodd':continue
            attrs=dict(e.attrib);d=attrs.pop('d')
            points=tuple(float(v) for v in d.replace('M','').replace('L','').replace('Z','').split())
            for k in ('stroke-width',):attrs[k]=float(attrs[k])
            result.append((attrs,points))
    return result


@pytest.mark.parametrize('dpr,width',[(1,190),(2,150)])
def test_native_browser_fill_oracle_and_static_vector_agreement(tmp_path,dpr,width):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    s=scene(width,extent=(.2,.2,7.8,5.8) if dpr==2 else (-.2,-.2,8.2,6.2));page=tmp_path/'index.html'
    page.write_text(s.to_html().replace('</html>','<script>'+CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S);assert match,result.stdout[-2000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    assert report['queries']==8100
    for exported in report['exports']:assert marks(s.to_svg(exported['state']))==marks(exported['svg'])
    # Independent rasterization checks actual holes, overlaps, colors and strokes.
    pytest.importorskip('resvg_py');Image=pytest.importorskip('PIL.Image')
    from PIL import ImageChops
    from inklet.render.preview import svg_png
    exported=report['exports'][-1]
    for name,svg in [('python',s.to_svg(exported['state'])),('browser',exported['svg'])]:
        source=tmp_path/(name+'.svg');source.write_text(svg,encoding='utf-8')
        svg_png(source,tmp_path/(name+'.png'),dpi=150)
    a,b=(Image.open(tmp_path/(name+'.png')).convert('RGB') for name in ('python','browser'))
    assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None
