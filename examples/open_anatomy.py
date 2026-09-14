"""Download a hash-locked CC BY anatomy model and render labelled Blender views."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

import inklet as i
from inklet.three.blender import find_blender

ROOT = Path(__file__).resolve().parents[1]


def acquire(folder):
    record = json.loads((ROOT/'examples/assets/open-anatomy.json').read_text())
    path = folder/record['filename']
    raw = path.read_bytes() if path.exists() else urlopen(record['url'], timeout=60).read()
    if len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise ValueError('NIH model does not match its recorded size and SHA-256')
    if not path.exists():
        path.write_bytes(raw)
    return path, record


def make_document(front, oblique, anchors):
    doc = i.document(width=240, columns=2, gap=12, margin=8)
    doc.add('title', i.text('Human cardiopulmonary anatomy', size=i.pt(18)), colspan=2)
    doc.add('source', i.text('Visible Human source model · lungs, airway and heart vessels', size=i.pt(9)), colspan=2)
    for column, (name, scene) in enumerate([('A  Overview', front), ('B  Oblique view', oblique)]):
        choices = [('Lung surface', 'w', 9), ('Upper airway', 'e', 13)] if column == 0 else [
            ('Vascular branches', 'e', 12), ('Source display base', 's', 7)]
        labels = [scene.annotate3d(anchors[label], label, side=side, clear=clear,
            hidden='show', size=i.pt(7.5), text_fill='#243c42',
            leader_style={'stroke':'#536c73','stroke_width':.22})
            for label,side,clear in choices]
        art = i.overlay([scene.diagram,*labels],align='origin')
        doc.add('view-'+str(column), i.vstack([i.text(name,size=i.pt(10)), art],gap=4), row=2, column=column)
    doc.add('credit', i.text('Model: kbrowne / NIH 3D, 3DPX-023212 v1.01 · CC BY 4.0', size=i.pt(8)), colspan=2)
    doc.add('changes', i.text('Adaptation: materials, lighting, cameras and vector labels. Source proportions retained; no physical scale inferred.', size=i.pt(8)), colspan=2)
    return doc


def make_highlight_document(neutral, highlighted):
    doc = i.document(width=220, columns=2, gap=10, margin=8)
    doc.add('title', i.text('Highlight a selected region', size=i.pt(18)), colspan=2)
    doc.add('scope', i.text('Same source geometry and camera; authored upper region, not anatomical segmentation.', size=i.pt(8)), colspan=2)
    for column, (title, scene) in enumerate([
        ('A  Neutral model', neutral), ('B  Selected region in amber', highlighted)
    ]):
        doc.add('view-'+str(column), i.vstack([
            i.text(title, size=i.pt(10)), scene.diagram,
        ], gap=4), row=2, column=column)
    doc.add('key', i.hstack([
        i.text('Selected region', size=i.pt(8), text_fill='#a45c16'),
        i.text('Remaining geometry', size=i.pt(8), text_fill='#586b6d'),
    ], gap=12), colspan=2)
    doc.add('credit', i.text('Model: kbrowne / NIH 3D, 3DPX-023212 v1.01 · CC BY 4.0', size=i.pt(8)), colspan=2)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/open-anatomy')
    parser.add_argument('--blender',type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    model, record = acquire(args.output)
    binary = find_blender(args.blender).path
    blend = args.output/'anatomy.blend'
    subprocess.run([str(binary),'--background','--factory-startup','--disable-autoexec',
        '--python-exit-code','1','--python',str(ROOT/'examples/blender/open_anatomy_scene.py'),
        '--',str(model),str(blend)],check=True,stdout=subprocess.DEVNULL,timeout=120)
    views = [i.render_blend(blend,width=90,height=108,camera=camera,
        engine='CYCLES',samples=64,dpi=300,passes=('depth',),blender=binary)
        for camera in ('Overview','Oblique')]
    figure = make_document(*views, json.loads(blend.with_suffix('.anchors.json').read_text())).compile()
    figure.save(args.output/'anatomy.svg',args.output/'anatomy.pdf')
    (args.output/'anatomy.png').write_bytes(figure.to_png(dpi=160))
    (args.output/'attribution.json').write_text(json.dumps(record,indent=2)+'\n')
    (args.output/'review.txt').write_text(figure.report())
    highlighted = i.render_blend(blend,width=90,height=108,camera='Overview',
        engine='CYCLES',samples=64,dpi=300,passes=('depth',),blender=binary,
        bindings={'Upper region': {'color': '#d88b32'},
                  'Context': {'color': '#c5d0d2'}})
    comparison = make_highlight_document(views[0], highlighted).compile()
    comparison.save(args.output/'highlight.svg', args.output/'highlight.pdf')
    (args.output/'highlight.png').write_bytes(comparison.to_png(dpi=160))
    (args.output/'highlight-review.txt').write_text(comparison.report())
    print(figure.report())
    print(comparison.report())


if __name__ == '__main__':
    main()
