"""Real fluorescence channels, exact vector label edges and calibrated measurements."""
import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
import inklet as i
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane
from inklet.experimental.slabs import Slab
from inklet.experimental.regions import BoxRegion
from inklet.experimental.channels import Channel,Composite
from biology.fluorescence import load

ROOT=Path(__file__).resolve().parents[1]
COLORS={'Membranes':'#00d5d5','Nuclei':'#f25cce'}
WINDOWS={'Membranes':(1200,11000),'Nuclei':(3500,22000)}
CONTOUR='#ffd166'


def candidate_labels(nuclei):
    sigma_um=.5;threshold=12000;minimum_volume=20
    smooth=ndi.gaussian_filter(nuclei.data.astype(float),sigma=np.array([sigma_um/d for d in nuclei.spacing_zyx]),mode='nearest')
    labels,count=ndi.label(smooth>threshold,structure=ndi.generate_binary_structure(3,1))
    sizes=np.bincount(labels.ravel())
    keep=np.flatnonzero(sizes*math.prod(nuclei.spacing_zyx)>=minimum_volume);keep=keep[keep>0]
    labels=np.where(np.isin(labels,keep),labels,0).astype('uint32')
    volume=Volume(labels,nuclei.spacing_zyx,nuclei.unit,nuclei.origin_xyz,
                  nuclei.source_id+' / generated threshold components')
    return volume,dict(method='Gaussian smoothing, fixed threshold, 6-connected components, size filtering',
        gaussian_sigma_um=sigma_um,boundary_mode='nearest',threshold=threshold,threshold_operator='>',
        minimum_volume_um3=minimum_volume,initial_components=count,retained_ids=[int(v) for v in keep],
        id_convention='SciPy scan-order IDs retained after filtering; no relabelling',
        validation='Illustrative processing only; no reference segmentation or accuracy assessment',
        components=[volume.measure(int(label)) for label in keep])


def composite(sampled):
    return Composite(tuple(Channel(name,sample,COLORS[name],WINDOWS[name]) for name,sample in sampled.items()),coverage='intersection')


def frame(image,plane,*,scale=10):
    layers=[i.box(width=image.width,height=image.height,pad=0,radius=0,fill='#e7ece9',stroke='none'),image]
    layers.append(i.box(width=image.width,height=image.height,pad=0,radius=0,fill='none',stroke='#172f32',stroke_width=.25))
    return i.vstack([i.overlay(layers,align='origin'),plane.scalebar(scale,width=image.width)],gap=3)


def outlined(base,labels,width,*,badges=False):
    layers=[base];reports=[]
    ids=[int(v) for v in np.unique(labels.data[labels.valid]) if v]
    for label in ids:
        contour=labels.contours(label);reports.append(contour.report())
        layers.append(contour.diagram(width=width,stroke=CONTOUR,stroke_width=.25,coverage='dash'))
        if badges:
            selected=(labels.data==label)&labels.valid
            # A maximum-distance sample is inside this mask, unlike some centroids.
            distance=ndi.distance_transform_edt(np.pad(selected,1),sampling=labels.plane.spacing_yx)[1:-1,1:-1]
            row,col=np.unravel_index(np.argmax(distance),selected.shape)
            at=labels.plane.project(labels.plane.world(int(row),int(col)),width=width)
            if distance[row,col]*width/labels.plane.extent[0]>=3:
                badge=i.box(i.text(str(label),size=i.pt(8),fill='#172f32'),
                            width=4.5,height=3.5,pad=.2,radius=.5,fill='white',stroke='none')
                layers.append(i.place([((at.x,at.y),badge)],origin=(0,0)))
                reports[-1]['badge_pixel_yx']=[int(row),int(col)]
    return i.overlay(layers,align='origin'),reports


def make_figure(volumes,labels,method):
    reference=volumes['Nuclei'];angle=math.radians(10)
    centre=reference.world(tuple((n-1)/2 for n in reference.data.shape))
    plane=Plane(centre,(1,0,0),(0,math.cos(angle),math.sin(angle)),(256,256),(.26,.26),'um')
    sampled={name:v.reslice(plane,kind='intensity') for name,v in volumes.items()}
    centre_composite=composite(sampled)
    slab=Slab(plane,8,32)
    projected={name:v.project_slab(slab,reduction='max') for name,v in volumes.items()}
    slab_composite=composite(projected)
    label_section=labels.reslice(plane,kind='labels')
    zoom=replace(plane,shape_yx=(128,128))
    zoom_sampled={name:v.reslice(zoom,kind='intensity') for name,v in volumes.items()}
    zoom_labels=labels.reslice(zoom,kind='labels')
    zoom_composite=composite(zoom_sampled)
    bounds=reference.report()['bounds_xyz']
    region=BoxRegion('ROI-1',(min(p[0] for p in zoom.corners),min(p[1] for p in zoom.corners),bounds[0][2]),
                     (max(p[0] for p in zoom.corners),max(p[1] for p in zoom.corners),bounds[1][2]),'um')
    width=87
    overview,contours=outlined(centre_composite.diagram(width=width),label_section,width,badges=True)
    detailed,zoom_contours=outlined(zoom_composite.diagram(width=width),zoom_labels,width,badges=True)
    overview=i.overlay([overview,region.outline(plane,width=width,stroke='white',stroke_width=.5)],align='origin')
    profile_row=plane.shape_yx[0]//2
    line=[plane.project(plane.world(profile_row,c),width=width) for c in (0,255)]
    marked=i.overlay([centre_composite.diagram(width=width),
        i.polyline([(p.x,p.y) for p in line],stroke='white',stroke_width=.25,stroke_dash=(1,1))],align='origin')
    pictures=[('membrane','a  Membranes / centre section',sampled['Membranes'].diagram(width=width,window=WINDOWS['Membranes']),plane),
              ('nuclei','b  Nuclei / centre section',sampled['Nuclei'].diagram(width=width,window=WINDOWS['Nuclei']),plane),
              ('composite','c  Composite / marked profile line',marked,plane),
              ('slab','d  8 µm maximum-intensity slab',slab_composite.diagram(width=width),plane),
              ('contours','e  Threshold component boundaries',overview,plane),
              ('zoom','f  ROI-1 / same 260 nm sampling',detailed,zoom)]
    doc=i.document(width=300,columns=3,margin=8,gap=7)
    doc.add('title',i.text('Fluorescence signals and exact label boundaries',size=i.pt(20)),colspan=3)
    doc.add('subtitle',i.text('Real two-channel microscopy · calibrated oblique sections · vector contours · transparent processing',size=i.pt(10)),colspan=3)
    doc.add('legend',centre_composite.legend(),colspan=3)
    doc.add('legend-note',i.text('Channel keys show display windows and weights. Gold: sampled label edges. Dashed gold: coverage limits.',size=i.pt(8)),colspan=3)
    for index,(name,title,image,geometry) in enumerate(pictures):
        row=4+2*(index//3);col=index%3
        doc.add(name+'-title',i.text(title,size=i.pt(9)),row=row,column=col)
        doc.add(name,frame(image,geometry),row=row+1,column=col)
    p=i.panel(72,50,x=(-33.28,33.28),y=(0,45000))
    profiles={}
    for name,s in sampled.items():
        values=s.data[profile_row];valid=s.valid[profile_row]
        profiles[name]=dict(row=profile_row,values=values.tolist(),valid=valid.tolist())
        runs=[];run=[]
        for column,(value,available) in enumerate(zip(values,valid)):
            if available:run.append(((column-127.5)*.26,float(value)))
            elif run:runs.append(run);run=[]
        if run:runs.append(run)
        for index,run in enumerate(runs):
            if len(run)>1:p.line(run,stroke=COLORS[name],stroke_width=.5,name=name if index==0 else None)
    p.axes(x='Distance along plane right / µm',y='Unwindowed intensity',count=4)
    doc.add('profile-title',i.text('g  Raw intensity along the marked line',size=i.pt(9)),row=8,column=0)
    doc.add('profile',p.build(),row=9,column=0)
    ranked=sorted(contours,key=lambda c:c['area']['area'],reverse=True)[:6]
    names=[str(c['label'])+('*' if c['coverage_segments'] else '') for c in ranked];values=[c['area']['area'] for c in ranked]
    p=i.panel(72,50,x=names,y=(0,max(values)*1.2))
    p.bars(names,values,bar_colors=['#b88627']*len(names))
    p.axes(x='Generated component ID',y='Sampled section area / µm²',count=4)
    doc.add('area-title',i.text('h  Six largest sampled component areas',size=i.pt(9)),row=8,column=1)
    doc.add('areas',i.vstack([p.build(),i.text('* Reaches image/source coverage limit',size=i.pt(7))],gap=2),row=9,column=1)
    p=i.panel(72,50,x=(0,65536),y=(0,45));histograms={}
    for name,s in sampled.items():
        counts,edges=np.histogram(s.data[s.valid],bins=32,range=(0,65536))
        percentages=counts/len(s.data[s.valid])*100
        p.line(list(zip(((edges[:-1]+edges[1:])/2).tolist(),percentages.tolist())),stroke=COLORS[name],stroke_width=.5)
        histograms[name]=dict(edges=edges.tolist(),counts=counts.tolist(),denominator=int(s.valid.sum()))
    p.axes(x='Unwindowed intensity / 16-bit range',y='Valid samples per bin / %',count=4)
    doc.add('histogram-title',i.text('i  Full-section intensity distributions',size=i.pt(9)),row=8,column=2)
    doc.add('histograms',p.build(),row=9,column=2)
    doc.add('method',i.text('Centre plane: 10° tilt from XY; source spacing ZYX 290 / 260 / 260 nm. '
        'Slab: 8 µm, 32 midpoint samples, trilinear intensity, per-channel maxima. '
        'Center and zoom retain the same output sampling; zoom does not add resolution. '
        'Labels are generated here: 0.5 µm Gaussian smoothing, intensity >12000, 6-connected components, '
        'minimum volume 20 µm³. IDs persist after size filtering. These components are not validated nuclei; '
        'touching structures can merge. Areas are sampled section estimates, not 3D volumes. '
        'Channel overlap in an RGB composite is not a colocalization result. '
        f"RGB display clipping: centre {100*centre_composite.report()['rgb_clipped_pixels']/65536:.1f}%; slab {100*slab_composite.report()['rgb_clipped_pixels']/65536:.1f}%.",width=284,size=i.pt(8)),colspan=3)
    doc.add('attribution',i.text('Allen Institute for Cell Science / scikit-image cells3d · source CC0. '
        'Inklet example processing and figure: Mark Marosi. No ground-truth or biological-replication claim.',width=284,size=i.pt(8)),colspan=3)
    evidence=dict(centre=centre_composite.report(),slab=slab_composite.report(),zoom=zoom_composite.report(),
                  region=region.report(),segmentation=method,contours=contours,zoom_contours=zoom_contours,
                  profiles=profiles,profile_world_endpoints=[plane.world(profile_row,0),plane.world(profile_row,255)],
                  histograms=histograms,ranked_area_labels=[c['label'] for c in ranked])
    return doc.compile(),evidence,sampled,label_section


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/fluorescence-biology')
    parser.add_argument('--source-cache',type=Path,default=ROOT/'out/fluorescence-biology/source')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    volumes,source=load(args.source_cache)
    labels,method=candidate_labels(volumes['Nuclei'])
    figure,evidence,sampled,label_section=make_figure(volumes,labels,method)
    print(figure.report(),flush=True)
    if figure.diagnostics:raise RuntimeError(figure.report())
    figure.export(args.output,dpi=190)
    np.savez_compressed(args.output/'sampled-arrays.npz',**{name:s.data for name,s in sampled.items()},
                        valid=label_section.valid,labels=label_section.data)
    report=dict(schema='inklet.fluorescence-biology/0.1',inklet_version=i.__version__,source=source,evidence=evidence,
                array_archive=dict(file='sampled-arrays.npz',sha256=hashlib.sha256((args.output/'sampled-arrays.npz').read_bytes()).hexdigest()))
    (args.output/'channels.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
