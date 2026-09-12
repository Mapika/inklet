"""Bounded GeoJSON feature snapshots and linked flat maps without GIS extras."""
from dataclasses import dataclass
import hashlib
import json
import math
import re
from pathlib import Path

from .regions import _ring, _sequence


def _position(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('positions need two finite longitude/latitude numbers')
    lon, lat = value
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError('longitude/latitude is outside the supported degree range')
    return tuple(value)


def _line(value):
    points = tuple(_position(p) for p in _sequence(value, 'line'))
    if len(set(points)) < 2:
        raise ValueError('lines need at least two distinct positions')
    if any(abs(a[0]-b[0]) > 180 for a,b in zip(points, points[1:])):
        raise ValueError('cut antimeridian-crossing lines before import')
    return points


def _coordinates(kind, value):
    if kind == 'Point': return _position(value)
    if kind == 'MultiPoint': return tuple(_position(p) for p in _sequence(value, 'multipoint'))
    if kind == 'LineString': return _line(value)
    if kind == 'MultiLineString': return tuple(_line(p) for p in _sequence(value, 'multiline'))
    if kind == 'Polygon': return tuple(_ring(p) for p in _sequence(value, 'polygon'))
    if kind == 'MultiPolygon': return tuple(_coordinates('Polygon', p) for p in _sequence(value, 'multipolygon'))
    raise ValueError('supported geometries are Point, MultiPoint, LineString, MultiLineString, Polygon and MultiPolygon')


@dataclass(frozen=True)
class GeoFeatures:
    """Immutable (string ID, geometry type, coordinates) records with provenance.

    Coordinates are longitude/latitude degrees, without altitude or legacy CRS.
    Geometry collections and null/empty geometries are unsupported. Polygon
    topology requirements are the same as GeoRegions; this does not repair data.
    """
    features: tuple
    source: str = ''
    attribution: str = ''

    def __post_init__(self):
        if not isinstance(self.source, str) or not isinstance(self.attribution, str):
            raise ValueError('source and attribution must be strings')
        records = []; seen = set()
        for record in _sequence(self.features, 'features'):
            if not isinstance(record, (list, tuple)) or len(record) != 3:
                raise ValueError('features need ID, geometry type and coordinates')
            key, kind, coords = record
            if not isinstance(key, str) or not key or key in seen:
                raise ValueError('feature IDs must be unique nonempty strings')
            seen.add(key)
            records.append((key, kind, _coordinates(kind, coords)))
        object.__setattr__(self, 'features', tuple(records))

    @classmethod
    def from_geojson(cls, source, *, attribution='', source_name=''):
        """Snapshot a FeatureCollection; values/properties come from a keyed table.

        Explicit feature IDs join one feature to one row. Every part of a
        multi-geometry retains that row identity. Supply provenance explicitly.
        """
        if not isinstance(source, dict) or source.get('type') != 'FeatureCollection':
            raise ValueError('expected a GeoJSON FeatureCollection')
        if 'crs' in source: raise ValueError('legacy CRS fields are unsupported')
        records = []
        for feature in _sequence(source.get('features'), 'features'):
            if not isinstance(feature, dict) or feature.get('type') != 'Feature':
                raise ValueError('expected a GeoJSON Feature')
            geometry = feature.get('geometry')
            if not isinstance(geometry, dict): raise ValueError('null geometry is unsupported')
            if 'crs' in feature or 'crs' in geometry: raise ValueError('legacy CRS fields are unsupported')
            records.append((feature.get('id'), geometry.get('type'), geometry.get('coordinates')))
        return cls(tuple(records), source_name, attribution)

    @classmethod
    def read(cls, path, *, attribution='', source_name=''):
        """Read UTF-8 GeoJSON, retaining caller-supplied source and attribution."""
        return cls.from_geojson(json.loads(Path(path).read_text(encoding='utf-8')),
                                attribution=attribution, source_name=source_name)

    @property
    def feature_ids(self): return tuple(key for key, _, _ in self.features)

    @property
    def digest(self):
        return hashlib.sha256(json.dumps([self.features, self.source, self.attribution],
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()



def _finite_map(value):
    return type(value) in (int,float) and math.isfinite(value)


def _validate_map_style(self):
    if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
        raise ValueError('view name needs a stable document cell identifier')
    extent=tuple(self.extent)
    if (len(extent)!=4 or not all(_finite_map(v) for v in extent) or
            not -180<=extent[0]<extent[2]<=180 or not -90<=extent[1]<extent[3]<=90):
        raise ValueError('extent needs increasing west/south/east/north degree bounds')
    breaks=tuple(self.breaks); colors=tuple(self.colors)
    if not all(_finite_map(v) for v in breaks) or any(a>=b for a,b in zip(breaks,breaks[1:])):
        raise ValueError('breaks must be finite and strictly increasing')
    if len(colors)!=len(breaks)+1 or any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in (*colors,self.missing_color)):
        raise ValueError('provide one hex color per bin and a hex missing color')
    if self.value is not None and (not isinstance(self.value,str) or not self.value):
        raise ValueError('value must be a column name or None')
    if self.value is None and breaks: raise ValueError('breaks require a value column')
    if not isinstance(self.value_label,str): raise ValueError('value label must be a string')
    object.__setattr__(self,'extent',extent);object.__setattr__(self,'breaks',breaks);object.__setattr__(self,'colors',colors)



def _map_legend(self, missing=False):
    if self.value is None: return []
    if not self.breaks: labels=['All values']
    else:
        labels=[f'< {self.breaks[0]:g}']
        labels += [f'{a:g}–< {b:g}' for a,b in zip(self.breaks,self.breaks[1:])]
        labels += [f'≥ {self.breaks[-1]:g}']
    entries=list(zip(labels,self.colors))
    if missing: entries.append(('Missing',self.missing_color))
    return entries


def _map_projection(extent, bounds):
    west, south, east, north = extent
    scale = min(bounds[2]/(east-west), bounds[3]/(north-south))
    if not math.isfinite(scale): raise ValueError('region extent is too small to project')
    w, h = (east-west)*scale, (north-south)*scale
    clip = [round(bounds[0]+(bounds[2]-w)/2,6), round(bounds[1]+(bounds[3]-h)/2,6), round(w,6), round(h,6)]
    def project(p): return [round(clip[0]+(p[0]-west)*scale,6), round(clip[1]+(north-p[1])*scale,6)]
    return clip, project


@dataclass(frozen=True)
class MapView:
    """Linked GeoJSON points, routes and regions on one plate-carree map.

    Paint follows table row order, then part order. Point radii and route widths
    are physical millimetres. All parts select/filter as one feature row; routes
    are straight segments in longitude/latitude, not geodesics. Extent, bins and
    legends remain fixed during filtering. The feature/table join must be exact.
    """
    name: str
    features: GeoFeatures
    extent: tuple[float, float, float, float]
    value: str | None = None
    breaks: tuple[float, ...] = ()
    colors: tuple[str, ...] = ('#34786b',)
    value_label: str = ''
    missing_color: str = '#d4d9d6'
    radius_mm: float = 1
    line_width_mm: float = .6

    def __post_init__(self):
        # Retain the existing region map's extent, colour and bin contract.
        if not isinstance(self.features, GeoFeatures): raise ValueError('features must be GeoFeatures')
        _validate_map_style(self)
        for name in ('radius_mm', 'line_width_mm'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 10:
                raise ValueError(f'{name} must be positive and at most 10 mm')

    def _legend(self, missing=False):
        return _map_legend(self, missing)

    def validate_table(self, table):
        if set(self.features.feature_ids) != set(table.row_ids):
            missing = set(table.row_ids)-set(self.features.feature_ids)
            extra = set(self.features.feature_ids)-set(table.row_ids)
            raise ValueError(f'map/table ID mismatch: missing geometry {sorted(missing)}, unmatched geometry {sorted(extra)}')
        if self.value is not None:
            if self.value not in table.columns: raise ValueError(f'unknown value column: {self.value}')
            if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in table.columns[self.value]):
                raise ValueError('map values must be numeric or null')

    def layer(self, table, bounds):
        clip, project = _map_projection(self.extent, bounds)
        features = {key: (kind, coords) for key, kind, coords in self.features.features}
        marks = []
        for n, key in enumerate(table.row_ids):
            value = table.columns[self.value][n] if self.value is not None else 0
            color = self.missing_color if value is None else self.colors[sum(value >= b for b in self.breaks)]
            kind, coords = features[key]
            if kind in ('Point', 'MultiPoint'):
                for point in ([coords] if kind == 'Point' else coords):
                    marks.append(dict(kind='circle', ids=[key], geometry=[*project(point), self.radius_mm], color=color, opacity=1))
            elif kind in ('LineString', 'MultiLineString'):
                for line in ([coords] if kind == 'LineString' else coords):
                    for a,b in zip(line, line[1:]):
                        if a == b: continue
                        marks.append(dict(kind='line', ids=[key,key], geometry=[*project(a), *project(b)], width=self.line_width_mm, color=color))
            else:
                for polygon in ([coords] if kind == 'Polygon' else coords):
                    rings = [[project(p) for p in ring] for ring in polygon]
                    xs,ys = zip(*(p for ring in rings for p in ring))
                    marks.append(dict(kind='polygon', ids=[key], geometry=rings, color=color,
                                      bounds=[min(xs),min(ys),max(xs),max(ys)]))
        return dict(name=self.name, clip=clip, marks=marks, color=self.colors[0], value=self.value,
                    picking='paint',
                    legend=self._legend(any(v is None for v in table.columns[self.value]) if self.value else False),
                    projection='plate-carree', extent=self.extent, geometry_digest=self.features.digest,
                    geography=dict(source=self.features.source, attribution=self.features.attribution,
                                   geometry_types=sorted({kind for _,kind,_ in self.features.features}),
                                   route_interpolation='straight longitude/latitude segments'))
