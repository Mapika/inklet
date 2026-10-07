"""Fit a plot's axes to the data its recorded marks draw.

`plot_spec()` without `x=`/`y=` used to fall back to a (0, 1) domain, so any
real data drew far outside its plot. This module reads a recipe's materialised
steps and returns the domains its marks need:

* Marks whose geometry *is* their data -- points, x/y sequences, rules -- are
  read directly. Reading them is exact and does not depend on the drawing
  code culling what falls outside a placeholder plot area.
* Everything else (histograms, densities, box plots, bars, areas...) is drawn
  once into a probe panel and the drawn extent is read back through the probe
  scales, so the extent is whatever the drawing code computed and not a second
  implementation of every statistic.

Categorical positions are found first, because a band scale has to exist
before a mark can be drawn against it.
"""
from __future__ import annotations

from collections.abc import Mapping
import inspect
import math
from numbers import Real

from .timescale import is_time_like

#: Steps that never carry data positions.
_FURNITURE = frozenset({
    'axes', 'axis', 'legend', 'title', 'grid', 'guide', 'colorbar', 'size_key',
    'width_key', 'background', 'label_lines', 'label_points', 'break_marks',
    'twin_x', 'twin_y', 'inset', 'group_labels', 'series', 'at_risk',
    'bracket', 'brackets', 'arrow', 'place', 'placed', 'over', 'under', 'draw',
    'outline', 'marks', 'region', 'map',
})

#: Marks drawn from `points`, an iterable of (x, y, ...) rows.
_POINTS = frozenset({
    'line', 'scatter', 'step', 'stem', 'errorbars', 'regression', 'hexbin',
    'hist2d', 'density_scatter', 'kde2d',
})

#: Marks whose first positional argument is a sequence of positions.
_AT = frozenset({'bars', 'lollipop', 'barplot', 'dotplot', 'dumbbell'})

#: Marks drawn from `groups`: a mapping of position to samples, or a list.
_GROUPS = frozenset({'boxplot', 'violin', 'strip', 'swarm', 'boxen', 'sina',
                     'raincloud', 'split_violin'})

#: Marks whose value axis starts at a baseline that should sit on the axis.
_BASELINED = frozenset({'bars', 'hist', 'stackarea', 'lollipop', 'barplot',
                        'stem', 'waterfall', 'streamgraph', 'kde', 'ecdf'})

#: How far each soft end of a fitted domain is pushed out, as a fraction of
#: its span, so markers and line caps do not sit on the axis lines.
PAD = 0.04

#: Rounding a domain out to whole ticks is kept only while it costs less than
#: this fraction of the span; past it the plot would be mostly empty axis.
_NICE_BUDGET = 0.12


#: Probed extents include half a stroke and a marker radius; data that fit the
#: unit domain read back a hair outside it.
_UNIT_SLACK = 0.02


class _Axis:
    """What the marks need along one axis."""

    def __init__(self):
        self.lo = math.inf
        self.hi = -math.inf
        self.hard = set()
        self.categories: list = []
        self.times: list = []

    def add(self, value, hard=False):
        if value is None:
            return
        if isinstance(value, str):
            if value not in self.categories:
                self.categories.append(value)
            return
        if is_time_like(value) and not isinstance(value, Real):
            self.times.append(value)
            return
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(number):
            return
        self.lo = min(self.lo, number)
        self.hi = max(self.hi, number)
        if hard:
            self.hard.add(number)

    def extend(self, values, hard=False):
        for value in _flat(values):
            self.add(value, hard)

    @property
    def numeric(self) -> bool:
        return self.lo <= self.hi

    @property
    def within_unit(self) -> bool:
        """True when the default (0, 1) domain already suits this axis.

        That is: nothing falls outside it, and the data fill at least half of
        it, so a density peaking at 0.03 is not drawn as a flat line.
        """
        if self.categories or self.times:
            return False
        if not self.numeric:
            return True
        return (self.lo >= -_UNIT_SLACK and self.hi <= 1.0 + _UNIT_SLACK
                and self.hi - self.lo >= 0.5)

    def probe_spec(self):
        """The domain a probe panel is drawn against on this axis.

        Marks that sample inside the domain (a density's curve) need one that
        already holds their data, with room for the tails they draw past it.
        """
        if self.categories:
            return list(self.categories)
        if self.numeric:
            span = (self.hi - self.lo) or abs(self.lo) or 1.0
            return (self.lo - span / 2, self.hi + span / 2)
        return (0.0, 1.0)

    def domain(self, *, scale: str = 'linear', nice: bool = True):
        """The fitted domain shorthand for `panel(x=..., y=...)`, or None."""
        if self.categories:
            return list(self.categories)
        if self.times and not self.numeric:
            return (min(self.times), max(self.times))
        if not self.numeric:
            return None
        lo, hi = self.lo, self.hi
        if scale == 'log':
            return _log_domain(lo, hi)
        if lo == hi:
            half = abs(lo) * 0.5 or 1.0
            return (lo - half, hi + half)
        span = hi - lo
        hard_lo, hard_hi = lo in self.hard, hi in self.hard
        padded = (lo if hard_lo else lo - PAD * span,
                  hi if hard_hi else hi + PAD * span)
        if not nice:
            return padded
        return _nice_if_cheap(padded, span, hard_lo, hard_hi, (lo, hi))


def _log_domain(lo, hi):
    if hi <= 0:
        return None
    if lo <= 0:
        lo = hi / 1000
    exponent = (math.log10(hi) - math.log10(lo)) * PAD
    return (lo / 10 ** exponent, hi * 10 ** exponent)


def _nice_if_cheap(domain, span, hard_lo, hard_hi, data):
    from .scale import Linear
    lo, hi = domain
    nice_lo, nice_hi = Linear((lo, hi), (0.0, 1.0)).nice().domain
    # Rounding never carries an axis across zero that the data do not cross:
    # an all-positive quantity should not grow a negative tick.
    if data[0] >= 0 > nice_lo:
        nice_lo = lo
    if data[1] <= 0 < nice_hi:
        nice_hi = hi
    if hard_lo:
        nice_lo = lo
    if hard_hi:
        nice_hi = hi
    budget = _NICE_BUDGET * span
    if lo - nice_lo <= budget:
        lo = nice_lo
    if nice_hi - hi <= budget:
        hi = nice_hi
    return (lo, hi)


def _flat(values):
    if values is None:
        return
    if isinstance(values, (str, bytes)) or is_time_like(values) or isinstance(values, Real):
        yield values
        return
    if isinstance(values, Mapping):
        values = values.values()
    try:
        items = iter(values)
    except TypeError:
        yield values
        return
    for item in items:
        yield from _flat(item)


def _column(points, index):
    out = []
    for row in points:
        try:
            out.append(row[index])
        except (TypeError, IndexError, KeyError):
            continue
    return out


def _bind(method_name, args, kwargs):
    from .panel import Panel
    method = getattr(Panel, method_name, None)
    if method is None:
        return None
    try:
        bound = inspect.signature(method).bind(None, *args, **kwargs)
    except TypeError:
        return None
    bound.apply_defaults()
    return bound.arguments


def _orient(arguments):
    return (arguments or {}).get('orient', 'v') in ('h', 'horizontal')


def _categories(steps, x: _Axis, y: _Axis):
    """Record string positions, which need band scales before any probe."""
    for method, args, kwargs in steps:
        arguments = _bind(method, args, kwargs)
        if arguments is None:
            continue
        horizontal = _orient(arguments)
        position = y if horizontal else x
        if method in _POINTS and 'points' in arguments:
            points = list(arguments['points'])
            for value in _column(points, 0):
                if isinstance(value, str):
                    x.add(value)
            for value in _column(points, 1):
                if isinstance(value, str):
                    y.add(value)
        elif method in _AT and 'at' in arguments:
            for value in arguments['at']:
                if isinstance(value, str):
                    position.add(value)
        elif method in _GROUPS:
            groups, at = arguments.get('groups'), arguments.get('at')
            if at is not None:
                keys = list(at)
            elif isinstance(groups, Mapping):
                keys = list(groups)
            else:
                keys = []
            for value in keys:
                if isinstance(value, str):
                    position.add(value)


def _read_points(method, arguments, x: _Axis, y: _Axis):
    points = list(arguments['points'])
    xs, ys = _column(points, 0), _column(points, 1)
    x.extend(xs)
    if method == 'errorbars':
        _spread(y, ys, arguments.get('yerr'))
        _spread(x, xs, arguments.get('xerr'))
    elif method == 'line' and arguments.get('err') is not None:
        _spread(y, ys, arguments['err'])
    if method == 'stem':
        horizontal = _orient(arguments)
        (x if horizontal else y).add(arguments.get('baseline', 0.0), hard=True)
    y.extend(ys)


def _spread(axis: _Axis, centres, err):
    """Add centre +/- error, for a scalar, per-point or per-point (lo, hi) error."""
    if err is None:
        return
    if isinstance(err, Real):
        errors = [(err, err)] * len(centres)
    else:
        errors = []
        for item in err:
            if isinstance(item, Real):
                errors.append((item, item))
            else:
                try:
                    down, up = item
                except (TypeError, ValueError):
                    errors.append((0.0, 0.0))
                    continue
                errors.append((down, up))
    for centre, (down, up) in zip(centres, errors):
        try:
            axis.add(float(centre) - float(down))
            axis.add(float(centre) + float(up))
        except (TypeError, ValueError):
            continue


def _read_direct(method, arguments, x: _Axis, y: _Axis) -> bool:
    """Read marks whose geometry is their data. False when not one of them."""
    if method in _POINTS and 'points' in arguments:
        _read_points(method, arguments, x, y)
    elif method in ('fill_between', 'band') and 'x' in arguments:
        x.extend(arguments['x'])
        for name in ('y0', 'y1', 'lo', 'hi'):
            if name in arguments:
                y.extend(arguments[name])
    elif method == 'hline':
        y.extend(arguments.get('y'))
    elif method == 'vline':
        x.extend(arguments.get('x'))
    elif method == 'hspan':
        y.extend([arguments.get('y0'), arguments.get('y1')])
    elif method == 'vspan':
        x.extend([arguments.get('x0'), arguments.get('x1')])
    elif method == 'ecdf' and _is_samples(arguments.get('values')):
        # Read, not probed: with `extend` the steps run to the edges of
        # whatever domain they are drawn against, so a probe would measure
        # its own placeholder and the fitted axis would keep widening.
        values = [v for v in arguments['values'] if v is not None]
        x.extend(values)
        y.add(0.0, hard=True)
        y.add(1.0 if arguments.get('normalize', True) else float(len(values)), hard=True)
    elif method in ('text', 'annotate'):
        x.add(arguments.get('x'))
        y.add(arguments.get('y'))
    else:
        return False
    return True


def _probe(method, args, kwargs, x: _Axis, y: _Axis, width, height):
    """Draw one mark into a placeholder panel and read back its data extent."""
    from .panel import panel
    from .scale import Band
    arguments = _bind(method, args, kwargs) or {}
    kwargs = dict(kwargs)
    # A probe never needs pixels; the vector form has the same extent.
    if 'raster' in arguments:
        kwargs['raster'] = False
    try:
        probe = panel(width, height, x=x.probe_spec(), y=y.probe_spec())
        before = [len(probe._under), len(probe._content), len(probe._over)]
        getattr(probe, method)(*args, **kwargs)
    except Exception:
        return
    # A `label_points` or `label_lines` call leaves an empty placeholder in
    # `_over` until the panel is built, and it has no box to read. Labels
    # are kept inside the plot area and never set a domain, so the probe
    # reads the marks alone and leaves the placeholders out.
    held = probe._deferred
    drawn = [node for node in (*probe._under[before[0]:], *probe._content[before[1]:],
                               *probe._over[before[2]:])
             if id(node) not in held]
    if not drawn:
        return
    box = drawn[0].bbox
    for node in drawn[1:]:
        box = box.union(node.bbox)
    horizontal = _orient(arguments)
    baseline = arguments.get('baseline', 0.0) if method in _BASELINED else None
    for axis, scale, lo, hi, is_value in (
            (x, probe.x, box.x0, box.x1, horizontal),
            (y, probe.y, box.y0, box.y1, not horizontal)):
        if isinstance(scale, Band):
            continue
        ends = sorted((scale.invert(lo), scale.invert(hi)))
        for end in ends:
            hard = (is_value and isinstance(baseline, Real)
                    and math.isclose(end, baseline, abs_tol=1e-9 * max(1.0, abs(ends[1] - ends[0]))))
            axis.add(float(baseline) if hard else end, hard=hard)


def measure(steps, width, height):
    """Return what the marks need along `(x, y)`, before padding or rounding.

    `steps` are `(method, args, kwargs)` triples with live data materialised.
    """
    x, y = _Axis(), _Axis()
    steps = [(m, a, k) for m, a, k in steps if m not in _FURNITURE]
    _categories(steps, x, y)
    probes = []
    for method, args, kwargs in steps:
        if method == 'annotate':
            # Recorded as (x, y, text) with recipe-only keywords.
            if len(args) >= 2:
                x.add(args[0])
                y.add(args[1])
            continue
        arguments = _bind(method, args, kwargs)
        if arguments is not None and _read_direct(method, arguments, x, y):
            continue
        if arguments is not None and method in _GROUPS and arguments.get('groups') is not None:
            # Samples lie along the value axis; a density-shaped mark (a
            # violin) samples only inside the domain it is probed against.
            (x if _orient(arguments) else y).extend(_group_samples(arguments['groups']))
        if arguments is not None and _is_samples(arguments.get('values')):
            # A distribution's samples lie along its position axis; reading
            # them first gives its probe a domain to sample in.
            (y if _orient(arguments) else x).extend(arguments['values'])
        probes.append((method, args, kwargs))
    for method, args, kwargs in probes:
        _probe(method, args, kwargs, x, y, width, height)
    return x, y


def _group_samples(groups):
    items = groups.values() if isinstance(groups, Mapping) else groups
    out = []
    for item in items:
        if _is_samples(item):
            out.extend(item)
    return out


def _is_samples(values) -> bool:
    if values is None or isinstance(values, (str, bytes)):
        return False
    if isinstance(values, Mapping):
        return all(_is_samples(v) for v in values.values())
    try:
        return all(isinstance(v, Real) for v in values)
    except TypeError:
        return False


def fit_domains(steps, width, height, *, x_scale='linear', y_scale='linear', nice=True):
    """Return `(x, y)` domain shorthands fitted to a recipe's marks.

    A returned domain is None when no mark said anything about that axis, in
    which case the caller keeps its usual default.
    """
    x, y = measure(steps, width, height)
    return x.domain(scale=x_scale, nice=nice), y.domain(scale=y_scale, nice=nice)
