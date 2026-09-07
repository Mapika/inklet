"""Streaming physical slab projections with explicit per-pixel coverage."""
from dataclasses import dataclass, replace
import math

from .volume import Volume, _numpy, _positive
from .sections import Plane, SampledSection, _snapshot
from .regions import BoxRegion


@dataclass(frozen=True)
class Slab:
    """A finite thickness about a Plane, sampled at equal-width bin midpoints.

    Thickness and offsets use the plane's physical unit. Increasing samples
    improves the numerical approximation, not the source acquisition resolution.
    """
    plane: Plane
    thickness: float
    samples: int

    def __post_init__(self):
        if not isinstance(self.plane,Plane):
            raise ValueError('Slab requires a Plane')
        object.__setattr__(self,'thickness',_positive(self.thickness,'slab thickness'))
        if type(self.samples) is not int or not 1<=self.samples<=2**63-1:
            raise ValueError('Slab samples must be a positive 64-bit integer')
        _positive(self.thickness/self.samples,'slab sampling step')
        # Validate both physical faces before sampling begins.
        self.face(-self.thickness/2)
        self.face(self.thickness/2)

    def face(self, offset):
        """A parallel plane at a signed physical distance along the normal."""
        offset=float(offset)
        if not math.isfinite(offset):raise ValueError('Slab offset must be finite')
        return replace(self.plane,centre_xyz=tuple(c+offset*n for c,n in
                       zip(self.plane.centre_xyz,self.plane.normal_xyz)))

    def report(self):
        return dict(schema='inklet.slab/0.1',plane=self.plane.report(),thickness=self.thickness,
                    samples=self.samples,step=self.thickness/self.samples,
                    sampling='equal-width bin midpoints along plane normal',
                    first_offset=self.thickness*(.5/self.samples-.5),
                    last_offset=self.thickness*((self.samples-.5)/self.samples-.5))


@dataclass(frozen=True, eq=False)
class SlabProjection:
    """Immutable intensity projection and count of contributing samples at each pixel."""
    slab: Slab
    volume: Volume
    reduction: str
    data: object
    counts: object
    region: BoxRegion | None = None

    def __post_init__(self):
        np = _numpy()
        _validate(self.volume,self.slab,self.reduction,self.region)
        data,counts = np.asarray(self.data),np.asarray(self.counts)
        if data.shape!=self.slab.plane.shape_yx or counts.shape!=data.shape:
            raise ValueError('Projection arrays must match the plane shape')
        if data.dtype.kind not in 'buif' or not np.isfinite(data).all():
            raise ValueError('Projection values must be finite numeric values')
        if counts.dtype.kind not in 'ui' or np.any(counts<0) or np.any(counts>self.slab.samples):
            raise ValueError('Projection counts must be integers between zero and samples')
        object.__setattr__(self,'data',_snapshot(np.where(counts>0,data,0)))
        object.__setattr__(self,'counts',_snapshot(counts))

    @property
    def valid(self):
        return _snapshot(self.counts>0)

    @property
    def coverage(self):
        """Contributing sample fraction, including both source and optional ROI limits."""
        return _snapshot(self.counts/self.slab.samples)

    def report(self):
        np = _numpy()
        count_values,frequencies = np.unique(self.counts,return_counts=True)
        return dict(schema='inklet.slab-projection/0.1',source=self.volume.report(),slab=self.slab.report(),
                    reduction=self.reduction,interpolation='trilinear intensity',
                    boundary='edge hold inside source voxel edges; outside source or region excluded',
                    normalization='mean divides by contributing samples; no zero padding',
                    selection=self.region.report() if self.region else None,
                    valid_pixels=int(np.count_nonzero(self.counts)),total_pixels=int(self.counts.size),
                    complete_pixels=int(np.count_nonzero(self.counts==self.slab.samples)),
                    count_histogram=[dict(count=int(c),pixels=int(n)) for c,n in zip(count_values,frequencies)])

    def diagram(self, *, width, window):
        """Windowed image; pixels with no contributing samples are transparent."""
        section=SampledSection(self.slab.plane,self.volume,'intensity',self.data,self.valid)
        diagram=section.diagram(width=width,window=window)
        return replace(diagram,kind='slab-projection',notes={'slab_projection':
                       self.report()|dict(display_window=list(window),width_mm=float(width))})


def _validate(volume,slab,reduction,region):
    if not isinstance(volume,Volume) or not isinstance(slab,Slab):
        raise ValueError('project_slab requires a Volume and Slab')
    if volume.unit!=slab.plane.unit:
        raise ValueError('Volume and slab must use the same physical unit')
    if reduction not in ('mean','max','min'):
        raise ValueError('Intensity reduction must be mean, max or min; label IDs are not projected')
    if region is not None and (not isinstance(region,BoxRegion) or region.unit!=volume.unit):
        raise ValueError('Region must be a BoxRegion with matching physical units')


def project_slab(volume, slab, *, reduction, region=None):
    """Reduce intensity samples with O(output pixels) working memory.

    Integer input is interpreted as intensity, never as categorical label IDs.
    Use BoxRegion.measure for exact source-label measurements instead.
    """
    _validate(volume,slab,reduction,region)
    np = _numpy()
    data=np.zeros(slab.plane.shape_yx,dtype=np.float64)
    counts=np.zeros(slab.plane.shape_yx,dtype=np.int64)
    for index in range(slab.samples):
        plane=slab.face(slab.thickness*((index+.5)/slab.samples-.5))
        section=volume.reslice(plane,kind='intensity')
        valid=section.valid if region is None else section.valid & region.mask(plane)
        first=valid & (counts==0)
        counts[valid]+=1
        if reduction=='mean':
            n=counts[valid]
            # Weighted terms avoid overflowing the sum or a difference of extremes.
            data[valid]=data[valid]*((n-1)/n)+section.data[valid]/n
        else:
            data[first]=section.data[first]
            operation=np.maximum if reduction=='max' else np.minimum
            data[valid]=operation(data[valid],section.data[valid])
    return SlabProjection(slab,volume,reduction,data,counts,region)
