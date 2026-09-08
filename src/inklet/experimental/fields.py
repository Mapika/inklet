"""Immutable triangle geometry with supplied, piecewise-constant face fields."""
from dataclasses import dataclass
import hashlib
import json
import math

from .selection import KeyedTable
from ..three.mesh import Mesh
from ..three.linalg import Vec3


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _area(a, b, c):
    cross = (b-a).cross(c-a)
    return math.hypot(cross.x,cross.y,cross.z)/2


@dataclass(frozen=True)
class MeshField:
    """One explicit ID, scalar and optional XYZ vector per triangular face.

    Geometry uses the declared length unit. Scalars and vectors are supplied
    values, not interpolated vertex data or results of a simulation solver.
    Missing scalars/vectors use None; a zero vector is a measured zero.
    """
    vertices: tuple
    faces: tuple
    ids: tuple
    scalars: tuple
    vectors: tuple
    unit: str = 'mm'
    scalar_unit: str = 'a.u.'
    vector_unit: str = 'a.u.'

    def __post_init__(self):
        for name in ('vertices', 'faces', 'ids', 'scalars', 'vectors'):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple)):
                raise ValueError(f'{name} must be an array')
        if not 3 <= len(self.vertices) <= 12288:
            raise ValueError('provide 3–12,288 vertices')
        vertices = []
        for point in self.vertices:
            if not isinstance(point, (list, tuple)) or len(point) != 3 or not all(map(_finite, point)):
                raise ValueError('vertices need three finite coordinates')
            vertices.append(tuple(point))
        faces = []
        for face in self.faces:
            if (not isinstance(face, (list, tuple)) or len(face) != 3 or
                    any(type(n) is not int or not 0 <= n < len(vertices) for n in face)):
                raise ValueError('faces need three valid integer vertex indices')
            a, b, c = (Vec3(*vertices[n]) for n in face)
            area = _area(a,b,c)
            if not math.isfinite(area) or area <= 0:
                raise ValueError('face area must be positive and representable')
            faces.append(tuple(face))
        count = len(faces)
        if not count or count > 4096 or any(len(getattr(self, n)) != count for n in ('ids','scalars','vectors')):
            raise ValueError('provide 1–4096 faces with matching IDs, scalars and vectors')
        if any(not isinstance(k, str) or not k for k in self.ids) or len(set(self.ids)) != count:
            raise ValueError('face IDs must be unique nonempty strings')
        if any(v is not None and not _finite(v) for v in self.scalars):
            raise ValueError('scalars must be finite numbers or None')
        vectors = []
        for value in self.vectors:
            if value is not None:
                if not isinstance(value, (list, tuple)) or len(value) != 3 or not all(map(_finite, value)):
                    raise ValueError('vectors need three finite components or None')
                if not math.isfinite(math.hypot(*value)):
                    raise ValueError('vector magnitude must be representable')
                value = tuple(value)
            vectors.append(value)
        if self.unit not in ('m','mm','um','nm'):
            raise ValueError('geometry unit must be m, mm, um or nm')
        if any(not isinstance(u,str) or not u.strip() for u in (self.scalar_unit,self.vector_unit)):
            raise ValueError('field units must be nonempty strings')
        for name, value in [('vertices',vertices),('faces',faces),('ids',self.ids),
                            ('scalars',self.scalars),('vectors',vectors)]:
            object.__setattr__(self,name,tuple(value))
        self.table()  # Validate derived values and the portable numeric contract.

    @classmethod
    def from_dict(cls, source):
        return cls(**{name:source[name] for name in
            ('vertices','faces','ids','scalars','vectors','unit','scalar_unit','vector_unit')})

    @classmethod
    def from_mesh(cls, mesh, *, ids, scalars, vectors, unit='mm',
                  scalar_unit='a.u.', vector_unit='a.u.'):
        """Attach explicit face-order IDs/values to a native or imported mesh.

        Groups are not inferred as identity: a group may contain many faces.
        Establish correspondence after any import triangulation or repair.
        """
        if not isinstance(mesh,Mesh): raise ValueError('mesh must be an Inklet Mesh')
        return cls([(p.x,p.y,p.z) for p in mesh.vertices],list(mesh.faces),
                   ids,scalars,vectors,unit,scalar_unit,vector_unit)

    def source(self):
        return {name:getattr(self,name) for name in
            ('vertices','faces','ids','scalars','vectors','unit','scalar_unit','vector_unit')}

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.source(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def mesh(self):
        return Mesh(tuple(Vec3(*p) for p in self.vertices),self.faces,self.ids)

    def table(self, name='mesh-faces'):
        columns = dict(id=self.ids,scalar=self.scalars,magnitude=[],x=[],y=[],z=[],area=[])
        for face, vector in zip(self.faces,self.vectors):
            points = [self.vertices[n] for n in face]
            for axis, key in enumerate(('x','y','z')):
                columns[key].append(math.fsum(p[axis]/3 for p in points))
            a,b,c = (Vec3(*p) for p in points)
            columns['area'].append(_area(a,b,c))
            columns['magnitude'].append(None if vector is None else math.hypot(*vector))
        return KeyedTable(name,columns)

    def validate_table(self, table):
        expected = self.table(table.name)
        if set(table.row_ids) != set(self.ids):
            raise ValueError('mesh/table ID mismatch')
        positions = {key:n for n,key in enumerate(expected.row_ids)}
        for name, values in expected.columns.items():
            if name not in table.columns:
                raise ValueError(f'missing mesh measurement column: {name}')
            for n,key in enumerate(table.row_ids):
                a,b = table.columns[name][n],values[positions[key]]
                if type(a) is not type(b) or a != b:
                    raise ValueError(f'mesh measurement mismatch: {key}, {name}')
