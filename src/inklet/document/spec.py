"""Deferred authoring objects evaluated by the document compiler."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
import math
from collections.abc import Mapping

from ..core import Diagram, DiagramError, mm


def length(value, name, *, zero=False):
    value = mm(value)
    if not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f'{name} must be finite and {"non-negative" if zero else "positive"}')
    return value


@contextmanager
def themed(theme):
    # Context-local themes also make concurrent document compilation independent.
    import inklet
    token = inklet._theme_context.set(theme)
    try:
        yield
    finally:
        inklet._theme_context.reset(token)


def freeze(value):
    """Snapshot ordinary containers; retain explicit live dependencies."""
    if isinstance(value, dict):
        return {k: freeze(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def fingerprint(value, trail=()):
    if isinstance(value, BuildSpec):
        if id(value) in trail:
            raise DiagramError('cyclic document dependency')
        return value.signature(trail + (id(value),))
    if hasattr(value, 'dependency_key'):
        return value.dependency_key
    if isinstance(value, Diagram):
        return ('diagram', id(value))
    if hasattr(value, 'legend_entries'):
        return repr(value)
    if isinstance(value, Mapping):
        return tuple((fingerprint(k, trail), fingerprint(v, trail)) for k, v in value.items())
    if isinstance(value, (tuple, list)):
        return tuple(fingerprint(v, trail) for v in value)
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def materialize(value, context):
    if isinstance(value, BuildSpec):
        return context.build(value)
    if hasattr(value, 'evaluate'):
        return value.evaluate()
    # CategorySet is a Mapping with behaviour; preserve it.
    if isinstance(value, dict):
        return {k: materialize(v, context) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(materialize(v, context) for v in value)
    return value


class BuildSpec:
    """Base protocol for versioned, deferred diagram definitions."""
    def signature(self, trail=()):
        raise NotImplementedError

    def render(self, context, width=None, height=None):
        raise NotImplementedError


# Marks first, then axes and outside furniture. Each phase preserves call order.
_PHASE = {'axis': 1, 'axes': 1, 'legend': 2, 'colorbar': 2,
          'group_labels': 3, 'inset': 3, 'bracket': 4, 'annotate': 5, 'title': 6}


@dataclass(eq=False)
class PlotSpec(BuildSpec):
    """A live plot recipe. Construct with `plot_spec()`.

    Panel drawing methods record instructions instead of drawing immediately.
    Axes, keys and insets are resolved after marks regardless of declaration
    order. Use `replace()` to revise a named instruction and `configure()` to
    change scales or default dimensions. `key=` belongs to the recipe, not paint.
    """
    width: float = 40
    height: float = 30
    options: dict = field(default_factory=dict)
    _steps: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.width = length(self.width, 'plot width')
        self.height = length(self.height, 'plot height')
        self.options = freeze(self.options)

    def __getattr__(self, name):
        from ..plot.panel import Panel
        forbidden = {'build', 'twin_x', 'twin_y', 'point', 'coord', 'invert'}
        method = getattr(Panel, name, None)
        if name.startswith('_') or name in forbidden or not callable(method):
            raise AttributeError(name)
        def record(*args, key=None, **kwargs):
            inspect.signature(method).bind(None, *args, **kwargs)
            return self._record(name, args, kwargs, key)
        return record

    def _record(self, name, args, kwargs, key):
        if key is not None and any(step[0] == key for step in self._steps):
            raise DiagramError(f'duplicate plot instruction key {key!r}')
        self._steps.append((key, name, freeze(args), freeze(kwargs)))
        return self

    def replace(self, key, *args, **kwargs):
        """Replace arguments of an instruction recorded with `key=...`."""
        for i, (found, method, _, _) in enumerate(self._steps):
            if found == key and key is not None:
                self._steps[i] = (key, method, freeze(args), freeze(kwargs))
                return self
        raise KeyError(key)

    def remove(self, key):
        for i, step in enumerate(self._steps):
            if key is not None and step[0] == key:
                del self._steps[i]
                return self
        raise KeyError(key)

    def configure(self, *, width=None, height=None, **options):
        if width is not None:
            self.width = length(width, 'plot width')
        if height is not None:
            self.height = length(height, 'plot height')
        self.options.update(freeze(options))
        return self

    def annotate(self, x, y, text, *, avoid_marks=True, key=None, **options):
        """Place a callout after marks, insets and brackets have been measured.

        Existing marks and furniture are considered by default. Set
        avoid_marks=False for the legacy placement policy or supply avoid=.
        Crowded layouts still report remaining conflicts in diagnostics.
        """
        return self._record('annotate', (x,y,text), dict(_avoid_marks=avoid_marks, **options), key)

    def group_labels(self, categories, *, key=None, **kwargs):
        return self._record('group_labels', (categories,), kwargs, key)

    def series(self, series, *, kind='line', uncertainty=True, key=None, **style):
        """Draw a shared Series definition, including its name and uncertainty."""
        if kind not in ('line', 'scatter'):
            raise ValueError('series kind must be line or scatter')
        return self._record('series', (series,), dict(kind=kind, uncertainty=uncertainty, **style), key)

    def twin_y(self, scale=None, **options):
        """Record a second y-axis; returned instructions share the parent area."""
        child = PlotSpec()
        self._record('twin_y', (child,), dict(scale=scale, **options), None)
        return child

    def twin_x(self, scale=None, **options):
        """Record a second x-axis; returned instructions share the parent area."""
        child = PlotSpec()
        self._record('twin_x', (child,), dict(scale=scale, **options), None)
        return child

    def signature(self, trail=()):
        return ('plot', self.width, self.height, fingerprint(self.options, trail),
                fingerprint(self._steps, trail))

    def render(self, context, width=None, height=None):
        from ..plot import panel
        p = panel(self.width if width is None else width,
                  self.height if height is None else height,
                  **materialize(self.options, context))
        self._replay(p, context)
        return p.build()

    def _replay(self, panel, context):
        for _, method, args, kwargs in sorted(self._steps, key=lambda s: _PHASE.get(s[1], 0)):
            if method in ('twin_x', 'twin_y'):
                twin = getattr(panel, method)(**materialize(kwargs, context))
                args[0]._replay(twin, context)
                continue
            args, kwargs = materialize(args, context), materialize(kwargs, context)
            if method == 'annotate':
                if kwargs.pop('_avoid_marks', True):
                    # build() resolves deferred external insets. Its children
                    # retain the data-coordinate frame used by Panel.annotate.
                    drawn = panel.build()
                    backgrounds={node.id for node in panel._under}
                    kwargs['avoid'] = (*kwargs.get('avoid', ()),
                                       *(node for node in drawn.children if node.id not in backgrounds))
                panel.annotate(*args, **kwargs)
            elif method == 'group_labels':
                args[0].group_labels(panel, **kwargs)
            elif method == 'series':
                args[0].draw(panel, **kwargs)
            else:
                getattr(panel, method)(*args, **kwargs)


def plot_spec(width=40, height=30, **options):
    """Defer Panel drawing instructions until a document is compiled."""
    return PlotSpec(width, height, options)


@dataclass(eq=False)
class ComponentSpec(BuildSpec):
    """A diagram factory with explicit, versioned arguments and dependencies."""
    factory: object
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    responsive: bool = False

    def configure(self, *args, **kwargs):
        if args:
            self.args = freeze(args)
        self.kwargs.update(freeze(kwargs))
        return self

    def signature(self, trail=()):
        return ('component', self.factory, fingerprint(self.args, trail),
                fingerprint(self.kwargs, trail), self.responsive)

    def render(self, context, width=None, height=None):
        kwargs = materialize(self.kwargs, context)
        if self.responsive:
            kwargs.update(width=width, height=height)
        node = self.factory(*materialize(self.args, context), **kwargs)
        if not isinstance(node, Diagram):
            raise DiagramError('component factory must return a Diagram')
        return node


def component(factory, *args, responsive=False, **kwargs):
    """Rebuild a component under its document theme when its arguments change.

    With `responsive=True`, the factory also receives its cell's width/height.
    Factories must be deterministic; pass changing inputs as explicit arguments.
    """
    if not callable(factory):
        raise TypeError('component needs a callable diagram factory')
    return ComponentSpec(factory, freeze(args), freeze(kwargs), responsive)
