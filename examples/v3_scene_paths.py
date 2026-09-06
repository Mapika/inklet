"""Camera-aware vector paths over an original rendered sensor housing."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import inklet as i

ROOT=Path(__file__).resolve().parents[1]


def make_scene(output, blender=None):
    from inklet.three.blender import find_blender
    binary=find_blender(blender)
    command=[str(binary.path),'--background','--factory-startup','--disable-autoexec',
        '--python-exit-code','1','--python',str(ROOT/'examples/blender/occlusion_scene.py'),'--',str(output)]
    process=subprocess.run(command,capture_output=True,text=True,timeout=90)
    if process.returncode:raise RuntimeError(process.stdout[-5000:]+process.stderr[-5000:])


def trajectory():
    # A conceptual winding path, not a field or physical simulation.
    return [(1.17*math.cos(t*6*math.pi),1.17*math.sin(t*6*math.pi),.52+2.2*t)
            for t in (n/600 for n in range(601))]


def make_document(front, perspective):
    points=trajectory()
    views=[('A  Complete path',front,'show','Every path segment is drawn over the scene.'),
           ('B  Visible sections',front,'omit','The housing hides the rear sections.'),
           ('C  Hidden sections dashed',front,'dash','Dashed lines show the occluded route.'),
           ('D  Perspective camera',perspective,'omit','The same world path through a different lens.')]
    doc=i.document(width=200,columns=2,margin=8,gap=6)
    doc.add('title',i.text('Vector paths in a 3D scene',size=i.pt(20),text_fill='#172f32'),colspan=2)
    doc.add('subtitle',i.text('One rendered housing. Camera-aware paths that stay editable in SVG and PDF.',
        size=i.pt(9),text_fill='#586b6d'),colspan=2)
    for index,(name,result,hidden,caption) in enumerate(views):
        path=result.path3d(points,hidden=hidden,stroke='#d47830',stroke_width=.45)
        art=i.overlay([result.diagram,path],align='origin')
        stack=i.vstack([i.text(name,size=i.pt(11),text_fill='#172f32'),art,
            i.text(caption,size=i.pt(8),text_fill='#586b6d')],gap=3,align='left')
        doc.add('view-'+str(index),stack,row=2+index//2,column=index%2)
    doc.add('caption',i.text('Original conceptual geometry and trajectory; no physical simulation is implied.',
        size=i.pt(8),text_fill='#586b6d'),colspan=2)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/v3-paths')
    parser.add_argument('--blender',type=Path)
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    scene=args.output/'sensor.blend';make_scene(scene,args.blender)
    with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
        jobs=[queue.submit(scene,width=85,height=78,engine='CYCLES',camera=camera,
            passes=('depth',),quality=args.quality,blender=args.blender)
            for camera in ('Overview','Perspective')]
        front,perspective=[job.result() for job in jobs]
    compiled=make_document(front,perspective).compile()
    if any(d.severity=='error' for d in compiled.diagnostics):raise RuntimeError(compiled.report())
    files=compiled.export(args.output,dpi=i.render_quality(args.quality).dpi)
    (args.output/'projection.json').write_text(json.dumps(dict(
        front=front.metadata['projection'],perspective=perspective.metadata['projection'],
        overlays=compiled.metadata['rendering']['scene_overlays']),indent=2)+'\n')
    print(compiled.report());print(files['review'])


if __name__=='__main__':main()
