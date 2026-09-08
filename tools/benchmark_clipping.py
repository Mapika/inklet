"""Fresh-process clipping and export measurements; simulated original data."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def measure(case):
    import inklet as i
    from inklet.core import Diagram, PathPrim, Subpath, Vec2
    if case=='band':
        top=[(k/500,4+3*math.sin(k/1000)) for k in range(50001)]
        bottom=[(x,y-3) for x,y in reversed(top)]
        node=i.polygon(top+bottom,fill='#387eaf',stroke='none',fill_opacity=.4)
    elif case=='curves':
        node=i.curve([(k/10,7*math.sin(k/15)) for k in range(1001)],stroke='#387eaf',stroke_width=.3)
    else:
        node=i.polyline([(k/500,7*math.sin(k/1000)) for k in range(50001)],stroke='#387eaf',stroke_width=.3)
    start=time.perf_counter();cut=i.clip(node,i.Rect(10,-4,90,4));clip=time.perf_counter()-start
    start=time.perf_counter();svg=i.to_svg(cut);svg_time=time.perf_counter()-start
    start=time.perf_counter();pdf=i.to_pdf(cut);pdf_time=time.perf_counter()-start
    assert svg==i.to_svg(cut) and pdf==i.to_pdf(cut)
    return dict(clip_seconds=clip,svg_seconds=svg_time,pdf_seconds=pdf_time,
                total_seconds=clip+svg_time+pdf_time,svg_bytes=len(svg.encode()),pdf_bytes=len(pdf))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=ROOT/'out/clipping-benchmark.json')
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--worker',choices=('line','band','curves'))
    args=parser.parse_args()
    if args.repeat<1:parser.error('--repeat must be positive')
    if args.worker:
        sys.path.insert(0,str(args.source.resolve()/'src'))
        print(json.dumps(measure(args.worker)));return
    cases=[]
    for case in ('line','band','curves'):
        runs=[]
        for _ in range(args.repeat):
            result=subprocess.run([sys.executable,__file__,'--source',str(args.source),'--worker',case],capture_output=True,text=True,check=True)
            runs.append(json.loads(result.stdout))
        record=dict(case=case,runs=runs,median={k:statistics.median(r[k] for r in runs) for k in runs[0]})
        cases.append(record);print(json.dumps(record),flush=True)
    digest=hashlib.sha256()
    for path in sorted((args.source/'src').rglob('*.py')):
        digest.update(path.relative_to(args.source).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(schema='inklet.clipping-benchmark/1',python=platform.python_version(),
        platform=platform.platform(),source_sha256=digest.hexdigest(),cases=cases),indent=2)+'\n')


if __name__=='__main__':main()
