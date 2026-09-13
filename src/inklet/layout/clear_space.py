"""Conservative placement in empty plot space, preserving label size."""
from __future__ import annotations
import math
from dataclasses import replace
from ..render.bounds import painted_bounds
from ..core import Diagram, DiagramError, PathPrim, Rect, resolve, mm


def _hits(a,b,box):
    enter,leave=0.,1.
    for start,end,lo,hi in [(a.x,b.x,box.x0,box.x1),(a.y,b.y,box.y0,box.y1)]:
        delta=end-start
        if abs(delta)<1e-12:
            if start<lo or start>hi:return False
        else:
            t0,t1=sorted(((lo-start)/delta,(hi-start)/delta));enter=max(enter,t0);leave=min(leave,t1)
            if enter>leave:return False
    return True


def place_in_clear_space(item, *, within, avoid=(), pad=1, clearance=.5, steps=9):
    """Place a Diagram inside a Rect, clear of supplied drawing geometry.

    Tests corners first, then a deterministic grid. Stroked paths use their
    segments (not their whole bounding boxes); filled subpaths and other
    primitives use conservative bounds. Transforms are resolved. This tests
    flattened vector geometry, not raster pixels, clipping or opacity. Use it
    for legends/callouts against plotted lines/marks; not as an occlusion test
    for rendered anatomy. Failure raises instead of silently hiding data.
    Returns absolute coordinates with the selected box in its notes.
    """
    if not isinstance(item,Diagram) or item.bbox is None or not isinstance(within,Rect):raise TypeError('clear-space placement requires a nonempty Diagram and a Rect')
    pad,clearance=mm(pad),mm(clearance)
    if not all(math.isfinite(v) and v>=0 for v in (pad,clearance)):raise ValueError('pad/clearance must be finite and nonnegative')
    if type(steps) is not int or steps<2:raise ValueError('steps must be an integer >= 2')
    if not all(math.isfinite(v) for v in (within.x0,within.y0,within.x1,within.y1)):raise ValueError('placement rectangle must be finite')
    root=next(p for p in resolve(item).values() if p.diagram is item)
    painted=painted_bounds(item,root.world,root.style)
    b=item.bbox.union(painted) if painted is not None else item.bbox
    lo=within.x0+pad;hi=within.x1-pad-b.width;top=within.y0+pad;bottom=within.y1-pad-b.height
    if hi<lo or bottom<top:raise DiagramError('legend/content is larger than the available region; use an external legend or enlarge the panel')
    segments=[];boxes=[]
    for art in avoid:
        if not isinstance(art,Diagram):raise TypeError('avoid entries must be Diagrams')
        for placed in resolve(art).values():
            node=placed.diagram
            if node.prim is None:continue
            radius=(placed.style.stroke_width or 0)/2
            # Affine scaling stretches a stroke too; use a conservative norm.
            t=placed.world;radius*=math.sqrt(t.a*t.a+t.b*t.b+t.c*t.c+t.d*t.d)
            if isinstance(node.prim,PathPrim):
                for sub in node.prim.subpaths:
                    pts=tuple(t.apply(v) for v in sub.points)
                    if not pts:continue
                    if node.prim.filled and placed.style.fill!='none':boxes.append((Rect.hull(pts),radius))
                    else:
                        segments.extend((a,b,radius) for a,b in zip(pts,pts[1:]))
                        if sub.closed:segments.append((pts[-1],pts[0],radius))
            else:boxes.append((placed.bbox,radius))
    candidates=[(hi,top),(lo,top),(hi,bottom),(lo,bottom)]
    candidates.extend((lo+(hi-lo)*c/(steps-1),top+(bottom-top)*r/(steps-1)) for r in range(steps) for c in range(steps-1,-1,-1))
    for x,y in dict.fromkeys(candidates):
        def expanded(radius):return Rect(x-clearance-radius,y-clearance-radius,x+b.width+clearance+radius,y+b.height+clearance+radius)
        if any(_hits(a,z,expanded(radius)) for a,z,radius in segments):continue
        if any(not (v.x1<expanded(r).x0 or v.x0>expanded(r).x1 or v.y1<expanded(r).y0 or v.y0>expanded(r).y1) for v,r in boxes if v is not None):continue
        result=item.translated(x-b.x0,y-b.y0)
        result=replace(result,notes={**result.notes,'clear_space':{'box':(x,y,x+b.width,y+b.height),'clearance':clearance}})
        return result
    raise DiagramError('no clear legend/content placement found; use an external legend, a larger panel, or fewer entries')
