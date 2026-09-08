"""Linked contour and streamline views from immutable nodal grid fields."""
from dataclasses import dataclass
import math
import re

from ..fields import _finite
from ..grid import GridField,Streamlines


@dataclass(frozen=True)
class GridFieldView:
    """Equal-scale XY views; picking and filtering use explicit cell identities.

    Contours and streamlines are fixed source-derived geometry. Filtering hides
    their cell pieces, without recomputing interpolation or trajectories.
    """
    name: str
    field: GridField
    levels: tuple = (1,2,3)
    colors: tuple = ('#e4edef','#a2cbd1','#528f9e','#225767')
    contours: bool = True
    cells: bool = False
    streamlines: Streamlines | None = None
    scale_bar: float | None = None

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if not isinstance(self.field,GridField):raise ValueError('field must be a GridField')
        levels,colors=tuple(self.levels),tuple(self.colors)
        if not 1<=len(levels)<=16 or not all(map(_finite,levels)) or any(a>=b for a,b in zip(levels,levels[1:])):
            raise ValueError('provide 1–16 finite increasing contour levels')
        if len(colors)!=len(levels)+1 or any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in colors):
            raise ValueError('provide one hex color per scalar bin')
        if type(self.contours) is not bool or type(self.cells) is not bool:raise ValueError('contours and cells must be booleans')
        if self.scale_bar is not None and (not _finite(self.scale_bar) or self.scale_bar<=0):raise ValueError('scale_bar must be positive and finite')
        if self.streamlines is not None and (not isinstance(self.streamlines,Streamlines) or self.streamlines.source_digest!=self.field.digest):
            raise ValueError('streamlines must belong to this exact field source')
        object.__setattr__(self,'levels',levels);object.__setattr__(self,'colors',colors)

    def validate_table(self,table):self.field.validate_table(table)

    def legend(self):
        if not self.cells:
            entries=[(f'{v:g}',self.colors[n+1]) for n,v in enumerate(self.levels)] if self.contours else []
            masked=any(None in row for row in self.field.scalars) or (self.streamlines is not None and any(None in row for row in self.field.vectors))
            return entries+([('Masked cell','#dedede')] if masked else [])
        labels=[f'< {self.levels[0]:g}']+[f'{a:g}–< {b:g}' for a,b in zip(self.levels,self.levels[1:])]+[f'≥ {self.levels[-1]:g}']
        entries=list(zip(labels,self.colors))
        if None in self.field.table().columns['scalar']:entries.append(('Missing','#dedede'))
        return entries

    def layer(self,table,bounds):
        self.validate_table(table)
        field=self.field;left,right=field.x[0],field.x[-1];bottom,top=field.y[0],field.y[-1]
        reserve=12 if self.scale_bar is not None else 6
        scale=min((bounds[2]-6)/(right-left),(bounds[3]-reserve)/(top-bottom))
        if not math.isfinite(scale) or scale<=0:raise ValueError('grid projection must be finite and representable')
        ox=bounds[0]+(bounds[2]-(right-left)*scale)/2;oy=bounds[1]+(bounds[3]-reserve+6-(top-bottom)*scale)/2
        def project(point):return [ox+(point[0]-left)*scale,oy+(top-point[1])*scale]
        marks=[];data=field.table().columns
        for n,(key,ix,iy) in enumerate(field.cells()):
            x,y=project((field.x[ix],field.y[iy+1]));w=(field.x[ix+1]-field.x[ix])*scale;h=(field.y[iy+1]-field.y[iy])*scale
            value=data['scalar'][n];missing=value is None or (self.streamlines is not None and data['magnitude'][n] is None)
            color='#dedede' if missing else self.colors[sum(value>=v for v in self.levels)]
            marks.append(dict(kind='rect',ids=[key],geometry=[x,y,w,h],opacity=1 if self.cells or missing else 0,color=color))
        def line(key,a,b,color,width=.26,**extra):
            marks.append(dict(kind='line',ids=[key,key],geometry=project(a)+project(b),color=color,width=width,
                              selected_width=width+.2,pickable=False,**extra))
        if self.contours:
            colors=dict(zip(self.levels,self.colors[1:]))
            for segment in field.contours(self.levels):line(segment.cell_id,*segment.points,colors[segment.level])
        if self.streamlines is not None:
            for trace in self.streamlines.lines:
                for a,b in zip(trace.points,trace.points[1:]):
                    for key,p,q in field.split_segment(a,b):line(key,p,q,'#263f49',.22)
                if len(trace.points)>3:
                    # One direction arrow at the middle of each integrated path.
                    n=len(trace.points)//2;a,b=trace.points[n-1:n+1];p,q=project(a),project(b)
                    dx,dy=q[0]-p[0],q[1]-p[1];length=math.hypot(dx,dy)
                    cell=field.locate(b)
                    if length and cell is not None:
                        ix,iy=cell;key=field.ids[iy*(len(field.x)-1)+ix];ux,uy=dx/length,dy/length;head=.85
                        for sign in (-1,1):
                            tip=(left+(q[0]-head*ux+sign*head*.45*uy-ox)/scale,
                                 top-(q[1]-head*uy-sign*head*.45*ux-oy)/scale)
                            for owner,ahead,bhead in field.split_segment(b,tip):
                                if field.sample(tuple((a+b)/2 for a,b in zip(ahead,bhead)),'vectors') is not None:
                                    line(owner,ahead,bhead,'#263f49',.22,highlight=False)
        if len(marks)>40000:raise ValueError('grid view exceeds 40,000 marks; reduce levels, seeds or tracing limits')
        if self.scale_bar is not None:
            import inklet as i
            from .drawings import DrawingView,DrawingItem
            length=self.scale_bar*scale
            if length>bounds[2]-25:raise ValueError('scale bar exceeds the available panel width')
            def ruler(table,width,height):
                bar=i.polyline([(0,0),(length,0)],stroke='#263f49',stroke_width=.35).translated(3+length/2,height-3)
                label=i.text(f'{self.scale_bar:g} {field.unit}',size=i.pt(7),markup=False)
                return [DrawingItem((),bar),DrawingItem((),label.translated(5+length-label.bbox.x0,height-3-label.bbox.center.y))]
            marks.extend(DrawingView('ruler',ruler).layer(table,bounds)['marks'])
        return dict(name=self.name,x='x',y='y',clip=bounds,marks=marks,color='#263f49',
            grid=dict(source_digest=field.digest,extent=[left,bottom,right,top],origin_mm=[ox,oy],scale_mm_per_unit=scale,
                unit=field.unit,scalar_unit=field.scalar_unit,vector_unit=field.vector_unit,
                interpolation='linear triangles; lower-left to upper-right diagonal',
                table_summary='arithmetic corner means; magnitude of the mean vector',
                missing='any missing corner masks the entire cell for that field',levels=self.levels,
                selection='cell identity; derived line pieces follow cell visibility',
                streamlines=None if self.streamlines is None else self.streamlines.report()))
