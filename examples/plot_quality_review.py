"""Numeric-axis regression specimens with original simulated measurements."""
import argparse
from pathlib import Path

import inklet as i


CAPTION = '''Original simulated measurements, not experimental results.
(a) A line varying by five units around one million. (b) A scatter plot whose
horizontal coordinates span five femtoseconds. (c) Horizontal uncertainty bars
with an explicitly supplied half-width of 0.2 femtoseconds. (d) A line varying
by half a unit around one trillion. Axis labels must distinguish the measured
positions without changing the underlying data or units.
Recipe and figure: MIT, Mark Marosi.
'''


def make_document():
    doc = i.preset('scientific.general').customize(
        width=220, margin=6, gap=12,
    ).document(columns=2, share_plot_margins=True).letters()
    for index, (name, domain, xlabel) in enumerate([
        ('large', (1e6, 1e6 + 5), 'Frequency / Hz'),
        ('small', (0, 5e-15), 'Time / s'),
        ('intervals', (0, 5e-15), 'Time / s'),
        ('narrow', (1e12, 1e12 + .5), 'Frequency / Hz'),
    ]):
        points = [(domain[0] + (domain[1] - domain[0]) * j / 5, y)
                  for j, y in enumerate([1, 2, 1.5, 3, 2.5, 4])]
        plot = i.plot_spec(height=45, x=domain, y=(0, 5))
        if name in ('small', 'intervals'):
            if name == 'intervals':
                plot.errorbars(points[1:-1], xerr=.2e-15, stroke='#34786b')
            plot.scatter(points, color='#34786b', size=1)
        else:
            plot.line(points, stroke='#4774a0')
        plot.axes(x=xlabel, y='Response')
        doc.add(name, plot, row=index // 2, column=index % 2)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/plot-quality'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    figure = make_document().compile()
    figure.save(args.output / 'figure.svg', args.output / 'figure.png')
    (args.output / 'caption.txt').write_text(CAPTION, encoding='utf-8')
    print(figure.report())


if __name__ == '__main__':
    main()
