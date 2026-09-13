"""Joint placement of explicitly registered page annotations."""
from __future__ import annotations
from dataclasses import dataclass, replace
import math
from collections.abc import Mapping
from ..core import Diagram, DiagramError, Rect, Vec2, AnchorRef, mm, resolve
from ..render.bounds import painted_bounds
from .clear_space import _hits


@dataclass(frozen=True)
class FigureAnnotation:
    """A movable label, key or inset in page coordinates.

    ``within`` restricts the full painted footprint. ``target`` is a point,
    Diagram or AnchorRef in the base drawing; it adds a leader. ``at`` pins the
    footprint center. ``positions`` supplies candidate centers instead of the
    default grid/compass search. Fonts and geometry are never scaled.
    """
    body: Diagram
    within: Rect | None = None
    target: object = None
    at: object = None
    positions: tuple | None = None


def _point(value):
    p=value if isinstance(value,Vec2) else Vec2(*value)
    if not all(math.isfinite(v) for v in (p.x,p.y)):raise ValueError('annotation points must be finite')
    return p


def _overlap(a,b,pad=0):
    return not (a.x1+pad<=b.x0 or b.x1+pad<=a.x0 or a.y1+pad<=b.y0 or b.y1+pad<=a.y0)


def _cross(a,b,c,d):
    def turn(p,q,r):return (q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x)
    return turn(a,b,c)*turn(a,b,d)<0 and turn(c,d,a)*turn(c,d,b)<0


def _endpoint(target,box):
    center=box.center;delta=target-center
    if delta.length<1e-12:return center
    factors=[box.width/2/abs(delta.x) if delta.x else math.inf,box.height/2/abs(delta.y) if delta.y else math.inf]
    return center+delta*min(factors)


def place_annotations(art, annotations, *, avoid=None, clearance=.6, pad=1,
                      steps=7, beam=128, leader_color='#77858e', leader_width=.2):
    """Jointly place page annotations with hard label/mark clearance.

    Explicit registrations can mix legends, callouts and insets across regions.
    Fixed placements are respected. A deterministic bounded beam search considers
    alternatives together, preferring short leaders and fewer leader crossings.
    Labels cannot cover other labels or another annotation's leader. Existing
    content stays fixed. Targets/regions use the base drawing's coordinates.

    Default obstacles are the base art. ``avoid`` can instead select its data
    marks, excluding intentionally enclosing backgrounds or anatomy surfaces.
    As in clear-space placement, filled marks use conservative bounds; this is
    a finite candidate search, not a proof that every possible layout fails.
    No result is returned when no collision-free candidate combination is found.
    """
    import inklet as i
    from ..figure import apply_theme
    if not isinstance(art,Diagram) or art.bbox is None:raise TypeError('place_annotations needs a nonempty base Diagram')
    if not isinstance(annotations,Mapping):raise TypeError('annotations must map unique names to FigureAnnotation objects')
    if not annotations:return art
    if any(not isinstance(k,str) or not k for k in annotations):raise ValueError('annotation names must be nonempty strings')
    clearance,pad,leader_width=map(mm,(clearance,pad,leader_width))
    if not all(math.isfinite(v) and v>=0 for v in (clearance,pad,leader_width)):raise ValueError('annotation lengths must be finite and nonnegative')
    if type(steps) is not int or steps<2 or type(beam) is not int or not 1<=beam<=4096:raise ValueError('steps must be >=2 and beam must be between 1 and 4096')
    placements=resolve(art)
    blocked=_ObstacleIndex([art] if avoid is None else avoid)
    candidates={}
    for name,spec in annotations.items():
        if not isinstance(spec,FigureAnnotation) or not isinstance(spec.body,Diagram):raise TypeError('each annotation needs a FigureAnnotation with a Diagram body')
        body=apply_theme(spec.body,i.current_theme());here=resolve(body)[body.id]
        ink=painted_bounds(body,here.world,here.style)
        box=body.bbox
        if box is None:raise ValueError(f'annotation {name} has no bounds')
        if ink is not None:box=box.union(ink)
        region=spec.within if spec.within is not None else art.bbox
        if not isinstance(region,Rect) or not all(math.isfinite(v) for v in (region.x0,region.y0,region.x1,region.y1)):raise ValueError('annotation region must be a finite Rect')
        target=spec.target
        if isinstance(target,(Diagram,AnchorRef)):
            node=target.diagram if isinstance(target,AnchorRef) else target
            if node.id not in placements:raise ValueError(f'annotation {name} target is absent from the base drawing')
            target=placements[node.id].point(target.name) if isinstance(target,AnchorRef) else placements[node.id].bbox.center
        elif target is not None:target=_point(target)
        low=Vec2(region.x0+pad+box.width/2,region.y0+pad+box.height/2)
        high=Vec2(region.x1-pad-box.width/2,region.y1-pad-box.height/2)
        points=[]
        if spec.at is not None:points=[_point(spec.at)]
        elif spec.positions is not None:points=[_point(p) for p in spec.positions]
        else:
            if target is not None:
                for multiple in (1.,2.,3.):
                    for dx,dy in [(1,-1),(-1,-1),(1,1),(-1,1),(1,0),(-1,0),(0,-1),(0,1)]:
                        points.append(target+Vec2(dx*(box.width/2+clearance*multiple+2),dy*(box.height/2+clearance*multiple+2)))
            points += [Vec2(low.x+(high.x-low.x)*c/(steps-1),low.y+(high.y-low.y)*r/(steps-1)) for r in range(steps) for c in range(steps-1,-1,-1)]
        choices=[]
        for index,p in enumerate(dict.fromkeys(points)):
            b=Rect(p.x-box.width/2,p.y-box.height/2,p.x+box.width/2,p.y+box.height/2)
            if p.x<low.x-1e-9 or p.x>high.x+1e-9 or p.y<low.y-1e-9 or p.y>high.y+1e-9:continue
            if target is not None and b.contains(target):continue
            if blocked.hits(b,clearance):continue
            line=None if target is None else (target,_endpoint(target,b))
            cost=(line[1]-line[0]).length if line else index*.001
            choices.append((cost,index,body.translated(p.x-box.center.x,p.y-box.center.y),b,line))
        if not choices:raise DiagramError(f'annotation {name!r} has no clear candidate; enlarge its region, change obstacles or supply positions')
        candidates[name]=sorted(choices,key=lambda v:(v[0],v[1]))
    # Place the most constrained items first, independent of insertion order.
    order=sorted(candidates,key=lambda n:(len(candidates[n]),n))
    states=[(0.,{})]
    for name in order:
        following=[]
        for score,chosen in states:
            for candidate in candidates[name]:
                cost,index,node,b,line=candidate;crossings=0;valid=True
                for old in chosen.values():
                    ob,ol=old[3],old[4]
                    if _overlap(b,ob,clearance):valid=False;break
                    if (line and _hits(*line,ob.pad(clearance+leader_width/2))) or (ol and _hits(*ol,b.pad(clearance+leader_width/2))):valid=False;break
                    if line and ol and _cross(*line,*ol):crossings+=1
                if valid:following.append((score+cost+crossings*10,{**chosen,name:candidate}))
        if not following:raise DiagramError(f'no joint annotation layout found at {name!r}; supply more positions, enlarge regions or increase beam')
        following.sort(key=lambda state:state[0]);states=following[:beam]
    score,chosen=states[0];leaders=[];labels=[];records={}
    for name in sorted(chosen):
        _,_,node,b,line=chosen[name]
        labels.append(node)
        if line:leaders.append(i.as_drawn(i.polyline(line,stroke=leader_color,stroke_width=leader_width)))
        records[name]={'box':(b.x0,b.y0,b.x1,b.y1),'locked':annotations[name].at is not None,'leader':None if line is None else [(p.x,p.y) for p in line]}
    return Diagram(children=(art,*leaders,*labels),notes={**art.notes,'annotations':{'placements':records,'score':score,'beam':beam}},kind='figure-annotations')


class _ObstacleIndex:
    """Compiled page-space path geometry shared by all candidate tests."""
    def __init__(self,items):
        from ..core import PathPrim
        from ..figure import apply_theme
        from .. import current_theme
        self.segments=[];self.boxes=[]
        for art in items:
            if not isinstance(art,Diagram):raise TypeError('annotation obstacles must be Diagrams')
            for p in resolve(apply_theme(art,current_theme()),base_style=current_theme().style_for("root")).values():
                prim=p.diagram.prim
                if prim is None:continue
                stroke=p.style.stroke not in (None,'none')
                t=p.world;radius=(p.style.stroke_width or 0)*.5*math.sqrt(t.a*t.a+t.b*t.b+t.c*t.c+t.d*t.d) if stroke else 0
                if isinstance(prim,PathPrim):
                    for sub in prim.subpaths:
                        pts=[t.apply(v) for v in sub.points]
                        if not pts:continue
                        if prim.filled and p.style.fill not in (None,'none'):self.boxes.append((Rect.hull(pts),radius))
                        elif stroke:
                            self.segments.extend((a,b,radius) for a,b in zip(pts,pts[1:]))
                            if sub.closed:self.segments.append((pts[-1],pts[0],radius))
                elif p.bbox is not None:self.boxes.append((p.bbox,radius))
    def hits(self,box,clearance):
        return any(_overlap(box.pad(clearance+r),b) for b,r in self.boxes) or any(_hits(a,b,box.pad(clearance+r)) for a,b,r in self.segments)
