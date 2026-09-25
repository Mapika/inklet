"""A cohort study on one page: six panels with the plot types added after 4.1.

One 183 mm page with the `scientific.cell` preset tells one simulated story:

    a  an embedding of 12,000 cells, coloured and named by cluster
    b  a dot plot of marker genes per cluster, with a colorbar and size key
    c  split violins of one gene by sex in three clusters
    d  box plots and a swarm with stacked significance brackets
    e  Kaplan-Meier curves for two arms with a number-at-risk table
    f  a forest plot of hazard ratios by subgroup

All data are simulated or illustrative, and the P values are made up: no
test is run. The docs page is docs/cohort-figure.md.

    PYTHONPATH=src .venv/bin/python examples/cohort_figure.py

Writes out/cohort-figure/figure.svg, .pdf and .png and prints the lint
report. The gallery image is gallery/cohort-figure.png:

    PYTHONPATH=src .venv/bin/python examples/cohort_figure.py --gallery
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import inklet as i

ROOT = Path(__file__).resolve().parents[1]

style = i.preset('scientific.cell')
blue, amber, magenta, grey, green, ink = style.theme.palette
rng = random.Random(8)

# -- a: embedding ---------------------------------------------------------------

clusters = {'T cells': (-4.2, 2.4), 'NK': (-1.2, 4.6), 'B cells': (-4.6, -2.8),
            'Monocytes': (2.8, 1.6), 'DC': (5.2, 4.4), 'Platelets': (3.6, -4.2)}
umap, names = [], []
for name, (cx, cy) in clusters.items():
    for _ in range(rng.randint(900, 3000)):
        turn = rng.uniform(0, 2 * math.pi)
        umap.append((cx + .5 * math.cos(turn) + rng.gauss(0, .55),
                     cy + .35 * math.sin(turn) + rng.gauss(0, .45)))
        names.append(name)
cells = i.plot_spec(height=40, x=(-8, 8.5), y=(-7, 7))
cells.embedding(umap, names, arrows='UMAP', size=.3)

# -- b: dot plot ------------------------------------------------------------------

genes = ['Cd3e', 'Nkg7', 'Ms4a1', 'Lyz2', 'Fcer1a', 'Ppbp']
order = list(clusters)
markers = {'T cells': {'Cd3e'}, 'NK': {'Nkg7', 'Cd3e'}, 'B cells': {'Ms4a1'},
           'Monocytes': {'Lyz2'}, 'DC': {'Fcer1a', 'Lyz2'}, 'Platelets': {'Ppbp'}}
fraction = [[rng.uniform(.6, .95) if g in markers[c] else rng.uniform(0, .2)
             for g in genes] for c in order]
mean = [[rng.uniform(1.8, 3) if g in markers[c] else rng.uniform(0, .7)
         for g in genes] for c in order]
dots = i.plot_spec(height=40, x=genes, y=order[::-1])
dots.dotplot(fraction[::-1], mean[::-1])
dots.axis('bottom', rotate=90, spine=False).axis('left', spine=False)
dots.colorbar(label='mean expression', length=14)
dots.size_key(title='fraction', format='{:.0%}')

# -- c: split violins ---------------------------------------------------------------

groups = ['T cells', 'NK', 'Monocytes']
female = {g: [rng.gauss(2.2 + .5 * k, .6) for _ in range(90)] for k, g in enumerate(groups)}
male = {g: [rng.gauss(2.0 + .2 * k, .7) for _ in range(80)]
        + [rng.gauss(4.6, .3) for _ in range(8 + 6 * k)] for k, g in enumerate(groups)}
violins = i.plot_spec(height=32, x=groups, y=(0, 6))
violins.split_violin(female, male, name=['female', 'male'], quartiles=True,
                     color=[magenta, green])
violins.axes(y='expression / log CPM').legend(side='top')

# -- d: brackets --------------------------------------------------------------------

doses = ['vehicle', 'low', 'mid', 'high']
response = {d: [rng.gauss(m, .45) for _ in range(10)]
            for d, m in zip(doses, (3.0, 3.3, 4.6, 5.2))}
signif = i.plot_spec(height=32, x=doses, y=(0, 11))
signif.boxplot(response, outliers=False).swarm(response, color=[blue] * 4)
signif.brackets([('vehicle', 'low', .31), ('vehicle', 'mid', 3e-4),
                 ('vehicle', 'high', 2e-6), ('low', 'high', 8e-5),
                 ('mid', 'high', .042)], hide_ns=True)
signif.axes(y='IFN score / a.u.')

# -- e: survival ------------------------------------------------------------------


def arm(rate, n=70):
    durations, events = [], []
    for _ in range(n):
        event, dropout = rng.expovariate(rate), rng.uniform(8, 60)
        durations.append(round(min(event, dropout, 36), 1))
        events.append(event <= min(dropout, 36))
    return durations, events


months = [0, 12, 24, 36]
survival = i.plot_spec(height=32, x=(0, 36), y=(0, 1))
survival.kaplan_meier({'placebo': arm(1 / 16), 'treated': arm(1 / 34)},
                      color=[ink, blue], pvalue=.002)
survival.axes(x='time / months', y='survival', x_options={'ticks': months})
survival.legend(corner='ne')
survival.at_risk(ticks=months)

# -- f: forest plot ---------------------------------------------------------------

subgroups = [
    'Age',
    {'label': '< 65', 'estimate': .58, 'low': .40, 'high': .84, 'weight': 38, 'n': 82},
    {'label': '≥ 65', 'estimate': .71, 'low': .46, 'high': 1.10, 'weight': 24, 'n': 58},
    'Sex',
    {'label': 'female', 'estimate': .55, 'low': .35, 'high': .86, 'weight': 27, 'n': 66},
    {'label': 'male', 'estimate': .70, 'low': .47, 'high': 1.05, 'weight': 35, 'n': 74},
    {'label': 'Overall', 'estimate': .63, 'low': .48, 'high': .83, 'summary': True},
]


def forest():
    # Built when the page compiles, so the preset's type sizes apply.
    return i.forest(subgroups, log=True, limits=(.25, 2), measure='HR',
                    right=['ci', 'n'], label='hazard ratio', width=24,
                    summary_line=True)


def make_document():
    doc = style.document(columns=12, share_plot_margins=True).letters()
    doc.add('cells', cells, row=0, column=0, colspan=4)
    doc.add('dots', dots, row=0, column=4, colspan=5)
    doc.add('violins', violins, row=0, column=9, colspan=3)
    doc.add('signif', signif, row=1, column=0, colspan=3)
    doc.add('survival', survival, row=1, column=3, colspan=4)
    doc.add('forest', i.component(forest), row=1, column=7, colspan=5, align='n')
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=ROOT/'out/cohort-figure')
    parser.add_argument('--gallery', action='store_true',
                        help='also write gallery/cohort-figure.png')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    figure = make_document().compile()
    print(figure.report())
    figure.save(args.output/'figure.svg', args.output/'figure.pdf')
    png = figure.to_png(dpi=300)
    (args.output/'figure.png').write_bytes(png)
    if args.gallery:
        (ROOT/'gallery/cohort-figure.png').write_bytes(png)


if __name__ == '__main__':
    main()
