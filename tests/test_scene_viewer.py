"""Native scene/browser handoff, GPU resources and explicit fallback semantics."""
import base64
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import inklet as i
from inklet.core import Diagram, EllipsePrim, MarkerBatchPrim, Rect, RectPrim, PathPrim, Subpath, Style
from inklet.core.batch import RECORD


def drawing(*, stroke='none', marker='circle'):
    records=b''.join(RECORD.pack(x,y,size,k%3,2**53+k) for k,(x,y,size) in enumerate(
        [(-5,-2,3),(-3,-1,4),(-2,0,3),(3,2,2),(5,-1,3),(0,3,1)]))
    if marker in ('evenodd','nonzero'):
        outer=i.marker('star',1).prim.subpaths[0].points
        shape=PathPrim((Subpath(tuple(reversed(outer)),closed=True),),filled=True,fill_rule=marker)
    else:
        shape=i.marker(marker,1).prim
    batch=MarkerBatchPrim(shape,records,('red','blue',None))
    dots=Diagram(prim=batch,style=Style(fill='green',stroke=stroke,stroke_width=.3,fill_opacity=.45))
    clipped=i.window(dots,Rect(-5,-4,6,4)).rotated(13).styled(opacity=.7)
    return i.compile_scene(Diagram(children=(clipped,i.text('Native text',size=2).translated(0,7))))


def payload(page):
    return json.loads(re.search(r'<script type="application/json" id="scene">(.*?)</script>',page,re.S)[1])


def test_scene_handoff_retains_buffer_precision_and_native_structure():
    scene=drawing();p=payload(scene.to_html())
    assert p['schema']=='inklet.compiled-viewer/1'
    assert p['backend']=='auto' and len(p['batches'])==1
    batch=p['batches'][0]
    records=list(RECORD.iter_unpack(base64.b64decode(p['buffers'][batch['buffer']])))
    assert records[0][-1]==2**53 and records[-1][-1]==2**53+5
    assert batch['palette']==[[255,0,0,.45],[0,0,255,.45],[0,128,0,.45]]
    assert '<clipPath' in p['frame'] and 'opacity="0.7"' in p['frame']
    assert '<use' in p['frame'] and 'data-source-index=' not in p['frame']
    assert 'foreignObject' not in p['frame'] # only the runtime chooses display resources
    assert scene.to_svg()==scene.to_svg()


@pytest.mark.parametrize('backend',['auto','webgl2','canvas','svg'])
def test_html_is_offline_and_escapes_authored_text_once(backend):
    page=drawing().to_html(title='</title><script>bad</script><!--TITLE-->',backend=backend)
    assert '<title>&lt;/title&gt;' in page and '<script>bad</script>' not in page
    assert 'src="http' not in page and '/*SCENE*/' not in page
    assert payload(page)['backend']==backend


def test_outlines_use_native_svg_instead_of_losing_stroke():
    p=payload(drawing(stroke='black').to_html())
    assert not p['batches']
    assert 'outlines' in p['native'][0]['reason']
    assert p['frame'].count('data-source-index=')==6


@pytest.mark.parametrize('backend',['gpu','bad',None])
def test_invalid_backend_fails_before_export(backend):
    with pytest.raises(ValueError):drawing().to_html(backend=backend)


CHECKS=r'''
<script>
inkletScene.ready.then(async r=>{
 const ok=(value,message)=>{if(!value)throw Error(message);};
 try{
  let first=r.layers[0];
  ok(first.actual==='webgl2','WebGL2 path not exercised');
  ok(r.svg.querySelectorAll('foreignObject').length===1,'missing browser surface');
  ok(r.svg.querySelectorAll('[data-source-index]').length===0,'expanded point DOM');
  const uploads=r.uploadBytes;r.zoom(1.5);r.setViewport(r.original);
  ok(r.uploadBytes===uploads,'zoom uploaded immutable buffers again');
  const before=JSON.stringify(r.viewport);let rejected=false;
  try{r.setViewport([0,0,0,1]);}catch{rejected=true;}
  ok(rejected&&JSON.stringify(r.viewport)===before,'invalid viewport changed state');
  const svg=r.exportSVG(),doc=new DOMParser().parseFromString(svg,'image/svg+xml');
  ok(!svg.includes('foreignObject')&&!svg.includes('<canvas'),'export has raster surfaces');
  ok(doc.querySelectorAll('[data-source-index]').length===6,'export lost observations');
  ok(svg.includes('9007199254740997'),'source identity lost integer precision');
  document.body.dataset.vectorExport=btoa(unescape(encodeURIComponent(svg)));
  ok(doc.querySelectorAll('clipPath').length>0&&doc.querySelectorAll('use').length>0,'export lost native art');
  // Backend switches may choose different retained backing resolutions.
  // Start both reference painters at the original viewport for an equal grid.
  r.setBackend('webgl2');first=r.layers[0];
  const count=r.layers[0].batch.count,initial=new Uint8Array(first.canvas.width*first.canvas.height*4);
  first.gpu.gl.readPixels(0,0,first.canvas.width,first.canvas.height,first.gpu.gl.RGBA,first.gpu.gl.UNSIGNED_BYTE,initial);
  ok(initial.some(v=>v>0),'GPU drew no ink');
  // Compare GPU coverage to independent Canvas painting on the same local grid.
  const width=first.canvas.width,height=first.canvas.height;r.setBackend('canvas');
  const canvas=r.layers[0].context.getImageData(0,0,width,height).data;
  let sum=0,n=width*height;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++)sum+=Math.abs(initial[((height-1-y)*width+x)*4+3]-canvas[(y*width+x)*4+3]);
  ok(sum/n<3,'GPU/Canvas alpha disagreement: '+sum/n);
  r.setBackend('webgl2');const gl=r.layers[0].gpu.gl;
  gl.getExtension('WEBGL_lose_context').loseContext();
  await new Promise(resolve=>setTimeout(resolve,80));
  ok(r.layers[0].actual==='canvas'&&r.layers[0].reason.includes('lost'),'context loss did not fall back');
  ok(r.layers[0].batch.count===count,'fallback lost data');
  r.setBackend('svg');ok(r.svg.querySelectorAll('[data-source-index]').length===count,'SVG display lost data');
  r.setBackend('auto');ok(r.layers[0].actual==='canvas'&&r.layers[0].reason.includes('Software'),'auto did not avoid software WebGL');
  const secondHost=document.createElement('div');secondHost.style.width='400px';document.body.append(secondHost);
  const second=new CompiledSceneViewer(secondHost,{...r.scene,backend:'canvas'});await second.ready;
  const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);ok(new Set(ids).size===ids.length,'duplicate IDs');
  const surface=second.layers[0];ok(Math.abs(surface.canvas.getBoundingClientRect().width-surface.foreign.getBoundingClientRect().width)<.1,'embedded instance depends on page CSS');
  second.dispose();ok(!secondHost.children.length,'dispose retained DOM');
  document.body.dataset.viewerTest='passed';document.body.dataset.alphaError=String(sum/n);
 }catch(error){document.body.dataset.viewerTest=error.stack;}
});
</script>
'''


@pytest.mark.parametrize('marker',['circle','square','triangle','diamond','star','evenodd','nonzero'])
@pytest.mark.parametrize('dpr',[1,2])
def test_headless_webgl_canvas_switching_context_loss_and_export(tmp_path,dpr,marker):
    browser=shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:pytest.skip('Chrome not installed')
    page=tmp_path/'viewer.html';page.write_text(drawing(marker=marker).to_html(backend='webgl2').replace('</body>',CHECKS+'</body>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--enable-unsafe-swiftshader',
                           '--use-gl=angle','--use-angle=swiftshader','--dump-dom',
                           '--virtual-time-budget=6000',f'--force-device-scale-factor={dpr}',
                           f'--user-data-dir={tmp_path}/profile',page.as_uri()],
                          capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr[-2000:]
    assert 'data-viewer-test="passed"' in result.stdout,re.search(r'<body[^>]*>',result.stdout)[0]+'\n'+result.stderr[-1500:]
    from io import BytesIO
    Image=pytest.importorskip("PIL.Image")
    ImageChops=pytest.importorskip("PIL.ImageChops")
    ImageStat=pytest.importorskip("PIL.ImageStat")
    pytest.importorskip("resvg_py")
    from inklet.render.raster import png_bytes
    exported=base64.b64decode(re.search(r'data-vector-export="([^"]+)"',result.stdout)[1]).decode()
    native=drawing(marker=marker).to_svg(text='outline',precision=6,background='white')
    a=Image.open(BytesIO(png_bytes(exported,600,400))).convert('RGB')
    b=Image.open(BytesIO(png_bytes(native,600,400))).convert('RGB')
    assert max(ImageStat.Stat(ImageChops.difference(a,b)).mean)<.01



def test_no_webgl_uses_canvas_and_reports_fallback(tmp_path):
    browser=shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:pytest.skip('Chrome not installed')
    check="""<script>inkletScene.ready.then(r=>{document.body.dataset.viewerTest=r.layers[0].actual==='canvas'&&r.layers[0].reason?'passed':'failed';});</script>"""
    page=tmp_path/'viewer.html';page.write_text(drawing().to_html().replace('</body>',check+'</body>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-webgl','--dump-dom',
                           '--virtual-time-budget=2000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],capture_output=True,text=True,timeout=30)
    assert 'data-viewer-test="passed"' in result.stdout,result.stdout[-3000:]


def test_repeated_placements_share_the_serialized_source_buffer():
    prim=MarkerBatchPrim(EllipsePrim(.5,.5),RECORD.pack(0,0,2,0,0))
    root=Diagram(children=(Diagram(prim=prim),Diagram(prim=prim).translated(5,0)))
    p=payload(i.compile_scene(root).to_html())
    assert len(p['batches'])==2 and len(p['buffers'])==1
    assert p['batches'][0]['buffer']==p['batches'][1]['buffer']


@pytest.mark.parametrize('marker',['circle','square','triangle','diamond','star','evenodd','nonzero'])
@pytest.mark.parametrize('backend',['webgl2','canvas'])
@pytest.mark.parametrize('dpr',[1,2])
def test_composited_surface_stays_aligned_with_native_svg(tmp_path,backend,dpr,marker):
    """Catch HTML-surface layout rounding after SVG clipping and rotation."""
    import html
    Image=pytest.importorskip('PIL.Image')
    ImageChops=pytest.importorskip('PIL.ImageChops')
    ImageStat=pytest.importorskip('PIL.ImageStat')
    browser=shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:pytest.skip('Chrome not installed')
    images=[]
    for mode in (backend,'svg'):
        page=tmp_path/f'{mode}.html';picture=tmp_path/f'{mode}.png'
        check="<script>inkletScene.ready.then(r=>{r.zoom(1.15);r.setViewport(r.original);r.setViewport([r.original[0]+.2,r.original[1]+.3,...r.original.slice(2)]);document.body.dataset.stage=JSON.stringify(host.getBoundingClientRect().toJSON());});</script>"
        page.write_text(drawing(marker=marker).to_html(backend=mode).replace('</body>',check+'</body>'))
        result=subprocess.run([browser,'--headless','--no-sandbox','--enable-unsafe-swiftshader',
                               '--use-gl=angle','--use-angle=swiftshader','--dump-dom',
                               '--virtual-time-budget=1000','--window-size=1200,1000',
                               f'--force-device-scale-factor={dpr}',f'--screenshot={picture}',
                               f'--user-data-dir={tmp_path}/{mode}-profile',page.as_uri()],
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr[-1500:]
        box=json.loads(html.unescape(re.search(r'data-stage="([^"]+)"',result.stdout)[1]))
        crop=tuple(round(box[k]*dpr) for k in ('left','top','right','bottom'))
        images.append(Image.open(picture).convert('RGB').crop(crop))
    difference=ImageChops.difference(*images)
    assert max(ImageStat.Stat(difference).mean)<.5


@pytest.mark.parametrize('kind',['cross','plus'])
def test_open_markers_keep_native_stroke_semantics(kind):
    p=payload(drawing(marker=kind).to_html())
    assert not p['batches'] and p['native'][0]['count']==6


def test_polygon_metadata_retains_exact_shape_and_fill_rule():
    from inklet.core import PathPrim, Subpath, Vec2
    shape=PathPrim((Subpath(tuple(Vec2(*p) for p in [(0,0),(2,0),(2,2),(0,2),(0,0)]),closed=True),),filled=True,fill_rule='evenodd')
    batch=MarkerBatchPrim(shape,RECORD.pack(0,0,1,0,0))
    p=payload(i.compile_scene(Diagram(prim=batch,style=Style(stroke='none'))).to_html())
    geometry=p['batches'][0]
    assert geometry['fill_rule']=='evenodd'
    assert len(geometry['vertices'])==4
    assert geometry['bounds']==[0,0,2,2]


@pytest.mark.parametrize('shape',[
    RectPrim(2,2,.3),
    i.marker('plus',1).prim,
])
def test_unsupported_geometry_stays_native(shape):
    batch=MarkerBatchPrim(shape,RECORD.pack(0,0,1,0,0))
    p=payload(i.compile_scene(Diagram(prim=batch)).to_html())
    assert not p['batches'] and 'shape' in p['native'][0]['reason']


def test_self_intersecting_polygon_stays_native_without_internal_alpha_seams():
    outer=i.marker('star',1).prim.subpaths[0].points
    shape=PathPrim((Subpath(tuple(outer[k] for k in (0,4,8,2,6)),closed=True),),filled=True)
    batch=MarkerBatchPrim(shape,RECORD.pack(0,0,1,0,0))
    p=payload(i.compile_scene(Diagram(prim=batch,style=Style(stroke='none'))).to_html())
    assert not p['batches'] and 'shape' in p['native'][0]['reason']


@pytest.mark.parametrize('backend',['webgl2','canvas'])
@pytest.mark.parametrize('dpr',[1,2])
def test_surface_reuse_growth_shrink_and_context_loss(tmp_path,backend,dpr):
    browser=shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:pytest.skip('Chrome not installed')
    checks=r"""<script>
    inkletScene.ready.then(async r=>{
      const ok=(v,m)=>{if(!v)throw Error(m);};
      try{
        const b=r.original,bytes=r.uploadBytes;
        r.zoom(1.15);r.setViewport(b);
        const warmed=r.report();
        for(let k=0;k<8;k++){
          const s=k%2?1:1.15;
          r.setViewport([b[0]+k*.1,b[1],b[2]/s,b[3]/s]);
        }
        let report=r.report();
        ok(report.surfacePaints===warmed.surfacePaints,'small view changes repainted');
        ok(report.surfaceResizes===warmed.surfaceResizes,'small view changes reallocated');
        ok(report.reusedSurfaces>warmed.reusedSurfaces,'reuse not reported');
        r.setViewport([b[0],b[1],b[2]/8,b[3]/8]);
        const large=r.layers[0].canvas.width*r.layers[0].canvas.height;
        ok(r.report().surfacePaints>warmed.surfacePaints,'zoom growth did not repaint');
        ok(r.layers[0].reduced,'extreme zoom did not report resolution limit');
        for(const layer of r.layers)ok(layer.canvas.width<=4096&&layer.canvas.height<=4096&&layer.canvas.width*layer.canvas.height<=4000000,'surface exceeded budget');
        r.setViewport(b);
        ok(r.layers[0].canvas.width*r.layers[0].canvas.height<large,'zoom out did not release excess pixels');
        ok(!r.layers[0].reduced,'fit did not restore full resolution');
        ok(r.uploadBytes===bytes,'view changes reuploaded geometry');
        const painted=r.report().surfacePaints;
        r.render();ok(r.report().surfacePaints===painted,'unchanged render repainted');
        if(r.layers[0].gpu){
          r.layers[0].gpu.gl.getExtension('WEBGL_lose_context').loseContext();
          r.render();await new Promise(resolve=>setTimeout(resolve,80));
          ok(r.layers[0].actual==='canvas'&&r.layers[0].painted,'cached surface hid context loss');
          ok(r.report().surfacePaints>painted,'fallback did not paint');
        }
        document.body.dataset.cacheTest='passed';
      }catch(e){document.body.dataset.cacheTest=e.stack;}
    });</script>"""
    page=tmp_path/'cache.html';page.write_text(drawing(marker='star').to_html(backend=backend).replace('</body>',checks+'</body>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--enable-unsafe-swiftshader',
        '--use-gl=angle','--use-angle=swiftshader','--dump-dom','--virtual-time-budget=6000',
        f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr[-1500:]
    assert 'data-cache-test="passed"' in result.stdout,re.search(r'<body[^>]*>',result.stdout)[0]
