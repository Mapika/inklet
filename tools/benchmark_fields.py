"""Measure dense vector fields in a fresh process against a source checkout.

Example: .venv/bin/python tools/benchmark_fields.py --source out/release-publish
Peak RSS includes authoring, compilation and PDF export (Linux/macOS only).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--size', type=int, default=200)
    parser.add_argument('--vector', choices=['batched', 'seamless'], default='seamless')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trace-pdf', action='store_true', help='Measure PDF allocations; timings include tracing overhead')
    args = parser.parse_args()
    if args.size < 1:
        parser.error('--size must be positive')
    sys.path.insert(0, str(args.source.resolve() / 'src'))
    import inklet as i
    from inklet.figure import apply_theme
    values = [[(math.sin(x / 17) * math.cos(y / 23) + 1) / 2
               for x in range(args.size)] for y in range(args.size)]
    start = time.perf_counter()
    root = apply_theme(i.panel(79.3, 63.7).matrix(
        values, ramp=i.ramp(['#204060', '#f2c14e']), vector=args.vector).build(), i.theme())
    built = time.perf_counter()
    scene = i.compile_scene(root)
    compiled = time.perf_counter()
    if args.trace_pdf:
        import tracemalloc
        tracemalloc.start()
    pdf = scene.to_pdf()
    exported = time.perf_counter()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = dict(version=i.__version__, size=args.size, vector=args.vector,
                  python=platform.python_version(), platform=platform.platform(),
                  author_seconds=built-start, compile_seconds=compiled-built,
                  pdf_seconds=exported-compiled, total_seconds=exported-start,
                  pdf_bytes=len(pdf), peak_rss_mib=peak/(1024**2 if sys.platform == 'darwin' else 1024))
    if args.trace_pdf:
        report['pdf_peak_allocated_mib'] = tracemalloc.get_traced_memory()[1] / 1024**2
        report['timings_include_tracing'] = True
        tracemalloc.stop()
    svg = scene.to_svg()
    report['svg_sha256'] = hashlib.sha256(svg.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.pdf').write_bytes(pdf)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
