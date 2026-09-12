"""Linked identities must survive shared compiled marker execution."""
import base64
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.core.batch import RECORD
from inklet.experimental.browser import BrowserFigure, LineView, ScatterView
from inklet.experimental.browser.compiled import compiled_marks
from inklet.experimental.selection import KeyedTable


def figure():
    table = KeyedTable('compiled-check', dict(id=[f'row-{n}' for n in range(1024)],
        x=[n % 32 for n in range(1024)], y=[n // 32 for n in range(1024)]))
    return BrowserFigure(table, [ScatterView('cloud', 'x', 'y', (-1, 33), (-1, 33)),
        LineView('line', 'x', 'y', (-1, 33), (-1, 33))])


def test_compiled_payload_preserves_identity_geometry_and_state_digest():
    f = figure()
    before = f.payload()
    page = f.to_html(renderer='compiled', backend='auto')
    payload = json.loads(re.search(r'id="scene">(.*?)</script>', page, re.S)[1])
    compiled = payload.pop('compiled')
    assert payload == before == f.payload()
    batch = compiled['batches'][0]
    records = list(RECORD.iter_unpack(base64.b64decode(compiled['buffers'][0])))
    layer = before['layers'][0]
    assert batch['row_ids'] == [[point[0]] for point in layer['points']]
    assert [(r[0], r[1]) for r in records] == [tuple(p[1:]) for p in layer['points']]
    assert [r[-1] for r in records] == list(range(1024))
    assert batch['palette'] == [[52, 120, 107, .65]]
    assert 'src="http' not in page
    assert len(compiled['native_marks']) == 1023


def test_packing_keeps_native_paint_between_circle_runs_and_per_mark_alpha():
    marks = [dict(kind='circle', ids=['a'], geometry=[1, 2, .4], opacity=.2),
             dict(kind='line', ids=['a', 'b'], geometry=[1, 2, 3, 4], width=.3),
             dict(kind='circle', ids=['b'], geometry=[3, 4, .7], opacity=.8)]
    payload = dict(width=10, height=10, row_ids=['a', 'b'],
                   layers=[dict(clip=[0, 0, 10, 10], color='#34786b', marks=marks)])
    compiled = compiled_marks(payload)
    root = ET.fromstring(compiled['frame'])
    assert [node.tag.rsplit('}', 1)[-1] for node in root[1]] == ['g', 'line', 'g']
    assert [b['palette'][0][3] for b in compiled['batches']] == [.2, .8]


@pytest.mark.parametrize('renderer,backend', [('bad','svg'), ('compiled','hybrid'), ('classic','webgl2')])
def test_unsupported_renderer_combinations_fail_before_export(renderer, backend):
    with pytest.raises(ValueError):
        figure().to_html(renderer=renderer, backend=backend)


@pytest.mark.parametrize('backend', ['svg', 'canvas', 'webgl2'])
def test_filtering_reuses_records_and_intersects_spatial_candidates(tmp_path, backend):
    browser = shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:
        pytest.skip('Chrome/Chromium not installed')
    page = figure().to_html(renderer='compiled', backend=backend)
    checks = r"""
    <script>
    inkletDocument.ready.then(async()=>{
      const ok=(v,m)=>{if(!v)throw Error(m);},r=inklet,v=r.compiled,b=v.batches[0];
      const records=b.records,uploads=v.uploadBytes,original=r.state();
      if(r.backend==='webgl2')ok(v.layers[0].actual==='webgl2','GPU path not exercised');
      r.setVisible(['row-1','row-500','row-1000']);r.select(['row-1','row-2']);
      ok(v.batches[0].records===records&&v.uploadBytes===uploads,'filter replaced immutable records');
      const indices=v.candidates(b,b.box,1200,800);
      ok(JSON.stringify([...indices])==='[1,500,1000]','filtered source order');
      const box=[b.box[0],b.box[1],b.box[2]/2,b.box[3]/2];
      const unfiltered=v.spatialCandidates(b,box,1200,800);
      ok(unfiltered!==null,'spatial index not exercised');
      ok(JSON.stringify([...v.candidates(b,box,1200,800)])===JSON.stringify([...unfiltered].filter(k=>[1,500,1000].includes(k))),'filter/index intersection');
      ok(r.selected.has('row-2')&&!r.shown('row-2'),'hidden selection lost');
      ok(r.nativeMarks.every(node=>node.style.display==='none'),'filtered lines bridge missing rows');
      const state=r.state();r.loadState(state);
      ok(JSON.stringify(r.state())===JSON.stringify(state),'state round trip');
      const dom=new DOMParser().parseFromString(r.exportSVG(),'image/svg+xml');
      ok(dom.querySelectorAll('circle').length===4,'export does not contain 3 marks and 1 highlight');
      r.setBackend('svg');
      ok(v.svg.querySelectorAll('[data-source-index]').length===3,'SVG fallback ignored filter');
      r.setBackend('canvas');r.setVisible([]);
      ok(v.layers[0].candidateCount===0,'empty filter still paints');
      r.loadState(original);
      ok(v.layers[0].candidateCount===1024,'restored rows missing');
      ok(v.batches[0].records===records,'backend switching replaced source records');
      document.body.dataset.compiledTest='passed';
    }).catch(e=>document.body.dataset.compiledTest=e.stack);
    </script>
    """
    path = tmp_path/'index.html'
    path.write_text(page.replace('</html>', checks+'</html>'))
    result = subprocess.run([browser, '--headless', '--no-sandbox', '--use-gl=angle',
        '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--dump-dom',
        '--virtual-time-budget=6000', f'--user-data-dir={tmp_path}/profile', path.as_uri()],
        capture_output=True, text=True, timeout=40)
    match = re.search(r'data-compiled-test="([^"]*)"', result.stdout)
    assert match, result.stderr[-2000:]
    assert html.unescape(match[1]) == 'passed'


@pytest.mark.parametrize('backend', ['svg', 'canvas', 'webgl2'])
@pytest.mark.parametrize('dpr', [1, 2])
def test_complete_regional_display_matches_classic_svg(tmp_path, backend, dpr):
    from test_regional_report import recipe
    from inklet.experimental.selection import SelectionState
    Image = pytest.importorskip('PIL.Image')
    ImageChops = pytest.importorskip('PIL.ImageChops')
    ImageStat = pytest.importorskip('PIL.ImageStat')
    browser = shutil.which('google-chrome') or shutil.which('chromium')
    if not browser:
        pytest.skip('Chrome/Chromium not installed')
    f = recipe.make_scene()
    state = f.state(SelectionState.for_table(f.table, selected=['HUN', 'EST'],
        visible=['HUN', 'AUT', 'DEU', 'CZE', 'POL', 'SVK']))
    images = []
    for renderer, mode in [('classic', 'svg'), ('compiled', backend)]:
        page = f.to_html(renderer=renderer, backend=mode, state=state)
        page = page.replace('</style>', '</style><style>#stage{position:fixed;left:0;top:0;'
                            'width:1112px;height:1342px;z-index:10}</style>', 1)
        # Crop just the drawing; differing backend controls must not influence
        # this independently executed full-figure paint comparison.
        check = """<script>inkletDocument.ready.then(()=>{
            document.body.dataset.stage=JSON.stringify(document.getElementById('stage').getBoundingClientRect().toJSON());
        });</script>"""
        path = tmp_path/f'{renderer}.html'
        picture = tmp_path/f'{renderer}.png'
        path.write_text(page.replace('</html>', check+'</html>'))
        result = subprocess.run([browser, '--headless', '--no-sandbox', '--enable-unsafe-swiftshader',
            '--use-gl=angle', '--use-angle=swiftshader', '--dump-dom', '--virtual-time-budget=2000',
            '--window-size=1400,2200', f'--force-device-scale-factor={dpr}', f'--screenshot={picture}',
            f'--user-data-dir={tmp_path}/{renderer}-profile', path.as_uri()],
            capture_output=True, text=True, timeout=40)
        match = re.search(r'data-stage="([^"]+)"', result.stdout)
        assert match, result.stderr[-2000:]
        box = json.loads(html.unescape(match[1]))
        crop = tuple(round(box[k]*dpr) for k in ('left', 'top', 'right', 'bottom'))
        images.append(Image.open(picture).convert('RGB').crop(crop))
    assert images[0].size == images[1].size
    assert max(ImageStat.Stat(ImageChops.difference(*images)).mean) < .5
