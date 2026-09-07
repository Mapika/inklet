"""Linked world and Europe maps from pinned public-domain Natural Earth data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from inklet import read_csv
from inklet.experimental.browser import BrowserFigure, GeoRegions, RegionView
from inklet.experimental.selection import KeyedTable, SelectionState

DATA=Path(__file__).with_name('data')
CREDIT=('Made with Natural Earth · public-domain country boundaries at 1:110m. '
        'Population estimates are from the pinned source snapshot (mostly 2019; see each row’s year), '
        'not current estimates. Antarctica is excluded. Country/map units and boundaries follow the source.')


def load_table():
    with (DATA/'world-population.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    columns={key:[r[key] for r in rows] for key in ('id','country','continent')}
    for key in ('population','population_year','population_millions'):
        columns[key]=[float(r[key]) if r[key] else None for r in rows]
    return KeyedTable('natural-earth-population',columns)


def make_views(table, *, world_only=False):
    regions=GeoRegions.read(DATA/'world-countries.geojson')
    unknown=set(table.row_ids)-set(regions.feature_ids)
    if unknown: raise ValueError(f'country IDs have no source geometry: {sorted(unknown)}')
    # This recipe explicitly restricts geometry to the requested table cohort.
    # The general BrowserFigure API continues to require an exact join.
    ids=set(table.row_ids)
    regions=GeoRegions(tuple(feature for feature in regions.features if feature[0] in ids))
    options=dict(value='population_millions',breaks=(1,5,20,100),
                 colors=('#edf5df','#c6dfad','#83be98','#388e83','#155b68'),
                 value_label='Population / millions')
    views=[RegionView('world',regions,(-180,-60,180,85),**options)]
    if not world_only:views.append(RegionView('europe',regions,(-15,34,45,72),**options))
    return views


def make_scene(*, world_only=False):
    table=load_table()
    return BrowserFigure(table,make_views(table,world_only=world_only),width=190,columns=1)


def read_replacement(path):
    data=read_csv(path,types={'population':float,'population_year':float})
    required=('id','country','continent','population','population_year')
    if any(key not in data.columns for key in required):
        raise ValueError(f'CSV requires columns: {", ".join(required)}')
    columns={key:data.columns[key] for key in required}
    if any(v<0 for v in columns['population']): raise ValueError('population must be nonnegative')
    if any(v!=int(v) or not 1<=v<=9999 for v in columns['population_year']):
        raise ValueError('population years must be whole years from 1 to 9999')
    columns['population_millions']=tuple(v/1_000_000 for v in columns['population'])
    return KeyedTable('natural-earth-population',columns),data.source.sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-world'))
    saved=parser.add_mutually_exclusive_group()
    saved.add_argument('--state',type=Path,help='Restore a view saved from the target revision')
    saved.add_argument('--rebase-state',type=Path,help='Transfer a view from the original pinned map')
    replacement=parser.add_mutually_exclusive_group()
    replacement.add_argument('--year',type=int,help='Replace with rows dated this year in the pinned source')
    replacement.add_argument('--csv',type=Path,help='Replace population table with a supplied CSV')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--viewport',choices=('reset','preserve'),default='reset')
    args=parser.parse_args();original=make_scene();scene=original;revision=None;credit=CREDIT
    title='World population · Natural Earth'
    replacing=args.year is not None or args.csv is not None
    if args.rebase_state and not replacing: parser.error('--rebase-state requires --year or --csv')
    if not replacing and (args.missing!='error' or args.viewport!='reset'):
        parser.error('--missing and --viewport require --year or --csv')
    old_state=(json.loads(args.rebase_state.read_text(encoding='utf-8')) if args.rebase_state
               else original.state(SelectionState.for_table(original.table,selected=[] if args.state else ['HUN'])))
    state=old_state
    if replacing:
        if args.csv:
            title='World population · supplied CSV'
            table,digest=read_replacement(args.csv)
            source=dict(file=args.csv.name,sha256=digest,kind='user-supplied CSV')
            credit=('Made with Natural Earth · public-domain country boundaries at 1:110m. '
                    f'Population values and years come from the supplied CSV {args.csv.name} '
                    f'(SHA-256 {digest}). Population / millions is recalculated from population. '
                    'Country/map units and boundaries follow Natural Earth; Antarctica is excluded.')
        else:
            title=f'World population · {args.year} source cohort'
            ids=[key for key,year in zip(original.table.row_ids,original.table.columns['population_year']) if year==args.year]
            table=KeyedTable(original.table.name,original.table.subset(ids))
            source=dict(file='world-population.csv',sha256=hashlib.sha256((DATA/'world-population.csv').read_bytes()).hexdigest(),
                        kind='pinned source year subset',year=args.year)
            credit+=f' This revision includes only the {len(ids)} rows dated {args.year}; omitted countries are blank.'
        if not table.row_ids: parser.error('replacement contains no countries')
        revision=original.replace_data(table,state=old_state,views=make_views(table),
                                       missing=args.missing,viewport=args.viewport)
        scene=revision.figure;state=revision.state()
    if args.state: state=json.loads(args.state.read_text(encoding='utf-8'))
    scene.validate_state(state)
    overview=BrowserFigure(scene.table,make_views(scene.table,world_only=True),width=190,columns=1)
    args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('figure.svg',scene.to_svg(state)),('view.json',json.dumps(state,indent=2)+'\n'),
                      ('world.svg',overview.to_svg()),
                      ('index.html',scene.to_html(title=title,state=state,
                                                 attribution=credit,search_columns=('country','continent')))]:
        (args.output/name).write_text(text,encoding='utf-8')
    if revision:
        report=revision.report();report['source']=source
        (args.output/'revision.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        with (args.output/'population.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(scene.table.columns)
            writer.writerows(zip(*scene.table.columns.values()))
        print(f"Revision: {len(report['removed_ids'])} removed, {len(report['added_ids'])} added, "
              f"{len(report['changed_ids'])} changed; dropped selection {report['removed_selected']}; "
              f"dropped filter {report['removed_visible']}; viewport {report['viewport_policy']}.")
    print(args.output/'index.html')


if __name__=='__main__':main()
