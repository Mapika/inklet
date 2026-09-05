"""Render all presets as SVG/PDF, independent previews and an HTML comparison."""
from pathlib import Path
import argparse
import html
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import inklet as i


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/presets')
    parser.add_argument('--gallery-image', type=Path, help='Write a documentation contact sheet PNG')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('preset_example', ROOT/'examples/presets.py')
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records, cards = [], []
    for name in i.preset_names():
        doc = example.make_document(name)
        compiled = doc.compile()
        bad = [d for d in compiled.diagnostics if d.code in ('RULE_FAILED', 'OFF_CANVAS', 'TINY_TEXT', 'KEY_MISMATCH')]
        if bad: raise RuntimeError(f'{name}: {bad}')
        compiled.export(output/name, dpi=150)
        records.append(dict(name=name, width=compiled.root.width, height=compiled.root.height,
                            preset=compiled.metadata['preset'], diagnostics=len(compiled.diagnostics)))
        note = 'Provisional journal style' if any(s.status == 'unverified' for s in doc.preset.sources) else doc.preset.description
        cards.append(f'''<article data-family="{name.split('.')[0]}">
<h2>{html.escape(name)}</h2><p>{html.escape(note)}</p>
<a href="{name}/figure.svg"><img src="{name}/figure.png" alt="Mixed figure using {name}" loading="lazy"></a>
<p>{compiled.root.width:g} × {compiled.root.height:.1f} mm · auto height</p>
<nav><a href="{name}/figure.svg">SVG</a> <a href="{name}/figure.pdf">PDF</a>
<a href="{name}/figure.html">Review and diagnostics</a></nav></article>''')
        print(f'{name}: SVG, PDF and both previews written', flush=True)
    (output/'manifest.json').write_text(json.dumps(records, indent=2)+'\n')
    (output/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Inklet presets</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#f5f6f8;color:#19202c;margin:0;padding:32px}
header{max-width:900px;margin:0 auto 28px}h1{font-size:36px;margin:0}h2{font-size:18px}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}
article{background:white;border:1px solid #d9dde4;border-radius:10px;padding:20px}
article[hidden]{display:none}img{width:100%;height:440px;object-fit:contain}a{color:#245b8a}
nav{display:flex;gap:16px;flex-wrap:wrap}select{font:inherit;padding:6px;margin-left:8px}</style>
<header><h1>Inklet presets</h1><p>The same simulated plots, workflow, table and native 3D object.
Each figure uses its preset's default width and fits its content vertically.
Open SVG or PDF to inspect it at its physical size.</p>
<label>Show family<select id="family"><option value="all">All presets</option>
<option>scientific</option><option>educational</option><option>marketing</option></select></label></header>
<main>'''+''.join(cards)+'''</main><script>
document.getElementById('family').addEventListener('change', event => {
  document.querySelectorAll('article').forEach(card => {
    card.hidden = event.target.value !== 'all' && card.dataset.family !== event.target.value;
  });
});</script></html>''')
    if args.gallery_image:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
        width, height, columns = 620, 640, 3
        sheet = Image.new('RGB', (columns*width, ((len(records)+columns-1)//columns)*height), '#f1f3f6')
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.truetype('DejaVuSans.ttf', 21)
        for index, record in enumerate(records):
            x, y = (index % columns)*width, (index // columns)*height
            draw.rounded_rectangle((x+10, y+10, x+width-10, y+height-10), radius=10, fill='white')
            draw.text((x+24, y+24), record['name'], fill='#19202c', font=font)
            with Image.open(output/record['name']/'figure.png') as original:
                picture = ImageOps.contain(original.convert('RGB'), (width-48, height-85))
                sheet.paste(picture, (x+(width-picture.width)//2, y+65+(height-85-picture.height)//2))
        args.gallery_image.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.gallery_image)
    print(output/'index.html')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
