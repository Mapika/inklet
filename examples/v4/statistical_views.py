"""Linked empirical distributions and supplied ranges for simulated cycle times."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, ECDFView, FacetView, IntervalView, RevisionOption
from inklet.experimental.selection import KeyedTable, SelectionState

CREDIT = ('Original simulated cycle times by Mark Marosi · MIT material. '
          'The ranges are illustrative supplied bounds, not confidence intervals. '
          'ECDFs describe nonmissing source estimates in each process; filtering hides markers only.')


def make_table(*, revised=False):
    values={'A':[12,14,14,15,18,None,17,20,22,24],
            'B':[10,12,13,13,14,16,15,17,19,21]}
    columns=dict(id=[],process=[],batch=[],estimate=[],lower=[],upper=[])
    for batch in range(1,11):
        for process in ('A','B'):
            if revised and (process,batch)==('B',10): continue
            value=11 if revised and (process,batch)==('A',1) else values[process][batch-1]
            lo=None if value is None or (process,batch)==('A',4) else value-2
            hi=None if value is None or (process,batch)==('A',4) else value+3
            for name,item in zip(columns,(f'{process.lower()}-{batch}',process,batch,value,lo,hi)):
                columns[name].append(item)
    return KeyedTable('cycle-times',columns)


def make_scene(*, revised=False):
    return BrowserFigure(make_table(revised=revised),[
        FacetView(ECDFView('distribution','estimate',(5,30),x_label='Cycle time / s'),
                  'process',('A','B'),('Process A','Process B')),
        FacetView(IntervalView('ranges','batch','estimate',(.4,10.6),(5,30),
                              x_label='Batch',y_label='Cycle time / s',lower='lower',upper='upper',
                              interval_label='Illustrative supplied range; not a confidence interval',color='#4774a0'),
                  'process',('A','B'),('Process A','Process B')),
    ],width=210,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-statistics'))
    parser.add_argument('--revised',action='store_true')
    parser.add_argument('--state',type=Path)
    args=parser.parse_args()
    figure=make_scene(revised=args.revised);alternate=make_scene(revised=not args.revised)
    state=(json.loads(args.state.read_text()) if args.state else
           figure.state(SelectionState.for_table(figure.table,selected=['a-2'])))
    labels=('Original · 20 batches','Revised · 19 batches')
    page=figure.to_html(title='Cycle-time distributions and supplied ranges',state=state,attribution=CREDIT,
                        search_columns=('process','batch'),revision_label=labels[args.revised],
                        revisions=[RevisionOption(labels[not args.revised],alternate,CREDIT,
                                                  search_columns=('process','batch'))])
    args.output.mkdir(parents=True,exist_ok=True)
    for name,value in (('index.html',page),('figure.svg',figure.to_svg(state)),
                       ('view.json',json.dumps(state,indent=2)+'\n')):
        (args.output/name).write_text(value,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__': main()
