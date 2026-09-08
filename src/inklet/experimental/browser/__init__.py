"""Experimental linked plot documents for offline browser rendering.

Python owns layout and text shaping. The browser consumes physical geometry,
clips marks to measured plot areas, and preserves explicit row identities.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
import hashlib
import html
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from ...core import resolve
from ..selection import KeyedTable, SelectionState
from .regions import GeoRegions
from .timeaxis import TimeAxis
from .series import SeriesView
from .drawings import DrawingItem, DrawingView
from .images import LabelImageView
from .fields import MeshFieldView
from ..temporal import time_milliseconds

SCHEMA = 'inklet.browser-scatter/0.1'
STATE_SCHEMA = 'inklet.browser-view/0.1'


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value)!=4 or not all(_finite(v) for v in value):
        raise ValueError('viewport needs four finite numbers')
    if value[2]<=0 or value[3]<=0: raise ValueError('viewport dimensions must be positive')
    return tuple(value)


@dataclass(frozen=True)
class _CartesianView:
    """Shared fixed numeric or explicit temporal axes for measured views."""
    name: str
    x: str
    y: str
    x_domain: tuple[float, float] | TimeAxis
    y_domain: tuple[float, float] | TimeAxis
    x_label: str = ''
    y_label: str = ''

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if any(not isinstance(v,str) or not v for v in (self.x,self.y)):
            raise ValueError('coordinate columns must be nonempty strings')
        if any(not isinstance(v,str) for v in (self.x_label,self.y_label)):
            raise ValueError('axis labels must be strings')
        for name in ('x_domain','y_domain'):
            if isinstance(getattr(self,name),TimeAxis):
                continue
            domain=tuple(getattr(self,name))
            if len(domain)!=2 or not all(_finite(v) for v in domain) or domain[0]==domain[1] or not math.isfinite(domain[1]-domain[0]):
                raise ValueError('linear domains need two distinct finite endpoints')
            object.__setattr__(self,name,domain)
        if not isinstance(self.color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',self.color):
            raise ValueError('color must be a six-digit hex colour')


@dataclass(frozen=True)
class ScatterView(_CartesianView):
    """Circular points with radius in millimetres."""
    radius_mm: float = .45
    color: str = '#34786b'

    def __post_init__(self):
        super().__post_init__()
        if not _finite(self.radius_mm) or not 0 < self.radius_mm <= 10:
            raise ValueError('radius must be positive and at most 10 mm')


@dataclass(frozen=True)
class LineView(_CartesianView):
    """Connect adjacent source rows; null pairs break the line.

    Filtering removes incident segments without bridging gaps. Picking a
    segment selects its nearer endpoint row (the later endpoint at a tie).
    """
    line_width_mm: float = .45
    color: str = '#34786b'
    max_gap_seconds: float | None = field(default=None, kw_only=True)

    def __post_init__(self):
        super().__post_init__()
        if not _finite(self.line_width_mm) or not 0 < self.line_width_mm <= 10:
            raise ValueError('line width must be positive and at most 10 mm')
        if self.max_gap_seconds is not None:
            if not _finite(self.max_gap_seconds) or self.max_gap_seconds <= 0:
                raise ValueError('max_gap_seconds must be finite and positive')
            if not isinstance(self.x_domain,TimeAxis):
                raise ValueError('max_gap_seconds requires a temporal x axis')


@dataclass(frozen=True)
class BarView(_CartesianView):
    """Numeric-position bars with width in position-axis data units.

    Vertical bars extend from baseline to y at x; horizontal bars extend from
    baseline to x at y. Zero-area bars have no visible or pickable mark.
    """
    bar_width: float = .8
    baseline: float = 0
    orientation: str = 'vertical'
    color: str = '#34786b'

    def __post_init__(self):
        super().__post_init__()
        if not _finite(self.bar_width) or self.bar_width <= 0:
            raise ValueError('bar width must be finite and positive')
        if not _finite(self.baseline): raise ValueError('baseline must be finite')
        if self.orientation not in ('vertical', 'horizontal'):
            raise ValueError('bar orientation must be vertical or horizontal')
        if isinstance(self.y_domain if self.orientation=='vertical' else self.x_domain,TimeAxis):
            raise ValueError('bars support a temporal position axis, not a temporal value axis')


@dataclass(frozen=True)
class IntervalView(_CartesianView):
    """Supplied absolute interval bounds and a center, linked by source row.

    Declare the interval's meaning explicitly. Inklet does not estimate it.
    Missing bounds retain the center marker and omit the interval.
    """
    lower: str = field(kw_only=True)
    upper: str = field(kw_only=True)
    interval_label: str = field(kw_only=True)
    orientation: str = 'vertical'
    cap_width_mm: float = 2
    radius_mm: float = .6
    line_width_mm: float = .3
    color: str = '#34786b'

    def __post_init__(self):
        super().__post_init__()
        if any(not isinstance(v,str) or not v.strip() for v in (self.lower,self.upper,self.interval_label)):
            raise ValueError('interval bounds need column names and an explicit interval_label')
        if self.orientation not in ('vertical','horizontal'):
            raise ValueError('interval orientation must be vertical or horizontal')
        if isinstance(self.y_domain if self.orientation=='vertical' else self.x_domain,TimeAxis):
            raise ValueError('intervals require a numeric value axis')
        for name in ('cap_width_mm','radius_mm','line_width_mm'):
            if not _finite(getattr(self,name)) or not 0 < getattr(self,name) <= 10:
                raise ValueError(f'{name} must be positive and at most 10 mm')


@dataclass(frozen=True)
class ECDFView:
    """A fixed reference ECDF and individually selectable observation markers.

    Ties use count(value <= x) / n; None is excluded from n. Filtering hides
    observation markers only. Replacing the data rebuilds the reference curve.
    """
    name: str
    value: str
    x_domain: tuple[float,float]
    x_label: str = ''
    y_label: str = 'Cumulative fraction'
    radius_mm: float = .55
    line_width_mm: float = .3
    color: str = '#34786b'
    y_domain: tuple[float,float] = field(default=(0,1.05),init=False)

    def __post_init__(self):
        if isinstance(self.x_domain,TimeAxis):
            raise ValueError('ECDF values must use a numeric domain')
        checked=ScatterView(self.name,self.value,'ecdf_fraction',self.x_domain,self.y_domain,
                            self.x_label,self.y_label,self.radius_mm,self.color)
        object.__setattr__(self,'x_domain',checked.x_domain)
        if not _finite(self.line_width_mm) or not 0 < self.line_width_mm <= 10:
            raise ValueError('line width must be positive and at most 10 mm')

    @property
    def x(self): return self.value

    @property
    def y(self): return 'ecdf_fraction'


@dataclass(frozen=True)
class FacetView:
    """Repeat a Cartesian view over explicit, ordered string categories.

    Domains and styling are shared. Empty categories retain their panels.
    Lines follow source order within each category, with null coordinate
    pairs breaking the line. Unlisted/null categories remain in the table
    and are reported in the scene's facet_groups metadata.
    """
    view: ScatterView | LineView | BarView | IntervalView | ECDFView | SeriesView
    column: str
    values: tuple[str,...]
    labels: tuple[str,...] = ()

    def __post_init__(self):
        if type(self.view) not in (ScatterView,LineView,BarView,IntervalView,ECDFView,SeriesView):
            raise ValueError('facets require a Cartesian plot view')
        if not isinstance(self.column,str) or not self.column:
            raise ValueError('facet column must be a nonempty string')
        if isinstance(self.values,(str,bytes)) or isinstance(self.labels,(str,bytes)):
            raise ValueError('facet values and labels must be sequences of strings')
        values=tuple(self.values);labels=tuple(self.labels) or values
        if not 1<=len(values)<=12 or any(not isinstance(v,str) or not v for v in values) or len(set(values))!=len(values):
            raise ValueError('provide one to twelve unique nonempty string facet values')
        if len(labels)!=len(values) or any(not isinstance(v,str) or not v for v in labels):
            raise ValueError('provide one nonempty string label per facet value')
        object.__setattr__(self,'values',values);object.__setattr__(self,'labels',labels)

    @property
    def name(self):
        return self.view.name


def _expand_facets(table, definitions):
    views=[];metadata={};rows={};groups=[]
    for definition in definitions:
        if not isinstance(definition,FacetView):
            views.append(definition);continue
        if definition.column not in table.columns: raise ValueError(f'unknown facet column: {definition.column}')
        categories=table.columns[definition.column]
        if any(v is not None and not isinstance(v,str) for v in categories):
            raise ValueError('facet columns must contain strings or null')
        positions={value:[] for value in definition.values};unassigned=[]
        for n,(key,value) in enumerate(zip(table.row_ids,categories)):
            if value in positions: positions[value].append(n)
            else: unassigned.append(key)
        groups.append(dict(name=definition.name,column=definition.column,values=definition.values,unassigned_ids=unassigned))
        for n,(value,label) in enumerate(zip(definition.values,definition.labels)):
            view=replace(definition.view,name=f'{definition.name}__facet_{n}')
            views.append(view);rows[view.name]=positions[value]
            metadata[view.name]=dict(column=definition.column,value=value,label=label)
    if len(views)>12: raise ValueError('a browser figure supports at most twelve expanded panels')
    if len({v.name for v in views})!=len(views): raise ValueError('expanded view names must be unique')
    return views,metadata,rows,groups


@dataclass(frozen=True)
class RegionView:
    """Flat longitude/latitude map fitted with equal physical degree scales.

    Extent is (west, south, east, north). Colors use explicit half-open value
    bins: below first break, between breaks, at/above the last break. A missing
    value uses missing_color. Values and legend never rescale during filtering.
    """
    name: str
    regions: GeoRegions
    extent: tuple[float,float,float,float]
    value: str | None = None
    breaks: tuple[float,...] = ()
    colors: tuple[str,...] = ('#34786b',)
    value_label: str = ''
    missing_color: str = '#d4d9d6'

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if not isinstance(self.regions,GeoRegions): raise ValueError('regions must be GeoRegions')
        extent=tuple(self.extent)
        if (len(extent)!=4 or not all(_finite(v) for v in extent) or
                not -180<=extent[0]<extent[2]<=180 or not -90<=extent[1]<extent[3]<=90):
            raise ValueError('extent needs increasing west/south/east/north degree bounds')
        breaks=tuple(self.breaks); colors=tuple(self.colors)
        if not all(_finite(v) for v in breaks) or any(a>=b for a,b in zip(breaks,breaks[1:])):
            raise ValueError('breaks must be finite and strictly increasing')
        if len(colors)!=len(breaks)+1 or any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in (*colors,self.missing_color)):
            raise ValueError('provide one hex color per bin and a hex missing color')
        if self.value is not None and (not isinstance(self.value,str) or not self.value):
            raise ValueError('value must be a column name or None')
        if self.value is None and breaks: raise ValueError('breaks require a value column')
        if not isinstance(self.value_label,str): raise ValueError('value label must be a string')
        object.__setattr__(self,'extent',extent);object.__setattr__(self,'breaks',breaks);object.__setattr__(self,'colors',colors)

    def _legend(self, missing=False):
        if self.value is None: return []
        if not self.breaks: labels=['All values']
        else:
            labels=[f'< {self.breaks[0]:g}']
            labels += [f'{a:g}–< {b:g}' for a,b in zip(self.breaks,self.breaks[1:])]
            labels += [f'≥ {self.breaks[-1]:g}']
        entries=list(zip(labels,self.colors))
        if missing: entries.append(('Missing',self.missing_color))
        return entries


def _region_layer(view,table,bounds):
    west,south,east,north=view.extent
    scale=min(bounds[2]/(east-west),bounds[3]/(north-south))
    if not math.isfinite(scale): raise ValueError('region extent is too small to project')
    w,h=(east-west)*scale,(north-south)*scale
    clip=[round(bounds[0]+(bounds[2]-w)/2,6),round(bounds[1]+(bounds[3]-h)/2,6),round(w,6),round(h,6)]
    def project(p): return [round(clip[0]+(p[0]-west)*scale,6),round(clip[1]+(north-p[1])*scale,6)]
    features=dict(view.regions.features);marks=[]
    for n,key in enumerate(table.row_ids):
        value=table.columns[view.value][n] if view.value is not None else 0
        color=view.missing_color if value is None else view.colors[sum(value>=b for b in view.breaks)]
        for polygon in features[key]:
            rings=[[project(p) for p in ring] for ring in polygon]
            vertices=[p for ring in rings for p in ring]
            xs,ys=zip(*vertices)
            marks.append(dict(kind='polygon',ids=[key],geometry=rings,color=color,
                              bounds=[min(xs),min(ys),max(xs),max(ys)]))
    return dict(name=view.name,clip=clip,marks=marks,color=view.colors[0],value=view.value,
                legend=view._legend(any(v is None for v in table.columns[view.value]) if view.value else False),
                projection='plate-carree',extent=view.extent,geometry_digest=view.regions.digest)


def _marks(layer):
    if 'marks' in layer: return layer['marks']
    return [dict(kind='circle', ids=[key], geometry=[x,y,layer['radius']])
            for key,x,y in layer['points']]


def _svg_mark(mark, color, selected=False):
    """Shared physical geometry and styling contract for static vector export."""
    g=mark['geometry']; kind=mark['kind']; color=mark.get('color',color)
    if kind=='image':
        if selected:
            b=mark['bounds']
            return 'rect',dict(x=str(b[0]),y=str(b[1]),width=str(b[2]-b[0]),height=str(b[3]-b[1]),
                               fill='none',stroke='#bd5636',**{'stroke-width':'.4'})
        attrs=dict(zip(('x','y','width','height'),map(str,g)),href=mark['href'])
        if mark.get('smooth') is False: attrs['image-rendering']='pixelated'
        if mark.get('preserve_aspect') is False: attrs['preserveAspectRatio']='none'
        return 'image',attrs
    if kind=='polygon':
        path=' '.join('M '+' L '.join(f'{x} {y}' for x,y in ring)+' Z' for ring in g)
        return 'path',{'d':path,'fill-rule':'evenodd','fill':'none' if selected else color,
                       'stroke':'#bd5636' if selected else '#ffffff',
                       'stroke-width':'.6' if selected else '.2','stroke-linejoin':'round'}
    if kind=='circle':
        tag='circle'; attrs=dict(cx=g[0],cy=g[1],r=g[2]+(.3 if selected else 0))
    elif kind=='rect':
        tag='rect'; attrs=dict(zip(('x','y','width','height'),g))
    else:
        tag='line'; attrs=dict(zip(('x1','y1','x2','y2'),g))
        attrs.update({'stroke-width':mark.get('selected_width',mark['width']+.6) if selected else mark['width'],
                      'stroke-linecap':'round','stroke':'#bd5636' if selected else color})
    if kind!='line':
        attrs.update({'fill':'none','stroke':'#bd5636','stroke-width':.3} if selected
                     else {'fill':color,'fill-opacity':mark.get('opacity',.65)})
    return tag,{key:str(value) for key,value in attrs.items()}


class BrowserFigure:
    """Measured linked circles, line segments, bars and geographic regions.

    The scene snapshots a keyed table. Null coordinate pairs omit marks and
    break lines. Page zoom never recomputes domains, ticks or layout.
    """
    _schema = 'inklet.browser-figure/0.1'
    def __init__(self, table: KeyedTable, views, *, width=190, columns=None):
        import inklet as i
        definitions=tuple(views)
        if not definitions or len(definitions)>4 or any(type(v) not in (ScatterView,LineView,BarView,IntervalView,ECDFView,SeriesView,RegionView,DrawingView,LabelImageView,MeshFieldView,FacetView) for v in definitions):
            raise ValueError('provide one to four supported plot or facet view definitions')
        if len({v.name for v in definitions})!=len(definitions): raise ValueError('view names must be unique')
        views,facet_metadata,facet_rows,facet_groups=_expand_facets(table,definitions)
        columns=min(2,len(views)) if columns is None else columns
        if type(columns) is not int or not 1<=columns<=4: raise ValueError('columns must be from 1 to 4')
        doc=i.document(width=width,columns=columns,gap=9,margin=6,
                       share_plot_margins=bool(facet_groups) or any(isinstance(v,MeshFieldView) for v in views)).letters()
        coordinates={};statistics={};ecdf_curves={}
        for index,view in enumerate(views):
            if isinstance(view,(DrawingView,LabelImageView,MeshFieldView)):
                if isinstance(view,(LabelImageView,MeshFieldView)): view.validate_table(table)
                p=i.plot_spec(x=(0,1),y=(0,1),height=58)
                p.line([(0,0),(1,1)],stroke='none',stroke_width=0)
                if isinstance(view,MeshFieldView):
                    p.legend(entries=view.legend(),side='bottom',title=f'Scalar / {view.field.scalar_unit}',markup=False)
            elif isinstance(view,RegionView):
                if set(view.regions.feature_ids)!=set(table.row_ids):
                    missing=set(table.row_ids)-set(view.regions.feature_ids)
                    extra=set(view.regions.feature_ids)-set(table.row_ids)
                    raise ValueError(f'region/table ID mismatch: missing geometry {sorted(missing)}, unmatched geometry {sorted(extra)}')
                if view.value is not None:
                    if view.value not in table.columns: raise ValueError(f'unknown value column: {view.value}')
                    if any(v is not None and not _finite(v) for v in table.columns[view.value]):
                        raise ValueError('region values must be numeric or null')
                p=i.plot_spec(x=(0,1),y=(0,1),height=58)
                # Reserve the full map area even though browser marks are added
                # later. A legend-only panel would otherwise fit to its text.
                p.line([(0,0),(1,1)],stroke='none',stroke_width=0)
                entries=view._legend(any(v is None for v in table.columns[view.value]) if view.value else False)
                if entries: p.legend(entries=entries,side='bottom',title=view.value_label or view.value,markup=False)
            else:
                indices=facet_rows.get(view.name,range(len(table.row_ids)))
                if isinstance(view,ECDFView):
                    if view.value not in table.columns: raise ValueError(f'unknown column: {view.value}')
                    raw=table.columns[view.value]
                    if any(v is not None and not _finite(v) for v in raw):
                        raise ValueError('ECDF values must be numeric or null')
                    ordered=sorted(raw[n] for n in indices if raw[n] is not None)
                    ranks={value:(n+1)/len(ordered) for n,value in enumerate(ordered)}
                    fractions=[None]*len(raw)
                    for n in indices: fractions[n]=ranks.get(raw[n])
                    coordinates[view.name,'y']=fractions
                    statistics[view.name]=dict(kind='ecdf',method='count(value <= x) / n',
                        population='fixed source rows in this panel',n=len(ordered),
                        missing=sum(raw[n] is None for n in indices),filtering='markers only; reference population unchanged')
                    curve=[]
                    if ordered:
                        previous_x=min(view.x_domain[0],view.x_domain[1],ordered[0]);previous_y=0
                        for value,fraction in sorted(ranks.items()):
                            curve.extend(((previous_x,previous_y,value,previous_y),(value,previous_y,value,fraction)))
                            previous_x,previous_y=value,fraction
                        curve.append((previous_x,previous_y,max(*view.x_domain,ordered[-1]),previous_y))
                    ecdf_curves[view.name]=curve
                if isinstance(view,IntervalView):
                    for column in (view.lower,view.upper):
                        if column not in table.columns: raise ValueError(f'unknown interval column: {column}')
                        if any(v is not None and not _finite(v) for v in table.columns[column]):
                            raise ValueError(f'interval column {column!r} must be numeric or null')
                    statistics[view.name]=dict(kind='interval',label=view.interval_label,
                        population='supplied source-row intervals',filtering='hide rows without recomputing intervals',
                        missing_intervals=0)
                    for row,(lo,hi) in enumerate(zip(table.columns[view.lower],table.columns[view.upper])):
                        if lo is not None and hi is not None and lo > hi:
                            raise ValueError(f'interval row {row}: require lower <= upper')
                if isinstance(view,SeriesView): view.validate_table(table)
                for axis,column in (() if isinstance(view,SeriesView) else (('x',view.x),('y',view.y))):
                    if isinstance(view,ECDFView) and axis=='y': continue
                    if column not in table.columns: raise ValueError(f'unknown column: {column}')
                    domain=getattr(view,axis+'_domain')
                    if isinstance(domain,TimeAxis):
                        values=[]
                        for row,value in enumerate(table.columns[column]):
                            try:
                                milliseconds=time_milliseconds(value,domain.mode)
                                values.append(None if milliseconds is None else (milliseconds-domain.milliseconds[0])/1000)
                            except ValueError as error:
                                raise ValueError(f'coordinate column {column!r}, row {row}: {error}') from error
                        coordinates[view.name,axis]=values
                    else:
                        if any(v is not None and not _finite(v) for v in table.columns[column]):
                            raise ValueError(f'coordinate column {column!r} must be numeric or null')
                        coordinates[view.name,axis]=table.columns[column]
                p=i.plot_spec(x=view.x_domain.scale() if isinstance(view.x_domain,TimeAxis) else view.x_domain,
                              y=view.y_domain.scale() if isinstance(view.y_domain,TimeAxis) else view.y_domain,height=58)
                labels={axis:(getattr(view,axis+'_label') or getattr(view,axis)) +
                        (' / UTC' if isinstance(getattr(view,axis+'_domain'),TimeAxis) and
                         getattr(view,axis+'_domain').mode=='utc' else '') for axis in ('x','y')}
                p.axes(**labels)
                if view.name in facet_metadata:
                    p.title(i.text(facet_metadata[view.name]['label'],markup=False))
            doc.add(view.name,p,row=index//columns,column=index%columns)
        figure=doc.compile()
        if any(d.severity=='error' for d in figure.diagnostics): raise ValueError(figure.report())
        # Outlined glyphs preserve Python's shaping without external fonts or
        # browser font loading. HTML supplies textual/data alternatives.
        frame=figure.to_svg(text='outline')
        root=ET.fromstring(frame)
        width_mm,height_mm=map(float,(root.attrib['width'][:-2],root.attrib['height'][:-2]))
        cells={p.diagram.name:p for p in resolve(figure.root).values() if p.diagram.kind=='document-cell'}
        layers=[]
        for view in views:
            placement=cells[view.name]; rect=placement.diagram.notes['plot_area']
            # Document cell transforms are translations; fail if that contract changes.
            t=placement.world
            if (t.a,t.b,t.c,t.d)!=(1.,0.,0.,1.): raise ValueError('unsupported transformed plot cell')
            bounds=[rect.x0+t.e,rect.y0+t.f,rect.width,rect.height]
            bounds=[round(v,6) for v in bounds]
            if isinstance(view,(DrawingView,LabelImageView,MeshFieldView)):
                layers.append(view.layer(table,bounds));continue
            if isinstance(view,RegionView):
                layers.append(_region_layer(view,table,bounds));continue
            xd=(0,(view.x_domain.milliseconds[1]-view.x_domain.milliseconds[0])/1000) if isinstance(view.x_domain,TimeAxis) else view.x_domain
            yd=(0,(view.y_domain.milliseconds[1]-view.y_domain.milliseconds[0])/1000) if isinstance(view.y_domain,TimeAxis) else view.y_domain
            def project(x,y):
                px=bounds[0]+(x-xd[0])/(xd[1]-xd[0])*bounds[2]
                py=bounds[1]+(1-(y-yd[0])/(yd[1]-yd[0]))*bounds[3]
                if not math.isfinite(px) or not math.isfinite(py): raise ValueError('projected coordinate overflow')
                return [round(px,6),round(py,6)]
            if isinstance(view,SeriesView):
                layer=view.layer(table,bounds,project,facet_rows.get(view.name,range(len(table.row_ids))))
                if view.name in facet_metadata: layer['facet']=facet_metadata[view.name]
                layers.append(layer);continue
            points=[]; missing=0; marks=[]; previous=None; previous_x=None; gap_count=0
            gap_ms=(Decimal(str(view.max_gap_seconds))*1000 if isinstance(view,LineView)
                    and view.max_gap_seconds is not None else None)
            if isinstance(view,ECDFView):
                marks=[dict(kind='line',ids=[],reference=True,geometry=[*project(a,b),*project(c,d)],
                            width=view.line_width_mm,color='#9aa9a3') for a,b,c,d in ecdf_curves[view.name]]
            for n in facet_rows.get(view.name,range(len(table.row_ids))):
                key,x,y=table.row_ids[n],coordinates[view.name,'x'][n],coordinates[view.name,'y'][n]
                if x is None or y is None:
                    missing+=1; previous=None; continue
                px,py=project(x,y)
                points.append([key,px,py])
                if isinstance(view,ECDFView):
                    marks.append(dict(kind='circle',ids=[key],geometry=[px,py,view.radius_mm]))
                elif isinstance(view,IntervalView):
                    lo,hi=table.columns[view.lower][n],table.columns[view.upper][n]
                    center=y if view.orientation=='vertical' else x
                    if lo is not None and hi is not None:
                        if not lo <= center <= hi:
                            raise ValueError(f'interval row {n}: require lower <= center <= upper')
                        a,b=(project(x,lo),project(x,hi)) if view.orientation=='vertical' else (project(lo,y),project(hi,y))
                        cap=view.cap_width_mm/2
                        segments=[[*a,*b]]
                        for cx,cy in (a,b):
                            segments.append([cx-cap,cy,cx+cap,cy] if view.orientation=='vertical' else [cx,cy-cap,cx,cy+cap])
                        marks.extend(dict(kind='line',ids=[key,key],geometry=[round(v,6) for v in segment],
                                          width=view.line_width_mm,selected_width=view.line_width_mm+.2) for segment in segments)
                    else: statistics[view.name]['missing_intervals']+=1
                    marks.append(dict(kind='circle',ids=[key],geometry=[px,py,view.radius_mm]))
                elif isinstance(view,LineView):
                    if previous is not None and gap_ms is not None and abs(round(x*1000)-round(previous_x*1000))>gap_ms:
                        previous=None;gap_count+=1
                    if previous is not None:
                        marks.append(dict(kind='line',ids=[previous[0],key],
                                          geometry=[*previous[1:],px,py],width=view.line_width_mm))
                    previous=[key,px,py];previous_x=x
                elif isinstance(view,BarView):
                    if view.orientation=='vertical':
                        a,b=project(x-view.bar_width/2,view.baseline),project(x+view.bar_width/2,y)
                    else:
                        a,b=project(view.baseline,y-view.bar_width/2),project(x,y+view.bar_width/2)
                    box=[min(a[0],b[0]),min(a[1],b[1]),round(abs(b[0]-a[0]),6),round(abs(b[1]-a[1]),6)]
                    if box[2] and box[3]: marks.append(dict(kind='rect',ids=[key],geometry=box))
            layer=dict(name=view.name,x=view.x,y=view.y,clip=bounds,points=points,
                       color=view.color,missing=missing)
            time_axes={axis:getattr(view,axis+'_domain').metadata() for axis in ('x','y')
                       if isinstance(getattr(view,axis+'_domain'),TimeAxis)}
            if time_axes: layer['time_axes']=time_axes
            if view.name in statistics: layer['statistics']=statistics[view.name]
            if isinstance(view,ECDFView): layer['derived_y']=coordinates[view.name,'y']
            if isinstance(view,LineView) and view.max_gap_seconds is not None:
                layer['max_gap_seconds']=view.max_gap_seconds;layer['time_gaps']=gap_count
            if view.name in facet_metadata: layer['facet']=facet_metadata[view.name]
            if isinstance(view,ScatterView): layer['radius']=view.radius_mm
            else: layer['marks']=marks
            if isinstance(view,(ECDFView,IntervalView)): layer['radius']=view.radius_mm
            layers.append(layer)
        payload=dict(schema=self._schema,table=table.name,data_digest=table.digest,row_ids=table.row_ids,
                     columns=dict(table.columns),width=width_mm,height=height_mm,frame=frame,layers=layers)
        if table.key!='id': payload['key']=table.key
        if facet_groups: payload['facet_groups']=facet_groups
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)
        payload['scene_digest']=hashlib.sha256(raw.encode()).hexdigest()
        self._json=json.dumps(payload,separators=(',',':'),allow_nan=False)
        self.table=table
        self._views=definitions
        self._width=width
        self._columns=columns

    def payload(self):
        """Return an independent copy of the portable scene data."""
        return json.loads(self._json)

    def replace_data(self, table: KeyedTable, *, state=None, views=None,
                     width=None, columns=None, missing='error', viewport='reset'):
        """Compile revised data and explicitly transfer an old view state.

        Returns a FigureRevision containing a new BrowserFigure, state and
        change report. The original stays usable, including on failure. Table
        name and key must stay the same. Removed selected/filtered IDs fail
        unless missing='drop'. New rows enter only an all-rows filter.

        View definitions and layout are reused unless supplied. Map geometry
        must still join exactly: supply revised RegionViews if IDs change.
        Viewport resets to the new page by default; 'preserve' explicitly keeps
        the old physical page rectangle, subject to the new figure's limits.
        """
        if not isinstance(table,KeyedTable): raise ValueError('table must be a KeyedTable')
        if table.key!=self.table.key: raise ValueError('replacement must retain the key column')
        if viewport not in ('reset','preserve'): raise ValueError('viewport must be reset or preserve')
        selection,old_viewport=self.validate_state(self.state() if state is None else state)
        rebased=selection.rebase(table,missing=missing)
        revised=BrowserFigure(table,self._views if views is None else views,
                              width=self._width if width is None else width,
                              columns=self._columns if columns is None else columns)
        new_state=revised.state(rebased.state,
                                viewport=old_viewport if viewport=='preserve' else None)
        report=self._revision_report(revised)
        report.update(removed_selected=rebased.removed_selected,removed_visible=rebased.removed_visible,
                      missing_policy=missing,viewport_policy=viewport)
        return FigureRevision(revised,json.dumps(new_state),json.dumps(report))

    def _revision_report(self, revised):
        """Static differences shared by Python and embedded browser revisions."""
        before=self.table; table=revised.table
        old_ids=set(before.row_ids); new_ids=set(table.row_ids)
        common=old_ids & new_ids
        old_columns=set(before.columns); new_columns=set(table.columns)
        # Compare JSON representations, so bool/number and int/float changes
        # are reported consistently with the table digest's serialization.
        def rows(source):
            return {key:json.dumps({c:values[n] for c,values in source.columns.items()},
                                   sort_keys=True,separators=(',',':'),allow_nan=False)
                    for n,key in enumerate(source.row_ids) if key in common}
        old_rows,new_rows=rows(before),rows(table)
        return dict(schema='inklet.browser-revision/0.1',table=table.name,key=table.key,
                    previous_data_digest=before.digest,data_digest=table.digest,
                    previous_scene_digest=self.payload()['scene_digest'],
                    scene_digest=revised.payload()['scene_digest'],
                    added_ids=sorted(new_ids-old_ids),removed_ids=sorted(old_ids-new_ids),
                    changed_ids=sorted(k for k in common if old_rows[k]!=new_rows[k]),
                    added_columns=sorted(new_columns-old_columns),removed_columns=sorted(old_columns-new_columns),
                    order_changed=[k for k in before.row_ids if k in common]!=[k for k in table.row_ids if k in common])

    def state(self, selection=None, *, viewport=None):
        selection=selection or SelectionState.for_table(self.table)
        selection.validate(self.table)
        payload=self.payload()
        result=dict(schema=STATE_SCHEMA,scene_digest=payload['scene_digest'],
                    selection=json.loads(selection.to_json()),
                    viewport=list(_box([0,0,payload['width'],payload['height']] if viewport is None else viewport)))
        self.validate_state(result)
        return result

    def validate_state(self, value):
        if not isinstance(value,dict) or set(value)!={'schema','scene_digest','selection','viewport'}:
            raise ValueError('invalid browser state fields')
        if value['schema']!=STATE_SCHEMA or value['scene_digest']!=self.payload()['scene_digest']:
            raise ValueError('browser state belongs to a different scene revision')
        selection=SelectionState.from_json(json.dumps(value['selection']))
        selection.validate(self.table)
        viewport=_box(value['viewport'])
        p=self.payload()
        if (abs(viewport[0])>p['width']*100 or abs(viewport[1])>p['height']*100 or
                not p['width']/100<=viewport[2]<=p['width']*100 or
                not p['height']/100<=viewport[3]<=p['height']*100):
            raise ValueError('viewport is outside the preview limits')
        return selection,viewport

    def to_svg(self, state=None):
        """Export the selected page viewport with clipped vector marks."""
        selection,viewport=self.validate_state(state if state is not None else self.state())
        p=self.payload();root=ET.fromstring(p['frame']);ns='{http://www.w3.org/2000/svg}'
        root.set('viewBox',' '.join(map(str,viewport)))
        root.set('width',f'{viewport[2]}mm');root.set('height',f'{viewport[3]}mm')
        # Mark layer first, measured frame/text afterwards. Background remains first.
        marks=ET.Element(ns+'g',{'id':'browser-marks'})
        highlights=ET.Element(ns+'g',{'id':'browser-selection'})
        defs=ET.SubElement(marks,ns+'defs')
        visible=set(self.table.row_ids if selection.visible_ids is None else selection.visible_ids)
        selected=set(selection.selected_ids)
        for n,layer in enumerate(p['layers']):
            clip_id=f'browser-clip-{n}'
            clip=ET.SubElement(defs,ns+'clipPath',{'id':clip_id})
            ET.SubElement(clip,ns+'rect',dict(zip(('x','y','width','height'),map(str,layer['clip']))))
            group=ET.SubElement(marks,ns+'g',{'clip-path':f'url(#{clip_id})'})
            highlight=ET.SubElement(highlights,ns+'g',{'clip-path':f'url(#{clip_id})'})
            for mark in _marks(layer):
                if not all(key in visible for key in mark['ids']): continue
                tag,attrs=_svg_mark(mark,layer['color'])
                ET.SubElement(group,ns+tag,attrs)
                if mark.get('highlight',True) and any(key in selected for key in mark['ids']):
                    tag,attrs=_svg_mark(mark,layer['color'],True)
                    ET.SubElement(highlight,ns+tag,attrs)
        root.insert(1,marks)
        root.append(highlights)
        ET.register_namespace('','http://www.w3.org/2000/svg')
        ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
        return ET.tostring(root,encoding='unicode')

    def to_html(self, *, title='Linked plot views', backend='svg', state=None,
                attribution='Built with Inklet.', search_columns=(),
                revision_label='Original', revisions=()):
        if not isinstance(attribution,str): raise ValueError('attribution must be a string')
        if isinstance(search_columns,str): raise ValueError('search columns must be a sequence of column names')
        search_columns=tuple(search_columns)
        if any(c not in self.table.columns for c in search_columns): raise ValueError('unknown search column')
        if state is not None: self.validate_state(state)
        if backend not in ('svg','canvas','hybrid'): raise ValueError('unknown browser backend')
        revisions=tuple(revisions)
        if len(revisions)>7 or any(not isinstance(r,RevisionOption) for r in revisions):
            raise ValueError('provide up to seven RevisionOption alternatives')
        options=(RevisionOption(revision_label,self,attribution,search_columns),*revisions)
        if len({r.label for r in options})!=len(options): raise ValueError('revision labels must be unique')
        if any(r.figure.table.name!=self.table.name or r.figure.table.key!=self.table.key for r in options):
            raise ValueError('revisions must retain the table name and key column')
        catalog=dict(labels=[r.label for r in options],
                     alternatives=[dict(scene=r.figure.payload(),attribution=r.attribution,
                                        search_columns=r.search_columns) for r in revisions],
                     reports=[[a.figure._revision_report(b.figure) for b in options] for a in options] if revisions else [])
        template=Path(__file__).with_name('page.html').read_text(encoding='utf-8')
        script=Path(__file__).with_name('runtime.js').read_text(encoding='utf-8')
        script_values={"/*DEFAULT_BACKEND*/'svg'":backend,'/*SEARCH_COLUMNS*/[]':search_columns,
                       '/*INITIAL_STATE*/null':state,'/*REVISION_CATALOG*/null':catalog}
        script=re.sub('|'.join(re.escape(k) for k in script_values),
                      lambda m:json.dumps(script_values[m.group()],allow_nan=False).replace('<','\\u003c'),script)
        p=self.payload()
        template=template.replace('/*ASPECT*/190/78',f"{p['width']}/{p['height']}")
        replacements={'<!--TITLE-->':html.escape(title),
                      '<!--ATTRIBUTION-->':html.escape(attribution),
                      '<!--FILTER_LABEL-->':'Search rows' if search_columns else 'Row ID contains',
                      '/*PAYLOAD*/':self._json.replace('<','\\u003c'), '/*RUNTIME*/':script}
        # Substitute once: authored strings may themselves contain template tokens.
        return re.sub(r'<!--TITLE-->|<!--ATTRIBUTION-->|<!--FILTER_LABEL-->|/\*PAYLOAD\*/|/\*RUNTIME\*/',
                      lambda match: replacements[match.group()],template)


@dataclass(frozen=True)
class RevisionOption:
    """A named Python-compiled alternative with its own plain-text source credit."""
    label: str
    figure: BrowserFigure
    attribution: str
    search_columns: tuple[str,...] = ()

    def __post_init__(self):
        if not isinstance(self.label,str) or not self.label.strip(): raise ValueError('revision label must be nonempty')
        if not isinstance(self.figure,BrowserFigure): raise ValueError('revision figure must be a BrowserFigure')
        if not isinstance(self.attribution,str): raise ValueError('revision attribution must be a string')
        if isinstance(self.search_columns,str): raise ValueError('search columns must be a sequence of column names')
        columns=tuple(self.search_columns)
        if any(c not in self.figure.table.columns for c in columns): raise ValueError('unknown search column')
        object.__setattr__(self,'search_columns',columns)


@dataclass(frozen=True)
class FigureRevision:
    """Recompiled figure with independent copies of its saved state and report."""
    figure: BrowserFigure
    _state_json: str = field(repr=False)
    _report_json: str = field(repr=False)

    def state(self):
        return json.loads(self._state_json)

    def report(self):
        return json.loads(self._report_json)


class BrowserScatter(BrowserFigure):
    """Compatibility entry point for the original single-row scatter study."""
    _schema = SCHEMA

    def __init__(self, table, views, *, width=190):
        views=tuple(views)
        if any(type(v) is not ScatterView for v in views):
            raise ValueError('BrowserScatter accepts only ScatterView; use BrowserFigure for mixed marks')
        super().__init__(table,views,width=width,columns=len(views) or 1)
