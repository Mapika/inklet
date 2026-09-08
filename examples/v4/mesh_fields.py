"""Linked scalar and vector face fields on a simulated triangular surface."""
import argparse
import json
import math
from pathlib import Path

import inklet as i
from inklet.experimental.fields import MeshField
from inklet.experimental.browser import (BrowserFigure, DrawingItem, DrawingView,
    MeshFieldView, RevisionOption, ScatterView)
from inklet.experimental.selection import SelectionState

REVISIONS=('original','deformed','updated','removed')
CREDIT=('Simulated triangular surface and supplied face fields by Mark Marosi · MIT. '
        'No simulation or interpolation is performed. Plan colors are constant per face; arrows show XY components '
        'with 0.22 mm of geometry per vector unit. The scatter uses full XYZ magnitude. '
        'The fixed-camera 3D panel is an unpickable reference and stays visible during filtering. '
        'Plan triangles, arrows and scatter points follow face visibility. Geometry is in mm; field units are arbitrary.')


def make_field(revision='original'):
    if revision not in REVISIONS:raise ValueError('unknown field revision')
    vertices=[];faces=[];ids=[];scalars=[];vectors=[]
    for y in range(5):
        for x in range(7):
            z=.55*math.sin(x*math.pi/6)*math.sin(y*math.pi/4)
            if revision=='deformed':z*=2
            vertices.append((x,y,z))
    for y in range(4):
        for x in range(6):
            a=y*7+x
            for side,face in enumerate(((a,a+1,a+8),(a,a+8,a+7))):
                key=f'face-{y*12+x*2+side:02d}'
                if revision=='removed' and key=='face-19':continue
                cx=sum(vertices[n][0] for n in face)/3;cy=sum(vertices[n][1] for n in face)/3
                value=round(2+math.sin(cx*.8)*math.cos(cy*.6),3)
                vector=(round(-(cy-2)*.6,3),round((cx-3)*.4,3),round(.15*cx,3))
                if key=='face-00':vector=(0,0,0)
                if key=='face-47':value=None;vector=None
                if revision=='updated' and x>=3:
                    value=None if value is None else value+.6
                    vector=None if vector is None else tuple(v*1.4 for v in vector)
                faces.append(face);ids.append(key);scalars.append(value);vectors.append(vector)
    return MeshField(vertices,faces,ids,scalars,vectors,'mm','a.u.','a.u.')


def make_views(field):
    scalar=MeshFieldView('scalar',field,breaks=(1.5,2,2.5),
                         colors=('#e5edf0','#b3d2d7','#71a9b4','#347687'),vector_scale=.22,scale_bar=1)
    vectors=MeshFieldView('vectors',field,breaks=scalar.breaks,colors=scalar.colors,vectors=True,vector_scale=.22,scale_bar=1)
    def surface(table,width,height):
        field.validate_table(table)
        node=i.model(field.mesh(),width=width-8,view=(28,48),style='solid',sort='exact',
                     colors={key:scalar.color(value) for key,value in zip(field.ids,field.scalars)},
                     cull=False,hidden=True,stroke_width=.12,lift=0,shade=0)
        if node.bbox.height>height-6:node=node.scaled((height-6)/node.bbox.height)
        node=node.translated(width/2-node.bbox.center.x,height/2-node.bbox.center.y)
        return [DrawingItem((),node,description='Fixed-camera 3D reference; face colors match the plan')]
    return [scalar,vectors,DrawingView('surface',surface),
            ScatterView('values','scalar','magnitude',(.8,3.7),(-.1,2.4),
                x_label=f'Face scalar / {field.scalar_unit}',y_label=f'XYZ magnitude / {field.vector_unit}',radius_mm=.7)]


def make_scene(revision='original',*,width=210,field=None):
    field=make_field(revision) if field is None else field
    return BrowserFigure(field.table(),make_views(field),width=width,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-mesh-fields'))
    parser.add_argument('--revision',choices=REVISIONS,default='original')
    parser.add_argument('--json',type=Path,help='Replacement MeshField source; input.json is the template')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--rebase-state',type=Path,help='Reconcile an original 210 mm state with this source')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.state and args.rebase_state:parser.error('choose state or rebase-state')
    if args.json and args.revision!='original':parser.error('choose JSON or a built-in revision')
    field=MeshField.from_dict(json.loads(args.json.read_text())) if args.json else make_field(args.revision)
    if field.unit!='mm':parser.error('this recipe uses mm geometry; adapt make_views for other length units')
    scene=make_scene(field=field);original=make_scene()
    if args.rebase_state:
        revision=original.replace_data(scene.table,views=make_views(field),
            state=json.loads(args.rebase_state.read_text()),missing=args.missing)
        state=revision.state();report=revision.report()
    else:
        state=json.loads(args.state.read_text()) if args.state else scene.state(
            SelectionState.for_table(scene.table,selected=['face-19'] if 'face-19' in scene.table.row_ids else []))
        report=original.replace_data(scene.table,views=make_views(field)).report()
    scene.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    credit=CREDIT if not args.json else ('User-supplied MeshField JSON. '+CREDIT[CREDIT.index('No simulation'):].replace('field units are arbitrary',f'scalar unit: {field.scalar_unit}; vector unit: {field.vector_unit}'))
    alternatives=[] if args.json else [RevisionOption(name.capitalize(),make_scene(name),CREDIT)
                                       for name in REVISIONS if name!=args.revision]
    (args.output/'index.html').write_text(scene.to_html(title='Linked mesh fields · '+('supplied data' if args.json else 'simulated surface'),
        state=state,attribution=credit,revision_label='Supplied source' if args.json else args.revision.capitalize(),
        revisions=alternatives),encoding='utf-8')
    for name,value in [('view.json',state),('revision.json',report),('input.json',field.source()),
        ('measurements.json',dict(scene.table.columns)),('field.json',dict(source_digest=field.digest,
             unit=field.unit,scalar_unit=field.scalar_unit,vector_unit=field.vector_unit,
             methods='Area from 3D triangle cross product; vector magnitude from XYZ components',credit=credit))]:
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
