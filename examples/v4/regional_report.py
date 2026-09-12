"""Complete offline regional workflow: real boundaries, simulated monthly values."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from inklet.experimental.browser import (BrowserFigure, ECDFView, FacetView, GeoRegions,
    RegionView, RevisionOption, ScatterView, SeriesView, TimeAxis)
from inklet.experimental.selection import KeyedTable, SelectionState

DATA = Path(__file__).with_name('data')
GROUPS = {
    'West': ('BEL','FRA','GBR','IRL','LUX','NLD'),
    'Central': ('AUT','CZE','DEU','HUN','POL','SVK'),
    'North': ('DNK','EST','FIN','LVA','LTU','SWE'),
}
SAMPLES = tuple((f'2025-{m:02d}-01', f'month_{m:02d}') for m in range(1,13))
CREDIT = ('SIMULATED measurements: monthly service completion rates, January–December 2025. '
          'These invented values do not describe actual countries or organizations. '
          'Original simulation by Mark Marosi, MIT. Made with Natural Earth: public-domain '
          '1:110m country boundaries from the pinned repository snapshot. Group assignments '
          'are authored for this example. The ECDF uses the fixed source-country population; '
          'filtering hides country markers without recomputing it.')


def make_table(*, revised=False):
    with (DATA/'world-population.csv').open(newline='', encoding='utf-8') as stream:
        names = {r['id']:r['country'] for r in csv.DictReader(stream)}
    columns = {k:[] for k in ('id','country','group',*(c for _,c in SAMPLES),'initial','latest','change')}
    for group, countries in GROUPS.items():
        for n, key in enumerate(countries):
            if revised and key == 'EST': continue
            g = tuple(GROUPS).index(group)
            values = [round(65+g*3+n*2 + (m-1)*(.65+n*.08) +
                            2*math.sin((m+n)*math.pi/6), 1) for m in range(1,13)]
            if key == 'HUN': values[5] = None  # Missing June; never bridge this gap.
            if revised and key == 'HUN': values[-1] = round(values[-1]+2.5, 1)
            row = (key,names[key],group,*values,values[0],values[-1],round(values[-1]-values[0],1))
            for column, value in zip(columns,row): columns[column].append(value)
    return KeyedTable('regional-service-report',columns)


def read_table(path):
    """Accept the same explicit wide-table contract; derive comparisons afresh."""
    with path.open(newline='',encoding='utf-8') as stream:
        reader=csv.DictReader(stream)
        expected=['id','country','group',*(c for _,c in SAMPLES)]
        if reader.fieldnames != expected:
            raise ValueError('CSV headers must be exactly: '+','.join(expected))
        columns={c:[] for c in expected}
        for n,row in enumerate(reader,2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'CSV row {n}: incorrect field count')
            for c in expected:
                value=row[c]
                if c.startswith('month_'):
                    value=None if value=='' else float(value)
                    if value is not None and (not math.isfinite(value) or not 0<=value<=100):
                        raise ValueError(f'CSV row {n}, {c}: expected a percentage from 0 to 100')
                elif not value.strip(): raise ValueError(f'CSV row {n}, {c}: expected a nonempty string')
                columns[c].append(value)
            if row['group'] not in GROUPS: raise ValueError(f'CSV row {n}: unknown group')
    if not columns['id']: raise ValueError('regional report needs at least one country')
    columns['initial']=list(columns['month_01']);columns['latest']=list(columns['month_12'])
    columns['change']=[None if a is None or b is None else round(b-a,1)
                       for a,b in zip(columns['initial'],columns['latest'])]
    return KeyedTable('regional-service-report',columns)


def write_table(table, path):
    fields=['id','country','group',*(c for _,c in SAMPLES)]
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(fields)
        writer.writerows(zip(*(table.columns[c] for c in fields)))


def make_views(table):
    regions=GeoRegions.read(DATA/'world-countries.geojson')
    allowed={key for countries in GROUPS.values() for key in countries}
    unknown=set(table.row_ids)-allowed
    if unknown: raise ValueError(f'countries outside this report extent/cohort: {sorted(unknown)}')
    regions=GeoRegions(tuple(f for f in regions.features if f[0] in table.row_ids))
    return [
        RegionView('map',regions,(-12,43,33,71),value='latest',breaks=(75,80,85,90),
                   colors=('#e1eee7','#b8d5c7','#7fb4a2','#428c7c','#205f57'),
                   value_label='December completion / %'),
        SeriesView('history',SAMPLES,TimeAxis(('2024-12-20','2025-12-12'),mode='date'),(60,100),
                   x_label='Month',y_label='Completion / %'),
        ECDFView('distribution','latest',(60,100),x_label='December completion / %'),
        FacetView(ScatterView('comparison','initial','latest',(60,85),(65,100),
                             x_label='January completion / %',y_label='December completion / %',
                             radius_mm=.9,color='#4774a0'),
                  'group',tuple(GROUPS)),
    ]


def make_scene(*, revised=False, width=210, table=None):
    table=make_table(revised=revised) if table is None else table
    return BrowserFigure(table,make_views(table),width=width,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-regional-report'))
    parser.add_argument('--state',type=Path,help='Saved state matching the chosen data at 210 mm')
    parser.add_argument('--group',choices=tuple(GROUPS))
    parser.add_argument('--revised',action='store_true')
    parser.add_argument('--csv',type=Path,help='Replacement wide CSV; exported data.csv is the template')
    parser.add_argument('--rebase-state',type=Path,help='Original 210 mm state to apply to replacement data')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--render',action='store_true',help='Also export PDF and 150 dpi PNG (render extra)')
    parser.add_argument('--renderer',choices=('classic','compiled'),default='classic',
                        help='Use the shared compiled viewer for linked marks')
    parser.add_argument('--backend',choices=('svg','canvas','hybrid','auto','webgl2'),default=None)
    args=parser.parse_args()
    if args.renderer=='compiled' and args.backend=='hybrid': parser.error('compiled rendering does not use hybrid')
    if args.renderer=='classic' and args.backend in ('auto','webgl2'): parser.error('auto/webgl2 require --renderer compiled')
    if args.csv and args.revised: parser.error('choose --csv or --revised')
    if args.state and args.rebase_state: parser.error('choose --state or --rebase-state')
    if args.group and (args.state or args.rebase_state): parser.error('choose a group or saved state')
    original=make_scene()
    table=read_table(args.csv) if args.csv else make_table(revised=args.revised)
    figure=make_scene(table=table)
    if args.rebase_state:
        revision=original.replace_data(table,views=make_views(table),
            state=json.loads(args.rebase_state.read_text()),missing=args.missing)
        state=revision.state();report=revision.report()
    else:
        selected=['HUN'] if 'HUN' in table.row_ids else []
        visible=[key for key,group in zip(table.row_ids,table.columns['group']) if group==args.group] if args.group else None
        state=json.loads(args.state.read_text()) if args.state else figure.state(
            SelectionState.for_table(table,selected=selected,visible=visible))
        report=original.replace_data(table,views=make_views(table),missing=args.missing).report()
    figure.validate_state(state)
    args.output.mkdir(parents=True,exist_ok=True)
    label='Replacement CSV' if args.csv else ('Revised · 17 countries' if args.revised else 'Original · 18 countries')
    credit=(f'User-supplied measurements from {args.csv.name}; SHA-256 {hashlib.sha256(args.csv.read_bytes()).hexdigest()}. '
            'Made with Natural Earth: public-domain 1:110m country boundaries from the pinned repository snapshot. '
            'The ECDF uses the fixed source-country population; filtering hides markers only.' if args.csv else CREDIT)
    title='Regional service report · supplied measurements' if args.csv else 'Regional service report · simulated measurements'
    options=[] if args.csv else [RevisionOption('Original · 18 countries' if args.revised else 'Revised · 17 countries',
        make_scene(revised=not args.revised),CREDIT,search_columns=('country','group'))]
    (args.output/'index.html').write_text(figure.to_html(title=title,
        renderer=args.renderer,backend=args.backend or ('auto' if args.renderer=='compiled' else 'svg'),
        state=state,attribution=credit,search_columns=('country','group'),revision_label=label,revisions=options),encoding='utf-8')
    (args.output/'view.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    (args.output/'revision.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    write_table(table,args.output/'data.csv')
    (args.output/'provenance.json').write_text(json.dumps(dict(credit=credit, data_digest=table.digest,
        scene_digest=figure.payload()['scene_digest'], geometry_source=json.loads((DATA/'world-map-source.json').read_text()),
        exports=dict(widths_mm=[210,160],viewport='reset for physical-width exports; exact saved viewport in figure.svg')),indent=2)+'\n',encoding='utf-8')
    for width in (210,160):
        resized=figure.replace_data(table,state=state,width=width,columns=2,viewport='reset')
        svg=args.output/f'figure-{width}mm.svg';svg.write_text(resized.figure.to_svg(resized.state()),encoding='utf-8')
        (args.output/f'view-{width}mm.json').write_text(json.dumps(resized.state(),indent=2)+'\n',encoding='utf-8')
        if args.render:
            from inklet.render.preview import svg_png
            from inklet.render.preview import svg_pdf
            svg_png(svg,svg.with_suffix('.png'),dpi=150)
            svg_pdf(svg,svg.with_suffix('.pdf'))
    # Exact browser viewport reconstruction, independent of full-page resized exports.
    (args.output/'figure.svg').write_text(figure.to_svg(state),encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__': main()
