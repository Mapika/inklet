"""Six linked panels of original simulated monthly regional operations."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import (
    BarView, BrowserFigure, FacetView, LineView, RevisionOption,
)
from inklet.experimental.selection import KeyedTable, SelectionState


REGIONS = ('North', 'South', 'West')
CREDIT = (
    'Original simulated monthly operations by Mark Marosi · MIT material. '
    'Regions are invented business categories; values are not company accounts. '
    'The North and South revision removes West rows without changing retained values.'
)


def make_scene(*, without_west=False):
    # Interleave regions deliberately: line adjacency is local to each facet.
    revenue = {
        'North': [42, 45, 44, 51, 55, None, 59, 57, 63, 65, 62, 71],
        'South': [35, 37, 39, 38, 44, 46, 43, 49, 52, 50, 55, 60],
        'West': [48, 46, 51, 54, 52, 58, 61, 60, 57, 64, 68, 72],
    }
    profit = {
        'North': [4, 6, -2, 8, 10, -4, 12, 7, 14, 0, 9, 16],
        'South': [-3, 2, 4, -1, 6, 5, -2, 8, 10, 7, 11, 14],
        'West': [7, -2, 9, 11, 5, 12, 13, 10, -3, 14, 16, 18],
    }
    columns = {name: [] for name in ('id', 'region', 'month', 'revenue', 'profit')}
    for month in range(1, 13):
        for region in REGIONS:
            if without_west and region == 'West':
                continue
            row = (f'{region.lower()}-{month:02d}', region, month,
                   revenue[region][month - 1], profit[region][month - 1])
            for name, value in zip(columns, row):
                columns[name].append(value)
    table = KeyedTable('regional-monthly-operations', columns)
    return BrowserFigure(table, [
        FacetView(LineView(
            'revenue', 'month', 'revenue', (.4, 12.6), (30, 80),
            x_label='Month', y_label='Revenue / kEUR', color='#34786b',
        ), column='region', values=REGIONS),
        FacetView(BarView(
            'profit', 'month', 'profit', (.4, 12.6), (-6, 20),
            x_label='Month', y_label='Profit / kEUR', bar_width=.7, color='#4774a0',
        ), column='region', values=REGIONS),
    ], width=240, columns=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/v4-facets'))
    parser.add_argument('--state', type=Path)
    parser.add_argument('--without-west', action='store_true',
                        help='Start with the North and South revision, keeping empty West panels.')
    args = parser.parse_args()
    figure = make_scene(without_west=args.without_west)
    alternate = make_scene(without_west=not args.without_west)
    state = (json.loads(args.state.read_text(encoding='utf-8')) if args.state else
             figure.state(SelectionState.for_table(figure.table, selected=['north-03'])))
    figure.validate_state(state)
    labels = ('All regions · 36 monthly rows', 'North and South only · 24 monthly rows')
    html = figure.to_html(
        title='Regional operations · simulated data', state=state,
        attribution=CREDIT, search_columns=('region', 'month'),
        revision_label=labels[args.without_west],
        revisions=[RevisionOption(
            label=labels[not args.without_west], figure=alternate,
            attribution=CREDIT, search_columns=('region', 'month'),
        )],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ('index.html', html), ('figure.svg', figure.to_svg(state)),
        ('view.json', json.dumps(state, indent=2) + '\n'),
    ):
        (args.output / name).write_text(content, encoding='utf-8')
    print(args.output / 'index.html')


if __name__ == '__main__':
    main()
