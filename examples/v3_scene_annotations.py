"""World measurements and editable annotations over an original Blender scene."""
import argparse
import json
from pathlib import Path

import inklet as i
from v3_scene_paths import make_scene

ROOT = Path(__file__).resolve().parents[1]
INK, MUTED, ACCENT = '#172f32', '#586b6d', '#a85518'


def make_document(scene):
    label_style = dict(size=i.pt(8), text_fill=INK,
                       leader_style=dict(stroke=INK, stroke_width=.25))
    labels = [
        scene.annotate3d((.51,-.68,1.7), 'Ceramic housing', side='e', clear=15, **label_style),
        scene.annotate3d((.26,0,3.275), 'Connector', side='ne', clear=9, hidden='show', **label_style),
        scene.annotate3d((-.51,.68,1.1), 'Rear surface', side='w', clear=22, hidden='dash', **label_style),
    ]
    measures = [
        scene.dimension3d((0,0,.4), (0,0,2.8), scale=100, unit='mm', offset=24,
            hidden='show', size=i.pt(8), stroke=INK, stroke_width=.25),
        scene.dimension3d((-1.168,-.876,.17), (1.168,.876,.17), scale=100,
            unit='mm', offset=13, hidden='show', size=i.pt(8), stroke=INK, stroke_width=.25),
    ]
    arrows = [
        scene.arrow3d((-1.8,-.1,1.5), (1.8,.1,1.5), hidden='dash',
            head_size=1.8, stroke=ACCENT, stroke_width=.45),
        scene.annotate3d((1.8,.1,1.5), 'Direction', side='n', clear=5,
            hidden='show', leader=False, size=i.pt(8), text_fill=ACCENT),
    ]
    # Two orthogonal world vectors in the clear space beside the housing.
    angle = scene.angle3d((-2.6,-.8,1.4), (-1.6,-.8,1.4), (-1.6,-.8,2.4),
        radius=.8, hidden='show', side='w', clear=8,
        size=i.pt(9), stroke=ACCENT, stroke_width=.35)
    panels = [
        ('A  Visible and hidden targets', labels, 'A dashed leader identifies the rear surface.'),
        ('B  World-space dimensions', measures, 'Explicit scale: 1 scene unit = 100 mm.'),
        ('C  Depth-tested arrow', arrows, 'The housing hides the middle of the shaft.'),
        ('D  A measured 3D angle', [angle], 'The projected arc retains the true 90° label.'),
    ]
    doc = i.document(width=220, columns=2, margin=8, gap=8)
    doc.add('title', i.text('Measurements in a rendered scene', size=i.pt(20), text_fill=INK), colspan=2)
    doc.add('subtitle', i.text('World coordinates for geometry. Page units for readable text and annotation strokes.',
        size=i.pt(9), text_fill=MUTED), colspan=2)
    for n, (title, layers, caption) in enumerate(panels):
        art = i.overlay([scene.diagram, *layers], align='origin')
        doc.add('view-'+str(n), i.vstack([
            i.text(title, size=i.pt(11), text_fill=INK), art,
            i.text(caption, size=i.pt(8), text_fill=MUTED),
        ], gap=4, align='left'), row=2+n//2, column=n%2)
    doc.add('caption', i.text('Original conceptual apparatus; dimensions illustrate an authored scale.',
        size=i.pt(8), text_fill=MUTED), colspan=2)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/v3-annotations')
    parser.add_argument('--scene', type=Path, help='Reuse the sensor.blend from the scene-paths example')
    parser.add_argument('--blender', type=Path)
    parser.add_argument('--quality', choices=('draft','preview','final'), default='final')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.scene or args.output/'sensor.blend'
    if args.scene is None:
        make_scene(source, args.blender)
    scene = i.render_blend(source, width=85, height=78, engine='CYCLES', camera='Overview',
        passes=('depth',), quality=args.quality, blender=args.blender)
    figure = make_document(scene).compile()
    if any(d.severity=='error' for d in figure.diagnostics):
        raise RuntimeError(figure.report())
    files = figure.export(args.output, dpi=i.render_quality(args.quality).dpi)
    (args.output/'annotations.json').write_text(json.dumps(
        figure.metadata['rendering']['scene_annotations'], indent=2)+'\n')
    print(figure.report())
    print(files['review'])


if __name__ == '__main__':
    main()
