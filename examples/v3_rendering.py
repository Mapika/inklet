"""Blender scene views, object annotations, vector brushes and live plots.

Run `python tools/v3_showcase.py` to create the reusable .blend and export this
figure. The Blender authoring script is examples/blender/lab_scene.py.
"""
from pathlib import Path
import inklet as i
from inklet.core import Diagram, RectPrim

ROOT=Path(__file__).resolve().parents[1]


def scene_panel(path,camera,*,width,height,bindings=None):
    raw=i.blend_scene(path,width=90,height=64.8,camera=camera,
        scene='Laboratory',engine='CYCLES',samples=48,dpi=310,
        landmarks={'connector':{'object':'Connector','point':[0,0,.1]},
                   'controller':'Controller'},bindings=bindings or {})
    # Render at a fixed print resolution; layout may reuse and scale these pixels.
    rendered=raw.scaled(width/90)
    tip=i.resolve(rendered)[raw.id].point('connector')
    # An explicit projected anchor keeps the leader attached to its object.
    return i.annotate(raw.at('connector'),'Electrode connector',side='n',
                      clear=tip.y+rendered.height/2+4,search=False,within=rendered,
                      size=i.pt(7),head='triangle',through=[raw])


def appearance_panel(*,width,height):
    def shape(brush):
        return i.paint(Diagram(prim=RectPrim(width*.28,17,2),style=i.Style(stroke='none')),brush)
    return i.vstack([
        i.hstack([shape(i.LinearGradient(((0,'#1b6687'),(.5,'#73c3b4'),(1,'#f4d166')))),
                  shape(i.RadialGradient(((0,'#ffffff'),(1,'#6b60b5')))),
                  shape(i.Hatch(color='#245b8a',background='#edf5f9'))],gap=3),
        i.text('Vector gradients and hatching',size=i.pt(7))],gap=3)


def make_document(scene_file=None):
    scene_file=Path(scene_file or ROOT/'out/v3/lab.blend')
    if not scene_file.is_file():
        raise FileNotFoundError('Create the example scene first: python tools/v3_showcase.py')
    doc=i.preset('scientific.general').document(width=190,columns=2,gap=7)
    doc.add('title',i.component(i.title,'Rendered scenes and scientific figures'),colspan=2)
    panels=i.subfigure(columns=2,margin=0,gap=7).letters()
    panels.add('overview',i.component(scene_panel,scene_file,'Overview',responsive=True),row=0,column=0,min_height=82)
    panels.add('detail',i.component(scene_panel,scene_file,'Detail',responsive=True),row=0,column=1,min_height=82)
    data=i.dataset({'time':[0,1,2,3,4,5], 'signal':[.2,1.2,2.8,4.3,5.1,5.5],
                    'reference':[.2,.6,1.1,1.6,2.,2.2]},name='reactor demonstration',
                    source=i.Source('Inklet v3 showcase',method='simulated'))
    response=i.plot_spec(height=43,x=(0,5),y=(0,6))
    response.line(data.points('time','signal'),name='Response',stroke='#236c8c')
    response.line(data.points('time','reference'),name='Reference',stroke='#dd873b')
    response.axes(x='Time / s',y='Signal / a.u.').legend()
    panels.add('response',response,row=1,column=0)
    panels.add('brushes',i.component(appearance_panel,responsive=True),row=1,column=1)
    doc.add('panels',panels,colspan=2)
    doc.add('caption',i.component(i.text,
        'Original procedural scene; simulated data. Scene pixels are embedded; labels and plots remain vector.',
        size=i.pt(6.5)),colspan=2)
    return doc


if __name__=='__main__':
    make_document().export(ROOT/'out/v3/showcase')
