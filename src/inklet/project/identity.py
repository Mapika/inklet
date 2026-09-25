"""Explicit correspondence between entities and local content IDs."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
from .assets import name
from ..selection import KeyedTable, SelectionState, _ids


@dataclass(frozen=True, init=False)
class EntityMap:
    """An immutable entity registry with source-local, many-to-one bindings.

    IDs are explicit strings, never inferred from row position or display text.
    A local ID identifies exactly one entity; an entity may have many targets.
    """
    entities: tuple[str, ...]
    sources: Mapping

    def __init__(self, entities=(), sources=None):
        entities = _ids(entities, 'entities')
        copied = {}
        for source, bindings in (sources or {}).items():
            name(source, 'source name')
            if not isinstance(bindings, Mapping):
                raise ValueError('source bindings must map local IDs to entity IDs')
            values = {}
            for local, entity in bindings.items():
                name(local, 'local ID')
                if entity not in entities:
                    raise ValueError(f'unknown entity {entity!r} in {source}')
                values[local] = entity
            copied[source] = MappingProxyType(dict(sorted(values.items())))
        object.__setattr__(self, 'entities', entities)
        object.__setattr__(self, 'sources', MappingProxyType(dict(sorted(copied.items()))))

    def selected(self, source, local_ids):
        """Translate a source selection to canonical entity IDs."""
        bindings = self.sources[source]
        requested = _ids(local_ids, 'local selection')
        unknown = set(requested) - bindings.keys()
        if unknown:
            raise ValueError(f'unmapped IDs in {source}: {sorted(unknown)}')
        return tuple(sorted({bindings[key] for key in requested}))

    def targets(self, entities):
        """Translate canonical selection to every mapped content source."""
        requested = set(_ids(entities, 'entity selection'))
        if requested - set(self.entities):
            raise ValueError('selection contains unknown entities')
        return {source: tuple(local for local, entity in bindings.items() if entity in requested)
                for source, bindings in self.sources.items()}

    def selection_for(self, source, table, entities):
        """Bind selection to an existing table with source-local keys."""
        self.validate_source(source, table.row_ids)
        return SelectionState.for_table(table, selected=self.targets(entities)[source])

    def validate_source(self, source, local_ids):
        """Require exact coverage, including IDs which are currently unselected."""
        actual = set(_ids(local_ids, 'source IDs'))
        expected = set(self.sources[source])
        if actual != expected:
            raise ValueError(f'{source} correspondence mismatch: unmapped={sorted(actual-expected)}, missing={sorted(expected-actual)}')

    def view(self, source, table, view):
        """Map a source-native drawing/image/field view into the linked runtime."""
        from ..experimental.browser.mapped import MappedView
        return MappedView(source, table, view, self)

    def joined_table(self, name, tables):
        """Join keyed tables by explicit entities for the existing linked runtime.

        Output rows use canonical IDs. Columns use source__column names. Missing
        source entities become null. Multiple rows for one entity are ambiguous
        here and must be explicitly aggregated by the author before joining.
        """
        columns = {'id': self.entities}
        for source, table in sorted(tables.items()):
            self.validate_source(source, table.row_ids)
            bindings = self.sources[source]
            if len(set(bindings.values())) != len(bindings):
                raise ValueError(f'ambiguous entity join for {source}; aggregate explicitly')
            indices = {bindings[local]: n for n, local in enumerate(table.row_ids)}
            for column, values in table.columns.items():
                if column == table.key:
                    continue
                key = f'{source}__{column}'
                if key in columns:
                    raise ValueError(f'ambiguous joined column {key}')
                columns[key] = tuple(values[indices[e]] if e in indices else None for e in self.entities)
        return KeyedTable(name, columns)

    def changes(self, revised):
        """Report removed entities and every removed or reassigned local binding."""
        changed = []
        for source, bindings in self.sources.items():
            newer = revised.sources.get(source, {})
            for local, entity in bindings.items():
                if newer.get(local) != entity:
                    changed.append({'source': source, 'id': local, 'before': entity, 'after': newer.get(local)})
        return {'removed_entities': sorted(set(self.entities)-set(revised.entities)), 'changed_bindings': changed}

    def to_dict(self):
        return {'schema': 'inklet.entities/0.1', 'entities': list(self.entities),
                'sources': {source: dict(bindings) for source, bindings in self.sources.items()}}

    @classmethod
    def from_dict(cls, value):
        if (not isinstance(value, dict) or set(value) != {'schema', 'entities', 'sources'}
                or value['schema'] != 'inklet.entities/0.1'):
            raise ValueError('unsupported entity map')
        return cls(value['entities'], value['sources'])
