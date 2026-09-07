"""Research solver contracts, using real saved-camera projection without Blender."""
from dataclasses import replace
import itertools
import json
import math
import random
import struct

import pytest
import inklet as i
from inklet.experimental.figure_planner import Length, SlotLock, Target, View, _assignment, plan


def view(name='front', *, surface=10., depth=True, height=80., shift=0.):
    metadata = dict(width_mm=100., height_mm=height, pixels=[10, 10], cache_key=name,
        projection=dict(type='ORTHO', world_to_camera=[[1,0,0,shift],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
                        bounds=[-2,2,-2,2], near=.1, far=20))
    passes = {'depth': i.ScenePass('depth', (10,10), 1, 100, height, struct.pack('<100f', *([surface]*100)))} if depth else {}
    return View(name, i.SceneRender(i.spacer(100, height), metadata, False, passes))


def test_assignment_matches_exhaustive_small_problems():
    rng = random.Random(7)
    for n, m in ((1,1), (2,3), (3,5), (4,4)):
        for _ in range(30):
            costs = [[rng.randrange(10) if rng.random() > .2 else math.inf for _ in range(m)] for _ in range(n)]
            expected = min(sum(costs[r][c] for r, c in enumerate(cols)) for cols in itertools.permutations(range(m), n))
            result = _assignment(costs)
            if math.isinf(expected):
                assert result is None
            else:
                assert len(set(result)) == n
                assert sum(costs[r][c] for r, c in enumerate(result)) == expected
    assert _assignment([[1], [2]]) is None


def test_visibility_unknown_occluded_and_out_of_frame_are_distinct():
    targets = (Target('a', 'Alpha', (0,0,-3)),)
    for v in (view(surface=2), view(depth=False), view(shift=5)):
        result = plan(targets, [v])
        assert not result.feasible
        assert 'No eligible view for targets: a' in result.issues[0]
        with pytest.raises(ValueError, match='infeasible'):
            result.diagram()
    allowed = replace(targets[0], visibility='in_frame')
    result = plan([allowed], [view(depth=False)])
    assert result.feasible and result.placements[0].visible is None
    assert 'stroke-dasharray' in i.to_svg(result.diagram())
    assert not plan([allowed], [view(shift=5)]).feasible


def test_joint_search_reconsiders_a_view_that_does_not_fit_the_page():
    target = Target('a', 'Alpha', (0,0,-1))
    tall, wide = view('a-tall', height=400), view('b-wide', height=50)
    assert not plan([target], [tall], max_height=80).feasible
    result = plan([target], [tall, wide], max_height=80)
    assert result.feasible and result.views == ('b-wide',)
    assert result.height <= 80


def test_measured_labels_slots_export_and_physical_bounds():
    targets = [Target(str(n), 'A long measured label '+str(n), (n/20, n/30, -1)) for n in range(12)]
    result = plan(targets, [view()], width=170, font_pt=9)
    assert result.feasible
    assert len({p.slot for p in result.placements}) == len(targets)
    layer = result.diagram()
    assert layer.width == pytest.approx(result.width)
    assert layer.height == pytest.approx(result.height)
    svg = i.to_svg(layer)
    assert 'A long measured label' in svg and '<text' in svg
    assert i.to_pdf(layer).startswith(b'%PDF')
    for side in ('w', 'e'):
        placements = sorted((p for p in result.placements if p.side == side), key=lambda p: p.y)
        for a, b in zip(placements, placements[1:]):
            label_height = i.text(targets[int(a.target)].label, size=i.pt(9)).height
            assert b.y-a.y >= label_height+1.99
    json.dumps(result.report(), allow_nan=False)
    assert not plan(targets, [view()], width=60).feasible


def test_author_locks_are_hard_constraints_and_conflicts_are_reported():
    a, b = Target('a', 'A', (0,0,-1)), Target('b', 'B', (1,0,-1))
    result = plan([a,b], [view()], locks=[SlotLock('a','front','e',0)])
    assert result.feasible
    assert next(p for p in result.placements if p.target == 'a').slot == ('front','e',0)
    result = plan([a,b], [view()], locks=[SlotLock('a','front','e',0), SlotLock('b','front','e',0)])
    assert not result.feasible and 'same label slot' in ' '.join(result.issues)
    assert not plan([a], [view()], locks=[SlotLock('a','front','e',10000)]).feasible
    assert not plan([a], [view('a'),view('b')], required_views=['a','b'], max_views=1).feasible


def test_revision_preserves_identity_and_prior_slots_when_feasible():
    targets = [Target('a', 'First', (-1,.4,-1)), Target('b', 'Second', (1,-.4,-1))]
    before = plan(targets, [view()], image_scales=(1,))
    revised = [replace(t, label=t.label+' revised', world=(-t.world[0], t.world[1], -1)) for t in targets]
    after = plan(revised, [view()], previous=before, move_penalty=1000, image_scales=(1,))
    assert after.feasible and not after.moved
    assert {p.target: p.slot for p in before.placements} == {p.target: p.slot for p in after.placements}
    fresh = plan(revised, [view()], image_scales=(1,))
    assert any(a.slot != b.slot for a,b in zip(before.placements, fresh.placements))
    assert after.report()['targets'][0]['label'] == 'First revised'


def test_ties_are_deterministic_and_budget_is_not_silently_truncated():
    targets = [Target('a','A',(0,0,-1)), Target('b','B',(1,0,-1))]
    views = [view('a'),view('b')]
    first = plan(targets, views)
    second = plan(reversed(targets), reversed(views))
    assert first.report() == second.report()
    with pytest.raises(ValueError, match='exceeding max_evaluations'):
        plan(targets, views, max_evaluations=1)


def test_length_conversion_requires_units_and_does_not_follow_display_transforms():
    length = Length.between((0,0,0), (3,4,0), metres_per_unit=.001)
    assert length.value('mm') == pytest.approx(5)
    assert length.label('mm') == '5 mm'
    # Illustration geometry is separate; rebuilding it cannot mutate a measurement.
    endpoints = [(0,0,0), (3,4,0)]
    fixed = Length.between(*endpoints, metres_per_unit=1)
    endpoints[1] = (30,40,0)
    assert fixed.label('m') == '5 m'
    with pytest.raises(ValueError): fixed.value('s')
    with pytest.raises(ValueError): Length(math.nan)
    with pytest.raises(ValueError): Length.between(*endpoints, metres_per_unit=0)


@pytest.mark.parametrize('options', [dict(width=math.nan), dict(max_height=-1), dict(font_pt=0),
    dict(max_views=True), dict(image_scales=()), dict(image_scales=(1.1,)), dict(depth_bias=-1),
    dict(view_penalty=-1), dict(max_evaluations=0), dict(required_views=('missing',)),
    dict(locks=(SlotLock('missing','front','w',0),)), dict(locks=(SlotLock('a','front','w',-1),))])
def test_invalid_requests(options):
    with pytest.raises(ValueError): plan([Target('a','A',(0,0,-1))], [view()], **options)


def test_duplicate_and_invalid_semantic_ids():
    target = Target('a','A',(0,0,-1))
    with pytest.raises(ValueError): plan([target,target], [view()])
    with pytest.raises(ValueError): plan([target], [view(),view()])
    with pytest.raises(ValueError): Target('', 'A', (0,0,0))
    with pytest.raises(ValueError): Target('a', 'A\nB', (0,0,0))
    with pytest.raises(ValueError): Target('a', 'A', (0,math.inf,0))


def test_camera_plane_candidate_does_not_abort_other_views():
    perspective = view('perspective')
    perspective.render.metadata['projection']['type'] = 'PERSP'
    alternate = view('alternate')
    alternate.render.metadata['projection']['world_to_camera'][2][3] = -3
    result = plan([Target('a','A',(0,0,0))], [perspective, alternate])
    assert result.feasible and result.views == ('alternate',)


def test_preview_guide_examples_with_saved_snapshot(tmp_path, monkeypatch):
    from pathlib import Path
    import re
    guide = Path(__file__).resolve().parents[1]/'docs/research-preview.md'
    snapshot = view().render
    snapshot.metadata['landmarks'] = {'probe': {'world': [0,0,-1]}}
    monkeypatch.setattr(i, 'render_blend', lambda *a, **kw: snapshot)
    monkeypatch.chdir(tmp_path)
    namespace = dict(updated_targets=[Target('probe','Temperature probe',(.5,0,-1))],
                     updated_views=[View('Overview',snapshot), View('Detail',snapshot)])
    for block in re.findall(r'^```python\n(.*?)^```', guide.read_text(), re.M|re.S):
        exec(block, namespace)
    assert (tmp_path/'planned.svg').is_file()
    assert (tmp_path/'planned.pdf').read_bytes().startswith(b'%PDF')
    assert namespace['revised'].feasible
    assert namespace['dimension_text'] == '8 m'
    assert namespace['caption_text'] == '8000 mm'


def test_draw_uses_the_measured_labels_even_if_the_author_changes_theme(monkeypatch):
    result = plan([Target('a','Measured label',(0,0,-1))], [view()])
    def unexpected(*args, **kwargs):
        raise AssertionError('A solved plan must not reshape labels against a new theme')
    monkeypatch.setattr(i, 'text', unexpected)
    layer = result.diagram()
    assert layer.width == pytest.approx(result.width)
    assert 'Measured label' in i.to_svg(layer)


def test_region_rejects_visible_anchor_when_surface_is_hidden_or_unknown():
    from inklet.experimental.figure_planner import Region
    region = Region(((0,0,-1), (.5,0,-3), (1,0,-3), (1.5,0,-3)), .75, 1)
    target = Target('a','Part',(0,0,-1), region=region)
    result = plan([target], [view(surface=2)])
    assert not result.feasible
    evidence = result.report()['constraints']['regions']['front']['a']
    assert evidence['visible_fraction'] == .25
    assert evidence['visible_samples'] == 1
    assert plan([replace(target, region=replace(region, min_visible_fraction=.25))], [view(surface=2)]).feasible is False  # only one visible point has zero span
    unknown = plan([replace(target, visibility='in_frame')], [view(depth=False)])
    assert not unknown.feasible
    assert unknown.report()['constraints']['regions']['front']['a']['unknown_samples'] == 4


def test_region_span_constrains_image_size_and_out_of_frame_samples_count():
    from inklet.experimental.figure_planner import Region
    target = Target('a','A',(0,0,-1), region=Region(((-1,0,-1),(1,0,-1),(9,0,-1)), 2/3, 70))
    result = plan([target], [view()], width=180, image_scales=(1.,.5))
    assert result.feasible
    region = result.report()['constraints']['selected_regions']['a']
    assert region['visible_fraction'] == pytest.approx(2/3)
    assert region['visible_span_mm'] >= 70
    assert not plan([target], [view()], width=180, image_scales=(.5,)).feasible


def test_crossing_refinement_reduces_cost_and_respects_forbidden_edges():
    from inklet.experimental.planner_geometry import refine, leaders_cross
    up = ((0,0),(2,2),(3,2))
    down = ((0,2),(2,0),(3,0))
    straight0 = ((0,0),(2,0),(3,0))
    straight1 = ((0,2),(2,2),(3,2))
    assert leaders_cross(up, down)
    assert not leaders_cross(straight0, straight1)
    assert not leaders_cross(((0,0),(1,1)), ((1,1),(2,0)))
    assert not leaders_cross(((0,0),(2,0)), ((1,0),(3,0)))
    lines = [[up,straight0],[straight1,down]]
    assignment, info = refine([[0,2],[2,0]], [0,1], lines, ['v','v'], 10, 4)
    assert assignment == [1,0]
    assert info == dict(initial_crossings=1,crossings=0,steps=1,status='local_optimum')
    locked, info = refine([[0,math.inf],[math.inf,0]], [0,1], lines, ['v','v'], 10, 4)
    assert locked == [0,1] and info['crossings'] == 1
    assert refine([[0,2],[2,0]], [0,1], lines, ['v','v'], 10, 0)[1]['status'] == 'step_limit'
    assert refine([[0,2],[2,0]], [0,1], lines, ['v','other'], 10, 4)[1]['crossings'] == 0


def test_crossing_search_can_move_to_a_free_slot():
    from inklet.experimental.planner_geometry import refine
    lines = [[((0,0),(2,2)),((0,0),(2,0)),((0,0),(2,-1))],
             [((0,2),(2,2)),((0,2),(2,0)),((0,2),(2,-1))]]
    assigned, info = refine([[0,math.inf,1],[math.inf,0,math.inf]], [0,1], lines, ['v']*3, 10, 4)
    assert assigned == [2,1] and info['crossings'] == 0


def test_crossing_penalty_can_override_soft_history_but_not_author_lock():
    a,b = Target('a','A',(-1,1,-1)),Target('b','B',(-1,-1,-1))
    before = plan([a,b], [view()], locks=[SlotLock('a','front','e',2), SlotLock('b','front','e',10)], image_scales=(1,))
    targets = [replace(a,world=b.world),replace(b,world=a.world)]
    options = dict(previous=before, locks=[SlotLock('a','front','e',2)], image_scales=(1,), move_penalty=1000)
    plain = plan(targets,[view()],**options)
    improved = plan(targets,[view()],**options,crossing_penalty=5000)
    assert plain.report()['crossing_pairs'] == [('a','b')]
    assert improved.report()['crossing_pairs'] == []
    assert improved.placements[0].slot == ('front','e',2)
    assert improved.report()['constraints']['assignment_method'] == 'local_refinement'


def test_revision_displacement_measures_page_positions_even_with_same_slots():
    target = Target('a','Alpha',(0,0,-1))
    before = plan([target],[view()],image_scales=(1,))
    p = before.placements[0]
    after = plan([target],[view()], width=150, image_scales=(1,), previous=before,
                 locks=[SlotLock(p.target,p.view,p.side,p.row)])
    assert not after.moved
    expected = math.dist(before.label_positions()['a'],after.label_positions()['a'])
    assert expected > 0
    assert after.report()['constraints']['revision_displacement_mm']['a'] == pytest.approx(expected)


@pytest.mark.parametrize('samples,fraction,span', [([],1,1), ([(0,0,0)]*2,1,1),
    ([(0,0,0),(1,0,0)],0,1), ([(0,0,0),(1,0,0)],1.1,1),
    ([(0,0,0),(1,0,0)],1,math.nan), ([(0,0,0),(1,0,0)],1,0)])
def test_invalid_region_requests(samples, fraction, span):
    from inklet.experimental.figure_planner import Region
    with pytest.raises(ValueError): Region(samples,fraction,span)


def test_invalid_refinement_controls():
    for options in (dict(crossing_penalty=-1),dict(crossing_penalty=math.nan),dict(max_refinement_steps=-1),dict(max_refinement_steps=True)):
        with pytest.raises(ValueError): plan([Target('a','A',(0,0,-1))],[view()],**options)


def test_random_refinement_never_increases_full_objective_or_breaks_constraints():
    from inklet.experimental.planner_geometry import leaders_cross, refine
    rng = random.Random(29)
    for _ in range(25):
        n,m = 4,6
        costs = [[rng.randrange(20) if rng.random()>.15 else math.inf for _ in range(m)] for _ in range(n)]
        assigned = _assignment(costs)
        if assigned is None: continue
        targets = [(rng.random()*10,rng.random()*10) for _ in range(n)]
        ends = [(15,rng.random()*10) for _ in range(m)]
        lines = [[(t,end) for end in ends] for t in targets]
        def objective(a):
            return sum(costs[r][s] for r,s in enumerate(a))+11*sum(leaders_cross(lines[r][a[r]],lines[s][a[s]]) for r in range(n) for s in range(r+1,n))
        improved,info = refine(costs,assigned,lines,['v']*m,11,3)
        assert objective(improved) <= objective(assigned)
        assert len(set(improved)) == n
        assert all(math.isfinite(costs[r][s]) for r,s in enumerate(improved))
        assert info['steps'] <= 3
        assert refine(costs,assigned,lines,['v']*m,11,3) == (improved,info)


def test_report_mutations_do_not_change_stored_evidence():
    result=plan([Target('a','A',(0,0,-1))],[view()])
    report=result.report()
    report['constraints']['visibility']['front']['a']['visible']=False
    report['alternatives'][0]['score']=-1
    assert result.report()['constraints']['visibility']['front']['a']['visible'] is True
    assert result.report()['alternatives'][0]['score'] >= 0


def test_region_review_markers_preserve_bounds_and_show_hidden_samples():
    from inklet.experimental.figure_planner import Region
    target=Target('a','A',(0,0,-1),region=Region(((-1,0,-1),(1,0,-1),(0,0,-3)),.6,5))
    result=plan([target],[view(surface=2)])
    normal=result.diagram();review=result.diagram(show_regions=True)
    assert review.width == pytest.approx(normal.width)
    assert review.height == pytest.approx(normal.height)
    svg=i.to_svg(review)
    assert '#168276' in svg and '#ad6b25' in svg
    with pytest.raises(ValueError): result.diagram(show_regions='yes')


def test_region_guide_example_runs_against_saved_projection():
    from pathlib import Path
    import re
    candidate=view()
    candidate.render.metadata['projection']['world_to_camera'][2][3]=-3
    namespace={'views':[candidate]}
    guide=Path(__file__).resolve().parents[1]/'docs/research-study.md'
    for block in re.findall(r'^```python\n(.*?)^```',guide.read_text(),re.M|re.S):
        exec(block,namespace)
    assert namespace['result'].feasible
