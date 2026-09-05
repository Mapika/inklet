"""Versioned scientific data, shared scales, units and source records."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
from types import MappingProxyType

from ..core import DiagramError


@dataclass(frozen=True)
class Source:
    """Data origin and construction method carried into an export manifest.

    `method` distinguishes measured, digitized, simulated and illustrative data.
    `path` is optional; when present its SHA-256 is captured on construction.
    """
    citation: str
    method: str = 'measured'
    path: str | None = None
    sha256: str | None = field(default=None, init=False)

    def __post_init__(self):
        if self.method not in ('measured', 'digitized', 'simulated', 'illustrative'):
            raise ValueError('source method must be measured, digitized, simulated or illustrative')
        if self.path is not None:
            path = Path(self.path).resolve()
            object.__setattr__(self, 'path', str(path))
            object.__setattr__(self, 'sha256', hashlib.sha256(path.read_bytes()).hexdigest())


class Dataset:
    """An equal-length column table with explicit updates and a revision number.

    Values are snapshotted as tuples. `update()` validates the complete table
    before changing it, so failed edits cannot leave columns out of alignment.
    """
    def __init__(self, columns, *, units=None, source: Source | None = None, name='data'):
        self.name = str(name)
        self.source = source
        self.units = MappingProxyType(dict(units or {}))
        self._columns = self._validate(columns)
        if set(self.units).difference(self._columns):
            raise DiagramError('units name unknown data columns')
        self.revision = 0

    @staticmethod
    def _validate(columns):
        def snapshot(value):
            if isinstance(value,(tuple,list)): return tuple(snapshot(v) for v in value)
            if isinstance(value,dict): return MappingProxyType({k:snapshot(v) for k,v in value.items()})
            return value
        if any(not isinstance(k,str) for k in columns):
            raise DiagramError('dataset column names must be strings')
        values = {k: tuple(snapshot(v) for v in column) for k,column in columns.items()}
        if not values or len({len(v) for v in values.values()}) != 1:
            raise DiagramError('dataset needs columns of equal length')
        return values

    @property
    def columns(self):
        return MappingProxyType(self._columns)

    @property
    def dependency_key(self):
        return (id(self), self.revision)

    def update(self, **columns):
        unknown = set(columns).difference(self._columns)
        if unknown:
            raise DiagramError(f'unknown columns: {unknown!r}')
        new = self._validate({**self._columns, **columns})
        self._columns = new
        self.revision += 1
        return self

    def column(self, name):
        if name not in self._columns:
            raise KeyError(name)
        return DataRef(self, (name,))

    def points(self, x, y):
        self.column(x); self.column(y)
        return DataRef(self, (x, y))


@dataclass(frozen=True)
class DataRef:
    table: Dataset
    names: tuple

    @property
    def dependency_key(self):
        return (self.table.dependency_key, self.names)

    def evaluate(self):
        columns = [self.table.columns[name] for name in self.names]
        return columns[0] if len(columns) == 1 else tuple(zip(*columns))

    @property
    def unit(self):
        if len(self.names) != 1:
            raise DiagramError('a points reference has separate x and y units')
        return self.table.units.get(self.names[0], '')


def values(data):
    return data.evaluate() if isinstance(data, DataRef) else tuple(data)


@dataclass(frozen=True)
class SharedScale:
    """One live numeric domain computed from all supplied column references."""
    columns: tuple
    padding: float = .05
    include_zero: bool = False
    kind: str = 'linear'

    def __post_init__(self):
        if not self.columns or any(not isinstance(c, DataRef) or len(c.names) != 1 for c in self.columns):
            raise DiagramError('shared_scale needs one or more dataset columns')
        if len({c.unit for c in self.columns}) != 1:
            raise DiagramError('shared scales require matching units; convert the data explicitly')
        if self.kind not in ('linear', 'log'):
            raise ValueError('shared scale kind must be linear or log')
        if not math.isfinite(self.padding) or self.padding < 0:
            raise ValueError('scale padding must be finite and non-negative')
        if self.kind == 'log' and self.include_zero:
            raise ValueError('log scales cannot include zero')

    @property
    def dependency_key(self):
        return (tuple(c.dependency_key for c in self.columns), self.padding, self.include_zero, self.kind)

    def evaluate(self):
        from ..plot import linear, log
        numbers = [float(v) for c in self.columns for v in c.evaluate()]
        if not numbers or not all(math.isfinite(v) for v in numbers):
            raise DiagramError('shared scale data must be non-empty and finite')
        lo, hi = min(numbers), max(numbers)
        if self.kind == 'log':
            if lo <= 0:
                raise DiagramError('log scale data must be positive')
            a, b = math.log(lo), math.log(hi)
            extra = (b-a or 1)*self.padding
            return log((math.exp(a-extra), math.exp(b+extra) if b != a or extra else hi*10))
        if self.include_zero:
            lo, hi = min(lo, 0), max(hi, 0)
        span = hi-lo or abs(lo) or 1
        if hi == lo:
            hi = lo+span
        return linear((lo-span*self.padding, hi+span*self.padding))


def shared_scale(*columns, padding=.05, include_zero=False, kind='linear'):
    """Share a live numeric domain across plots, rejecting incompatible units."""
    return SharedScale(tuple(columns), padding, include_zero, kind)


@dataclass(frozen=True)
class Series:
    """Shared name, colour, values and optional absolute uncertainty bounds."""
    name: str
    x: object
    y: object
    color: str
    lower: object = None
    upper: object = None

    def __post_init__(self):
        for name in ('x', 'y', 'lower', 'upper'):
            data = getattr(self, name)
            if data is not None and not isinstance(data, DataRef):
                object.__setattr__(self, name, tuple(data))
        if (self.lower is None) != (self.upper is None):
            raise DiagramError('series uncertainty needs both lower and upper bounds')

    @property
    def dependency_key(self):
        return tuple(v.dependency_key if isinstance(v, DataRef) else v
                     for v in (self.name, self.x, self.y, self.color, self.lower, self.upper))

    def draw(self, panel, *, kind='line', uncertainty=True, **style):
        x, y = values(self.x), values(self.y)
        if len(x) != len(y) or not x:
            raise DiagramError('series needs non-empty, equal-length x and y values')
        if uncertainty and self.lower is not None:
            lo, hi = values(self.lower), values(self.upper)
            if len(lo) != len(x) or len(hi) != len(x) or any(a > b for a,b in zip(lo,hi)):
                raise DiagramError('series uncertainty bounds must match the data and satisfy lower <= upper')
            panel.band(x, lo, hi, color=self.color, name=self.name)
        if kind == 'line':
            panel.line(tuple(zip(x,y)), name=self.name, stroke=self.color, **style)
        else:
            panel.scatter(tuple(zip(x,y)), name=self.name, color=self.color, **style)


def dataset(columns, *, units=None, source=None, name='data'):
    """Create a versioned Dataset with units and an optional source record."""
    return Dataset(columns, units=units, source=source, name=name)


@dataclass(frozen=True)
class DerivedData:
    """A deterministic transformation of explicit live inputs.

    Use `derive()` to construct one. Pass every changing input explicitly;
    changes hidden in a closure cannot invalidate a compiled document.
    """
    factory: object
    inputs: tuple

    @property
    def dependency_key(self):
        from .spec import fingerprint
        return (self.factory, fingerprint(self.inputs))

    def evaluate(self):
        from .spec import freeze
        def evaluate(value):
            if hasattr(value, 'evaluate'):
                return value.evaluate()
            if isinstance(value, tuple):
                return tuple(evaluate(v) for v in value)
            if isinstance(value, dict):
                return {k: evaluate(v) for k, v in value.items()}
            return value
        return freeze(self.factory(*(evaluate(v) for v in self.inputs)))


def derive(factory, *inputs):
    """Derive live values, such as filtered rows or stacked series, from inputs."""
    from .spec import freeze
    if not callable(factory):
        raise TypeError('derive needs a callable transformation')
    return DerivedData(factory, freeze(inputs))


@dataclass(eq=False)
class CategoryEncoding:
    """A live selection of a CategorySet shared by marks, axes and legends."""
    definition: object
    selected: tuple | None = None

    def __post_init__(self):
        from ..plot.categories import CategorySet
        if not isinstance(self.definition, CategorySet):
            raise TypeError('CategoryEncoding needs an inklet.categories() definition')
        if self.selected is not None:
            self.select(self.selected)

    def select(self, keys):
        chosen = self.definition.subset(keys)
        self.selected = tuple(chosen)
        return self

    @property
    def dependency_key(self):
        return (repr(self.definition), self.selected)

    def evaluate(self):
        return self.definition if self.selected is None else self.definition.subset(self.selected)

    def scale(self, *, reverse=False, gap=1., padding=.1, outer=None):
        return CategoryScale(self, reverse, gap, padding, outer)


@dataclass(frozen=True)
class CategoryScale:
    encoding: CategoryEncoding
    reverse: bool = False
    gap: float = 1.
    padding: float = .1
    outer: float | None = None

    @property
    def dependency_key(self):
        return (self.encoding.dependency_key,self.reverse,self.gap,self.padding,self.outer)

    def evaluate(self):
        return self.encoding.evaluate().scale(reverse=self.reverse,gap=self.gap,
                                              padding=self.padding,outer=self.outer)


@dataclass(frozen=True)
class FileRef:
    """An explicit file dependency for component factories such as `asset`."""
    path: object

    def __post_init__(self):
        object.__setattr__(self,'path',Path(self.path).resolve())
        if not self.path.is_file(): raise FileNotFoundError(self.path)

    @property
    def dependency_key(self):
        return (str(self.path),hashlib.sha256(self.path.read_bytes()).hexdigest())

    def evaluate(self):
        return self.path
