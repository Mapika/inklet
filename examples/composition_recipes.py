"""One reusable report layout with live plots, native 3D and a nested workflow."""
import argparse
import json
from pathlib import Path
import inklet as i


def make_template():
    flow=i.composition(150,20)
    for n,(name,label) in enumerate([('input','Measurements'),('model','Model'),('output','Comparison')]):
        flow.add(name,i.module(label,min_width=28,min_height=11,pad=2),
                 x=flow.page_width*(n+.5)/3,y=10,anchor='center')
    flow.link('input:out','model:in').link('model:out','output:in')
    flow.port('entry','input:in').port('exit','output:out')

    recipe=i.composition(180,110)
    recipe.slot('heading',x=10,y=5,anchor='nw')
    recipe.slot('chart',x=13,y=25,anchor='area-nw',width=recipe.page_width*.58-20,height=40)
    recipe.slot('object',x=recipe.page_width*.8,y=43,anchor='center')
    recipe.add('object_label',i.component(i.text,'Illustrative model',font_size=3),
               x=recipe.page_width*.8,y=72,anchor='center')
    recipe.add('workflow',flow,x=5,y=86,width=recipe.page_width-10,height=20)
    recipe.port('entry','workflow:entry').port('exit','workflow:exit')
    recipe.constrain(recipe.page_width,minimum=140,message='report needs at least 140 mm')
    return recipe


def make_reports():
    data=i.dataset({'x':[0,1,2,3,4], 'y':[1,2.2,2.8,3.2,4.1]},
                   name='illustrative-response',units={'x':'s','y':'mm'})
    chart=i.plot_spec(x=(0,4),y=(0,5),clip=True)
    chart.line(data.points('x','y'),stroke='#34786b',stroke_width=.65,name='Response',key='response')
    chart.scatter(data.points('x','y'),color='#34786b',size=1.3,key='samples')
    chart.axes(x='Time / s',y='Displacement / mm',x_options={'count':3},y_options={'count':4})
    chart.legend(side='bottom')
    recipe=make_template()
    first=recipe.instantiate(heading=i.component(i.text,'Response study / A',font_size=4.8),
                            chart=chart,object=i.component(i.solid,'cube',width=28,style='shaded'))
    second=recipe.instantiate(heading=i.component(i.text,'Response study / B',font_size=4.8),
                             chart=chart,object=i.component(i.solid,'sphere',width=28,style='toon'))
    second['chart'].style('response',stroke='#aa5b36',name='Styled response')
    second['chart'].style('samples',color='#aa5b36',marker='diamond')
    second['workflow']['model'].configure('Revised model')
    second['object_label'].configure('Alternative geometry')
    return (first,second),data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/composition-recipes'))
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    reports,data=make_reports()
    compiled=[]
    for n,report in enumerate(reports):
        doc=i.preset('scientific.general').document(width=180,height=110,margin=0)
        doc.add('report',report)
        for width in (180,150):
            doc.configure(width=width)
            figure=doc.compile();stem=args.output/f'report-{n+1}-{width}mm'
            paths=[stem.with_suffix('.svg')]
            if args.render:paths.extend([stem.with_suffix('.pdf'),stem.with_suffix('.png')])
            figure.save(*paths)
            stem.with_suffix('.html').write_text(figure.scene.to_html(title=f'Response study {n+1}'),encoding='utf-8')
        compiled.append((doc,figure,figure.to_svg()))
    data.update(y=[1.4,2.5,3.2,3.6,4.4])
    stats=[]
    for n,(doc,old,svg) in enumerate(compiled):
        changed=doc.compile();changed.save(args.output/f'revised-{n+1}.svg')
        assert changed.to_svg()!=svg and old.to_svg()==svg and doc.compile() is changed
        stats.append(dict(changed.stats))
    (args.output/'build-stats.json').write_text(json.dumps(stats,indent=2)+'\n')
    (args.output/'caption.txt').write_text('Original illustrative data and generated geometry; no experimental claims. '
        'Two independent instances share live measurements while preserving their own styles and content.\n')
    print(args.output)


if __name__=='__main__':main()
