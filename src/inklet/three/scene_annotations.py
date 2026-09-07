"""Vector annotations in a saved scene's camera frame."""
import math

from ..core import Diagram, PhantomPrim, Rect, Style, Vec2, mm
from ..draw import annotate, as_drawn, dimension
from ..draw.coords import active_theme
from .scene_projection import _Camera, _vector


def _number(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{name} must be finite' + (' and positive' if positive else ''))
    return value


def _policy(rendered, hidden, depth_bias):
    if hidden not in ('omit', 'dash', 'show'):
        raise ValueError('hidden must be omit, dash or show')
    camera = _Camera(rendered, depth_bias)
    if hidden != 'show' and camera.depth is None:
        raise ValueError("Request passes=('depth',) to hide occluded annotations")
    return camera


def _layer(rendered, parts, kind, record, anchors=()):
    # A phantom retains the image frame while actual label extents can grow it.
    # An envelope override would crop labels placed outside the image.
    frame = Rect.from_size(rendered.metadata['width_mm'], rendered.metadata['height_mm'])
    result = Diagram(prim=PhantomPrim(frame), children=tuple(parts), kind='scene-annotation',
        notes={'scene_annotation': dict(type=kind,
            source_cache_key=rendered.metadata.get('cache_key'), **record)})
    result.anchor('origin', Vec2(0, 0))
    for name, point in anchors:
        result.anchor(name, point)
    return result


def _state(points, hidden):
    in_frame = all(p.in_frame for p in points)
    obscured = any(p.visible is False for p in points)
    return in_frame and (hidden != 'omit' or not obscured), obscured


def annotate3d(rendered, point, text, *, side='n', clear=2., hidden='omit',
               depth_bias=1e-3, leader=True, head='none', size=None,
               avoid=(), leader_style=None, **text_style):
    camera = _policy(rendered, hidden, depth_bias)
    world = _vector(point)
    projected = camera.project(camera.local(world))
    clear = _number(mm(clear), 'clear')
    if clear < 0:
        raise ValueError('clear must be non-negative')
    shown, obscured = _state([projected], hidden)
    paint = dict(leader_style or {})
    if hidden == 'dash' and obscured:
        paint['stroke_dash'] = (1., 1.)
    target = Diagram(prim=PhantomPrim(Rect(projected.point.x, projected.point.y,
        projected.point.x, projected.point.y)), kind='scene-target')
    target.anchor('target', projected.point)
    target.anchor('origin', Vec2(0, 0))
    # Build even an omitted label so invalid author options never depend on visibility.
    label = annotate(target.at('target'), text, side=side, clear=clear,
        leader=leader, head=head, size=size, avoid=avoid,
        leader_style=paint, through=(rendered.diagram,), **text_style)
    return _layer(rendered, [label] if shown else [], 'label',
        dict(world=world, hidden=hidden, visible=projected.visible,
             in_frame=projected.in_frame, shown=shown, depth_bias=camera.bias),
        [('target', projected.point)])


def dimension3d(rendered, a, b, text=None, *, scale=1., unit='scene units',
                precision=3, offset=0., hidden='omit', depth_bias=1e-3,
                size=None, tick=1.2, witness=True, plate=True, **style):
    camera = _policy(rendered, hidden, depth_bias)
    a, b = _vector(a), _vector(b)
    scale = _number(scale, 'scale', positive=True)
    if type(precision) is not int or not 0 <= precision <= 12:
        raise ValueError('precision must be an integer from 0 to 12')
    if not isinstance(unit, str):
        raise ValueError('unit must be a string')
    distance = _number(math.dist(a, b), 'world distance', positive=True)
    value = _number(distance*scale, 'scaled distance', positive=True)
    offset = _number(mm(offset), 'offset')
    tick = _number(mm(tick), 'tick', positive=True)
    pa, pb = [camera.project(camera.local(p)) for p in (a, b)]
    shown, obscured = _state([pa, pb], hidden)
    caption = text
    if caption is None:
        caption = (f'{value:.{precision}f}'.rstrip('0').rstrip('.') or '0') if precision else str(round(value))
    if text is None and unit:
        from .. import escape_markup
        caption += ' ' + escape_markup(unit)
    paint = style | ({'stroke_dash': (1., 1.)} if hidden == 'dash' and obscured else {})
    drawing = as_drawn(dimension(pa.point, pb.point, caption, offset=offset,
        tick=tick, witness=witness, plate=plate, size=size, **paint))
    return _layer(rendered, [drawing] if shown else [], 'dimension',
        dict(world=[a, b], distance=distance, value=value, scale=scale, unit=unit,
             hidden=hidden, visible=[pa.visible, pb.visible], shown=shown,
             depth_bias=camera.bias), [('start', pa.point), ('end', pb.point)])


def arrow3d(rendered, a, b, *, hidden='omit', depth_bias=1e-3,
            head='triangle', head_size=1.6, step_px=1., max_samples=200_000, **style):
    from ..links import HEADS
    from ..links.link import _head_prim
    camera = _policy(rendered, hidden, depth_bias)
    a, b = _vector(a), _vector(b)
    if head not in HEADS:
        raise ValueError(f'head must be one of {HEADS}')
    head_size = _number(mm(head_size), 'head_size', positive=True)
    if math.dist(a, b) <= 1e-12:
        raise ValueError('An arrow requires distinct world points')
    shaft = rendered.path3d([a, b], hidden=hidden, depth_bias=depth_bias,
        step_px=step_px, max_samples=max_samples, **style)
    local_a, local_b = camera.local(a), camera.local(b)
    # Do not project a clipped endpoint onto the camera plane or invent a tip there.
    clipped = camera.clip(local_a, local_b)
    parts = [shaft]
    tip_shown = False
    if clipped is not None and all(value >= 0 for value in camera.planes(local_b)):
        tip = camera.project(local_b)
        start = camera.project(clipped[0]).point
        span = tip.point-start
        tip_shown = head != 'none' and span.length > 1e-9 and (hidden == 'show' or tip.visible is True)
        if tip_shown:
            prim, _ = _head_prim(head, tip.point, span.normalized(), min(head_size, span.length/2))
            ink = style.get('stroke', active_theme().ink)
            parts.append(Diagram(prim=prim, kind='arrowhead', style=Style(
                fill=ink if prim.filled else 'none', stroke=ink,
                stroke_width=style.get('stroke_width', active_theme().hairline),
                opacity=style.get('opacity'))))
    return _layer(rendered, parts, 'arrow', dict(world=[a, b], hidden=hidden,
        head=head, head_shown=tip_shown, head_size=head_size, depth_bias=camera.bias))


def angle3d(rendered, a, vertex, b, text=None, *, radius=None, precision=1,
            hidden='omit', depth_bias=1e-3, side='n', clear=2., size=None,
            step_px=1., max_samples=200_000, **style):
    _policy(rendered, hidden, depth_bias)
    a, vertex, b = _vector(a), _vector(vertex), _vector(b)
    lengths = [math.dist(p, vertex) for p in (a, b)]
    for length in lengths:
        _number(length, 'angle arm length', positive=True)
    u, v = [tuple((x-y)/length for x, y in zip(p, vertex))
            for p, length in zip((a, b), lengths)]
    dot = max(-1., min(1., sum(x*y for x, y in zip(u, v))))
    perpendicular = tuple(y-dot*x for x, y in zip(u, v))
    sine = math.hypot(*perpendicular)
    if sine < 1e-10:
        raise ValueError('An angle requires non-collinear arms')
    angle = math.atan2(sine, dot)
    w = tuple(x/sine for x in perpendicular)
    radius = _number(min(lengths)*.3 if radius is None else radius, 'radius', positive=True)
    if type(precision) is not int or not 0 <= precision <= 12:
        raise ValueError('precision must be an integer from 0 to 12')
    def on_arc(t):
        return tuple(p+radius*(x*math.cos(t)+y*math.sin(t)) for p, x, y in zip(vertex, u, w))
    # The arc lies in the WORLD plane of the two arms, then passes through the camera.
    points = [on_arc(angle*n/64) for n in range(65)]
    route = [vertex, *points, vertex]
    arc = rendered.path3d(route, hidden=hidden, depth_bias=depth_bias,
        step_px=step_px, max_samples=max_samples, **style)
    caption = text if text is not None else f'{math.degrees(angle):.{precision}f}°'
    label = annotate3d(rendered, on_arc(angle/2), caption, side=side, clear=clear,
        hidden=hidden, depth_bias=depth_bias, size=size, leader=False,
        text_fill=style.get('stroke', active_theme().ink))
    return _layer(rendered, [arc, label], 'angle', dict(world=[a, vertex, b],
        degrees=math.degrees(angle), radius=radius, hidden=hidden, depth_bias=float(depth_bias)))
