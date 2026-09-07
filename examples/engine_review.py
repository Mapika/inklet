"""Dense plots, transparent ink and nested fixed drawings in one document."""
import argparse
import json
import math
from pathlib import Path
import random

import inklet as i

ROOT = Path(__file__).resolve().parents[1]
CAPTION = '''Rendering and layout checks with original simulated data.
(a) 30,000 normally distributed points (seed 2026), painted in input order at
300 dpi with marker fill opacity 0.3; axes remain vector. (b) A damped sinusoid
with a supplied interval of fixed half-width 0.15, not a fitted confidence interval.
(c) Two outlined blocks and italic text with a halo, composited together at
60 percent opacity. Thick strokes and the text halo extend beyond their layout
envelopes. (d) Fixed-size blocks with unequal heights in a nested grid, including
automatically reserved panel-letter space. No text or stroke is scaled to fit.
Recipe and figure: MIT, Mark Marosi.
'''


def transparent_ink():
    boxes = i.hstack([
        i.box('Input',width=24,height=18,fill='#d5e9f4',stroke='#0072b2',stroke_width=2),
        i.box('Output',width=24,height=18,fill='#f9ddca',stroke='#d55e00',stroke_width=2),
    ],gap=10)
    label = i.text('f(x)',size=8,font_style='italic',halo=1.6,halo_color='#bddbee',text_fill='#222222')
    return i.vstack([boxes,label],gap=10).styled(opacity=.6)


def make_document():
    doc = i.preset('scientific.general').customize(width=200,margin=6,gap=10).document(columns=2).letters()
    rng = random.Random(2026)
    points = [(rng.gauss(0,1),rng.gauss(0,1)) for _ in range(30000)]
    p = i.plot_spec(height=44,x=(-4,4),y=(-4,4))
    p.scatter(points,raster=True,size=.6,color='#0072b2',fill_opacity=.3,dpi=300).axes(x='x',y='y')
    doc.add('cloud',p,row=0,column=0)
    xs = [j/20 for j in range(121)]
    ys = [math.exp(-x/4)*math.sin(2*x) for x in xs]
    p = i.plot_spec(height=44,x=(0,6),y=(-1.2,1.2))
    p.band(xs,[y-.15 for y in ys],[y+.15 for y in ys],fill='#0072b2',fill_opacity=.18)
    p.line(list(zip(xs,ys)),stroke='#0072b2').axes(x='Time / s',y='Response')
    doc.add('signal',p,row=0,column=1)
    doc.add('transparency',i.component(transparent_ink),row=1,column=0,align='nw')
    nested = i.subfigure(columns=2,gap=6,row_gap=6).letters(start='i')
    for name,label,height,row,column in [('input','Input',30,0,0),('model','Model',18,0,1),('output','Output',12,1,0)]:
        nested.add(name,i.component(i.box,label,width=26,height=height,fill='#e8eef2'),row=row,column=column,align='nw')
    doc.add('nested',nested,row=1,column=1,align='nw')
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/engine-review')
    parser.add_argument('--quality-only',action='store_true',help='Export the identical transparency specimen on either engine revision')
    args = parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.quality_only:
        node = transparent_ink()
        options = dict(margin=5,background='white',text='embed')
        (args.output/'transparency.svg').write_text(i.to_svg(node,**options))
        (args.output/'transparency.pdf').write_bytes(i.to_pdf(node,**options))
        return
    compiled = make_document().compile()
    print(compiled.report(),flush=True)
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    (args.output/'report.json').write_text(json.dumps(dict(version=i.__version__,
        width_mm=compiled.root.width,height_mm=compiled.root.height,
        stats=dict(compiled.stats),diagnostics=[dict(code=d.code,severity=d.severity) for d in compiled.diagnostics]),indent=2)+'\n')


if __name__=='__main__':main()
