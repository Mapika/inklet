"""An annotated laboratory cutaway with detail views and an illustrative data plot."""
import argparse
import json
import math
from pathlib import Path
import subprocess

import inklet as i
from inklet.three.blender import find_blender
from inklet.three import templates

ROOT=Path(__file__).resolve().parents[1]
INK,MUTED,ACCENT='#172f32','#586b6d','#a85518'
LABELS=('Exhaust manifold','Cable tray','Reactor A','Reactor B','Feed pump',
        'Control display','Sample rack','Flow cell','Detector','Gas supply',
        'Recirculator','Transfer line')


def create_lab(path,blender=None):
    binary=find_blender(blender)
    process=subprocess.run([str(binary.path),'--background','--factory-startup','--disable-autoexec',
        '--threads','4','--python-exit-code','1','--python',str(ROOT/'examples/blender/complex_lab_scene.py'),
        '--',str(templates._WORKER),str(path)],capture_output=True,text=True,timeout=90)
    if process.returncode:
        raise RuntimeError(process.stdout[-6000:]+process.stderr[-6000:])
    return process.stdout


def annotated_overview(scene):
    groups=[('w',{'Exhaust manifold','Reactor A','Reactor B','Gas supply','Sample rack','Transfer line'}),
            ('e',{'Cable tray','Feed pump','Control display','Flow cell','Detector','Recirculator'})]
    parts=[scene.diagram]
    for side,names in groups:
        ordered=sorted(names,key=lambda name:scene.project(scene.metadata['landmarks'][name]['world']).point.y)
        sign=-1 if side=='w' else 1
        for row,name in enumerate(ordered):
            world=scene.metadata['landmarks'][name]['world']
            projected=scene.project(world)
            y=-51+row*19
            body=i.text(name,size=i.pt(8),text_fill=INK)
            box=body.bbox
            x=sign*95-(box.width if side=='w' else 0)
            body=body.translated(x-box.x0,y-box.center.y)
            leader=i.as_drawn(i.polyline([projected.point,i.Vec2(sign*91,y),i.Vec2(sign*94,y)],
                stroke='#50646a',stroke_width=.25,stroke_dash=(1.,1.) if projected.visible is False else None))
            i.crossing(leader,scene.diagram)
            marker=i.marker('circle',size=.9,fill='white',stroke=INK,stroke_width=.25)
            dot=i.place([(projected.point,marker)],origin=(0,0))
            callout=i.Diagram(children=(leader,body,i.as_drawn(dot)),kind='scene-callout',
                notes={'scene_annotation':dict(type='callout',name=name,world=world,
                    visible=projected.visible,in_frame=projected.in_frame,
                    source_cache_key=scene.metadata['cache_key'])})
            callout.anchor('origin',i.Vec2(0,0))
            parts.append(callout)
    left=scene.metadata['landmarks']['width_left']['world']
    right=scene.metadata['landmarks']['width_right']['world']
    parts.append(scene.dimension3d(left,right,unit='m',offset=7,hidden='show',size=i.pt(8),
        stroke=INK,stroke_width=.25))
    # Conceptual transfer route, kept separate from the authored physical tubing.
    route=[(-2,1.0,1.75),(-1.0,.3,1.4),(.53,-.65,1.10),(.53,-1.25,1.33)]
    parts.append(scene.path3d(route,hidden='dash',stroke=ACCENT,stroke_width=.45))
    return i.overlay(parts,align='origin')


def response_plot():
    panel=i.panel(64,41,x=(0,12),y=(0,1.1))
    points=[(n/10,1-math.exp(-n/30)) for n in range(121)]
    panel.line(points,stroke='#237f83',stroke_width=.45)
    panel.line([(x,max(0,1-math.exp(-(x-1.5)/4))) for x,_ in points],
        stroke=ACCENT,stroke_width=.45,stroke_dash=(1.2,.7))
    panel.axes(x='Time / min',y='Response / a.u.')
    return panel.build()


def make_document(renders):
    doc=i.document(width=260,columns=3,margin=8,gap=7)
    doc.add('title',i.text('An instrumented laboratory',size=i.pt(22),text_fill=INK),colspan=3)
    doc.add('subtitle',i.text('A complete 3D cutaway with twelve callouts, a measured footprint and a projected transfer route.',
        size=i.pt(9),text_fill=MUTED),colspan=3)
    doc.add('overview',annotated_overview(renders['Overview']),colspan=3)
    doc.add('key',i.text('Solid leaders: visible targets. Dashed leaders: obscured targets. Amber path: illustrative transfer route.',
        size=i.pt(8),text_fill=MUTED),colspan=3)
    for col,(camera,title) in enumerate([('Process','A  Process bench'),('Analysis','B  Analysis island')]):
        doc.add(camera,i.vstack([i.text(title,size=i.pt(10),text_fill=INK),renders[camera].diagram],gap=4,align='left'),row=4,column=col)
    doc.add('response',i.vstack([i.text('C  Illustrative response',size=i.pt(10),text_fill=INK),response_plot()],
        gap=4,align='left'),row=4,column=2)
    doc.add('caption',i.text('Original conceptual geometry. Response curves are analytic examples, not simulation results from the apparatus.',
        size=i.pt(8),text_fill=MUTED),colspan=3)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/v3-complex')
    parser.add_argument('--blender',type=Path)
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    parser.add_argument('--rebuild',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    scene=args.output/'laboratory.blend'
    if args.rebuild or not scene.exists():
        (args.output/'creation.log').write_text(create_lab(scene,args.blender))
    landmarks={name:'Target '+name for name in LABELS}|{'width_left':'Width left','width_right':'Width right'}
    with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
        jobs={camera:queue.submit(scene,width=180 if camera=='Overview' else 76,
            height=130 if camera=='Overview' else 55,camera=camera,engine='CYCLES',
            quality=args.quality,passes=('depth',),landmarks=landmarks if camera=='Overview' else {},
            blender=args.blender) for camera in ('Overview','Process','Analysis')}
        renders={name:job.result() for name,job in jobs.items()}
    figure=make_document(renders).compile()
    if any(d.severity=='error' for d in figure.diagnostics):
        raise RuntimeError(figure.report())
    print(figure.report())
    print(figure.export(args.output,dpi=i.render_quality(args.quality).dpi)['review'])
    inventory=i.inspect_blend(scene,blender=args.blender)
    (args.output/'scene-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')


if __name__=='__main__':main()
