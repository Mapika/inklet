"""Build the curated showcase, its export library and an offline gallery."""
import argparse
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import inklet as i


def recipes():
    spec=importlib.util.spec_from_file_location('showcase_figures',ROOT/'examples/showcase/figures.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def file_hash(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def asset_files(output, *, download=False):
    lock=json.loads((ROOT/'examples/showcase/assets.lock.json').read_text())
    folder=output/'assets'/lock['id']
    for item in lock['files']:
        path=folder/item['path']
        if path.is_file() and file_hash(path)==item['sha256']:continue
        if not download:
            raise ValueError('Architecture needs the CC0 chair: run with --download-assets')
        path.parent.mkdir(parents=True,exist_ok=True)
        request=urllib.request.Request(item['url'],headers={'User-Agent':'Inklet showcase builder (github.com/Mapika/inklet)'})
        with urllib.request.urlopen(request,timeout=60) as response:
            data=response.read(item['size']+1)
        if len(data)!=item['size'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError(f'Asset checksum mismatch: {item["path"]}')
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as temp:
            temp.write(data);staged=Path(temp.name)
        staged.replace(path)
    return folder/'modern_arm_chair_01_1k.blend',lock


def prepare_scene(kind, output, chair=None):
    from inklet.three.blender import find_blender
    script=ROOT/'examples/showcase/blender_scenes.py';path=output/'scenes'/(kind+'.blend')
    stamp=path.with_suffix('.json')
    inputs={'builder':file_hash(script),'kind':kind,
            'chair':file_hash(chair) if chair else None,
            'asset_lock':file_hash(ROOT/'examples/showcase/assets.lock.json') if chair else None}
    if path.is_file() and stamp.is_file():
        saved=json.loads(stamp.read_text())
        if saved.get('inputs')==inputs and saved.get('sha256')==file_hash(path):return path
    path.parent.mkdir(parents=True,exist_ok=True)
    command=[str(find_blender().path),'--background','--factory-startup','--disable-autoexec',
             '--python-exit-code','1','--python',str(script),'--',kind,str(path)]
    if chair:command.append(str(chair))
    process=subprocess.run(command,capture_output=True,text=True,timeout=120)
    if process.returncode:raise RuntimeError((process.stdout+process.stderr)[-5000:])
    stamp.write_text(json.dumps({'inputs':inputs,'sha256':file_hash(path)},indent=2)+'\n')
    return path


def gallery_page(records):
    esc=html.escape
    cards=[]
    for item in records:
        name=item['id']
        scene_link=f'<a href="{esc(item["scene"])}" download>Blender scene</a>' if item.get('scene') else ''
        cards.append(f'''<article data-category="{esc(item['category'])}">
<a href="{name}/figure.html"><img src="{name}/figure.png" alt="{esc(item['title'])}" loading="lazy"></a>
<div class="copy"><small>{esc(item['category'])}</small><h2>{esc(item['title'])}</h2>
<p>{esc(item['description'])}</p><p class="origin">{esc(item['origin'])}</p>
<nav><a href="{name}/figure.html">Review</a><a href="{name}/figure.svg">SVG</a>
<a href="{name}/figure.pdf">PDF</a><a href="{name}/figure.png" download>PNG</a>
<a href="source/figures.py">Source</a>{scene_link}</nav></div></article>''')
    categories=sorted(set(item['category'] for item in records))
    options=''.join(f'<option>{esc(category)}</option>' for category in categories)
    return f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Inklet showcase</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f4f6;color:#182b40;font:16px/1.6 system-ui,sans-serif}}
header,main,footer{{max-width:1240px;margin:auto;padding:32px}}header{{padding-top:64px}}
header small{{letter-spacing:.16em}}h1{{font-size:clamp(36px,6vw,68px);line-height:1.05;margin:18px 0}}
header p{{max-width:650px;color:#49647a}}.controls{{display:flex;gap:16px;flex-wrap:wrap;align-items:center}}
select{{padding:10px;border:1px solid #bbc8d4;border-radius:6px;font:inherit;background:white}}
main{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}}article{{background:white;border-radius:12px;overflow:hidden;border:1px solid #dfe5eb}}
article img{{width:100%;aspect-ratio:1.25;object-fit:contain;display:block}}.copy{{padding:24px;border-top:1px solid #eef1f4}}
h2{{font-size:25px;line-height:1.2;margin:8px 0}}small,.origin{{color:#52687c}}.origin{{font-size:13px}}
nav{{display:flex;gap:16px;flex-wrap:wrap}}a{{color:#175f86;text-underline-offset:3px}}article[hidden]{{display:none}}
footer{{font-size:14px}}@media(max-width:720px){{main{{grid-template-columns:1fr}}header,main,footer{{padding:22px}}}}
</style><header><small>INKLET / SHOWCASE LIBRARY</small><h1>Figures worth sharing.</h1>
<p>Plots, scientific illustrations and architectural scenes, made with Inklet. Every figure includes editable exports, runnable source and a clear account of its data and assets.</p>
<div class="controls"><label for="category">Explore</label><select id="category"><option value="">All figures</option>{options}</select>
<a href="catalog.json">Catalogue and provenance</a><a href="source/README.md">Rebuild this collection</a></div></header>
<main>{''.join(cards)}</main><footer>Inklet code: MIT. Furniture asset: CC0, Vibrant Nordic / Poly Haven. See the catalogue for sources. All scientific examples are mathematical or illustrative.</footer>
<script>document.querySelector('#category').addEventListener('change',event=>{{for(const card of document.querySelectorAll('article'))card.hidden=!!event.target.value&&card.dataset.category!==event.target.value;}});</script></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/showcase')
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    parser.add_argument('--only',nargs='+',help='Build selected catalogue IDs')
    parser.add_argument('--plots-only',action='store_true',help='No Blender or downloaded assets required')
    parser.add_argument('--download-assets',action='store_true',help='Fetch the pinned CC0 furniture asset (about 12 MB)')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--archive',action='store_true',help='Also write an inklet-showcase.zip beside the output directory')
    args=parser.parse_args();module=recipes()
    if args.list:
        for item in module.CATALOG:print(item['id']+' — '+item['title'])
        return 0
    if args.only and set(args.only)-{item['id'] for item in module.CATALOG}:
        parser.error('Unknown showcase ID')
    selected=[item for item in module.CATALOG if (not args.only or item['id'] in args.only)
              and (not args.plots_only or item['category']=='Mathematical plots')]
    if not selected:parser.error('No figures selected')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    records=[];assets=[]
    for entry in selected:
        print('Building '+entry['id'],flush=True)
        scene=None
        if entry['category']!='Mathematical plots':
            kind='architecture' if entry['id'].startswith('architecture') else entry['id']
            chair=None
            if kind=='architecture':
                chair,lock=asset_files(output,download=args.download_assets)
                if not assets:assets.append(lock)
            scene=prepare_scene(kind,output,chair)
        compiled=module.make_document(entry,scene=scene,quality=args.quality).compile()
        errors=[d for d in compiled.diagnostics if d.severity=='error']
        if errors:raise RuntimeError(compiled.report())
        files=compiled.export(output/entry['id'],dpi=i.render_quality(args.quality).dpi)
        records.append(dict(entry,quality=args.quality,diagnostics=[dict(code=d.code,severity=d.severity,message=d.message)
            for d in compiled.diagnostics],image_sha256=file_hash(files['png']),
            scene=str(scene.relative_to(output)) if scene else None))
        print(compiled.report(),flush=True)
    source=output/'source';source.mkdir(exist_ok=True)
    for name in ('figures.py','blender_scenes.py','assets.lock.json','README.md'):
        shutil.copy2(ROOT/'examples/showcase'/name,source/name)
    shutil.copy2(__file__,source/'showcase_gallery.py')
    catalog=dict(version=i.__version__,quality=args.quality,figures=records,assets=assets,
                 sources={path.name:file_hash(path) for path in sorted(source.iterdir()) if path.is_file()})
    (output/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (output/'index.html').write_text(gallery_page(records),encoding='utf-8')
    if args.archive:
        print(shutil.make_archive(str(output.parent/'inklet-showcase'),'zip',root_dir=output))
    print(output/'index.html')
    return 0


if __name__=='__main__':raise SystemExit(main())
