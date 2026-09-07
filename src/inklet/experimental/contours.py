"""Exact sampled-label pixel-edge boundaries, separated from coverage limits."""
from dataclasses import dataclass, field
import math

import inklet as i
from inklet.core import PathPrim, Subpath, Vec2
from .sections import SampledSection
from .volume import _numpy, _positive


def _runs(edges, *, vertical):
    """Merge collinear unit pixel edges without diagonal interpolation or smoothing."""
    np=_numpy();result=[]
    if vertical:edges=edges.T
    for row,line in enumerate(edges):
        changes=np.diff(np.pad(line.astype(np.int8),(1,1)))
        for start,stop in zip(np.flatnonzero(changes==1),np.flatnonzero(changes==-1)):
            a,b=(row-.5,int(start)-.5),(row-.5,int(stop)-.5)
            if vertical:a,b=a[::-1],b[::-1]
            result.append((a,b))
    return tuple(result)


@dataclass(frozen=True, eq=False)
class LabelContour:
    """Boundary segments of one exact label ID on a sampled section grid.

    Observed edges separate two valid pixels. Coverage edges abut invalid
    samples or the image extent and are never silently treated as background.
    Holes and disconnected components are retained without joining diagonals.
    """
    section: SampledSection
    label: int
    observed_yx: tuple = field(init=False)
    coverage_yx: tuple = field(init=False)

    def __post_init__(self):
        if not isinstance(self.section,SampledSection) or self.section.kind!='labels':
            raise ValueError('Contours require a label SampledSection')
        if type(self.label) is not int or self.label<0:
            raise ValueError('Contour label must be a nonnegative integer ID')
        np=_numpy()
        selected=(self.section.data==self.label)&self.section.valid
        foreground=np.pad(selected,1)
        valid=np.pad(self.section.valid,1)
        observed=[];coverage=[]
        for vertical in (False,True):
            if vertical:
                a,b=foreground[1:-1,:-1],foreground[1:-1,1:]
                va,vb=valid[1:-1,:-1],valid[1:-1,1:]
            else:
                a,b=foreground[:-1,1:-1],foreground[1:,1:-1]
                va,vb=valid[:-1,1:-1],valid[1:,1:-1]
            different=a^b
            observed.extend(_runs(different&va&vb,vertical=vertical))
            coverage.extend(_runs(different&~(va&vb),vertical=vertical))
        object.__setattr__(self,'observed_yx',tuple(observed))
        object.__setattr__(self,'coverage_yx',tuple(coverage))

    def report(self):
        dy,dx=self.section.plane.spacing_yx
        def length(edges):
            return sum(math.hypot((b[0]-a[0])*dy,(b[1]-a[1])*dx) for a,b in edges)
        return dict(schema='inklet.label-contour/0.1',section=self.section.report(),label=self.label,
                    observed_segments=len(self.observed_yx),coverage_segments=len(self.coverage_yx),
                    observed_length=length(self.observed_yx),coverage_length=length(self.coverage_yx),
                    length_unit=self.section.plane.unit,area=self.section.measure(self.label),
                    estimator='sampled pixel-edge boundary; no smoothing or diagonal interpolation',
                    boundary='observed: both samples valid; coverage: invalid neighbour or image extent')

    def world_segments(self, *, include_coverage=False):
        """Physical XYZ edge pairs for use with saved-camera vector paths."""
        if type(include_coverage) is not bool:raise ValueError('include_coverage must be boolean')
        edges=self.observed_yx+(self.coverage_yx if include_coverage else ())
        return tuple((self.section.plane.world(*a),self.section.plane.world(*b)) for a,b in edges)

    def diagram(self, *, width, stroke, stroke_width=.25, coverage='omit'):
        """Vector boundaries aligned with the section image; coverage edges are explicit."""
        width=_positive(width,'width');stroke_width=_positive(stroke_width,'stroke width')
        if coverage not in ('omit','dash','show'):
            raise ValueError('Contour coverage must be omit, dash or show')
        plane=self.section.plane;ny,nx=plane.shape_yx
        scale=width/plane.extent[0]
        def point(yx):
            row,column=yx
            return Vec2((column-(nx-1)/2)*plane.spacing_yx[1]*scale,
                        (row-(ny-1)/2)*plane.spacing_yx[0]*scale)
        layers=[i.box(width=width,height=width*plane.extent[1]/plane.extent[0],pad=0,radius=0,fill='none',stroke='none')]
        for name,edges in [('observed',self.observed_yx),('coverage',self.coverage_yx)]:
            if not edges or (name=='coverage' and coverage=='omit'):continue
            subs=tuple(Subpath((point(a),point(b)),False) for a,b in edges)
            diagram=i.Diagram(prim=PathPrim(subs,filled=False),kind='label-contour').styled(
                stroke=stroke,stroke_width=stroke_width,fill='none',
                stroke_dash=(1,1) if name=='coverage' and coverage=='dash' else None)
            layers.append(diagram)
        return i.overlay(layers,align='origin').note('label_contour',self.report()|dict(
            coverage_display=coverage,width_mm=width,stroke=stroke,stroke_width_mm=stroke_width))
