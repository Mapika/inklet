"""Render complete fixtures and compare PNGs with reviewed SVG/PDF baselines.

Run --update only when intentionally accepting a visible change. Normal runs
never replace the baseline. A local HTML report includes every difference.
"""
from pathlib import Path
import argparse
import hashlib
import html
import importlib.util
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from inklet.render.preview import svg_png, pdf_png
from inklet.typeset.fonts import find_font


def main():
    from PIL import Image, ImageChops
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update',action='store_true')
    parser.add_argument('--suite',choices=('v1','v2','v25','all'),default='all')
    parser.add_argument('--output',type=Path,default=ROOT/'tmp/visual-check')
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    baseline=ROOT/'tests/visual/baseline';baseline.mkdir(exist_ok=True)
    fonts={f'{weight}-{italic}':hashlib.sha256(Path(find_font('DejaVu Sans',weight,italic).path).read_bytes()).hexdigest()
           for weight,italic in [('regular',False),('bold',False),('regular',True)]}
    manifest=baseline/'fonts.json'
    if not args.update and (not manifest.exists() or json.loads(manifest.read_text())!=fonts):
        raise SystemExit('Visual baseline font mismatch: install the recorded DejaVu Sans fonts before comparison. Do not update baselines to hide an environment mismatch.')
    module_spec=importlib.util.spec_from_file_location('visual_fixtures',ROOT/'tests/visual/fixtures.py')
    fixtures=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(fixtures)
    def selected_figures():
        if args.suite in ('v1','all'):
            yield from fixtures.figures()
        if args.suite in ('v2','all'):
            sys.path.insert(0,str(ROOT/'examples'))
            from v2_cases import cases
            for name,document in cases():
                yield f'v2-{name}',document.compile()
        if args.suite in ('v25','all'):
            sys.path.insert(0,str(ROOT/'examples'))
            from v25_document import make_document
            yield 'v25-document',make_document().compile()
    records=[];failed=False
    for name,fig in selected_figures():
        fig.save(out/f'{name}.svg',out/f'{name}.pdf',text='embed')
        for backend,renderer in [('svg',svg_png),('pdf',pdf_png)]:
            stem=f'{name}-{backend}';png=out/f'{stem}.png'
            renderer(out/f'{name}.{backend}',png,dpi=150)
            old=baseline/png.name;copied=out/f'{stem}-baseline.png'
            if args.update:shutil.copyfile(png,old)
            if not old.exists():
                failed=True;records.append({'case':stem,'error':'missing baseline'});continue
            shutil.copyfile(old,copied)
            with Image.open(old) as a,Image.open(png) as b:
                if a.size != b.size:
                    record={'case':stem,'error':'page dimensions changed'};failed=True
                else:
                    diff=ImageChops.difference(a.convert('RGB'),b.convert('RGB'))
                    channels=diff.split();mask=ImageChops.lighter(ImageChops.lighter(*channels[:2]),channels[2])
                    changed=sum(mask.histogram()[25:])/(a.width*a.height)
                    diff.point(lambda p:min(255,p*5)).save(out/f'{stem}-diff.png')
                    record={'case':stem,'changed_fraction':changed,'passed':changed<=.001}
                    failed |= not record['passed']
                records.append(record)
    if args.update:manifest.write_text(json.dumps(fonts,indent=2)+'\n')
    (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
    rows=''.join(f'<section><h2>{html.escape(r["case"])}</h2><p>{html.escape(str(r))}</p><div>'+''.join(
        f'<figure><figcaption>{label}</figcaption><img src="{r["case"]}{suffix}.png"></figure>'
        for label,suffix in [('Baseline','-baseline'),('Current',''),('Difference ×5','-diff')])+'</div></section>' for r in records)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Inklet visual checks</title><style>body{font:16px sans-serif;margin:32px}section div{display:flex}figure{width:32%;margin:4px}img{max-width:100%}</style><h1>Inklet visual checks</h1>'+rows)
    print(out/'index.html')
    return int(failed)

if __name__=='__main__':raise SystemExit(main())
