"""Enforce elapsed-time budgets for a complete local figure-project lifecycle."""
from pathlib import Path
import argparse
import json
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'examples')]
import inklet
from inklet.project import FigureProject
import project_workflow as recipe


def measure(root, width):
    stages = {}
    def timed(name, action):
        start = time.perf_counter()
        value = action()
        stages[name] = time.perf_counter()-start
        return value
    inputs = recipe.write_inputs(root/'inputs')
    project = timed('build', lambda: recipe.project(inputs))
    original = project.editor.figure.to_svg()
    timed('edit', lambda: project.editor.command('edit', {'path': '/diagram/a', 'placement': {'x': 8}}))
    edited = project.editor.figure.to_svg()
    timed('undo', lambda: project.editor.command('undo'))
    assert project.editor.figure.to_svg() == original
    timed('redo', lambda: project.editor.command('redo'))
    assert project.editor.figure.to_svg() == edited
    targets = timed('select', lambda: project.select('image', ['region-a']))
    assert targets['measurements'] == ('sample-a',)
    bundle = timed('save', lambda: project.save(root/'bundle', asset_root=inputs))
    reopened = timed('reopen', lambda: FigureProject.open(bundle, recipe.recipe))
    assert reopened.editor.figure.to_svg() == edited and reopened.selected == ('a',)
    revised = recipe.write_inputs(root/'revised', revised=True)
    newer, report = timed('revise', lambda: reopened.revise(recipe.recipe(revised),
        assets=recipe.manifest(revised), identities=recipe.inputs(revised)[2]))
    assert report['removed_selection'] == [] and newer.selected == ('a',)
    assert newer.editor.figure.to_svg() != edited and reopened.editor.figure.to_svg() == edited
    timed('resize', lambda: newer.editor.command('edit', {'path': '/', 'page': {'width': width}}))
    assert abs(newer.editor.figure.root.bbox.width-width) < 1e-8
    figure = newer.editor.figure
    svg = timed('svg', figure.to_svg)
    pdf = timed('pdf', figure.to_pdf)
    assert '<svg' in svg and pdf.startswith(b'%PDF')
    stages['total'] = sum(stages.values())
    return stages


def check_budgets(records, limits):
    if set(records) != set(limits):
        raise ValueError('Project budget stages must match measured stages exactly')
    checks = []
    for stage, value in records.items():
        limit = limits[stage]
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 0 < limit < float('inf'):
            raise ValueError(f'Invalid project budget: {stage}')
        checks.append(dict(stage=stage, seconds=value, limit=limit, passed=0 <= value <= limit))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/project-benchmark.json')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--budgets', type=Path, default=ROOT/'tests/performance/project-budgets.json')
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('repeat must be positive')
    budgets = json.loads(args.budgets.read_text())
    results = []
    for width in (140, 190):
        runs = []
        for _ in range(args.repeat):
            with tempfile.TemporaryDirectory(prefix='inklet-project-benchmark-') as folder:
                runs.append(measure(Path(folder), width))
        medians = {key: statistics.median(run[key] for run in runs) for key in runs[0]}
        checks = check_budgets(medians, budgets['seconds'])
        results.append(dict(width_mm=width, runs=runs, checks=checks))
        print(width, medians, flush=True)
    report = dict(version=inklet.__version__, python=sys.version, platform=platform.platform(),
        method='Median elapsed seconds; same process, fresh project and temporary files each run. Input fixture creation and validation excluded; revision includes recipe reconstruction. Filesystem/font caches may be warm.',
        budgets=budgets, cases=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    return int(any(not check['passed'] for case in results for check in case['checks']))


if __name__ == '__main__':
    raise SystemExit(main())
