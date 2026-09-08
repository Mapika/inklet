"""Measured native Inklet drawings associated with explicit table identities."""
import base64
from dataclasses import dataclass
import math
import re

from ...core import Diagram, Envelope
from ...render.svg import to_svg
from ...figure import Figure, apply_theme
from ...render.paint import resolve_paint
from ...render.bounds import painted_bounds


@dataclass(frozen=True)
class DrawingItem:
    """A native drawing in panel-local mm, optionally associated with table rows.

    Empty IDs describe an unpickable reference. Multiple IDs require every row
    to be visible, useful for a connector between two components. Picking uses
    an explicit rectangular hit box, or the drawing's padded bounding box.
    """
    ids: tuple[str, ...]
    diagram: Diagram
    hit_box: tuple[float, float, float, float] | None = None
    description: str = ''
    pickable: bool = True
    highlight: bool = True

    def __post_init__(self):
        if isinstance(self.ids,(str,bytes)): raise ValueError('drawing IDs must be a sequence')
        ids=tuple(self.ids)
        if any(not isinstance(k,str) or not k for k in ids) or len(set(ids))!=len(ids):
            raise ValueError('drawing IDs must be unique nonempty strings')
        if not isinstance(self.diagram,Diagram): raise ValueError('drawing item needs a native Diagram')
        if not isinstance(self.description,str): raise ValueError('drawing description must be a string')
        if type(self.pickable) is not bool or type(self.highlight) is not bool:
            raise ValueError('pickable and highlight must be booleans')
        object.__setattr__(self,'ids',ids)
        if self.hit_box is not None:
            box=tuple(self.hit_box)
            if (len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                    or box[2]<=0 or box[3]<=0):
                raise ValueError('hit_box needs finite x, y and positive width, height in panel mm')
            object.__setattr__(self,'hit_box',box)


@dataclass(frozen=True)
class DrawingView:
    """Compile native drawings at the measured panel size in Python.

    build(table, width_mm, height_mm) returns DrawingItems. The browser receives
    self-contained outlined SVG assets and hit boxes, never Python callbacks.
    No automatic geometric silhouette picking or camera manipulation is implied.
    """
    name: str
    build: object

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if not callable(self.build): raise ValueError('drawing build must be callable')

    def layer(self,table,bounds):
        items=tuple(self.build(table,bounds[2],bounds[3]));marks=[];assigned=set()
        for item in items:
            if not isinstance(item,DrawingItem): raise ValueError('drawing build must return DrawingItems')
            unknown=set(item.ids)-set(table.row_ids)
            if unknown: raise ValueError(f'drawing/table ID mismatch: {sorted(unknown)}')
            assigned.update(item.ids)
            program=resolve_paint(apply_theme(item.diagram,Figure().theme),stable_ids=True)
            root=program.root
            ink=painted_bounds(root,root.transform,root.style)
            rect=(root.bbox if ink is None else root.bbox.union(ink)).pad(.5)
            x,y,w,h=rect.x0,rect.y0,rect.width,rect.height
            if any(not math.isfinite(v) for v in (x,y,w,h)) or w<=0 or h<=0:
                raise ValueError('drawing needs positive finite bounds')
            if x < -1e-6 or y < -1e-6 or x+w > bounds[2]+1e-6 or y+h > bounds[3]+1e-6:
                raise ValueError(f'drawing {item.ids} exceeds its measured panel; adjust its layout')
            hx,hy,hw,hh=item.hit_box or (x,y,w,h)
            if hx < 0 or hy < 0 or hx+hw > bounds[2]+1e-6 or hy+hh > bounds[3]+1e-6:
                raise ValueError('drawing hit box exceeds its panel')
            viewport=Diagram(id='drawing-viewport',children=(root,),envelope_override=Envelope.from_rect(rect))
            source=to_svg(viewport,text='outline')
            href='data:image/svg+xml;base64,'+base64.b64encode(source.encode()).decode()
            marks.append(dict(kind='image',ids=item.ids,reference=not item.ids,
                geometry=[round(bounds[0]+x,6),round(bounds[1]+y,6),round(w,6),round(h,6)],
                bounds=[round(bounds[0]+hx,6),round(bounds[1]+hy,6),round(bounds[0]+hx+hw,6),round(bounds[1]+hy+hh,6)],
                href=href,description=item.description,pickable=item.pickable,highlight=item.highlight))
        return dict(name=self.name,clip=bounds,marks=marks,color='#34786b',
            drawing=dict(unit='panel mm',picking='rectangular hit boxes; first associated ID',
                         omitted_ids=[k for k in table.row_ids if k not in assigned]))
