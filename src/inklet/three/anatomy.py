"""Layered anatomical illustrations and registered overview/detail cameras."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from ..core import Diagram, Envelope, Rect, Vec2, mm
from .camera import Camera, View, as_camera
from .mesh import Mesh, MeshError
from .overlays import _xyz


def _length(value,name,zero=False):
    value=mm(value)
    if not math.isfinite(value) or value<0 or (not zero and value==0):raise ValueError(f'{name} must be finite and positive')
    return value


def _focus(value):
    mesh=value if isinstance(value,Mesh) else Mesh(tuple(_xyz(p) for p in value),())
    if not mesh.vertices:raise MeshError('anatomy focus must contain points')
    return mesh


@dataclass
class AnatomyView:
    """A fixed viewport with named surfaces, paths and markers in one camera.

    Construct with `anatomy_view`. Layer data stays in source 3D coordinates;
    changing the focus never transforms layers independently. Overlays are
    X-ray drawings by default. Named layer order controls default painting.
    build(depth='occluded') jointly sorts opaque filled surfaces and hides
    covered paths and markers; surface styles must match except for color. No registration or dataset
    selection is inferred: all layers must already share physical coordinates.
    """
    view: View
    width: float
    height: float
    _layers: list = field(default_factory=list,repr=False)

    @property
    def area(self):return Rect.from_size(self.width,self.height)

    def _add(self,name,kind,data,style):
        if not isinstance(name,str) or not name:raise ValueError('layer name must be a nonempty string')
        if any(row[0]==name for row in self._layers):raise ValueError(f'duplicate anatomy layer {name!r}')
        self._layers.append((name,kind,data,dict(style)))
        return self

    def surface(self,name,mesh,**style):
        if not isinstance(mesh,Mesh):raise TypeError('surface requires a Mesh')
        if {'view','width','height','backend'} & style.keys():raise ValueError('the AnatomyView owns the surface camera and dimensions')
        return self._add(name,'surface',mesh,style)

    def paths(self,name,lines,**style):
        return self._add(name,'paths',tuple(tuple(_xyz(p) for p in line) for line in lines),style)

    def markers(self,name,points,**style):
        return self._add(name,'markers',tuple(_xyz(p) for p in points),style)

    def style(self,name,**changes):
        """Restyle one named layer without refitting its geometry or siblings."""
        for k,(key,kind,data,options) in enumerate(self._layers):
            if key==name:
                if kind=='surface' and {'view','width','height','backend'} & changes.keys():
                    raise ValueError('the AnatomyView owns the surface camera and dimensions')
                self._layers[k]=(key,kind,data,{**options,**changes})
                return self
        raise KeyError(name)

    def zoom(self,focus,*,width,height,pad=1,layers=None):
        """Reframe selected layers in the same camera orientation and projection.

        Focus is a Mesh or iterable of 3D points. Only fitting changes; the eye,
        basis and perspective stay shared. Original and zoom remain independent
        builders, sharing immutable geometry. `layers` filters by explicit name.
        """
        width,height,pad=_length(width,'width'),_length(height,'height'),_length(pad,'pad',True)
        if 2*pad>=min(width,height):raise ValueError('padding consumes the anatomy viewport')
        focus=_focus(focus)
        names={row[0] for row in self._layers} if layers is None else ({layers} if isinstance(layers,str) else set(layers))
        unknown=names-{row[0] for row in self._layers}
        if unknown:raise ValueError(f'unknown anatomy layers: {sorted(unknown)}')
        return AnatomyView(self.view.fitted(focus,width-2*pad,height-2*pad),width,height,
                           [(name,kind,data,dict(style)) for name,kind,data,style in self._layers if name in names])

    def window(self,detail):
        """The detail's full viewport, expressed in this overview's coordinates.

        Includes the zoom's padding/aspect ratio, not just the focus's tight
        bounds. Use this for locator rectangles and magnification connectors.
        """
        if not isinstance(detail,AnatomyView):raise TypeError('window needs an AnatomyView')
        for key in ['eye','right','up','forward','perspective','focal','near']:
            if getattr(self.view,key)!=getattr(detail.view,key):raise ValueError('locator views must share a camera; create the detail with zoom()')
        ratio=self.view.scale/detail.view.scale
        offset=self.view.offset-detail.view.offset*ratio
        b=detail.area
        return Rect(b.x0*ratio+offset.x,b.y0*ratio+offset.y,b.x1*ratio+offset.x,b.y1*ratio+offset.y)

    def lighting(self, direction=(-.4,-.6,-1), *, levels=16, smooth=80):
        """Set one smooth-lighting treatment across all current surfaces."""
        light=_xyz(direction)
        if light.dot(light)==0 or type(levels) is not int or not 2<=levels<=64 or not math.isfinite(smooth) or not 0<smooth<=180:
            raise ValueError('lighting needs a nonzero direction, 2–64 levels and smoothing in (0,180]')
        for name,kind,data,style in self._layers:
            if kind=='surface':self.style(name,light=light,levels=levels,smooth=smooth,shading='smooth')
        return self

    def cut(self,normal,offset=0):
        """Section all layers in source coordinates without changing the camera.

        Keeps normal·point >= offset. Surfaces have open cuts, not invented
        interior caps. Paths are split at the same plane; markers are filtered.
        The original builder and its data remain unchanged.
        """
        from .section import plane,clip_paths
        normal,offset=plane(normal,offset);layers=[]
        for name,kind,data,style in self._layers:
            if kind=='surface':data=data.clipped(normal,offset);style={**style,'cull':False}
            elif kind=='paths':data=clip_paths(data,normal,offset)
            else:data=tuple(p for p in data if normal.dot(p)>=offset)
            layers.append((name,kind,data,dict(style)))
        return AnatomyView(self.view,self.width,self.height,layers)

    def build(self, *, depth='layers'):

        """Render all layers into a clipped, fixed-size native vector viewport."""
        import inklet as i
        if depth not in ('layers','occluded'):raise ValueError('anatomy depth must be layers or occluded')
        nodes=[];visibility=None
        if depth=='occluded':
            from .section import SurfaceVisibility
            surfaces=[(name,data,style) for name,kind,data,style in self._layers if kind=='surface' and data.faces]
            if surfaces:
                common={k:v for k,v in surfaces[0][2].items() if k!='color'}
                if common.get('opacity',1)!=1 or any({k:v for k,v in style.items() if k!='color'}!=common for _,_,style in surfaces):
                    raise ValueError('occluded anatomy requires opaque surfaces with shared styles; only color may differ')
                if common.get('style','solid') not in ('solid','shaded','toon') or common.get('cull',False) or 'colors' in common:
                    raise ValueError('occluded anatomy requires filled surfaces, cull=False and one color per layer')
                merged=surfaces[0][1].grouped(surfaces[0][0]).merged(*(data.grouped(name) for name,data,_ in surfaces[1:]))
                options=dict(style='solid',shading='smooth',cull=False,ridges=False,hidden=False)
                options.update(common);options.update(sort='exact',colors={name:style.get('color','#d3d0ca') for name,_,style in surfaces})
                nodes.append(i.model(merged,view=self.view,**options))
                visibility=SurfaceVisibility(merged,self.view)
        for name,kind,data,style in self._layers:
            if kind=='surface':
                if depth=='occluded' or not data.faces:continue
                options=dict(style='solid',shading='smooth',sort='depth',cull=True,ridges=False,hidden=False,color='#d3d0ca')
                options.update(style);node=i.model(data,view=self.view,**options)
            elif kind=='paths':node=self.view.paths(visibility.paths(data) if visibility else data,**style)
            else:node=self.view.markers(tuple(p for p in data if visibility.visible_point(p)) if visibility else data,**style)
            nodes.append(node.named(name))
        area=self.area
        return Diagram(children=tuple(nodes),kind='anatomy-view',clip_region=area.corners,
                       envelope_override=Envelope.from_rect(area),notes={'anatomy_view':{'layers':[v[0] for v in self._layers],'width':self.width,'height':self.height,'scale':self.view.scale,'depth':depth}})

    def inset(self,focus,*,width,height,corner='ne',side=None,gap=2,layers=None,**style):
        """Overview plus a registered inset or external detail, with locator lines.

        `side='right'` (or left/top/bottom) places detail outside the overview;
        otherwise `corner` places it inside. Uses Inklet's existing inset layout.
        Fonts and stroke widths retain their requested sizes in both views.
        """
        import inklet as i
        detail=self.zoom(focus,width=width,height=height,layers=layers)
        window=self.window(detail)
        area=self.area
        panel=i.panel(self.width,self.height,x=(area.x0,area.x1),y=(area.y1,area.y0))
        panel.draw(self.build())
        panel.inset(detail.build(),corner=corner,side=side,pad=gap,width=None,
                    zoom=(window.x0,window.x1,window.y0,window.y1),**style)
        from ..figure import apply_theme
        return apply_theme(panel.build(),i.current_theme())


def anatomy_view(reference,*,width,height,camera='front',pad=1):
    """Fit one camera to a reference mesh and author layers without projections.

    `camera` is a preset, Camera or already oriented View. The reference may
    also be 3D points when a View is supplied. Coordinates must already be in
    one physical frame; no FlyWire/MaleCNS-specific assumptions are made.
    """
    width,height,pad=_length(width,'width'),_length(height,'height'),_length(pad,'pad',True)
    if 2*pad>=min(width,height):raise ValueError('padding consumes the anatomy viewport')
    reference=_focus(reference)
    view=(camera.fitted(reference,width-2*pad,height-2*pad) if isinstance(camera,View)
          else as_camera(camera).frame(reference,width-2*pad,height-2*pad))
    return AnatomyView(view,width,height)
