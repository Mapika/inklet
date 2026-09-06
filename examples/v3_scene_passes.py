"""One Blender render as a beauty panel, numeric passes and object cutouts.

Create out/v3/lab.blend with tools/v3_showcase.py first, then run this file.
"""
from pathlib import Path
import inklet as i

ROOT = Path(__file__).resolve().parents[1]


def render(scene_file):
    return i.render_blend(scene_file, width=75, height=54, camera='Overview',
        engine='CYCLES', dpi=310, samples=48,
        passes=('depth', 'normal', 'object_id'),
        landmarks={'controller': 'Controller'})


def make_document(scene_file=None, *, rendered=None):
    result = rendered or render(scene_file or ROOT / 'out/v3/lab.blend')
    selected = ['Controller', 'Display', *sorted(name for name in result.metadata['object_ids']
                                                if name.startswith('Control button'))]
    stencil = result.object_mask(*selected)
    cutout = i.mask(result.diagram, stencil, mode='alpha', dpi=310)
    panels = [
        ('a  Rendered scene', result.diagram, 'Cycles · authored materials and lighting'),
        ('b  Depth', result.passes['depth'].to_diagram(value_range=(10, 18)),
         'White = 10 · black = 18 scene units'),
        ('c  Surface normals', result.passes['normal'].to_diagram(),
         'World XYZ mapped from [−1, 1] to RGB'),
        ('d  Object IDs', result.passes['object_id'].to_diagram(),
         'Categorical preview · numeric IDs saved separately'),
        ('e  Object mask', i.overlay([i.box('', width=75, height=54,
            fill='#e4eaf0', stroke='none'), stencil]),
         'Controller, display and controls · white = selected'),
        ('f  Isolated objects', cutout, 'Same render, camera and physical coordinates'),
    ]
    doc = i.preset('scientific.general').document(width=245, columns=3, gap=6)
    doc.add('title', i.component(i.title, 'Scene data and object masks'), colspan=3)
    for index, (label, art, caption) in enumerate(panels):
        panel = i.vstack([i.text(label, size=i.pt(8)), art,
                          i.text(caption, size=i.pt(6))], gap=3)
        doc.add('panel-' + str(index), panel, row=1 + index // 3, column=index % 3)
    doc.add('caption', i.component(i.text,
        'One original Blender scene. Depth, normal and object-ID arrays retain float32 values; plot text stays vector.',
        size=i.pt(7)), colspan=3)
    return doc


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, default=ROOT / 'out/v3/lab.blend')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/v3-passes/showcase')
    args = parser.parse_args()
    result = render(args.scene)
    compiled = make_document(rendered=result).compile()
    if any(d.severity == 'error' for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    files = compiled.export(args.output)
    for name, data in result.passes.items():
        data.save(args.output / (name + '.npy'))
    print(compiled.report())
    print(files['review'])
