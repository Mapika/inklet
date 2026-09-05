"""Common resolved paint tree consumed by the v2 export backends.

Transforms and clip/compositing groups remain structural. Inherited paint is
made explicit, while group opacity stays on its original group so overlapping
children are composited together instead of faded individually.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType
from urllib.parse import quote
from ..core import Diagram, Style, DiagramError

MITER_LIMIT = 4.0
DEFAULT_PAINT = Style(fill='#000000', stroke='none', stroke_width=1.,
                      stroke_linecap='butt', stroke_linejoin='miter',
                      fill_opacity=1., stroke_opacity=1.)


@dataclass(frozen=True)
class PaintProgram:
    root: Diagram
    node_count: int
    ids: object


def resolve_paint(root, *, stable_ids=False):
    """Freeze inherited paint choices once for SVG and PDF export."""
    count = 0
    ids = {}
    def identify(node, path, scope=''):
        # Cell names are local to a document. Preserve named IDs across edits,
        # but qualify nested cells by their containing cell. Escape separators
        # so a literal slash in a name cannot impersonate a nested path.
        here = f'{scope}cell-{quote(node.name, safe="")}' if node.kind == 'document-cell' else path
        if node.id in ids:
            raise DiagramError(f'duplicate drawing id {node.id!r}')
        ids[node.id] = here if stable_ids else node.id
        child_scope = f'{here}/' if node.kind == 'document-cell' else scope
        for index,child in enumerate(node.children): identify(child,f'{here}/{index}',child_scope)
    identify(root,'page')
    def notes(value):
        if isinstance(value,str): return ids.get(value,value)
        if isinstance(value,dict): return {k:notes(v) for k,v in value.items()}
        if isinstance(value,tuple): return tuple(notes(v) for v in value)
        if isinstance(value,list): return [notes(v) for v in value]
        return value
    def visit(node, inherited):
        nonlocal count
        count += 1
        effective = node.style.over(inherited)
        if effective.stroke_linecap not in ('butt', 'round', 'square'):
            raise DiagramError(f'invalid stroke cap {effective.stroke_linecap!r}')
        if effective.stroke_linejoin not in ('miter', 'round', 'bevel'):
            raise DiagramError(f'invalid stroke join {effective.stroke_linejoin!r}')
        style = replace(effective, opacity=node.style.opacity)
        children = tuple(visit(child, replace(effective, opacity=None)) for child in node.children)
        return replace(node, id=ids[node.id], style=style, children=children, anchors=dict(node.anchors),
                       attached_to=tuple(ids.get(v,v) for v in node.attached_to),
                       notes=notes(node.notes), _cache={})
    result = visit(root, DEFAULT_PAINT)
    return PaintProgram(result, count, MappingProxyType(ids))
