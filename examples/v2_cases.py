"""Complete figures used by v2 visual and performance checks."""
from dataclasses import replace
import math
import inklet as i
from v2_document import make_document


def cases():
    yield 'workflow',make_document()
    theme=replace(i.theme('nature'),font_family='DejaVu Sans',font_size=2.8,font_size_small=2.5)
    data=i.dataset({'time':list(range(21)),
                    'a':[2+math.sin(t/3) for t in range(21)],
                    'b':[3+math.cos(t/4) for t in range(21)]},
                   units={'time':'s','a':'mV','b':'mV'},
                   source=i.Source('Inklet benchmark',method='simulated'))
    scale=i.shared_scale(data.column('a'),data.column('b'))
    doc=i.document(width=180,columns=2,theme=theme)
    for index,(column,title) in enumerate([('a','Short label'),('b','Longer measurement label'),('a','Replicate A'),('b','Replicate B')]):
        p=i.plot_spec(x=(0,20),y=scale).axes(x='Time / s',y=title)
        p.series(i.Series(column,data.column('time'),data.column(column),'#367ca4' if column=='a' else '#c27850'))
        p.legend(side='bottom')
        doc.add(f'panel{index}',p,row=index//2,column=index%2,min_height=45)
    yield 'shared-scales',doc

    doc=i.document(width=160,columns=2,theme=theme)
    p=i.plot_spec(x=(0,10),y=(0,10)).axes(x='Time / s',y='Signal')
    p.line([(0,1),(5,7),(10,5)],name='Signal')
    p.twin_y((0,100),label='Efficiency / %',color='#b65e3b').line([(0,20),(5,70),(10,90)],name='Efficiency')
    p.legend(side='bottom');doc.add('twin',p,row=0,min_height=55)
    matrix=i.plot_spec().colorbar(side='right').matrix([[.1,.7,.3],[.8,.4,.2]],ramp=i.ramp(['white','#27618e']),raster=False)
    matrix.axes();doc.add('matrix',matrix,row=0,column=1,min_height=55)
    yield 'twins-matrix',doc

    child=i.plot_spec(20,18,x=(7,10),y=(7,10),clip=True).line([(7,7),(10,10)])
    parent=i.plot_spec(x=(0,10),y=(0,10),clip=True)
    parent.inset(child,side='right',width=None,plate=False,zoom=(7,10,7,10))
    parent.line([(0,0),(10,10)]).axes(x='Before revision',y='Signal',key='axes')
    doc=i.document(width=110,theme=theme);doc.add('plot',parent,min_height=55)
    doc.compile()
    child.axes().title('Detail')
    parent.replace('axes',x='Revised axis label',y='Measured signal')
    doc.width=125
    yield 'late-inset',doc

    cats=i.CategoryEncoding(i.categories({'a':'#527da8','b':'#cb7853','c':'#76a071'},
                                         labels={'a':'Control','b':'Drug A','c':'Drug B'},
                                         groups={'Reference':['a'],'Treatment':['b','c']}))
    data=i.dataset({'group':['a','b','c'],'value':[4,6,8]})
    p=i.plot_spec(x=(0,10),y=cats.scale(reverse=True)).legend(side='bottom',columns=2)
    p.axes(x='Outcome');p.group_labels(cats,side='left')
    p.bars(data.column('group'),data.column('value'),orient='h',bar_colors=cats)
    doc=i.document(width=100,theme=theme);doc.add('plot',p,min_height=50)
    doc.compile();data.update(group=['a','c'],value=[4,8]);cats.select(['c','a'])
    yield 'category-subset',doc

    data=i.dataset({'x':[k/100 for k in range(1001)],
                    'y':[5+4*math.sin(k/60) for k in range(1001)]},
                   source=i.Source('Inklet dense benchmark',method='simulated'))
    p=i.plot_spec(x=(0,10),y=(0,10),clip=True)
    p.scatter(data.points('x','y'),raster=True,size=.5,stroke='none',color='#397c9e')
    p.line([(0,0),(10,10)],stroke='#b95c42').axes(x='Time',y='Response').title('Dense raster layer')
    doc=i.document(width=110,theme=theme);doc.add('dense',p,min_height=55)
    yield 'dense',doc
