"""Dense vector lines and measured axis typography, with external captions."""
import argparse
import json
import math
from pathlib import Path
import inklet as i

ROOT=Path(__file__).resolve().parents[1]
CAPTION='''Plot rendering review with original simulated data.
(a) A 100,001-sample signal with sinusoidal components and a narrow Gaussian
peak, reduced for vector rendering at a tolerance of 0.02 mm. (b) The selected
4.23--4.27 s interval, showing every original sample in grey and the reduced
line in blue; the tolerance is recomputed at the enlarged physical scale.
(c) Illustrative frequency-response values with explicit axis typography and
matching grid selection. (d) A simulated matrix with an independently sized
colorbar label and tick labels. Simplification changes rendering geometry only;
endpoints and global coordinate extrema are retained. No fitted uncertainty or
experimental measurements are shown. Recipe and artwork: MIT, Mark Marosi.
'''


def signal(count=100001):
    return [(10*k/(count-1),math.sin(4*10*k/(count-1))+.25*math.cos(11*10*k/(count-1))
             +3*math.exp(-((10*k/(count-1)-4.25)/.002)**2)) for k in range(count)]


def axes_specimen():
    p=i.panel(60,36,x=(1000,9000),y=(0,1))
    p.line([(1000,.1),(4000,.6),(9000,.85)],stroke='#176b9b')
    p.axes(x='Frequency / Hz',y='Response',font_size='11pt',font_weight='bold')
    f=i.figure(width=110,margin=5);f.add(p.build());return f


def make_document():
    doc=i.preset('scientific.general').customize(width=200,margin=6,gap=12).document(columns=2,row_gap=10).letters()
    points=signal()
    p=i.plot_spec(height=44,x=(0,10),y=(-1.5,2.7),clip=True)
    p.line(points,simplify=.02,stroke='#176b9b')
    p.axes(x='Time / s',y='Response')
    doc.add('signal',p,row=0,column=0)
    detail=[pair for pair in points if 4.23<=pair[0]<=4.27]
    p=i.plot_spec(height=44,x=(4.23,4.27),y=(-1.5,2.7),clip=True)
    p.line(detail,name='Original',stroke='#777777',stroke_width=.6)
    p.line(detail,name='Reduced',simplify=.02,stroke='#176b9b',stroke_width=.18)
    p.axes(x='Time / s',y='Response',count=4).legend(side='bottom')
    doc.add('detail',p,row=0,column=1)
    p=i.plot_spec(height=44,x=(1000,9000),y=(0,1))
    p.line([(1000,.1),(2500,.35),(4000,.6),(6500,.77),(9000,.85)],stroke='#176b9b')
    options=dict(count=8,font_size='9pt',font_weight='bold')
    p.grid(y=False,x_options=options)
    p.axis('bottom',label='Frequency / Hz',**options)
    p.axis('left',label='Response',tick_font_size='8pt',label_font_size='9pt')
    doc.add('typography',p,row=1,column=0)
    p=i.plot_spec(height=44,x=(0,10),y=(0,6))
    field=[[math.sin((x+.5)/3)*math.cos((y+.5)/2) for x in range(10)] for y in range(6)]
    p.matrix(field,ramp=i.ramp(['#eff4ef','#28756a']),scale=i.linear((-1,1)))
    p.axes(x='Position / mm',y='Position / mm')
    p.colorbar(label='Signal',tick_font_size='8pt',label_font_size='9pt',ticks=[-1,0,1])
    doc.add('field',p,row=1,column=1)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/plot-engine-review')
    parser.add_argument('--axes-only',action='store_true',help='Export the same font-override specimen on either revision')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.axes_only:
        axes_specimen().save(args.output/'axes.svg',args.output/'axes.pdf',args.output/'axes.png');return
    compiled=make_document().compile()
    print(compiled.report(),flush=True)
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    reductions=[node.notes['line_simplification'] for node in compiled.root.walk() if 'line_simplification' in node.notes]
    (args.output/'report.json').write_text(json.dumps(dict(version=i.__version__,reductions=reductions,
        diagnostics=[dict(code=d.code,severity=d.severity) for d in compiled.diagnostics]),indent=2)+'\n')


if __name__=='__main__':main()
