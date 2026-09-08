"""Calendar dates and offset-aware collection times for simulated daily batches."""
import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path

from inklet.experimental.browser import BarView, BrowserFigure, LineView, RevisionOption, TimeAxis
from inklet.experimental.selection import KeyedTable, SelectionState

CREDIT = ('Original simulated daily batches by Mark Marosi · MIT material. '
          'All counts and durations are invented. Collection times use explicit '
          '+01:00 and +02:00 offsets. The revision restores March 31 and April 2 duration.')


def make_table(*, revised=False, backend='native'):
    columns = dict(id=[], day=[], collected=[], batches=[], duration=[])
    for n in range(10):
        day = date(2026, 3, 27) + timedelta(days=n)
        if n == 4 and not revised:
            continue
        offset = '+01:00' if n < 2 else '+02:00'
        values = (day.isoformat(), day, datetime.fromisoformat(day.isoformat()+'T12:00:00'+offset),
                  [18,24,21,27,26,30,23,31,28,35][n],
                  None if n == 6 and not revised else [4.,5.,3.,4.5,4.,3.5,4.5,4.,3.,2.5][n])
        for name,value in zip(columns,values):
            columns[name].append(value)
    if backend == 'pandas':
        import pandas as pd
        return KeyedTable.from_pandas('daily-batches', pd.DataFrame(columns),
                                      time_columns={'day':'date','collected':'utc'})
    if backend == 'polars':
        import polars as pl
        return KeyedTable.from_polars('daily-batches', pl.DataFrame(columns),
                                      time_columns={'day':'date','collected':'utc'})
    if backend != 'native':
        raise ValueError('backend must be native, pandas or polars')
    from inklet.experimental.temporal import time_value
    for column,mode in (('day','date'),('collected','utc')):
        columns[column] = [time_value(value,mode) for value in columns[column]]
    return KeyedTable('daily-batches',columns)


def make_scene(*, revised=False, backend='native'):
    return BrowserFigure(make_table(revised=revised,backend=backend),[
        BarView('daily','day','batches',TimeAxis(('2026-03-26','2026-04-06')),(0,40),
                x_label='Reporting date', y_label='Completed batches', bar_width=18*3600),
        LineView('duration','collected','duration',
                 TimeAxis(('2026-03-26T12:00:00Z','2026-04-06T12:00:00Z'),mode='utc'),(0,6),
                 x_label='Collection time', y_label='Processing / hours',max_gap_seconds=36*3600,
                 color='#4774a0'),
    ],width=210,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-time'))
    parser.add_argument('--backend',choices=('native','pandas','polars'),default='native')
    parser.add_argument('--revised',action='store_true')
    parser.add_argument('--state',type=Path)
    args=parser.parse_args()
    figure=make_scene(revised=args.revised,backend=args.backend)
    alternate=make_scene(revised=not args.revised,backend=args.backend)
    state=(json.loads(args.state.read_text()) if args.state else
           figure.state(SelectionState.for_table(figure.table,selected=['2026-03-29'])))
    labels=('Original · 9 daily rows','Restored · 10 daily rows')
    page=figure.to_html(title='Daily batches · simulated time series',state=state,attribution=CREDIT,
                        search_columns=('day','collected'),revision_label=labels[args.revised],
                        revisions=[RevisionOption(labels[not args.revised],alternate,CREDIT,
                                                  search_columns=('day','collected'))])
    args.output.mkdir(parents=True,exist_ok=True)
    for name,value in (('index.html',page),('figure.svg',figure.to_svg(state)),
                       ('view.json',json.dumps(state,indent=2)+'\n')):
        (args.output/name).write_text(value,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':
    main()
