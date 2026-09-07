"""Original polygon geometry review: a hole, concavity, islands and overlaps."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, GeoRegions, RegionView

from inklet.experimental.selection import KeyedTable


def make_scene():
    regions=GeoRegions.read(Path(__file__).with_name('fixtures')/'region-shapes.geojson')
    table=KeyedTable('region-shapes',dict(id=regions.feature_ids,value=[None,20,40,60]))
    return BrowserFigure(table,[RegionView('regions',regions,(-.2,-.2,8.2,6.2),
        value='value',breaks=(20,40,60),colors=('#eeeeee','#a8c9be','#498e78','#24594c'),value_label='Illustrative value')],width=130)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-region-shapes'))
    args=parser.parse_args();scene=make_scene();args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('figure.svg',scene.to_svg()),('view.json',json.dumps(scene.state(),indent=2)+'\n'),
                      ('index.html',scene.to_html(title='Region geometry · simulated data'))]:
        (args.output/name).write_text(text,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()
