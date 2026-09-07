"""Immutable keyed tables and portable selection states; experimental, schema 0.1.

This prototype accepts JSON scalar columns and explicit string row IDs. It does
not infer identity from position or provide a browser execution engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from collections.abc import Mapping

SCHEMA = 'inklet.selection/0.1'


def _name(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{label} must be a nonempty string')
    return value


def _ids(values, label):
    if isinstance(values, (str, bytes)):
        raise ValueError(f'{label} must be a sequence of row IDs')
    result = tuple(_name(v, 'row ID') for v in values)
    if len(set(result)) != len(result):
        raise ValueError(f'{label} contains duplicate row IDs')
    return tuple(sorted(result))


@dataclass(frozen=True, init=False)
class KeyedTable:
    """Snapshot scalar columns with a stable table name and unique string key.

    Replacing or reordering data produces a new digest. Use explicit state
    rebasing to preserve identities across that change. No optional dependencies.
    """
    name: str
    key: str
    columns: Mapping
    row_ids: tuple[str, ...]
    digest: str

    def __init__(self, name, columns, *, key='id'):
        _name(name, 'table name'); _name(key, 'key column')
        if not isinstance(columns, Mapping) or key not in columns:
            raise ValueError('columns must contain the key column')
        copied = {}
        for column, values in columns.items():
            _name(column, 'column name')
            if isinstance(values, (str, bytes)):
                raise ValueError('columns must contain sequences, not strings')
            copied[column] = tuple(values)
            for value in copied[column]:
                if type(value) not in (str, int, float, bool, type(None)):
                    raise ValueError('table cells must be JSON scalars')
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('use null for missing data; nonfinite numbers are unsupported')
                if type(value) is int and abs(value) > 2**53 - 1:
                    raise ValueError('integers outside the portable JSON range must be strings')
        if len({len(v) for v in copied.values()}) != 1:
            raise ValueError('columns must have equal lengths')
        _ids(copied[key], 'key column')
        payload = json.dumps(dict(name=name, key=key, columns=copied),
                             sort_keys=True, separators=(',', ':'), allow_nan=False)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'key', key)
        object.__setattr__(self, 'columns', MappingProxyType(copied))
        object.__setattr__(self, 'row_ids', copied[key])
        object.__setattr__(self, 'digest', hashlib.sha256(payload.encode()).hexdigest())

    def subset(self, ids):
        """Return columns in source order, rejecting IDs absent from this table."""
        requested = set(_ids(ids, 'subset'))
        missing = requested.difference(self.row_ids)
        if missing:
            raise ValueError(f'unknown row IDs: {sorted(missing)!r}')
        indices = [n for n, key in enumerate(self.row_ids) if key in requested]
        return {name: tuple(values[n] for n in indices) for name, values in self.columns.items()}


@dataclass(frozen=True)
class SelectionState:
    """A selection and optional visibility filter tied to exact table contents.

    ``visible_ids=None`` means all rows; an empty tuple means no rows. Filtering
    preserves selected hidden rows. Rebinding changed inputs is always explicit.
    """
    table: str
    data_digest: str
    selected_ids: tuple[str, ...] = ()
    visible_ids: tuple[str, ...] | None = None

    def __post_init__(self):
        _name(self.table, 'table name')
        if (not isinstance(self.data_digest, str) or len(self.data_digest) != 64
                or any(c not in '0123456789abcdef' for c in self.data_digest)):
            raise ValueError('data digest must be a SHA-256 hex string')
        object.__setattr__(self, 'selected_ids', _ids(self.selected_ids, 'selection'))
        if self.visible_ids is not None:
            object.__setattr__(self, 'visible_ids', _ids(self.visible_ids, 'visibility filter'))

    @classmethod
    def for_table(cls, table, *, selected=(), visible=None):
        state = cls(table.name, table.digest, selected, visible)
        state.validate(table)
        return state

    def validate(self, table):
        if self.table != table.name:
            raise ValueError('state belongs to a different table')
        if self.data_digest != table.digest:
            raise ValueError('state data changed; explicitly rebase before applying')
        requested = set(self.selected_ids) | set(self.visible_ids or ())
        missing = requested.difference(table.row_ids)
        if missing:
            raise ValueError(f'unknown row IDs: {sorted(missing)!r}')

    def visible(self, table):
        self.validate(table)
        return table.subset(table.row_ids if self.visible_ids is None else self.visible_ids)

    def rebase(self, table, *, missing='error'):
        """Bind to revised contents; report removed IDs when explicitly dropping.

        Newly added rows enter an all-rows filter but not an explicit ID filter.
        Surviving selected IDs remain selected even when currently hidden.
        """
        if missing not in ('error', 'drop'):
            raise ValueError('missing must be error or drop')
        if self.table != table.name:
            raise ValueError('state belongs to a different table')
        present = set(table.row_ids)
        removed_selection = tuple(k for k in self.selected_ids if k not in present)
        removed_filter = tuple(k for k in self.visible_ids or () if k not in present)
        if missing == 'error' and (removed_selection or removed_filter):
            raise ValueError('revised table removed selected or filtered row IDs')
        state = SelectionState.for_table(table,
            selected=tuple(k for k in self.selected_ids if k in present),
            visible=None if self.visible_ids is None else tuple(k for k in self.visible_ids if k in present))
        return RebasedSelection(state, removed_selection, removed_filter)

    def to_json(self):
        return json.dumps(dict(schema=SCHEMA, table=self.table, data_digest=self.data_digest,
                               selected_ids=self.selected_ids, visible_ids=self.visible_ids),
                          sort_keys=True, indent=2, allow_nan=False) + '\n'

    @classmethod
    def from_json(cls, payload):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError(f'duplicate state field: {key}')
                result[key] = value
            return result
        value = json.loads(payload, object_pairs_hook=unique)
        fields = {'schema', 'table', 'data_digest', 'selected_ids', 'visible_ids'}
        if not isinstance(value, dict) or set(value) != fields or value['schema'] != SCHEMA:
            raise ValueError('unsupported selection state schema or fields')
        if not isinstance(value['selected_ids'], list) or not (
                value['visible_ids'] is None or isinstance(value['visible_ids'], list)):
            raise ValueError('state IDs must be JSON arrays or a null visibility filter')
        return cls(value['table'], value['data_digest'], value['selected_ids'], value['visible_ids'])


@dataclass(frozen=True)
class RebasedSelection:
    state: SelectionState
    removed_selected: tuple[str, ...]
    removed_visible: tuple[str, ...]
