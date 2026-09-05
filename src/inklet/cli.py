"""Local build, dependency checks and source-watching preview server."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
import math
import signal
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import quote, urlsplit


def doctor():
    """Return available optional renderers without importing heavy dependencies."""
    return {
        'python': sys.version.split()[0],
        'pillow': importlib.util.find_spec('PIL') is not None,
        'numpy': importlib.util.find_spec('numpy') is not None,
        'chromium': next((p for n in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(n))),None),
        'poppler': shutil.which('pdftoppm'),
        'fontconfig': shutil.which('fc-match'),
    }


def load_figure(script):
    """Execute an author script and obtain its make_document()/make_figure()."""
    path=Path(script).resolve()
    before=list(sys.path)
    sys.path.insert(0,str(path.parent))
    try:
        namespace=runpy.run_path(str(path),run_name='__inklet_build__')
        for name in ('make_document','make_figure'):
            if callable(namespace.get(name)):
                result=namespace[name]()
                break
        else:
            result=namespace.get('doc',namespace.get('fig'))
        if result is None:
            raise ValueError('author script must define make_document(), make_figure(), doc or fig')
        from .document import Document
        if isinstance(result,Document):result=result.compile()
        if not all(hasattr(result,name) for name in ('save','export','lint')):
            raise TypeError('author script must return a Document, CompiledFigure or Figure')
        return result
    finally:
        sys.path[:]=before


def build(script,output,name,dpi=None,vectors_only=False,compare_pdf=True,compare_to=None):
    if vectors_only and compare_to is not None:
        raise ValueError('--compare-to requires a review bundle, not --vectors-only')
    figure=load_figure(script)
    output=Path(output).resolve()
    if vectors_only:
        output.mkdir(parents=True,exist_ok=True)
        text=getattr(figure,'metadata',{}).get('publication',{}).get('text','embed')
        figure.save(output/f'{name}.svg',output/f'{name}.pdf',text=text)
        target=output/f'{name}.svg'
    else:
        target=figure.export(output,name=name,compare_pdf=compare_pdf,compare_to=compare_to,
                            **({} if dpi is None else {'dpi':dpi}))['review']
    print(target)
    return 0


def _watch_files(script,extra):
    """Watch author code plus explicitly supplied data/asset files or directories."""
    paths={Path(script).resolve()}
    roots=[Path(script).resolve().parent,*map(lambda p:Path(p).resolve(),extra)]
    for root in roots:
        if root.is_file():paths.add(root)
        elif root.is_dir():
            # Author-directory code is automatic; explicit directories include data.
            pattern='*.py' if root==Path(script).resolve().parent else '*'
            paths.update(p for p in root.rglob(pattern) if p.is_file() and
                         not any(part.startswith('.') or part in ('__pycache__','node_modules','out') for part in p.relative_to(root).parts))
    return tuple(sorted((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in paths if p.exists()))


def watch(script,output,*,name='figure',dpi=None,port=8765,interval=.5,extra=(),compare_pdf=True,compare_to=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    state={'generation':0,'building':False,'error':None}
    active={'process':None}
    lock=threading.Lock();stop=threading.Event()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/status':
                with lock:payload=json.dumps(state).encode()
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
            elif path=='/':
                payload=f'''<!doctype html><meta charset="utf-8"><title>Inklet preview</title>
<style>body{{font:14px system-ui;margin:0}}header{{padding:10px 20px}}iframe{{width:100%;height:calc(100vh - 65px);border:0}}pre{{white-space:pre-wrap;color:#a22;padding:12px}}</style>
<header id="status">Building…</header><pre id="error" hidden></pre><iframe id="review" title="Figure review"></iframe>
<script>let generation=0;async function poll(){{try{{const s=await(await fetch('/status',{{cache:'no-store'}})).json();document.getElementById('status').textContent=s.building?'Building…':s.error?'Build failed; showing the last successful figure':'Watching source files';const error=document.getElementById('error');error.hidden=!s.error;error.textContent=s.error||'';if(s.generation!==generation){{generation=s.generation;document.getElementById('review').src='{quote(name)}.html?v='+generation}}}}catch(e){{document.getElementById('status').textContent='Preview server disconnected'}}}}setInterval(poll,500);poll();</script>'''.encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers();self.wfile.write(payload)
            else:super().do_GET()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,directory=str(output)))
    def rebuild():
        previous=None
        while not stop.is_set():
            try:current=_watch_files(script,extra)
            except OSError:
                stop.wait(interval);continue
            if current!=previous:
                previous=current
                with lock:state.update(building=True,error=None)
                command=[sys.executable,'-m','inklet','build',str(Path(script).resolve()),
                         '--output',str(output),'--name',name]
                if dpi is not None: command.extend(['--dpi',str(dpi)])
                reference=compare_to or (output/f'{name}-manifest.json' if (output/f'{name}-manifest.json').exists() else None)
                if reference is not None: command.extend(['--compare-to',str(reference)])
                if not compare_pdf:command.append('--no-pdf-preview')
                try:
                    with lock:
                        if stop.is_set(): break
                        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                                 text=True,start_new_session=(os.name=='posix'))
                        active['process']=process
                    stdout,stderr=process.communicate(timeout=120)
                    with lock:
                        state['building']=False
                        if process.returncode:state['error']=(stderr or stdout)[-12000:]
                        else:state['generation']+=1
                except (OSError,subprocess.TimeoutExpired) as error:
                    if active['process'] is not None:
                        terminate(active['process'])
                    with lock:state.update(building=False,error=str(error))
                finally:
                    with lock:active['process']=None
            stop.wait(interval)
    def terminate(process):
        if process.poll() is None:
            if os.name=='posix': os.killpg(process.pid,signal.SIGTERM)
            else: process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill();process.wait()
    worker=threading.Thread(target=rebuild,daemon=True);worker.start()
    print(f'Inklet preview: http://127.0.0.1:{server.server_port}/',flush=True)
    previous_signal=None
    if threading.current_thread() is threading.main_thread():
        def interrupted(signum,frame): raise KeyboardInterrupt
        previous_signal=signal.signal(signal.SIGTERM,interrupted)
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:
        stop.set();server.server_close()
        with lock:process=active['process']
        if process is not None:terminate(process)
        worker.join(timeout=4)
        if previous_signal is not None:signal.signal(signal.SIGTERM,previous_signal)
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(prog='inklet',description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='check optional preview dependencies')
    for name in ('build','watch'):
        p=sub.add_parser(name)
        p.add_argument('script',type=Path)
        p.add_argument('--output',type=Path,default=Path('out/review'))
        p.add_argument('--name',default='figure')
        p.add_argument('--dpi',type=float,help='preview DPI; defaults to the publication profile or 150')
        p.add_argument('--compare-to',type=Path,help='previous bundle manifest or directory')
        p.add_argument('--no-pdf-preview',action='store_true')
        if name=='build':p.add_argument('--vectors-only',action='store_true')
        else:
            p.add_argument('--port',type=int,default=8765)
            p.add_argument('--interval',type=float,default=.5)
            p.add_argument('--watch',type=Path,action='append',default=[])
    args=parser.parse_args(argv)
    try:
        if args.command=='doctor':
            print(json.dumps(doctor(),indent=2));return 0
        from .render.bundle import validate_options
        validate_options(args.name,150 if args.dpi is None else args.dpi,'embed')
        if args.command=='build':
            return build(args.script,args.output,args.name,args.dpi,args.vectors_only,not args.no_pdf_preview,args.compare_to)
        if not math.isfinite(args.interval) or args.interval<=0:parser.error('--interval must be finite and positive')
        return watch(args.script,args.output,name=args.name,dpi=args.dpi,port=args.port,
                     interval=args.interval,extra=args.watch,compare_pdf=not args.no_pdf_preview,compare_to=args.compare_to)
    except Exception as error:
        print(f'Inklet: {type(error).__name__}: {error}',file=sys.stderr)
        return 1
