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


def _scale(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError('component scale must be a finite positive number')
    return float(value)


@dataclass(frozen=True)
class _Slot(BuildSpec):
    name: str

    def signature(self, trail=()): return ('composition-slot', self.name)

    def render(self, context, width=None, height=None):
        raise LayoutError(f'unbound composition slot {self.name!r}; use instantiate()')


def _copy_recipe(value, memo):
    """Copy supported authoring definitions, keeping external dependencies live."""
    from copy import copy
    from .spec import PlotSpec
    from .module import ModuleSpec
    if isinstance(value, (Composition, PlotSpec, ComponentSpec, ModuleSpec)):
        if id(value) not in memo:
            result = copy(value)
            memo[id(value)] = result
            result.__dict__ = {k:_copy_recipe(v, memo) for k,v in vars(value).items()}
        return memo[id(value)]
    if isinstance(value, (_Part, LayoutValue)):
        return type(value)(**{k:_copy_recipe(v, memo) for k,v in vars(value).items()})
    if isinstance(value, dict): return {k:_copy_recipe(v, memo) for k,v in value.items()}
    if isinstance(value, list): return [_copy_recipe(v, memo) for v in value]
    if isinstance(value, tuple): return tuple(_copy_recipe(v, memo) for v in value)
    return freeze(value)


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
    scale: float = 1


@dataclass(eq=False)
class Composition(BuildSpec):
    """A figure assembled from named children and measured expressions.

    Coordinates and expressions use `unit` millimetres (default 1). Plot width
    and height describe data regions. Other children retain their authored size
    unless explicit dimensions are provided. `anchor=None` preserves the local
    coordinate frame; `nw`, `center`, registered ports and `area-nw` align a
    measured point to (x, y). Dimension fitting never scales text or strokes. Explicit scale uniformly
    scales the complete child artwork, including typography and strokes.
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
    _ports: dict = field(default_factory=dict, repr=False)

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

    def add(self, name, item, *, x=0, y=0, anchor=None, width=None, height=None, scale=1):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
            raise ValueError('component names start with a letter and contain letters, digits, underscores or hyphens')
        if any(part.name == name for part in self._parts): raise LayoutError(f'duplicate component {name!r}')
        self._parts.append(_Part(name, item, x, y, anchor, width, height, _scale(scale)))
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

    def slot(self, name, **placement):
        """Declare a required content input with the same placement options as add()."""
        self.add(name, _Slot(name), **placement)
        return self

    def copy(self):
        """Copy nested compositions, plots, modules and component instructions.

        Literal containers and arrays are independent. Data, scales, Series,
        static Diagrams, factories and other external BuildSpecs remain shared.
        """
        return _copy_recipe(self, {})

    def instantiate(self, **items):
        """Create an independent recipe, filling required slots and replacing defaults.

        Keys name direct children. Every direct slot is required; unknown keys
        fail before copying. Supplied supported recipes are copied as well.
        Instantiate nested templates separately before supplying them as inputs.
        """
        names = {p.name for p in self._parts}
        unknown = items.keys() - names
        missing = {p.name for p in self._parts if isinstance(p.item, _Slot)} - items.keys()
        if unknown: raise LayoutError(f'unknown composition inputs: {", ".join(sorted(unknown))}')
        if missing: raise LayoutError(f'missing composition inputs: {", ".join(sorted(missing))}')
        memo = {}
        result = _copy_recipe(self, memo)
        for name, item in items.items(): result.replace(name, _copy_recipe(item, memo))
        return result

    def configure(self, *, width=None, height=None, unit=None, fit_top=None):
        """Atomically update authored page dimensions or coordinate units."""
        updates = {name:length(value, f'composition {name}') for name,value in
                   (('width',width),('height',height),('unit',unit)) if value is not None}
        if fit_top is not None: updates['fit_top'] = bool(fit_top)
        self.__dict__.update(updates)
        return self

    def place(self, name, **placement):
        """Edit a child's placement without replacing its content or named links.

        Accepts x, y, anchor, width, height and uniform scale as in add(). Expressions and
        resulting geometry are validated during compilation.
        """
        from dataclasses import replace
        unknown = placement.keys() - {'x','y','anchor','width','height','scale'}
        if unknown: raise TypeError(f'unknown placement options: {", ".join(sorted(unknown))}')
        if 'scale' in placement: placement['scale'] = _scale(placement['scale'])
        for index,part in enumerate(self._parts):
            if part.name == name:
                self._parts[index] = replace(part, **freeze(placement))
                return self
        raise KeyError(name)

    def layout_overrides(self, reference):
        """Capture changed layout and compatible named labels against a reference.

        Return JSON-compatible, versioned decisions keyed by named child paths.
        Other content, styles, data, links and constraints remain in Python.
        """
        from .layout_overrides import capture
        return capture(self, reference)

    def with_layout_overrides(self, value, *, missing='error'):
        """Return an independent edited recipe and a reconciliation report.

        Removed targets or measured references raise by default. missing='drop'
        explicitly drops incompatible target entries and reports their paths.
        Geometry, anchor availability and layout cycles are checked at compile.
        """
        from .layout_overrides import apply
        return apply(self, value, missing=missing)

    def port(self, name, target):
        """Expose a child's name:anchor as a reusable composition attachment point."""
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
            raise ValueError('port names start with a letter and contain letters, digits, underscores or hyphens')
        if not isinstance(target,str) or not target or target.count(':') > 1:
            raise ValueError('port targets must be name or name:anchor strings')
        child,sep,anchor = target.partition(':')
        if child not in {p.name for p in self._parts} or (sep and not anchor):
            raise LayoutError(f'unknown composition port target {target!r}')
        self._ports[name] = target
        return self

    def constrain(self, value, *, minimum=0, message='composition needs more space'):
        """Require an expression to meet a minimum; fail before drawing."""
        self._constraints.append((value, minimum, message))
        return self

    def link(self, source, target, **options):
        """Route a branch or return between named children (`name:port`)."""
        self._links.append((source, target, freeze(options)))
        return self

    def annotate(self, target, text, **options):
        """Place a measured callout; a unique name enables saved label editing."""
        name = options.get('name')
        if name is not None:
            if not isinstance(name,str) or not name: raise ValueError('annotation name must be a nonempty string')
            if any(opts.get('name')==name for _,_,opts in self._annotations):
                raise LayoutError(f'duplicate annotation name {name!r}')
        self._annotations.append((target, text, freeze(options)))
        return self

    def signature(self, trail=()):
        return ('composition', self.width, self.height, self.unit, self.fit_top,
                tuple(fingerprint(vars(p), trail) for p in self._parts),
                fingerprint((self._constraints, self._links, self._annotations, self.bindings, self._ports), trail))

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
                    node = context.build(item, w, h).copy()
                    factor = _scale(part.scale)
                    if factor != 1:
                        scaled = node.scaled(factor)
                        # Keep registered ports directly available to measured
                        # placement; their coordinates precede the new scale.
                        for key in node.anchors: scaled.anchors[key] = placed_anchor(node,key)
                        node = scaled
                    return node
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
        shift = -min(0, content.bbox.y0) if self.fit_top else 0
        if shift: content = content.translated(0, shift)
        result = Diagram(children=(content,), kind='composition', envelope_override=
                       Envelope.from_rect(Rect(0,0,page['width']*self.unit,page['height']*self.unit)))
        from ..core import Vec2
        for name,target in self._ports.items():
            child,sep,anchor = target.partition(':')
            wrapper = place(child)
            point = wrapper.transform.apply(placed_anchor(build(child), anchor if sep else 'center'))
            result.anchor(name, point + Vec2(0,shift))
        return result


def composition(width, height, *, unit=1, fit_top=False):
    """Create a measured composition; see Composition for coordinate semantics."""
    return Composition(width, height, unit, fit_top)
