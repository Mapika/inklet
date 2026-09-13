"""Small runnable demonstration; geometry and pathways are illustrative."""
from pathlib import Path
import inklet as i
from inklet.three import Camera
from inklet.three.solids import sphere


def build():
    mesh=sphere(subdivisions=3)
    view=Camera.named('three-quarter').frame(mesh,width=45)
    surface=i.model(mesh,view=view,style='solid',shading='smooth',
                    color='#c5c2bc',opacity=.6)
    lines=[[(-.4,-.15,-.1),(-.15,-.1,.1),(.1,0,.05),(.35,.15,.25)],
           [(-.15,-.1,.1),(-.05,.15,.3),(.15,.25,.35)]]
    tissue=i.drawn([surface,view.paths(lines,color='#668fb8',stroke_width=.35),
                    view.markers([lines[0][-1],lines[1][-1]],color='#e4b83e',radius=.8)])
    pathway=i.as_drawn(i.arrow([(0,14),(5,5),(15,3),(23,10)],
                               color='#66a486',stroke_width=.6,head_length=2.5))
    labels=i.vstack([i.tag('CB intrinsic',size=3,fill='#86a9c6',color='white'),
                     i.tag('Projection neuron',size=3,fill='#66a486',color='white')],gap=3)
    source=i.tag('source',size=3,fill='#eee').translated(10,12)
    target=i.tag('target',size=3,fill='#ddd').translated(40,12)
    edges=[i.connect(a,b,offset=4,standoff=.5,arrow_size=2,stroke='#777')
           for a,b in [(source,target),(target,source)]]
    callouts=i.label_column([i.tag(s,size=2.5,fill='white',pad=.5) for s in ['102','103']],
                            [(49,11.5),(49,12.5)],x=60,bounds=(5,22),gap=1.5)
    network=i.Diagram(children=(*edges,source,target,callouts))
    return i.vstack([i.text('Shared camera and measured annotations',size=4),
                      i.hstack([tissue,i.vstack([pathway,labels],gap=7)],gap=10),
                      network,
                      i.text('Illustrative geometry, not measured anatomy',size=2.5)],gap=5)

if __name__=='__main__':
    out=Path('out/scientific-authoring');out.mkdir(parents=True,exist_ok=True)
    for ext,save in [('svg',i.save_svg),('pdf',i.save_pdf)]:save(build(),str(out/('example.'+ext)),text='embed')
