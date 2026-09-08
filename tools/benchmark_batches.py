"""Measure vector scatter authoring, scene compilation and native export.

Run each sample in a fresh process. --source accepts a checkout or an archive
containing src/. --compile-only makes million-point storage tests practical
without conflating them with vector serialization and viewer performance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--count', type=int, default=10000)
    parser.add_argument('--compile-only', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.count < 1: parser.error('--count must be positive')
    sys.path.insert(0, str(args.source.resolve()/'src'))
    import inklet as i
    from inklet.figure import apply_theme
    start = time.perf_counter()
    panel = i.panel(80, 50, x=(0, 1), y=(0, 1), clip=False)
    panel.scatter((((k*0.6180339887498949) % .98+.01,
                    (k*0.4142135623730951) % .98+.01) for k in range(args.count)),
                  size=.4, color='#245b8a', fill_opacity=.35)
    root = apply_theme(panel.build(), i.theme())
    built = time.perf_counter()
    scene = i.compile_scene(root)
    compiled = time.perf_counter()
    report = dict(count=args.count, python=platform.python_version(), platform=platform.platform(),
                  author_seconds=built-start, compile_seconds=compiled-built,
                  nodes=scene.stats['visited_nodes'], geometry=scene.stats['new_geometry'])
    report['packed_bytes'] = sum(len(n.prim.data) for n in root.walk()
                                 if type(n.prim).__name__ == 'MarkerBatchPrim')
    if not args.compile_only:
        start = time.perf_counter(); svg = scene.to_svg(); end = time.perf_counter()
        report.update(svg_seconds=end-start, svg_bytes=len(svg.encode()))
        start = time.perf_counter(); pdf = scene.to_pdf(); end = time.perf_counter()
        report.update(pdf_seconds=end-start, pdf_bytes=len(pdf))
    report['peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    digest = hashlib.sha256()
    for path in sorted((args.source/'src').rglob('*.py')):
        digest.update(path.relative_to(args.source/'src').as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    report['source_sha256'] = digest.hexdigest()
    result = json.dumps(report, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    print(result)


if __name__ == '__main__': main()
