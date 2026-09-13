"""Native Inklet panels positioned in reference-figure design coordinates."""
from pathlib import Path
import numpy as np
import inklet as i
from inklet.core import Rect, Envelope, RectPrim


class Page:
    def __init__(self,width,height,physical_width=200,font='Arimo'):
        self.width,self.height,self.s,self.font=width,height,physical_width/width,font
        self.nodes=[];self.panels={};self.panel_nodes={}
        self.area=Rect(-.8,-.8,width*self.s+.8,height*self.s+.8)

    def text(self,value,x,y,size=18,align='left',valign='top',weight='regular',angle=0,font=None,markup=False,italic=False):
        node=i.text(str(value),size=size*self.s,font=font or self.font,markup=markup,font_style='italic' if italic else 'normal',
                    bounds='ink',weight=weight,text_fill='black',line_height=1.08)
        if angle:node=node.rotated(angle)
        b=node.bbox
        node=node.translated(x*self.s-{'left':b.x0,'center':b.center.x,'right':b.x1}[align],
                             y*self.s-{'top':b.y0,'center':b.center.y,'bottom':b.y1}[valign])
        self.nodes.append(node);return node

    def line(self,points,color='black',width=1,dash=None):
        style=dict(stroke=color,stroke_width=width*self.s,fill='none')
        if dash:style['stroke_dash']=tuple(x*self.s for x in dash)
        self.nodes.append(i.as_drawn(i.polyline([(x*self.s,y*self.s) for x,y in points],**style)))

    def rect(self,x,y,w,h,fill='none',stroke='none',width=1):
        self.nodes.append(i.Diagram(prim=RectPrim(w*self.s,h*self.s),
            style=i.Style(fill=fill,stroke=stroke,stroke_width=width*self.s)).translated((x+w/2)*self.s,(y+h/2)*self.s))

    def plot(self,key,box,xlim,ylim,xticks,yticks,xlabel=None,ylabel=None,
             xlabels=True,ylabels=True,rotate=0,xformat=None,frame=True,tick_size=17,label_size=20):
        x,y,w,h=box;p=i.panel(w*self.s,h*self.s,x=xlim,y=ylim)
        options=dict(tick_font_size=tick_size*self.s,label_font_size=label_size*self.s,
                     tick_size=5*self.s,tick_pad=5*self.s,label_pad=9*self.s,
                     stroke='#444444',stroke_width=.8*self.s,font_family=self.font,
                     text_fill='#222222',thin=False)
        p.axes(x=xlabel,y=ylabel,x_options=dict(ticks=xticks,labels=xlabels,rotate=rotate,format=xformat),
               y_options=dict(ticks=yticks,labels=ylabels),**options)
        if frame:
            p.axis('top',ticks=[],labels=False,**options);p.axis('right',ticks=[],labels=False,**options)
        self.panels[key]={'box':list(box),'xlim':list(xlim) if isinstance(xlim,tuple) else str(xlim),
                          'ylim':list(ylim) if isinstance(ylim,tuple) else str(ylim)}
        p._paper_key=key
        return p

    def add_plot(self,p,box):
        x,y,w,h=box
        node=p.placed(x*self.s,y*self.s)
        self.nodes.append(node);self.panel_nodes[p._paper_key]=node

    def key(self,items,x,y,size=16,row=22,columns=1,colwidth=135,patch=False):
        entries=[(label,i.Diagram(prim=RectPrim(24*self.s,12*self.s)).styled(fill=color,stroke='none') if patch else i.as_drawn(i.polyline(
            [(0,0),(26*self.s,0)],stroke=color,stroke_width=2.5*self.s))) for label,color in items]
        options=dict(font_size=size*self.s,font_family=self.font,swatch=12*self.s,
                     gap=8*self.s,markup=False)
        row_height=max(i.legend([entry],**options).height for entry in entries)
        node=i.legend(entries,columns=columns,row_gap=max(0,row*self.s-row_height),
                      col_gap=14*self.s,**options)
        box=node.bbox
        self.nodes.append(node.translated(x*self.s-box.x0,y*self.s-box.y0))

    def build(self):
        return i.Diagram(children=tuple(self.nodes),kind='paper-recreation',
            envelope_override=Envelope.from_rect(self.area))


def runs(*arrays):
    """Keep missing samples as gaps in every line and confidence band."""
    arrays=[np.asarray(a,dtype=float) for a in arrays]
    valid=np.logical_and.reduce([np.isfinite(a) for a in arrays]);starts=np.flatnonzero(valid & ~np.r_[False,valid[:-1]])
    ends=np.flatnonzero(valid & ~np.r_[valid[1:],False])+1
    return [tuple(a[start:end] for a in arrays) for start,end in zip(starts,ends) if end-start>1]


def lines(panel,x,y,color,width,opacity=1):
    for xx,yy in runs(x,y):panel.line(zip(xx,yy),stroke=color,stroke_width=width,opacity=opacity)
