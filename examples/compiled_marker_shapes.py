"""Five accelerated filled marker shapes with native axes and vector exports."""
import argparse
from pathlib import Path
import random
import inklet as i
from inklet.plot.marks import scatter

CAPTION = '''Five filled marker shapes with simulated observations. Each panel
contains 2,500 points with varying sizes and two overlapping colour groups.
The browser uses packed WebGL2 or Canvas layers; SVG and PDF retain vector
markers. Marker order, transparency and panel clipping are shared by all modes.
MIT, Mark Marosi.'''


def make_document():
    rng = random.Random(3905)
    doc = i.preset('scientific.general').customize(width=210, margin=6, gap=10).document(columns=3, row_gap=10).letters()
    for index, shape in enumerate(('circle', 'square', 'triangle', 'diamond', 'star')):
        p = i.panel(38, 36, x=(-3, 3), y=(-3, 3))
        points = [(rng.gauss((k % 2)*1.2-.6, .9), rng.gauss(0, 1)) for k in range(2500)]
        layer = scatter(p, points, marker=shape, size=[rng.uniform(.35, 1.5) for _ in points],
                  color=['#245b8a' if k % 2 else '#c87942' for k in range(len(points))],
                  stroke='none', fill_opacity=.35)
        p.draw(i.window(i.as_drawn(layer), p.area))
        p.axes(x='Coordinate x', y='Coordinate y')
        doc.add(shape, p.build(), row=index//3, column=index%3)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/compiled-marker-shapes'))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    compiled = make_document().compile()
    if any(d.severity == 'error' for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    (args.output/'index.html').write_text(compiled.scene.to_html(title='Filled marker shapes'), encoding='utf-8')
    compiled.save(args.output/'figure.svg', args.output/'figure.pdf', args.output/'figure.png')
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n', ' ')+'}\n')
    print(args.output/'index.html')


if __name__ == '__main__':
    main()
