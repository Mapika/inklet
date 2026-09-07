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
    max_width wraps string labels; oversized unbreakable content raises.
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
    max_width: float | None = None

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
        if self.max_width is not None:
            self.max_width = length(self.max_width, 'maximum width')
            if self.max_width < self.min_width: raise ValueError('maximum width is below minimum width')
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
        dx,dy = self.label_offset
        horizontal = 2*(self.pad+abs(dx))
        vertical = 2*(self.pad+abs(dy))
        options = {'markup':False, **self.text_style}
        if self.max_width is not None:
            available = self.max_width-horizontal
            if available <= 0:
                raise LayoutError('module maximum width leaves no room for its label and padding')
            from ..core import mm
            requested = options.get('width')
            options['width'] = available if requested is None else min(mm(requested), available)
        body = label if isinstance(label, Diagram) else text(label, **options)
        w = max(self.min_width, body.width+horizontal)
        h = max(self.min_height, body.height+vertical)
        if self.max_width is not None and w > self.max_width+1e-7:
            raise LayoutError('module label exceeds its maximum width; shorten unbreakable text or increase max_width')
        if self.max_height is not None and h > self.max_height:
            raise LayoutError('module label exceeds its maximum height; reduce lines or increase max_height')
        frame = box(width=w, height=h, pad=0, **self.box_style)
        frame = frame.translated(-frame.bbox.x0, -frame.bbox.y0)
        body = body.translated(w/2+dx-body.bbox.center.x, h/2+dy-body.bbox.center.y)
        node = Diagram(children=(frame,body), kind='module',
                       envelope_override=Envelope.from_rect(Rect(0,0,w,h)))
        for name,(x,y) in self.ports.items(): node.anchor(name, Vec2(x*w,y*h))
        return node


def module(label, **options):
    """Create a measured module with fractional ports.

    Width follows label edits. Set max_width to wrap text within a physical
    limit, including padding and label_offset. Unbreakable text or Diagram
    labels that exceed the limit raise LayoutError; labels are never scaled.
    """
    return ModuleSpec(label, **freeze(options))
