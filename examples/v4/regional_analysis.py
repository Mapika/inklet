"""Link original simulated region geometry and CSV values without a map service."""
import argparse
import csv
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, GeoRegions, RegionView, BarView, ScatterView
from inklet.experimental.selection import KeyedTable, SelectionState

FIXTURES=Path(__file__).with_name('fixtures')


def make_scene(width=190):
    with (FIXTURES/'regions.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    columns={key:[row[key] for row in rows] for key in ('id','label','group')}
    columns.update({key:[float(row[key]) for row in rows] for key in ('revenue','cost')})
    columns['region']=[1,2,3,4]
    table=KeyedTable('regional-analysis',columns)
    regions=GeoRegions.read(FIXTURES/'regions.geojson')
    return BrowserFigure(table,[
        RegionView('revenueMap',regions,(-.1,-.1,2.1,2.1),value='revenue',breaks=(40,60),
                   colors=('#d4e8df','#78b5a1','#245f50'),value_label='Revenue / kEUR'),
        RegionView('costMap',regions,(-.1,-.1,2.1,2.1),value='cost',breaks=(25,35),
                   colors=('#dae6ef','#83aac9','#365e82'),value_label='Cost / kEUR'),
        BarView('revenue','region','revenue',(.4,4.6),(0,70),'Region index','Revenue / kEUR',color='#34786b'),
        ScatterView('costRevenue','cost','revenue',(20,40),(30,70),'Cost / kEUR','Revenue / kEUR',radius_mm=.9),
    ],width=width)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-regions'))
    parser.add_argument('--state',type=Path)
    parser.add_argument('--width',type=float,default=190)
    parser.add_argument('--group',choices=['North','South'])
    args=parser.parse_args();scene=make_scene(args.width)
    if args.state and args.group: parser.error('choose saved state or group, not both')
    if args.state: state=json.loads(args.state.read_text(encoding='utf-8'))
    else:
        visible=[key for key,group in zip(scene.table.row_ids,scene.table.columns['group']) if group==args.group] if args.group else None
        state=scene.state(SelectionState.for_table(scene.table,visible=visible))
    scene.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('figure.svg',scene.to_svg(state)),('view.json',json.dumps(state,indent=2)+'\n'),
                      ('index.html',scene.to_html(title='Regional analysis · simulated data',state=state))]:
        (args.output/name).write_text(text,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()
