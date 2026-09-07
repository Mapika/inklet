"""Calibrated scalar volumes for microscopy figures (experimental).

Arrays are Z,Y,X. World coordinates are X,Y,Z in an explicit physical unit.
The origin is the centre of voxel [0,0,0]; voxel edges extend half a spacing
beyond the first and last centres. Optional dependencies load only when used.
"""
from dataclasses import dataclass
import io
import math

import inklet as i
from inklet.core import ImagePrim
from inklet.three.scene_projection import _vector

_UNITS = {'m':1., 'mm':1e-3, 'um':1e-6, 'nm':1e-9}


def _numpy():
    try:
        import numpy as np
    except ImportError as error:
        raise ImportError('Calibrated volumes require inklet[volume]') from error
    return np


def _positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name+' must be finite and positive')
    return value


@dataclass(frozen=True, eq=False)
class Volume:
    """An immutable scalar snapshot with explicit voxel calibration and identity."""
    data: object
    spacing_zyx: tuple[float,float,float]
    unit: str
    origin_xyz: tuple[float,float,float] = (0.,0.,0.)
    source_id: str = ''

    def __post_init__(self):
        np = _numpy()
        array = np.asarray(self.data)
        if array.ndim != 3 or not all(array.shape) or array.dtype.kind not in 'buif':
            raise ValueError('Volume data must be a non-empty, real numeric Z,Y,X array')
        if not np.isfinite(array).all():
            raise ValueError('Volume data must be finite; supply an explicit missing-data policy first')
        spacing = tuple(_positive(v,'voxel spacing') for v in self.spacing_zyx)
        if len(spacing) != 3:
            raise ValueError('spacing_zyx must contain three values')
        if self.unit not in _UNITS:
            raise ValueError('Volume unit must be m, mm, um or nm')
        if not isinstance(self.source_id,str) or not self.source_id.strip():
            raise ValueError('source_id must identify the volume source')
        origin=_vector(self.origin_xyz)
        _positive(math.prod(spacing),'voxel volume')
        if any(not math.isfinite(o+d*(n-.5)) or not math.isfinite(o-d/2)
               for o,d,n in zip(origin,spacing[::-1],array.shape[::-1])):
            raise ValueError('Calibrated volume bounds must be finite')
        # An immutable bytes owner also prevents callers re-enabling writes.
        snapshot = np.frombuffer(array.tobytes(order='C'),dtype=array.dtype).reshape(array.shape)
        object.__setattr__(self,'data',snapshot)
        object.__setattr__(self,'spacing_zyx',spacing)
        object.__setattr__(self,'origin_xyz',origin)

    def world(self, index_zyx):
        """Convert a finite fractional voxel index to a physical X,Y,Z position."""
        index = _vector(index_zyx)
        return tuple(self.origin_xyz[k]+index[2-k]*self.spacing_zyx[2-k] for k in range(3))

    def report(self):
        return dict(schema='inklet.volume/0.1',source_id=self.source_id,
            shape_zyx=list(self.data.shape),spacing_zyx=list(self.spacing_zyx),unit=self.unit,metres_per_unit=_UNITS[self.unit],
            origin_xyz=list(self.origin_xyz),origin_convention='centre of voxel [0,0,0]',
            bounds_xyz=[list(self.world((-.5,)*3)),list(self.world(tuple(n-.5 for n in self.data.shape)))])

    def slice(self, axis, index):
        """An axis-aligned physical section, with the second axis pointing up."""
        if axis not in ('x','y','z'):
            raise ValueError('Slice axis must be x, y or z')
        dim = 'zyx'.index(axis)
        if type(index) is not int or not 0 <= index < self.data.shape[dim]:
            raise ValueError('Slice index must be an integer inside the volume')
        return Slice(self,axis,index)

    def crop(self, start_zyx, stop_zyx):
        """Half-open voxel bounds; preserve the original physical coordinate frame."""
        start,stop=tuple(start_zyx),tuple(stop_zyx)
        if len(start)!=3 or len(stop)!=3 or any(type(v) is not int for v in start+stop):
            raise ValueError('Crop bounds must contain three integer voxel indices')
        if any(not 0 <= a < b <= n for a,b,n in zip(start,stop,self.data.shape)):
            raise ValueError('Crop bounds must define a non-empty region inside the volume')
        return Volume(self.data[tuple(slice(a,b) for a,b in zip(start,stop))],
                      self.spacing_zyx,self.unit,self.world(start),self.source_id)

    def reslice(self, plane, *, kind):
        """Sample an explicit physical plane: linear intensities or nearest labels."""
        from .sections import reslice
        return reslice(self, plane, kind=kind)

    def project_slab(self, slab, *, reduction, region=None):
        """Project physical intensity samples, optionally restricted to a shared region."""
        from .slabs import project_slab
        return project_slab(self, slab, reduction=reduction, region=region)

    def measure(self, label):
        """Voxel-count volume, centroid and boundary status of one integer label.

        Disconnected voxels with the same ID remain one label. This is not an
        instance detector or a claim that a source segmentation is correct.
        """
        np = _numpy()
        if self.data.dtype.kind not in 'bui' or type(label) is not int or label <= 0:
            raise ValueError('Measurements require integer labels and a positive integer label ID')
        mask = self.data == label
        count = int(np.count_nonzero(mask))
        if not count:
            raise ValueError('Label is absent from the volume')
        coords = np.nonzero(mask)
        centroid = self.world(tuple(float(c.mean()) for c in coords))
        touches = any(bool(np.any(c==0) or np.any(c==n-1)) for c,n in zip(coords,self.data.shape))
        return dict(source_id=self.source_id,label=label,voxel_count=count,
            volume=count*math.prod(self.spacing_zyx),volume_unit=self.unit+'^3',
            centroid_xyz=list(centroid),touches_boundary=touches)

    def surface(self, label, *, allow_clipped=False, step_size=1):
        """Marching-cubes surface of one label, in calibrated world coordinates.

        A one-voxel background pad closes voxel-edge surfaces. Boundary-touching
        labels require allow_clipped=True: their resulting caps are artificial.
        Display subsampling never changes measure(), which uses every voxel.
        """
        np = _numpy()
        if type(allow_clipped) is not bool or type(step_size) is not int or step_size < 1:
            raise ValueError('allow_clipped must be boolean and step_size a positive integer')
        measured = self.measure(label)
        if measured['touches_boundary'] and not allow_clipped:
            raise ValueError('Label touches the volume boundary; allow_clipped=True explicitly permits artificial caps')
        try:
            from skimage.measure import marching_cubes
        except ImportError as error:
            raise ImportError('Surface extraction requires inklet[volume]') from error
        # Include background at both ends of every sampled axis even for a
        # coarse display stride; otherwise the last sampled plane can be solid.
        padding = [(1,1+(-(n+1) % step_size)) for n in self.data.shape]
        mask = np.pad(self.data == label,padding).astype(np.uint8)
        vertices,faces,_,_ = marching_cubes(mask,level=.5,spacing=self.spacing_zyx,
            step_size=step_size,allow_degenerate=False,gradient_direction='descent')
        # Descent-mode faces retain outward winding after the ZYX -> XYZ conversion.
        vertices = vertices[:,::-1]-np.array(self.spacing_zyx[::-1])+self.origin_xyz
        return i.Mesh(tuple(i.Vec3(*v) for v in vertices),
                      tuple(tuple(int(v) for v in f) for f in faces),
                      name=f'{self.source_id}:label={label}')


@dataclass(frozen=True)
class Slice:
    volume: Volume
    axis: str
    index: int

    def __post_init__(self):
        if not isinstance(self.volume,Volume) or self.axis not in ('x','y','z'):
            raise ValueError('Slice requires a Volume and an x, y or z axis')
        if type(self.index) is not int or not 0 <= self.index < self.volume.data.shape['zyx'.index(self.axis)]:
            raise ValueError('Slice index must be an integer inside the volume')

    @property
    def axes(self):
        return {'z':('x','y'),'y':('x','z'),'x':('y','z')}[self.axis]

    @property
    def extent(self):
        return tuple(self.volume.data.shape['zyx'.index(a)]*self.volume.spacing_zyx['zyx'.index(a)] for a in self.axes)

    def project(self, world_xyz, *, width):
        """Image-centred mm (+y down); accepts points in this voxel slab only."""
        width = _positive(width,'width')
        world = _vector(world_xyz)
        normal = 'xyz'.index(self.axis)
        spacing = self.volume.spacing_zyx[2-normal]
        centre = self.volume.origin_xyz[normal]+self.index*spacing
        tolerance=spacing*1e-9+4*math.ulp(centre)
        if abs(world[normal]-centre) > spacing/2+tolerance:
            raise ValueError('Point is outside this slice slab')
        points=[]
        for a,extent in zip(self.axes,self.extent):
            dim='xyz'.index(a)
            start=self.volume.origin_xyz[dim]-self.volume.spacing_zyx[2-dim]/2
            value=world[dim]-start
            tolerance=self.volume.spacing_zyx[2-dim]*1e-9+4*math.ulp(start)
            if not -tolerance <= value <= extent+tolerance:
                raise ValueError('Point is outside this slice extent')
            points.append((value-extent/2)*width/self.extent[0])
        return i.Vec2(points[0],-points[1])

    def diagram(self, *, width, window):
        """A greyscale slice with an explicit shared display window and no resampling."""
        np = _numpy()
        from PIL import Image
        width = _positive(width,'width')
        if len(window) != 2 or not all(math.isfinite(v) for v in window) or window[0]>=window[1]:
            raise ValueError('window must contain finite increasing intensity limits')
        values = np.take(self.volume.data,self.index,axis='zyx'.index(self.axis))
        pixels = np.flipud(np.rint(np.clip((values.astype(float)-window[0])/(window[1]-window[0]),0,1)*255).astype(np.uint8))
        buffer=io.BytesIO();Image.fromarray(pixels).save(buffer,format='PNG')
        report=self.volume.report()|dict(axis=self.axis,index=self.index,display_axes=list(self.axes),
            display_window=list(window),width_mm=width,extent=list(self.extent))
        return i.Diagram(prim=ImagePrim(source=self.volume.source_id,width=width,
            height=width*self.extent[1]/self.extent[0],data=buffer.getvalue(),smooth=False),
            kind='microscopy-slice',notes={'calibrated_slice':report})

    def scalebar(self, length, *, width):
        """A separate vector key; place beside the image without further scaling."""
        length,width = _positive(length,'scale-bar length'),_positive(width,'width')
        if length > self.extent[0]:
            raise ValueError('Scale bar exceeds the slice width')
        mm = length*width/self.extent[0]
        bar=i.polyline([(0,0),(mm,0)],stroke='#172f32',stroke_width=.5)
        label=f'{length:g} '+('µm' if self.volume.unit=='um' else self.volume.unit)
        return i.vstack([bar,i.text(label,size=i.pt(8))],gap=1)
