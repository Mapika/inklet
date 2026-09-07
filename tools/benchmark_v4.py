"""Record cold, cached, data-edit, label-edit, resize and export engine baselines.

Each sample uses a fresh process; compare a release checkout with --source.
No performance thresholds are inferred from the measurements automatically.
"""
from pathlib import Path
import argparse
import json
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = {'ordinary': 100, 'dense-vector': 3000}


def workload(count, *, edited=False, label='Response'):
    import inklet as i
    import math
    x = tuple(n/(count-1)*10 for n in range(count))
    y = tuple(math.sin(v)+(.1 if edited else 0) for v in x)
    table = i.dataset({'x': x, 'y': y}, name='benchmark', units={'x': 's'})
    doc = i.document(width=210, columns=2).letters()
    plots = []
    for column, kind in enumerate(('line', 'scatter')):
        p = i.plot_spec(x=(0, 10), y=(-1.3, 1.3), height=55)
        getattr(p, kind)(table.points('x', 'y'), **({'size': .5} if kind=='scatter' else {}))
        p.axes(x='Time / s', y=label if column==0 else 'Response', key='axes')
        doc.add(kind, p, row=0, column=column); plots.append(p)
    return doc, table, plots


def measure(case):
    import inklet as i
    doc, data, plots = workload(CASES[case])
    records = {}
    def compile_stage(name):
        start = time.perf_counter(); figure = doc.compile(); elapsed = time.perf_counter()-start
        if any(d.severity=='error' for d in figure.diagnostics): raise AssertionError(figure.report())
        records[name] = dict(seconds=elapsed, compiler=dict(figure.stats))
        return figure
    first = compile_stage('cold')
    start=time.perf_counter(); assert doc.compile() is first
    # A cached snapshot's stats describe its original build, not this lookup.
    records['cached'] = dict(seconds=time.perf_counter()-start)
    original = first.to_svg()
    data.update(y=[v+.1 for v in data.columns['y']])
    revised = compile_stage('data_edit')
    assert revised is not first and first.to_svg()==original
    plots[0].replace('axes', x='Time / s', y='Updated response')
    labelled = compile_stage('label_edit'); before_resize=labelled.to_svg()
    doc.width=250; compile_stage('resize'); doc.width=210
    restored=compile_stage('resize_back')
    assert restored.to_svg()==before_resize
    fresh, _, _ = workload(CASES[case], edited=True, label='Updated response')
    assert fresh.compile().to_svg()==before_resize
    start=time.perf_counter();svg=restored.to_svg();svg_time=time.perf_counter()-start
    start=time.perf_counter();pdf=restored.to_pdf();pdf_time=time.perf_counter()-start
    rss=None
    try:
        import resource
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
    except ImportError: pass
    return dict(case=case,points_per_panel=CASES[case],version=i.__version__,stages=records,
                svg_seconds=svg_time,pdf_seconds=pdf_time,svg_bytes=len(svg.encode()),pdf_bytes=len(pdf),
                peak_rss_mib=rss,correctness='cached/clean, old snapshot and resize round trip passed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=ROOT/'out/v4-baseline.json')
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--label',default='working-tree')
    parser.add_argument('--budgets',type=Path,help='Optional budgets for the matching reference environment')
    parser.add_argument('--worker',choices=CASES,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.repeat<1: parser.error('repeat must be positive')
    if args.worker:
        sys.path.insert(0,str(args.source.resolve()/'src'))
        print(json.dumps(measure(args.worker)));return
    records=[]
    for name in CASES:
        runs=[]
        for _ in range(args.repeat):
            result=subprocess.run([sys.executable,__file__,'--source',str(args.source.resolve()),'--worker',name],
                                  capture_output=True,text=True,check=True,timeout=180)
            runs.append(json.loads(result.stdout))
        medians={stage:statistics.median(run['stages'][stage]['seconds'] for run in runs) for stage in runs[0]['stages']}
        medians.update({key:statistics.median(run[key] for run in runs) for key in ('svg_seconds','pdf_seconds','peak_rss_mib') if all(run[key] is not None for run in runs)})
        records.append(dict(case=name,median=medians,runs=runs));print(name,medians,flush=True)
    cpu=platform.processor()
    if Path('/proc/cpuinfo').exists():
        cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),cpu)
    report=dict(schema='inklet.v4-baseline/0.1',label=args.label,environment=dict(
        python=sys.version,platform=platform.platform(),machine=platform.machine(),cpu=cpu),
        method='Fresh process per sample; imports/setup excluded; RSS includes process and validation; medians of repeats. System font/filesystem caches may be warm.',cases=records)
    failed=False
    if args.budgets:
        budgets=json.loads(args.budgets.read_text())
        expected=budgets['environment']
        actual=dict(cpu=cpu,python=f'{sys.version_info.major}.{sys.version_info.minor}',system=platform.system())
        if expected!=actual:
            raise SystemExit(f'Budget environment mismatch: expected {expected!r}; got {actual!r}')
        checks=[]
        for record in records:
            for metric,limit in budgets['limits'][record['case']].items():
                measured=record['median'][metric]
                checks.append(dict(case=record['case'],metric=metric,value=measured,limit=limit,passed=measured<=limit))
        report['budget_checks']=checks
        failed=any(not check['passed'] for check in checks)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    return int(failed)


if __name__=='__main__':raise SystemExit(main())
