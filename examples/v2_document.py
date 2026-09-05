"""A complete live figure: architecture, uncertainty, inset and grouped outcomes.

All numerical values are simulated demonstrations, not results from AlphaFold.
Run: python -m inklet build examples/v2_document.py --output out/v2
"""
from dataclasses import replace
import math
import inklet as i


def caption(content, *, width, height):
    return i.text(content, width=width, size=2.4, markup=False)


def make_document():
    theme=replace(i.theme('nature'),font_family='DejaVu Sans',font_size=2.8,font_size_small=2.5)
    data=i.dataset({'time':list(range(11)),
                    'signal':[1+v*.65+.3*math.sin(v) for v in range(11)],
                    'lower':[.5+v*.65+.3*math.sin(v) for v in range(11)],
                    'upper':[1.5+v*.65+.3*math.sin(v) for v in range(11)]},
                   units={'time':'s','signal':'a.u.','lower':'a.u.','upper':'a.u.'},
                   source=i.Source('Inklet v2 demonstration',method='simulated'),name='response')
    scale=i.shared_scale(data.column('lower'),data.column('upper'),include_zero=True)
    series=i.Series('Response',data.column('time'),data.column('signal'),'#367ca4',
                    data.column('lower'),data.column('upper'))
    detail=i.plot_spec(20,16,x=(7,10),y=(4,8),clip=True).line(data.points('time','signal'),stroke='#367ca4').axes()
    response=i.plot_spec(40,38,x=(0,10),y=scale,clip=True)
    response.legend(side='bottom').inset(detail,side='right',width=None,plate=False,pad=3,zoom=(7,10,4,8))
    response.axes(x='Time / s',y='Response / a.u.',key='axes').series(series)
    response.title('a  Simulated response')

    definition=i.categories({'control':'#657d91','a':'#bf7652','b':'#6b9568'},
                            labels={'control':'Control','a':'A','b':'B'},
                            groups={'Reference':['control'],'Treatment':['a','b']})
    encoding=i.CategoryEncoding(definition)
    outcomes=i.dataset({'condition':['control','a','b'],'value':[3.1,6.3,7.8]},
                       source=i.Source('Inklet v2 demonstration',method='simulated'),name='outcomes')
    bars=i.plot_spec(40,38,x=(0,10),y=encoding.scale(reverse=True))
    bars.legend(side='bottom',columns=3,markup=False).group_labels(encoding,side='left')
    bars.bars(outcomes.column('condition'),outcomes.column('value'),orient='h',bar_colors=encoding)
    bars.axes(x='Outcome / a.u.');bars.title('b  Simulated outcomes')

    doc=i.document(width=210,columns=4,theme=theme,gap=7)
    doc.add('database',i.component(i.database,'Sequence\ndatabase',width=28,height=22),
            row=0,column=0,min_width=28,min_height=38)
    doc.add('features',i.component(i.feature_matrix,[[.1,.6,.3],[.5,.2,.8],[.2,.9,.4]],
                                  cell=7,row_labels=['A','B','C'],column_labels=['X','Y','Z']),
            row=0,column=1,colspan=2,min_width=35,min_height=38)
    doc.add('prediction',i.component(i.box,'Predicted\nstructure',width=30,height=20),
            row=0,column=3,min_width=30,min_height=38)
    doc.link('database:output','features:row-1')
    doc.link('features:output','prediction')
    doc.add('response',response,row=1,column=0,colspan=2,min_width=85,min_height=65)
    doc.add('outcomes',bars,row=1,column=2,colspan=2,min_width=85,min_height=65)
    doc.add('caption',i.component(caption,'Illustrative workflow and simulated data. Bands show supplied uncertainty bounds; the inset follows the response data.',responsive=True),
            row=2,colspan=4,min_width=100,min_height=12)
    return doc


if __name__=='__main__':
    print(make_document().export('out/v2',name='document')['review'])
