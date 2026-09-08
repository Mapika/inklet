"""Immutable axis-aligned box assemblies with explicit physical units."""
from dataclasses import dataclass
import hashlib
import json
import math


def _triple(value, label, positive=False):
    if not isinstance(value,(tuple,list)) or len(value)!=3:
        raise ValueError(f'{label} needs three coordinates')
    if any(type(v) not in (int,float) or not math.isfinite(v) or (positive and v<=0) for v in value):
        raise ValueError(f'{label} needs finite'+(' positive' if positive else '')+' coordinates')
    return tuple(value)


@dataclass(frozen=True)
class BoxComponent:
    id: str
    size: tuple[float,float,float]
    center: tuple[float,float,float]

    def __post_init__(self):
        if not isinstance(self.id,str) or not self.id: raise ValueError('component ID must be a nonempty string')
        object.__setattr__(self,'size',_triple(self.size,'size',positive=True))
        object.__setattr__(self,'center',_triple(self.center,'center'))
        if any(not math.isfinite(v) for corner in self.bounds for v in corner):
            raise ValueError('component bounds overflow')
        if any(lo>=hi for lo,hi in zip(*self.bounds)):
            raise ValueError('component size is too small to represent at its center')

    @property
    def bounds(self):
        return tuple(tuple(c+sign*s/2 for c,s in zip(self.center,self.size)) for sign in (-1,1))


@dataclass(frozen=True)
class BoxAssembly:
    components: tuple[BoxComponent,...]
    unit: str

    def __post_init__(self):
        parts=tuple(self.components)
        if not parts or any(not isinstance(p,BoxComponent) for p in parts):
            raise ValueError('assembly needs at least one BoxComponent')
        if len(set(p.id for p in parts))!=len(parts): raise ValueError('duplicate component ID')
        if self.unit not in ('m','mm'): raise ValueError('assembly unit must be explicitly m or mm')
        object.__setattr__(self,'components',parts)
        if any(not math.isfinite(v) for v in self.size): raise ValueError('assembly extent overflow')

    @classmethod
    def from_dict(cls,source):
        if not isinstance(source,dict): raise ValueError('assembly source must be an object')
        raw=source.get('components')
        if not isinstance(raw,list): raise ValueError('assembly components must be an array')
        parts=[]
        for component in raw:
            if not isinstance(component,dict) or component.get('shape')!='box':
                raise ValueError('only explicit axis-aligned box components are supported')
            parts.append(BoxComponent(component.get('id'),component.get('size'),component.get('center')))
        return cls(tuple(parts),source.get('unit'))

    @property
    def ids(self): return tuple(p.id for p in self.components)

    @property
    def bounds(self):
        return (tuple(min(p.bounds[0][axis] for p in self.components) for axis in range(3)),
                tuple(max(p.bounds[1][axis] for p in self.components) for axis in range(3)))

    @property
    def size(self): return tuple(hi-lo for lo,hi in zip(*self.bounds))

    def distance(self, first, second):
        parts={p.id:p for p in self.components}
        if first not in parts or second not in parts: raise ValueError('unknown component ID')
        distance=math.dist(parts[first].center,parts[second].center)
        if not math.isfinite(distance): raise ValueError('component distance overflow')
        return distance

    def section(self, axis, position):
        """Closed-box intersection with an axis plane; rectangles retain IDs.

        Returned (id, (left, bottom, right, top)) coordinates follow remaining
        XYZ axes in order. Box-face planes are included, with no cut thickness.
        """
        if axis not in ('x','y','z'): raise ValueError('section axis must be x, y or z')
        if type(position) not in (int,float) or not math.isfinite(position):
            raise ValueError('section position must be finite')
        dim='xyz'.index(axis);a,b=[k for k in range(3) if k!=dim];result=[]
        for part in self.components:
            lo,hi=part.bounds
            if lo[dim]<=position<=hi[dim]: result.append((part.id,(lo[a],lo[b],hi[a],hi[b])))
        return tuple(result)

    def report(self):
        content=dict(unit=self.unit,components=[dict(id=p.id,shape='box',size=p.size,center=p.center) for p in self.components])
        return dict(schema='inklet.box-assembly/0.1',**content,bounds=self.bounds,size=self.size,
                    geometry_digest=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                    measurements='axis-aligned bounding extent and center distances; no mechanical solver')
