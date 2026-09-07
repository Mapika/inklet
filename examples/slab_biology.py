"""Real microscopy slab projections and a region shared with 3D and source measurements."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import inklet as i
from inklet.experimental.sections import SampledSection
from inklet.experimental.slabs import Slab
from inklet.experimental.regions import BoxRegion
from biology.data import fetch,load
from real_biology import ROOT,WINDOW,build_scene
from oblique_biology import planes,framed_section

COLOR='#b33279'
SLAB_COLOR='#2464b4'


def make_figure(raw,masks,record,rendered):
    plane=planes(record['nucleus']['centroid_xyz'])[0]
    slab=Slab(plane,thickness=3.2,samples=41)
    region=BoxRegion('ROI-1',(12,.4,17),(24,2.8,27),'um')
    projections={name:raw.project_slab(slab,reduction=name) for name in ('mean','min','max')}
    restricted=raw.project_slab(slab,reduction='mean',region=region)
    centre=raw.reslice(plane,kind='intensity')
    coverage=SampledSection(plane,raw,'intensity',projections['mean'].coverage,np.ones(plane.shape_yx,dtype=bool))
    measurements=[region.measure(masks[name],label=label) for name,label in [('nucleus',1),('mito',157),('mito',124)]]
    profile=[]
    for index in range(slab.samples):
        offset=slab.thickness*((index+.5)/slab.samples-.5)
        face=slab.face(offset);section=raw.reslice(face,kind='intensity')
        selected=section.valid & region.mask(face)
        profile.append(dict(offset=offset,pixels=int(selected.sum()),
                            mean_intensity=float(section.data[selected].mean()) if selected.any() else None))
    assert all(np.array_equal(p.counts,projections['mean'].counts) for p in projections.values())
    total=sum(p['pixels'] for p in profile)
    assert int(restricted.counts.sum())==total
    assert np.isclose(np.sum(restricted.data*restricted.counts)/total,
                      sum(p['mean_intensity']*p['pixels'] for p in profile if p['pixels'])/total)
    doc=i.document(width=300,columns=2,margin=8,gap=8)
    doc.add('title',i.text('Sections, slabs and one shared region',size=i.pt(21)),colspan=2)
    doc.add('subtitle',i.text('Real HeLa FIB-SEM · 3.2 µm slab · 41 depth samples · physical selection ROI-1',size=i.pt(10)),colspan=2)
    layers=[rendered.diagram]
    faces=[slab.face(offset) for offset in (-slab.thickness/2,slab.thickness/2)]
    if not all(rendered.project(p).in_frame for face in faces for p in face.corners):
        raise RuntimeError('Slab exceeds camera frame')
    for face in faces:
        layers.append(rendered.path3d([*face.corners,face.corners[0]],hidden='dash',depth_bias=.04,stroke=SLAB_COLOR,stroke_width=.5))
    for a,b in zip(faces[0].corners,faces[1].corners):
        layers.append(rendered.path3d([a,b],hidden='dash',depth_bias=.04,stroke=SLAB_COLOR,stroke_width=.5))
    for a,b in region.edges:
        layers.append(rendered.path3d([a,b],hidden='dash',depth_bias=.04,stroke=COLOR,stroke_width=.5))
    layers.append(rendered.annotate3d(region.upper_xyz,'ROI-1',side='e',clear=4,hidden='dash',depth_bias=.04,size=i.pt(10),text_fill=COLOR))
    doc.add('scene-title',i.text('a  Blue slab boundaries and magenta region in source coordinates',size=i.pt(11)),colspan=2)
    doc.add('scene',i.overlay(layers,align='origin'),colspan=2)
    doc.add('scene-note',i.text('Surface colors: purple nucleus, teal mitochondria, amber ER. Dashed 3D edges are depth-occluded.',size=i.pt(8)),colspan=2)
    pictures=[('section','b  Centre section',centre,WINDOW),('mean','c  Mean intensity / contributing samples',projections['mean'],WINDOW),
              ('min','d  Minimum intensity / darker structures',projections['min'],WINDOW),
              ('max','e  Maximum intensity / brighter structures',projections['max'],WINDOW),
              ('coverage','f  Source coverage / black 0, white 1',coverage,(0,1)),
              ('restricted','g  Mean restricted to ROI-1 at every depth',restricted,WINDOW)]
    for index,(name,title,sampled,window) in enumerate(pictures):
        row=5+2*(index//2);column=index%2
        image=sampled.diagram(width=126,window=window)
        image=i.overlay([image,region.outline(plane,width=126,stroke=COLOR,stroke_width=.5)],align='origin')
        doc.add(name+'-title',i.text(title,size=i.pt(10)),row=row,column=column)
        doc.add(name,framed_section(image,plane,SLAB_COLOR),row=row+1,column=column)
    names=['Nucleus 1','Mito 157','Mito 124'];values=[m['volume'] for m in measurements]
    p=i.panel(110,55,x=names,y=(0,max(values)*1.2))
    p.bars(names,values,bar_colors=['#9e8fb0','#0a666f','#0a666f'])
    p.axes(y='Selected source-label volume / µm³',count=4)
    doc.add('volumes-title',i.text('h  Source voxel measurements within ROI-1',size=i.pt(10)),row=11,column=0)
    doc.add('volumes',i.vstack([p.build(),i.text(' / '.join(f'{name}: {value:.3f}' for name,value in zip(names,values))+' µm³',width=126,size=i.pt(8))],gap=3),row=12,column=0)
    p=i.panel(110,55,x=(-1.6,1.6),y=(17000,27000))
    runs=[];run=[]
    for sample in profile:
        if sample['pixels']:run.append((sample['offset'],sample['mean_intensity']))
        elif run:runs.append(run);run=[]
    if run:runs.append(run)
    for run in runs:
        if len(run)>1:p.line(run,stroke=COLOR,stroke_width=.5)
    p.axes(x='Distance along slab normal / µm',y='Mean EM intensity in ROI-1',count=4)
    doc.add('profile-title',i.text('i  Intensity through depth / available ROI samples',size=i.pt(10)),row=11,column=1)
    doc.add('profile',p.build(),row=12,column=1)
    doc.add('method',i.text('All microscopy panels use the same [17000, 26000] window and 80 nm output pixels. '
        'Pale grey: no contributing samples. Magenta image outlines mark the central-plane box intersection, '
        'not the full slab selection footprint. Coverage is the fraction of requested depth samples inside the source. '
        'Mean intensity excludes unavailable samples. Source-label volumes use original s4 voxel centres inside ROI-1, '
        'independent of slab sampling; IDs remain exact. These are selected portions of labels, not complete organelles.',width=280,size=i.pt(8)),colspan=2)
    doc.add('attribution',i.text('COSEM / HHMI Janelia · jrc_hela-3 · CC BY 4.0 · Heinrich et al., Nature (2021). '
        'Automated source segmentations; masks can overlap. No cell-membership or biological-replication inference.',width=280,size=i.pt(8)),colspan=2)
    evidence=dict(slab=slab.report(),selection=region.report(),centre_section=centre.report(),
                  projections={name:p.report() for name,p in projections.items()},restricted=restricted.report(),
                  measurements=measurements,depth_profile=profile)
    return doc.compile(),evidence,projections,restricted


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/slab-biology')
    parser.add_argument('--source-cache',type=Path,default=ROOT/'out/real-biology/source.n5')
    parser.add_argument('--blender',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    lock=fetch(args.source_cache);arrays,transform=load(args.source_cache)
    raw,masks,record,scene,rendered=build_scene(args.output/'scene',arrays,transform,blender=args.blender,camera_margin=1.40)
    figure,evidence,projections,restricted=make_figure(raw,masks,record,rendered)
    print(figure.report(),flush=True)
    if figure.diagnostics:raise RuntimeError(figure.report())
    figure.export(args.output,dpi=170)
    np.savez_compressed(args.output/'projection-arrays.npz',**{name:p.data for name,p in projections.items()},
                        counts=projections['mean'].counts,restricted=restricted.data,restricted_counts=restricted.counts)
    report=dict(schema='inklet.slab-biology/0.1',inklet_version=i.__version__,dataset=record['dataset'],
        source_level=record['level'],source_grid=raw.report(),source_lock='examples/biology/organelle.lock.json',
        license=lock['license'],publication=lock['publication'],evidence=evidence,
        array_archive=dict(file='projection-arrays.npz',sha256=hashlib.sha256((args.output/'projection-arrays.npz').read_bytes()).hexdigest()),
        camera='Overview',scene_overlays=figure.metadata['rendering'].get('scene_overlays',[]),
        render={key:rendered.metadata[key] for key in ('blender','execution','projection','pixels','width_mm','height_mm','cache_key')})
    (args.output/'slabs.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
