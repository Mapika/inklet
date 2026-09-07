"""Linked world and Europe maps from pinned public-domain Natural Earth data."""
import argparse
import csv
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, GeoRegions, RegionView
from inklet.experimental.selection import KeyedTable, SelectionState

DATA=Path(__file__).with_name('data')
CREDIT=('Made with Natural Earth · public-domain country boundaries at 1:110m. '
        'Population estimates are from the pinned source snapshot (mostly 2019; see each row’s year), '
        'not current estimates. Antarctica is excluded. Country/map units and boundaries follow the source.')


def make_scene(*, world_only=False):
    with (DATA/'world-population.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    columns={key:[r[key] for r in rows] for key in ('id','country','continent')}
    for key in ('population','population_year','population_millions'):
        columns[key]=[float(r[key]) if r[key] else None for r in rows]
    table=KeyedTable('natural-earth-population',columns)
    regions=GeoRegions.read(DATA/'world-countries.geojson')
    options=dict(value='population_millions',breaks=(1,5,20,100),
                 colors=('#edf5df','#c6dfad','#83be98','#388e83','#155b68'),
                 value_label='Population / millions')
    views=[RegionView('world',regions,(-180,-60,180,85),**options)]
    if not world_only:views.append(RegionView('europe',regions,(-15,34,45,72),**options))
    return BrowserFigure(table,views,width=190,columns=1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-world'))
    parser.add_argument('--state',type=Path)
    args=parser.parse_args();scene=make_scene()
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state else scene.state(SelectionState.for_table(scene.table,selected=['HUN']))
    scene.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('figure.svg',scene.to_svg(state)),('view.json',json.dumps(state,indent=2)+'\n'),
                      ('world.svg',make_scene(world_only=True).to_svg()),
                      ('index.html',scene.to_html(title='World population · Natural Earth',state=state,
                                                 attribution=CREDIT,search_columns=('country','continent')))]:
        (args.output/name).write_text(text,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()
