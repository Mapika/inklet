"""Shared category order, colours, labels and groups for related plots."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..core import DiagramError, Vec2, mm
from .scale import GroupedBand


@dataclass(frozen=True)
class CategorySet(Mapping):
    """An immutable colour mapping. Use `categories()` to construct one.

    `subset()` preserves the original order and colours. `scale()` supplies
    axis labels and group spacing; `legend_entries` supplies matching swatches.
    Passing this mapping as `bars(bar_colors=...)` records category legend keys.
    """
    _entries: tuple
    _groups: tuple = ()

    def __iter__(self):
        return (key for key, _, _ in self._entries)

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, key):
        for item, color, _ in self._entries:
            if item == key:
                return color
        raise KeyError(key)

    @property
    def labels(self):
        return {key: label for key, _, label in self._entries}

    @property
    def groups(self):
        return dict(self._groups)

    @property
    def legend_entries(self):
        return tuple((label, color) for _, color, label in self._entries)

    def subset(self, keys):
        """Select categories in their original order; reject unknown/empty selections."""
        selected = set(keys)
        unknown = selected.difference(self)
        if unknown:
            raise DiagramError(f'unknown categories: {unknown!r}')
        entries = tuple(entry for entry in self._entries if entry[0] in selected)
        if not entries:
            raise DiagramError('a category subset must not be empty')
        groups = tuple((name, tuple(k for k in items if k in selected))
                       for name, items in self._groups if any(k in selected for k in items))
        return CategorySet(entries, groups)

    def scale(self, range=(0., 1.), *, reverse=False, gap=1., padding=.1, outer=None):
        """A categorical axis; `reverse=True` reads top to bottom on y."""
        rows = [items for _, items in self._groups] if self._groups else [tuple(self)]
        if reverse:
            rows = [tuple(reversed(row)) for row in reversed(rows)]
        keys = tuple(k for row in rows for k in row)
        breaks = tuple(sum(len(row) for row in rows[:i]) for i in builtins_range(1, len(rows)))
        return _CategoryBand(categories=keys, range=tuple(mm(v) for v in range),
                             padding=padding, outer=outer, group_breaks=breaks,
                             gap=gap, labels=tuple(self.labels.items()))

    def group_labels(self, panel, *, side='bottom', pad=None, **style):
        """Add group brackets outside a panel, after its axes have been added.

        Uses the matching category scale on x (top/bottom) or y (left/right).
        Empty groups from a subset are omitted; one-member groups span one slot.
        """
        import inklet
        from ..draw.coords import active_theme
        if side not in ('top', 'bottom', 'left', 'right'):
            raise ValueError('group label side must be top, bottom, left or right')
        scale = panel.x if side in ('top', 'bottom') else panel.y
        if not isinstance(scale, _CategoryBand) or set(scale.categories) != set(self):
            raise DiagramError('group labels need this category set’s scale on the selected axis')
        gap = active_theme().gap('s') if pad is None else mm(pad)
        bounds = inklet.as_drawn(panel.build()).bbox
        at = {'top': bounds.y0-gap, 'bottom': bounds.y1+gap,
              'left': bounds.x0-gap, 'right': bounds.x1+gap}[side]
        direction = {'top':'n', 'bottom':'s', 'left':'w', 'right':'e'}[side]
        for name, keys in self._groups:
            edges = [edge for key in keys for edge in scale.edges(key)]
            lo, hi = min(edges), max(edges)
            a, b = ((Vec2(lo, at), Vec2(hi, at)) if side in ('top', 'bottom')
                    else (Vec2(at, lo), Vec2(at, hi)))
            panel.over(inklet.bracket(a, b, side=direction, text=name, **style), clip=False)
        return panel


@dataclass(frozen=True, slots=True)
class _CategoryBand(GroupedBand):
    labels: tuple = ()

    def tick_labels(self, ticks):
        labels = dict(self.labels)
        return tuple(labels[t] for t in ticks)


# Avoid shadowing the built-in in scale(range=...).
builtins_range = range


def categories(colors: Mapping, *, labels: Mapping | None = None,
               groups: Mapping | None = None) -> CategorySet:
    """Define category colours and order once for scales, bars, keys and groups.

    `colors` is an ordered mapping from category values to colours. Optional
    `labels` maps those values to display names. `groups` maps group names to
    consecutive categories and must partition the complete category order.
    """
    if not isinstance(colors, Mapping) or not colors:
        raise DiagramError('categories needs a non-empty mapping of values to colours')
    labels = {} if labels is None else dict(labels)
    if set(labels).difference(colors):
        raise DiagramError('category labels contain unknown values')
    entries = tuple((key, color, str(labels.get(key, key))) for key, color in colors.items())
    if len({label for _, _, label in entries}) != len(entries):
        raise DiagramError('category display labels must be distinct for unambiguous legend keys')
    rows = () if groups is None else tuple((str(name), tuple(keys)) for name, keys in groups.items())
    if groups is not None and (not rows or any(not keys for _, keys in rows)
                              or tuple(k for _, keys in rows for k in keys) != tuple(colors)):
        raise DiagramError('groups must partition the category order into non-empty consecutive groups')
    return CategorySet(entries, rows)
