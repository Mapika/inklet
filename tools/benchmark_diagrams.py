"""Measure graph layout and routing against a selected source checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def measure():
    import inklet as i
    from inklet.core import Rect
    from inklet.links.link import _drop_contained, link_flags
    i.use_theme('nature')
    # Distinct nested artwork makes each graph node contribute eight obstacles.
    nodes = {}
    for rank in range(6):
        for lane in range(6):
            body = i.vstack([i.text(f'{rank}.{lane} / {j}',size=2) for j in range(6)],gap=.5)
            nodes[rank,lane] = i.box(body,width=18,height=24)
    # Graph keys are strings; tuple node keys are intentionally not public API.
    nodes = {f'{rank}-{lane}':node for (rank,lane),node in nodes.items()}
    edges = [(f'{rank}-{lane}',f'{rank+1}-{lane}') for rank in range(5) for lane in range(6)]
    edges += [(f'{rank}-{lane}',f'{rank+2}-{(lane+1)%6}') for rank in range(4) for lane in range(6)]
    start=time.perf_counter()
    graph = i.graph(nodes,edges,direction='right',rank_gap=18,gap=8,route='avoid')
    layout=time.perf_counter()-start
    fig=i.figure(width=260)
    graph.add_to(fig)
    start=time.perf_counter();root,_=fig.build();routing=time.perf_counter()-start
    start=time.perf_counter();svg=fig.to_svg();export=time.perf_counter()-start
    assert fig.to_svg()==svg
    flags=[flag for node in root.walk() for flag in link_flags(node)]
    boxes=[Rect(x*20,y*20,x*20+12,y*20+12) for x in range(15) for y in range(15)]
    obstacles=boxes+[b.pad(-2) for b in boxes]
    start=time.perf_counter();pruned=_drop_contained(obstacles);pruning=time.perf_counter()-start
    return dict(version=i.__version__,layout_seconds=layout,routing_seconds=routing,
                svg_seconds=export,pruning_seconds=pruning,remaining_obstacles=len(pruned),
                nodes=len(nodes),edges=len(edges),route_flags=flags,svg_bytes=len(svg.encode()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--output',type=Path,default=ROOT/'out/diagram-benchmark.json')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.repeat<1:parser.error('--repeat must be positive')
    if args.worker:
        sys.path.insert(0,str(args.source.resolve()/'src'))
        print(json.dumps(measure()));return
    runs=[]
    for _ in range(args.repeat):
        run=subprocess.run([sys.executable,__file__,'--source',str(args.source),'--worker'],
                           capture_output=True,text=True,check=True)
        runs.append(json.loads(run.stdout))
        print(run.stdout.strip(),flush=True)
    source=args.source.resolve()/'src';digest=hashlib.sha256()
    for path in sorted(source.rglob('*.py')):
        digest.update(path.relative_to(source).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    report=dict(schema='inklet.diagram-benchmark/1',python=platform.python_version(),
                platform=platform.platform(),source_sha256=digest.hexdigest(),runs=runs,
                median={key:statistics.median(run[key] for run in runs)
                        for key,value in runs[0].items() if isinstance(value,(int,float))})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
