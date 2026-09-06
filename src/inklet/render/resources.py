"""Backend capabilities and explicit raster/scene provenance."""
import hashlib
from ..core import ImagePrim, Affine


def rendering_manifest(root):
    from dataclasses import asdict
    from .brushes import PaintedPrim
    scenes, rasters, resources, paints, blends, overlays = [], [], {}, {}, set(), []
    def visit(node,parent):
        world=parent@node.transform
        if isinstance(node.prim,PaintedPrim):
            brush=node.prim.brush
            paints.setdefault(repr(brush),dict(type=type(brush).__name__,**asdict(brush)))
        if node.kind=='blend': blends.add(node.notes['blend_mode'])
        if 'scene_overlay' in node.notes:
            overlays.append(dict(node_id=node.id, transform=asdict(world), **node.notes['scene_overlay']))
        if isinstance(node.prim,ImagePrim) and 'scene_render' in node.notes:
            scenes.append(dict(node_id=node.id, transform=asdict(world), **node.notes['scene_render']))
        if isinstance(node.prim,ImagePrim) and 'raster_layer' in node.notes:
            rasters.append(dict(node_id=node.id, transform=asdict(world), **node.notes['raster_layer']))
        if isinstance(node.prim, ImagePrim):
            p=node.prim
            key = hashlib.sha256(p.data).hexdigest() if p.data is not None else p.source
            item=resources.setdefault(key, dict(sha256=key if p.data is not None else None,
                                               source=p.source, placements=0, pixels=p.pixel_size))
            item['placements'] += 1
        for child in node.children: visit(child,world)
    visit(root,Affine())
    return dict(schema_version=1, scenes=scenes, scene_overlays=overlays, raster_layers=rasters,
                image_resources=list(resources.values()),paint_resources=list(paints.values()),
                blend_modes=sorted(blends))


def rendering_capabilities():
    """Declared format support; no renderer is selected implicitly."""
    return dict(svg=dict(text='editable or outlined',gradients='vector',hatching='vector',
                         blending='vector',masks='explicit raster',scenes='embedded raster',scene_paths='vector'),
                pdf=dict(text='embedded or outlined',gradients='vector',hatching='vector',
                         blending='vector',masks='explicit raster',scenes='embedded raster',scene_paths='vector'),
                png=dict(renderer='resvg',extra='render',browser_required=False,
                         transparent_background=True,max_pixels=40_000_000))
