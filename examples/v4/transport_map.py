"""Original mixed GeoJSON map linked to supplied asset activity and history."""
import argparse
import json
from pathlib import Path

from inklet.experimental.browser import BrowserFigure, GeoFeatures, MapView, BarView, SeriesView, RevisionOption
from inklet.experimental.selection import KeyedTable, SelectionState

FIXTURE = Path(__file__).with_name('fixtures')/'transport.geojson'
CREDIT = ('Original illustrative transport fixture · MIT. Coordinates describe an invented district, '
          'routes and stops, not real locations. Activity values are supplied simulated visits/day '
          'for overlapping asset populations; do not sum them. Map lengths and areas are not physical measurements.')


def make_scene(revision='original', width=210):
    if revision not in ('original','rerouted','removed'): raise ValueError('unknown revision')
    raw = json.loads(FIXTURE.read_text())
    if revision == 'rerouted': raw['features'][2]['geometry']['coordinates'][1] = [4,.5]
    if revision == 'removed': raw['features'] = [f for f in raw['features'] if f['id'] != 'branches']
    geo = GeoFeatures.from_geojson(raw, source_name='Original transport fixture', attribution=CREDIT)
    activity = {'district':(None,None,None), 'islands':(120,140,160), 'main-route':(420,460,490),
                'branches':(260,240,280), 'terminal':(320,350,380), 'stops':(180,210,230)}
    table = KeyedTable('transport-map', dict(id=geo.feature_ids,
        asset=[key.replace('-',' ').title() for key in geo.feature_ids],
        kind=[kind for _,kind,_ in geo.features], position=list(range(len(geo.feature_ids))),
        week1=[activity[key][0] for key in geo.feature_ids],
        week2=[activity[key][1] for key in geo.feature_ids],
        week3=[activity[key][2] for key in geo.feature_ids]))
    style = dict(value='week3', breaks=(200,400), colors=('#91b7a2','#5783a2','#bd7748'),
                 missing_color='#e5ebe7', value_label='Week 3 / visits per day', radius_mm=1.2, line_width_mm=.8)
    views = [MapView('overview',geo,(-1,-1,11,6),**style), MapView('detail',geo,(.4,.1,7.6,4.8),**style),
             BarView('activity','week3','position',(0,550),(-.5,5.5),
                     x_label='Week 3 / visits per day',y_label='Source row index',orientation='horizontal'),
             SeriesView('history',[(1,'week1'),(2,'week2'),(3,'week3')],(.8,3.2),(0,550),
                        x_label='Week',y_label='Supplied visits per day')]
    return BrowserFigure(table, views, width=width)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-transport-map'))
    parser.add_argument('--revision',choices=('original','rerouted','removed'),default='original')
    parser.add_argument('--state',type=Path,help='Saved state belonging to the chosen revision')
    parser.add_argument('--rebase',type=Path,help='Saved original state to transfer to the chosen revision')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--renderer',choices=('classic','compiled'),default='compiled')
    parser.add_argument('--backend',choices=('svg','canvas','hybrid','auto','webgl2'),default='svg')
    parser.add_argument('--render',action='store_true',help='Also export PNG and PDF previews')
    args = parser.parse_args()
    if args.state and args.rebase: parser.error('choose --state or --rebase')
    f = make_scene(args.revision); report = {}
    if args.rebase:
        original = make_scene()
        transition = original.replace_data(f.table, views=f._views, state=json.loads(args.rebase.read_text()), missing=args.missing)
        state, report = transition.state(), transition.report()
    else:
        state = json.loads(args.state.read_text()) if args.state else f.state(SelectionState.for_table(f.table, selected=['main-route']))
    f.validate_state(state)
    args.output.mkdir(parents=True,exist_ok=True)
    options = [RevisionOption(name.title(),make_scene(name),CREDIT,('asset','kind')) for name in ('original','rerouted','removed') if name != args.revision]
    (args.output/'index.html').write_text(f.to_html(title='Transport map · illustrative asset activity',
        renderer=args.renderer, backend=args.backend, state=state, attribution=CREDIT,
        search_columns=('asset','kind'),revision_label=args.revision.title(),revisions=options),encoding='utf-8')
    for name,value in [('view.json',state),('revision.json',report),('sources.json',f.payload()['layers'][0]['geography'])]:
        (args.output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    for width in (210,170):
        resized = f.replace_data(f.table,state=state,width=width)
        path = args.output/f'figure-{width}mm.svg';path.write_text(resized.figure.to_svg(resized.state()),encoding='utf-8')
        (args.output/f'view-{width}mm.json').write_text(json.dumps(resized.state(),indent=2)+'\n')
        if args.render:
            from inklet.render.preview import svg_png, svg_pdf
            svg_png(path,path.with_suffix('.png'),dpi=150);svg_pdf(path,path.with_suffix('.pdf'))
    print(args.output/'index.html')


if __name__ == '__main__': main()
