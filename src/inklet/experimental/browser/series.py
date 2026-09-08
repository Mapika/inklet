"""Explicit wide-table series: one stable entity ID across all samples."""
from dataclasses import dataclass
from decimal import Decimal

from ..temporal import time_milliseconds, time_value
from .timeaxis import TimeAxis


@dataclass(frozen=True)
class SeriesView:
    """Draw one numeric series per row using explicit (position, column) samples.

    Positions must increase, independently of axis direction. Null values break
    lines; markers retain isolated samples. Picking any sample selects its row.
    No interpolation, aggregation or implicit table reshaping is performed.
    """
    name: str
    samples: tuple[tuple[float | str, str], ...]
    x_domain: tuple[float, float] | TimeAxis
    y_domain: tuple[float, float]
    x_label: str = 'Sample'
    y_label: str = 'Value'
    radius_mm: float = .4
    line_width_mm: float = .3
    color: str = '#78958f'
    max_gap_seconds: float | None = None

    def __post_init__(self):
        # Local import keeps the public API in browser without an import cycle.
        from . import ScatterView, LineView, _finite
        if isinstance(self.y_domain, TimeAxis):
            raise ValueError('series values require a numeric y domain')
        checked = ScatterView(self.name, self.x, self.y, self.x_domain, self.y_domain,
                              self.x_label, self.y_label, self.radius_mm, self.color)
        LineView(self.name, self.x, self.y, self.x_domain, self.y_domain,
                 line_width_mm=self.line_width_mm, color=self.color,
                 max_gap_seconds=self.max_gap_seconds)
        object.__setattr__(self, 'x_domain', checked.x_domain)
        object.__setattr__(self, 'y_domain', checked.y_domain)
        if not isinstance(self.samples, (tuple, list)) or not self.samples:
            raise ValueError('series samples need a nonempty ordered sequence of (position, column) pairs')
        samples = []; positions = []; columns = set()
        for sample in self.samples:
            if not isinstance(sample, (tuple, list)) or len(sample) != 2:
                raise ValueError('each series sample needs a (position, column) pair')
            position, column = sample
            if not isinstance(column, str) or not column or column in columns:
                raise ValueError('series sample columns must be unique nonempty strings')
            columns.add(column)
            if isinstance(self.x_domain, TimeAxis):
                position = time_value(position, self.x_domain.mode)
                if position is None: raise ValueError('series positions must not be null')
                coordinate = time_milliseconds(position, self.x_domain.mode)
            else:
                if not _finite(position): raise ValueError('series positions must be finite numbers')
                coordinate = position
            samples.append((position, column)); positions.append(coordinate)
        if any(a >= b for a, b in zip(positions, positions[1:])):
            raise ValueError('series positions must be strictly increasing')
        object.__setattr__(self, 'samples', tuple(samples))

    @property
    def x(self): return self.x_label or 'Sample'

    @property
    def y(self): return self.y_label or 'Value'

    def validate_table(self, table):
        from . import _finite
        for _, column in self.samples:
            if column not in table.columns: raise ValueError(f'unknown series column: {column}')
            for row, value in enumerate(table.columns[column]):
                if value is not None and not _finite(value):
                    raise ValueError(f'series column {column!r}, row {row}: values must be numeric or null')

    def layer(self, table, bounds, project, indices):
        temporal = isinstance(self.x_domain, TimeAxis)
        positions = [(time_milliseconds(p, self.x_domain.mode) - self.x_domain.milliseconds[0])/1000
                     if temporal else p for p, _ in self.samples]
        gap = Decimal(str(self.max_gap_seconds))*1000 if self.max_gap_seconds is not None else None
        segments = []; markers = []; missing = 0; gaps = 0
        for n in indices:
            key = table.row_ids[n]; previous = None
            for (position, column), x in zip(self.samples, positions):
                y = table.columns[column][n]
                if y is None:
                    missing += 1; previous = None; continue
                point = project(x, y)
                sample = dict(x=position, y=y, column=column)
                if previous is not None:
                    px, pp, ps = previous
                    if gap is not None and abs(round(x*1000)-round(px*1000)) > gap:
                        gaps += 1
                    else:
                        segments.append(dict(kind='line', ids=[key,key], geometry=[*pp,*point],
                                             width=self.line_width_mm, selected_width=self.line_width_mm+.2,
                                             samples=[ps,sample]))
                markers.append(dict(kind='circle', ids=[key], geometry=[*point,self.radius_mm], sample=sample))
                previous = (x,point,sample)
        # Paint markers last so endpoints and isolated measurements stay pickable.
        layer = dict(name=self.name, x=self.x, y=self.y, clip=bounds, color=self.color,
                     marks=segments+markers, radius=self.radius_mm, missing=missing,
                     series=dict(samples=self.samples, identity='one series per source row',
                                 missing='null samples break lines', sample_count=len(self.samples)))
        if temporal: layer['time_axes'] = dict(x=self.x_domain.metadata())
        if gap is not None: layer.update(max_gap_seconds=self.max_gap_seconds, time_gaps=gaps)
        return layer
