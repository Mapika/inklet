"""XY face picking and calibrated planar vectors on triangle meshes."""
from dataclasses import dataclass
import math
import re

from ..fields import MeshField, _finite


@dataclass(frozen=True)
class MeshFieldView:
    """An equal-scale XY projection with piecewise-constant face colors.

    Faces paint in source order; later faces win where XY projections overlap.
    This is a plan projection, not a 3D visibility query. Arrows show the XY
    components at face centroids; vector_scale is geometry units / vector unit.
    """
    name: str
    field: MeshField
    breaks: tuple = (0, 1)
    colors: tuple = ('#d9e8ee','#7eb6bc','#287c83')
    vectors: bool = False
    vector_scale: float = .1
    missing_color: str = '#dedede'
    scale_bar: float | None = None

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if not isinstance(self.field,MeshField): raise ValueError('field must be a MeshField')
        breaks,colors = tuple(self.breaks),tuple(self.colors)
        if not all(map(_finite,breaks)) or any(a>=b for a,b in zip(breaks,breaks[1:])):
            raise ValueError('breaks must be finite and strictly increasing')
        if len(colors)!=len(breaks)+1 or any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in (*colors,self.missing_color)):
            raise ValueError('provide a hex color for every bin and missing values')
        if type(self.vectors) is not bool or not _finite(self.vector_scale) or self.vector_scale<=0:
            raise ValueError('vectors must be boolean and vector_scale finite and positive')
        if self.scale_bar is not None and (not _finite(self.scale_bar) or self.scale_bar<=0):
            raise ValueError('scale_bar must be a finite positive geometry length')
        for face in self.field.faces:
            a,b,c = [self.field.vertices[n] for n in face]
            area = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if not math.isfinite(area) or area==0:
                raise ValueError('every face must have a nondegenerate XY projection')
        object.__setattr__(self,'breaks',breaks);object.__setattr__(self,'colors',colors)

    def validate_table(self,table):
        self.field.validate_table(table)

    def color(self,value):
        return self.missing_color if value is None else self.colors[sum(value>=b for b in self.breaks)]

    def legend(self):
        labels = ([f'< {self.breaks[0]:g}'] + [f'{a:g}–< {b:g}' for a,b in zip(self.breaks,self.breaks[1:])] +
                  [f'≥ {self.breaks[-1]:g}']) if self.breaks else ['All values']
        return list(zip(labels,self.colors)) + ([('Missing',self.missing_color)] if None in self.field.scalars else [])

    def layer(self,table,bounds):
        self.validate_table(table)
        data=self.field.table().columns
        xs=[p[0] for p in self.field.vertices];ys=[p[1] for p in self.field.vertices]
        # Include arrow tips even in the scalar-only view so paired plans align.
        for x,y,v in zip(data['x'],data['y'],self.field.vectors):
            if v is not None: xs.append(x+v[0]*self.vector_scale);ys.append(y+v[1]*self.vector_scale)
        left,right,bottom,top=min(xs),max(xs),min(ys),max(ys)
        reserve=12 if self.scale_bar is not None else 6
        scale=min((bounds[2]-6)/(right-left),(bounds[3]-reserve)/(top-bottom))
        if not all(math.isfinite(v) for v in (left,right,bottom,top,scale)) or scale<=0:
            raise ValueError('field projection must be finite and representable')
        ox=bounds[0]+(bounds[2]-(right-left)*scale)/2
        oy=bounds[1]+(bounds[3]-reserve+6-(top-bottom)*scale)/2
        def project(x,y):return [ox+(x-left)*scale,oy+(top-y)*scale]
        marks=[]
        for key,face,value in zip(self.field.ids,self.field.faces,self.field.scalars):
            ring=[project(*self.field.vertices[n][:2]) for n in face]
            ring.append(ring[0])
            px,py=zip(*ring)
            marks.append(dict(kind='polygon',ids=[key],geometry=[ring],color=self.color(value),
                              bounds=[min(px),min(py),max(px),max(py)]))
        if self.vectors:
            for key,x,y,v in zip(self.field.ids,data['x'],data['y'],self.field.vectors):
                if v is None or (v[0]==0 and v[1]==0):continue
                start=project(x,y);end=project(x+v[0]*self.vector_scale,y+v[1]*self.vector_scale)
                dx,dy=end[0]-start[0],end[1]-start[1];length=math.hypot(dx,dy)
                if length==0:continue
                ux,uy=dx/length,dy/length;head=min(1.1,length*.35)
                for a,b in [(start,end),(end,[end[0]-head*ux+head*.45*uy,end[1]-head*uy-head*.45*ux]),
                            (end,[end[0]-head*ux-head*.45*uy,end[1]-head*uy+head*.45*ux])]:
                    marks.append(dict(kind='line',ids=[key,key],geometry=a+b,width=.22,color='#183f48',
                                      pickable=False,highlight=False))
        if self.scale_bar is not None:
            import inklet as i
            from .drawings import DrawingView, DrawingItem
            length=self.scale_bar*scale
            if length>bounds[2]-25:raise ValueError('scale bar exceeds the available panel width')
            def ruler(table,width,height):
                bar=i.polyline([(0,0),(length,0)],stroke='#183f48',stroke_width=.35).translated(3+length/2,height-3)
                label=i.text(f'{self.scale_bar:g} {self.field.unit}',size=i.pt(7),markup=False)
                label=label.translated(5+length-label.bbox.x0,height-3-label.bbox.center.y)
                return [DrawingItem((),bar),DrawingItem((),label)]
            marks.extend(DrawingView('ruler',ruler).layer(table,bounds)['marks'])
        return dict(name=self.name,clip=bounds,marks=marks,color=self.colors[0],value='scalar',
                    field=dict(source_digest=self.field.digest,projection='XY, equal physical scale',
                        picking='triangle interiors; source order resolves overlapping faces',
                        scalar='piecewise constant per face; no interpolation',unit=self.field.unit,
                        scalar_unit=self.field.scalar_unit,vector_unit=self.field.vector_unit,
                        vector_scale=self.vector_scale,scale_bar=self.scale_bar,vector_components='XY',
                        zero_vectors='no arrow',missing_vectors='no arrow; magnitude remains null',
                        scale_mm_per_unit=scale,origin_mm=[ox,oy],extent=[left,bottom,right,top]))
