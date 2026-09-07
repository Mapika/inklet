"""Finite view selection and measured label assignment for scene snapshots.

This experiment optimizes an explicit discrete cost, not scientific meaning or
perceptual quality. No Blender process runs during planning. All lengths are mm
except target world coordinates and explicitly converted measurements.
"""
from dataclasses import asdict, dataclass
from itertools import combinations
import math

import inklet as i
from inklet.core import Envelope, PhantomPrim, Rect
from inklet.three.scene_projection import _vector
from inklet.three.scene_projection import ProjectedPoint


@dataclass(frozen=True)
class Target:
    """Stable semantic identity, literal label and authoritative world point.

    visibility='visible' requires a passing depth sample. 'in_frame' explicitly
    permits occlusion or unknown visibility, represented by a dashed leader.
    """
    id: str
    label: str
    world: tuple[float, float, float]
    visibility: str = 'visible'

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError('Target id must be a non-empty string')
        if not isinstance(self.label, str) or not self.label.strip() or '\n' in self.label:
            raise ValueError('Target label must be non-empty and single-line')
        if self.visibility not in ('visible', 'in_frame'):
            raise ValueError('Target visibility must be visible or in_frame')
        object.__setattr__(self, 'world', _vector(self.world))


@dataclass(frozen=True)
class View:
    """Stable candidate identity and a SceneRender snapshot from the same scene."""
    id: str
    render: object


@dataclass(frozen=True)
class SlotLock:
    """Keep a target in this view, side and row (not an absolute page position)."""
    target: str
    view: str
    side: str
    row: int


@dataclass(frozen=True)
class Length:
    """A length in metres, independent of any illustration transforms."""
    metres: float

    def __post_init__(self):
        if not math.isfinite(self.metres) or self.metres < 0:
            raise ValueError('Length must be finite and non-negative')

    @classmethod
    def between(cls, a, b, *, metres_per_unit):
        scale = _positive(metres_per_unit, 'metres_per_unit')
        return cls(math.dist(_vector(a), _vector(b))*scale)

    def value(self, unit='m'):
        units = {'m': 1., 'cm': .01, 'mm': .001, 'um': 1e-6}
        if unit not in units:
            raise ValueError('Length unit must be m, cm, mm or um')
        return self.metres/units[unit]

    def label(self, unit='m', *, precision=3):
        if type(precision) is not int or not 1 <= precision <= 12:
            raise ValueError('precision must be an integer from 1 to 12')
        return f'{self.value(unit):.{precision}g} {unit}'


def _positive(value, name, *, zero=False):
    value = float(value)
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f'{name} must be finite and {"non-negative" if zero else "positive"}')
    return value


@dataclass(frozen=True)
class Placement:
    target: str
    view: str
    side: str
    row: int
    x: float
    y: float
    target_x: float
    target_y: float
    visible: bool | None
    leader_mm: float

    @property
    def slot(self):
        return self.view, self.side, self.row


@dataclass(frozen=True)
class Plan:
    """A feasible layout or an explicit failure; no partial success rendering."""
    feasible: bool
    views: tuple[str, ...]
    placements: tuple[Placement, ...]
    width: float
    height: float
    image_width: float
    font_pt: float
    score: float | None
    issues: tuple[str, ...]
    alternatives: tuple[dict, ...]
    evaluated: int
    moved: tuple[str, ...]
    _targets: tuple[Target, ...]
    _views: tuple[View, ...]
    _settings: dict
    _labels: tuple[i.Diagram, ...]

    def report(self):
        """JSON-compatible evidence including coordinates, IDs and render keys."""
        return dict(schema='inklet.figure-plan/0.1', experimental=True,
            feasible=self.feasible, views=list(self.views), width_mm=self.width,
            height_mm=self.height, image_width_mm=self.image_width,
            font_pt=self.font_pt, score=self.score, issues=list(self.issues),
            evaluated=self.evaluated, moved=list(self.moved),
            placements=[asdict(p) for p in self.placements],
            alternatives=list(self.alternatives),
            constraints=dict(self._settings),
            total_leader_mm=sum(p.leader_mm for p in self.placements),
            targets=[asdict(t) for t in self._targets],
            sources={v.id: v.render.metadata.get('cache_key') for v in self._views})

    def diagram(self):
        """Selected snapshots and vector labels in a bounded vertical layout."""
        if not self.feasible:
            raise ValueError('Cannot draw an infeasible plan: '+'; '.join(self.issues))
        labels = {t.id: body for t, body in zip(self._targets, self._labels)}
        candidates = {v.id: v.render for v in self._views}
        panels = []
        for name in self.views:
            scene = candidates[name]
            scale = self.image_width/scene.metadata['width_mm']
            height = scene.metadata['height_mm']*scale
            picture = scene.diagram.scaled(scale)
            parts = [picture]
            for p in self.placements:
                if p.view != name:
                    continue
                body = labels[p.target]
                box = body.bbox
                body = body.translated(p.x-(box.width if p.side == 'w' else 0)-box.x0,
                                       p.y-box.center.y)
                sign = -1 if p.side == 'w' else 1
                line = i.as_drawn(i.polyline([
                    (p.target_x, p.target_y), (sign*(self.image_width/2+1.5), p.y),
                    (p.x-sign, p.y)], stroke='#586b6d', stroke_width=.25,
                    stroke_dash=None if p.visible is True else (1., 1.)))
                i.crossing(line, picture)
                dot = i.as_drawn(i.place([((p.target_x, p.target_y),
                    i.marker('circle', size=.8, fill='white', stroke='#172f32', stroke_width=.25))], origin=(0, 0)))
                parts.extend((line, body, dot))
            # One millimetre above and below also contains edge target markers.
            bounds = Rect.from_size(self.width, height+2)
            parts.append(i.Diagram(prim=PhantomPrim(bounds)))
            panel = i.Diagram(children=tuple(parts), envelope_override=Envelope.from_rect(bounds),
                              notes={'research_view': name})
            panels.append(panel)
        result = i.vstack(panels, gap=6)
        result.notes['research_plan'] = self.report()
        return result


def _assignment(costs):
    """Rectangular Hungarian assignment; forbidden edges are infinity.

    Returns a minimum-cost injective row-to-column map, or None. Complexity
    O(rows**2 * columns); deterministic input order breaks equal-cost ties.
    """
    n = len(costs)
    m = len(costs[0]) if n else 0
    if n > m:
        return None
    u, v = [0.]*(n+1), [0.]*(m+1)
    p, way = [0]*(m+1), [0]*(m+1)
    for row in range(1, n+1):
        p[0] = row
        j0 = 0
        minimum, used = [math.inf]*(m+1), [False]*(m+1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m+1):
                if not used[j]:
                    cur = costs[i0-1][j-1]-u[i0]-v[j]
                    if cur < minimum[j]:
                        minimum[j], way[j] = cur, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            if not math.isfinite(delta):
                return None
            for j in range(m+1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    result = [0]*n
    for j in range(1, m+1):
        if p[j]:
            result[p[j]-1] = j-1
    return result


def plan(targets, views, *, width=180., max_height=240., font_pt=8.,
         min_image_width=45., max_views=3, image_scales=(1., .8),
         required_views=(), locks=(), previous=None, view_penalty=80.,
         move_penalty=25., shrink_penalty=80., depth_bias=1e-3,
         max_evaluations=2000):
    """Jointly enumerate view subsets/sizes and solve measured label assignment.

    Hard constraints: page width/height, minimum image width, fixed label size,
    depth visibility, distinct label slots, required views and author slot locks.
    Cost (mm-equivalent): total leader length + view_penalty per view +
    move_penalty per changed prior slot or added/removed prior view +
    shrink_penalty * (1-image_scale) per view. It does not score crossings.

    Two outside label columns use real text measurements; panels stack vertically.
    All panels use the same width, selected from image_scales. Exhaustive only
    within this finite model. Budget overflow raises rather than claiming success.
    """
    targets, views, locks = tuple(targets), tuple(views), tuple(locks)
    if not targets or not views:
        raise ValueError('Provide at least one target and one candidate view')
    if len({t.id for t in targets}) != len(targets):
        raise ValueError('Target ids must be unique')
    if any(not isinstance(v.id, str) or not v.id.strip() for v in views) or len({v.id for v in views}) != len(views):
        raise ValueError('View ids must be non-empty and unique')
    if type(max_views) is not int or max_views < 1:
        raise ValueError('max_views must be a positive integer')
    if type(max_evaluations) is not int or max_evaluations < 1:
        raise ValueError('max_evaluations must be a positive integer')
    width = _positive(width, 'width')
    max_height = _positive(max_height, 'max_height')
    font_pt = _positive(font_pt, 'font_pt')
    min_image_width = _positive(min_image_width, 'min_image_width')
    view_penalty = _positive(view_penalty, 'view_penalty', zero=True)
    move_penalty = _positive(move_penalty, 'move_penalty', zero=True)
    shrink_penalty = _positive(shrink_penalty, 'shrink_penalty', zero=True)
    depth_bias = _positive(depth_bias, 'depth_bias', zero=True)
    scales = tuple(sorted({_positive(s, 'image_scale') for s in image_scales}, reverse=True))
    if not scales or scales[0] > 1:
        raise ValueError('image_scales must contain values in (0, 1]')
    if previous is not None and not previous.feasible:
        raise ValueError('previous must be a feasible Plan')
    target_ids, view_ids = {t.id for t in targets}, {v.id for v in views}
    required = set(required_views)
    lock_map = {}
    for lock in locks:
        if lock.target not in target_ids or lock.view not in view_ids:
            raise ValueError('Locks must reference known target and view ids')
        if lock.side not in ('w', 'e') or type(lock.row) is not int or lock.row < 0:
            raise ValueError('Lock side must be w/e and row a non-negative integer')
        if lock.target in lock_map:
            raise ValueError('Only one lock per target is allowed')
        lock_map[lock.target] = (lock.view, lock.side, lock.row)
        required.add(lock.view)
    if not required <= view_ids:
        raise ValueError('required_views must reference known views')
    # Sort by identity so caller ordering does not change tie resolution.
    targets = tuple(sorted(targets, key=lambda t: t.id))
    views = tuple(sorted(views, key=lambda v: v.id))
    old = {p.target: p.slot for p in previous.placements} if previous else {}
    labels = tuple(i.text(t.label, size=i.pt(font_pt), text_fill='#172f32') for t in targets)
    boxes = [body.bbox for body in labels]
    column = max(b.width for b in boxes)+4
    pitch = max(b.height for b in boxes)+2
    available_width = width-2*column
    ratios = {}
    projected = {}
    for view in views:
        rw = _positive(view.render.metadata['width_mm'], 'render width')
        rh = _positive(view.render.metadata['height_mm'], 'render height')
        ratios[view.id] = rh/rw
        for target in targets:
            try:
                point = view.render.project(target.world, depth_bias=depth_bias)
            except ValueError as error:
                if 'on the perspective camera plane' not in str(error):
                    raise
                # An unusable candidate must not prevent another view from
                # satisfying this target. Its placeholder is never assigned.
                point = ProjectedPoint(i.Vec2(0, 0), 0., False, False)
            projected[view.id, target.id] = point

    settings = dict(max_height_mm=max_height, min_image_width_mm=min_image_width,
        font_family=i.current_theme().font_family,
        label_sizes_mm={t.id: dict(width=b.width, height=b.height) for t, b in zip(targets, boxes)},
        max_views=max_views, image_scales=list(scales), required_views=sorted(required),
        locks=[asdict(lock) for lock in locks], depth_bias_scene_units=depth_bias,
        view_penalty=view_penalty, move_penalty=move_penalty, shrink_penalty=shrink_penalty,
        previous_slots={key: list(value) for key, value in old.items()},
        previous_views=list(previous.views) if previous else [],
        visibility={v.id: {t.id: dict(in_frame=projected[v.id, t.id].in_frame,
            visible=projected[v.id, t.id].visible) for t in targets} for v in views})

    def eligible(t, name):
        p = projected[name, t.id]
        return p.in_frame and (t.visibility == 'in_frame' or p.visible is True)

    issues = []
    if available_width < min_image_width:
        issues.append('Labels leave too little image width; increase page width or shorten labels.')
    missing = [t.id for t in targets if not any(eligible(t, v.id) for v in views)]
    if missing:
        issues.append('No eligible view for targets: '+', '.join(missing)+'. Add a view or revise the explicit visibility requirement.')
    if len(required) > max_views:
        issues.append('Required or locked views exceed max_views; increase it or revise the locks.')
    if len(set(lock_map.values())) != len(lock_map):
        issues.append('Two targets lock the same label slot; revise one lock.')
    for target in targets:
        if target.id in lock_map and not eligible(target, lock_map[target.id][0]):
            issues.append(f'Locked view cannot satisfy visibility for {target.id}; change the view or lock.')

    def failure(messages, evaluated=0):
        return Plan(False, (), (), width, 0., 0., font_pt, None, tuple(messages), (),
                    evaluated, (), targets, views, settings, labels)

    if issues:
        return failure(issues)
    count = sum(math.comb(len(views)-len(required), k-len(required))
                for k in range(max(1, len(required)), min(max_views, len(views))+1))*len(scales)
    if count > max_evaluations:
        raise ValueError(f'Search requires {count} evaluations, exceeding max_evaluations={max_evaluations}')
    solutions, evaluated = [], 0
    mandatory = tuple(v for v in views if v.id in required)
    optional = tuple(v for v in views if v.id not in required)
    for k in range(max(1, len(required)), min(max_views, len(views))+1):
        for extra in combinations(optional, k-len(required)):
            subset = tuple(sorted(mandatory+extra, key=lambda v: v.id))
            names = tuple(v.id for v in subset)
            for fraction in scales:
                evaluated += 1
                iw = available_width*fraction
                height = sum(iw*ratios[name]+2 for name in names)+6*(k-1)
                if iw < min_image_width or height > max_height:
                    continue
                slots = []
                for view in subset:
                    h = iw*ratios[view.id]
                    rows = math.floor(h/pitch)
                    for side in ('w', 'e'):
                        for row in range(rows):
                            x = (-1 if side == 'w' else 1)*(iw/2+3)
                            y = (row-(rows-1)/2)*pitch
                            slots.append((view.id, side, row, x, y))
                costs, lengths = [], []
                for t in targets:
                    row_costs, row_lengths = [], []
                    for name, side, row, x, y in slots:
                        p = projected[name, t.id]
                        scale = iw/next(v.render.metadata['width_mm'] for v in subset if v.id == name)
                        sign = -1 if side == 'w' else 1
                        # Match the actual two-segment leader, excluding 1 mm text clearance.
                        distance = math.hypot(sign*(iw/2+1.5)-p.point.x*scale,
                                              y-p.point.y*scale)+.5
                        allowed = eligible(t, name) and (t.id not in lock_map or lock_map[t.id] == (name, side, row))
                        moved = t.id in old and old[t.id] != (name, side, row)
                        row_costs.append(distance+move_penalty*moved if allowed else math.inf)
                        row_lengths.append(distance)
                    costs.append(row_costs)
                    lengths.append(row_lengths)
                assigned = _assignment(costs)
                if assigned is None:
                    continue
                placements = []
                for index, slot_index in enumerate(assigned):
                    t = targets[index]
                    name, side, row, x, y = slots[slot_index]
                    p = projected[name, t.id]
                    scale = iw/next(v.render.metadata['width_mm'] for v in subset if v.id == name)
                    placements.append(Placement(t.id, name, side, row, x, y,
                        p.point.x*scale, p.point.y*scale, p.visible, lengths[index][slot_index]))
                changed_views = len(set(names)^set(previous.views)) if previous else 0
                score = sum(costs[n][col] for n, col in enumerate(assigned))+view_penalty*k+shrink_penalty*(1-fraction)*k+move_penalty*changed_views
                moved = tuple(p.target for p in placements if p.target in old and p.slot != old[p.target])
                solutions.append((score, names, iw, height, tuple(placements), moved))
    if not solutions:
        return failure(['No layout satisfies page height, image width, visibility and label slots together. Increase page bounds/max_views, add suitable views, or revise locks.'], evaluated)
    solutions.sort(key=lambda s: (s[0], s[1], -s[2]))
    score, names, iw, height, placements, moved = solutions[0]
    alternatives = tuple(dict(score=s[0], views=list(s[1]), image_width_mm=s[2],
                              height_mm=s[3], moved=list(s[5])) for s in solutions[:5])
    return Plan(True, names, placements, width, height, iw, font_pt, score, (), alternatives,
                evaluated, moved, targets, views, settings, labels)
