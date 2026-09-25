"""A dense, journal-page figure: thirteen panels on one 183 mm page.

Built with the `scientific.cell` preset and simulated data only. The layout
follows a multi-panel Cell figure: a circuit diagram, stacked and diverging
bars with counts, a dumbbell, a labelled scatter, a heatmap with its colorbar
and a zoomed inset, cumulative distributions, a dot plot over many
categories, a radar chart and a donut.

    PYTHONPATH=src .venv/bin/python examples/dense_figure.py

Writes out/dense-figure/figure.svg, .pdf and .png and prints the lint report.
The gallery image is gallery/dense-figure.png:

    scripts/rasterise.sh out/dense-figure/figure.svg gallery/dense-figure.png 3
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import inklet as i

ROOT = Path(__file__).resolve().parents[1]
STYLE = i.preset('scientific.cell')
BLUE, AMBER, MAGENTA, GREY, GREEN, INK = STYLE.theme.palette
PALE = '#e3e3e3'
rng = random.Random(2026)


# -- a: circuit schematic ----------------------------------------------------

def circuit():
    scene = i.composition(42, 30)
    boxes = [('sensory', 'sensory\nneurons', 0, 11, AMBER), ('pn', 'projection\nneurons', 15, 11, BLUE),
             ('lh', 'lateral\nhorn', 30, 1, GREY), ('mb', 'mushroom\nbody', 30, 21, GREY)]
    for name, label, x, y, color in boxes:
        scene.add(name, i.module(label, min_width=11, min_height=7, pad=.8,
                                 text_style={'size': i.pt(5)},
                                 box_style={'fill': i.mix(color, '#ffffff', .78), 'stroke': color,
                                            'corner_radius': .6}), x=x, y=y)
    scene.link('sensory:out', 'pn:in', route='straight')
    scene.link('pn:n', 'lh:in', route='orthogonal', corner=.6)
    scene.link('pn:s', 'mb:in', route='orthogonal', corner=.6)
    return scene


# -- b: stacked horizontal bars with counts -----------------------------------

CLUSTERS = ['102', '79', '81', '116', '186', '153', '250', '249']
SPECIFIC = [51, 43, 18, 40, 9, 26, 15, 14]
DIMORPHIC = [1, 0, 7, 6, 3, 7, 6, 6]
ISOMORPHIC = [0, 0, 1, 3, 1, 3, 2, 4]
b = i.plot_spec(height=26, x=(0, 60), y=CLUSTERS[::-1])
b.bars(CLUSTERS, [SPECIFIC, DIMORPHIC, ISOMORPHIC], stacked=True, orient='h', width=.78,
       colors=[BLUE, AMBER, GREY], names=['specific', 'dimorphic', 'isomorphic'],
       labels=True, stroke='none')
b.axes(x='cell types', y='cluster')
b.legend()

# -- c: dumbbell -------------------------------------------------------------

TYPES = ['DA1', 'VA1v', 'VA1d', 'DL3', 'VL2a', 'DC3', 'VM4']
FEMALE = [9.1, 6.2, 5.4, 3.3, 2.8, 2.2, 1.1]
MALE = [12.6, 8.9, 4.7, 5.1, 2.3, 3.0, 1.4]
c = i.plot_spec(height=26, x=(0, 14), y=TYPES[::-1])
c.dumbbell(TYPES, [FEMALE, MALE], orient='h', names=['female', 'male'], colors=[MAGENTA, GREEN])
c.axes(x='synapses / 10³')
c.legend()

# -- d: labelled scatter ------------------------------------------------------

cloud = [(rng.uniform(0, 100), max(0., rng.gauss(4, 4))) for _ in range(90)]
named = {'VA1v': (78, 55), 'MZ_lv': (60, 43), 'M_lvPNm45': (86, 43), 'VA1d': (75, 35),
         'M_vPNml63': (69, 28), 'DA1_lPN': (97, 13), 'VL2a': (5, 12), 'M_vPNml67': (4, 41)}
d = i.plot_spec(height=28, x=(0, 100), y=(0, 60))
d.line([(0, 2), (100, 26)], stroke=GREY, stroke_dash=(.8, .6), stroke_width=STYLE.theme.hairline)
d.scatter(cloud, size=.7, color=PALE, name='other')
d.scatter(list(named.values()), size=1.1, color=MAGENTA, name='pheromone')
d.label_points(list(named.values()), list(named))
d.axes(x='pheromone input / %', y='dimorphic output / %')
d.legend()

# -- e: heatmap with default ramp, colorbar and zoom inset ---------------------

SIDE = 36
blocks = [(0, 7), (7, 15), (15, 22), (22, 30), (30, 36)]
def weight(r, col):
    same = any(lo <= r < hi and lo <= col < hi for lo, hi in blocks)
    return max(0., (2.6 if same else .5) + rng.gauss(0, .55) + (1.2 if r == col else 0))
FIELD = [[weight(r, col) for col in range(SIDE)] for r in range(SIDE)]
zoom = i.plot_spec(width=11, height=11, x=(6.5, 14.5), y=(14.5, 6.5))
zoom.matrix([row[7:15] for row in FIELD[7:15]], x=range(7, 15), y=range(7, 15),
            scale=i.linear((0, 4.5)))
e = i.plot_spec(height=28, x=(-.5, SIDE - .5), y=(SIDE - .5, -.5))
e.matrix(FIELD, x=range(SIDE), y=range(SIDE), scale=i.linear((0, 4.5)))
e.axes(x='target', y='source', x_options={'ticks': []}, y_options={'ticks': []})
e.colorbar(side='bottom', label='log synapses', ticks=[0, 2, 4])
e.inset(zoom, side='right', zoom=(6.5, 14.5, 14.5, 6.5), width=None, plate=False)

# -- f: cumulative distributions ------------------------------------------------

f = i.plot_spec(height=28, x=(0, 1), y=(0, 1))
for name, color, shape in [('dimorphic', AMBER, 1.6), ('isomorphic', INK, 5.)]:
    samples = [rng.betavariate(shape, 2.2) for _ in range(160)]
    f.ecdf(samples, name=name, stroke=color)
f.axes(x='fraction of dimorphic inputs', y='cumulative fraction')
f.legend()

# -- g: dot plot over many categories -------------------------------------------

GLOMERULI = ['DA1', 'VA1v', 'VA1d', 'VA2', 'VC4', 'VA7l', 'VM5v', 'DL3', 'DL2d', 'DL1', 'VL2p',
             'VM6', 'DP1l', 'DM1', 'VM1', 'VC5', 'DL2v', 'VL1', 'DA2', 'DA3', 'VA6', 'VM7d',
             'DC3', 'VA3', 'VA4', 'VC3', 'DC2', 'VP1d', 'DL4', 'VM3', 'DM6', 'VM2', 'DP1m',
             'VP3', 'VM4', 'DM3']
base = [180, 125, 120, 90] + [rng.uniform(15, 75) for _ in GLOMERULI[4:]]
male = [v * rng.uniform(.9, 1.15) for v in base]
female = [v * rng.uniform(.75, 1.02) for v in base]
female[:3] = [128, 98, 102]
g = i.plot_spec(height=22, x=GLOMERULI, y=(0, 200))
g.dumbbell(GLOMERULI, [male, female], names=['male CNS', 'FAFB'], colors=[GREEN, MAGENTA],
           size=1.2)
g.axes(y='neurons', x='glomerulus', x_options={'rotate': 90})
g.legend(corner='ne', columns=2)

# -- h: radar ---------------------------------------------------------------------

def radar():
    p = i.polar(10, r=(0, 1), zero='up', winding='cw')
    p.radar_grid(['pheromones', 'hygro/thermo', 'aversive', 'attractive', 'unclear'])
    p.radar([.9, .35, .3, .25, .4], name='dimorphic', color=BLUE)
    p.radar([.45, .4, .42, .38, .44], name='remaining', color=INK, fill=False)
    p.legend(side='bottom', columns=2)
    return p.build()

# -- i: donut ------------------------------------------------------------------

def donut():
    p = i.polar(8, hole=4, zero='up', winding='cw')
    p.pie([73.7, 24.8, 1.5], colors=[PALE, INK, AMBER], names=['noise', 'isomorphic', 'dimorphic'])
    p.legend(side='bottom')
    return p.build()

# -- j: diverging horizontal bars -------------------------------------------------

PNS = ['VA1v_vPN', 'M_lvPNm45', 'MZ_lv2PN', 'M_vPNml67', 'VA1d_vPN', 'M_vPNml76',
       'VL2a_vPN', 'AL-AST1', 'M_l2PN3t18', 'DA1_lPN', 'ALON3', 'CB3447']
SPEC = [52, 40, 35, 32, 28, 27, 24, 19, 14, 12, 10, 8]
DIMO = [-33, -8, -4, -3, -9, -2, -14, -18, -3, -2, -1, -4]
j = i.plot_spec(height=30, x=(-40, 60), y=PNS[::-1])
j.bars(PNS, SPEC, orient='h', width=.72, fill=BLUE, names=['sex-specific'], stroke='none')
j.bars(PNS, DIMO, orient='h', width=.72, fill=AMBER, names=['dimorphic'], stroke='none')
j.vline(0, stroke=INK, stroke_width=STYLE.theme.stroke, front=True)
j.vline(9, stroke=INK, stroke_dash=(.6, .5), stroke_width=STYLE.theme.hairline, front=True)
j.axes(x='% output')
j.legend()

# -- k: cumulative counts on a log axis ---------------------------------------------

k = i.plot_spec(height=30, x=i.log((1, 1000)), y=i.log((1e4, 3e6)))
for total, color, name in [(2.2e6, INK, 'isomorphic'), (1.9e5, BLUE, 'sex-specific'),
                           (9e4, AMBER, 'dimorphic')]:
    points = [(10 ** (t / 20), total * (1 - .8 * math.exp(-(t / 20) * 1.6))) for t in range(0, 61)]
    k.line(points, stroke=color, name=name)
k.vline(10, stroke=GREY, stroke_dash=(.6, .5), stroke_width=STYLE.theme.hairline)
k.axes(x='weight', y='connections (cum.)')
k.legend()

# -- l: diverging correlation matrix ---------------------------------------------------

MARKERS = ['fru', 'dsx', 'Gad1', 'VGlut', 'ChAT', 'Tk', 'NPF', 'sNPF']
def correlation(a, b_):
    if a == b_: return 1.
    return max(-.95, min(.95, math.cos(a * 1.3 + b_ * .7) * .8 + rng.gauss(0, .12)))
CORR = [[0.] * len(MARKERS) for _ in MARKERS]
for r in range(len(MARKERS)):
    for col in range(r, len(MARKERS)):
        CORR[r][col] = CORR[col][r] = correlation(r, col) if r != col else 1.
l = i.plot_spec(height=30, x=MARKERS, y=MARKERS)
l.matrix(CORR, x=MARKERS, y=MARKERS, center=0)
l.axes(x_options={'rotate': 90})
l.colorbar(side='right', label='correlation', ticks=[-1, 0, 1])

# -- m: violin of fractions ---------------------------------------------------------------

GROUPS = {'fru+': [rng.betavariate(5, 2) for _ in range(60)],
          'dsx+': [rng.betavariate(3, 3) for _ in range(60)],
          'both': [rng.betavariate(6, 1.6) for _ in range(60)],
          'none': [rng.betavariate(1.4, 5) for _ in range(60)]}
m = i.plot_spec(height=30, x=list(GROUPS), y=(0, 1))
m.violin(GROUPS, colors=[i.mix(color, '#ffffff', .45) for color in (BLUE, MAGENTA, AMBER, GREY)])
m.axes(y='fraction dimorphic')


def make_document():
    doc = STYLE.document(columns=12, share_plot_margins=True).letters()
    doc.add('circuit', circuit(), row=0, column=0, colspan=3, align='nw')
    doc.add('bars', b, row=0, column=3, colspan=5)
    doc.add('dumbbell', c, row=0, column=8, colspan=4)
    doc.add('scatter', d, row=1, column=0, colspan=4)
    doc.add('heatmap', e, row=1, column=4, colspan=4)
    doc.add('ecdf', f, row=1, column=8, colspan=4)
    doc.add('dots', g, row=2, column=0, colspan=7)
    doc.add('radar', i.component(radar), row=2, column=7, colspan=3, align='n')
    doc.add('donut', i.component(donut), row=2, column=10, colspan=2, align='n')
    doc.add('diverging', j, row=3, column=0, colspan=3)
    doc.add('log', k, row=3, column=3, colspan=3)
    doc.add('correlation', l, row=3, column=6, colspan=3)
    doc.add('violin', m, row=3, column=9, colspan=3)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=ROOT/'out/dense-figure')
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    compiled = make_document().compile()
    print(compiled.report())
    compiled.save(output/'figure.svg', output/'figure.pdf')
    (output/'figure.png').write_bytes(compiled.to_png(dpi=300))


if __name__ == '__main__':
    main()
