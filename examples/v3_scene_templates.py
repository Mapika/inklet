"""Create the three packaged starter scenes and export a complete comparison."""
import argparse
from pathlib import Path
import inklet as i

ROOT = Path(__file__).resolve().parents[1]


def make_document(renders):
    doc = i.document(width=210,columns=2,margin=8,gap=6)
    doc.add('title',i.text('Three editable scene templates',size=i.pt(20),text_fill='#172f32'),colspan=2)
    doc.add('subtitle',i.text('Packaged geometry, named cameras and annotation landmarks. No asset downloads.',
        size=i.pt(9),text_fill='#586b6d'),colspan=2)
    for row,(name,title,caption) in enumerate([
        ('laboratory','Laboratory apparatus','Vessel geometry and illustrative fill level.'),
        ('product','Product studio','Enclosure proportions and accent colour.'),
        ('architecture','Architectural room','Room dimensions and original furniture.'),
    ]):
        for col,camera in enumerate(('Overview','Detail')):
            scene = renders[name,camera]
            key = {'laboratory':'probe','product':'control','architecture':'table'}[name]
            world = scene.metadata['landmarks'][key]['world']
            # Keep labels above the frame for readable comparisons at print size.
            point = scene.project(world).point
            label = scene.annotate3d(world,key.title(),side='n',clear=point.y+scene.diagram.height/2+2,
                hidden='show',size=i.pt(7.5),leader_style=dict(stroke='#172f32',stroke_width=.2))
            art = i.overlay([scene.diagram,label],align='origin')
            doc.add(name+'-'+camera,i.vstack([
                i.text(title+' · '+camera.lower(),size=i.pt(10),text_fill='#172f32'),
                art,i.text(caption,size=i.pt(8),text_fill='#586b6d')],gap=3,align='left'),
                row=row+2,column=col)
    doc.add('caption',i.text('Original conceptual models. Render pixels are embedded; annotations remain vector.',
        size=i.pt(8),text_fill='#586b6d'),colspan=2)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/v3-templates')
    parser.add_argument('--blender',type=Path)
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    parser.add_argument('--rebuild',action='store_true',help='Replace generated .blend files')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    catalogue=i.scene_templates()
    paths={}
    for name in catalogue:
        path=args.output/(name+'.blend')
        if args.rebuild or not path.exists():
            i.create_scene(name,path,blender=args.blender,overwrite=args.rebuild)
        paths[name]=path
    with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
        jobs={(name,camera):queue.submit(path,width=87,height=65.25,camera=camera,
            engine='CYCLES',passes=('depth',),quality=args.quality,blender=args.blender,
            landmarks=catalogue[name]['landmarks'])
            for name,path in paths.items() for camera in ('Overview','Detail')}
        renders={key:job.result() for key,job in jobs.items()}
    figure=make_document(renders).compile()
    if any(d.severity=='error' for d in figure.diagnostics):
        raise RuntimeError(figure.report())
    print(figure.report())
    print(figure.export(args.output,dpi=i.render_quality(args.quality).dpi)['review'])


if __name__=='__main__':main()
