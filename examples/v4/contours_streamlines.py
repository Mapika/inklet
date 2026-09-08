"""Contours and streamlines from simulated nodal grid fields."""
import argparse
import json
import math
from pathlib import Path

import inklet as i
from inklet.experimental.grid import GridField
from inklet.experimental.browser import (BrowserFigure, DrawingItem, DrawingView,
    GridFieldView, RevisionOption, ScatterView)
from inklet.experimental.selection import SelectionState

REVISIONS=('original','reversed','masked','updated')
CREDIT=('Simulated nodal scalar and XY vector fields by Mark Marosi · MIT. '
        'Scalar samples are squared radius about the origin; vectors rotate about (0.5, 0). '
        'Interpolation is linear on fixed lower-left/upper-right cell triangles. '
        'Streamlines use normalized-vector RK4, not time integration. Missing corners mask whole cells. '
        'Table/scatter values are arithmetic corner means and magnitude of the mean vector. '
        'Selection and filtering act on cell pieces without recomputing contours or trajectories.')
LEVELS=(.5,1,2,3,4)
COLORS=('#dbe8ed','#749eb2','#518a9f','#327287','#24576e','#163d59')


def make_field(revision='original'):
    if revision not in REVISIONS:raise ValueError('unknown field revision')
    axis=[n/4 for n in range(-8,9)];scalars=[];vectors=[]
    for y in axis:
        sr=[];vr=[]
        for x in axis:
            missing=revision=='masked' and -.8<x<-.2 and .4<y<1.0
            sr.append(None if missing else (x*x+y*y)*(1.25 if revision=='updated' else 1))
            sign=-1 if revision=='reversed' else 1
            vr.append(None if missing else (-sign*y,sign*(x-.5)))
        scalars.append(sr);vectors.append(vr)
    return GridField(axis,axis,[f'cell-{n:03d}' for n in range(256)],scalars,vectors)


def make_views(field):
    traces=field.streamlines([(f'seed-{n}',(.5+radius,0)) for n,radius in enumerate((.3,.6,.9,1.2,1.45))],
                             step=.04,max_length=12,max_steps=800)
    common=dict(field=field,levels=LEVELS,colors=COLORS,scale_bar=1)
    return [GridFieldView('contours',**common),
            GridFieldView('streamlines',**common,contours=False,streamlines=traces),
            GridFieldView('means',**common,contours=False,cells=True),
            ScatterView('values','scalar','magnitude',(-.2,9),(-.1,3.5),
                x_label=f'Corner mean scalar / {field.scalar_unit}',
                y_label=f'Magnitude of mean vector / {field.vector_unit}',radius_mm=.45)]


def make_scene(revision='original',*,width=210,field=None):
    field=make_field(revision) if field is None else field
    return BrowserFigure(field.table(),make_views(field),width=width,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-contours-streamlines'))
    parser.add_argument('--revision',choices=REVISIONS,default='original')
    parser.add_argument('--json',type=Path,help='Replacement GridField source; input.json is the template')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--rebase-state',type=Path,help='Reconcile an original 210 mm state with this source')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.state and args.rebase_state:parser.error('choose state or rebase-state')
    if args.json and args.revision!='original':parser.error('choose JSON or a built-in revision')
    field=GridField.from_dict(json.loads(args.json.read_text())) if args.json else make_field(args.revision)
    if field.unit!='mm':parser.error('this recipe uses mm geometry; adapt make_views for other length units')
    scene=make_scene(field=field);original=make_scene()
    if args.rebase_state:
        revision=original.replace_data(scene.table,views=make_views(field),
            state=json.loads(args.rebase_state.read_text()),missing=args.missing)
        state=revision.state();report=revision.report()
    else:
        state=json.loads(args.state.read_text()) if args.state else scene.state(
            SelectionState.for_table(scene.table,selected=['cell-133'] if 'cell-133' in scene.table.row_ids else []))
        report=original.replace_data(scene.table,views=make_views(field)).report()
    scene.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    credit=CREDIT if not args.json else 'User-supplied nodal GridField JSON; linear triangle interpolation and normalized-vector RK4. Cell summaries are arithmetic corner means.'
    alternatives=[] if args.json else [RevisionOption(name.capitalize(),make_scene(name),CREDIT)
                                       for name in REVISIONS if name!=args.revision]
    (args.output/'index.html').write_text(scene.to_html(title='Contours and streamlines · '+('supplied data' if args.json else 'simulated nodal fields'),
        state=state,attribution=credit,revision_label='Supplied source' if args.json else args.revision.capitalize(),
        revisions=alternatives),encoding='utf-8')
    for name,value in [('view.json',state),('revision.json',report),('input.json',field.source()),
        ('measurements.json',dict(scene.table.columns)),('field.json',dict(source_digest=field.digest,
             unit=field.unit,scalar_unit=field.scalar_unit,vector_unit=field.vector_unit,
             methods='Cell area; arithmetic corner means; magnitude of the mean XY vector',
             tracing=make_views(field)[1].streamlines.report(),credit=credit))]:
        (args.output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (args.output/'figure.svg').write_text(scene.to_svg(state),encoding='utf-8')
    for width in (210,170):
        export=scene.replace_data(scene.table,state=state,width=width)
        svg=args.output/f'figure-{width}mm.svg';svg.write_text(export.figure.to_svg(export.state()),encoding='utf-8')
        (args.output/f'view-{width}mm.json').write_text(json.dumps(export.state(),indent=2)+'\n')
        if args.render:
            from inklet.render.preview import svg_png,svg_pdf
            svg_png(svg,svg.with_suffix('.png'),dpi=150);svg_pdf(svg,svg.with_suffix('.pdf'))
    print(args.output/'index.html')


if __name__=='__main__':main()
