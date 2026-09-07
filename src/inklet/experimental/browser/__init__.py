"""Experimental scatter documents for offline browser rendering.

Python owns layout and text shaping. The browser consumes physical geometry,
clips marks to measured plot areas, and preserves explicit row identities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from ...core import resolve
from ..selection import KeyedTable, SelectionState

SCHEMA = 'inklet.browser-scatter/0.1'
STATE_SCHEMA = 'inklet.browser-view/0.1'


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value)!=4 or not all(_finite(v) for v in value):
        raise ValueError('viewport needs four finite numbers')
    if value[2]<=0 or value[3]<=0: raise ValueError('viewport dimensions must be positive')
    return tuple(value)


@dataclass(frozen=True)
class ScatterView:
    """A linear scatter view with explicit domains and physical marker size."""
    name: str
    x: str
    y: str
    x_domain: tuple[float, float]
    y_domain: tuple[float, float]
    x_label: str = ''
    y_label: str = ''
    radius_mm: float = .45
    color: str = '#34786b'

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if any(not isinstance(v,str) or not v for v in (self.x,self.y)):
            raise ValueError('coordinate columns must be nonempty strings')
        if any(not isinstance(v,str) for v in (self.x_label,self.y_label)):
            raise ValueError('axis labels must be strings')
        for name in ('x_domain','y_domain'):
            domain=tuple(getattr(self,name))
            if len(domain)!=2 or not all(_finite(v) for v in domain) or domain[0]==domain[1] or not math.isfinite(domain[1]-domain[0]):
                raise ValueError('linear domains need two distinct finite endpoints')
            object.__setattr__(self,name,domain)
        if not _finite(self.radius_mm) or not 0<self.radius_mm<=10:
            raise ValueError('radius must be positive and at most 10 mm')
        if not isinstance(self.color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',self.color):
            raise ValueError('color must be a six-digit hex colour')


class BrowserScatter:
    """A compiled, immutable JSON snapshot for one or more coordinated views.

    Supported marks are circular scatter points with linear axes. Missing/null
    coordinate pairs are omitted per view. Other nonnumeric coordinates fail.
    Browser zoom navigates the page; it does not recompute data domains or ticks.
    """
    def __init__(self, table: KeyedTable, views, *, width=190):
        import inklet as i
        views=tuple(views)
        if not views or len(views)>4 or any(not isinstance(v,ScatterView) for v in views):
            raise ValueError('provide one to four ScatterView definitions')
        if len({v.name for v in views})!=len(views): raise ValueError('view names must be unique')
        doc=i.document(width=width,columns=len(views),gap=9,margin=6).letters()
        for view in views:
            for column in (view.x,view.y):
                if column not in table.columns: raise ValueError(f'unknown column: {column}')
                if any(v is not None and not _finite(v) for v in table.columns[column]):
                    raise ValueError(f'coordinate column {column!r} must be numeric or null')
            p=i.plot_spec(x=view.x_domain,y=view.y_domain,height=58)
            p.axes(x=view.x_label or view.x,y=view.y_label or view.y)
            doc.add(view.name,p,row=0,column=len(doc._cells))
        figure=doc.compile()
        if any(d.severity=='error' for d in figure.diagnostics): raise ValueError(figure.report())
        # Outlined glyphs preserve Python's shaping without external fonts or
        # browser font loading. HTML supplies textual/data alternatives.
        frame=figure.to_svg(text='outline')
        root=ET.fromstring(frame)
        width_mm,height_mm=map(float,(root.attrib['width'][:-2],root.attrib['height'][:-2]))
        cells={p.diagram.name:p for p in resolve(figure.root).values() if p.diagram.kind=='document-cell'}
        layers=[]
        for view in views:
            placement=cells[view.name]; rect=placement.diagram.notes['plot_area']
            # Document cell transforms are translations; fail if that contract changes.
            t=placement.world
            if (t.a,t.b,t.c,t.d)!=(1.,0.,0.,1.): raise ValueError('unsupported transformed plot cell')
            bounds=[rect.x0+t.e,rect.y0+t.f,rect.width,rect.height]
            bounds=[round(v,6) for v in bounds]
            points=[];missing=0
            for key,x,y in zip(table.row_ids,table.columns[view.x],table.columns[view.y]):
                if x is None or y is None: missing+=1;continue
                px=bounds[0]+(x-view.x_domain[0])/(view.x_domain[1]-view.x_domain[0])*bounds[2]
                py=bounds[1]+(1-(y-view.y_domain[0])/(view.y_domain[1]-view.y_domain[0]))*bounds[3]
                if not math.isfinite(px) or not math.isfinite(py): raise ValueError('projected coordinate overflow')
                points.append([key,round(px,6),round(py,6)])
            layers.append(dict(name=view.name,x=view.x,y=view.y,clip=bounds,points=points,
                               radius=view.radius_mm,color=view.color,missing=missing))
        payload=dict(schema=SCHEMA,table=table.name,data_digest=table.digest,row_ids=table.row_ids,
                     columns=dict(table.columns),width=width_mm,height=height_mm,frame=frame,layers=layers)
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)
        payload['scene_digest']=hashlib.sha256(raw.encode()).hexdigest()
        self._json=json.dumps(payload,separators=(',',':'),allow_nan=False)
        self.table=table

    def payload(self):
        """Return an independent copy of the portable scene data."""
        return json.loads(self._json)

    def state(self, selection=None, *, viewport=None):
        selection=selection or SelectionState.for_table(self.table)
        selection.validate(self.table)
        payload=self.payload()
        result=dict(schema=STATE_SCHEMA,scene_digest=payload['scene_digest'],
                    selection=json.loads(selection.to_json()),
                    viewport=list(_box([0,0,payload['width'],payload['height']] if viewport is None else viewport)))
        self.validate_state(result)
        return result

    def validate_state(self, value):
        if not isinstance(value,dict) or set(value)!={'schema','scene_digest','selection','viewport'}:
            raise ValueError('invalid browser state fields')
        if value['schema']!=STATE_SCHEMA or value['scene_digest']!=self.payload()['scene_digest']:
            raise ValueError('browser state belongs to a different scene revision')
        selection=SelectionState.from_json(json.dumps(value['selection']))
        selection.validate(self.table)
        viewport=_box(value['viewport'])
        p=self.payload()
        if (abs(viewport[0])>p['width']*100 or abs(viewport[1])>p['height']*100 or
                not p['width']/100<=viewport[2]<=p['width']*100 or
                not p['height']/100<=viewport[3]<=p['height']*100):
            raise ValueError('viewport is outside the preview limits')
        return selection,viewport

    def to_svg(self, state=None):
        """Export the selected page viewport with clipped vector scatter marks."""
        selection,viewport=self.validate_state(state if state is not None else self.state())
        p=self.payload();root=ET.fromstring(p['frame']);ns='{http://www.w3.org/2000/svg}'
        root.set('viewBox',' '.join(map(str,viewport)))
        root.set('width',f'{viewport[2]}mm');root.set('height',f'{viewport[3]}mm')
        # Mark layer first, measured frame/text afterwards. Background remains first.
        marks=ET.Element(ns+'g',{'id':'browser-marks'})
        highlights=ET.Element(ns+'g',{'id':'browser-selection'})
        defs=ET.SubElement(marks,ns+'defs')
        visible=set(self.table.row_ids if selection.visible_ids is None else selection.visible_ids)
        selected=set(selection.selected_ids)
        for n,layer in enumerate(p['layers']):
            clip_id=f'browser-clip-{n}'
            clip=ET.SubElement(defs,ns+'clipPath',{'id':clip_id})
            ET.SubElement(clip,ns+'rect',dict(zip(('x','y','width','height'),map(str,layer['clip']))))
            group=ET.SubElement(marks,ns+'g',{'clip-path':f'url(#{clip_id})'})
            highlight=ET.SubElement(highlights,ns+'g',{'clip-path':f'url(#{clip_id})'})
            chosen=[]
            for key,x,y in layer['points']:
                if key not in visible: continue
                ET.SubElement(group,ns+'circle',{'cx':str(x),'cy':str(y),'r':str(layer['radius']),
                    'fill':layer['color'],'fill-opacity':'0.65'})
                if key in selected: chosen.append((x,y))
            for x,y in chosen:
                ET.SubElement(highlight,ns+'circle',{'cx':str(x),'cy':str(y),'r':str(layer['radius']+.3),
                    'fill':'none','stroke':'#bd5636','stroke-width':'.3'})
        root.insert(1,marks)
        root.append(highlights)
        ET.register_namespace('','http://www.w3.org/2000/svg')
        ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
        return ET.tostring(root,encoding='unicode')

    def to_html(self, *, title='Linked scatter views', backend='svg'):
        if backend not in ('svg','canvas','hybrid'): raise ValueError('unknown browser backend')
        template=Path(__file__).with_name('page.html').read_text(encoding='utf-8')
        script=Path(__file__).with_name('runtime.js').read_text(encoding='utf-8')
        script=script.replace("/*DEFAULT_BACKEND*/'svg'",json.dumps(backend))
        return template.replace('<!--TITLE-->',html.escape(title)).replace('/*PAYLOAD*/',self._json.replace('<','\\u003c')).replace('/*RUNTIME*/',script)
