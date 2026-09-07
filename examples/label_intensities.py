"""Real microscopy: reusable TIFF import and per-label intensity tables."""
import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import inklet as i
from inklet.experimental.sections import Plane
from inklet.experimental.regions import BoxRegion
from inklet.experimental.measurements import measure_labels
from biology.fluorescence import load
from fluorescence_biology import candidate_labels, composite, outlined, frame

ROOT=Path(__file__).resolve().parents[1]
INK='#172f32';PURPLE='#a23a8d';TEAL='#137b83';GOLD='#a97620'


def make_figure(volumes,labels,method):
    reference=volumes['Nuclei'];angle=math.radians(10)
    centre=reference.world(tuple((n-1)/2 for n in reference.data.shape))
    plane=Plane(centre,(1,0,0),(0,math.cos(angle),math.sin(angle)),(256,256),(.26,.26),'um')
    sampled={name:v.reslice(plane,kind='intensity') for name,v in volumes.items()}
    label_section=labels.reslice(plane,kind='labels')
    zoom=replace(plane,shape_yx=(128,128))
    zoom_samples={name:v.reslice(zoom,kind='intensity') for name,v in volumes.items()}
    zoom_labels=labels.reslice(zoom,kind='labels')
    bounds=reference.report()['bounds_xyz']
    region=BoxRegion('ROI-1',(min(p[0] for p in zoom.corners),min(p[1] for p in zoom.corners),bounds[0][2]),
                     (max(p[0] for p in zoom.corners),max(p[1] for p in zoom.corners),bounds[1][2]),'um')
    native=measure_labels(labels,volumes)
    section=measure_labels(label_section,sampled)
    ids=[r['label'] for r in native.rows if r['channel']=='Nuclei']
    roi=measure_labels(labels,volumes,label_ids=ids,region=region)
    def index(table):return {(r['label'],r['channel']):r for r in table.rows}
    n,s,r=index(native),index(section),index(roi)
    visible=[label for label in ids if (label,'Nuclei') in s]
    ranked=sorted(visible,key=lambda label:n[label,'Nuclei']['measure'],reverse=True)[:6]
    width=87
    overview,contours=outlined(composite(sampled).diagram(width=width),label_section,width,badges=True)
    overview=i.overlay([overview,region.outline(plane,width=width,stroke='white',stroke_width=.5)],align='origin')
    detailed,zoom_contours=outlined(composite(zoom_samples).diagram(width=width),zoom_labels,width,badges=True)
    doc=i.document(width=300,columns=3,margin=8,gap=7)
    doc.add('title',i.text('From microscopy labels to quantitative plots',size=i.pt(20)),colspan=3)
    doc.add('subtitle',i.text('One calibrated TIFF · persistent component IDs · source intensities · reusable CSV and JSON tables',size=i.pt(10)),colspan=3)
    doc.add('legend',composite(sampled).legend(),colspan=3)
    doc.add('key',i.text('Gold: sampled label edges; dashed gold: coverage limits. White box: ROI-1. Charts use unwindowed intensities.',size=i.pt(8)),colspan=3)
    def panel(name,title,content,row,col):
        doc.add(name+'-title',i.text(title,size=i.pt(9)),row=row,column=col)
        doc.add(name,content,row=row+1,column=col)
    panel('overview','a  Generated IDs on a 10° oblique section',frame(overview,plane),4,0)
    panel('zoom','b  ROI-1 / same 260 nm sampling',frame(detailed,zoom),4,1)
    names=[str(label) for label in ranked]
    points=[(str(label),n[label,'Nuclei']['mean']) for label in ranked]
    p=i.panel(72,65,x=names,y=(0,26000))
    p.errorbars(points,yerr=[n[label,'Nuclei']['std'] for label in ranked],cap=1.5,stroke=PURPLE,stroke_width=.5)
    p.scatter(points,size=2.4,color=PURPLE)
    p.axes(x='Generated component ID',y='Native nuclear intensity',count=4)
    panel('means','c  Native mean ± within-component SD',i.vstack([p.build(),i.text('Six largest native components visible in a.',size=i.pt(7)),
        i.text('SD describes voxel spread; it is not uncertainty.',size=i.pt(7))],gap=3),4,2)
    cross=[(n[label,'Membranes']['mean'],n[label,'Nuclei']['mean']) for label in ids]
    p=i.panel(72,55,x=(1000,2500),y=(12000,26000))
    p.scatter(cross,size=2.2,color=TEAL)
    p.axes(x='Native membrane mean intensity',y='Native nuclear mean intensity',count=4)
    panel('channels','d  Two signals / all 17 generated components',p.build(),6,0)
    paired=[(n[label,'Nuclei']['mean'],s[label,'Nuclei']['mean']) for label in visible]
    p=i.panel(72,55,x=(12000,26000),y=(12000,26000))
    p.line([(12000,12000),(26000,26000)],stroke='#abb6b7',stroke_width=.25,stroke_dash=(2,2))
    p.scatter(paired,size=2.2,color=PURPLE)
    p.axes(x='Native nuclear mean intensity',y='Section nuclear mean intensity',count=4)
    panel('paired','e  The same 11 IDs / section versus volume',p.build(),6,1)
    fractions=[100*r[label,'Nuclei']['count']/n[label,'Nuclei']['count'] for label in ranked]
    p=i.panel(72,55,x=names,y=(0,100))
    p.bars(names,fractions,bar_colors=[GOLD]*len(names))
    p.axes(x='Generated component ID',y='Native labelled voxels inside ROI / %',count=4)
    panel('roi','f  How much of each component is inside ROI-1?',p.build(),6,2)
    doc.add('method',i.text('Labels: Gaussian σ = 0.5 µm, nuclear intensity >12000, 6-connected components, minimum volume 20 µm³. '
        'These are illustrative threshold components, not validated nuclei. Native statistics use original voxels; section statistics '
        'use trilinear intensities and nearest-neighbour labels on the same plane. Each component is one point in d and e, '
        'not an independent biological replicate. Dashed diagonal in e indicates equal means. '
        'ROI-1 is a physical XY box through the available Z depth; f selects native voxel centres, not a rectangular crop of the oblique image. '
        'Display windows do not alter statistics. No background correction, colocalization or intensity calibration is inferred.',width=284,size=i.pt(8)),colspan=3)
    doc.add('credit',i.text('Allen Institute for Cell Science / scikit-image cells3d, CC0. Calibrated spacing ZYX: 290 / 260 / 260 nm. '
        'Inklet processing and figure: Mark Marosi. Source hashes, boundary flags, counts, methods and plotted values accompany the figure.',width=284,size=i.pt(8)),colspan=3)
    evidence=dict(plane=plane.report(),region=region.report(),segmentation=method,
        contours=contours,zoom_contours=zoom_contours,display=composite(sampled).report(),
        tables=dict(native=native.report(),section=section.report(),roi=roi.report()),
        plots=dict(ranked_ids=ranked,visible_ids=visible,all_ids=ids,cross_channel_means=cross,
                   native_section_means=paired,roi_percent=fractions),
        interpretation='Threshold components from one image; no reference labels, biological replication or inferred colocalization')
    return doc.compile(),evidence,dict(native=native,section=section,roi=roi),sampled,label_section


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/label-intensities')
    parser.add_argument('--source-cache',type=Path,default=ROOT/'out/fluorescence-biology/source')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    volumes,source=load(args.source_cache)
    labels,method=candidate_labels(volumes['Nuclei'])
    figure,evidence,tables,sampled,label_section=make_figure(volumes,labels,method)
    print(figure.report(),flush=True)
    if figure.diagnostics:raise RuntimeError(figure.report())
    figure.export(args.output,dpi=190)
    for name,table in tables.items():
        (args.output/(name+'.csv')).write_text(table.to_csv())
        (args.output/(name+'.json')).write_text(table.to_json())
    np.savez_compressed(args.output/'sampled-arrays.npz',**{name:s.data for name,s in sampled.items()},
                        valid=label_section.valid,labels=label_section.data)
    report=dict(schema='inklet.label-intensities-example/0.1',inklet_version=i.__version__,source=source,evidence=evidence,
        exports={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.suffix in ('.csv','.npz')})
    (args.output/'measurements.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
