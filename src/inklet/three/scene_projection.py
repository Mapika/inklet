"""Camera projection and vector paths tested against immutable scene depth."""
from dataclasses import dataclass
import math

from ..core import Diagram, Envelope, PathPrim, Rect, Style, Subpath, Vec2


@dataclass(frozen=True)
class ProjectedPoint:
    """A world point in centred figure millimetres, with camera visibility.

    depth is axial camera distance in scene units, matching Cycles Z for both
    supported camera types. visible is None without depth, False outside the frame.
    """
    point: Vec2
    depth: float
    in_frame: bool
    visible: bool | None


def _vector(point):
    if isinstance(point, (str, bytes)):
        raise ValueError('A world point requires three finite coordinates')
    try:
        point = tuple(float(value) for value in point)
    except (TypeError, ValueError):
        raise ValueError('A world point requires three finite coordinates') from None
    if len(point) != 3 or not all(math.isfinite(value) for value in point):
        raise ValueError('A world point requires three finite coordinates')
    return point


class _Camera:
    def __init__(self, rendered, depth_bias):
        self.rendered = rendered
        try:
            self.camera = rendered.metadata['projection']
        except KeyError:
            raise ValueError('This snapshot has no camera projection; render it again with Inklet dev4+') from None
        if self.camera['type'] not in ('ORTHO', 'PERSP'):
            raise ValueError('Projection supports orthographic and perspective cameras')
        self.perspective = self.camera['type'] == 'PERSP'
        self.width = rendered.metadata['width_mm']
        self.height = rendered.metadata['height_mm']
        self.pixels = rendered.metadata['pixels']
        self.depth = rendered.passes.get('depth')
        self.bias = float(depth_bias)
        if not math.isfinite(self.bias) or self.bias < 0:
            raise ValueError('depth_bias must be finite and non-negative')

    def local(self, point):
        point = _vector(point)
        return tuple(sum(row[j]*point[j] for j in range(3))+row[3]
                     for row in self.camera['world_to_camera'][:3])

    def planes(self, point):
        x, y, z = point
        distance = -z
        scale = distance if self.perspective else 1
        left, right, bottom, top = self.camera['bounds']
        return (distance-self.camera['near'], self.camera['far']-distance,
                x-left*scale, right*scale-x, y-bottom*scale, top*scale-y)

    def project(self, local):
        x, y, z = local
        distance = -z
        if self.perspective and distance == 0:
            raise ValueError('A point on the perspective camera plane has no finite projection')
        scale = distance if self.perspective else 1
        left, right, bottom, top = self.camera['bounds']
        u = (x/scale-left)/(right-left)
        v = (top-y/scale)/(top-bottom)
        point = Vec2((u-.5)*self.width, (v-.5)*self.height)
        depth = distance
        in_frame = all(value >= -1e-9 for value in self.planes(local))
        visible = None
        if not in_frame:
            visible = False
        elif self.depth is not None:
            px = max(0, min(self.pixels[0]-1, int(u*self.pixels[0])))
            py = max(0, min(self.pixels[1]-1, int(v*self.pixels[1])))
            surface = self.depth.value(px, py)
            visible = math.isfinite(surface) and depth <= surface+self.bias
        return ProjectedPoint(point, depth, in_frame, visible)

    def clip(self, a, b):
        start, end = 0., 1.
        for first, last in zip(self.planes(a), self.planes(b)):
            if first < 0 and last < 0:
                return None
            if first < 0:
                start = max(start, first/(first-last))
            elif last < 0:
                end = min(end, first/(first-last))
        if start >= end:
            return None
        return (_lerp(a, b, start), _lerp(a, b, end))


def _lerp(a, b, fraction):
    return tuple(x+(y-x)*fraction for x, y in zip(a, b))


def project(rendered, point, *, depth_bias=1e-3):
    camera = _Camera(rendered, depth_bias)
    return camera.project(camera.local(point))


def path3d(rendered, points, *, hidden='omit', depth_bias=1e-3,
           step_px=1., max_samples=200_000, **style):
    if hidden not in ('omit', 'dash', 'show'):
        raise ValueError('hidden must be omit, dash or show')
    step_px = float(step_px)
    if not math.isfinite(step_px) or step_px <= 0:
        raise ValueError('step_px must be finite and positive')
    if type(max_samples) is not int or max_samples < 2:
        raise ValueError('max_samples must be an integer of at least two')
    camera = _Camera(rendered, depth_bias)
    if hidden != 'show' and camera.depth is None:
        raise ValueError("Request passes=('depth',) to hide occluded path segments")
    points = [camera.local(point) for point in points]
    if len(points) < 2:
        raise ValueError('A 3D path requires at least two world points')
    visible_runs, hidden_runs = [], []
    sampled = 0

    def append(a, b, visible):
        if a == b:
            return
        runs = visible_runs if visible else hidden_runs
        if runs and runs[-1][-1] == a:
            previous = runs[-1][-2]
            u, v = a-previous, b-a
            if abs(u.x*v.y-u.y*v.x) < 1e-10 and u.x*v.x+u.y*v.y >= 0:
                runs[-1][-1] = b
            else:
                runs[-1].append(b)
        else:
            runs.append([a, b])

    for original_a, original_b in zip(points, points[1:]):
        clipped = camera.clip(original_a, original_b)
        if clipped is None:
            continue
        a, b = clipped
        pa, pb = camera.project(a).point, camera.project(b).point
        if hidden == 'show':
            append(pa, pb, True)
            continue
        length = math.hypot((pb.x-pa.x)*camera.pixels[0]/camera.width,
                            (pb.y-pa.y)*camera.pixels[1]/camera.height)
        if length > step_px*(max_samples-sampled):
            raise ValueError('Projected path exceeds max_samples; increase step_px or max_samples')
        count = max(1, math.ceil(length/step_px))
        sampled += count
        if sampled > max_samples:
            raise ValueError('Projected path exceeds max_samples; increase step_px or max_samples')
        for index in range(count):
            fraction = (index+.5)/count
            # Screen-linear samples need perspective-correct world interpolation.
            t = ((fraction/-b[2])/((1-fraction)/-a[2]+fraction/-b[2])
                 if camera.perspective else fraction)
            visible = camera.project(_lerp(a, b, t)).visible
            p = Vec2(pa.x+(pb.x-pa.x)*index/count, pa.y+(pb.y-pa.y)*index/count)
            q = Vec2(pa.x+(pb.x-pa.x)*(index+1)/count, pa.y+(pb.y-pa.y)*(index+1)/count)
            append(p, q, visible)
    options = {'fill': 'none', 'stroke_linecap': 'round', **style}
    children = []
    for runs, occluded in ((hidden_runs, True), (visible_runs, False)):
        if not runs or (occluded and hidden == 'omit'):
            continue
        paint = options | ({'stroke_dash': (1., 1.)} if occluded else {})
        children.append(Diagram(prim=PathPrim(tuple(Subpath(tuple(run)) for run in runs), filled=False),
                                style=Style(**paint), kind='scene-path'))
    result = Diagram(children=tuple(children), kind='scene-overlay',
        envelope_override=Envelope.from_rect(Rect.from_size(camera.width, camera.height)),
        notes={'scene_overlay': dict(source_cache_key=rendered.metadata.get('cache_key'),
            hidden=hidden, depth_bias=camera.bias, step_px=step_px,
            samples=sampled, visible_runs=len(visible_runs), hidden_runs=len(hidden_runs))})
    result.anchor('origin', Vec2(0, 0))
    return result
