"""Measure complete v2/v2.5 figures, enforcing build budgets and cache reuse."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'examples')]
import inklet as i
from v2_cases import cases
from v25_document import make_document as v25_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'tmp/v2-benchmark')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    budgets=json.loads((ROOT/'tests/visual/v2-budgets.json').read_text())
    results=[];failed=False
    for name,doc in [*cases(),('v25-document',v25_document())]:
        start=time.perf_counter();compiled=doc.compile();cold=time.perf_counter()-start
        start=time.perf_counter();cached=doc.compile();warm=time.perf_counter()-start
        if cached is not compiled:raise AssertionError(f'{name}: cached compile rebuilt the document')
        start=time.perf_counter();compiled.save(out/f'{name}.svg',out/f'{name}.pdf');export=time.perf_counter()-start
        record=dict(case=name,compile_seconds=cold,cached_seconds=warm,export_seconds=export,
                    recipe_builds=compiled.stats['builds'],cache_hits=compiled.stats['cache_hits'],
                    nodes=compiled.stats['node_count'],diagnostics=len(compiled.diagnostics),
                    svg_bytes=(out/f'{name}.svg').stat().st_size,pdf_bytes=(out/f'{name}.pdf').stat().st_size,
                    passed=cold<=budgets[name])
        failed|=not record['passed'];results.append(record);print(json.dumps(record),flush=True)
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return int(failed)

if __name__=='__main__':raise SystemExit(main())
