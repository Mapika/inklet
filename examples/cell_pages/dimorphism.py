"""Connection and network dimorphism: a dense Cell page (panels A-Q) on the 4.4 API.

The 5.0 acceptance test. Everything is placed by the 12-column document grid,
measured composition (stacks, graphs, links), catalog plots and the label
placement engine: there are no page or panel coordinates, no per-label
offsets and no hand-placed legends. Where 4.4 cannot express the reference,
the panel is the closest honest approximation and the gap is logged in
examples/cell_pages/GAPS-dimorphism.md.

Data come from the Sep 13 reconstruction in examples/inspo/: the released
MaleCNS/FlyWire tables summarised in computed.npz, the transcribed values in
authored_charts.TRANSCRIBED, the published communities, and the real anatomy
cache projected by examples/inspo/anatomy.py.

    PYTHONPATH=src .venv/bin/python -W error::DeprecationWarning \\
        examples/cell_pages/dimorphism.py

Writes out/cell-pages/dimorphism.{svg,pdf,png} and prints the lint report.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path('/home/markmarosi/projects/inklet')
INSPO = ROOT/'examples/inspo'
sys.path.insert(0, str(INSPO))
from anatomy import Anatomy                      # noqa: E402  (projection code)
from authored_charts import TRANSCRIBED          # noqa: E402  (reference readings)

STYLE = i.preset('scientific.cell')
BLUE, AMBER, MAGENTA, GREY, GREEN, INK = STYLE.theme.palette
PALE = '#ececec'
RED = '#c62d2b'
LIGHT_BLUE = '#bcdbe6'
HAIR = STYLE.theme.hairline
PT5 = i.pt(5)


# -- data ------------------------------------------------------------------------

def load(data_dir: Path, chart_dir: Path):
    d = dict(np.load(chart_dir/'computed.npz'))
    communities = pd.read_feather(data_dir/'communities.feather').sort_values('community_id')
    clusters = json.loads((chart_dir.parent/'cluster-chart-data.json').read_text())
    return d, communities, clusters


# -- A: cumulative connection weights ---------------------------------------------

def panel_a(d):
    """The key under the plot, as in the reference, unless beside it makes the page shorter."""
    return i.choose(below=cumulative(d, side='bottom'), beside=cumulative(d, corner='best'))


def cumulative(d, **key):
    grid = d['weight_grid']
    totals = [d[f'cdf{k}'] for k in range(3)]
    everything = sum(t[-1] for t in totals)
    p = i.plot_spec(height=24, x=i.log((1, 1000)), y=i.log((1e4, 4e7)))
    for k, color in [(0, INK), (2, BLUE), (1, AMBER)]:
        share = f'{100 * totals[k][-1] / everything:.1f}%'
        p.line(list(zip(grid, np.maximum(totals[k], 1e4))), stroke=color, name=share)
    noise_c, noise_s = float(d['noise_connection_pct']), float(d['noise_synapse_pct'])
    # The reference splits these notes either side of the threshold; annotate(side='w')
    # is overridden when the west side is short of room (see GAPS), so one note carries both.
    p.vline(10, stroke=INK, stroke_dash=(.4, .4), stroke_width=HAIR)
    p.annotate(10, 1.5e7, f'noise ← | → signal\n{noise_c:.0f}% | {100 - noise_c:.0f}% of connections\n'
                          f'{noise_s:.0f}% | {100 - noise_s:.0f}% of synapses',
               side='n', leader=False, size=PT5)
    p.label_lines(where='end')
    p.axes(x='weight (♂)', y='no. of connections (cum.)')
    dot = lambda color: i.marker('circle', 1.2, fill=color, stroke='none')
    p.legend(title='cell types', plate=False, **key,
             entries=[('isomorphic', dot(INK)), ('dimorphic', dot(AMBER)), ('sex-specific', dot(BLUE))])
    return p


# -- anatomy helpers (projection by examples/inspo/anatomy.py) ---------------------

class Artwork:
    """Real anatomy in the plotting frame, wrapped for AnatomyView cells."""

    def __init__(self, data_dir):
        self.a = Anatomy(data_dir)

    def camera(self, view='front'):
        a = self.a
        return Anatomy.camera(a.frame((0, 0, 1, 1), view=view), view)

    def runs(self, body, step=3):
        """Unbranched skeleton runs in 3D, every `step`-th node plus both ends."""
        xyz, ids, parents = self.a.skeleton(int(body))
        lookup = {int(n): k for k, n in enumerate(ids)}
        children = np.zeros(len(ids), int)
        for parent in parents:
            if parent in lookup:
                children[lookup[parent]] += 1
        out = []
        for start in np.flatnonzero(children != 1):
            if parents[start] not in lookup:
                continue
            chain, current = [start], start
            while parents[current] in lookup:
                current = lookup[parents[current]]
                chain.append(current)
                if children[current] != 1:
                    break
            keep = chain[::step] + ([chain[-1]] if (len(chain) - 1) % step else [])
            out.append([tuple(xyz[k]) for k in keep])
        return out

    def view(self, reference, width, view='front', height=None, pad=.5):
        """An AnatomyView whose height follows the reference's projected aspect."""
        pts = np.asarray(reference)
        axes = {'front': (0, 1), 'dorsal': (0, 2)}[view]
        aspect = np.ptp(pts[:, axes[1]]) / np.ptp(pts[:, axes[0]])
        natural = width * aspect
        h = natural if height is None else min(height, natural)
        w = width if h == natural else h / aspect
        return i.anatomy_view([tuple(p) for p in pts[::max(1, len(pts) // 4000)]],
                              width=w, height=h, camera=self.camera(view), pad=pad)

    def mesh_points(self, *names):
        return np.concatenate([self.a.mesh(n)[0] for n in names])


# -- B: vpoEN in both sexes ------------------------------------------------------

def panel_b(art: Artwork):
    a = art.a
    ids = a.ids('vpoEN', side='L')
    female = [a.display_mesh('female-' + str(b), 3000) for b in a.manifest['female_groups']['vpoEN']]
    lines = [r for b in ids for r in art.runs(b)]
    points = [p for r in lines for p in r]
    brain = art.mesh_points('male-brain')

    def arbors(width, view):
        v = art.view(points, width, view)
        for k, mesh in enumerate(female):
            v.surface(f'female-{k}', mesh, color=MAGENTA, opacity=.45)
        v.paths('male', lines, color=GREEN, stroke_width=.12, opacity=.75, depth_cue=0)
        return v.build()

    def locator(width, view):
        v = art.view(brain, width, view)
        v.surface('brain', a.display_mesh('male-brain', 2500), color='#dddddd', opacity=.5)
        v.paths('vpoEN', lines, color='#555555', stroke_width=.1, depth_cue=0)
        return v.build()

    def factory(*, width, height):
        side = width * .38
        caption = lambda s: i.text(s, fill=GREY, size=PT5)
        left = i.vstack([locator(side, 'front'), caption('frontal'),
                         locator(side, 'dorsal'), caption('dorsal')], gap=.8)
        right = i.vstack([arbors(width - side - 2, 'front'), arbors(width - side - 2, 'dorsal')], gap=1.5)
        head = i.hstack([i.text('vpoEN (isomorphic)'), i.text('♂', fill=GREEN, size=i.pt(9)),
                         i.text('♀', fill=MAGENTA, size=i.pt(9))], gap=2, align='center')
        return i.vstack([head, i.hstack([left, right], gap=2, align='center')], gap=1, align='left')
    return i.component(factory, responsive=True)


# -- C: connection-level dimorphism --------------------------------------------------

def node(letter, color, *, hollow=False):
    return i.circle(i.text(letter, fill=color if hollow else 'white'), width=3.4, height=3.4,
                    fill='white' if hollow else color, stroke=color,
                    stroke_width=HAIR, stroke_dash=(.5, .4) if hollow else None)


def panel_c():
    """Three cell types in two columns (male, female), laid out by the graph engine.

    Composing the circles with hstack/vstack and joining them with
    i.connect(within=...) misplaces nested endpoints (see GAPS), so the rows
    are graph ranks, each row label joined to its row by a hidden same-rank edge.
    """
    def factory():
        rows = [('AVLP569', 'female-specific', 's', BLUE), ('vpoEN', 'isomorphic', 'i', INK),
                ('aSP10C_a', 'dimorphic', 'd', AMBER)]
        nodes, edges = {}, []
        for k, (name, kind, letter, color) in enumerate(rows):
            nodes[f'label{k}'] = i.vstack([i.text(name), i.text(f'({kind})', size=PT5)],
                                          gap=.2, align='right')
            nodes[f'm{k}'] = node(letter, color, hollow=k == 0)
            nodes[f'f{k}'] = node(letter, color)
        hidden = {'stroke': 'none', 'head': 'none', 'same_rank': True}
        link = {'stroke': AMBER, 'stroke_width': STYLE.theme.thick}
        edges += [edge for k in range(3)
                  for edge in ((f'label{k}', f'm{k}', hidden), (f'm{k}', f'f{k}', hidden))]
        edges += [('m0', 'm1', {**link, 'stroke_dash': (.6, .5), 'label': i.text('0')}),
                  ('f0', 'f1', {**link, 'label': i.text('23')}),
                  ('m1', 'm2', {**link, 'label': i.text('420')}),
                  ('f1', 'f2', {**link, 'label': i.text('237')})]
        g = i.graph(nodes, edges, direction='down', rank_gap=4.5, gap=1.6).build()
        head = i.hstack([i.text('♂', size=i.pt(10)), i.text('♀', size=i.pt(10))], gap=2)
        notes = i.vstack([i.vstack([i.text('connection\nby definition', align='left', size=PT5),
                                    i.text('dimorphic', fill=AMBER, size=PT5)], align='left'),
                          i.vstack([i.text('connection\npotentially', align='left', size=PT5),
                                    i.text('dimorphic', fill=AMBER, size=PT5)], align='left')],
                         gap=5, align='left')
        body = i.hstack([i.vstack([head, g], gap=1, align='right'), notes], gap=1.5, align='center')
        return i.vstack([i.text('connection-level dimorphism'), body], gap=1, align='right')
    return factory()


# -- D: the worked t-test ---------------------------------------------------------

def table(headers, values, tint):
    return i.value_table([values], headers=headers, font_size=PT5, header_size=PT5,
                         pad=(.6, .3), min_cell_width=5.2, header_fill=tint,
                         stroke='#aaaaaa', stroke_width=HAIR)


def panel_d(art: Artwork):
    a = art.a
    ids = a.ids('aSP10C_a', side='R')
    lines = [r for b in ids for r in art.runs(b)]
    central = art.mesh_points('central-brain')

    def factory(*, width, height):
        green, pink = '#dfead8', '#f3dcea'
        steps = [(['left', 'right'], [202, 218], [107, 130], 'scale\nweights'),
                 (['left', 'right'], [159.6, 172.2], [107, 130], 'square\nroot'),
                 (['mean', 'std'], [12.9, .35], [10.9, .75], 't-statistics')]
        # Graph ranks rather than stacks joined by i.connect(within=...), which
        # misplaces nested endpoints (see GAPS).
        nodes, edges = {}, []
        arrow = {'stroke': INK, 'stroke_width': HAIR}
        for k, (headers, male, female, note) in enumerate(steps):
            nodes[f'm{k}'] = table(headers, male, green)
            nodes[f'f{k}'] = table(headers, female, pink)
            if k:
                edges += [(f'm{k - 1}', f'm{k}', {**arrow, 'label': i.text(steps[k - 1][3], size=PT5)}),
                          (f'f{k - 1}', f'f{k}', arrow)]
        nodes['test'] = table(['t', 'p'], [3.44, .08], '#eeeeee')
        nodes['corrected'] = table(['p'], [.55], '#eeeeee')
        nodes['verdict'] = i.text('connection\nisomorphic', size=PT5)
        edges += [('m2', 'test', {**arrow, 'label': i.text('t-statistics', size=PT5)}),
                  ('f2', 'test', arrow),
                  ('test', 'corrected', {**arrow, 'label': i.text('FDR correction', size=PT5)}),
                  ('corrected', 'verdict', {'stroke': 'none', 'head': 'none', 'same_rank': True})]
        flow = i.graph(nodes, edges, direction='down', rank_gap=3.2, gap=1.5).build()
        sexes = i.hstack([i.text('♂', fill=GREEN, size=i.pt(9)), i.text('♀', fill=MAGENTA, size=i.pt(9))],
                         gap=14)
        tables = i.vstack([sexes, flow], gap=1)
        pair = i.graph({'v': i.hstack([i.text('vpoEN'), i.marker('circle', 1.6, fill=INK)], gap=.8),
                        's': i.hstack([i.text('aSP10C_a'), i.marker('circle', 1.6, fill=INK)], gap=.8)},
                       [('v', 's')], layout='layered', direction='down', rank_gap=1.5).build()
        side = max(pair.bbox.width, width - tables.bbox.width - 2)
        v = art.view(central, side)
        v.surface('brain', a.display_mesh('central-brain', 2500), color='#eeeeee', opacity=.6)
        v.paths('aSP10C_a', lines, color=GREEN, stroke_width=.12, opacity=.8, depth_cue=0)
        left = i.vstack([pair, v.build()], gap=2, align='right')
        return i.hstack([left, tables], gap=2, align='top')
    # The table flow has a fixed width; the brain takes what is left. Built at
    # zero width, the panel is at its narrowest, which is what the cell must reserve.
    return i.component(factory, responsive=True), lettered_width(factory(width=0, height=None))


# -- E: the classification flow ---------------------------------------------------

def step(text, fill='#e6e6e6', color=INK, **style):
    return i.box(i.text(text, fill=color, size=PT5), pad=.6, radius=.3, fill=fill,
                 stroke=style.pop('stroke', 'none'), **style)


def panel_e():
    def factory():
        discard = i.vstack([step('discard', fill='white', stroke=INK, stroke_dash=(.6, .4),
                                 stroke_width=HAIR),
                            i.text('~80% of connections\n~10% of synapses', size=PT5)], gap=.6)
        test = i.vstack([i.text('t-statistics', fill=GREY), step('sex difference ≥ 30%\nand p ≤ 0.1')],
                        gap=.4)
        nodes = {'threshold': step('conn. weight >\nnoise threshold'),
                 'isotypes': step('conn. between\nisomorphic types'),
                 'discard': discard,
                 'specific': step('conn. involves\nsex-specific type(s)'),
                 'test': test,
                 'iso': step('isomorphic\nconnection', fill=INK, color='white'),
                 'dim': step('dimorphic\nconnection', fill=AMBER)}
        # "yes" from the first test runs across, as in the reference; the two
        # outcomes share the last rank.
        edges = [('threshold', 'isotypes', {'label': 'yes', 'same_rank': True}),
                 ('threshold', 'discard', 'no'),
                 ('isotypes', 'iso', 'yes'), ('isotypes', 'specific', 'no'),
                 ('specific', 'test', 'no'), ('specific', 'dim', 'yes'),
                 ('test', 'dim', 'yes'), ('test', 'iso', 'no'),
                 ('iso', 'dim', {'same_rank': True, 'stroke': 'none', 'head': 'none'})]
        return i.graph(nodes, edges, layout='layered', direction='down', rank_gap=2.5, gap=1.5).build()
    return factory()


# -- F: vpoEN input and output fractions ------------------------------------------------

def panel_f():
    bars = TRANSCRIBED['vpoen_bars']                    # (dimorphic, isomorphic) per bar
    keys = ['in-m', 'in-f', 'out-m', 'out-f']
    cats = i.categories({k: INK for k in keys},
                        labels={'in-m': 'in ♂', 'in-f': 'in ♀', 'out-m': 'out ♂', 'out-f': 'out ♀'})
    p = i.plot_spec(height=24, x=cats.scale(), y=(0, 1))
    p.bars(keys, [[b[1] for b in bars], [b[0] for b in bars]], stacked=True, width=.72,
           color=[INK, AMBER], name=['isomorphic', 'dimorphic'],
           stroke='none')
    p.axes(y='fraction of synapses', x_options={'rotate': 90})  # four distinct labels do not fit flat
    p.title('vpoEN')
    p.legend(side='bottom', columns=1)
    return p


# -- G: all type-to-type connections -------------------------------------------------

def superscript(v):
    if v == 0:
        return '0'
    return '10' + str(round(math.log10(v))).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))


def panel_g(d):
    s = d['scatter']
    scale = lambda: i.symlog((0, 1e5), linthresh=1)
    p = i.plot_spec(height=24, x=scale(), y=scale())
    p.rect(0, 0, 5, 1e5, fill=PALE, stroke='none')
    p.rect(0, 0, 1e5, 5, fill=PALE, stroke='none')
    buckets = [('> 0.1', '#aaaaaa', .1, 2), ('≤ 0.1', GREEN, .05, .1),
               ('≤ 0.05', AMBER, .01, .05), ('≤ 0.01', RED, -1, .01)]
    for name, color, lo, hi in buckets:
        flag = (s[:, 2] > lo) & (s[:, 2] <= hi)
        p.scatter(s[flag, :2].tolist(), size=.35, color=color, name=name, raster=True, fill_opacity=.6)
    p.line([(1, 1), (1e5, 1e5)], stroke=INK, stroke_width=HAIR)
    for factor in (.7, 1.3):
        p.line([(1, factor), (1e5 / 1.3, 1e5 / 1.3 * factor)], stroke=INK,
               stroke_dash=(.5, .4), stroke_width=HAIR)
    p.annotate(2, 2, 'noise', side='sw', leader=False)
    ticks = {'ticks': [0, 1, 1e2, 1e4], 'format': superscript}
    p.axes(x='weight ♂ (scaled)', y='weight ♀', x_options=ticks, y_options=ticks)
    p.title('all type-to-type connections')
    p.legend(title='p-values\n(FDR-corrected)', corner='se')
    return p


# -- H: dimorphic fraction per cell type ------------------------------------------------

def panel_h(d):
    p = i.plot_spec(height=24, x=(1, 0), y=(0, 1))
    for flag, color in [(1, AMBER), (0, INK)]:
        for prefix, dash in [('type', None), ('expr', (.4, .4))]:
            values = d[f'{prefix}_fraction_{flag}']
            p.ecdf(values.tolist(), complementary=True, stroke=color, stroke_dash=dash)
    marked = [(.3, float(np.mean(d[f'{prefix}_fraction_0'] >= .3))) for prefix in ('type', 'expr')]
    p.label_points(marked, [f'{100 * y:.1f}%' for _, y in marked])
    line = lambda dash: i.polyline([(0, 0), (3, 0)], stroke=INK, stroke_width=STYLE.theme.stroke,
                                   stroke_dash=dash)
    p.axes(x='fraction of dimorphic\nin- or outputs', y='fraction of types (cumulative)',
           x_options={'ticks': [1, .5, 0]})

    shares = [.006, .011, .031, .069]                   # transcribed from the reference
    bars = i.plot_spec(height=24, x=['a', 'b', 'c', 'd'], y=(0, .075))
    bars.bars(['a', 'b', 'c', 'd'], shares, width=.7, bar_colors=[BLUE, '#e07b53', '#8fb4dd', '#c8bd8a'],
              stroke='none')
    bars.axis('right', ticks=[0, .02, .04, .06], format='{:.0%}', label='fraction of neurons')
    bars.axis('bottom', labels=False, tick_size=0)

    # As in the reference, the key sits in the empty top left of the data.
    p.legend(corner='nw', plate=False,
             entries=[('dimorphic types', AMBER), ('isomorphic types', INK),
                      ('all types', line(None)), ('fru+|dsx+ only', line((.4, .4)))])
    h = i.subfigure(columns=[3, 1], gap=1)
    h.add('curves', p, row=0, column=0)
    h.add('neurons', bars, row=0, column=1)
    return h


# -- I, J: pies expanded into bars -------------------------------------------------------

def pies(label, values, outline, legend):
    iso, dim, noise = values
    small = {'size': PT5}
    p = i.polar(6.5)                    # breakout() turns the pie to face its bar
    p.pie([iso, dim, noise], color=[INK, AMBER, PALE], name=['isomorphic', 'dimorphic', 'noise'],
          labels=[f'{iso}%', f'{dim}%', f'{noise}%'], label_options=small,
          stroke=outline, stroke_width=STYLE.theme.stroke)
    p.breakout([0, 1], labels='{share:.1%}', label_options=small, title='without\nnoise', width=2)
    if legend:
        p.legend(side='left')
    # The sex symbol stands at the pie's upper left, as in the reference.
    return i.hstack([i.text(label), p.build()], gap=.5, align='top')


def panel_pies(axis_label, male, female, legend=False):
    def factory():
        column = i.vstack([pies('♂', male, GREEN, False), pies('♀', female, MAGENTA, legend)],
                          gap=1, align='right')
        return i.hstack([i.text(axis_label, angle=90), column], gap=1, align='center')
    return i.component(factory)


# -- K: where the dimorphic connections are ------------------------------------------------

def panel_k(art: Artwork, d):
    a = art.a
    xyz = a.warp(d['syn_xyz_nm'])
    signed = d['syn_signed']
    ramp = i.ramp([MAGENTA, '#f4f0f2', GREEN])
    brain = art.mesh_points('male-brain')

    def colorbar(length):
        return i.colorbar(ramp, domain=(-1, 1), length=length, ticks=[-1, 0, 1],
                          label='male − female\nconnection weight',
                          format=lambda t: {-1: 'more in female', 0: '0', 1: 'more in male'}[round(t)])

    def factory(*, width, height):
        # Measured composition: the key's own width decides what the view gets.
        key_width = colorbar(20).bbox.width + 1.5
        v = art.view(brain, width - key_width)
        v.surface('brain', a.display_mesh('male-brain', 3000), color='#f4f4f4', opacity=.7)
        edges = np.linspace(-1, 1, 9)
        for lo, hi in zip(edges, edges[1:]):
            flag = (signed >= lo) & (signed <= hi)
            if flag.any():
                v.markers(f'bin{lo:+.2f}', [tuple(p) for p in xyz[flag]],
                          color=ramp((lo + hi) / 4 + .5), radius=.25, opacity=.7, depth_cue=0)
        key = colorbar(v.height * .9)
        view = v.build()
        body = i.hstack([view, key], gap=1.5, align='center')
        return i.vstack([body, i.text('synapses in dimorphic connections')], gap=1)
    return i.component(factory, responsive=True)


# -- L: hierarchy levels --------------------------------------------------------------------

def hierarchy(communities):
    """Nested partitions with the real final community sizes (illustrative levels)."""
    final = np.array([len(v) for v in communities.types], float)
    ids = communities.community_id.tolist()
    enriched = dict(zip(ids, communities.enriched))
    counts = TRANSCRIBED['hierarchy_counts']
    bounds = {counts[-1]: np.arange(len(final) + 1)}
    for n in reversed(counts[:-1]):
        children = bounds[min(bounds)]
        bounds[n] = children[np.linspace(0, len(children) - 1, n + 1).round().astype(int)]

    highlight = [str(c) for c in ids if enriched[c]]

    def build(level, lo, hi):
        if level == len(counts) - 1:
            return {str(ids[k]): float(final[k]) for k in range(lo, hi)}
        edges = bounds[counts[level + 1]]
        tree = {}
        for k in range(len(edges) - 1):
            if edges[k] >= lo and edges[k + 1] <= hi:
                name = f'{level + 1}.{k}'
                tree[name] = build(level + 1, edges[k], edges[k + 1])
                if any(enriched[ids[j]] for j in range(edges[k], edges[k + 1])):
                    highlight.append(name)
        return tree

    top = bounds[counts[0]]
    tree = {}
    for k in range(len(top) - 1):
        name = f'0.{k}'
        tree[name] = build(0, top[k], top[k + 1])
        if any(enriched[ids[j]] for j in range(top[k], top[k + 1])):
            highlight.append(name)
    return tree, highlight


LABELLED = [79, 81, 89, 102, 103, 116, 153, 185, 186, 249, 250, 270]


def panel_l(communities):
    tree, highlight = hierarchy(communities)
    p = i.plot_spec(height=66, width=30)
    p.icicle(tree, gap=2.2, highlight=set(highlight), labels=[str(c) for c in LABELLED],
             levels=True, counts=True, color=LIGHT_BLUE)
    p.title('hierarchy levels')
    return p


# -- M: adjacency matrix with a zoom ---------------------------------------------------------

CLASSES = [('CB-intrinsic', '#cfcc9e'), ('CB-sensory', '#e8dc8a'), ('ascending', '#8db878'),
           ('descending', '#b88cc0'), ('visual centrifugal', '#e0ae62'),
           ('visual projection', '#9ccbe0'), ('other', '#2e2e2e')]


def class_layers(p, matrix, classes, rows, cols):
    """Rows tinted by neuron class, shade by log weight.

    The API has no per-row hue for a matrix (see GAPS), and a raster matrix
    cannot leave missing cells transparent, so one matrix carries both: class
    k occupies the value band [2k, 2k + 1], which a stepped ramp of
    white-to-class-colour segments paints in that class's hue.
    """
    values = np.log1p(matrix)
    top = float(np.quantile(values[values > 0], .97))
    shade = np.minimum(values, top) / top * .999
    banded = 2 * classes[:, None] + shade
    cells = [[float(v) if w > 0 else None for v, w in zip(row, raw)]
             for row, raw in zip(banded, values)]
    stops = [c for _, color in CLASSES for c in ('#ffffff', color)]
    p.matrix(cells, x=cols, y=rows, ramp=i.ramp(stops), scale=i.linear((0, len(stops) - 1)),
             missing='#ffffff', raster=True)


def panel_m(d, communities):
    matrix, classes = d['matrix'], d['community_class']
    n = len(matrix)
    enriched = set(communities.loc[communities.enriched, 'community_id'])
    lo, hi = 70, 120
    zoom = i.plot_spec(width=32, height=32, x=(lo - .5, hi - .5), y=(hi - .5, lo - .5))
    class_layers(zoom, matrix[lo:hi, lo:hi], classes[lo:hi], range(lo, hi), range(lo, hi))
    for c in range(lo, hi):
        zoom.rect(c - .5, c - .5, c + .5, c + .5, fill='none',
                  stroke=RED if c in enriched else INK, stroke_width=HAIR, front=True)
    shown = [c for c in LABELLED if lo <= c < hi]
    zoom.label_points([(c, c) for c in shown], [str(c) for c in shown], fill=RED)

    p = i.plot_spec(height=32, x=(-.5, n - .5), y=(n - .5, -.5))
    class_layers(p, matrix, classes, range(n), range(n))
    p.axes(x='target (postsynaptic)', y='source (presynaptic)',
           x_options={'ticks': []}, y_options={'ticks': []})
    p.inset(zoom, side='right', zoom=(lo - .5, hi - .5, hi - .5, lo - .5), width=None, plate=False)
    square = lambda color: i.marker('square', 1.6, fill='none', stroke=color,
                                    stroke_width=STYLE.theme.stroke)
    p.title('adjacency matrix')
    # A bottom legend wider than the data is charged to the side margins (see
    # GAPS), so the key is a grid row of its own.
    key = i.legend([(name, color) for name, color in CLASSES] +
                   [('cluster', square(INK)), ('enriched cluster', square(RED))], columns=5)
    m = i.subfigure(columns=1, gap=1)
    m.add('matrix', p, row=0, column=0)
    m.add('key', key, row=1, column=0, align='w')
    return m


# -- N: composition of enriched clusters ---------------------------------------------------

def panel_n(clusters):
    rows = clusters[:12] + clusters[12:]
    names = [str(r['cluster']).replace('enriched-total', 'enriched total') for r in rows]
    counts = [[r['specific'] for r in rows], [r['dimorphic'] for r in rows], [r['isomorphic'] for r in rows]]
    totals = [r['total'] for r in rows]
    shares = [[c / t for c, t in zip(series, totals)] for series in counts]
    labels = [[str(c) if c else '' for c in series] for series in counts]
    p = i.plot_spec(height=36, x=(0, 1), y=names[::-1])
    p.bars(names, shares, stacked=True, orient='h', width=.78, color=[BLUE, AMBER, GREY],
           name=['specific', 'dimorphic', 'isomorphic'], labels=labels, stroke='none')
    p.axes(x='proportion of cell types', y='enriched cluster ID')
    p.legend(side='top')
    return p


# -- O: network between clusters -----------------------------------------------------------

def panel_o(d, communities):
    matrix, dim = d['matrix'], d['dim_matrix']
    ids = [102, 250, 107, 270, 185, 79, 216, 135, 249, 81, 116, 186, 103, 258, 257, 206, 189, 153,
           89, 280, 1, 302]
    enriched = set(communities.loc[communities.enriched, 'community_id'])
    sizes = dict(zip(communities.community_id, communities.type_n))
    candidates = sorted(((matrix[a, b], a, b) for a in ids for b in ids if a != b and matrix[a, b] > 0),
                        reverse=True)[:80]
    edges = [(str(a), str(b), float(w), 'dimorphic' if dim[a, b] / w > .4 else 'isomorphic')
             for w, a, b in candidates]
    p = i.plot_spec(height=36)
    p.network({str(c): float(sizes[c]) for c in ids}, edges, shape='square', arrows=True, diameter=3.5,
              groups={str(c): 'enriched' if c in enriched else 'not enriched' for c in ids},
              color={'enriched': RED, 'not enriched': '#c8c8c8'},
              edge_color={'isomorphic': '#555555', 'dimorphic': AMBER})
    p.width_key(title='edge weight\n(no. of synapses)', values=[50000, 1000], format='{:,.0f}', side='bottom')
    p.size_key(title='no. of types\nin cluster', values=[50, 10], side='right')
    p.legend(side='bottom', columns=2)
    return p


# -- P: cluster 102 anatomy ------------------------------------------------------------------

def panel_p(art: Artwork):
    a = art.a
    ids = a.ids('cluster-102')
    dimorphic = [b for b in ids if 'dimorphic' in str(a.neurons.loc[b, 'dimorphism'])]
    specific = [b for b in ids if b not in dimorphic]
    cns = art.mesh_points('male-brain', 'male-vnc')

    def factory(*, width, height):
        v = art.view(cns, width, height=66 if height is None else min(66, height - 10))
        for name in ('male-brain', 'male-vnc'):
            v.surface(name, a.display_mesh(name, 3000), color='#e8e8e8', opacity=.6)
        v.paths('male-specific', [r for b in specific for r in art.runs(b, 5)],
                color=BLUE, stroke_width=.09, opacity=.35, depth_cue=0)
        v.paths('dimorphic', [r for b in dimorphic for r in art.runs(b, 5)],
                color=AMBER, stroke_width=.09, opacity=.6, depth_cue=0)
        view = v.build()
        key = i.legend([('male-specific', BLUE), ('sexually dimorphic', AMBER)])
        # place_in_clear_space(within=view.bbox) finds no room once the view is
        # height-capped (the mesh bounding box is mostly empty space; see GAPS).
        title = i.hstack([i.text('cluster'), i.text('102', weight='bold')], gap=.6)
        return i.vstack([title, view, key], gap=1)
    return i.component(factory, responsive=True)


# -- Q: fru/dsx expression of clusters -------------------------------------------------------

def panel_q():
    fractions = TRANSCRIBED['q_fractions']              # non-enriched, enriched
    rows = ['enriched', 'non-enriched']
    series = [[fractions[1][k], fractions[0][k]] for k in range(4)]
    p = i.plot_spec(height=12, x=(0, 1), y=rows)
    p.bars(rows, series, stacked=True, orient='h', width=.8,
           color=[BLUE, '#c8465a', '#9b59a6', '#e6e6e6'],
           name=['fru+/dsx−', 'fru−/dsx+', 'fru+/dsx+', 'fru−/dsx−'], stroke='none')
    p.axis('top', ticks=[0, .2, .4, .6, .8, 1])
    p.axis('left', label='clusters')
    p.title('proportion of non-isomorphic cell types')
    p.legend(side='bottom')
    return p


# -- the page ----------------------------------------------------------------------------------

def lettered_width(diagram):
    """The width a diagram needs once the page letter is attached.

    Fixed artwork reserves this on its own; a responsive factory has no one
    natural width, so D asks for the width of its narrowest build, lettered.
    """
    return i.letters([diagram], start='A', style=STYLE.letter_style, pad=STYLE.letter_pad)[0].bbox.width


def make_document(data_dir: Path, chart_dir: Path):
    d, communities, clusters = load(data_dir, chart_dir)
    art = Artwork(data_dir)
    # Diagrams built eagerly (C, E) are measured against the active theme, which
    # preset.document() does not activate on its own (see GAPS).
    i.use_theme(STYLE.theme)
    doc = STYLE.document(columns=12, share_plot_margins=False).letters(start='A', anchor='cell')
    doc.add('a', panel_a(d), row=0, column=0, colspan=3)
    doc.add('b', panel_b(art), row=0, column=3, colspan=3, align='nw')
    doc.add('c', panel_c(), row=0, column=6, colspan=3, align='n')
    d_panel, d_minimum = panel_d(art)
    # +0.5 mm: a responsive cell is handed ~0.14 mm more than its letter leaves (see GAPS).
    doc.add('d', d_panel, row=0, column=9, colspan=3, align='nw', min_width=d_minimum + .5)
    doc.add('e', panel_e(), row=1, column=0, colspan=3, align='n')
    doc.add('f', panel_f(), row=1, column=3, colspan=2)
    doc.add('g', panel_g(d), row=1, column=5, colspan=3)
    doc.add('h', panel_h(d), row=1, column=8, colspan=4)
    for name, column, colspan, pies in [
            ('i', 0, 3, panel_pies('% of connections', (24.8, 1.5, 73.7), (24.8, .3, 74.9))),
            ('j', 3, 4, panel_pies('% of synapses in connections', (85.5, 4.9, 9.6), (88.6, .7, 10.8),
                                   legend=True))]:
        doc.add(name, pies, row=2, column=column, colspan=colspan)
    doc.add('k', panel_k(art, d), row=2, column=7, colspan=5, align='n')
    doc.add('l', panel_l(communities), row=3, column=0, colspan=2, rowspan=3)
    doc.add('m', panel_m(d, communities), row=3, column=2, colspan=6)
    doc.add('n', panel_n(clusters), row=4, column=2, colspan=3, rowspan=2)
    doc.add('o', panel_o(d, communities), row=4, column=5, colspan=3, rowspan=2)
    doc.add('p', panel_p(art), row=3, column=8, colspan=4, rowspan=2, align='n')
    doc.add('q', panel_q(), row=5, column=8, colspan=4)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=ROOT/'out/cell-pages')
    parser.add_argument('--data', type=Path, default=MAIN/'out/inspo-recreated/data')
    parser.add_argument('--charts', type=Path, default=MAIN/'out/inspo-native/chart-data')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    compiled = make_document(args.data, args.charts).compile()
    print(compiled.report())
    compiled.save(args.output/'dimorphism.svg', args.output/'dimorphism.pdf')
    (args.output/'dimorphism.png').write_bytes(compiled.to_png(dpi=300))


if __name__ == '__main__':
    main()
