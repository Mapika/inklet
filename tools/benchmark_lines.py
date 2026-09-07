"""Compare complete dense-line builds and exports in fresh Python processes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def measure(mode):
    import inklet as i
    import math
    points=[(k/10000,math.sin(k/2500)+.25*math.cos(11*k/10000)
             +3*math.exp(-((k/10000-4.25)/.002)**2)) for k in range(100001)]
    p=i.plot_spec(height=55,x=(0,10),y=(-1.5,2.7),clip=True)
    p.line(points,stroke='#176b9b',**({'simplify':.02} if mode=='reduced' else {}))
    p.axes(x='Time / s',y='Response')
    doc=i.document(width=120);doc.add('signal',p)
    start=time.perf_counter();compiled=doc.compile();build=time.perf_counter()-start
    start=time.perf_counter();svg=compiled.to_svg();svg_time=time.perf_counter()-start
    start=time.perf_counter();pdf=compiled.to_pdf();pdf_time=time.perf_counter()-start
    assert compiled.to_svg()==svg and compiled.to_pdf()==pdf
    notes=[n.notes['line_simplification'] for n in compiled.root.walk() if 'line_simplification' in n.notes]
    return dict(version=i.__version__,mode=mode,compile_seconds=build,svg_seconds=svg_time,
                pdf_seconds=pdf_time,total_seconds=build+svg_time+pdf_time,svg_bytes=len(svg.encode()),pdf_bytes=len(pdf),
                input_points=len(points),output_points=notes[0]['output_points'] if notes else len(points))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--mode',choices=('both','exact','reduced'),default='both')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--output',type=Path,default=ROOT/'out/line-benchmark.json')
    args=parser.parse_args()
    if args.repeat<1:parser.error('--repeat must be positive')
    if args.worker:
        sys.path.insert(0,str(args.source.resolve()/'src'))
        print(json.dumps(measure(args.mode)));return
    modes=('exact','reduced') if args.mode=='both' else (args.mode,)
    cases=[]
    for mode in modes:
        runs=[]
        for _ in range(args.repeat):
            run=subprocess.run([sys.executable,__file__,'--source',str(args.source),'--mode',mode,'--worker'],capture_output=True,text=True,check=True)
            runs.append(json.loads(run.stdout))
        record=dict(mode=mode,runs=runs,median={key:statistics.median(run[key] for run in runs)
                    for key,value in runs[0].items() if isinstance(value,(int,float))})
        cases.append(record);print(json.dumps(record['median']),flush=True)
    source=args.source.resolve()/'src';digest=hashlib.sha256()
    for path in sorted(source.rglob('*.py')):digest.update(path.relative_to(source).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    report=dict(schema='inklet.line-benchmark/1',python=platform.python_version(),platform=platform.platform(),
                source_sha256=digest.hexdigest(),cases=cases)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
