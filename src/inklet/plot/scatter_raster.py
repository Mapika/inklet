"""Rasterize a scatter layer while leaving axes, text and legends vector."""
from __future__ import annotations

import io
import math
from dataclasses import replace

from ..core import Affine, Diagram, DiagramError, EllipsePrim, ImagePrim, PathPrim, Rect, RectPrim, Vec2, resolve
from ..draw.coords import active_theme, as_drawn
from ..themes.color import parse_color
from ..render.paint import MITER_LIMIT


def raster_scatter(node: Diagram, *, dpi: float = 300, clip: Rect | None = None) -> Diagram:
    """Paint standard marker geometry to an embedded antialiased RGBA PNG.

    Pillow is optional and imported only for this path. The returned image
    retains the vector layer's physical coordinates, including overhangs when
    clipping is disabled. Group opacity is applied once after compositing.
    """
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError("scatter dpi must be finite and positive")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise DiagramError('scatter(raster=True) requires Pillow; install inklet[images]') from None
    from ..figure import apply_theme

    theme = active_theme()
    opacity = 1.0 if node.style.opacity is None else node.style.opacity
    node = as_drawn(replace(node, style=replace(node.style, opacity=1.0)))
    placements = [p for p in resolve(apply_theme(node, theme),
                                    base_style=theme.style_for('root')).values()
                  if p.diagram.prim is not None]
    if any(p.style.stroke_dash for p in placements):
        raise DiagramError("raster scatter does not support dashed marker outlines; use raster=False")
    boxes = []
    for p in placements:
        b = p.bbox
        pad = (p.style.stroke_width or 0)/2 if p.style.stroke not in (None,'none') else 0
        if p.style.stroke_linejoin == "miter" and isinstance(p.diagram.prim, (RectPrim, PathPrim)):
            pad *= MITER_LIMIT
        boxes.append(Rect(b.x0-pad,b.y0-pad,b.x1+pad,b.y1+pad))
    box = clip or Rect(min(b.x0 for b in boxes), min(b.y0 for b in boxes),
                       max(b.x1 for b in boxes), max(b.y1 for b in boxes))
    width=max(1,math.ceil(box.width*dpi/25.4))
    height=max(1,math.ceil(box.height*dpi/25.4))
    if width*height > 16_000_000:
        raise DiagramError("raster scatter exceeds 16 million pixels; reduce dpi or plot extent")
    aa=min(3, max(1, int(math.sqrt(16_000_000/(width*height)))))
    image=Image.new('RGBA',(width*aa,height*aa))
    sx,sy=width*aa/box.width,height*aa/box.height
    def pixel(v): return ((v.x-box.x0)*sx,(v.y-box.y0)*sy)
    painted=set()
    for p,b in zip(placements,boxes):
        if b.x1 < box.x0 or b.x0 > box.x1 or b.y1 < box.y0 or b.y0 > box.y1: continue
        x0=max(0,math.floor((b.x0-box.x0)*sx)-2)
        y0=max(0,math.floor((b.y0-box.y0)*sy)-2)
        x1=min(width*aa,math.ceil((b.x1-box.x0)*sx)+3)
        y1=min(height*aa,math.ceil((b.y1-box.y0)*sy)+3)
        if x1<=x0 or y1<=y0: continue
        shape=p.diagram.prim
        size=(x1-x0,y1-y0)
        patch=Image.new('RGBA',size)
        style=p.style
        def local(v):
            x,y=pixel(p.world.apply(v));return (x-x0,y-y0)
        def mask(stroke):
            m=Image.new('L',size)
            d=ImageDraw.Draw(m)
            weight=max(1,round((style.stroke_width or 0)*sx))
            if isinstance(shape,EllipsePrim):
                bounds=[local(Vec2(-shape.rx,-shape.ry)),local(Vec2(shape.rx,shape.ry))]
                if stroke:
                    # Pillow outlines sit inside their bounding rectangle;
                    # SVG/PDF strokes straddle the geometric boundary.
                    (ax, ay), (bx, by) = bounds
                    rx = (style.stroke_width or 0)*sx/2
                    ry = (style.stroke_width or 0)*sy/2
                    d.ellipse((ax-rx, ay-ry, bx+rx, by+ry), fill=255)
                    if bx-ax > 2*rx and by-ay > 2*ry:
                        d.ellipse((ax+rx, ay+ry, bx-rx, by-ry), fill=0)
                else:
                    d.ellipse(bounds, fill=255)
            elif isinstance(shape,RectPrim):
                corners=shape.rect.corners
                pts=[local(v) for v in corners]
                if stroke:_stroke(d, pts, True, weight, style)
                else:d.polygon(pts,fill=255)
            elif isinstance(shape,PathPrim):
                for sub in shape.subpaths:
                    pts=[local(v) for v in sub.points]
                    if stroke:
                        _stroke(d, pts, sub.closed, weight, style)
                    elif shape.filled:d.polygon(pts,fill=255)
            else: raise DiagramError(f"unsupported raster scatter primitive: {type(shape).__name__}")
            return m
        for stroke,color,alpha in [(False,style.fill,style.fill_opacity),(True,style.stroke,style.stroke_opacity)]:
            if color in (None,'none') or (stroke and not style.stroke_width):continue
            rgb=parse_color(color);painted.add(color)
            a=1. if alpha is None else alpha
            m=mask(stroke)
            if a!=1:m=m.point(lambda v:round(v*a))
            layer=Image.new('RGBA',size,(*rgb,255));layer.putalpha(m)
            patch=Image.alpha_composite(patch,layer)
        image.alpha_composite(patch,(x0,y0))
    image=image.resize((width,height),Image.Resampling.LANCZOS)
    if opacity!=1:image.putalpha(image.getchannel('A').point(lambda v:round(v*opacity)))
    payload=io.BytesIO();image.save(payload,format='PNG')
    result=Diagram(prim=ImagePrim('scatter',box.width,box.height,pixel_size=(width,height),
                                 data=payload.getvalue(),smooth=True),kind='raster-scatter',
                   transform=Affine.translation(box.center.x,box.center.y))
    result.anchor('origin',Vec2(-box.center.x,-box.center.y))
    result.note('ramp_colours',tuple(sorted(painted)))
    result.note('raster_dpi',dpi)
    return result


def _stroke(draw, points, closed, width, style):
    """Union of segment strips, joins and caps, painted once into a mask."""
    radius = width/2
    points = [Vec2(*p) for p in points]
    segments = list(zip(points, points[1:] + points[:1] if closed else points[1:]))
    normals = []
    def polygon(ps):
        draw.polygon([(p.x, p.y) for p in ps], fill=255)
    def disc(p):
        draw.ellipse((p.x-radius, p.y-radius, p.x+radius, p.y+radius), fill=255)
    for a, b in segments:
        v = b-a
        if v.length == 0:
            normals.append(Vec2(0, 0))
            continue
        n = Vec2(-v.y, v.x)*(radius/v.length)
        normals.append(n)
        polygon([a+n, b+n, b-n, a-n])
    join = style.stroke_linejoin or "miter"
    for i in (range(len(points)) if closed else range(1, len(points)-1)):
        p = points[i]
        n1, n2 = normals[i-1], normals[i]
        if join == "round":
            disc(p)
        else:
            for sign in (-1, 1):
                a, b = p+n1*sign, p+n2*sign
                denominator = radius*radius + n1.x*n2.x + n1.y*n2.y
                if join == "miter" and denominator > 1e-12:
                    offset = (n1+n2)*(sign*radius*radius/denominator)
                    if offset.length <= MITER_LIMIT*radius:
                        polygon([p, a, p+offset, b])
                        continue
                polygon([p, a, b])
    if not closed and segments:
        for p, other, n in [(points[0], points[1], normals[0]),
                             (points[-1], points[-2], normals[-1])]:
            cap = style.stroke_linecap or "butt"
            if cap == "round":
                disc(p)
            elif cap == "square" and (p-other).length:
                extension = (p-other)*(radius/(p-other).length)
                polygon([p+n, p-n, p-n+extension, p+n+extension])
