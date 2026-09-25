"""Project entity maps; moved to `inklet.project.identity` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.project.identity`.
"""
from inklet.project.identity import (  # noqa: F401
    EntityMap,
    KeyedTable,
    Mapping,
    MappingProxyType,
    SelectionState,
    _ids,
    dataclass,
    name,
)
