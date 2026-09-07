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


CAPTION = """Per-component fluorescence intensities in a calibrated microscopy volume.
(a) Two-channel Allen Institute for Cell Science cells3d data on a plane tilted 10° from XY.
Membranes are cyan and nuclei magenta. Gold contours follow generated label pixels;
dashed gold indicates source or image coverage limits. Numeric badges retain component IDs.
White outlines ROI-1. (b) Central 128 by 128 sample zoom, retaining the overview's 260 nm sampling.
Scale bars, 10 µm. (c) Native nuclear mean ± population standard deviation of voxel intensities
for the six largest native components visible in a. Whiskers describe within-component
spread, not standard errors or confidence intervals. (d) Native mean membrane versus nuclear
intensity for all 17 generated components. (e) Section versus native nuclear mean for the
same 11 section-visible IDs; the dashed diagonal indicates equal means. (f) Percentage of
native labelled voxel centres inside ROI-1, in the same six-ID order as c. ROI-1 spans the
available Z depth; selection uses a half-open physical box, not an oblique image crop.

Native ZYX spacing is 290 / 260 / 260 nm. Labels use 0.5 µm Gaussian smoothing, nuclear
intensity greater than 12000, 6-connected components, and a minimum volume of 20 µm³.
These illustrative threshold components are not validated nuclei; touching structures can
merge and dim structures can be missed. Native boundary flags and section coverage edges
are recorded. Native statistics use original voxels; section statistics use trilinear
intensities and nearest-neighbour labels on the same plane. Display windows are 1200 to
11000 for membranes and 3500 to 22000 for nuclei, with unit weights and additive display RGB.
Windows do not alter measurements. Each component is one point in d and e, not an independent
biological replicate. No background correction, intensity calibration or colocalization is
inferred. Source data: Allen Institute for Cell Science / scikit-image cells3d, CC0.
Processing and figure: Mark Marosi, MIT. Source hashes, methods, counts and plotted values
accompany the figure.
"""


def write_caption(output):
    """Keep manuscript prose separate from the exported figure artwork."""
    (output/'caption.txt').write_text(CAPTION)
    latex=CAPTION.replace('µm³',r'\(\mu\mathrm{m}^3\)').replace('µm',r'\(\mu\mathrm{m}\)')
    latex=latex.replace('°',r'\(^{\circ}\)').replace('±',r'\(\pm\)')
    # A caption is one LaTeX paragraph; preserve line wrapping, remove blank lines.
    (output/'caption.tex').write_text('\\caption{'+latex.replace('\n\n','\n').strip()+'}\n')


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
    width=85
    overview,contours=outlined(composite(sampled).diagram(width=width),label_section,width,badges=True)
    overview=i.overlay([overview,region.outline(plane,width=width,stroke='white',stroke_width=.5)],align='origin')
    detailed,zoom_contours=outlined(composite(zoom_samples).diagram(width=width),zoom_labels,width,badges=True)
    doc=i.document(width=300,columns=3,margin=8,gap=7)
    keys=[i.hstack([i.box(width=2.5,height=2.5,pad=0,radius=0,fill=color,stroke='none'),
                    i.text(name,size=i.pt(8))],gap=2)
          for name,color in [('Membranes','#00d5d5'),('Nuclei','#f25cce')]]
    doc.add('legend',i.hstack(keys,gap=6),colspan=3)
    def panel(name,content,*,row,column):
        tagged=i.letters([content],start=chr(ord('a')+3*row+column))[0]
        doc.add(name,tagged,row=row+1,column=column)
    panel('overview',frame(overview,plane),row=0,column=0)
    panel('zoom',frame(detailed,zoom),row=0,column=1)
    names=[str(label) for label in ranked]
    points=[(str(label),n[label,'Nuclei']['mean']) for label in ranked]
    p=i.panel(70,65,x=names,y=(0,26000))
    p.errorbars(points,yerr=[n[label,'Nuclei']['std'] for label in ranked],cap=1.5,stroke=PURPLE,stroke_width=.5)
    p.scatter(points,size=2.4,color=PURPLE)
    p.axes(x='Generated component ID',y='Native nuclear intensity',count=4)
    panel('means',p.build(),row=0,column=2)
    cross=[(n[label,'Membranes']['mean'],n[label,'Nuclei']['mean']) for label in ids]
    p=i.panel(70,55,x=(1000,2500),y=(12000,26000))
    p.scatter(cross,size=2.2,color=TEAL)
    p.axes(x='Native membrane mean intensity',y='Native nuclear mean intensity',count=4)
    panel('channels',p.build(),row=1,column=0)
    paired=[(n[label,'Nuclei']['mean'],s[label,'Nuclei']['mean']) for label in visible]
    p=i.panel(70,55,x=(12000,26000),y=(12000,26000))
    p.line([(12000,12000),(26000,26000)],stroke='#abb6b7',stroke_width=.25,stroke_dash=(2,2))
    p.scatter(paired,size=2.2,color=PURPLE)
    p.axes(x='Native nuclear mean intensity',y='Section nuclear mean intensity',count=4)
    panel('paired',p.build(),row=1,column=1)
    fractions=[100*r[label,'Nuclei']['count']/n[label,'Nuclei']['count'] for label in ranked]
    p=i.panel(70,55,x=names,y=(0,100))
    p.bars(names,fractions,bar_colors=[GOLD]*len(names))
    p.axes(x='Generated component ID',y='Native labelled voxels inside ROI / %',count=4)
    panel('roi',p.build(),row=1,column=2)
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
    write_caption(args.output)
    for name,table in tables.items():
        (args.output/(name+'.csv')).write_text(table.to_csv())
        (args.output/(name+'.json')).write_text(table.to_json())
    np.savez_compressed(args.output/'sampled-arrays.npz',**{name:s.data for name,s in sampled.items()},
                        valid=label_section.valid,labels=label_section.data)
    report=dict(schema='inklet.label-intensities-example/0.1',inklet_version=i.__version__,source=source,evidence=evidence,
        exports={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.suffix in ('.csv','.npz') or p.name in ('caption.txt','caption.tex')})
    (args.output/'measurements.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
