"""Reusable plot layers, independent styling and a responsive mixed composition."""
import argparse
import json
from pathlib import Path

import inklet as i

CAPTION = ('Original illustrative data, not experimental measurements. '
           '(a,b) One live response recipe, independently styled. Bounds are supplied ranges, '
           'not inferred confidence intervals. (c) Grouped category comparisons with independent axis options. '
           '(d) Individual observations and quartile summaries. '
           '(e) A responsive diagram composed from named modules and ports. '
           'The revised figure changes the shared response data without changing author choices.')


def make_document(width=180):
    data=i.dataset(dict(x=[0,1,2,3,4],y=[1,2.2,2,3.6,4.1],
                        low=[.6,1.8,1.7,3.2,3.7],high=[1.4,2.6,2.3,4,4.5]),name='response',
                   units={'x':'s','y':'mV','low':'mV','high':'mV'})
    signal=i.Series('Response',data.column('x'),data.column('y'),'#34786b',data.column('low'),data.column('high'))
    layer=i.plot_spec().series(signal,key='response')
    observations=i.plot_spec().scatter(data.points('x','y'),size=1.4,color='#34786b',key='samples')
    base=i.plot_spec(x=(0,4),y=(0,5),height=34,clip=True).extend(layer).extend(observations)
    base.axes(x='Time / s',y='Response / mV',key='axes',x_options={'count':3},y_options={'count':4})
    base.legend(side='bottom',key='legend')
    alternate=base.copy().style('response',color='#aa5b36',name='Alternative style',stroke_width=.7)
    alternate.style('samples',marker='diamond',color='#aa5b36',size=1.8)
    alternate.style('axes',y_options={'count':3,'format':lambda v:f'{v:g}'})

    bars=i.plot_spec(x=['Control','Treatment','Recovery'],y=(0,8),height=34)
    bars.bars(['Control','Treatment','Recovery'],[[3,5,4],[4,6.5,5]],
              colors=['#527da8','#b96932'],names=['Before','After'],grouped=True)
    bars.axes(y='Response / a.u.',x_options={'rotate':20,'tick_font_size':i.pt(7)},y_options={'count':4})
    bars.legend(side='bottom')

    samples={'A':[1.8,2,2,2.4,2.8,3.2,4.1], 'B':[2.5,3,3,3.4,4,4.4,5.2]}
    boxes=i.plot_spec().boxplot(samples,colors=['#c6d6df','#e0c7b7'],key='summary')
    points=i.plot_spec().swarm(samples,size=1.3,colors=['#355a75','#965329'],key='observations')
    distribution=i.plot_spec(x=['A','B'],y=(0,6),height=34).extend(boxes).extend(points)
    distribution.axes(y='Measurement / a.u.',x_options={'tick_font_size':i.pt(9)},y_options={'count':4})

    flow=i.composition(160,22)
    for n,(name,label) in enumerate([('input','Live data'),('recipe','Plot recipes'),('output','Figure exports')]):
        flow.add(name,i.module(label,min_width=27,min_height=11,pad=2),
                 x=flow.page_width*(n+.5)/3,y=11,anchor='center')
    flow.link('input:out','recipe:in');flow.link('recipe:out','output:in')
    doc=i.preset('scientific.general').document(width=width,columns=2,gap=9,row_gap=9).letters()
    for n,(name,plot) in enumerate([('base',base),('variant',alternate),('categories',bars),('distribution',distribution)]):
        doc.add(name,plot,row=n//2,column=n%2)
    doc.add('workflow',flow,row=2,colspan=2,min_height=25)
    return doc,data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/plot-composition'))
    parser.add_argument('--render',action='store_true',help='Also render PNG and PDF')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    doc,data=make_document()
    original=doc.compile();before=original.to_svg()
    for width in (180,150):
        doc.configure(width=width);figure=doc.compile()
        paths=[args.output/f'figure-{width}mm.svg']
        if args.render:paths.extend([args.output/f'figure-{width}mm.pdf',args.output/f'figure-{width}mm.png'])
        figure.save(*paths)
        (args.output/f'figure-{width}mm.html').write_text(figure.scene.to_html(),encoding='utf-8')
    data.update(y=[1.5,2.5,2.3,4,4.4],low=[1.1,2.1,2,3.6,4],high=[1.9,2.9,2.6,4.4,4.8])
    revised=doc.compile();revised.save(args.output/'revised.svg')
    assert original.to_svg()==before and doc.compile() is revised
    (args.output/'caption.txt').write_text(CAPTION+'\n',encoding='utf-8')
    (args.output/'build-stats.json').write_text(json.dumps(dict(revised.stats),indent=2)+'\n')
    print(args.output)


if __name__=='__main__': main()
