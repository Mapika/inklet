"""Paths and point clouds in an existing model camera, with no independent fit.

These are X-ray overlays: depth changes tone and painting order, not visibility.
For occlusion against rendered surface depth, use SceneRender's overlay API.
"""
from __future__ import annotations
import math
from ..core import Diagram, PathPrim, Subpath, Vec2, mm
from ..themes import mix
from .linalg import Vec3
from .mesh import MeshError


def _xyz(point):
    if isinstance(point, Vec3):
        v = point
    else:
        try:
            x, y, z = point
            v = Vec3(float(x), float(y), float(z))
        except (TypeError, ValueError):
            raise MeshError("3D overlays require finite (x, y, z) points") from None
    if not all(math.isfinite(c) for c in (v.x, v.y, v.z)):
        raise MeshError("3D overlays require finite (x, y, z) points")
    return v


def _options(depth_cue, levels, opacity, width):
    if not math.isfinite(depth_cue) or not 0 <= depth_cue <= 1:
        raise ValueError("depth_cue must be between 0 and 1")
    if isinstance(levels, bool) or not isinstance(levels, int) or not 1 <= levels <= 64:
        raise ValueError("levels must be an integer between 1 and 64")
    if not math.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError("opacity must be between 0 and 1")
    if not math.isfinite(width) or width <= 0:
        raise ValueError("stroke width / radius must be finite and positive")


def _paint(items, *, color, paper, depth_cue, levels, opacity, width, filled, kind):
    if not items:
        return Diagram(kind=kind)
    lo = min(d for d, _ in items); hi = max(d for d, _ in items)
    buckets = [[] for _ in range(levels)]
    for depth, sub in items:
        index = int((depth-lo)/(hi-lo)*(levels-1)) if hi > lo else 0
        buckets[index].append(sub)
    children = []
    # Far items first. Batch subpaths to keep tracing and layout bounded.
    for index in reversed(range(levels)):
        ink = mix(color, paper, depth_cue*index/max(1, levels-1))
        for start in range(0, len(buckets[index]), 64):
            prim = PathPrim(tuple(buckets[index][start:start+64]), filled=filled)
            children.append(Diagram(prim=prim, kind=kind).styled(
                fill=ink if filled else "none", stroke="none" if filled else ink,
                stroke_width=width, stroke_linecap="round", stroke_linejoin="round"))
    result = Diagram(children=tuple(children), kind=kind).styled(opacity=opacity)
    result.notes['projection'] = dict(depth_range=(lo, hi), depth_cue=depth_cue,
                                      occlusion="xray", count=len(items))
    return result


def paths3d(view, lines, *, color="#668fb8", stroke_width=0.25,
            depth_cue=0.3, levels=8, opacity=1., paper="#ffffff"):
    """Project 3D polylines through a fitted View as batched vector paths.

    Width stays in page millimetres. Farther segments fade toward ``paper``.
    All calls using the same View share position and scale; they are not
    recentered independently. Empty runs are allowed; nonfinite points are not.
    """
    width = mm(stroke_width); _options(depth_cue, levels, opacity, width)
    items = []
    for line in lines:
        hits = [view.project(_xyz(v)) for v in line]
        for a, b in zip(hits, hits[1:]):
            if min(a.depth, b.depth) < view.near:
                raise MeshError("3D overlay crosses the camera near plane; clip it before projection")
            if a.point != b.point:
                items.append(((a.depth+b.depth)/2, Subpath((a.point, b.point))))
    return _paint(items, color=color, paper=paper, depth_cue=depth_cue,
                  levels=levels, opacity=opacity, width=width, filled=False,
                  kind="projected-paths")


def points3d(view, points, *, color="#668fb8", radius=0.35, shape="circle",
             depth_cue=0.3, levels=8, opacity=1., paper="#ffffff"):
    """Project a point cloud with fixed-size circle, square or diamond markers.

    A radius is a page length, independent of the units of the 3D data.
    The returned Diagram shares the View's origin with models and paths3d.
    """
    radius = mm(radius); _options(depth_cue, levels, opacity, radius)
    if shape not in ("circle", "square", "diamond"):
        raise ValueError("shape must be circle, square or diamond")
    count = 20 if shape == "circle" else 4
    angle = math.pi/4 if shape == "square" else 0.
    offsets = tuple(Vec2(math.cos(angle+k*2*math.pi/count)*radius,
                         math.sin(angle+k*2*math.pi/count)*radius) for k in range(count))
    items = []
    for point in points:
        hit = view.project(_xyz(point))
        if hit.depth < view.near:
            raise MeshError("3D point is behind the camera near plane")
        items.append((hit.depth, Subpath(tuple(hit.point+v for v in offsets), closed=True)))
    return _paint(items, color=color, paper=paper, depth_cue=depth_cue,
                  levels=levels, opacity=opacity, width=radius, filled=True,
                  kind="projected-points")
