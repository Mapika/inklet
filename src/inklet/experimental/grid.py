"""Rectilinear nodal fields with explicit triangle interpolation and tracing."""
from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import json
import math
import re

from .fields import _finite
from .selection import KeyedTable


def _array(value, name):
    if not isinstance(value,(list,tuple)):raise ValueError(f'{name} must be an array')
    return value


def _mean(values):
    scale=max(map(abs,values))
    return scale*math.fsum((v/scale)/len(values) for v in values) if scale else 0.0


@dataclass(frozen=True)
class ContourSegment:
    cell_id: str
    level: float
    points: tuple


@dataclass(frozen=True)
class Streamline:
    id: str
    points: tuple
    forward: str
    backward: str
    closed: bool = False

    def __post_init__(self):
        points=tuple(tuple(_array(p,'trace point')) for p in _array(self.points,'trace points'))
        if not isinstance(self.id,str) or not self.id or not 1<=len(points)<=4001:
            raise ValueError('trace needs an ID and 1–4001 points')
        if any(len(p)!=2 or not all(map(_finite,p)) for p in points):raise ValueError('trace points must be finite XY pairs')
        if any(not math.isfinite(math.dist(a,b)) for a,b in zip(points,points[1:])):raise ValueError('trace segments must have finite length')
        if type(self.closed) is not bool or any(not isinstance(v,str) or not v for v in (self.forward,self.backward)):
            raise ValueError('trace needs explicit termination reasons and a boolean closed flag')
        if self.closed and points[0]!=points[-1]:raise ValueError('closed trace must return to its seed')
        object.__setattr__(self,'points',points)


@dataclass(frozen=True)
class Streamlines:
    source_digest: str
    lines: tuple
    step: float
    max_length: float
    max_steps: int
    min_speed: float

    def __post_init__(self):
        lines=tuple(_array(self.lines,'lines'))
        if not 1<=len(lines)<=32 or any(not isinstance(v,Streamline) for v in lines) or len({v.id for v in lines})!=len(lines):
            raise ValueError('provide 1–32 uniquely identified Streamlines')
        if not isinstance(self.source_digest,str) or not re.fullmatch('[0-9a-f]{64}',self.source_digest):raise ValueError('streamlines need a source digest')
        if any(not _finite(v) or v<=0 for v in (self.step,self.max_length)) or not _finite(self.min_speed) or self.min_speed<0:
            raise ValueError('tracing parameters must be finite and positive; min_speed may be zero')
        if type(self.max_steps) is not int or not 1<=self.max_steps<=2000:raise ValueError('invalid tracing step budget')
        object.__setattr__(self,'lines',lines)

    def report(self):
        return dict(source_digest=self.source_digest,method='normalized-vector RK4; step in geometry units',
            step=self.step,max_length_per_direction=self.max_length,max_steps_per_direction=self.max_steps,
            min_speed=self.min_speed,lines=[dict(id=line.id,points=len(line.points),forward=line.forward,
                backward=line.backward,closed=line.closed,length=sum(math.dist(a,b) for a,b in zip(line.points,line.points[1:])))
                for line in self.lines])


@dataclass(frozen=True)
class GridField:
    """Increasing X/Y axes; nodal scalar and XY-vector matrices in Y,X order.

    Every rectangular cell has an explicit ID, in row-major order from low Y.
    Each cell splits from lower-left to upper-right. Interpolation is linear
    within those triangles, not bilinear. Any missing corner masks that entire
    cell for the affected field; scalar and vector masks are independent.
    """
    x: tuple
    y: tuple
    ids: tuple
    scalars: tuple
    vectors: tuple
    unit: str = 'mm'
    scalar_unit: str = 'a.u.'
    vector_unit: str = 'a.u.'

    def __post_init__(self):
        for name in ('x','y'):
            axis=tuple(_array(getattr(self,name),name))
            if len(axis)<2 or not all(map(_finite,axis)) or any(not 0<b-a<math.inf for a,b in zip(axis,axis[1:])):
                raise ValueError('axes need at least two finite, strictly increasing coordinates')
            if not math.isfinite(axis[-1]-axis[0]):raise ValueError('axis span must be representable')
            object.__setattr__(self,name,axis)
        count=(len(self.x)-1)*(len(self.y)-1)
        ids=tuple(_array(self.ids,'ids'))
        if count>4096 or len(ids)!=count or any(not isinstance(k,str) or not k for k in ids) or len(set(ids))!=count:
            raise ValueError('provide at most 4096 cells and one unique nonempty ID per cell')
        object.__setattr__(self,'ids',ids)
        for name in ('scalars','vectors'):
            matrix=_array(getattr(self,name),name);rows=[]
            if len(matrix)!=len(self.y):raise ValueError('nodal matrices must match Y,X axis lengths')
            for row in matrix:
                row=_array(row,name)
                if len(row)!=len(self.x):raise ValueError('nodal matrices must match Y,X axis lengths')
                values=[]
                for value in row:
                    if value is not None:
                        if name=='scalars':
                            if not _finite(value):raise ValueError('scalars must be finite numbers or None')
                        else:
                            value=tuple(_array(value,'vector'))
                            if len(value)!=2 or not all(map(_finite,value)) or not math.isfinite(math.hypot(*value)):
                                raise ValueError('vectors need two finite components with representable magnitude')
                    values.append(value)
                rows.append(tuple(values))
            object.__setattr__(self,name,tuple(rows))
        if self.unit not in ('m','mm','um','nm') or any(not isinstance(v,str) or not v.strip() for v in (self.scalar_unit,self.vector_unit)):
            raise ValueError('use m/mm/um/nm geometry and explicit nonempty field units')
        self.table()

    def source(self):
        return {name:getattr(self,name) for name in ('x','y','ids','scalars','vectors','unit','scalar_unit','vector_unit')}

    @classmethod
    def from_dict(cls,source):return cls(**{name:source[name] for name in ('x','y','ids','scalars','vectors','unit','scalar_unit','vector_unit')})

    @property
    def digest(self):return hashlib.sha256(json.dumps(self.source(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    @property
    def min_spacing(self):return min(b-a for axis in (self.x,self.y) for a,b in zip(axis,axis[1:]))

    def cells(self):
        for iy in range(len(self.y)-1):
            for ix in range(len(self.x)-1):
                yield self.ids[iy*(len(self.x)-1)+ix],ix,iy

    def corners(self,ix,iy,kind):
        matrix=getattr(self,kind)
        return (matrix[iy][ix],matrix[iy][ix+1],matrix[iy+1][ix+1],matrix[iy+1][ix])

    def table(self,name='grid-cells'):
        columns={k:[] for k in ('id','x','y','area','scalar','vx','vy','magnitude')}
        for key,ix,iy in self.cells():
            scalar=self.corners(ix,iy,'scalars');vector=self.corners(ix,iy,'vectors')
            scalar=None if None in scalar else _mean(scalar)
            vector=None if None in vector else tuple(_mean([v[n] for v in vector]) for n in (0,1))
            area=(self.x[ix+1]-self.x[ix])*(self.y[iy+1]-self.y[iy])
            if not math.isfinite(area) or area<=0:raise ValueError('cell area must be positive and representable')
            row=(key,_mean(self.x[ix:ix+2]),_mean(self.y[iy:iy+2]),area,scalar,
                 *(vector if vector is not None else (None,None)),None if vector is None else math.hypot(*vector))
            for column,value in zip(columns,row):columns[column].append(value)
        return KeyedTable(name,columns)

    def validate_table(self,table):
        expected=self.table(table.name)
        if set(expected.row_ids)!=set(table.row_ids):raise ValueError('grid/table ID mismatch')
        positions={key:n for n,key in enumerate(expected.row_ids)}
        for name,values in expected.columns.items():
            if name not in table.columns:raise ValueError(f'missing grid measurement column: {name}')
            for n,key in enumerate(table.row_ids):
                a,b=table.columns[name][n],values[positions[key]]
                if type(a) is not type(b) or a!=b:raise ValueError(f'grid measurement mismatch: {key}, {name}')

    def locate(self,point):
        x,y=point
        if not (self.x[0]<=x<=self.x[-1] and self.y[0]<=y<=self.y[-1]):return None
        return min(bisect_right(self.x,x)-1,len(self.x)-2),min(bisect_right(self.y,y)-1,len(self.y)-2)

    def sample(self,point,kind='scalars'):
        if kind not in ('scalars','vectors'):raise ValueError('sample kind must be scalars or vectors')
        if len(_array(point,'point'))!=2 or not all(map(_finite,point)):raise ValueError('point needs finite XY coordinates')
        cell=self.locate(point)
        if cell is None:return None
        ix,iy=cell;values=self.corners(ix,iy,kind)
        if None in values:return None
        u=(point[0]-self.x[ix])/(self.x[ix+1]-self.x[ix]);v=(point[1]-self.y[iy])/(self.y[iy+1]-self.y[iy])
        weights=(1-u,u-v,v,0) if v<=u else (1-v,0,u,v-u)
        def blend(raw):
            scale=max(map(abs,raw))
            return scale*max(-1.,min(1.,math.fsum(w*(a/scale) for w,a in zip(weights,raw)))) if scale else 0.0
        return blend(values) if kind=='scalars' else tuple(blend([a[n] for a in values]) for n in (0,1))

    def contours(self,levels):
        levels=tuple(_array(levels,'levels'))
        if not levels or len(levels)>16 or not all(map(_finite,levels)) or any(a>=b for a,b in zip(levels,levels[1:])):
            raise ValueError('provide 1–16 finite strictly increasing contour levels')
        segments=[];seen=set()
        for key,ix,iy in self.cells():
            values=self.corners(ix,iy,'scalars')
            if None in values:continue
            points=((self.x[ix],self.y[iy]),(self.x[ix+1],self.y[iy]),(self.x[ix+1],self.y[iy+1]),(self.x[ix],self.y[iy+1]))
            for tri in ((0,1,2),(0,2,3)):
                for level in levels:
                    hits=[]
                    for a,b in zip(tri,tri[1:]+tri[:1]):
                        va,vb=values[a],values[b]
                        # Half-open ownership: equal vertices belong to the high side.
                        if (va<level)==(vb<level):continue
                        scale=max(abs(va),abs(vb),abs(level),1e-300)
                        t=(level/scale-va/scale)/(vb/scale-va/scale)
                        point=tuple((1-t)*p+t*q for p,q in zip(points[a],points[b]))
                        if point not in hits:hits.append(point)
                    if len(hits)==2 and hits[0]!=hits[1]:
                        edge=(level,*sorted(hits))
                        if edge not in seen:
                            seen.add(edge);segments.append(ContourSegment(key,level,tuple(hits)))
        return tuple(segments)

    def split_segment(self,a,b):
        cuts=[0.,1.]
        for n,axis in enumerate((self.x,self.y)):
            if a[n]!=b[n]:cuts.extend((v-a[n])/(b[n]-a[n]) for v in axis if min(a[n],b[n])<v<max(a[n],b[n]))
        cuts=sorted(set(cuts))
        for lo,hi in zip(cuts,cuts[1:]):
            p=tuple((1-lo)*x+lo*y for x,y in zip(a,b));q=tuple((1-hi)*x+hi*y for x,y in zip(a,b))
            cell=self.locate(tuple((x+y)/2 for x,y in zip(p,q)))
            if cell is not None:
                ix,iy=cell;yield self.ids[iy*(len(self.x)-1)+ix],p,q

    def streamlines(self,seeds,*,step,max_length,max_steps=1000,min_speed=1e-12):
        seeds=tuple(_array(seeds,'seeds'))
        if not 1<=len(seeds)<=32:raise ValueError('provide 1–32 explicitly identified seeds')
        if not _finite(step) or not 0<step<=self.min_spacing/4 or step/1024==0:
            raise ValueError('step must be positive and at most one quarter of the smallest grid interval')
        if not _finite(max_length) or max_length<=0 or not _finite(min_speed) or min_speed<0:
            raise ValueError('max_length must be positive; min_speed must be nonnegative and finite')
        if type(max_steps) is not int or not 1<=max_steps<=2000:raise ValueError('max_steps must be 1–2000 per direction')
        copied=[];ids=set()
        for entry in seeds:
            if not isinstance(entry,(list,tuple)) or len(entry)!=2:raise ValueError('seed needs an ID and XY point')
            key,point=entry
            if not isinstance(key,str) or not key or key in ids:raise ValueError('seed IDs must be unique nonempty strings')
            point=tuple(_array(point,'seed'))
            if len(point)!=2 or not all(map(_finite,point)):raise ValueError('seed needs finite XY coordinates')
            ids.add(key);copied.append((key,point))
        def direction(point,sign):
            if self.locate(point) is None:return None,'boundary'
            value=self.sample(point,'vectors')
            if value is None:return None,'missing'
            speed=math.hypot(*value)
            if speed<=min_speed:return None,'stagnation'
            return tuple(sign*v/speed for v in value),None
        def trace(seed,sign):
            points=[seed];distance=0;initial,reason=direction(seed,sign)
            if reason:return points,reason,False
            for _ in range(max_steps):
                h=min(step,max_length-distance)
                if h<step/1024:return points,'length',False
                p=points[-1];first,reason=direction(p,sign)
                if reason:return points,reason,False
                while h>=step/1024:
                    def advance(vector,amount):return tuple(v+amount*d for v,d in zip(p,vector))
                    second,reason=direction(advance(first,h/2),sign)
                    third,reason=(direction(advance(second,h/2),sign) if second is not None else (None,reason))
                    fourth,reason=(direction(advance(third,h),sign) if third is not None else (None,reason))
                    if fourth is not None:
                        end=tuple(v+h*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(p,first,second,third,fourth))
                        _,reason=direction(end,sign)
                        if reason is None:
                            # Test each crossed cell, including a corner crossing
                            # that RK stages alone could miss.
                            if any(self.sample(tuple((x+y)/2 for x,y in zip(a,b)),'vectors') is None for _,a,b in self.split_segment(p,end)):
                                reason='missing'
                            else:break
                    h/=2
                else:return points,reason or 'resolution',False
                actual=math.dist(p,end)
                if actual==0:return points,'resolution',False
                points.append(end);distance+=actual
                if distance>8*step and math.dist(end,seed)<step*.5:
                    tangent,_=direction(end,sign)
                    supported=all(self.sample(tuple((x+y)/2 for x,y in zip(a,b)),'vectors') is not None
                                  for _,a,b in self.split_segment(p,seed))
                    within_length=distance-actual+math.dist(p,seed)<=max_length
                    if supported and within_length and tangent is not None and sum(a*b for a,b in zip(tangent,initial))>.9:
                        points[-1]=seed;return points,'loop',True
            return points,'steps',False
        lines=[]
        for key,seed in copied:
            forward,fr,closed=trace(seed,1)
            if closed:points=forward;br='not traced: forward loop'
            else:
                backward,br,_=trace(seed,-1);points=list(reversed(backward[1:]))+forward
            lines.append(Streamline(key,tuple(points),fr,br,closed))
        return Streamlines(self.digest,tuple(lines),step,max_length,max_steps,min_speed)
