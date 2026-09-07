"""Bounded architecture modules and automatic connector-label placement."""
import argparse
import json
from pathlib import Path
import inklet as i

ROOT=Path(__file__).resolve().parents[1]
CAPTION='''Diagram engine review with original illustrative workflows.
(a) An asynchronous service architecture. Module labels wrap within 34 mm;
connectors attach to measured ports. A request enters validation, is queued,
processed and stored; monitoring and audit services receive separate events.
(b) Three labelled channels between two services. Label positions are selected
automatically against all shafts, node artwork and other label plates.
These diagrams describe an illustrative system, not a deployed service.
Recipe and artwork: MIT, Mark Marosi.
'''


def channels():
    a=i.box('Gateway',width=24,height=16,fill='#e1edf4',stroke='#307399')
    b=i.box('Worker',width=24,height=16,fill='#e1edf4',stroke='#307399').translated(110,0)
    fig=i.figure(width=155,margin=4)
    fig.add(i.Diagram(children=(a,b)))
    for port,label,color in [(-2,'request','#307399'),(0,'progress','#666666'),(2,'complete','#a05a28')]:
        fig.link(a,b,port=port,target_port=port,label=i.text(label,size=2.5,text_fill=color),stroke=color,
                 arrow_size=1.2)
    return fig


def architecture():
    scene=i.composition(184,88)
    labels=[('client','Client applications'),('validate','Request validation'),
            ('worker','Background processing'),('store','Results storage'),
            ('cache','Response cache'),('queue','Persistent job queue'),
            ('monitor','Service monitoring'),('audit','Immutable audit log')]
    for index,(name,label) in enumerate(labels):
        scene.add(name,i.module(label,min_width=34,max_width=34,min_height=16,
                  text_style={'size':3},box_style={'fill':'#e1edf4' if index<4 else '#f6ecdf',
                  'stroke':'#307399' if index<4 else '#a36e39','corner_radius':1}),
                  x=4+(index%4)*46,y=8+(index//4)*56)
    for a,b,label in [('client:out','validate:in',None),('worker:out','store:in',None),
                      ('validate:s','queue:n','enqueue'),
                      ('worker:s','monitor:n','metrics'),('store:s','audit:n','record'),
                      ('client:s','cache:n','lookup')]:
        scene.link(a,b,label=label,route='avoid',corner=1)
    scene.link('cache:out','queue:in',label='miss',route='straight')
    qx,qy=scene.point('queue','out')
    wx,wy=scene.point('worker','in')
    scene.link('queue:out','worker:in',route='orthogonal',corner=1,
               waypoints=[(qx+6,qy),(wx-6,wy)])
    return scene


def make_document():
    doc=i.preset('scientific.general').customize(width=200,margin=6).document(row_gap=10).letters()
    doc.add('architecture',architecture(),row=0,align='nw')
    doc.add('channels',i.component(lambda:channels().build()[0]),row=1,align='nw')
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/diagram-review')
    parser.add_argument('--labels-only',action='store_true',help='Export a specimen compatible with the previous engine')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.labels_only:
        channels().save(args.output/'labels.svg',args.output/'labels.pdf',args.output/'labels.png')
        return
    compiled=make_document().compile()
    print(compiled.report())
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    (args.output/'report.json').write_text(json.dumps(dict(version=i.__version__,
        diagnostics=[dict(code=d.code,severity=d.severity) for d in compiled.diagnostics]),indent=2)+'\n')


if __name__=='__main__':main()
