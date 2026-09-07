"""Physical oblique section planes shared by microscopy, labels and 3D figures."""
from dataclasses import dataclass
import io
import math

import inklet as i
from inklet.core import ImagePrim
from inklet.three.scene_projection import _vector
from .volume import Volume, _UNITS, _numpy, _positive


def _snapshot(array):
    np = _numpy()
    return np.frombuffer(array.tobytes(order='C'), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True)
class Plane:
    """A rectangular sampling plane; output rows run downward, columns rightward.

    Vectors are world XYZ directions. Their normalized forms must be orthogonal.
    Spacing is row/column in the declared physical unit, not source voxel indices.
    """
    centre_xyz: tuple[float, float, float]
    right_xyz: tuple[float, float, float]
    up_xyz: tuple[float, float, float]
    shape_yx: tuple[int, int]
    spacing_yx: tuple[float, float]
    unit: str

    def __post_init__(self):
        centre = _vector(self.centre_xyz)
        directions = []
        for value in (self.right_xyz, self.up_xyz):
            vector = _vector(value)
            norm = math.hypot(*vector)
            if not math.isfinite(norm) or norm == 0:
                raise ValueError('Plane directions must be finite and nonzero')
            directions.append(tuple(v / norm for v in vector))
        if abs(sum(a*b for a,b in zip(*directions))) > 1e-10:
            raise ValueError('Plane right and up directions must be orthogonal')
        shape = tuple(self.shape_yx)
        if len(shape) != 2 or any(type(n) is not int or n < 1 for n in shape):
            raise ValueError('shape_yx must contain two positive integers')
        spacing = tuple(_positive(v, 'pixel spacing') for v in self.spacing_yx)
        if len(spacing) != 2:
            raise ValueError('spacing_yx must contain two values')
        if self.unit not in _UNITS:
            raise ValueError('Plane unit must be m, mm, um or nm')
        _positive(math.prod(spacing), 'pixel area')
        object.__setattr__(self, 'centre_xyz', centre)
        object.__setattr__(self, 'right_xyz', directions[0])
        object.__setattr__(self, 'up_xyz', directions[1])
        object.__setattr__(self, 'shape_yx', shape)
        object.__setattr__(self, 'spacing_yx', spacing)
        if not all(math.isfinite(v) for p in self.corners for v in p):
            raise ValueError('Plane bounds must be finite')

    @property
    def extent(self):
        """Full pixel-edge width and height in physical units."""
        return (self.shape_yx[1]*self.spacing_yx[1], self.shape_yx[0]*self.spacing_yx[0])

    @property
    def normal_xyz(self):
        a,b = self.right_xyz,self.up_xyz
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

    def world(self, row, column):
        """Physical XYZ for a fractional output pixel index; index 0 is a centre."""
        row,column = float(row),float(column)
        if not math.isfinite(row) or not math.isfinite(column):
            raise ValueError('Pixel indices must be finite')
        u = (column-(self.shape_yx[1]-1)/2)*self.spacing_yx[1]
        v = ((self.shape_yx[0]-1)/2-row)*self.spacing_yx[0]
        return tuple(c+u*r+v*t for c,r,t in zip(self.centre_xyz,self.right_xyz,self.up_xyz))

    @property
    def corners(self):
        """Top-left, top-right, bottom-right, bottom-left physical pixel edges."""
        ny,nx = self.shape_yx
        return tuple(self.world(y,x) for y,x in ((-.5,-.5),(-.5,nx-.5),(ny-.5,nx-.5),(ny-.5,-.5)))

    def project(self, world_xyz, *, width):
        """Project an on-plane point to image-centred page mm, with +y downward."""
        width = _positive(width, 'width')
        delta = tuple(p-c for p,c in zip(_vector(world_xyz),self.centre_xyz))
        u,v,w = (sum(a*b for a,b in zip(delta,axis))
                 for axis in (self.right_xyz,self.up_xyz,self.normal_xyz))
        tolerance = min(self.spacing_yx)*1e-7+8*max(math.ulp(c) for c in self.centre_xyz)
        if abs(w) > tolerance:
            raise ValueError('Point is outside the section plane')
        if abs(u) > self.extent[0]/2+tolerance or abs(v) > self.extent[1]/2+tolerance:
            raise ValueError('Point is outside the section extent')
        return i.Vec2(u*width/self.extent[0], -v*width/self.extent[0])

    def scalebar(self, length, *, width):
        """A separate vector key in physical units; scale together with the image."""
        length,width = _positive(length,'scale-bar length'),_positive(width,'width')
        if length > self.extent[0]:
            raise ValueError('Scale bar exceeds the section width')
        bar = i.polyline([(0,0),(length*width/self.extent[0],0)], stroke='#172f32', stroke_width=.5)
        unit = 'µm' if self.unit == 'um' else self.unit
        return i.vstack([bar,i.text(f'{length:g} {unit}',size=i.pt(8))],gap=1)

    def report(self):
        return dict(schema='inklet.section-plane/0.1',centre_xyz=list(self.centre_xyz),
                    right_xyz=list(self.right_xyz),up_xyz=list(self.up_xyz),
                    normal_xyz=list(self.normal_xyz),shape_yx=list(self.shape_yx),
                    spacing_yx=list(self.spacing_yx),unit=self.unit,
                    extent=list(self.extent),corners_xyz=[list(p) for p in self.corners],
                    convention='pixel centres; rows down, columns right; zero-thickness plane')


@dataclass(frozen=True, eq=False)
class SampledSection:
    """An immutable resampled array plus an explicit source-coverage mask."""
    plane: Plane
    volume: Volume
    kind: str
    data: object
    valid: object

    def __post_init__(self):
        np = _numpy()
        if not isinstance(self.plane,Plane) or not isinstance(self.volume,Volume):
            raise ValueError('Section requires a Plane and Volume')
        if self.kind not in ('intensity','labels') or self.plane.unit != self.volume.unit:
            raise ValueError('Invalid section kind or mismatched physical units')
        data,valid = np.asarray(self.data),np.asarray(self.valid)
        if data.shape != self.plane.shape_yx or valid.shape != data.shape or valid.dtype.kind != 'b':
            raise ValueError('Section data and boolean validity must match the plane shape')
        if data.dtype.kind not in 'buif' or not np.isfinite(data).all():
            raise ValueError('Section values must be finite numeric values')
        if self.kind == 'labels' and data.dtype.kind not in 'bui':
            raise ValueError('Label sections require integer values')
        object.__setattr__(self,'data',_snapshot(data))
        object.__setattr__(self,'valid',_snapshot(valid))

    def report(self):
        return dict(schema='inklet.sampled-section/0.1',source=self.volume.report(),
                    plane=self.plane.report(),kind=self.kind,
                    interpolation='trilinear' if self.kind=='intensity' else 'nearest; half ties to upper index',
                    boundary='edge hold inside voxel edges; invalid outside source extent',
                    valid_pixels=int(self.valid.sum()),total_pixels=int(self.valid.size),
                    dtype=str(self.data.dtype))

    def measure(self, label):
        """Sampled label area, not 3D volume or a native-resolution measurement."""
        np = _numpy()
        if self.kind != 'labels' or type(label) is not int or label < 0:
            raise ValueError('Area measurements require a label section and nonnegative integer ID')
        count = int(np.count_nonzero((self.data==label)&self.valid))
        area = math.prod(self.plane.spacing_yx)
        return dict(source_id=self.volume.source_id,label=label,sampled_pixels=count,
                    area=count*area,area_unit=self.plane.unit+'^2',
                    valid_area=int(self.valid.sum())*area,estimator='nearest-label pixel-count area')

    def diagram(self, *, width, window):
        """Windowed greyscale RGBA image; out-of-volume samples are transparent."""
        np = _numpy()
        from PIL import Image
        width = _positive(width,'width')
        if len(window)!=2 or not all(math.isfinite(v) for v in window) or window[0]>=window[1]:
            raise ValueError('window must contain finite increasing intensity limits')
        grey = np.rint(np.clip((self.data.astype(float)-window[0])/(window[1]-window[0]),0,1)*255).astype('uint8')
        rgba = np.stack([grey,grey,grey,self.valid.astype('uint8')*255],axis=-1)
        buffer = io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG')
        return i.Diagram(prim=ImagePrim(source=self.volume.source_id,width=width,
            height=width*self.plane.extent[1]/self.plane.extent[0],data=buffer.getvalue(),smooth=False),
            kind='oblique-section',notes={'sampled_section':self.report()|dict(display_window=list(window),width_mm=width)})


def reslice(volume, plane, *, kind):
    """Resample a plane; labels preserve exact integer IDs, including uint64."""
    np = _numpy()
    if not isinstance(volume,Volume) or not isinstance(plane,Plane):
        raise ValueError('reslice requires a Volume and Plane')
    if volume.unit != plane.unit:
        raise ValueError('Volume and plane must use the same physical unit')
    if kind not in ('intensity','labels'):
        raise ValueError('kind must be intensity or labels')
    if kind == 'labels' and volume.data.dtype.kind not in 'bui':
        raise ValueError('Label resampling requires an integer volume')
    ny,nx = plane.shape_yx
    u = (np.arange(nx)-(nx-1)/2)*plane.spacing_yx[1]
    v = ((ny-1)/2-np.arange(ny))*plane.spacing_yx[0]
    coordinates = []
    with np.errstate(over='ignore',invalid='ignore'):
        for dim in (2,1,0):
            world = plane.centre_xyz[dim]+u[None,:]*plane.right_xyz[dim]+v[:,None]*plane.up_xyz[dim]
            coordinates.append((world-volume.origin_xyz[dim])/volume.spacing_zyx[2-dim])
    indices = np.stack(coordinates)
    shape = np.array(volume.data.shape)[:,None,None]
    valid = np.all(np.isfinite(indices)&(indices>=-.5-1e-9)&(indices<=shape-.5+1e-9),axis=0)
    safe = np.clip(np.where(valid[None,:,:],indices,0),0,shape-1)
    if kind == 'labels':
        # Direct integer indexing avoids converting large source IDs to float.
        nearest = np.floor(safe+.5).astype(np.intp)
        values = volume.data[tuple(nearest)]
    else:
        try:
            from scipy.ndimage import map_coordinates
        except ImportError as error:
            raise ImportError('Oblique intensity sections require inklet[volume]') from error
        values = map_coordinates(volume.data,safe,order=1,mode='nearest',prefilter=False,output=np.float64)
    values = np.where(valid,values,0)
    return SampledSection(plane,volume,kind,values,valid)
