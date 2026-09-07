"""Common plots from typed CSV tables, with a separate manuscript caption."""
import argparse
import hashlib
import json
from pathlib import Path

import inklet as i

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(__file__).with_name('data')/'general-plots'
CAPTION='''Illustrative machine-learning, engineering and business plots.
(a) Three simulated training-loss curves. (b) Simulated accuracy versus inference latency for the same model names.
(c) A simulated first-order sensor response with Gaussian observation noise. (d) Residuals from the same response model, in fixed-width bins.
(e) Simulated quarterly revenue by product. (f) Each product's share of total revenue within the quarter.
All CSV inputs are original simulated data, not observed measurements or external benchmark results.
The sensor noise uses a fixed seed (2026) and standard deviation 0.03. Model and residual columns are supplied in the data;
no fit or statistical uncertainty is inferred by Inklet.
Data, recipe and figure: MIT, Mark Marosi.
'''


def load_data():
    definitions={
        'learning':dict(types={k:float for k in ('epoch','baseline','refined','ensemble')}),
        'benchmark':dict(types={'latency':float,'accuracy':float},units={'latency':'ms'}),
        'sensor':dict(types={k:float for k in ('time','measured','model','residual')},units={'time':'s'}),
        'revenue':dict(types={k:float for k in ('subscriptions','services','licensing')},
                       units={k:'kEUR' for k in ('subscriptions','services','licensing')}),
    }
    return {name:i.read_csv(DATA/(name+'.csv'),name=name,citation='Inklet illustrative '+name,method='simulated',**options)
            for name,options in definitions.items()}


def make_document(*,legacy=False):
    tables=load_data()
    style=i.preset('scientific.general').customize(width=240,margin=6,gap=8)
    doc=style.document(columns=3).letters()
    axis_options={'stroke_width':style.theme.stroke} if legacy else {}
    legend_options={'columns':1} if legacy else {}
    def axes(plot,**kwargs):return plot.axes(**kwargs,**axis_options)
    def legend(plot):return plot.legend(side='bottom',**legend_options)
    learning=tables['learning']
    p=i.plot_spec(height=40,x=(0,60),y=(0,1.2))
    colors={name:style.theme.color(n) for n,name in enumerate(('Baseline','Refined','Ensemble'))}
    for name,column in [('Baseline','baseline'),('Refined','refined'),('Ensemble','ensemble')]:
        p.line(learning.points('epoch',column),name=name,stroke=colors[name])
    axes(p,x='Epoch',y='Training loss');legend(p)
    doc.add('learning',p,row=0,column=0)
    benchmark=tables['benchmark']
    p=i.plot_spec(height=40,x=(10,45),y=(.75,.95))
    # Explicit dependencies keep the point positions live after data edits.
    for index,name in enumerate(benchmark.columns['model']):
        points=i.derive(lambda xy,n: (xy[n],),benchmark.points('latency','accuracy'),index)
        p.scatter(points,name=name,color=colors[name],size=1.8)
    axes(p,x='Inference latency / ms',y='Accuracy');legend(p)
    doc.add('benchmark',p,row=0,column=1)
    sensor=tables['sensor']
    p=i.plot_spec(height=40,x=(0,6),y=(-.1,1.15))
    p.scatter(sensor.points('time','measured'),name='Observed',size=.8)
    p.line(sensor.points('time','model'),name='Model')
    axes(p,x='Time / s',y='Normalized response');legend(p)
    doc.add('response',p,row=0,column=2)
    p=i.plot_spec(height=40,x=(-.12,.12),y=(0,45))
    p.hist(sensor.column('residual'),bins=[n*.02 for n in range(-6,7)])
    axes(p,x='Response residual',y='Observations')
    doc.add('residuals',p,row=1,column=0)
    revenue=tables['revenue'];products=['Subscriptions','Services','Licensing']
    p=i.plot_spec(height=40,x=revenue.columns['quarter'],y=(0,210))
    p.bars(revenue.column('quarter'),tuple(revenue.column(name.lower()) for name in products),names=products)
    axes(p,x='Quarter',y='Revenue / kEUR');legend(p)
    doc.add('revenue',p,row=1,column=1)
    shares=i.derive(lambda *columns: tuple(tuple(100*v/sum(period) for v,period in zip(column,zip(*columns))) for column in columns),
                    *(revenue.column(name.lower()) for name in products))
    p=i.plot_spec(height=40,x=revenue.columns['quarter'],y=products[::-1])
    p.matrix(shares,x=revenue.column('quarter'),y=products,ramp=i.ramp('tol-ylorbr'),scale=i.linear((0,100)),raster=False)
    axes(p,x='Quarter',count=4)
    p.colorbar(side='bottom',label='Quarterly revenue share / %',ticks=[0,50,100],**axis_options)
    doc.add('composition',p,row=1,column=2)
    return doc,tables


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/general-plots')
    parser.add_argument('--legacy-look',action='store_true',help='Reproduce the previous axis weight and stacked legends for comparison')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    doc,tables=make_document(legacy=args.legacy_look);figure=doc.compile()
    print(figure.report(),flush=True)
    if figure.diagnostics:raise RuntimeError(figure.report())
    figure.export(args.output,dpi=190)
    (args.output/'caption.txt').write_text(CAPTION)
    latex=CAPTION.replace('%',r'\%').replace('\n',' ')
    (args.output/'caption.tex').write_text('\\caption{'+latex.strip()+'}\n')
    report=dict(schema='inklet.general-plots/0.1',inklet_version=i.__version__,legacy_look=args.legacy_look,
        sources={name:dict(file=Path(table.source.path).name,sha256=table.source.sha256,method=table.source.method,
                          columns=dict(table.columns),units=dict(table.units)) for name,table in tables.items()},
        figure=dict(width_mm=figure.root.width,height_mm=figure.root.height,diagnostics=len(figure.diagnostics)),
        caption_sha256=hashlib.sha256(CAPTION.encode()).hexdigest())
    (args.output/'data.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
