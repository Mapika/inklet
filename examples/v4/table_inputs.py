"""Equivalent pandas/Polars snapshots and revisions of simulated workshop data."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, BarView, FacetView, LineView, RevisionOption
from inklet.experimental.selection import KeyedTable, SelectionState


CREDIT = ('Original simulated workshop observations by Mark Marosi · MIT material. '
          'No measured production data. Bench B has missing turnaround in week 4. '
          'The revision corrects bench A week 3 and removes bench B week 8.')


def make_table(backend, *, revised=False):
    columns = dict(id=[], bench=[], week=[], units=[], turnaround=[])
    for week in range(1, 9):
        for bench in ('A', 'B'):
            row = (f'{bench.lower()}-{week}', bench, week,
                   (18, 23, 20, 28, 25, 31, 29, 35)[week - 1] + (4 if bench == 'B' else 0),
                   None if (bench, week) == ('B', 4) else
                   (7., 6.5, 8., 5.5, 6., 4.5, 5., 4.)[week - 1] + (1 if bench == 'B' else 0))
            for name, value in zip(columns, row):
                columns[name].append(value)
    if backend == 'pandas':
        import pandas as pd
        frame = pd.DataFrame(columns).astype({'week': 'Int64', 'units': 'Int64',
                                              'turnaround': 'Float64', 'bench': 'category'})
        if revised:
            frame = frame.loc[frame.id != 'b-8'].copy()
            frame.loc[frame.id == 'a-3', 'units'] = 24
        return KeyedTable.from_pandas('workshop', frame)
    if backend == 'polars':
        import polars as pl
        frame = pl.DataFrame(columns).with_columns(pl.col('bench').cast(pl.Categorical))
        if revised:
            frame = frame.filter(pl.col('id') != 'b-8').with_columns(
                pl.when(pl.col('id') == 'a-3').then(24).otherwise(pl.col('units')).alias('units'))
        return KeyedTable.from_polars('workshop', frame)
    raise ValueError('backend must be pandas or polars')


def make_scene(backend, *, revised=False):
    original = BrowserFigure(make_table(backend), [
        FacetView(BarView('units', 'week', 'units', (.4, 8.6), (0, 45),
                          x_label='Week', y_label='Completed units', bar_width=.65,
                          color='#34786b'), 'bench', ('A', 'B'), ('Bench A', 'Bench B')),
        FacetView(LineView('turnaround', 'week', 'turnaround', (.4, 8.6), (0, 10),
                           x_label='Week', y_label='Turnaround / days', color='#4774a0'),
                  'bench', ('A', 'B'), ('Bench A', 'Bench B')),
    ], width=180, columns=2)
    return original.replace_data(make_table(backend, revised=True)).figure if revised else original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('pandas', 'polars'), default='pandas')
    parser.add_argument('--output', type=Path, default=Path('out/v4-tables'))
    parser.add_argument('--state', type=Path)
    parser.add_argument('--revised', action='store_true')
    args = parser.parse_args()
    figure = make_scene(args.backend, revised=args.revised)
    alternate = make_scene(args.backend, revised=not args.revised)
    state = (json.loads(args.state.read_text(encoding='utf-8')) if args.state else
             figure.state(SelectionState.for_table(figure.table, selected=['a-3'])))
    labels = ('Original · 16 observations', 'Corrected · 15 observations')
    html = figure.to_html(title='Workshop observations · simulated data', state=state,
                          attribution=CREDIT, search_columns=('bench', 'week'),
                          revision_label=labels[args.revised],
                          revisions=[RevisionOption(labels[not args.revised], alternate, CREDIT,
                                                    search_columns=('bench', 'week'))])
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ('index.html', html), ('figure.svg', figure.to_svg(state)),
        ('view.json', json.dumps(state, indent=2) + '\n'),
    ):
        (args.output / name).write_text(content, encoding='utf-8')
    print(args.output / 'index.html')


if __name__ == '__main__':
    main()
