"""Physical typography, plot furniture and common anatomy layers."""
import numpy as np
import inklet as i
from data import GROUPS,COLORS
INK='#243642';TEAL='#087f8c';PURPLE='#8055a5';GOLD='#e58f29';BLUE='#3b73b9'
AX=dict(tick_font_size=2,label_font_size=2.3,count=3,tick_size=.8,tick_pad=.6,label_pad=1.1)


def chart(w,h,x,y):return i.panel(w,h,x=x,y=y)
def caption(node,words):return i.vstack([node,i.text(words,size=2.15,fill=INK,markup=False,align='center')],gap=2)
def key(entries,columns=2):return i.legend(entries,font_size=2.2,columns=columns,swatch=2.2,gap=2,row_gap=1.3,markup=False,text_fill=INK)
def ecdf(values):
    result=[]
    for k,value in enumerate(values):result.extend([(value,k/len(values)),(value,(k+1)/len(values))])
    return result

def axes(p,x=None,y=None,**kwargs):return p.axes(x=x,y=y,**AX,**kwargs)

def anatomy(d,w,h,groups=GROUPS,camera=None,focus=None,context=True):
    a=i.anatomy_view(d.brain if focus is None else focus,width=w,height=h,camera=camera or d.camera,pad=1)
    if context:a.surface('brain',d.brain,color='#d2d8d9',opacity=.38)
    for name in ['AL-L','AL-R']:
        a.surface(name,d.rois[name],color='#9db7bb',opacity=.45)
    for g in groups:a.paths(g,d.lines[g],color=COLORS[GROUPS.index(g)],stroke_width=.16,opacity=.75,depth_cue=.15)
    return a

