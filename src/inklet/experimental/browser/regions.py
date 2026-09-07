"""Immutable GeoJSON polygon input for the bounded offline map preview."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


def _sequence(value, label):
    if not isinstance(value,(list,tuple)) or not value:
        raise ValueError(f'{label} must be a nonempty array')
    return value


def _ring(value):
    points=[]
    for position in _sequence(value,'linear ring'):
        if (not isinstance(position,(list,tuple)) or len(position)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in position)):
            raise ValueError('positions need two finite longitude/latitude numbers')
        lon,lat=position
        if not -180<=lon<=180 or not -90<=lat<=90:
            raise ValueError('longitude/latitude is outside the supported degree range')
        points.append((lon,lat))
    if len(points)<4 or points[0]!=points[-1]:
        raise ValueError('linear rings need at least four positions and explicit closure')
    if len(set(points[:-1]))<3: raise ValueError('linear ring needs three distinct vertices')
    if any(abs(b[0]-a[0])>180 for a,b in zip(points,points[1:])):
        raise ValueError('cut antimeridian-crossing polygons before import')
    # Translation avoids cancellation for small local polygons far from zero.
    x,y=points[0]
    area=sum((a[0]-x)*(b[1]-y)-(b[0]-x)*(a[1]-y) for a,b in zip(points,points[1:]))
    if area==0: raise ValueError('linear ring has zero signed area')
    return tuple(points)


@dataclass(frozen=True)
class GeoRegions:
    """Snapshot string feature IDs and Polygon/MultiPolygon coordinates.

    This validates structure, coordinate bounds and nondegenerate closed rings.
    It is not a topology repair/validation engine: supply simple rings, contained
    holes and nonoverlapping multipolygon parts. Ring orientation is accepted
    either way; rendering and picking use the even-odd fill rule per polygon.
    """
    features: tuple

    def __post_init__(self):
        features=[];seen=set()
        for key,polygons in _sequence(self.features,'features'):
            if not isinstance(key,str) or not key or key in seen:
                raise ValueError('feature IDs must be unique nonempty strings')
            seen.add(key)
            copied=tuple(tuple(_ring(ring) for ring in _sequence(poly,'polygon'))
                         for poly in _sequence(polygons,'multipolygon'))
            features.append((key,copied))
        object.__setattr__(self,'features',tuple(features))

    @classmethod
    def from_geojson(cls, source):
        """Import a FeatureCollection with explicit string feature IDs.

        Properties are not used for joins or values; the keyed table supplies
        those. Altitudes, other geometry types and legacy CRS fields fail.
        """
        if not isinstance(source,dict) or source.get('type')!='FeatureCollection':
            raise ValueError('expected a GeoJSON FeatureCollection')
        if 'crs' in source: raise ValueError('legacy CRS fields are unsupported; use longitude/latitude')
        features=[]
        for feature in _sequence(source.get('features'),'features'):
            if not isinstance(feature,dict) or feature.get('type')!='Feature':
                raise ValueError('expected a GeoJSON Feature')
            geometry=feature.get('geometry')
            if not isinstance(geometry,dict) or geometry.get('type') not in ('Polygon','MultiPolygon'):
                raise ValueError('only non-null Polygon and MultiPolygon geometries are supported')
            if 'crs' in feature or 'crs' in geometry: raise ValueError('legacy CRS fields are unsupported')
            coordinates=geometry.get('coordinates')
            features.append((feature.get('id'),[coordinates] if geometry['type']=='Polygon' else coordinates))
        return cls(tuple(features))

    @classmethod
    def read(cls, path):
        """Read a UTF-8 GeoJSON file without optional geospatial dependencies."""
        return cls.from_geojson(json.loads(Path(path).read_text(encoding='utf-8')))

    @property
    def feature_ids(self):
        return tuple(key for key,_ in self.features)

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.features,separators=(',',':'),allow_nan=False).encode()).hexdigest()
