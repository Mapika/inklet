"""Two physical oblique planes shared by real microscopy, labels and a 3D scene."""
import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import inklet as i
from inklet.core import ImagePrim
from inklet.experimental.sections import Plane
from biology.data import fetch,load
from real_biology import ROOT,WINDOW,COLORS,build_scene

PLANE_COLORS = ('#b33279','#2464b4')


def planes(centre):
    result = []
    for rotation,tilt in ((20,4),(-18,-8)):
        angle,pitch = math.radians(rotation),math.radians(tilt)
        right = (math.cos(angle),0,math.sin(angle))
        up = (-math.sin(angle)*math.cos(pitch),math.sin(pitch),math.cos(angle)*math.cos(pitch))
        result.append(Plane(centre,right,up,(351,401),(.08,.08),'um'))
    return result


def overlay_section(section, labels, width):
    base = section.diagram(width=width,window=WINDOW)
    rgba = np.array(Image.open(io.BytesIO(base.prim.data))).astype(float)
    for name in ('nucleus','er','mito'):
        selected = labels[name].valid & (labels[name].data>0)
        rgba[selected,:3] = rgba[selected,:3]*.45+np.array(COLORS[name])*255*.55
    buffer = io.BytesIO();Image.fromarray(np.rint(rgba).astype('uint8')).save(buffer,format='PNG')
    return i.Diagram(prim=ImagePrim(source='Matched oblique labels',width=width,height=base.height,
        data=buffer.getvalue(),smooth=False),notes={'sampled_section':section.report(),'overlay_alpha':.55})


def framed_section(diagram, plane, color, *, profile=False):
    # A visible backing distinguishes invalid transparent samples from dark EM.
    backing = i.box(width=diagram.width,height=diagram.height,pad=0,radius=0,fill='#e7ece9',stroke='none')
    border = i.box(width=diagram.width,height=diagram.height,pad=0,radius=0,fill='none',stroke=color,stroke_width=.5)
    layers = [backing,diagram,border]
    if profile:
        row = plane.shape_yx[0]//2
        start,end = (plane.project(plane.world(row,col),width=diagram.width) for col in (0,plane.shape_yx[1]-1))
        layers.append(i.polyline([(start.x,start.y),(end.x,end.y)],stroke=color,stroke_width=.3,stroke_dash=(1,1)))
    return i.vstack([i.overlay(layers,align='origin'),plane.scalebar(5,width=diagram.width)],gap=3)


def make_figure(raw,masks,record,rendered):
    bank = planes(record['nucleus']['centroid_xyz'])
    if not all(rendered.project(corner).in_frame for plane in bank for corner in plane.corners):
        raise RuntimeError('Sampling planes exceed the camera frame; increase camera_margin')
    sampled = [raw.reslice(plane,kind='intensity') for plane in bank]
    labels = [{name:volume.reslice(plane,kind='labels') for name,volume in masks.items()} for plane in bank]
    evidence = []
    for plane,section,mask in zip(bank,sampled,labels):
        assert all(np.array_equal(section.valid,s.valid) for s in mask.values())
        foreground = {name:dict(sampled_pixels=int(np.count_nonzero(s.data[s.valid])),
            area=float(np.count_nonzero(s.data[s.valid])*math.prod(plane.spacing_yx)),area_unit='um^2') for name,s in mask.items()}
        row = plane.shape_yx[0]//2
        evidence.append(dict(section=section.report(),foreground=foreground,
            source_labels={name:[int(v) for v in np.unique(s.data[s.valid]) if v] for name,s in mask.items()},
            nucleus_1=mask['nucleus'].measure(1),mitochondrial_157=mask['mito'].measure(157),
            profile=dict(row=row,world_endpoints=[plane.world(row,0),plane.world(row,plane.shape_yx[1]-1)],
                         values=section.data[row].tolist(),valid=section.valid[row].tolist())))
    doc = i.document(width=300,columns=2,margin=8,gap=8)
    doc.add('title',i.text('One volume, two oblique section planes',size=i.pt(21)),colspan=2)
    doc.add('subtitle',i.text('Real HeLa FIB-SEM · shared physical coordinates · exact source label IDs',size=i.pt(10)),colspan=2)
    layers = [rendered.diagram]
    for index,(plane,color) in enumerate(zip(bank,PLANE_COLORS)):
        layers.append(rendered.path3d([*plane.corners,plane.corners[0]],hidden='dash',depth_bias=.04,stroke=color,stroke_width=.5))
        layers.append(rendered.annotate3d(plane.corners[0],f'Plane {"AB"[index]}',side='w',clear=3,
            hidden='dash',depth_bias=.04,size=i.pt(10),text_fill=color))
    doc.add('scene-title',i.text('a  Sampling planes in the original 3D coordinate frame',size=i.pt(11)),colspan=2)
    doc.add('scene',i.overlay(layers,align='origin'),colspan=2)
    doc.add('scene-caption',i.text('Magenta A: +4° tilt from XZ. Blue B: −8° tilt from XZ. Dashed 3D edges are depth-occluded.',size=i.pt(8)),colspan=2)
    for index,(plane,section,mask,color) in enumerate(zip(bank,sampled,labels,PLANE_COLORS)):
        row = 5+index*2
        raw_picture = framed_section(section.diagram(width=126,window=WINDOW),plane,color,profile=True)
        overlay = framed_section(overlay_section(section,mask,126),plane,color)
        letter = 'bd'[index];letter2 = 'ce'[index]
        doc.add(f'raw-{index}-title',i.text(f'{letter}  Plane {"AB"[index]} / microscopy and profile line',size=i.pt(10)),row=row,column=0)
        doc.add(f'labels-{index}-title',i.text(f'{letter2}  Plane {"AB"[index]} / matching source labels',size=i.pt(10)),row=row,column=1)
        doc.add(f'raw-{index}',raw_picture,row=row+1,column=0)
        doc.add(f'labels-{index}',overlay,row=row+1,column=1)
    keys = ['nucleus','mito','er'];names = ['Nucleus','Mito','ER']
    areas = [[e['foreground'][k]['area'] for k in keys] for e in evidence]
    p = i.panel(110,55,x=names,y=(0,max(max(a) for a in areas)*1.18))
    p.bars(names,areas,names=['Plane A','Plane B'],colors=PLANE_COLORS)
    p.axes(y='Sampled mask area / µm²',count=4).legend(side='top',columns=2,font_size=i.pt(8))
    doc.add('areas-title',i.text('f  Cross-sectional areas on the output grid',size=i.pt(10)),row=9,column=0)
    doc.add('areas',p.build(),row=10,column=0)
    p = i.panel(110,55,x=(-16,16),y=(13000,32000))
    for index,(plane,section,color) in enumerate(zip(bank,sampled,PLANE_COLORS)):
        row = plane.shape_yx[0]//2
        runs=[];run=[]
        for col in range(plane.shape_yx[1]):
            if section.valid[row,col]:run.append(((col-(plane.shape_yx[1]-1)/2)*plane.spacing_yx[1],float(section.data[row,col])))
            elif run:runs.append(run);run=[]
        if run:runs.append(run)
        for number,run in enumerate(runs):
            if len(run)>1:p.line(run,stroke=color,stroke_width=.3,name=f'Plane {"AB"[index]}' if number==0 else None)
    p.axes(x='Distance along plane right axis / µm',y='Interpolated EM intensity',count=4).legend(side='top',columns=2,font_size=i.pt(8))
    doc.add('profiles-title',i.text('g  Intensities sampled along the marked lines',size=i.pt(10)),row=9,column=1)
    doc.add('profiles',p.build(),row=10,column=1)
    doc.add('method',i.text('Both planes: 80 nm output pixels; the same [17000, 26000] image window. Pale grey: outside source coverage. '
        'Images use trilinear sampling; source labels use nearest neighbours. Areas are sampled section estimates, not volumes. '
        'Overlapping source masks are counted separately. Output sampling does not increase acquisition resolution.',width=280,size=i.pt(8)),colspan=2)
    doc.add('attribution',i.text('COSEM / HHMI Janelia · jrc_hela-3 · CC BY 4.0 · Heinrich et al., Nature (2021). '
        'Automated source segmentations; no cell-membership or biological-replication inference.',width=280,size=i.pt(8)),colspan=2)
    return doc.compile(),evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/oblique-biology')
    parser.add_argument('--source-cache',type=Path,default=ROOT/'out/real-biology/source.n5')
    parser.add_argument('--blender',type=Path)
    args = parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    lock=fetch(args.source_cache);arrays,transform=load(args.source_cache)
    raw,masks,record,scene,rendered=build_scene(args.output/'scene',arrays,transform,blender=args.blender,camera_margin=1.40)
    figure,evidence=make_figure(raw,masks,record,rendered)
    print(figure.report(),flush=True)
    if any(d.severity=='error' for d in figure.diagnostics):raise RuntimeError(figure.report())
    figure.export(args.output,dpi=170)
    report=dict(schema='inklet.oblique-biology/0.1',inklet_version=i.__version__,dataset=record['dataset'],
        source_level=record['level'],source_grid=raw.report(),source_lock='examples/biology/organelle.lock.json',
        license=lock['license'],publication=lock['publication'],planes=evidence,
        scene_overlays=figure.metadata['rendering'].get('scene_overlays',[]),
        render=dict(blender=rendered.metadata['blender'],execution=rendered.metadata['execution'],
                    projection=rendered.metadata['projection'],pixels=rendered.metadata['pixels'],
                    width_mm=rendered.metadata['width_mm'],height_mm=rendered.metadata['height_mm'],
                    camera='Overview',cache_key=rendered.metadata['cache_key']))
    (args.output/'sections.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
