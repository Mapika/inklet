"""Linked calibrated label images and source-pixel measurements; simulated data."""
import argparse
import json
import math
from pathlib import Path

from inklet.experimental.browser import BrowserFigure,IntervalView,LabelImageView,RevisionOption,ScatterView
from inklet.experimental.measurement import LabelImage
from inklet.experimental.selection import SelectionState

REVISIONS=('original','calibrated','updated','relabeled')
CREDIT=('Original simulated intensity image and labels by Mark Marosi · MIT material. '
        'These shapes are a visualization fixture, not observed cells or an inferred segmentation. '
        'Area counts labeled source pixels using the declared calibration. Mean and minimum–maximum '
        'use nonmissing labeled intensities; ranges are not confidence intervals. '
        'The source image stays visible during filtering; region outlines, picking and plot marks follow visibility.')


def make_image(revision='original'):
    if revision not in REVISIONS:raise ValueError('unknown image revision')
    centers=[(8,9,5,6),(24,9,6,5),(40,9,5,6),(55,9,5,6),
             (9,29,6,5),(24,29,6,6),(40,29,5,6),(55,29,5,5)]
    intensity=[];labels=[]
    for y in range(40):
        intensity_row=[];label_row=[]
        for x in range(64):
            label=0
            for n,(cx,cy,rx,ry) in enumerate(centers,1):
                radius=((x-cx)/rx)**2+((y-cy)/ry)**2
                inside=radius<=1
                if n==3:inside=inside and radius>=.25
                if n==7:inside=((x-37)/2)**2+((y-29)/4)**2<=1 or ((x-43)/2)**2+((y-29)/4)**2<=1
                if inside:label=n;break
            value=round(4+1.4*math.sin(x/5)+.04*y,2)
            if label:
                cx,cy,_,_=centers[label-1]
                value=round(12+label*8+(x-cx)*.8+(y-cy)*1.1+2*math.sin(x/4),2)
                if revision=='updated' and label==2:value+=5
                if revision!='updated' and (label==8 or (label==5 and (x+y)%17==0)):value=None
            intensity_row.append(value);label_row.append(0 if revision=='relabeled' and label==8 else label)
        intensity.append(intensity_row);labels.append(label_row)
    regions=[(f'region-{n}',n) for n in range(1,9) if revision!='relabeled' or n!=8]
    return LabelImage(intensity,labels,regions,(.6,.4) if revision=='calibrated' else (.4,.4),'um')


def make_views(image):
    unit='µm' if image.unit=='um' else image.unit
    return [LabelImageView('intensity',image,(0,100),5),
            LabelImageView('labels',image,(0,100),5,mode='labels'),
            IntervalView('intensities','label','mean',(.4,8.6),(0,90),x_label='Region label',y_label='Intensity / a.u.',
                         lower='minimum',upper='maximum',
                         interval_label='Observed pixel minimum–maximum; not a confidence interval',color='#4774a0'),
            ScatterView('area','area','mean',(0,35),(0,90),x_label=f'Labeled area / {unit}²',
                        y_label='Mean intensity / a.u.',radius_mm=.9)]


def make_scene(revision='original',*,width=210,image=None):
    image=make_image(revision) if image is None else image
    return BrowserFigure(image.table('scientific-regions'),make_views(image),width=width,columns=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/v4-scientific'))
    parser.add_argument('--revision',choices=REVISIONS,default='original')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--rebase-state',type=Path,help='Original 210 mm state to reconcile against the chosen image')
    parser.add_argument('--json',type=Path,help='Replacement LabelImage JSON; input.json is the template')
    parser.add_argument('--missing',choices=('error','drop'),default='error')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.state and args.rebase_state:parser.error('choose state or rebase-state')
    if args.json and args.revision!='original':parser.error('choose a built-in revision or JSON replacement')
    image=LabelImage.from_dict(json.loads(args.json.read_text())) if args.json else make_image(args.revision)
    if image.unit!='um' or image.extent[0]<5:parser.error('this recipe uses µm calibration and a 5 µm scale bar; adapt make_views for other units/extents')
    scene=make_scene(image=image);original=make_scene()
    if args.rebase_state:
        revision=original.replace_data(scene.table,views=make_views(image),
            state=json.loads(args.rebase_state.read_text()),missing=args.missing)
        state=revision.state();report=revision.report()
    else:
        state=json.loads(args.state.read_text()) if args.state else scene.state(
            SelectionState.for_table(scene.table,selected=['region-3'] if 'region-3' in scene.table.row_ids else []))
        report=original.replace_data(scene.table,views=make_views(image)).report()
    scene.validate_state(state);args.output.mkdir(parents=True,exist_ok=True)
    alternatives=[] if args.json else [RevisionOption(name.capitalize(),make_scene(name),CREDIT)
                                       for name in REVISIONS if name!=args.revision]
    credit=(f'User-supplied image and labels from {args.json.name}; source digest {image.digest}. '
            'Area and intensity summaries use labeled source pixels. The ranges are observed minimum–maximum, '
            'not confidence intervals. Source image remains visible when region overlays are filtered.' if args.json else CREDIT)
    (args.output/'index.html').write_text(scene.to_html(title='Calibrated region measurements · '+('supplied data' if args.json else 'simulated image'),
        state=state,attribution=credit,revision_label='Supplied image' if args.json else args.revision.capitalize(),
        revisions=alternatives),encoding='utf-8')
    source=dict(intensity=image.intensity,labels=image.labels,spacing_yx=image.spacing_yx,unit=image.unit,
                regions=[dict(id=key,label=label) for key,label in image.regions])
    for name,value in [('view.json',state),('revision.json',report),('input.json',source),
                       ('measurements.json',dict(scene.table.columns)),('image.json',image.report()|dict(credit=credit))]:
        (args.output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (args.output/'figure.svg').write_text(scene.to_svg(state),encoding='utf-8')
    for width in (210,170):
        export=scene.replace_data(scene.table,state=state,width=width)
        svg=args.output/f'figure-{width}mm.svg';svg.write_text(export.figure.to_svg(export.state()),encoding='utf-8')
        (args.output/f'view-{width}mm.json').write_text(json.dumps(export.state(),indent=2)+'\n')
        if args.render:
            from inklet.render.preview import svg_png,svg_pdf
            svg_png(svg,svg.with_suffix('.png'),dpi=150);svg_pdf(svg,svg.with_suffix('.pdf'))
    print(args.output/'index.html')


if __name__=='__main__':main()
