"""First 4.0 experiment: explicit identity, saved state and finite offline views.

Run from the checkout: python examples/v4/linked_selection.py --output out/v4-linked
Rebuild a downloaded state: add --state path/to/selection.json.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
import sys

import inklet as i
from inklet.experimental.selection import KeyedTable, SelectionState

HERE = Path(__file__).resolve().parent
FILTERS = ('All regions', 'North', 'South', 'No regions')


def load_table():
    with (HERE/'fixtures/regions.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    return KeyedTable('regional-analysis', {
        name: [float(row[name]) if name in ('revenue', 'cost') else row[name] for row in rows]
        for name in rows[0]
    })


def make_state(table, selected='', group='All regions'):
    if group not in FILTERS: raise ValueError('unknown region group')
    visible = None if group == 'All regions' else tuple(
        key for key, value in zip(table.row_ids, table.columns['group']) if value == group)
    return SelectionState.for_table(table, selected=() if not selected else (selected,), visible=visible)


def make_document(table, state, *, width=190):
    state.validate(table)
    data = state.visible(table)
    chosen = set(state.selected_ids)
    colors = ['#bd5636' if key in chosen else '#34786b' for key in data['id']]
    doc = i.document(width=width, columns=2, gap=10, margin=6).letters()
    # Keep scale/category positions stable while filtering the visible marks.
    p = i.plot_spec(x=table.columns['label'], y=(0, 75), height=56)
    if data['id']:
        p.bars(data['label'], data['revenue'], bar_colors=colors)
    p.axes(y='Revenue / kEUR')
    doc.add('revenue', p, row=0, column=0)
    p = i.plot_spec(x=(15, 45), y=(0, 75), height=56)
    for key, cost, revenue, color in zip(data['id'], data['cost'], data['revenue'], colors):
        p.scatter([(cost, revenue)], color=color, size=2.5 if key in chosen else 1.8)
    p.axes(x='Cost / kEUR', y='Revenue / kEUR')
    doc.add('cost-revenue', p, row=0, column=1)
    return doc


def build_html(table, destination):
    """Package 20 precompiled states, not an arbitrary browser plot compiler."""
    states = []
    for group in FILTERS:
        for key in ('', *table.row_ids):
            state = make_state(table, key, group)
            figure = make_document(table, state).compile()
            states.append(dict(group=group, selected=key, state=json.loads(state.to_json()),
                               svg=figure.to_svg(), rows=state.visible(table)))
    # JSON in a script element must not permit an authored label to close it.
    payload = json.dumps(states, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
    template = (HERE/'linked_selection.html').read_text()
    options = '<option value="">No selection</option>' + ''.join(
        f'<option value="{html.escape(key, quote=True)}">{html.escape(label)}</option>'
        for key, label in zip(table.row_ids, table.columns['label']))
    page = template.replace('<!--OPTIONS-->', options).replace('/*STATES*/', payload)
    destination.write_text(page)
    return len(states)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/v4-linked'))
    parser.add_argument('--state', type=Path)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    table = load_table()
    state = SelectionState.from_json(args.state.read_text()) if args.state else make_state(table, 'north-east')
    figure = make_document(table, state).compile()
    if figure.diagnostics: raise RuntimeError(figure.report())
    figure.save(args.output/'figure.svg', args.output/'figure.pdf', args.output/'figure.png')
    (args.output/'selection.json').write_text(state.to_json())
    (args.output/'caption.txt').write_text(
        'Simulated regional revenue and costs, in kEUR. Orange marks indicate selected IDs. '
        'Filtering preserves category positions and hidden selections. Original MIT fixtures.\n')
    count = build_html(table, args.output/'index.html')
    (args.output/'report.json').write_text(json.dumps(dict(
        schema='inklet.v4-linked-preview/0.1', version=i.__version__,
        data_digest=table.digest, state=json.loads(state.to_json()),
        browser_mode='precompiled-states', browser_states=count,
        stages=dict(figure.stats), diagnostics=len(figure.diagnostics)), indent=2)+'\n')
    print(f'{args.output}/index.html: {count} offline states; SVG/PDF/PNG and selection.json saved')


if __name__ == '__main__':
    main()
