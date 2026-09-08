"""Benchmark complete rendering workloads in fresh Python processes.

Compare revisions with --source pointing at a checkout. Each repeat imports
that checkout in a new process, then measures compile, cached compile, SVG,
PDF and repeated export separately. Timings exclude imports and recipe setup.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ('grid64','scatter30000','images64','groups32')


def workload(name):
    import inklet as i
    import math
    import random
    if name == 'grid64':
        doc = i.document(width=480,columns=8,margin=4,gap=4,row_gap=5)
        for j in range(64):
            plot = i.plot_spec(height=24,x=(0,6),y=(-1.2,1.2))
            plot.line([(k/10,math.sin(k/10+j/5)) for k in range(61)]).axes(x='Time / s',y='Signal')
            doc.add(f'plot-{j}',plot,row=j//8,column=j%8)
        return doc
    if name == 'scatter30000':
        rng = random.Random(2026)
        doc = i.document(width=100)
        plot = i.plot_spec(height=60,x=(-4,4),y=(-4,4))
        plot.scatter([(rng.gauss(0,1),rng.gauss(0,1)) for _ in range(30000)],
                     raster=True,size=.7,color='#0072b2',fill_opacity=.3,dpi=150).axes(x='x',y='y')
        doc.add('cloud',plot)
        return doc
    if name == 'images64':
        from PIL import Image
        from inklet.core import ImagePrim
        import io
        rng = random.Random(2026)
        image = Image.frombytes('RGB',(256,256),rng.randbytes(256*256*3))
        data = io.BytesIO();image.save(data,format='PNG')
        doc = i.document(width=260,columns=8,gap=2)
        for j in range(64):
            doc.add(f'image-{j}',i.Diagram(prim=ImagePrim('simulated',28,28,data=data.getvalue())),
                    row=j//8,column=j%8)
        return doc
    if name == 'groups32':
        # Nested opacity must composite overlapping children as a group.
        # Labels exercise painted glyph bounds as well as primitive traversal.
        from inklet.core import Diagram, RectPrim
        marks = []
        for j in range(64):
            x, y = (j % 8)*16, (j // 8)*10
            marks.append(Diagram(prim=RectPrim(15,9)).styled(
                fill='#d5e9f4',stroke='#0072b2',stroke_width=.4).translated(x,y))
            marks.append(i.text(f'Value {j}',size=2.2,halo=.3).translated(x,y))
        root = Diagram(children=tuple(marks))
        for _ in range(32):
            root = Diagram(children=(root,),style=i.Style(opacity=.99))
        doc = i.document(width=140,margin=5)
        doc.add('nested-groups',root)
        return doc
    raise ValueError(name)


def measure(name):
    import inklet as i
    doc = workload(name)
    start=time.perf_counter();compiled=doc.compile();cold=time.perf_counter()-start
    assert not any(d.severity=='error' for d in compiled.diagnostics), compiled.report()
    start=time.perf_counter();cached=doc.compile();warm=time.perf_counter()-start
    assert cached is compiled
    start=time.perf_counter();svg=compiled.to_svg();svg_seconds=time.perf_counter()-start
    start=time.perf_counter();pdf=compiled.to_pdf();pdf_seconds=time.perf_counter()-start
    start=time.perf_counter()
    assert compiled.to_svg()==svg and compiled.to_pdf()==pdf
    repeated=time.perf_counter()-start
    rss=None
    try:
        import resource
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
    except ImportError:
        pass
    return dict(case=name,version=i.__version__,compile_seconds=cold,cached_seconds=warm,
                svg_seconds=svg_seconds,pdf_seconds=pdf_seconds,reexport_seconds=repeated,
                svg_bytes=len(svg.encode()),pdf_bytes=len(pdf),peak_rss_mib=rss,
                nodes=compiled.stats['node_count'],builds=compiled.stats['builds'],
                diagnostics=len(compiled.diagnostics))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=ROOT/'out/engine-benchmark.json')
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--case',choices=CASES,action='append',
                        help='Run only selected workloads; repeat to select several')
    parser.add_argument('--worker',choices=CASES,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.repeat < 1:parser.error('--repeat must be positive')
    if args.worker:
        sys.path.insert(0,str(args.source.resolve()/'src'))
        print(json.dumps(measure(args.worker)))
        return
    records=[]
    for name in args.case or CASES:
        runs=[]
        for _ in range(args.repeat):
            result=subprocess.run([sys.executable,__file__,'--source',str(args.source.resolve()),'--worker',name],
                                  capture_output=True,text=True,check=True)
            runs.append(json.loads(result.stdout))
        numeric=[k for k,v in runs[0].items() if isinstance(v,(int,float))]
        record=dict(case=name,version=runs[0]['version'],runs=runs,
                    median={key:statistics.median(run[key] for run in runs) for key in numeric})
        records.append(record)
        print(json.dumps({k:v for k,v in record.items() if k!='runs'}),flush=True)
    source = args.source.resolve()/'src'
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*.py')):
        digest.update(path.relative_to(source).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    report=dict(schema='inklet.engine-benchmark/1',python=platform.python_version(),
                platform=platform.platform(),processor=platform.processor(),repeat=args.repeat,cases=records)
    report['source_sha256'] = digest.hexdigest()
    report['dependencies'] = {name:importlib.metadata.version(name) for name in ('fonttools','uharfbuzz','Pillow')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
