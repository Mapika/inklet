"""Small complete figures exercising features that geometry-only tests miss."""
from dataclasses import replace
import math
import inklet


def figures():
    theme = replace(inklet.theme('nature'), font_family='DejaVu Sans',
                    font_size=2.5, font_size_small=2.2)
    inklet.use_theme(theme)
    p = inklet.panel(55,35,x=(0,10),y=(0,10),clip=True)
    p.scatter([(i/20,5+4*math.sin(i*.2)) for i in range(201)],
              size=.8, color='#247baa', stroke='none', raster=True)
    p.line([(0,0),(10,10)],stroke='#d64a35')
    p.axes(x='Time / s', y='Response')
    p.title('Dense layer + vector annotations')
    f = inklet.figure(width=89,theme=theme);f.add(p.build())
    yield 'dense', f

    p = inklet.panel(40,30,x=(0,10),y=(0,10),clip=True)
    sub = inklet.panel(20,16,x=(8,10),y=(8,10))
    sub.line([(8,8),(10,10)])
    p.inset(sub,side='right',width=None,zoom=(8,10,8,10),plate=False)
    p.line([(0,0),(10,10)]);p.axes(x='Parent',y='Axis added after inset')
    sub.axes()
    f = inklet.figure(width=115,theme=theme);f.add(p.build())
    yield 'inset', f

    p = inklet.panel(55,25,x=list('abcdefg'),y=(0,1))
    for i,marker in enumerate(('circle','square','diamond','triangle','star','cross','plus')):
        p.scatter([(chr(97+i),.7)],marker=marker,size=3,color='#ee6655',stroke='#224488',stroke_width=.5)
        p.scatter([(chr(97+i),.25)],marker=marker,size=3,color='#ee6655',stroke='#224488',stroke_width=.5,raster=True)
    p.axis('bottom');p.title('Vector / raster markers')
    f = inklet.figure(width=89,theme=theme);f.add(p.build())
    yield 'markers', f

    left=inklet.box('H_{2}O\n**Measured**',width=25,height=15,fill='#aaddff',fill_opacity=.6,radius=0)
    right=inklet.box('α + β\n//Estimated//',width=25,height=15,fill='#ffbb88',fill_opacity=.6,radius=2)
    f=inklet.figure(width=89,theme=theme)
    f.add(inklet.hstack([left,right],gap=-5));f.link(left,right,offset=8)
    yield 'type-opacity', f

    glyphs=[inklet.marker(shape,2,fill=color) for shape,color in
            [('circle','#4285b4'),('triangle','#db8b42'),('square','#559d78')]]
    db=inklet.database('Sequence\ndatabase',width=24,height=20)
    matrix=inklet.feature_matrix([[.2,.8,.4],[.7,.1,.6],[.3,.5,1]],cell=7,
                                row_labels=['A','B','C'],column_labels=glyphs,highlight_rows=[1])
    seq=inklet.sequence(glyphs,pitch=7,stem=2,baseline=True)
    f=inklet.figure(width=125,theme=theme)
    f.add(inklet.hstack([db,matrix,seq],gap=15))
    f.link(db.at('output'),matrix.at('row-1'));f.link(matrix.at('output'),seq.at('input'))
    yield 'components',f

    cats=inklet.categories({'a':'#527da8','b':'#cb7853','c':'#76a071'},
                          labels={'a':'Control','b':'Drug A','c':'Drug B'},
                          groups={'Reference':['a'],'Treatment':['b','c']}).subset(['c','a'])
    p=inklet.panel(40,30,x=(0,10),y=cats.scale(reverse=True))
    p.bars(['a','c'],[4,8],orient='h',bar_colors=cats)
    p.axes();cats.group_labels(p,side='left');p.legend(side='right',markup=False)
    f=inklet.figure(width=125,theme=theme);f.add(p.build())
    yield 'categories',f
