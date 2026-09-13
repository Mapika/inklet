"""Small absolute-coordinate scientific drawing vocabulary built on Inklet."""
import math
from pathlib import Path
import numpy as np
import inklet as i
from inklet.core import RectPrim, EllipsePrim
from anatomy import paths

BLUE='#668fb8';GOLD='#e4b83e';GREEN='#6d9259';PINK='#bd4396';BLACK='#252525';GRAY='#92918d'
class Page:
    def __init__(self,name,out):
        self.name=name;self.out=out;self.width=1346;self.height=1752;self.nodes=[];self.labels=0
        self.rect(0,0,self.width,self.height,'white')
    def rect(self,x,y,w,h,fill='white',stroke='none',width=.5):
        if w<=0 or h<=0:return
        node=i.Diagram(prim=RectPrim(w,h)).styled(fill=fill,stroke=stroke,stroke_width=width).translated(x+w/2,y+h/2)
        self.nodes.append(node)
        return node
    def ellipse(self,x,y,rx,ry,fill='none',stroke=BLACK,width=.6,angle=0):
        self.nodes.append(i.Diagram(prim=EllipsePrim(rx,ry)).styled(fill=fill,stroke=stroke,stroke_width=width).rotated(angle).translated(x,y))
    def text(self,text,x,y,size=12,*,color='#111111',weight='regular',target_width=None,name=None,align='left',angle=0,valign='top',bounds='font',line_align='left'):
        node=i.text(str(text),size=size,font='Arimo',weight=weight,align=line_align,markup=False,text_fill=color,line_height=1.03,bounds=bounds)
        if target_width and node.bbox.width:node=node.scaled(target_width/node.bbox.width,1)
        if angle:node=node.rotated(angle)
        b=node.bbox;node=node.translated(x-({'left':b.x0,'center':b.center.x,'right':b.x1}[align]),y-{'top':b.y0,'center':b.center.y,'bottom':b.y1}[valign])
        if name:node=node.named(name)
        self.nodes.append(node);self.labels+=1
        return node
    def line(self,points,color='#444444',width=.8,opacity=1,dash=None):
        node=paths([points],color,width=width,opacity=opacity,name='authored-line')
        if dash:node=node.styled(stroke_dash=dash)
        self.nodes.append(node)
    def poly(self,points,color,opacity=1):self.nodes.append(paths([points],color,fill=True,opacity=opacity,name='authored-polygon'))
    def dots(self,xy,color,r=2,opacity=1,shape='o',filled=True):
        if not len(xy):return
        ts=np.linspace(0,2*np.pi,13 if shape=='o' else 5)[:-1]+(np.pi/4 if shape=='s' else 0)
        curves=[np.asarray([x,y])+np.c_[np.cos(np.r_[ts,ts[0]]),np.sin(np.r_[ts,ts[0]])]*r for x,y in xy]
        self.nodes.append(paths(curves,color,fill=filled,width=.5,opacity=opacity,name='data-markers'))
    def arrow(self,points,color=BLACK,width=.7,head=4,*,smooth=0,dash=None):
        self.nodes.append(i.as_drawn(i.arrow(points,color=color,stroke_width=width,
                                            head_length=head,smooth=smooth,stroke_dash=dash)))
    def label(self,text,x,y,size=12,fill='#eeeeee',color=BLACK):
        node=i.tag(text,size=size,font='Arimo',fill=fill,color=color,
                   pad=(2,.7),radius=.7,markup=False)
        # Position from measured text padding, never character-count estimates.
        box=node.bbox
        self.nodes.append(node.translated(x-2-box.x0,y-.7-box.y0))
        self.labels+=1
    def axes(self,x,y,w,h,xlim,ylim,xticks,yticks,xlabel='',ylabel='',logx=False,logy=False,size=9):
        frame=i.panel(w,h,x=i.log(xlim) if logx else xlim,y=i.log(ylim) if logy else ylim)
        point=PlotMap(frame,x+w/2,y+h/2)
        self.line([(x,y),(x,y+h),(x+w,y+h)],BLACK,.7)
        def tick(value,log):
            if log and value>0 and abs(math.log10(value)-round(math.log10(value)))<1e-9:
                return '10'+str(round(math.log10(value))).translate(str.maketrans('-0123456789','⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))
            return f'{value:g}'
        for value in xticks:
            px=point([value],[ylim[0]])[0,0];self.line([(px,y+h),(px,y+h+3)],BLACK,.5);self.text(tick(value,logx),px,y+h+5,size,align='center')
        for value in yticks:
            py=point([xlim[0]],[value])[0,1];self.line([(x-3,py),(x,py)],BLACK,.5);self.text(tick(value,logy),x-5,py-size/2,size,align='right')
        if xlabel:self.text(xlabel,x+w/2,y+h+21,size+1,align='center')
        if ylabel:
            widest=max((i.text(tick(v,logy),size=size,font='Arimo',markup=False).bbox.width for v in yticks),default=0)
            title=i.text(ylabel,size=size+1,font='Arimo',markup=False).rotated(-90)
            bounds=title.bbox
            self.nodes.append(title.translated(x-10-widest-6-bounds.x1,y+h/2-bounds.center.y))
            self.labels+=1
        return point
    def fly(self,x,y,w,h):
        self.rect(x,y,w,h,'white','#cccccc',.8)
        cx=x+w*.5
        self.ellipse(cx,y+h*.22,w*.14,h*.095,'#b9bab7','#777777')
        self.ellipse(cx,y+h*.39,w*.13,h*.12,'#b9bab7','#777777')
        self.ellipse(cx,y+h*.67,w*.115,h*.25,'#b9bab7','#777777')
        for sign in [-1,1]:
            self.ellipse(cx+sign*w*.11,y+h*.67,w*.095,h*.25,'#eeeeee','#999999',.6,angle=sign*11)
            for k in range(3):
                yy=y+h*(.37+k*.09);self.line([(cx+sign*w*.1,yy),(cx+sign*w*(.3-k*.035),yy+h*.09),(cx+sign*w*.39,yy+h*(.03+k*.08))],'#777777',.6)
            self.line([(cx+sign*w*.06,y+h*.15),(cx+sign*w*.1,y+h*.1),(cx+sign*w*.15,y+h*.09)],'#ca536a',1)
            self.line([(cx+sign*w*.04,y+h*.49),(cx+sign*w*.16,y+h*.82)],'#aaa',.5)
    def wing(self,x,y,w,h):
        self.ellipse(x+w/2,y+h/2,w*.47,h*.34,'#f1f1ef','#cccccc',.5,angle=-12)
        for f in [.1,.3,.6]:self.line([(x+w*.08,y+h*.6),(x+w*.5,y+h*f),(x+w*.91,y+h*.33)],'#c1c1bd',.4)
    def root(self,width):return i.Diagram(children=tuple(self.nodes),name=self.name).scaled(width/self.width)


class PlotMap:
    """Numpy bridge to Inklet's shared axis/mark/region coordinates."""
    def __init__(self,panel,x,y):self.panel=panel;self.offset=i.Vec2(x,y)
    def __call__(self,x,y):
        xx,yy=np.broadcast_arrays(np.atleast_1d(x),np.atleast_1d(y))
        return np.array([(v.x+self.offset.x,v.y+self.offset.y) for v in self.panel.map(zip(xx.flat,yy.flat))])
    def region(self,x0,y0,x1,y1):
        b=self.panel.region(x0,y0,x1,y1);o=self.offset
        return i.Rect(b.x0+o.x,b.y0+o.y,b.x1+o.x,b.y1+o.y)
