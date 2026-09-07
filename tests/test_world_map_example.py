"""The real map must retain source attribution, country joins and usable selection."""
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess

import pytest
from inklet.experimental.browser import GeoRegions

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'examples/v4/data'


def test_natural_earth_snapshot_hashes_and_country_join():
    provenance=json.loads((DATA/'world-map-source.json').read_text())
    for name,digest in provenance['files'].items():assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==digest
    regions=GeoRegions.read(DATA/'world-countries.geojson')
    with (DATA/'world-population.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(regions.features)==len(rows)==176 and 'ATA' not in regions.feature_ids
    assert regions.feature_ids==tuple(r['id'] for r in rows)
    assert next(r for r in rows if r['id']=='HUN')['country']=='Hungary'
    assert sum(int(r['population_year'])==2019 for r in rows)==169
    assert sum(len(parts) for _,parts in regions.features)==280


CHECKS=r'''
(async()=>{
 await inklet.ready;const r=inklet,ok=(c,m)=>{if(!c)throw Error(m);};
 function pick(lon,lat,n=0){const l=r.scene.layers[n],b=l.clip,e=l.extent;
  return r.pick(b[0]+(lon-e[0])/(e[2]-e[0])*b[2],b[1]+(e[3]-lat)/(e[3]-e[1])*b[3],0)?.id;
 }
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);
  for(const [x,y,id] of [[19.04,47.5,'HUN'],[2.35,48.86,'FRA'],[-93.62,41.58,'USA'],[-47.88,-15.79,'BRA'],[133.88,-23.7,'AUS']])ok(pick(x,y)===id,'country pick '+id+' in '+backend);
  ok(pick(19.04,47.5,1)==='HUN','Europe/world identity disagreement');
 }
 const input=document.getElementById('id-filter');input.value='hungary';input.dispatchEvent(new Event('input'));
 ok(r.visible.size===1&&r.visible.has('HUN'),'country-name search failed');
 ok(document.getElementById('rows').textContent.includes('9769949'),'population integer rounded in table');
 document.querySelector('button[aria-label="Select HUN"]').click();
 ok(r.selected.has('HUN')&&r.overlay.querySelectorAll('path').length===2,'linked selection failed');
 const state=r.state();input.value='france';input.dispatchEvent(new Event('input'));
 ok(r.selected.has('HUN')&&!r.shown('HUN'),'filter discarded selection');r.loadState(state);
 ok(r.shown('HUN')&&r.selected.has('HUN'),'state reopen failed');
 ok(document.querySelector('footer').textContent.includes('Made with Natural Earth'),'source credit absent');
 ok(!document.querySelector('footer').textContent.includes('Original simulated data'),'real data mislabeled simulated');
 return {selected:[...r.selected],visible:[...r.visible]};
})().then(result=>{document.body.dataset.worldTest=JSON.stringify(result);})
.catch(error=>{document.body.dataset.worldTest=JSON.stringify({error:error.message});});
'''


@pytest.mark.parametrize('dpr',[1,2])
def test_real_country_picking_search_and_provenance(tmp_path,dpr):
    browser=next((p for n in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(n))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    recipe=runpy.run_path(str(ROOT/'examples/v4/world_population.py'));scene=recipe['make_scene']()
    page=scene.to_html(attribution=recipe['CREDIT'],search_columns=('country','continent'))
    path=tmp_path/'index.html';path.write_text(page.replace('</html>','<script>'+CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',path.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'data-world-test="([^"]*)"',result.stdout);assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1]));assert report=={'selected':['HUN'],'visible':['HUN']},report


def test_attribution_is_plain_text_and_search_columns_are_validated():
    recipe=runpy.run_path(str(ROOT/'examples/v4/world_population.py'));scene=recipe['make_scene'](world_only=True)
    page=scene.to_html(attribution='</footer><script>bad</script>')
    assert '&lt;/footer&gt;' in page and '<script>bad</script>' not in page
    with pytest.raises(ValueError,match='search'):scene.to_html(search_columns=('unknown',))
