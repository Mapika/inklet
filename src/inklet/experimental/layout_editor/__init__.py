"""Local browser editing of composition layouts, labels and styles through Python."""
from __future__ import annotations

import copy
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ...document import Composition, document
from ...document.layout_overrides import _EDITORS
from ...document.layout_overrides import SCHEMA, _targets, _placement, _expression


class LayoutEditor:
    """Edit a live Composition layout, labels and styles with matching Python exports.

    Use as a context manager and open url while the context stays alive. The
    source recipe is retained but never edited. Refresh explicitly after source
    changes. Width/height optionally fix the containing document's millimetres;
    otherwise its size follows the composition. History retains at most 100 edits.
    """

    def __init__(self, recipe, *, width=None, height=None, preset=None):
        if not isinstance(recipe,Composition): raise TypeError('LayoutEditor needs a Composition')
        self.source=recipe
        self.width,self.height,self.preset=width,height,preset
        self._lock=threading.RLock()
        self._value={'schema':SCHEMA,'targets':{}}
        self._undo=[];self._redo=[];self._revision=0
        self._server=None;self._thread=None
        self._token=secrets.token_urlsafe(32)
        self._recipe,self._figure,self._report=self._build(self._value)

    def _build(self,value,missing='error'):
        recipe,report=self.source.with_layout_overrides(value,missing=missing)
        options=dict(width=self.width if self.width is not None else recipe.width*recipe.unit,
                     height=self.height if self.height is not None else recipe.height*recipe.unit,margin=0)
        if self.preset is None: doc=document(**options)
        else:
            from ...document import preset
            doc=preset(self.preset).document(**options)
        doc.add('composition',recipe)
        figure=doc.compile()
        # Verify export before publishing a new state to clients.
        figure.to_svg()
        recipe.layout_overrides(self.source)
        return recipe,figure,report

    @property
    def figure(self):
        """Last successfully compiled snapshot, ready for SVG/PDF/PNG export."""
        with self._lock:return self._figure

    def overrides(self):
        """Return independently owned JSON-compatible saved layout choices."""
        with self._lock:return copy.deepcopy(self._value)

    def _geometry(self):
        from ...core import Vec2
        from ...draw.coords import placed_anchor, plot_area
        root,resolved=self._figure.build()
        targets=_targets(self._recipe)
        geometry={}
        def visit(node,path=''):
            if node.kind=='composition-part' and node.name:
                path=path+'/'+node.name
                if path in targets:
                    parent,part,_=targets[path]
                    placement=resolved[node.id];box=placement.bbox
                    child=node.children[0]
                    if part.anchor=='area-nw':
                        area=plot_area(child);point=Vec2(area.x0,area.y0)
                    elif part.anchor is None:point=Vec2(0,0)
                    else:point=placed_anchor(child,part.anchor)
                    anchor=placement.world.apply(point)
                    inverse=placement.world.inverse()
                    if box is not None:
                        geometry[path]=dict(box=[box.x0,box.y0,box.width,box.height],
                            anchor=[anchor.x,anchor.y],
                            inverse=[inverse.a/parent.unit,inverse.b/parent.unit,
                                     inverse.c/parent.unit,inverse.d/parent.unit])
            for child in node.children:visit(child,path)
        visit(root)
        return geometry

    def _gesture(self,value):
        from ...document.composition import LayoutValue, _scale
        if (not isinstance(value,dict) or not {'path','dx','dy'}<=set(value) or
                not set(value)<={'path','dx','dy','factor','corner'}):
            raise ValueError('gesture needs path and finite figure-space dx/dy')
        for key in ('dx','dy'):
            if type(value[key]) not in (int,float) or not math.isfinite(value[key]):
                raise ValueError('gesture displacement must be finite')
        path=value['path'];geometry=self._geometry()
        if not isinstance(path,str) or path not in geometry:raise ValueError('unknown gesture target')
        _,part,_=_targets(self._recipe)[path]
        box=geometry[path]['box'];anchor=geometry[path]['anchor']
        dx,dy=value['dx'],value['dy'];fields={}
        if 'factor' in value:
            factor=_scale(value['factor'])
            corner=value.get('corner','se')
            if corner not in ('nw','ne','sw','se'):raise ValueError('invalid scale corner')
            # The opposite corner remains fixed even for custom placement ports.
            px=box[0]+(box[2] if 'w' in corner else 0)
            py=box[1]+(box[3] if 'n' in corner else 0)
            dx+=(1-factor)*(px-anchor[0]);dy+=(1-factor)*(py-anchor[1])
            fields['scale']=part.scale*factor
        elif 'corner' in value:raise ValueError('scale corner requires a factor')
        a,b,c,d=geometry[path]['inverse'];ux,uy=a*dx+c*dy,b*dx+d*dy
        def offset(current,delta):
            if type(current) in (int,float):return current+delta
            # Fold repeated mouse offsets instead of growing expression depth.
            if isinstance(current,LayoutValue) and current.operation=='+' and type(current.args[1]) in (int,float):
                return LayoutValue('+',(current.args[0],current.args[1]+delta))
            return LayoutValue('+',(current,delta))
        for key,delta in (('x',ux),('y',uy)):
            if abs(delta)>1e-10:fields[key]=_expression(offset(getattr(part,key),delta),encode=True)
        return dict(path=path,placement=fields) if fields else None

    def snapshot(self):
        """Return current controls, revision and preview without rebuilding."""
        with self._lock:
            targets={}
            for path,(_,part,item) in _targets(self._recipe).items():
                entry={}
                if part is not None:
                    entry['placement']=_placement({k:getattr(part,k) for k in ('x','y','anchor','width','height','scale')},encode=True)
                if isinstance(item,Composition):
                    entry['page']={k:getattr(item,k) for k in ('width','height','unit','fit_top')}
                for group,adapter in _EDITORS.items():
                    controls={key:fields for key,(fields,_) in adapter.targets(item).items()}
                    if controls: entry[group]=controls
                targets[path]=entry
            return dict(revision=self._revision,targets=targets,overrides=self.overrides(),
                        undo=bool(self._undo),redo=bool(self._redo),report=copy.deepcopy(self._report),
                        svg=self._figure.to_svg(),geometry=self._geometry(),
                        viewbox=[float(x) for x in ET.fromstring(self._figure.to_svg()).attrib['viewBox'].split()])

    def _aliases(self, path, group):
        targets=_targets(self._recipe)
        if path not in targets:return [path]
        parent,part,item=targets[path]
        if group in ('page','labels','styles'):return [name for name,(_,_,child) in targets.items() if child is item]
        return [name for name,(owner,other,_) in targets.items()
                if owner is parent and other is not None and part is not None and other.name==part.name]

    def command(self, action, value=None, *, revision=None, missing='error'):
        """Compile a command atomically; a stale revision or failed build changes nothing.

        Actions: gesture (figure-space move/uniform scale), edit (placement/page/labels/styles), reset, load
        (override JSON), undo, redo and refresh (current source; clears history).
        Refresh may explicitly drop removed targets with missing='drop'.
        """
        with self._lock:
            if revision is not None and (type(revision) is not int or revision!=self._revision):
                raise ValueError('stale editor revision; reload the current editor state')
            if action=='gesture':
                value=self._gesture(value)
                if value is None:return self.snapshot()
                action='edit'
            candidate=copy.deepcopy(self._value)
            if action=='edit':
                if (not isinstance(value,dict) or 'path' not in value or
                        not set(value)<={'path','placement','page','labels','styles'} or len(value)<2):
                    raise ValueError('edit needs a path and placement/page/labels/styles fields')
                path=value['path']
                if not isinstance(path,str):raise ValueError('edit path must be a string')
                for group,fields in value.items():
                    if group=='path':continue
                    if not isinstance(fields,dict) or not fields:raise ValueError('edit fields must be nonempty objects')
                    for alias in self._aliases(path,group):
                        destination=candidate['targets'].setdefault(alias,{}).setdefault(group,{})
                        if group in _EDITORS:
                            for key,changes in _EDITORS[group].validate(fields).items():
                                destination.setdefault(key,{}).update(changes)
                        else: destination.update(fields)
            elif action=='reset':
                if not isinstance(value,str) or value not in _targets(self._recipe):raise ValueError('unknown reset target')
                for group in ('placement','page','labels','styles'):
                    for alias in self._aliases(value,group):
                        entry=candidate['targets'].get(alias,{})
                        entry.pop(group,None)
                        if not entry:candidate['targets'].pop(alias,None)
            elif action=='load': candidate=copy.deepcopy(value)
            elif action=='undo':
                if not self._undo:raise ValueError('nothing to undo')
                candidate=copy.deepcopy(self._undo[-1])
            elif action=='redo':
                if not self._redo:raise ValueError('nothing to redo')
                candidate=copy.deepcopy(self._redo[-1])
            elif action!='refresh':raise ValueError('unknown editor command')
            recipe,figure,report=self._build(candidate,missing if action=='refresh' else 'error')
            normalized=recipe.layout_overrides(self.source)
            if action=='refresh':self._undo.clear();self._redo.clear()
            elif action=='undo':self._redo.append(self._value);self._undo.pop()
            elif action=='redo':self._undo.append(self._value);self._redo.pop()
            elif normalized!=self._value:
                self._undo.append(self._value);self._undo=self._undo[-100:];self._redo.clear()
            self._value=normalized
            self._recipe,self._figure,self._report=recipe,figure,report
            self._revision+=1
            return self.snapshot()

    def _html(self):
        return (Path(__file__).with_name('page.html').read_text(encoding='utf-8').replace('__TOKEN__',self._token)
                .replace('/*WORKSPACE_CSS*/',Path(__file__).with_name('workspace.css').read_text(encoding='utf-8'))
                .replace('<!--WORKSPACE-->',Path(__file__).with_name('workspace.js').read_text(encoding='utf-8'))
                .replace('<!--GESTURES-->',Path(__file__).with_name('gestures.js').read_text(encoding='utf-8')))

    def start(self, *, port=0):
        """Start a loopback-only editor server; port=0 chooses a free local port."""
        if self._server is not None:return self
        editor=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,payload,kind='application/json',filename=None):
                if not isinstance(payload,bytes):payload=json.dumps(payload,allow_nan=False).encode()
                self.send_response(status)
                self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
                self.end_headers();self.wfile.write(payload)
            def local(self):
                if self.headers.get('Host')!=editor.url.removeprefix('http://'):
                    self.reply(403,{'error':'invalid editor host'});return False
                return True
            def do_GET(self):
                if not self.local():return
                try:
                    with editor._lock:
                        resource=urlsplit(self.path)
                        query=parse_qs(resource.query)
                        if 'revision' in query and query['revision']!=[str(editor._revision)]:
                            raise ValueError('stale editor revision; reload before exporting')
                        if resource.path=='/':
                            page=editor._html()
                            self.reply(200,page.encode(),'text/html; charset=utf-8')
                        elif resource.path=='/state':self.reply(200,editor.snapshot())
                        elif resource.path=='/layout.json':self.reply(200,editor.overrides(),filename='layout-overrides.json')
                        elif resource.path=='/figure.svg':self.reply(200,editor.figure.to_svg().encode(),'image/svg+xml',filename='figure.svg')
                        elif resource.path=='/figure.pdf':self.reply(200,editor.figure.to_pdf(),'application/pdf',filename='figure.pdf')
                        else:self.reply(404,{'error':'unknown editor resource'})
                except Exception as error:self.reply(400,{'error':str(error)})
            def do_POST(self):
                if not self.local():return
                if (self.path!='/command' or self.headers.get('X-Inklet-Token')!=editor._token or
                        self.headers.get('Origin',editor.url)!=editor.url):
                    self.reply(403,{'error':'invalid editor request'});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=1_000_000:raise ValueError('editor request must be between 1 and 1000000 bytes')
                    payload=json.loads(self.rfile.read(size))
                    if (not isinstance(payload,dict) or not {'action','revision'}<=set(payload) or
                            not set(payload)<={'action','revision','value','missing'} or type(payload['revision']) is not int):
                        raise ValueError('invalid editor command envelope')
                    self.reply(200,editor.command(**payload))
                except Exception as error:self.reply(400,{'error':str(error)})
        self._server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self._thread=threading.Thread(target=self._server.serve_forever,daemon=True)
        self._thread.start()
        return self

    @property
    def url(self):
        """Local URL while the server is running."""
        if self._server is None:raise RuntimeError('editor server is not running')
        return f'http://127.0.0.1:{self._server.server_port}'

    def close(self):
        """Stop the local server; compiled output and saved choices remain accessible."""
        if self._server is not None:
            self._server.shutdown();self._server.server_close();self._thread.join()
            self._server=None;self._thread=None

    def __enter__(self):return self.start()
    def __exit__(self,*args):self.close()
