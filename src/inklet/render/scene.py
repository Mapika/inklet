"""Backend-independent render snapshots and bounded revision reuse.

The authoring tree remains available for layout and diagnostics. Exporters read
these resolved nodes, which retain compositing groups and shared geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ..core import MarkerBatchPrim, Affine, Diagram, DiagramError, EllipsePrim, ImagePrim, PhantomPrim, Rect, RectPrim, Style, TextPrim, Vec2
from ..core.diagram import _inside_clips
from ..core.style import EMPTY_STYLE
from .bounds import geometry_bounds, primitive_bounds


@dataclass(frozen=True, eq=False)
class GeometryResource:
    """One immutable primitive, shared by placements and successive revisions."""
    prim: object = field(repr=False)

    @cached_property
    def bounds(self):
        return geometry_bounds(self.prim)


@dataclass(frozen=True, eq=False)
class SceneNode:
    """One placement with resolved paint, coordinates and clipping."""
    key: tuple[int, ...]
    id: str
    name: str | None
    kind: str
    geometry: GeometryResource | None
    transform: Affine
    local_style: Style
    style: Style
    world: Affine
    clip_region: tuple[Vec2, ...]
    world_clip: tuple[Vec2, ...]
    clip_regions: tuple[tuple[Vec2, ...], ...]
    blend_mode: str | None
    children: tuple[SceneNode, ...]

    @property
    def prim(self):
        return None if self.geometry is None else self.geometry.prim

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def visible_at(self, point: Vec2) -> bool:
        """Clip visibility only; this does not test the primitive's shape."""
        return _inside_clips(point, self.clip_regions)

    @cached_property
    def painted_bounds(self):
        box = (primitive_bounds(self.prim, self.world, self.style,
                                local_bounds=self.geometry.bounds)
               if self.geometry is not None else None)
        for child in self.children:
            other = child.painted_bounds
            if other is not None:
                box = other if box is None else box.union(other)
        if box is not None and self.world_clip:
            box = box.overlap(Rect.hull(self.world_clip))
        return box

    @cached_property
    def paint_count(self):
        from .analysis import primitive_paint_count
        count = primitive_paint_count(self.prim, self.style)
        for child in self.children:
            if count >= 2:
                break
            count += child.paint_count
        return min(count, 2)


@dataclass(frozen=True)
class SceneChange:
    key: tuple[int, ...]
    node_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class RenderScene:
    """A compiled native scene shared by SVG, PDF and PNG exports.

    Geometry and image bytes are retained. Font files are fingerprinted and
    checked at export; changing them requires a new compilation. The revision
    compiler retains only the supplied previous scene, with no global cache.
    """
    root: SceneNode
    bbox: Rect
    stats: Mapping
    changes: tuple[SceneChange, ...]
    _nodes: Mapping = field(repr=False)
    _resources: Mapping = field(repr=False)
    _images: Mapping = field(repr=False)
    _fonts: Mapping = field(repr=False)

    def walk(self):
        return self.root.walk()

    def validate_fonts(self):
        for path, digest in self._fonts.items():
            try:
                current = hashlib.sha256(Path(path).read_bytes()).digest()
            except OSError as exc:
                raise DiagramError(f'compiled font is unavailable: {path}; restart the process and rebuild the figure') from exc
            if current != digest:
                raise DiagramError(f'compiled font changed: {path}; restart the process and rebuild the figure')

    def sources_current(self):
        """Check external inputs when a document considers reusing a snapshot."""
        for path, data in self._images.items():
            try:
                if Path(path).read_bytes() != data:
                    return False
            except OSError:
                return False
        # Font verification is performed before and after actual exports.
        return True

    def to_svg(self, **options):
        from .svg import to_svg
        return to_svg(self, **options)

    def to_pdf(self, **options):
        from .pdf import to_pdf
        return to_pdf(self, **options)

    def to_png(self, **options):
        from .raster import to_png
        return to_png(self, **options)

    def damage_bounds(self, previous: RenderScene):
        """Conservative old/new ink union for changed placements, in page mm.

        This describes redraw coverage, not an incremental export. Removed
        content and changed ancestor compositing groups contribute too.
        """
        if self.bbox != previous.bbox:
            return self.bbox.union(previous.bbox)
        result = None
        for key in self._nodes.keys() | previous._nodes.keys():
            old, new = previous._nodes.get(key), self._nodes.get(key)
            if old is new:
                continue
            if (old is not None and new is not None
                    and all(getattr(old,field) == getattr(new,field) for field in
                            ('id','name','kind','geometry','world','local_style','style',
                             'clip_regions','blend_mode'))
                    and new.blend_mode is None and new.local_style.opacity in (None,1.)):
                continue
            for node in (old, new):
                box = node.painted_bounds if node is not None else None
                if box is not None:
                    result = box if result is None else result.union(box)
        return result


def compile_scene(root: Diagram | RenderScene, *, previous: RenderScene | None = None) -> RenderScene:
    """Resolve a drawing for all native backends, reusing an optional revision.

    Compilation visits the source tree, but unchanged resolved nodes and
    geometry resources are reused by identity. Statistics distinguish this
    traversal from actual rebuilding. No document layout is performed here.
    """
    if isinstance(root, RenderScene):
        return root
    if not isinstance(root, Diagram):
        raise TypeError('compile_scene expects a Diagram or RenderScene')
    old_nodes = previous._nodes if previous is not None else {}
    old_resources = previous._resources if previous is not None else {}
    resources, nodes, images, fonts = {}, {}, {}, {}
    # Small immutable shapes and shaped labels can be regenerated by layout.
    # Intern those by value. Dense paths use identity, avoiding a full data hash
    # on every revision; their future buffer representation will own that cost.
    small = (EllipsePrim, RectPrim, PhantomPrim, TextPrim)
    interned = {source: resource for source,resource in old_resources.values()
                if isinstance(source, small)}
    stats = dict(visited_nodes=0, reused_nodes=0, rebuilt_nodes=0,
                 reused_geometry=0, new_geometry=0, geometry_placements=0, image_bytes=0)
    changes = []
    prior_geometry = {id(resource) for _,resource in old_resources.values()}
    seen_geometry = set()

    def geometry(prim):
        if prim is None:
            return None
        stats['geometry_placements'] += 1
        key = id(prim)
        if key in resources:
            return resources[key][1]
        frozen = prim
        if isinstance(prim, ImagePrim) and prim.data is None:
            if prim.source not in images:
                try:
                    data = Path(prim.source).read_bytes()
                except OSError as exc:
                    raise DiagramError(f'cannot compile image resource: {prim.source}') from exc
                old_data = previous._images.get(prim.source) if previous is not None else None
                images[prim.source] = old_data if old_data == data else data
                stats['image_bytes'] += len(data)
            frozen = replace(prim, data=images[prim.source])
        record = old_resources.get(key)
        old = record[1] if record is not None and record[0] is prim else None
        if old is None and isinstance(prim, small):
            old = interned.get(prim)
        if old is not None and (frozen is prim or frozen == old.prim):
            resource = old
        else:
            resource = GeometryResource(frozen)
        if id(resource) not in seen_geometry:
            seen_geometry.add(id(resource))
            stats['reused_geometry' if id(resource) in prior_geometry else 'new_geometry'] += 1
        resources[key] = (prim, resource)
        if isinstance(prim, small):
            interned[prim] = resource
        from .brushes import PaintedPrim
        shape = prim.shape if isinstance(prim, PaintedPrim) else prim
        if isinstance(shape, TextPrim):
            paths = {shape.font_path} | {run.font_path for line in shape.lines for run in line.runs}
            for path in paths - {None}:
                if path not in fonts:
                    try:
                        fonts[path] = hashlib.sha256(Path(path).read_bytes()).digest()
                        if (previous is not None and path in previous._fonts
                                and previous._fonts[path] != fonts[path]):
                            raise DiagramError(f'compiled font changed: {path}; restart the process and rebuild the figure')
                    except OSError as exc:
                        raise DiagramError(f'cannot compile font resource: {path}') from exc
        return resource

    def visit(node, parent, inherited, clips, key):
        stats['visited_nodes'] += 1
        world = parent @ node.transform
        style = node.style.over(inherited)
        own_clip = tuple(world.apply(p) for p in node.clip_region)
        if own_clip:
            clips = clips + (own_clip,)
        resource = geometry(node.prim)
        children = tuple(visit(c, world, style, clips, key+(j,)) for j,c in enumerate(node.children))
        blend = node.notes.get('blend_mode') if node.kind == 'blend' else None
        old = old_nodes.get(key)
        reasons = []
        if old is None:
            reasons.append('added')
        else:
            if old.geometry is not resource: reasons.append('geometry')
            if old.local_style != node.style or old.style != style: reasons.append('paint')
            if old.transform != node.transform or old.world != world: reasons.append('transform')
            if old.clip_region != node.clip_region or old.clip_regions != clips: reasons.append('clip')
            if old.blend_mode != blend: reasons.append('compositing')
            if (old.id,old.name,old.kind) != (node.id,node.name,node.kind): reasons.append('identity')
            if old.children != children: reasons.append('children')
        if not reasons:
            result = old
            stats['reused_nodes'] += 1
        else:
            result = SceneNode(key,node.id,node.name,node.kind,resource,node.transform,
                               node.style,style,world,node.clip_region,own_clip,clips,blend,children)
            stats['rebuilt_nodes'] += 1
            changes.append(SceneChange(key,node.id,tuple(reasons)))
        nodes[key] = result
        return result

    resolved = visit(root, Affine(), EMPTY_STYLE, (), ())
    for key in sorted(old_nodes.keys() - nodes.keys()):
        changes.append(SceneChange(key,old_nodes[key].id,('removed',)))
    try:
        box = root.bbox
    except DiagramError:
        box = Rect(0.,0.,0.,0.)
    stats['marker_instances'] = sum(len(n.prim) for n in nodes.values()
                                    if isinstance(n.prim, MarkerBatchPrim))
    buffers = {id(resource.prim.data): resource.prim.data for _, resource in resources.values()
               if isinstance(resource.prim, MarkerBatchPrim)}
    stats['marker_buffer_bytes'] = sum(len(data) for data in buffers.values())
    return RenderScene(resolved,box,MappingProxyType(stats),tuple(changes),
                       MappingProxyType(nodes),MappingProxyType(resources),
                       MappingProxyType(images),MappingProxyType(fonts))


def canvas(root, width=None, height=None, margin=0.):
    """Shared physical page contract for all native backends."""
    from ..core.units import mm
    try:
        box = root.bbox
    except DiagramError:
        box = Rect(0.,0.,0.,0.)
    content = box.pad(margin)
    return (content, content.width if width is None else mm(width),
            content.height if height is None else mm(height))
