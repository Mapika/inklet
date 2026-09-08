"""Complete native figure with paint/data revisions and compiled scene evidence."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import random
import inklet as i
from inklet.core import Diagram, Envelope, Rect, RectPrim, Style

ROOT=Path(__file__).resolve().parents[1]
CAPTION='''Compiled-scene review using original simulated data and artwork.
(a) A smooth response curve and a second supplied response. (b) A seeded point
cloud. (c) Supplied category values. (d) A vector-hatched section cropped by a
painted window. (e) A simple processing diagram. (f) A shaded native 3D solid.
The paint revision changes only the cloud colour; the data revision changes
only the category values. Axes, text, curves, clipping and compositing use the
same compiled scene for SVG, PDF and PNG. Revision counters describe rendering
compilation, separately from document layout and export. No measured data or
statistical inference is represented. MIT, Mark Marosi.
'''


def frame(node):
    node=node.centered()
    return Diagram(children=(node,),kind='scene-review-panel',
                   envelope_override=Envelope.from_rect(Rect(-37,-24,37,24)))


def categories(values):
    p=i.panel(58,32,x=('A','B','C','D'),y=(0,80))
    p.bars(('A','B','C','D'),values,fill='#245b8a')
    p.axes(y='Response / %')
    return frame(p.build())


def make_document():
    doc=i.preset('scientific.general').customize(width=190,margin=6,gap=10).document(columns=2,row_gap=8).letters()
    p=i.panel(58,32,x=(0,10),y=(-1.2,1.2))
    x=[k/20 for k in range(201)]
    p.line([(t,math.exp(-t/12)*math.sin(t*1.6)) for t in x],stroke='#245b8a')
    p.line([(t,.7*math.cos(t*1.2)) for t in x],stroke='#d17839')
    p.axes(x='Time / s',y='Response')
    doc.add('responses',frame(p.build()),row=0,column=0)
    rng=random.Random(481)
    cloud=i.place([((rng.gauss(0,10),rng.gauss(0,6)),i.marker('circle',1.4,stroke='none')) for _ in range(450)])
    cloud=i.window(cloud,Rect(-29,-16,29,16))
    cloud=frame(cloud)
    doc.add('cloud',cloud.styled(fill='#245b8a',fill_opacity=.5),row=0,column=1)
    doc.add('categories',categories((28,46,37,62)),row=1,column=0)
    section=i.paint(Diagram(prim=RectPrim(62,40,7),style=Style(stroke='#245b8a',stroke_width=.6)),
                    i.Hatch(color='#245b8a',background='#dce9ed',spacing=1.8,stroke=.22))
    section=i.window(section,Rect(-25,-16,25,16)).rotated(12)
    doc.add('section',frame(section),row=1,column=1)
    left=i.box('Input');middle=i.box('Model');right=i.box('Output')
    row=i.hstack((left,middle,right),gap=8)
    fig=i.figure(width=85);fig.add(row);fig.link(left,middle);fig.link(middle,right)
    doc.add('workflow',frame(fig.build()[0]),row=2,column=0)
    solid=i.solid('cube',width=35,style='shaded',color='#5897ad',view='isometric')
    doc.add('solid',frame(solid),row=2,column=1)
    return doc,cloud


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/render-scene-review')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    doc,cloud=make_document();records=[]
    previous=None;initial=None;initial_svg=None
    for stage in ('initial','paint','data'):
        if stage=='paint':doc.replace('cloud',cloud.styled(fill='#d17839',fill_opacity=.5))
        if stage=='data':doc.replace('categories',categories((34,51,42,70)))
        compiled=doc.compile()
        if any(d.severity=='error' for d in compiled.diagnostics):raise RuntimeError(compiled.report())
        path=args.output/stage;path.mkdir(exist_ok=True)
        compiled.save(path/'figure.svg',path/'figure.pdf',path/'figure.png')
        if initial is None:initial=compiled;initial_svg=compiled.to_svg()
        else:assert initial.to_svg()==initial_svg
        stats=dict(compiled.scene.stats)
        if previous is not None:
            assert stats['reused_nodes']>0 and stats['reused_geometry']>0
            assert compiled.scene.to_svg(text='embed')==i.compile_scene(compiled.root).to_svg(text='embed')
        records.append(dict(stage=stage,scene=stats,document=dict(compiled.stats),
                            changes=[dict(key=c.key,node_id=c.node_id,reasons=c.reasons) for c in compiled.scene.changes]))
        previous=compiled
    (args.output/'revisions.json').write_text(json.dumps(records,indent=2)+'\n')
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    print(json.dumps([dict(stage=r['stage'],scene=r['scene']) for r in records],indent=2))


if __name__=='__main__':main()
