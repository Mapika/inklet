"""Spatial candidates must be conservative, ordered and visually identical."""
import json
from pathlib import Path
import random
import re
import shutil
import subprocess

import pytest
import inklet as i
from inklet.core import Diagram, MarkerBatchPrim, Rect, Style
from inklet.core.batch import RECORD


def dense_scene(marker='star',repeat=False):
    rng=random.Random(821)
    points=[(rng.uniform(-30,30),rng.uniform(-30,30),rng.uniform(.1,3)) for _ in range(1200)]
    # Centers outside a query can still paint into it. Include extreme sizes.
    points[:3]=[(-20,0,50),(15,2,35),(0,0,.2)]
    records=b''.join(RECORD.pack(x,y,size,k%3,2**53+k) for k,(x,y,size) in enumerate(points))
    prim=MarkerBatchPrim(i.marker(marker,1).prim,records,('red','blue','green'))
    layer=i.window(Diagram(prim=prim,style=Style(stroke='none',fill_opacity=.2)),Rect(-12,-12,12,12)).rotated(13)
    return i.compile_scene(Diagram(children=(layer,layer.translated(100,0))) if repeat else layer)


def chrome(tmp_path,page,*,dpr=1,picture=None):
    browser=shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:pytest.skip('Chrome not installed')
    args=[browser,'--headless','--no-sandbox','--enable-unsafe-swiftshader',
          '--use-gl=angle','--use-angle=swiftshader','--dump-dom','--virtual-time-budget=2000',
          '--window-size=1200,1000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/{page.stem}-profile']
    if picture:args.append(f'--screenshot={picture}')
    result=subprocess.run(args+[page.as_uri()],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr[-1000:]
    return result.stdout


def test_index_matches_brute_force_in_source_order_and_is_shared(tmp_path):
    script=r"""<script>inkletScene.ready.then(async r=>{
      const ok=(v,m)=>{if(!v)throw Error(m);};
      try{
        const batch=r.batches[0],index=new MarkerIndex(batch),data=batch.records,u=batch.bounds;
        for(let k=0;k<100;k++){
          const x=(k*1.371)%60-30,y=(k*2.743)%60-30,w=.01+(k%9)*2,h=.1+(k%7)*3;
          const actual=index.query([x,y,w,h]),expected=[];
          for(let j=0;j<batch.count;j++){
            const o=j*36,px=data.getFloat64(o,true),py=data.getFloat64(o+8,true),s=data.getFloat64(o+16,true);
            if(px+s*u[0]<=x+w&&py+s*u[1]<=y+h&&px+s*u[2]>=x&&py+s*u[3]>=y)expected.push(j);
          }
          ok(JSON.stringify(actual===null?Array.from({length:batch.count},(_,j)=>j):[...actual])===JSON.stringify(expected),'index disagrees with brute force');
        }
        // All centers on one axis must not divide by a zero grid span.
        for(const axis of [0,8]){
          const copy=new DataView(data.buffer.slice(0));
          for(let k=0;k<batch.count;k++)copy.setFloat64(k*36+axis,0,true);
          const flat=new MarkerIndex({...batch,records:copy});
          const candidates=flat.query([-100,-100,200,200]);
          ok(candidates===null,'degenerate grid axis lost markers');
          ok(flat.query([200,200,1,1]).length===0,'empty query retained markers');
        }
        // Reused scratch storage must never mutate a selection already held
        // by another placement or a pending GPU upload.
        const held=index.query([-5,-5,10,10]),snapshot=[...held];
        index.query([-100,-100,200,200]);index.query([200,200,1,1]);
        ok(JSON.stringify([...held])===JSON.stringify(snapshot),'later query mutated an earlier selection');
        // Bits at signed-word boundaries and a final partial word retain order.
        const edgeCount=97,edgeData=new DataView(new ArrayBuffer(edgeCount*36));
        for(let k=0;k<edgeCount;k++){edgeData.setFloat64(k*36,k,true);edgeData.setFloat64(k*36+16,.1,true);}
        const edge=new MarkerIndex({...batch,count:edgeCount,records:edgeData});
        const edgeRows=edge.query([30,-1,66,2]);
        ok(JSON.stringify([...edgeRows])===JSON.stringify(Array.from({length:67},(_,k)=>k+30)),'bitmap word boundary lost or reordered rows');
        ok(edge.bytes===edge.bounds.byteLength+edge.offsets.byteLength+edge.indices.byteLength+edge.selected.byteLength,'index byte count omitted scratch space');
        const touching=index.query([-1,-1,2,2]);ok(touching.includes(0),'large marker with outside center was lost');
        r.candidates(batch,[-1,-1,2,2],500,500);const bytes=r.report().spatialIndexBytes;
        r.candidates(r.batches[1],[-1,-1,2,2],500,500);
        ok(r.spatialIndexes.size===1&&r.report().spatialIndexBytes===bytes,'repeated placement duplicated index');
        const uploads=r.uploadBytes;
        r.setViewport([-2,-2,4,4]);
        ok(r.report().layers[0].candidateCount<batch.count,'renderer did not cull');
        ok(r.selectionUploadBytes>0,'GPU did not upload selected row indices');
        ok(r.report().layers[0].selectionCapacityBytes===batch.count*4,'selection capacity report is wrong');
        r.setViewport([-.5,-.5,1,1]);
        ok(r.uploadBytes===uploads,'culling reuploaded geometry');
        const exported=r.exportSVG(),doc=new DOMParser().parseFromString(exported,'image/svg+xml');
        ok(doc.querySelectorAll('[data-source-index]').length===batch.count*2,'export lost unselected observations');
        ok(exported.includes('9007199254742191'),'export rounded source ID');
        const selected=r.layers[0].candidateCount;
        r.layers[0].gpu.gl.getExtension('WEBGL_lose_context').loseContext();
        await new Promise(resolve=>setTimeout(resolve,80));r.render();
        ok(r.layers[0].actual==='canvas'&&r.layers[0].candidateCount===selected,'context loss changed candidates');
        ok(r.uploadBytes===uploads,'context loss reuploaded geometry');
        r.dispose();ok(r.spatialIndexes.size===0,'dispose retained spatial resources');
        document.body.dataset.cullingTest='passed';
      }catch(e){document.body.dataset.cullingTest=e.stack;}
    });</script>"""
    # Wider source bounds require a >=2 mm viewport under the viewer zoom cap.
    script=script.replace('[-.5,-.5,1,1]','[-1,-1,2,2]')
    page=tmp_path/'index.html';page.write_text(dense_scene(repeat=True).to_html(backend='webgl2').replace('</body>',script+'</body>'))
    output=chrome(tmp_path,page)
    assert 'data-culling-test="passed"' in output,re.search(r'<body[^>]*>',output)[0]


@pytest.mark.parametrize('marker',['circle','star'])
@pytest.mark.parametrize('backend',['webgl2','canvas'])
@pytest.mark.parametrize('dpr',[1,2])
def test_culled_ink_matches_svg_including_transparency_and_outside_centers(tmp_path,marker,backend,dpr):
    import html
    Image=pytest.importorskip('PIL.Image');ImageChops=pytest.importorskip('PIL.ImageChops');ImageStat=pytest.importorskip('PIL.ImageStat')
    scene=dense_scene(marker);images=[]
    for mode in (backend,'svg'):
        script="""<script>inkletScene.ready.then(r=>{r.setViewport([-2,-2,4,4]);document.body.dataset.stage=JSON.stringify(host.getBoundingClientRect().toJSON());document.body.dataset.report=JSON.stringify(r.report());});</script>"""
        page=tmp_path/f'{mode}.html';picture=tmp_path/f'{mode}.png';page.write_text(scene.to_html(backend=mode).replace('</body>',script+'</body>'))
        output=chrome(tmp_path,page,dpr=dpr,picture=picture)
        report=json.loads(html.unescape(re.search(r'data-report="([^"]+)"',output)[1]))
        if mode!='svg':
            assert report['layers'][0]['backend']==mode
            assert 0<report['layers'][0]['candidateCount']<1200
        box=json.loads(html.unescape(re.search(r'data-stage="([^"]+)"',output)[1]));crop=tuple(round(box[k]*dpr) for k in ('left','top','right','bottom'))
        images.append(Image.open(picture).convert('RGB').crop(crop))
    assert max(ImageStat.Stat(ImageChops.difference(*images)).mean)<.6
