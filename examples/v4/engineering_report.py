"""Linked dimensioned assembly, section, system diagram and supplied response."""
import argparse
import json
from pathlib import Path

import inklet as i
from inklet.core import group
from inklet.experimental.browser import BrowserFigure, DrawingItem, DrawingView, RevisionOption, SeriesView
from inklet.experimental.engineering import BoxAssembly
from inklet.experimental.selection import KeyedTable, SelectionState

FIXTURE=Path(__file__).with_name('fixtures')/'assembly.json'
COLORS=dict(base='#dbe6e3',support='#8eb9ad',sensor='#85aaca')
DEFAULT_LABELS=dict(base=[0,10],support=[-2,-8],sensor=[3,-8])
CREDIT=('Original illustrative assembly by Mark Marosi · MIT material. Dimensions are computed from '
        'axis-aligned boxes in millimetres. Response curves are supplied simulated values, not solved '
        'mechanics: base is fixed, support uses half the fixture response, sensor uses the fixture response. '
        'Geometry revisions do not recalculate these supplied responses. Section: zero-thickness Y = 0 mm. '
        'Picking uses rectangular component targets. System links indicate authored assembly relations.')


def make_assembly(revision='original'):
    source=json.loads(FIXTURE.read_text())
    if revision not in ('original','resized','removed'): raise ValueError('unknown assembly revision')
    if revision=='resized':
        source['components'][1].update(size=[10,10,36],center=[-25,0,23])
        source['components'][2].update(size=[26,16,12],center=[24,0,11])
    if revision=='removed': source['components']=[p for p in source['components'] if p['id']!='support']
    return BoxAssembly.from_dict(source)


def make_table(assembly):
    response=json.loads(FIXTURE.read_text())['response']
    columns={key:[] for key in ('id','width_mm','depth_mm','height_mm','center_x_mm','center_y_mm','center_z_mm',
                               'at_0N','at_10N','at_20N','at_30N')}
    for part in assembly.components:
        factor=dict(base=0,support=.5,sensor=1)[part.id]
        row=(part.id,*part.size,*part.center,*(v*factor for v in response['displacement_mm']))
        for name,value in zip(columns,row): columns[name].append(value)
    return KeyedTable('engineering-assembly',columns)


def read_labels(path=None):
    labels=dict(DEFAULT_LABELS) if path is None else json.loads(path.read_text())
    if not isinstance(labels,dict) or set(labels)-set(DEFAULT_LABELS): raise ValueError('unknown label IDs')
    import math
    for key,offset in labels.items():
        if (not isinstance(offset,(tuple,list)) or len(offset)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>20 for v in offset)):
            raise ValueError(f'label {key}: provide finite dx/dy in panel mm, within ±20 mm')
    return {key:tuple(value) for key,value in (DEFAULT_LABELS|labels).items()}


def text_at(text,x,y):
    body=i.text(text,size=i.pt(8),markup=False)
    return body.translated(x-body.bbox.center.x,y-body.bbox.center.y)


def polyline_at(points,**style):
    xs,ys=zip(*points)
    return i.polyline(points,**style).translated((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)


def drawings(assembly,labels,section=False):
    def build(table,width,height):
        if tuple(table.row_ids)!=assembly.ids: raise ValueError('assembly/table IDs or order differ')
        scale=min((width-20)/90,(height-22)/50)
        x0=width/2;y0=height-12 if section else height/2-3
        def point(x,y):return (x0+x*scale,y0-y*scale)
        if section: shapes=assembly.section('y',0)
        else: shapes=tuple((p.id,(p.bounds[0][0],p.bounds[0][1],p.bounds[1][0],p.bounds[1][1])) for p in assembly.components)
        objects=[];annotations=[]
        for key,(left,bottom,right,top) in shapes:
            x,y=point(left,top);w=(right-left)*scale;h=(top-bottom)*scale
            box=i.box(width=w,height=h,pad=0,radius=0,fill=COLORS[key],stroke='#365750',stroke_width=.3).translated(x+w/2,y+h/2)
            objects.append(DrawingItem((key,),box,(x,y,w,h),description=f'{key}; '+('Y = 0 section' if section else 'XY plan')))
            dx,dy=labels[key]
            anchor=(x+w/2,y+h/2 if key=='base' else y)
            # Keep the base label beneath its footprint, even in section.
            target=(anchor[0]+dx,anchor[1]+dy)
            label=text_at(key.capitalize(),*target)
            leader=polyline_at([anchor,target],stroke='#58716b',stroke_width=.2)
            annotations.append(DrawingItem((key,),group([leader,label]),(x,y,w,h),description=key+' label',pickable=False,highlight=False))
        lo,hi=assembly.bounds
        if section:
            a=point(hi[0]+5,lo[2]);b=point(hi[0]+5,hi[2])
            dimension=i.dimension(a,b,f'{assembly.size[2]:g} mm',size=i.pt(8),stroke='#365750',stroke_width=.25).translated((a[0]+b[0])/2,(a[1]+b[1])/2)
            reference=text_at('Section Y = 0 mm',width/2,4)
        else:
            a=point(lo[0],lo[1]-8);b=point(hi[0],lo[1]-8)
            dimension=i.dimension(a,b,f'{assembly.size[0]:g} mm',size=i.pt(8),stroke='#365750',stroke_width=.25).translated((a[0]+b[0])/2,(a[1]+b[1])/2)
            reference=text_at('XY plan · dimensions in mm',width/2,4)
        return [*objects,*annotations,DrawingItem((),dimension,description='Assembly extent'),DrawingItem((),reference)]
    return build


def system_drawing(assembly):
    def build(table,width,height):
        centers=dict(base=(width/2,height-10),support=(width*.27,17),sensor=(width*.73,17))
        objects=[];links=[]
        for part in assembly.components:
            x,y=centers[part.id]
            body=i.box(i.text(part.id.capitalize(),size=i.pt(8)),width=21,height=10,pad=1,radius=1,
                       fill=COLORS[part.id],stroke='#365750',stroke_width=.3).translated(x,y)
            objects.append(DrawingItem((part.id,),body,description=part.id+' system node'))
        for key in ('support','sensor'):
            if key not in assembly.ids: continue
            x,y=centers[key];bx,by=centers['base']
            line=polyline_at([(bx,by-5),(bx,32),(x,32),(x,y+5)],stroke='#58716b',stroke_width=.3)
            links.append(DrawingItem(('base',key),line,description='Base–'+key+' attachment',pickable=False,highlight=False))
        return [*links,*objects]
    return build


def make_views(assembly,labels):
    return [DrawingView('plan',drawings(assembly,labels)),
            DrawingView('section',drawings(assembly,labels,section=True)),
            DrawingView('system',system_drawing(assembly)),
            SeriesView('response',[(0,'at_0N'),(10,'at_10N'),(20,'at_20N'),(30,'at_30N')],
                       (-1,31),(-.03,.65),x_label='Load / N',y_label='Displacement / mm',radius_mm=.65)]


def make_scene(revision='original',*,width=210,labels=None):
    assembly=make_assembly(revision);labels=read_labels() if labels is None else labels
    return BrowserFigure(make_table(assembly),make_views(assembly,labels),width=width,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-engineering'))
    parser.add_argument('--revision',choices=('original','resized','removed'),default='original')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--rebase-state',type=Path,help='Apply an original 210 mm state to the chosen revision')
    parser.add_argument('--labels',type=Path,help='JSON label offsets, keyed by component ID, in panel mm')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.state and args.rebase_state: parser.error('choose state or rebase-state')
    labels=read_labels(args.labels);assembly=make_assembly(args.revision);figure=make_scene(args.revision,labels=labels)
    original=make_scene(labels=labels)
    if args.rebase_state:
        revision=original.replace_data(figure.table,views=make_views(assembly,labels),
            state=json.loads(args.rebase_state.read_text()),missing=args.missing)
        state=revision.state();report=revision.report()
    else:
        state=json.loads(args.state.read_text()) if args.state else figure.state(SelectionState.for_table(figure.table,selected=['sensor']))
        report=original.replace_data(figure.table,views=make_views(assembly,labels)).report()
    figure.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    alternatives=[RevisionOption(name.capitalize(),make_scene(name,labels=labels),CREDIT)
                  for name in ('original','resized','removed') if name!=args.revision]
    (args.output/'index.html').write_text(figure.to_html(title='Engineering assembly · supplied simulated response',
        state=state,attribution=CREDIT,revision_label=args.revision.capitalize(),revisions=alternatives),encoding='utf-8')
    for name,value in [('view.json',state),('labels.json',labels),('revision.json',report),
        ('assembly.json',assembly.report()|dict(orphaned_labels=sorted(set(labels)-set(assembly.ids))))]:
        (args.output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (args.output/'figure.svg').write_text(figure.to_svg(state),encoding='utf-8')
    for width in (210,170):
        resized=figure.replace_data(figure.table,state=state,width=width)
        svg=args.output/f'figure-{width}mm.svg';svg.write_text(resized.figure.to_svg(resized.state()),encoding='utf-8')
        (args.output/f'view-{width}mm.json').write_text(json.dumps(resized.state(),indent=2)+'\n')
        if args.render:
            from inklet.render.preview import svg_png,svg_pdf
            svg_png(svg,svg.with_suffix('.png'),dpi=150);svg_pdf(svg,svg.with_suffix('.pdf'))
    print(args.output/'index.html')


if __name__=='__main__':main()
