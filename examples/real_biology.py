"""Real calibrated FIB-SEM, source segmentations and measurements in one figure.

Data: COSEM / HHMI Janelia, jrc_hela-3, CC BY 4.0. Source prediction labels are
not ground truth. The fixed spatial crop does not infer cell membership.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
import inklet as i
from inklet.core import ImagePrim
from inklet.experimental.volume import Volume
from inklet.experimental.figure_planner import Target,View,plan
from inklet.three import templates
from inklet.three.blender import find_blender
from biology.data import fetch,load

ROOT=Path(__file__).resolve().parents[1]
COLORS={'nucleus':(.62,.56,.69),'mito':(.04,.40,.44),'er':(.72,.43,.15),'selected':(.02,.24,.30)}
HEX={'nucleus':'#9e8fb0','mito':'#0a666f','er':'#b86e26'}
START,STOP=(40,0,80),(640,62,630)
WINDOW=(17000,26000)


def write_mesh(path,mesh):
    with path.open('w') as file:
        for v in mesh.vertices:file.write(f'v {v.x:.9g} {v.y:.9g} {v.z:.9g}\n')
        for f in mesh.faces:file.write('f '+' '.join(str(v+1) for v in f)+'\n')


def prepare(output,arrays,transform):
    spacing=tuple(v/1000 for v in transform['scale'])
    origin=tuple(v/1000 for v in transform['translate'][::-1])
    raw=Volume(arrays['fibsem-uint16'],spacing,'um',origin,'jrc_hela-3/em/fibsem-uint16/s4').crop(START,STOP)
    masks={name:Volume(arrays[key],spacing,'um',origin,f'jrc_hela-3/labels/{key}/s4').crop(START,STOP)
           for name,key in [('nucleus','nucleus_seg'),('mito','mito_seg'),('er','er_seg')]}
    ids,counts=np.unique(masks['mito'].data,return_counts=True)
    ranked=sorted(((int(n),int(label)) for n,label in zip(counts,ids) if label),reverse=True)
    top=[masks['mito'].measure(label) for _,label in ranked[:8]]
    totals={name:dict(voxel_count=int(np.count_nonzero(v.data)),
        volume=float(np.count_nonzero(v.data)*np.prod(spacing)),volume_unit='um^3') for name,v in masks.items()}
    record=dict(dataset='jrc_hela-3',level='s4',crop_start_zyx=START,crop_stop_zyx=STOP,
        grid=raw.report(),display_window=WINDOW,totals=totals,top_mitochondrial_labels=top,
        nucleus=masks['nucleus'].measure(1),
        nonzero_source_labels={k:len(np.unique(v.data))-int(np.any(v.data==0)) for k,v in masks.items()},
        overlapping_voxels={a+' / '+b:int(np.count_nonzero((masks[a].data>0)&(masks[b].data>0)))
            for a,b in [('nucleus','mito'),('nucleus','er'),('mito','er')]})
    meshes=[];anchors=[]
    def add(name,values,label,material,step):
        v=Volume(values,spacing,'um',raw.origin_xyz,raw.source_id+'/'+name)
        measurement=v.measure(label)
        mesh=v.surface(label,allow_clipped=True,step_size=step)
        path=output/(name+'.obj');write_mesh(path,mesh)
        meshes.append(dict(name=name,file=path.name,material=material,step_size=step,
            vertices=len(mesh.vertices),triangles=len(mesh.faces),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            artificial_boundary_caps=measurement['touches_boundary']))
        return measurement
    add('nucleus-1',masks['nucleus'].data,1,'nucleus',2)
    anchors.append(dict(id='nucleus-1',object='nucleus-1',label='Nucleus / ID 1',centroid_xyz=record['nucleus']['centroid_xyz']))
    for measure in top[:3]:
        name='mito-'+str(measure['label'])
        add(name,masks['mito'].data,measure['label'],'selected',1)
        anchors.append(dict(id=name,object=name,label='Mitochondrion / ID '+str(measure['label']),centroid_xyz=measure['centroid_xyz']))
    remaining=(masks['mito'].data>0)&~np.isin(masks['mito'].data,[p['label'] for p in top[:3]])
    add('other-mito',remaining.astype('uint8'),1,'mito',2)
    add('endoplasmic-reticulum',(masks['er'].data>0).astype('uint8'),1,'er',2)
    scene=dict(source=record,meshes=meshes,anchors=anchors,colors=COLORS,bounds_xyz=raw.report()['bounds_xyz'])
    (output/'meshes.json').write_text(json.dumps(scene,indent=2)+'\n')
    return raw,masks,record,scene


def section_overlay(raw,masks,*,width):
    section=raw.slice('y',31);diagram=section.diagram(width=width,window=WINDOW)
    rgb=np.array(Image.open(io.BytesIO(diagram.prim.data)).convert('RGB')).astype(float)
    for name in ('nucleus','er','mito'):
        selected=np.flipud(masks[name].data[:,31,:]>0)
        rgb[selected]=rgb[selected]*.45+np.array(COLORS[name])*255*.55
    buffer=io.BytesIO();Image.fromarray(np.rint(rgb).astype('uint8')).save(buffer,format='PNG')
    return i.Diagram(prim=ImagePrim(source='Source segmentation overlay',width=width,height=diagram.height,
        data=buffer.getvalue(),smooth=False),notes={'calibrated_slice':diagram.notes['calibrated_slice'],'overlay_alpha':.55})


def make_figure(raw,masks,record,scene,rendered):
    targets=tuple(Target(a['id'],a['label'],rendered.metadata['landmarks'][a['id']]['world'],visibility='in_frame') for a in scene['anchors'])
    planned=plan(targets,[View('Overview',rendered)],width=340,max_height=220,font_pt=9,
                 image_scales=(1,),depth_bias=.04,crossing_penalty=25)
    if not planned.feasible:raise RuntimeError(str(planned.issues))
    record['plan']=planned.report()
    doc=i.document(width=360,columns=3,margin=8,gap=10)
    doc.add('title',i.text('From electron microscopy to measured 3D structures',size=i.pt(22)),colspan=3)
    doc.add('subtitle',i.text('HeLa / jrc_hela-3 / one calibrated crop, source organelle labels and editable vector annotations',size=i.pt(9)),colspan=3)
    doc.add('scene-title',i.text('a  Segmentation surfaces in physical coordinates',size=i.pt(11)),colspan=3)
    doc.add('scene',planned.diagram(),colspan=3)
    doc.add('scene-note',i.text('Purple: nucleus 1. Teal: mitochondria. Amber: endoplasmic reticulum. Dashed leaders indicate depth-occluded targets.',size=i.pt(8)),colspan=3)
    section=raw.slice('y',31);width=96
    for col,(name,title,diagram) in enumerate([
        ('microscopy','b  FIB-SEM / XZ section',section.diagram(width=width,window=WINDOW)),
        ('overlay','c  Matching segmentation',section_overlay(raw,masks,width=width))]):
        doc.add(name+'-title',i.text(title,size=i.pt(10)),row=5,column=col)
        doc.add(name,i.vstack([diagram,section.scalebar(5,width=width)],gap=3),row=6,column=col)
    xy=raw.slice('z',260);yz=raw.slice('x',266)
    scale=width/xy.extent[0]
    orthogonal=i.vstack([i.text('XY / source z index 300',size=i.pt(8)),xy.diagram(width=width,window=WINDOW),
        i.text('YZ / source x index 346 / rotated 90°',size=i.pt(8)),
        yz.diagram(width=scale*yz.extent[0],window=WINDOW).rotated(90),xy.scalebar(5,width=width),
        i.text('Voxel spacing (Z, Y, X)\n0.05184, 0.064, 0.064 µm\nNo thickness exaggeration',size=i.pt(8))],gap=4)
    doc.add('sections-title',i.text('d  Orthogonal sections',size=i.pt(10)),row=5,column=2)
    doc.add('sections',orthogonal,row=6,column=2)
    names=['Nucleus','Mito','ER'];keys=['nucleus','mito','er']
    p=i.panel(80,52,x=names,y=(0,550))
    p.bars(names,[record['totals'][k]['volume'] for k in keys],bar_colors=[HEX[k] for k in keys])
    p.axes(y='Mask volume / µm³',count=4)
    doc.add('volumes-title',i.text('e  Mask volumes in this crop',size=i.pt(10)),row=7,column=0)
    doc.add('volumes',p.build(),row=8,column=0)
    labels=[str(p['label'])+('†' if p['touches_boundary'] else '') for p in record['top_mitochondrial_labels']]
    p=i.panel(190,52,x=labels,y=(0,7))
    p.bars(labels,[p['volume'] for p in record['top_mitochondrial_labels']],fill=HEX['mito'])
    p.axes(x='Mitochondrial source label ID / largest eight in this crop',y='Mask volume / µm³',count=4)
    doc.add('mito-title',i.text('f  Source identities shared by geometry and measurements',size=i.pt(10)),row=7,column=1,colspan=2)
    doc.add('mito-volumes',p.build(),row=8,column=1,colspan=2)
    doc.add('measurement-note',i.text('† Label touches the crop boundary and may be incomplete. Masks overlap; the totals are not a partition of cell volume.',size=i.pt(8)),colspan=3)
    doc.add('caption',i.text('Data: COSEM / HHMI Janelia, jrc_hela-3, CC BY 4.0; Heinrich et al., Nature (2021). '
        'Source segmentations are automated estimates. Volumes count every retained s4 voxel; 3D display surfaces may be subsampled. '
        'Boundary-touching labels are flagged in the report. This spatial crop does not establish cell membership or biological replication.',
        width=340,size=i.pt(8)),colspan=3)
    return doc.compile()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/real-biology')
    parser.add_argument('--blender',type=Path)
    parser.add_argument('--rebuild',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=args.output/'source.n5';lock=fetch(source);arrays,transform=load(source)
    raw,masks,record,scene=prepare(args.output,arrays,transform)
    binary=find_blender(args.blender).path;blend=args.output/'organelle.blend'
    worker=ROOT/'examples/blender/organelle_scene.py'
    digest=hashlib.sha256((args.output/'meshes.json').read_bytes()+worker.read_bytes()+templates._WORKER.read_bytes()).hexdigest()
    stamp=args.output/'scene-state.json'
    state=json.loads(stamp.read_text()) if stamp.exists() else {}
    valid=blend.exists() and state.get('input_sha256')==digest and state.get('blend_sha256')==hashlib.sha256(blend.read_bytes()).hexdigest()
    if args.rebuild or not valid:
        result=subprocess.run([str(binary),'--background','--factory-startup','--disable-autoexec','--threads','4',
            '--python-exit-code','1','--python',str(ROOT/'examples/blender/organelle_scene.py'),'--',
            str(templates._WORKER),str(args.output.resolve()),str(blend.resolve())],capture_output=True,text=True,timeout=180)
        (args.output/'creation.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout[-3000:]+result.stderr[-3000:])
        stamp.write_text(json.dumps(dict(input_sha256=digest,blend_sha256=hashlib.sha256(blend.read_bytes()).hexdigest()))+'\n')
    rendered=i.render_blend(blend,camera='Overview',width=280,height=175,dpi=330,quality='final',
        engine='CYCLES',passes=('depth',),landmarks={a['id']:'Target '+a['id'] for a in scene['anchors']},blender=binary)
    figure=make_figure(raw,masks,record,scene,rendered)
    print(figure.report(),flush=True)
    if any(d.severity=='error' for d in figure.diagnostics):raise RuntimeError(figure.report())
    figure.export(args.output,dpi=160)
    record.update(schema='inklet.real-biology/0.1',inklet_version=i.__version__,license=lock['license'],
        source_publication=lock['publication'],meshes=scene['meshes'],
        render=dict(blender=rendered.metadata['blender'],execution=rendered.metadata['execution']))
    (args.output/'measurements.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':main()
