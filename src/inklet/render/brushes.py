"""Validated vector paint shared by SVG, PDF and PNG."""
from dataclasses import dataclass, replace
import hashlib
import math

from ..core import Prim, RectPrim, EllipsePrim, PathPrim
from ..themes.color import parse_color, to_hex


def _point(value):
    result = tuple(float(v) for v in value)
    if len(result) != 2 or not all(math.isfinite(v) for v in result):
        raise ValueError('Gradient points require two finite coordinates')
    return result


def _stops(value):
    stops = tuple((float(offset), to_hex(parse_color(color))) for offset, color in value)
    if len(stops) < 2 or stops[0][0] != 0 or stops[-1][0] != 1:
        raise ValueError('Gradient stops must begin at 0 and end at 1')
    if any(not math.isfinite(a[0]) or a[0] >= b[0] for a,b in zip(stops, stops[1:])):
        raise ValueError('Gradient stop offsets must strictly increase')
    return stops


@dataclass(frozen=True)
class LinearGradient:
    """Opaque colour stops from start to end in fractions of the shape bounds."""
    stops: tuple
    start: tuple = (0., 0.)
    end: tuple = (1., 0.)

    def __post_init__(self):
        object.__setattr__(self,'stops',_stops(self.stops))
        object.__setattr__(self,'start',_point(self.start))
        object.__setattr__(self,'end',_point(self.end))
        if self.start == self.end: raise ValueError('Gradient endpoints must differ')


@dataclass(frozen=True)
class RadialGradient:
    """Concentric opaque gradient in shape-bound fractions; circles become ellipses on rectangular bounds."""
    stops: tuple
    center: tuple = (.5, .5)
    radius: float = .5

    def __post_init__(self):
        object.__setattr__(self,'stops',_stops(self.stops))
        object.__setattr__(self,'center',_point(self.center))
        if not math.isfinite(self.radius) or self.radius <= 0: raise ValueError('Gradient radius must be positive')


@dataclass(frozen=True)
class Hatch:
    """Parallel vector strokes with spacing/width in local millimetres."""
    color: str = '#666666'
    spacing: float = 2.
    stroke: float = .2
    angle: float = 45.
    background: str | None = None

    def __post_init__(self):
        object.__setattr__(self,'color',to_hex(parse_color(self.color)))
        if self.background is not None: object.__setattr__(self,'background',to_hex(parse_color(self.background)))
        if not all(math.isfinite(v) and v > 0 for v in (self.spacing,self.stroke)):
            raise ValueError('Hatch spacing and stroke must be positive')
        if not math.isfinite(self.angle): raise ValueError('Hatch angle must be finite')


@dataclass(frozen=True)
class PaintedPrim(Prim):
    shape: Prim
    brush: LinearGradient | RadialGradient | Hatch

    def envelope(self): return self.shape.envelope()
    def trace(self): return self.shape.trace()


def paint(node, brush):
    """Fill a shape or shape group with a vector gradient or hatch; retain text and authored strokes."""
    if not isinstance(brush,(LinearGradient,RadialGradient,Hatch)):
        raise TypeError('brush must be LinearGradient, RadialGradient or Hatch')
    count=0
    def visit(part):
        nonlocal count
        prim=part.prim
        if isinstance(prim,PaintedPrim): prim=prim.shape
        if isinstance(prim,(RectPrim,EllipsePrim)) or isinstance(prim,PathPrim) and prim.filled:
            prim=PaintedPrim(prim,brush); count+=1
        return replace(part,prim=prim,children=tuple(visit(c) for c in part.children),_cache={})
    result=visit(node)
    if not count: raise ValueError('paint needs at least one filled shape')
    return result


def svg_brush(brush,w):
    key='inklet-paint-'+hashlib.sha256(repr(brush).encode()).hexdigest()[:20]
    registry=getattr(w,'paint_defs',None)
    if registry is None: registry=w.paint_defs=set()
    if key in registry: return key
    registry.add(key)
    w.open('defs',[])
    if isinstance(brush,Hatch):
        tag='pattern'
        w.open(tag,[('id',key),('patternUnits','userSpaceOnUse'),('width',w.n(brush.spacing)),
                    ('height',w.n(brush.spacing)),('patternTransform',f'rotate({w.n(brush.angle)})'),
                    ('stroke','none'),('fill','none')])
        if brush.background:
            w.empty('rect',[('width',w.n(brush.spacing)),('height',w.n(brush.spacing)),('fill',brush.background)])
        # Two boundary halves form one stroke without extending outside the tile.
        w.empty('path',[('d',f'M0 0H{w.n(brush.spacing)}M0 {w.n(brush.spacing)}H{w.n(brush.spacing)}'),
                        ('stroke',brush.color),('stroke-width',w.n(brush.stroke)),('fill','none')])
    else:
        if isinstance(brush,LinearGradient):
            tag='linearGradient'; attrs=list(zip(('x1','y1','x2','y2'),map(w.n,(*brush.start,*brush.end))))
        else:
            tag='radialGradient'; attrs=list(zip(('cx','cy','r'),map(w.n,(*brush.center,brush.radius))))
        w.open(tag,[('id',key),('color-interpolation','sRGB'),*attrs])
        for offset,color in brush.stops: w.empty('stop',[('offset',w.n(offset)),('stop-color',color)])
    w.close(tag);w.close('defs')
    return key


def pdf_shading(brush):
    """A PDF shading dictionary with a stitched colour interpolation function."""
    def rgb(color): return ' '.join(f'{c/255:.8f}' for c in parse_color(color))
    functions=[f'<< /FunctionType 2 /Domain [0 1] /C0 [{rgb(a[1])}] /C1 [{rgb(b[1])}] /N 1 >>'
               for a,b in zip(brush.stops,brush.stops[1:])]
    function=(functions[0] if len(functions)==1 else
              f'<< /FunctionType 3 /Domain [0 1] /Functions [{" ".join(functions)}] '
              f'/Bounds [{" ".join(str(s[0]) for s in brush.stops[1:-1])}] '
              f'/Encode [{"0 1 "*len(functions)}] >>')
    if isinstance(brush,LinearGradient): kind,coords=2,(*brush.start,*brush.end)
    else: kind,coords=3,(*brush.center,0,*brush.center,brush.radius)
    return (f'<< /ShadingType {kind} /ColorSpace /DeviceRGB /Coords [{" ".join(map(str,coords))}] '
            f'/Function {function} /Extend [true true] >>')
