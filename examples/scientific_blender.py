"""An illustrative synapse with vector labels and simulated response plots."""
import argparse
import math
from pathlib import Path
import subprocess

import inklet as i
from inklet.three.blender import find_blender

ROOT = Path(__file__).resolve().parents[1]


def make_document(scene):
    labels = []
    for point, text, side, clear in [
        ((-2.25,.5,2.1), 'Cutaway membrane', 'w', 13),
        ((-1.5,-.1,1.8), 'Synaptic vesicle', 'w', 14),
        ((1.55,.05,2.2), 'Vesicle pool', 'e', 25),
        ((.5,-.65,.26), 'Receptor', 'e', 30),
        ((0,-.6,.45), 'Released particles', 'sw', 17),
    ]:
        labels.append(scene.annotate3d(point, text, side=side, clear=clear,
            hidden='show', size=i.pt(8), text_fill='#243c42',
            leader_style={'stroke':'#536c73', 'stroke_width':.22}))
    art = i.overlay([scene.diagram, *labels], align='origin')
    doc = i.document(width=220, columns=2, gap=10, margin=8)
    doc.add('title', i.text('Synaptic release: an illustrative model', size=i.pt(17)), colspan=2)
    doc.add('scope', i.text('Schematic geometry and simulated curves; no measured biological dimensions.', size=i.pt(8)), colspan=2)
    doc.add('scene', art, colspan=2)
    times = [n/4 for n in range(81)]
    response = [0 if t<2 else (1-math.exp(-(t-2)/.8))*math.exp(-(t-2)/4) for t in times]
    plot = i.plot_spec(x=(0,20), y=(0,.7))
    plot.line(list(zip(times,response)), stroke='#287e8c', name='Illustrative response')
    plot.axes(x='Time / a.u.', y='Response / a.u.').legend(side='bottom')
    doc.add('response', plot, row=3, column=0, min_height=45)
    pool = i.plot_spec(x=(0,20), y=(0,1.05))
    pool.line([(t, math.exp(-t/6)) for t in times], stroke='#8457a4', name='Available fraction')
    pool.line([(t, 1-math.exp(-t/6)) for t in times], stroke='#ce8b34', name='Released fraction')
    pool.axes(x='Time / a.u.', y='Fraction').legend(side='bottom')
    doc.add('pool', pool, row=3, column=1, min_height=45)
    doc.add('caption', i.text('Curves are independent analytic demonstrations, not estimates from the rendered vesicles.', size=i.pt(8)), colspan=2)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/scientific-blender')
    parser.add_argument('--blender', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    binary = find_blender(args.blender).path
    source = args.output/'synapse.blend'
    subprocess.run([str(binary), '--background', '--factory-startup', '--disable-autoexec',
        '--python-exit-code', '1', '--python', str(ROOT/'examples/blender/synapse_scene.py'),
        '--', str(source)], check=True, stdout=subprocess.DEVNULL, timeout=120)
    scene = i.render_blend(source, width=140, height=105, camera='Overview',
        engine='CYCLES', samples=64, dpi=300, passes=('depth',), blender=binary)
    figure = make_document(scene).compile()
    figure.save(args.output/'synapse.svg', args.output/'synapse.pdf')
    (args.output/'synapse.png').write_bytes(figure.to_png(dpi=160))
    (args.output/'review.txt').write_text(figure.report())
    print(figure.report())


if __name__ == '__main__':
    main()
