"""Rebuild the experimental lab planning comparison and machine-readable evidence.

Run from the repository with: python examples/research_figure_planner.py
Requires Blender and inklet[render]. Planning itself needs only core Inklet.
"""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import time

import inklet as i
from inklet.experimental.figure_planner import Length, SlotLock, Target, View, plan
from inklet.three.blender import find_blender
from v3_complex_scene import create_lab, LABELS

ROOT = Path(__file__).resolve().parents[1]
CAMERAS = ('Overview', 'Process', 'Analysis', 'Services')
# Scene units are metres. The transfer landmark lies on the tube centreline;
# 4 cm tolerance covers its 3.2 cm radius, with sampling uncertainty recorded.
DEPTH_BIAS = .04


def build_scene(source, output, revision, blender):
    process = subprocess.run([str(blender), '--background', '--factory-startup',
        '--disable-autoexec', '--python-exit-code', '1', '--python',
        str(ROOT/'examples/blender/research_lab_views.py'), '--',
        str(source), str(output), revision], capture_output=True, text=True, timeout=90)
    if process.returncode:
        raise RuntimeError(process.stdout[-6000:]+process.stderr[-6000:])


def render_views(path, blender, quality):
    landmarks = {name: 'Target '+name for name in LABELS}
    landmarks.update(width_left='Width left', width_right='Width right')
    with i.RenderQueue(max_workers=2, max_gpu_jobs=1) as queue:
        jobs = {name: queue.submit(path, camera=name, width=120, height=87,
            engine='CYCLES', quality=quality, passes=('depth',), landmarks=landmarks,
            blender=blender) for name in CAMERAS}
        return tuple(View(name, jobs[name].result()) for name in CAMERAS)


def targets_for(views):
    points = views[0].render.metadata['landmarks']
    return tuple(Target(name.lower().replace(' ', '-'), name, points[name]['world']) for name in LABELS)


def coverage_first(targets, views, **options):
    """Independent baseline: fewest covering views, tie by ID, then place labels.

    It never revisits its camera choice after examining measured page constraints.
    Shares the joint planner's visibility predicate, candidate bank and label solver.
    """
    ordered = sorted(views, key=lambda v: v.id)
    for count in range(1, options.get('max_views', 3)+1):
        for subset in itertools.combinations(ordered, count):
            if not set(options.get('required_views', ())) <= {v.id for v in subset}:
                continue
            if all(any(v.render.project(t.world, depth_bias=DEPTH_BIAS).visible is True for v in subset) for t in targets):
                return plan(targets, subset, **(options | {'required_views': tuple(v.id for v in subset)}))
    return plan(targets, views, **options)


def export_plan(result, path):
    if not result.feasible:
        return
    doc = i.document(width=result.width+10, margin=5)
    doc.add('scene-plan', result.diagram())
    figure = doc.compile()
    figure.export(path, dpi=150)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/research-preview')
    parser.add_argument('--blender', type=Path)
    parser.add_argument('--quality', choices=('draft', 'preview', 'final'), default='preview')
    parser.add_argument('--rebuild', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    blender = find_blender(args.blender).path
    source = args.output/'laboratory.blend'
    if not source.exists() or args.rebuild:
        (args.output/'creation.log').write_text(create_lab(source, blender))
    renders = {}
    for revision in ('original', 'moved-gas'):
        path = args.output/(revision+'.blend')
        if not path.exists() or args.rebuild:
            build_scene(source, path, revision, blender)
        renders[revision] = render_views(path, blender, args.quality)
        print('Rendered', revision, flush=True)
    original, revised = renders['original'], renders['moved-gas']
    targets, new_targets = targets_for(original), targets_for(revised)
    points = original[0].render.metadata['landmarks']
    footprint = Length.between(points['width_left']['world'], points['width_right']['world'], metres_per_unit=1)
    options = dict(width=180, max_height=240, max_views=3, depth_bias=DEPTH_BIAS,
                   required_views=('Overview',))
    start = time.perf_counter()
    joint = plan(targets, original, **options)
    if not joint.feasible:
        raise RuntimeError(json.dumps(joint.report(), indent=2))
    # Preserve a low-numbered slot that also exists on the narrower page.
    locked = min((p for p in joint.placements if p.view == 'Overview'), key=lambda p: p.row)
    lock = SlotLock(locked.target, locked.view, locked.side, locked.row)
    cases = {
        'overview-only': plan(targets, original[:1], **options),
        'coverage-first': coverage_first(targets, original, **options),
        'joint': joint,
        'revised-with-lock': plan(new_targets, revised, **(options | {'width': 155}), previous=joint, locks=(lock,)),
        'revised-without-history': plan(new_targets, revised, **(options | {'width': 155})),
        'too-narrow': plan(targets, original, **(options | {'width': 70})),
        'strict-depth': plan(targets, original, **(options | {'depth_bias': .001})),
    }
    elapsed = time.perf_counter()-start
    visibility = {v.id: {t.id: v.render.project(t.world, depth_bias=DEPTH_BIAS).visible for t in targets} for v in original}
    prior_slots = {p.target: p.slot for p in joint.placements}
    changes = {name: [p.target for p in cases[name].placements if p.slot != prior_slots[p.target]]
               for name in ('revised-with-lock', 'revised-without-history')}
    # One measured value is reused in a schematic and a caption. The separately
    # moved gas assembly does not change this authoritative floor measurement.
    evidence = dict(experimental=True, depth_bias_scene_units=DEPTH_BIAS,
        scene_metres_per_unit=1, locked_slot=vars(lock), planning_seconds=elapsed,
        footprint={'metres': footprint.value('m'), 'millimetres': footprint.value('mm')},
        revision_slot_changes=changes,
        renders={revision: {v.id: dict(cache_key=v.render.metadata['cache_key'],
            pixels=v.render.metadata['pixels'], blender=v.render.metadata['blender'],
            execution=v.render.metadata['execution'], quality=args.quality) for v in views}
            for revision, views in renders.items()},
        visibility=visibility, cases={name: result.report() for name, result in cases.items()})
    (args.output/'comparison.json').write_text(json.dumps(evidence, indent=2)+'\n')
    for name, result in cases.items():
        export_plan(result, args.output/name)
        print(name, result.feasible, result.views, result.issues, flush=True)
    revised_plan = cases['revised-with-lock']
    if not revised_plan.feasible:
        raise RuntimeError('The revision is infeasible; inspect comparison.json')
    doc = i.document(width=380, columns=2, margin=8, gap=10)
    doc.add('title', i.text('Research preview / joint figure planning', size=i.pt(23)), colspan=2)
    doc.add('subtitle', i.text('Authored cameras, measured labels, depth-tested targets and explicit author constraints.', size=i.pt(10)), colspan=2)
    for col, (name, result) in enumerate((('Original / 180 mm', joint), ('Moved gas supply / 155 mm', revised_plan))):
        doc.add('heading-'+str(col), i.text(name, size=i.pt(12)), row=2, column=col)
        doc.add('plan-'+str(col), result.diagram(), row=3, column=col)
        doc.add('status-'+str(col), i.text(f'{len(result.placements)}/12 targets assigned; {len(result.views)} views; labels 8 pt', size=i.pt(9)), row=4, column=col)
    schematic = i.dimension((0, 0), (75, 0), footprint.label('m'), size=i.pt(9), stroke_width=.25)
    doc.add('measurement', schematic, colspan=2)
    doc.add('caption', i.text('Floor width: '+footprint.label('mm', precision=6)+'. Measurement shared with the schematic above.', size=i.pt(9)), colspan=2)
    doc.add('lock', i.text(f'Author lock: {locked.target}, {locked.view}, {locked.side}, row {locked.row}. Camera Overview retained.', size=i.pt(9)), colspan=2)
    doc.add('limits', i.text('Point visibility uses a declared 4 cm depth tolerance. Crossings and object recognition are not optimized.', size=i.pt(9)), colspan=2)
    figure = doc.compile()
    print(figure.report())
    figure.export(args.output, dpi=150)


if __name__ == '__main__':
    main()
