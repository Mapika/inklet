"""Rebuild a journal figure page: eight panels in the style of a Cell page.

The panels follow the plots of a published multi-panel figure on sexual
dimorphism in a connectome: cumulative connection counts, a decision
flowchart, stacked fractions, a weight scatter, cumulative distributions,
two pies with breakout bars, stacked bars with counts and proportion bars.
The microscopy panels of the original are left out. All data are simulated
or illustrative. The docs page "Rebuild a journal figure"
(docs/journal-figure.md) walks through the same code step by step.

    PYTHONPATH=src .venv/bin/python examples/journal_figure.py

Writes out/journal-figure/figure.svg, .pdf and .png and prints the lint
report. The gallery image is gallery/journal-figure.png:

    PYTHONPATH=src .venv/bin/python examples/journal_figure.py --gallery
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import inklet as i

ROOT = Path(__file__).resolve().parents[1]

# -- the preset ----------------------------------------------------------------

style = i.preset('scientific.cell')
blue, amber, magenta, grey, green, ink = style.theme.palette
pale = '#e4e4e4'
rng = random.Random(5)

# -- a: cumulative connections on log axes ---------------------------------------

growth = i.plot_spec(height=30, x=i.log((1, 1000)), y=i.log((1e4, 1e7)))
for total, share, color in [(2.2e6, '88.9%', grey), (1.9e5, '7.5%', blue), (9e4, '3.6%', amber)]:
    curve = [(10 ** (t / 20), total * (1 - .8 * math.exp(-t / 12))) for t in range(61)]
    growth.line(curve, stroke=color)
    growth.text(1000, total, share, anchor='se', offset=(0, -.6))
growth.vline(10, stroke=ink, stroke_dash=(.5, .5), stroke_width=style.theme.hairline)
growth.text(10, 1.2e4, 'noise', anchor='se', offset=(-.6, 0))
growth.text(10, 1.2e4, 'signal', anchor='sw', offset=(.6, 0))
growth.axes(x='weight', y='connections (cum.)')

# -- b: decision flowchart --------------------------------------------------------


def flowchart():
    scene = i.composition(64, 34)
    words = {'size': i.pt(5)}
    grey_box = {'fill': '#eeeeee', 'stroke': 'none', 'corner_radius': .5}
    steps = [('weight', 'weight > noise\nthreshold', 0, 0, grey_box, words),
             ('between', 'between isomorphic\ntypes', 26, 0, grey_box, words),
             ('test', 'difference ≥ 30%\nand p ≤ 0.1', 26, 13, grey_box, words),
             ('discard', 'discard', 0, 13,
              {'fill': 'none', 'stroke': ink, 'stroke_dash': (.6, .4), 'corner_radius': .5}, words),
             ('iso', 'isomorphic', 26, 26, {'fill': ink, 'stroke': 'none', 'corner_radius': .5},
              dict(words, text_fill='#ffffff')),
             ('dimo', 'dimorphic', 50, 26, {'fill': amber, 'stroke': 'none', 'corner_radius': .5},
              words)]
    for name, label, x, y, look, text in steps:
        scene.add(name, i.module(label, min_width=13, min_height=6, pad=.8,
                                 text_style=text, box_style=look), x=x, y=y)
    scene.link('weight:out', 'between:in', label='yes')
    scene.link('weight:s', 'discard:n', label='no')
    scene.link('between:s', 'test:n', label='yes')
    scene.link('between:out', 'dimo:n', label='no', route='orthogonal')
    scene.link('test:s', 'iso:n', label='no')
    scene.link('test:out', 'dimo:in', label='yes', route='orthogonal')
    return scene


# -- c: stacked fractions -------------------------------------------------------------

groups = ['in ♂', 'in ♀', 'out ♂', 'out ♀']
fractions = i.plot_spec(height=30, x=groups, y=(0, 1))
fractions.bars(groups, [[.99, .99, .52, .72], [.01, .01, .48, .28]], stacked=True,
               color=[ink, amber], name=['isomorphic', 'dimorphic'], width=.7)
fractions.axes(y='fraction of synapses', x_options={'rotate': 90})
fractions.legend(side='top')

# -- d: weight scatter on log axes ------------------------------------------------------

pairs = []
for _ in range(1500):
    male = 10 ** rng.uniform(0, 4.5)
    pairs.append((male, max(1., male * 10 ** rng.gauss(0, .25))))
dimorphic = [(m, f * 6) for m, f in pairs[:60] if f * 6 < 3e4]
weights = i.plot_spec(height=30, x=i.log((1, 1e5)), y=i.log((1, 1e5)))
weights.scatter(pairs, size=.5, color=grey, name='p > 0.1')
weights.scatter(dimorphic, size=.7, color=magenta, name='p ≤ 0.1')
weights.line([(1, 1), (1e5, 1e5)], stroke=ink, stroke_dash=(.6, .5),
             stroke_width=style.theme.hairline)
weights.axes(x='weight ♂', y='weight ♀')
weights.legend()

# -- e: cumulative distributions -----------------------------------------------------------

shares = i.plot_spec(height=30, x=(0, 1), y=(0, 1))
shares.ecdf([rng.betavariate(1.3, 2.5) for _ in range(200)], name='dimorphic types', stroke=amber)
shares.ecdf([rng.betavariate(.35, 6) for _ in range(400)], name='isomorphic types', stroke=ink)
shares.axes(x='fraction of dimorphic in- or outputs', y='fraction of types (cum.)')
shares.legend(corner='se')

# -- f: pies with breakout bars -----------------------------------------------------------------


def pies():
    rows = []
    for sex, iso, dimo, noise in [('♂', 24.8, 1.5, 73.7), ('♀', 24.8, .3, 74.9)]:
        p = i.polar(8)
        p.pie([iso, dimo, noise], color=[ink, amber, pale],
              labels=[f'{iso}%', f'{dimo}%', f'{noise}%'],
              name=['isomorphic', 'dimorphic', 'noise'] if sex == '♀' else None)
        p.breakout([0, 1], labels='{share:.1%}', gap=4,
                   title='without noise' if sex == '♂' else None)
        p.title(sex)
        if sex == '♀':
            p.legend(side='bottom', columns=3)
        rows.append(p.build())
    return i.column(rows, gap=3, align='left')


# -- g: stacked bars with counts ---------------------------------------------------------------

clusters = ['102', '79', '81', '116', '186', '153', '250', '249', '103', '89']
specific = [51, 43, 18, 40, 9, 26, 15, 14, 10, 6]
dimorphic_types = [1, 0, 7, 6, 3, 7, 6, 6, 3, 8]
isomorphic = [0, 0, 1, 3, 1, 3, 2, 4, 9, 18]
counts = i.plot_spec(height=30, x=(0, 60), y=clusters[::-1])
counts.bars(clusters, [specific, dimorphic_types, isomorphic], stacked=True, orient='h',
            width=.78, color=[blue, amber, grey], name=['specific', 'dimorphic', 'isomorphic'],
            labels=True, stroke='none')
counts.axes(x='cell types', y='enriched cluster')
counts.legend()

# -- h: proportion bars --------------------------------------------------------------------------

kinds = ['fru+/dsx-', 'fru-/dsx+', 'fru+/dsx+', 'fru-/dsx-']
proportion = i.plot_spec(height=14, x=(0, 1), y=['enriched', 'non-enriched'])
proportion.bars(['non-enriched', 'enriched'], [[.29, .55], [.01, .07], [0, .1], [.7, .28]],
                stacked=True, orient='h', width=.45, color=[blue, magenta, amber, pale],
                name=kinds, stroke='none')
proportion.axes(x='proportion of non-isomorphic types')
proportion.legend(side='bottom', columns=4)


# -- the page ------------------------------------------------------------------------------------

def make_document():
    doc = style.document(columns=12, share_plot_margins=True).letters()
    doc.add('growth', growth, row=0, column=0, colspan=4)
    doc.add('flowchart', flowchart(), row=0, column=4, colspan=5, align='nw')
    doc.add('fractions', fractions, row=0, column=9, colspan=3)
    doc.add('weights', weights, row=1, column=0, colspan=4)
    doc.add('shares', shares, row=1, column=4, colspan=4)
    doc.add('pies', i.component(pies), row=1, column=8, colspan=4, align='n')
    doc.add('counts', counts, row=2, column=0, colspan=6)
    doc.add('proportion', proportion, row=2, column=6, colspan=6)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=ROOT/'out/journal-figure')
    parser.add_argument('--gallery', action='store_true',
                        help='also write gallery/journal-figure.png')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    figure = make_document().compile()
    print(figure.report())
    figure.save(args.output/'figure.svg', args.output/'figure.pdf')
    (args.output/'figure.png').write_bytes(figure.to_png(dpi=300))
    if args.gallery:
        (ROOT/'gallery/journal-figure.png').write_bytes(figure.to_png(dpi=300))


if __name__ == '__main__':
    main()
