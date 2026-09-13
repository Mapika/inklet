"""Compare core tree operations in fresh processes against --source checkouts.

Timings exclude imports and recipe setup. Garbage collection stays enabled;
compare total_seconds because collection can move between individual phases.
SVG hashes and bounds let callers verify unchanged output across revisions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def measure():
    import inklet as i
    from inklet.core import RectPrim, resolve
    from inklet.figure import apply_theme
    cases = {}
    for name, count, kind in [('rectangles', 10000, 'mark'), ('labels', 2000, 'text')]:
        primitive = RectPrim(2, 3) if kind == 'mark' else i.text('Measured label', size=2).prim
        root = i.Diagram(children=tuple(i.Diagram(prim=primitive,kind=kind).translated(
            j % 100 * 3, j // 100 * 4) for j in range(count)))
        times = {}
        def timed(key, operation):
            start = time.perf_counter()
            result = operation()
            times[key] = time.perf_counter() - start
            return result
        themed = timed('theme_seconds', lambda: apply_theme(root, i.current_theme()))
        scene = timed('compile_seconds', lambda: i.compile_scene(themed))
        bounds = timed('bounds_seconds', lambda: scene.root.painted_bounds)
        timed('resolve_seconds', lambda: resolve(themed))
        revision = timed('revision_seconds', lambda: i.compile_scene(themed, previous=scene))
        assert revision.root is scene.root and not revision.changes
        svg = timed('svg_seconds', lambda: scene.to_svg(text='embed'))
        cases[name] = {**times, 'total_seconds': sum(times.values()), 'nodes': scene.stats['visited_nodes'],
                       'bounds': [bounds.x0, bounds.y0, bounds.x1, bounds.y1],
                       'svg_sha256': hashlib.sha256(svg.encode()).hexdigest()}
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=5)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    source = args.source.resolve() / 'src'
    if not (source / 'inklet' / '__init__.py').is_file():
        parser.error('--source must contain src/inklet')
    if args.worker:
        sys.path.insert(0, str(source))
        import inklet
        if not Path(inklet.__file__).resolve().is_relative_to(source):
            raise RuntimeError('benchmark imported Inklet outside the requested source')
        print(json.dumps(measure()))
        return
    runs = []
    for _ in range(args.repeat):
        result = subprocess.run([sys.executable, __file__, '--source', str(args.source),
            '--output', str(args.output), '--worker'], capture_output=True, text=True, check=True)
        runs.append(json.loads(result.stdout))
    medians = {name: {key: statistics.median(run[name][key] for run in runs)
        for key in runs[0][name] if key.endswith('_seconds')} for name in runs[0]}
    digest = hashlib.sha256()
    for path in sorted((args.source.resolve() / 'src').rglob('*.py')):
        digest.update(path.relative_to(args.source.resolve() / 'src').as_posix().encode()
                      + b'\0' + path.read_bytes() + b'\0')
    report = dict(schema='inklet.core-benchmark/1', repeat=args.repeat,
                  source_sha256=digest.hexdigest(), python=platform.python_version(), platform=platform.platform(), runs=runs, median=medians)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(medians, indent=2))


if __name__ == '__main__':
    main()
