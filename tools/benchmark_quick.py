"""Time the one-call API on big data: build + compile, SVG and PDF size, PNG time.

Each case runs in a fresh process so one case's memory and caches cannot skew
the next. The table is built from the table the caller already holds, so
generating the data is not timed. Usage:

    python tools/benchmark_quick.py                  # every case, table on stdout
    python tools/benchmark_quick.py --only scatter-500k
    python tools/benchmark_quick.py --png-dir DIR    # also save each PNG as DIR/<case>.png
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cases():
    """name -> (points, make_table, make_chart). `make_chart(i, table)` returns a chart."""
    import numpy as np
    import pandas as pd

    def scatter(n):
        def table():
            rng = np.random.default_rng(7)
            return pd.DataFrame({'x': rng.normal(size=n), 'y': rng.normal(size=n),
                                 'group': np.where(rng.random(n) < 0.5, 'control', 'treated')})
        return n, table, lambda i, t: i.scatter(t, x='x', y='y', color='group')

    def line(n):
        def table():
            t = np.linspace(0, 100, n)
            return pd.DataFrame({'t': t, 'signal': np.sin(t) + 0.1 * np.cos(9 * t)})
        return n, table, lambda i, t: i.line(t, x='t', y='signal')

    def hist(n):
        def table():
            return pd.DataFrame({'v': np.random.default_rng(7).normal(size=n)})
        return n, table, lambda i, t: i.hist(t, x='v')

    def facets(per):
        def table():
            rng = np.random.default_rng(7)
            n = 6 * per
            return pd.DataFrame({'x': rng.normal(size=n), 'y': rng.normal(size=n),
                                 'group': np.where(rng.random(n) < 0.5, 'a', 'b'),
                                 'panel': np.repeat([f'p{k}' for k in range(6)], per)})
        return 6 * per, table, lambda i, t: i.scatter(t, x='x', y='y', color='group',
                                                      facet_col='panel', facet_col_wrap=3)

    def heatmap(size):
        def table():
            return pd.DataFrame(np.random.default_rng(7).normal(size=(size, size)))
        return size * size, table, lambda i, t: i.heatmap(t)

    return {
        'scatter-1k': scatter(1_000),
        'scatter-10k': scatter(10_000),
        'scatter-100k': scatter(100_000),
        'scatter-500k': scatter(500_000),
        'line-100k': line(100_000),
        'hist-1M': hist(1_000_000),
        'facets-6x50k': facets(50_000),
        'heatmap-300x300': heatmap(300),
    }


def run_case(name, png_dir=None):
    import inklet as i
    points, make_table, make_chart = _cases()[name]
    table = make_table()
    start = time.perf_counter()
    chart = make_chart(i, table)
    compiled = chart.compile()
    build = time.perf_counter() - start
    start = time.perf_counter()
    svg = compiled.to_svg()
    svg_time = time.perf_counter() - start
    start = time.perf_counter()
    pdf = compiled.to_pdf()
    pdf_time = time.perf_counter() - start
    start = time.perf_counter()
    png = chart.to_png()
    png_time = time.perf_counter() - start
    if png_dir is not None:
        Path(png_dir).mkdir(parents=True, exist_ok=True)
        (Path(png_dir) / f'{name}.png').write_bytes(png)
    return dict(case=name, points=points, build_compile_s=build, svg_s=svg_time,
                svg_bytes=len(svg.encode()), pdf_s=pdf_time, pdf_bytes=len(pdf),
                png_s=png_time, png_bytes=len(png))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--only', action='append', help='run only this case (repeatable)')
    parser.add_argument('--png-dir', help='save each case PNG into this directory')
    parser.add_argument('--child', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        print(json.dumps(run_case(args.child, args.png_dir)))
        return
    names = args.only or list(_cases())
    rows = []
    for name in names:
        command = [sys.executable, __file__, '--child', name]
        if args.png_dir:
            command += ['--png-dir', args.png_dir]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                env=_child_env())
        if result.returncode:
            print(f'{name} failed:\n{result.stderr}', file=sys.stderr)
            continue
        rows.append(json.loads(result.stdout.strip().splitlines()[-1]))
    header = (f"{'case':<17}{'points':>9}{'build+compile s':>17}{'svg MB':>9}"
              f"{'pdf MB':>9}{'svg s':>8}{'pdf s':>8}{'png s':>8}")
    print(header)
    print('-' * len(header))
    for r in rows:
        print(f"{r['case']:<17}{r['points']:>9,}{r['build_compile_s']:>17.2f}"
              f"{r['svg_bytes'] / 1e6:>9.2f}{r['pdf_bytes'] / 1e6:>9.2f}{r['svg_s']:>8.2f}"
              f"{r['pdf_s']:>8.2f}{r['png_s']:>8.2f}")


def _child_env():
    env = dict(os.environ)
    # The package under test is the one next to this script, whatever PYTHONPATH says.
    env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    return env


if __name__ == '__main__':
    main()
