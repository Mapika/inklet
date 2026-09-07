"""Physical box selections shared by sections, projections and source measurements."""
from dataclasses import dataclass
import itertools
import math

import inklet as i
from inklet.three.scene_projection import _vector
from .volume import Volume, _UNITS, _numpy, _positive
from .sections import Plane, _snapshot


@dataclass(frozen=True)
class BoxRegion:
    """An axis-aligned world XYZ box with a stable, caller-assigned identity.

    Membership is lower-inclusive and upper-exclusive. Measurements select
    source voxel centres, without resampling or inferring biological instances.
    """
    selection_id: str
    lower_xyz: tuple[float, float, float]
    upper_xyz: tuple[float, float, float]
    unit: str

    def __post_init__(self):
        if not isinstance(self.selection_id,str) or not self.selection_id.strip():
            raise ValueError('A nonempty selection_id is required')
        lower,upper = _vector(self.lower_xyz),_vector(self.upper_xyz)
        if self.unit not in _UNITS:
            raise ValueError('Region unit must be m, mm, um or nm')
        for a,b in zip(lower,upper):
            _positive(b-a,'region extent')
        _positive(math.prod(b-a for a,b in zip(lower,upper)),'region volume')
        object.__setattr__(self,'lower_xyz',lower)
        object.__setattr__(self,'upper_xyz',upper)

    @property
    def edges(self):
        """Twelve world-space edge pairs for a linked 3D outline."""
        corners = list(itertools.product(*zip(self.lower_xyz,self.upper_xyz)))
        return tuple((a,b) for a,b in itertools.combinations(corners,2)
                     if sum(x!=y for x,y in zip(a,b))==1)

    def report(self):
        return dict(schema='inklet.box-region/0.1',selection_id=self.selection_id,
                    lower_xyz=list(self.lower_xyz),upper_xyz=list(self.upper_xyz),unit=self.unit,
                    membership='voxel or sample centres; lower inclusive, upper exclusive')

    def mask(self, plane):
        """Immutable YX membership of section pixel centres, independent of source coverage."""
        np = _numpy()
        if not isinstance(plane,Plane) or plane.unit != self.unit:
            raise ValueError('Region and Plane must use the same physical unit')
        ny,nx = plane.shape_yx
        u = (np.arange(nx)-(nx-1)/2)*plane.spacing_yx[1]
        v = ((ny-1)/2-np.arange(ny))*plane.spacing_yx[0]
        mask = np.ones((ny,nx),dtype=bool)
        for dim,(lower,upper) in enumerate(zip(self.lower_xyz,self.upper_xyz)):
            world = plane.centre_xyz[dim]+u[None,:]*plane.right_xyz[dim]+v[:,None]*plane.up_xyz[dim]
            mask &= (world>=lower)&(world<upper)
        return _snapshot(mask)

    def intersection(self, plane):
        """World XYZ polygon of box/plane intersection, clipped to the image extent.

        This draws the geometric boundary; membership on upper faces remains
        exclusive. A disjoint box produces an empty tuple.
        """
        if not isinstance(plane,Plane) or plane.unit != self.unit:
            raise ValueError('Region and Plane must use the same physical unit')
        points = list(plane.corners)
        for dim in range(3):
            for bound,sign in ((self.lower_xyz[dim],1),(self.upper_xyz[dim],-1)):
                if not points:return ()
                clipped=[]
                for a,b in zip(points,points[1:]+points[:1]):
                    da,db = sign*(a[dim]-bound),sign*(b[dim]-bound)
                    if da>=0:clipped.append(a)
                    if (da<0)!=(db<0):
                        t=da/(da-db)
                        clipped.append(tuple(x+t*(y-x) for x,y in zip(a,b)))
                points=clipped
        # Clipping exactly through a corner can emit repeated vertices.
        unique=[]
        for p in points:
            if p not in unique:unique.append(p)
        return tuple(unique)

    def outline(self, plane, *, width, **style):
        """Vector outline in the same image-centred page coordinates as Plane.project."""
        width = _positive(width,'width')
        points = self.intersection(plane)
        backing = i.box(width=width,height=width*plane.extent[1]/plane.extent[0],
                        pad=0,radius=0,fill='none',stroke='none')
        if len(points)>=2:
            projected = [plane.project(p,width=width) for p in (*points,points[0])]
            line = i.polyline([(p.x,p.y) for p in projected],**style)
            backing = i.overlay([backing,line],align='origin')
        backing.notes['selection'] = self.report()
        return backing

    def measure(self, volume, *, label):
        """Count an exact integer label within the box on the supplied source grid."""
        np = _numpy()
        if not isinstance(volume,Volume) or volume.unit != self.unit:
            raise ValueError('Region and Volume must use the same physical unit')
        if volume.data.dtype.kind not in 'bui' or type(label) is not int or label<0:
            raise ValueError('Measurements require integer labels and a nonnegative integer ID')
        slices=[]
        for dim in (2,1,0):
            coordinates = volume.origin_xyz[dim]+np.arange(volume.data.shape[2-dim])*volume.spacing_zyx[2-dim]
            start,stop = np.searchsorted(coordinates,[self.lower_xyz[dim],self.upper_xyz[dim]],side='left')
            slices.append(slice(int(start),int(stop)))
        selected = volume.data[tuple(slices)]
        count = int(np.count_nonzero(selected==label))
        voxel_volume = math.prod(volume.spacing_zyx)
        return dict(schema='inklet.region-measurement/0.1',selection=self.report(),source=volume.report(),
                    label=label,voxel_count=count,volume=count*voxel_volume,volume_unit=self.unit+'^3',
                    available_voxel_count=int(selected.size),available_grid_volume=int(selected.size)*voxel_volume,
                    estimator='source voxel-centre selection; full voxel volumes; supplied grid only')
