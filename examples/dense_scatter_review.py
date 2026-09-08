"""Packed vector scatter: density, bubbles, marker shapes and painted clipping."""
import argparse
import json
import math
from pathlib import Path
import random
import inklet as i
from inklet.core import MarkerBatchPrim, Rect

ROOT = Path(__file__).resolve().parents[1]
CAPTION = '''Packed vector scatter with deterministic simulated data.
(a) Thirty thousand observations from two overlapping normal distributions.
(b) Twelve hundred observations with marker diameter and colour supplied per
point. (c) Seven marker shapes, each drawn as a 300-point layer with constant
physical stroke width. (d) Five thousand triangular markers in a painted window;
markers, outlines and fills are cropped together. All data marks remain vector
in SVG and PDF. Source indices and paint order are retained in packed buffers.
These are rendering examples, not experimental measurements. MIT, Mark Marosi.'''


def make_document():
    rng = random.Random(6029)
    doc = i.preset('scientific.general').customize(width=190, margin=6, gap=12).document(columns=2, row_gap=9).letters()
    a = i.panel(66, 47, x=(-4,4), y=(-3,3))
    points = [(rng.gauss((k%2)*1.6-.8,.8),rng.gauss((k%2)*.8-.4,.65)) for k in range(30000)]
    a.scatter(points, size=.32, color='#245b8a', fill_opacity=.12, stroke='none')
    a.axes(x='Coordinate x', y='Coordinate y')
    doc.add('density', a.build(), row=0, column=0)
    b = i.panel(66, 47, x=(0,10), y=(0,10))
    points = [(rng.uniform(.3,9.7),rng.uniform(.3,9.7)) for _ in range(1200)]
    sizes = [.3+1.1*rng.random() for _ in points]
    colors = ['#245b8a' if x+y<10 else '#c87942' for x,y in points]
    b.scatter(points, size=sizes, color=colors, fill_opacity=.4, stroke='#35434c', stroke_width=.11)
    b.axes(x='Coordinate x', y='Coordinate y')
    doc.add('bubbles', b.build(), row=0, column=1)
    c = i.panel(66, 47, x=(0,10), y=(-.6,6.6))
    for row, marker in enumerate(('circle','square','triangle','diamond','star','cross','plus')):
        c.scatter([(rng.uniform(.4,9.6), row+rng.gauss(0,.13)) for _ in range(300)],
                  marker=marker, size=.65, color='#245b8a', stroke='#245b8a',
                  stroke_width=.11, fill_opacity=.35, stroke_opacity=.6)
    c.axes(x='Coordinate x', y='Marker index')
    doc.add('markers', c.build(), row=1, column=0)
    d = i.panel(66, 47, x=(-3,3), y=(-2,2), clip=False)
    from inklet.plot.marks import scatter
    points = [(rng.gauss(0,1.5),rng.gauss(0,1.0)) for _ in range(5000)]
    layer = scatter(d, points, size=.7, color='#a35f49', marker='triangle',
                    fill_opacity=.25, stroke='#603e37', stroke_width=.11)
    d.draw(i.window(i.as_drawn(layer), d.area), clip=False)
    d.axes(x='Coordinate x', y='Coordinate y')
    doc.add('window', d.build(), row=1, column=1)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/dense-scatter-review')
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    compiled = make_document().compile()
    errors = [d for d in compiled.diagnostics if d.severity=='error']
    if errors: raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg', args.output/'figure.pdf', args.output/'figure.png')
    batches = [n.prim for n in compiled.root.walk() if isinstance(n.prim, MarkerBatchPrim)]
    report = dict(scene=dict(compiled.scene.stats), batches=len(batches),
                  packed_records=sum(len(b) for b in batches),
                  packed_bytes=sum(len(b.data) for b in batches),
                  diagnostics=compiled.report())
    (args.output/'stats.json').write_text(json.dumps(report, indent=2)+'\n')
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ')+'}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
