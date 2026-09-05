"""Measured architecture modules with stable, named ports."""
from dataclasses import dataclass, field

from ..core import Diagram, Envelope, Rect, Vec2
from .spec import BuildSpec, fingerprint, freeze, length, materialize
from .compiler import LayoutError


@dataclass(eq=False)
class ModuleSpec(BuildSpec):
    """A label-sized module. Port coordinates are fractions of its box.

    Minimum dimensions, padding and label offsets are physical millimetres.
    A fixed height can be requested with max_height equal to min_height.
    """
    label: object
    min_width: float = 20
    min_height: float = 12
    pad: float = 3
    max_height: float | None = None
    ports: dict = field(default_factory=lambda: {'in':(0,.5), 'out':(1,.5)})
    text_style: dict = field(default_factory=dict)
    box_style: dict = field(default_factory=dict)
    label_offset: tuple = (0,0)

    def __post_init__(self):
        self._validate()

    def configure(self, label=None, **options):
        from dataclasses import replace
        candidate = replace(self, **options, **({} if label is None else {'label':label}))
        self.__dict__.update(candidate.__dict__)
        return self

    def _validate(self):
        from ..core import mm
        import math
        for name in ('min_width', 'min_height'): setattr(self,name,length(getattr(self,name), name))
        self.pad = length(self.pad, 'module padding', zero=True)
        self.label_offset = tuple(mm(v) for v in self.label_offset)
        if len(self.label_offset) != 2 or not all(math.isfinite(v) for v in self.label_offset):
            raise ValueError('label_offset needs two finite physical lengths')
        if self.max_height is not None:
            self.max_height = length(self.max_height, 'maximum height')
            if self.max_height < self.min_height: raise ValueError('maximum height is below minimum height')
        for name, point in self.ports.items():
            if not isinstance(name,str) or not name: raise ValueError('ports need non-empty names')
            if len(point) != 2 or any(not 0 <= float(v) <= 1 for v in point):
                raise ValueError('port coordinates must be fractions between 0 and 1')
        self.ports = {name:tuple(float(v) for v in point) for name,point in self.ports.items()}

    def signature(self, trail=()): return ('module', fingerprint(vars(self), trail))

    def render(self, context, width=None, height=None):
        from .. import box, text
        self._validate()
        label = materialize(self.label, context)
        body = label if isinstance(label, Diagram) else text(label, markup=False, **self.text_style)
        w = max(self.min_width, body.width+2*self.pad)
        h = max(self.min_height, body.height+2*self.pad)
        if self.max_height is not None and h > self.max_height:
            raise LayoutError('module label exceeds its maximum height; reduce lines or increase max_height')
        frame = box(width=w, height=h, pad=0, **self.box_style)
        frame = frame.translated(-frame.bbox.x0, -frame.bbox.y0)
        dx,dy = self.label_offset
        body = body.translated(w/2+dx-body.bbox.center.x, h/2+dy-body.bbox.center.y)
        node = Diagram(children=(frame,body), kind='module',
                       envelope_override=Envelope.from_rect(Rect(0,0,w,h)))
        for name,(x,y) in self.ports.items(): node.anchor(name, Vec2(x*w,y*h))
        return node


def module(label, **options):
    """Create a live architecture module; width follows measured label edits."""
    return ModuleSpec(label, **freeze(options))
