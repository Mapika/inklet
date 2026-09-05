"""Measured, named composition constraints for irregular scientific figures."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import operator
import re

from ..core import Affine, Diagram, Envelope, Rect
from ..draw.coords import placed_anchor, plot_area
from .spec import BuildSpec, ComponentSpec, fingerprint, freeze, length
from .compiler import LayoutError


@dataclass(frozen=True)
class LayoutValue:
    """A scalar layout expression evaluated after its dependencies are measured."""
    operation: str
    args: tuple

    def __add__(self, other): return LayoutValue('+', (self, other))
    def __radd__(self, other): return LayoutValue('+', (other, self))
    def __sub__(self, other): return LayoutValue('-', (self, other))
    def __rsub__(self, other): return LayoutValue('-', (other, self))
    def __mul__(self, other): return LayoutValue('*', (self, other))
    def __rmul__(self, other): return LayoutValue('*', (other, self))
    def __truediv__(self, other): return LayoutValue('/', (self, other))
    def __neg__(self): return self * -1


@dataclass(frozen=True)
class _Part:
    name: str
    item: object
    x: object = 0
    y: object = 0
    anchor: str | None = None
    width: object = None
    height: object = None


@dataclass(eq=False)
class Composition(BuildSpec):
    """A figure assembled from named children and measured expressions.

    Coordinates and expressions use `unit` millimetres (default 1). Plot width
    and height describe data regions. Other children retain their authored size
    unless explicit dimensions are provided. `anchor=None` preserves the local
    coordinate frame; `nw`, `center`, registered ports and `area-nw` align a
    measured point to (x, y). Layout never scales text or strokes.
    """
    width: float
    height: float
    unit: float = 1
    fit_top: bool = False
    _parts: list = field(default_factory=list, repr=False)
    _constraints: list = field(default_factory=list, repr=False)
    _links: list = field(default_factory=list, repr=False)
    _annotations: list = field(default_factory=list, repr=False)
    bindings: dict = field(default_factory=dict)

    def __post_init__(self):
        self.width = length(self.width, 'composition width')
        self.height = length(self.height, 'composition height')
        self.unit = length(self.unit, 'composition unit')

    @property
    def page_width(self): return LayoutValue('page', ('width',))

    @property
    def page_height(self): return LayoutValue('page', ('height',))

    def measure(self, name, dimension='width'):
        """Reference a child's measured width or height, in composition units."""
        if dimension not in ('width', 'height'): raise ValueError('measure needs width or height')
        return LayoutValue('measure', (name, dimension))

    def point(self, name, anchor='center'):
        """Reference a placed child's compass point or registered port."""
        return tuple(LayoutValue('point', (name, anchor, axis)) for axis in ('x', 'y'))

    def add(self, name, item, *, x=0, y=0, anchor=None, width=None, height=None):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
            raise ValueError('component names start with a letter and contain letters, digits, underscores or hyphens')
        if any(part.name == name for part in self._parts): raise LayoutError(f'duplicate component {name!r}')
        self._parts.append(_Part(name, item, x, y, anchor, width, height))
        return item

    def __getitem__(self, name):
        for part in self._parts:
            if part.name == name: return part.item
        return self.bindings[name]

    def replace(self, name, item):
        """Replace a child while preserving its placement and dependent references."""
        from dataclasses import replace
        for index,part in enumerate(self._parts):
            if part.name == name:
                self._parts[index] = replace(part,item=item)
                return item
        raise KeyError(name)

    def constrain(self, value, *, minimum=0, message='composition needs more space'):
        """Require an expression to meet a minimum; fail before drawing."""
        self._constraints.append((value, minimum, message))
        return self

    def link(self, source, target, **options):
        """Route a branch or return between named children (`name:port`)."""
        self._links.append((source, target, freeze(options)))
        return self

    def annotate(self, target, text, **options):
        """Place a measured callout after every child and connection exists."""
        self._annotations.append((target, text, freeze(options)))
        return self

    def signature(self, trail=()):
        return ('composition', self.width, self.height, self.unit, self.fit_top,
                tuple(fingerprint(vars(p), trail) for p in self._parts),
                fingerprint((self._constraints, self._links, self._annotations, self.bindings), trail))

    def render(self, context, width=None, height=None):
        from ..figure import Figure
        from ..links import route_all
        from ..core import resolve
        self.__post_init__()
        page = dict(width=self.width if width is None else width/self.unit,
                    height=self.height if height is None else height/self.unit)
        parts = {p.name: p for p in self._parts}
        built, placed, active = {}, {}, set()

        def evaluate(value):
            if isinstance(value, LayoutValue):
                op, args = value.operation, value.args
                if op == 'page': result = page[args[0]]
                elif op == 'measure': result = getattr(build(args[0]), args[1])/self.unit
                elif op == 'point':
                    wrapper = place(args[0])
                    result = getattr(wrapper.transform.apply(placed_anchor(build(args[0]), args[1])), args[2])/self.unit
                else: result = {'+':operator.add, '-':operator.sub, '*':operator.mul,
                                '/':operator.truediv}[op](*(evaluate(a) for a in args))
                if not math.isfinite(result): raise LayoutError('layout expression must be finite')
                return result
            if isinstance(value, dict): return {k:evaluate(v) for k,v in value.items()}
            if isinstance(value, (list, tuple)): return tuple(evaluate(v) for v in value)
            return value

        def guarded(kind, name, action):
            key = kind, name
            if name not in parts: raise LayoutError(f'unknown composition component {name!r}')
            if key in active: raise LayoutError(f'cyclic layout dependency at {name!r}')
            active.add(key)
            try: return action(parts[name])
            finally: active.remove(key)

        def expressions(value):
            if isinstance(value, LayoutValue): return True
            if isinstance(value, dict): return any(expressions(v) for v in value.values())
            if isinstance(value, (list,tuple)): return any(expressions(v) for v in value)
            return False

        def build(name):
            if name not in built:
                def perform(part):
                    item = part.item
                    if isinstance(item, ComponentSpec) and expressions((item.args,item.kwargs)):
                        item = ComponentSpec(item.factory, evaluate(item.args), evaluate(item.kwargs), item.responsive)
                    w = None if part.width is None else length(evaluate(part.width), 'child width')*self.unit
                    h = None if part.height is None else length(evaluate(part.height), 'child height')*self.unit
                    return context.build(item, w, h).copy()
                built[name] = guarded('measure', name, perform)
            return built[name]

        def place(name):
            if name not in placed:
                def perform(part):
                    node = build(name)
                    x, y = float(evaluate(part.x))*self.unit, float(evaluate(part.y))*self.unit
                    if not math.isfinite(x+y): raise LayoutError('component coordinates must be finite')
                    if part.anchor == 'area-nw':
                        area = plot_area(node)
                        if area is None: raise LayoutError(f'{name!r} has no plot area')
                        x, y = x-area.x0, y-area.y0
                    elif part.anchor is not None:
                        point = placed_anchor(node, part.anchor)
                        x, y = x-point.x, y-point.y
                    return Diagram(children=(node,), transform=Affine.translation(x,y),
                                   name=name, kind='composition-part').carry_notes(node)
                placed[name] = guarded('position', name, perform)
            return placed[name]

        for value, minimum, message in self._constraints:
            actual, floor = float(evaluate(value)), float(evaluate(minimum))
            if not math.isfinite(actual) or not math.isfinite(floor): raise LayoutError('layout constraints must be finite')
            if actual < floor-1e-6: raise LayoutError(message)
        content = Diagram(children=tuple(place(p.name) for p in self._parts), kind='composition-content')
        if content.bbox is None: raise LayoutError('cannot render an empty composition')
        def endpoint(value):
            if not isinstance(value, str): raise TypeError('endpoints must be name or name:port strings')
            name, sep, anchor = value.partition(':')
            place(name)
            # Keep the original child handle, so registered anchors resolve in
            # the complete hierarchy rather than on a synthetic wrapper.
            return built[name].at(anchor) if sep else built[name]
        if self._links:
            builder = Figure(theme=context.theme)
            from ..core import Vec2, AnchorRef
            def waypoint(point):
                if isinstance(point, AnchorRef): return point
                if isinstance(point, Vec2): return point*self.unit
                if len(point)==3 and isinstance(point[0],AnchorRef):
                    return point[0],point[1]*self.unit,point[2]*self.unit
                return tuple(v*self.unit for v in point)
            for a,b,options in self._links:
                options=evaluate(options)
                if 'waypoints' in options: options['waypoints']=tuple(waypoint(p) for p in options['waypoints'])
                builder.link(endpoint(a), endpoint(b), **options)
            content = Diagram(children=(content, route_all(builder._links, resolve(content))), kind='composition-content')
        if self._annotations:
            from ..draw.annotate import annotate
            for target, text, options in self._annotations:
                content = annotate(endpoint(target), text, within=content, **evaluate(options))
            from ..layout.labels import place_labels
            content = place_labels(content)
        if self.fit_top: content = content.translated(0, -min(0, content.bbox.y0))
        return Diagram(children=(content,), kind='composition', envelope_override=
                       Envelope.from_rect(Rect(0,0,page['width']*self.unit,page['height']*self.unit)))


def composition(width, height, *, unit=1, fit_top=False):
    """Create a measured composition; see Composition for coordinate semantics."""
    return Composition(width, height, unit, fit_top)
