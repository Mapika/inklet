"""Queued architectural views, a changed material, vector dimensions and a plot.

Create the room with tools/showcase_gallery.py --only architecture --download-assets.
"""
import argparse
import json
import math
from pathlib import Path
import inklet as i

ROOT=Path(__file__).resolve().parents[1]


def render_views(scene, *, quality='final', device='AUTO', blender=None):
    common=dict(width=85,height=65,quality=quality,engine='CYCLES',device=device,blender=blender,
        landmarks={'book':'Book',
            'table-left':{'object':'Coffee table','point':[-.85,0,.05]},
            'table-right':{'object':'Coffee table','point':[.85,0,.05]}})
    views=[('Overview',dict(camera='Overview')),
           ('Detail',dict(camera='Detail')),
           ('Sketch',dict(camera='Overview',style='sketch'))]
    with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
        initial=[queue.submit(scene,**common,**options) for name,options in views]
        for job in initial:job.result()
        changed=dict(camera='Overview',bindings={'Book':{'color':'#d85e45'}})
        # A second build changes one view; the other three must use their cache.
        views.append(('Changed material',changed))
        jobs=[queue.submit(scene,**common,**options) for name,options in views]
        results=[job.result() for job in jobs]
    assert all(result.cache_hit for result in results[:3])
    return list(zip((name for name,options in views),results))


def make_document(rendered):
    doc=i.preset('scientific.general').document(width=200,columns=2,gap=6,margin=8)
    doc.add('title',i.text('One scene, four render jobs',size=i.pt(20),text_fill='#172b42'),colspan=2)
    doc.add('subtitle',i.text('Automatic GPU rendering with editable vector annotations',
                             size=i.pt(9),text_fill='#49647a'),colspan=2)
    captions=('Table width, in authored scene units.', 'A closer view of the same room.',
              'Matte surfaces and procedural outlines.', 'Only the book material changes.')
    for index,(name,result) in enumerate(rendered):
        art=result.diagram
        if index==0:
            a=art.anchor_point('table-left');b=art.anchor_point('table-right')
            span=b-a;normal=i.Vec2(-span.y,span.x).normalized()
            offset=(art.height/2+5-(a.y+b.y)/2)/normal.y
            dimension=i.dimension(art.at('table-left'),art.at('table-right'),'1.7',
                offset=offset,size=i.pt(8),within=art,stroke='#294e65',stroke_width=.25)
            # Dimensions use projected coordinates; preserve their shared origin.
            art=i.overlay([art,dimension],align='origin')
        elif index==3:
            art=i.annotate(art.at('book'),'Coral base colour',side='s',
                clear=art.height/2-art.anchor_point('book').y+5,
                through=[art],within=art,search=False,size=i.pt(8),head='triangle',
                leader_style={'stroke':'#294e65','stroke_width':.25})
        art=i.overlay([i.spacer(width=85,height=85),art],align='origin')
        panel=i.vstack([i.text(chr(65+index)+'  '+name,size=i.pt(11),text_fill='#172b42'),art,
            i.text(captions[index],size=i.pt(8),text_fill='#49647a')],gap=3,align='left')
        doc.add('view-'+str(index),panel,row=2+index//2,column=index%2)
    panel=i.panel(172,28,x=(8,18),y=(0,1.1))
    xs=[8+n/10 for n in range(101)]
    panel.line([(x,math.sin(math.pi*(x-8)/10)) for x in xs],stroke='#258e9b',stroke_width=.35)
    panel.axes(x='Time / h',y='Relative signal')
    doc.add('plot',panel.build(),colspan=2)
    doc.add('caption',i.text('Conceptual room. The analytic curve is not a daylight simulation.',
                           size=i.pt(8),text_fill='#49647a'),colspan=2)
    doc.add('credits',i.text('Chair: Vibrant Nordic / Poly Haven (CC0). Room and figure: Inklet (MIT).',
                           size=i.pt(8),text_fill='#49647a'),colspan=2)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,default=ROOT/'out/showcase/scenes/architecture.blend')
    parser.add_argument('--output',type=Path,default=ROOT/'out/v3-jobs')
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    parser.add_argument('--device',default='AUTO')
    parser.add_argument('--blender',type=Path)
    args=parser.parse_args()
    rendered=render_views(args.scene,quality=args.quality,device=args.device,blender=args.blender)
    compiled=make_document(rendered).compile()
    if any(d.severity=='error' for d in compiled.diagnostics):raise RuntimeError(compiled.report())
    files=compiled.export(args.output,dpi=i.render_quality(args.quality).dpi)
    (args.output/'jobs.json').write_text(json.dumps([
        dict(view=name,cache_hit=result.cache_hit,cache_key=result.metadata['cache_key'],
             execution=result.metadata['execution']) for name,result in rendered],indent=2)+'\n')
    print(compiled.report())
    print(files['review'])


if __name__=='__main__':main()
