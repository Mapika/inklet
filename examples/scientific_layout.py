"""Dev14: coordinated annotations, constrained panels and native anatomy sections."""
from pathlib import Path
import argparse,json,math
import inklet as i
from inklet.core import Rect,Envelope
from inklet.three.solids import sphere
from inklet.render.raster import save_png


def build():
    mesh=sphere(subdivisions=3)
    lines=[[(-1.2,-.3,-.4),(-.3,-.15,-.1),(.3,.1,.2),(1.3,.2,.3)],
           [(-.2,-.9,.1),(.1,-.2,-.2),(.2,.3,.3),(.1,1.1,.4)]]
    def anatomy(w,h,cut=False):
        a=i.anatomy_view(mesh,width=w,height=h,camera='three-quarter')
        a.surface('tissue',mesh,color='#b9cdcf').paths('paths',lines,color='#b26383',stroke_width=.6)
        a.markers('sites',[line[-1] for line in lines],color='#e09b34',radius=.8)
        a.lighting(direction=(-.5,-.4,-1),levels=18)
        return (a.cut((1,0,0)) if cut else a).build(depth='occluded')
    matrix=[[math.sin(r/6)*math.cos(c/9) for c in range(72)] for r in range(72)]
    def heat(w,h):
        return i.panel(w,h,x=(0,72),y=(72,0)).matrix(matrix,ramp=i.ramp(['#edd9c1','#f3f4ee','#397583']),scale=i.linear((-1,1)),vector='batched').axes(x='column',y='row',tick_font_size=2.2,label_font_size=2.6).colorbar(side='right',tick_font_size=2)
    nodes={name:i.tag(name,size=2.8,pad=(2,1),fill=color,color='white') for name,color in [('source','#087f8c'),('branch','#8055a5'),('sink','#3b73b9')]}
    graph=i.graph(nodes,[('source','branch',{'stroke_width':.1,'arrow_size':.4}),('branch','source'),('branch','sink')],direction='right',gap=3,rank_gap=10,lane=3)
    network=graph.build(min_arrow_size=1.1,min_stroke_width=.18)
    art=i.panel_mosaic(['A B C','D D C'],{'A':i.PanelSpec(lambda w,h:anatomy(w,h),min_width=48), 'B':i.PanelSpec(lambda w,h:anatomy(w,h,True),min_width=48),'C':i.PanelSpec(heat,aspect=1,min_width=65,align='start'),'D':network},width=190,height=110,margin=4,gap=4,titles={'A':'Opaque anatomy','B':'Shared cut plane','C':'Batched vectors','D':'Joint page annotations'},label_size=3)
    region=Rect(0,110,190,130)
    art=i.Diagram(children=(art,),envelope_override=Envelope.from_rect(Rect(0,0,190,130)))
    annotations={'source':i.FigureAnnotation(i.tag('registered source',size=2.4,fill='white'),within=region,target=nodes['source']),
                 'sink':i.FigureAnnotation(i.tag('registered target',size=2.4,fill='white'),within=region,target=nodes['sink']),
                 'key':i.FigureAnnotation(i.legend([('path','#b26383'),('site','#e09b34')],font_size=2.4,columns=2,text_fill='#243642'),within=region,at=(155,120))}
    return i.place_annotations(art,annotations,clearance=.8,pad=1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('out/scientific-layout'));args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    art=build()
    i.save_svg(art,str(args.output/'figure.svg'),text='embed');i.save_pdf(art,str(args.output/'figure.pdf'),text='embed');save_png(art,args.output/'figure.png',dpi=200,background='white')
    review=i.review_figure(art,rules=['TINY_TEXT','OFF_CANVAS','MISSING_GLYPHS'],page=art.bbox,min_font_pt=5)
    review.save(args.output/'review');(args.output/'placement.json').write_text(json.dumps(art.notes['annotations'],indent=2))
    print('Built native scientific layout and review artifacts')

if __name__=='__main__':main()
