"""Inklet 2.5: nested panels, measured modules, annotations and print defaults.

All data are simulated. Build with `inklet build examples/v25_document.py`.
The returned document exposes named children for label and data revisions.
"""
import inklet as i


def caption(content, *, width, height):
    return i.text(content,width=width,size=i.pt(7),markup=False)


def architecture():
    art=i.composition(175,50)
    art.add('input',i.module('Observations',min_width=27),x=4,y=14.5)
    x,_=art.point('input','out')
    art.add('encoder',i.module('Shared encoder',min_height=25,
            ports={'in':(0,.5),'prediction':(1,.24),'uncertainty':(1,.76),'recycle':(.5,1)}),x=x+16,y=8)
    x,_=art.point('encoder','prediction')
    free=(art.page_width-x-53)/2
    art.constrain(free,message='Architecture labels need a wider page')
    art.add('prediction',i.module('Prediction',min_width=28),x=x+12+free,y=8)
    art.add('uncertainty',i.module('Uncertainty',min_width=28),x=x+12+free,y=25)
    art.link('input:out','encoder:in',name='observations')
    art.link('encoder:prediction','prediction:in',route='orthogonal',name='prediction-branch')
    art.link('encoder:uncertainty','uncertainty:in',route='orthogonal',name='uncertainty-branch')
    px,py=art.point('prediction','e');ex,_=art.point('encoder','recycle')
    art.link('prediction:e','encoder:recycle',route='orthogonal',
             waypoints=[(px+8,py),(px+8,44),(ex,44)],label='Refine',name='recycling',stroke='#687f93')
    return art


def make_document():
    data=i.dataset({'time':[0,1,2,3,4,5], 'response':[1,2.1,3.4,4.2,5.4,6.2],
                    'lower':[.6,1.6,2.8,3.6,4.8,5.7], 'upper':[1.4,2.6,4,4.8,6,6.7]},
                   name='simulated response',source=i.Source('Inklet 2.5 example',method='simulated'))
    series=i.Series('Response',data.column('time'),data.column('response'),'#367ca4',
                    data.column('lower'),data.column('upper'))
    response=i.plot_spec(x=(0,5),y=(0,8)).series(series).axes(x='Time / s',y='Response / a.u.')
    response.annotate(3,4.2,'After treatment',side='nw',size=2.5)
    response.legend(side='bottom')
    outcomes=i.dataset({'condition':['Control','Treatment'],'value':[3.2,6.1]},
                       name='simulated outcomes',source=i.Source('Inklet 2.5 example',method='simulated'))
    bars=i.plot_spec(x=i.band(['Control','Treatment']),y=(0,9))
    bars.bracket('Control','Treatment','**')
    bars.bars(outcomes.column('condition'),outcomes.column('value'),bar_colors=['#8798a5','#367ca4'])
    bars.axes(y='Outcome / a.u.')
    plots=i.subfigure(columns=2,gap=8).letters(start='b',size=i.pt(9))
    plots.add('response',response,row=0,column=0,min_height=68)
    plots.add('outcomes',bars,row=0,column=1,min_height=68)
    doc=i.publication('double-column').document(gap=4)
    workflow=i.subfigure().letters(start='a',size=i.pt(9))
    workflow.add('model',architecture(),min_height=52)
    doc.add('workflow',workflow,min_height=58)
    doc.add('measurements',plots,min_height=68)
    doc.add('caption',i.component(caption,
        'Simulated observations and outcomes. Shaded bounds and significance symbols are illustrative. '
        'Module labels, response data and page width can be edited without scaling the typography.',
        responsive=True),min_height=13)
    return doc


if __name__=='__main__':
    print(make_document().export('out/v25',name='document')['review'])
