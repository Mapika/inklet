"""Original simulated monthly operations: four linked views, offline and vector."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, ScatterView, LineView, BarView
from inklet.experimental.selection import KeyedTable


def make_scene():
    month=list(range(1,13))
    revenue=[42,45,44,51,55,None,59,57,63,65,62,71]
    margin=[4,6,-2,8,10,-4,12,7,14,0,9,16]
    hours=[180,190,195,200,210,215,220,218,230,238,235,245]
    table=KeyedTable('monthly-operations',dict(
        id=[f'month-{n:02d}' for n in month],month=month,
        revenue=revenue,margin=margin,hours=hours))
    return BrowserFigure(table,[
        LineView('revenue','month','revenue',(1,12),(35,75),
                 'Month','Revenue / kEUR',color='#34786b'),
        BarView('margin','month','margin',(.4,12.6),(-6,18),
                'Month','Margin / kEUR',bar_width=.7,color='#4774a0'),
        ScatterView('effort','hours','revenue',(170,255),(35,75),
                    'Work / h','Revenue / kEUR',radius_mm=.8,color='#8b6290'),
        BarView('horizontal','margin','month',(-6,18),(12.6,.4),
                'Margin / kEUR','Month',bar_width=.7,orientation='horizontal',color='#4774a0'),
    ],width=190,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-dashboard'))
    parser.add_argument('--state',type=Path)
    args=parser.parse_args();scene=make_scene()
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state else scene.state()
    # Validate before creating output files.
    scene.validate_state(state)
    args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('figure.svg',scene.to_svg(state)),
                      ('view.json',json.dumps(state,indent=2)+'\n'),
                      ('index.html',scene.to_html(title='Monthly operations · simulated data',state=state))]:
        (args.output/name).write_text(text,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()
