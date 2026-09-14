"""Budget reference-report rebuilds and real-clock offline browser interactions."""
from pathlib import Path
import argparse
import http.server
import json
import math
import platform
import secrets
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'examples/v4'),str(ROOT/'tools')]
from benchmark_project import check_budgets
import inklet
from inklet.experimental.browser import BrowserFigure, ScatterView
from inklet.experimental.selection import KeyedTable, SelectionState
import regional_report, engineering_report, scientific_report

CASES=('regional','engineering','scientific','dense-scatter')
RENDERERS=(('classic','svg'),('classic','canvas'),('classic','hybrid'),('compiled','svg'),('compiled','canvas'))


def scene(name, revised=False):
    if name=='regional': return regional_report.make_scene(revised=revised)
    if name=='engineering': return engineering_report.make_scene('resized' if revised else 'original')
    if name=='scientific': return scientific_report.make_scene('updated' if revised else 'original')
    count=3000
    table=KeyedTable('dense',dict(id=[f'row-{n:04}' for n in range(count)],
        x=[n/(count-1) for n in range(count)],y=[math.sin(n*.1)+(.1 if revised else 0) for n in range(count)]))
    return BrowserFigure(table,[ScatterView('first','x','y',(0,1),(-1.2,1.2)),
        ScatterView('second','y','x',(-1.2,1.2),(0,1))],width=210,columns=2)


def measure_python(name):
    times={}
    def timed(key,fn):
        start=time.perf_counter();value=fn();times[key]=time.perf_counter()-start;return value
    original=timed('build',lambda:scene(name))
    payload=timed('payload',original.payload)
    for renderer in ('classic','compiled'):
        html=timed('html_'+renderer,lambda:original.to_html(renderer=renderer))
        assert '<html' in html
    before=original.to_svg()
    state=original.state(SelectionState.for_table(original.table,selected=[original.table.row_ids[0]]))
    saved=json.loads(json.dumps(state))
    reopened=timed('reopen',lambda:scene(name))
    assert reopened.to_svg(saved)==original.to_svg(state)
    def revise():
        changed=scene(name,True)
        if name=='regional': views=regional_report.make_views(changed.table)
        elif name=='engineering': views=engineering_report.make_views(engineering_report.make_assembly('resized'),engineering_report.read_labels())
        elif name=='scientific': views=scientific_report.make_views(scientific_report.make_image('updated'))
        else: views=None
        return original.replace_data(changed.table,views=views,state=saved)
    revised=timed('revision',revise)
    assert revised.figure.table.digest!=original.table.digest
    assert revised.state()['selection']['selected_ids']==saved['selection']['selected_ids']
    for width in (160,210):
        resized=timed(f'resize_{width}',lambda:revised.figure.replace_data(revised.figure.table,state=revised.state(),width=width))
        assert resized.figure.payload()['width']==width
    svg=timed('svg',lambda:revised.figure.to_svg(revised.state()))
    assert '<svg' in svg and original.to_svg()==before
    times['total']=sum(times.values())
    return original,times,dict(rows=len(original.table.row_ids),layers=len(payload['layers']),svg_bytes=len(svg.encode()))


def browser_run(page, browser, directory):
    """Use an ephemeral loopback callback; never use Chromium virtual-time budgets."""
    done=threading.Event();result=[];token=secrets.token_hex(16)
    script=(ROOT/'tools/benchmark_report_browser.js').read_text()
    script+='\n.then(result=>fetch("/'+token+'",{method:"POST",body:JSON.stringify(result)})).catch(error=>fetch("/'+token+'",{method:"POST",body:JSON.stringify({error:String(error.stack||error)})}));'
    page=page.replace('</html>','<script>'+script+'</script></html>').encode()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path!='/': self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(page)
        def do_POST(self):
            if self.path!='/'+token: self.send_error(404);return
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=20_000_000: self.send_error(413);return
            try: result.append(json.loads(self.rfile.read(length)))
            except ValueError: self.send_error(400);return
            self.send_response(204);self.end_headers();done.set()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with (directory/'chrome.log').open('w') as log, tempfile.TemporaryDirectory(prefix='inklet-report-chrome-') as profile:
            process=subprocess.Popen([browser,'--headless','--no-sandbox','--disable-gpu','--disable-background-networking',
                '--window-size=1365,768',f'--user-data-dir={profile}',f'http://127.0.0.1:{server.server_port}/'],stdout=log,stderr=log)
            try:
                if not done.wait(45): raise RuntimeError(f'Browser timed out; see {directory}/chrome.log')
            finally:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    report=result[0]
    if 'error' in report: raise RuntimeError(report['error'])
    if report['external_resources']: raise AssertionError(report['external_resources'])
    return report


def complete_results(cases):
    if len(cases)!=len(CASES) or {case['name'] for case in cases}!=set(CASES):
        raise ValueError('Missing or duplicate report cases')
    for case in cases:
        modes=[(b['renderer'],b['backend']) for b in case['browsers']]
        if len(modes)!=len(RENDERERS) or set(modes)!=set(RENDERERS):
            raise ValueError('Missing or duplicate renderer/backend results')
        checks=[*case['python_checks'],*(c for b in case['browsers'] for c in b['checks'])]
        if not case['python_checks'] or any(not b['checks'] for b in case['browsers']):
            raise ValueError('Missing budget checks')
        if any(not check['passed'] for check in checks):
            return False
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/report-benchmark')
    parser.add_argument('--budgets',type=Path,default=ROOT/'tests/performance/report-budgets.json')
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium'))
    args=parser.parse_args()
    if args.repeat<1: parser.error('repeat must be positive')
    if not args.browser: parser.error('Chrome/Chromium is required; browser gates cannot skip')
    budgets=json.loads(args.budgets.read_text())
    if set(budgets['cases'])!=set(CASES): raise ValueError('Budgets must cover every report')
    args.output.mkdir(parents=True,exist_ok=True);results=[]
    report=dict(version=inklet.__version__,python=sys.version,platform=platform.platform(),budgets=budgets,cases=results,
        method='Three fresh Python figures by default; warm process/font caches. Revision includes revised source scene construction. Browser: fresh process per renderer/backend, seven warm operations; submission and two real frame callbacks measured separately. Browser ready is navigation-to-ready plus two frames, excluding process launch. No virtual clock; no GPU latency or physical input latency claim.')
    for name in CASES:
        runs=[]
        for _ in range(args.repeat): figure,values,inventory=measure_python(name);runs.append(values)
        median={key:statistics.median(run[key] for run in runs) for key in runs[0]}
        case=dict(name=name,inventory=inventory,python_runs=runs,python_checks=check_budgets(median,budgets['cases'][name]['python']),browsers=[])
        results.append(case)
        for renderer,backend in RENDERERS:
            folder=args.output/name/renderer/backend;folder.mkdir(parents=True,exist_ok=True)
            page=figure.to_html(renderer=renderer,backend=backend)
            (folder/'figure.html').write_text(page)
            measured=browser_run(page,args.browser,folder)
            assert measured['backend']==backend, measured['backend']
            svg=measured.pop('svg');(folder/'browser.svg').write_text(svg)
            expected=figure.to_svg(measured['state']);(folder/'python.svg').write_text(expected)
            # Independent pixel comparison remains in acceptance; here validate state
            # and physical SVG extents as correctness guards alongside timing.
            from xml.etree import ElementTree as ET
            assert ET.fromstring(svg).attrib['viewBox']==ET.fromstring(expected).attrib['viewBox']
            median={key:statistics.median(value) for key,value in measured['records'].items()}
            checks=check_budgets(median,budgets['cases'][name]['browser'])
            worst={key:max(value) for key,value in measured['records'].items()}
            checks.extend({**c,'stage':c['stage']+'_worst'} for c in check_budgets(worst,budgets['cases'][name]['browser']))
            measured.update(renderer=renderer,checks=checks)
            case['browsers'].append(measured)
        (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,median,flush=True)
    passed=complete_results(results)
    report['passed']=passed
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(not passed)


if __name__=='__main__': raise SystemExit(main())
