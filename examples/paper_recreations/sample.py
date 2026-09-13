"""Figure 4 reconstructed from released predictions and author-defined statistics."""
import ast,collections,io,pickle
import numpy as np
import pandas as pd
import inklet as i
from canvas import Page,lines

AGENTS=['#00ca71','#00a3db','#b254c5','#ffc000']
HOT=[['6151','6311'],['6251','6311','6511'],['6311','6511'],['6111','6211','6451','6511','6651']]
LearnState=collections.namedtuple('learn_state','filename means stds probs key next_seq')


class DataUnpickler(pickle.Unpickler):
    """Only the documented tuple and NumPy storage types; no author code runs."""
    def find_class(self,module,name):
        allowed={('__main__','learn_state'):LearnState,('numpy','ndarray'):np.ndarray,('numpy','dtype'):np.dtype,
                 ('numpy.core.multiarray','_reconstruct'):np._core.multiarray._reconstruct,
                 ('numpy.core.multiarray','scalar'):np._core.multiarray.scalar}
        try:return allowed[module,name]
        except KeyError:raise ValueError(f'Unexpected source-data pickle type: {module}.{name}') from None


def data(ref):
    book=pd.ExcelFile(ref/'sample-44286_2023_2_MOESM12_ESM.xlsx')
    tables=[pd.read_excel(book,s).set_index('index') for s in ['mean_predictions','stdev_predictions','probability_predictions']]
    ids=[str(c) for c in tables[0].columns[2:]]
    arrays=[np.stack([t[t.agent==a].sort_values('rounds').iloc[:,2:].to_numpy(float) for a in range(1,5)]) for t in tables]
    _,full,_=DataUnpickler(io.BytesIO((ref/'sample-all_data_variants_unified.pkl').read_bytes())).load()
    unified=dict(zip(full[0].key,full[0].means));background=np.array([unified[k] for k in ids])
    summary=pd.read_csv(ref/'sample-Experiment_Summary.csv');choices=[ast.literal_eval(v) for v in summary.Sequences]
    return ids,*arrays,background,choices


def build(ref):
    ids,mean,std,prob,background,choices=data(ref);page=Page(1600,1599);rounds=np.arange(21)
    page.text('a',0,0,28,weight='bold')
    for a,color in enumerate(AGENTS):
        box=(88+a*374,42,362,253);x,y,w,h=box
        p=page.plot(f'a{a+1}',box,(0,20),(15,65),list(range(0,20,2)),[20,30,40,50,60],
            xlabel='Bayesian optimization round',ylabel="Agent’s landscape view (°C)" if a==0 else None,ylabels=a==0)
        for curve in mean[a].T:lines(p,rounds,curve,'#808080',.6*page.s,.09)
        for name in HOT[a]:lines(p,rounds,mean[a,:,ids.index(name)],color,3*page.s)
        page.add_plot(p,box);page.text(f'Agent {a+1}',x+w/2,16,20,align='center')
        page.key([('Thermostable enzyme',color),('Other sequences','#d3d3d3')],x+7,y+h-48,size=16)
    page.text('b',0,382,28,weight='bold');box=(138,421,418,276)
    p=page.plot('b',box,(0,20),(-.02,.95),list(range(0,21,2)),[0,.2,.4,.6,.8],xlabel='Bayesian optimization round',ylabel='Pearson correlation with\nunified landscape model')
    corrs=[]
    for a,color in enumerate(AGENTS):
        values=[np.corrcoef(v,background)[0,1] for v in mean[a]];corrs.append(values);lines(p,rounds,values,color,2.7*page.s)
    page.add_plot(p,box);page.key([(f'Agent {n+1}',c) for n,c in enumerate(AGENTS)],147,429,size=15,row=20)
    page.text('c',615,382,28,weight='bold');box=(721,421,418,276)
    p=page.plot('c',box,(0,20),(-.4,1),list(range(0,21,2)),[-.4,-.2,0,.2,.4,.6,.8,1],xlabel='Bayesian optimization round',ylabel='Pearson correlation between\nagents’ predicted landscapes')
    p.line([(0,0),(20,0)],stroke='#aaaaaa',stroke_width=1.8*page.s,stroke_dash=(8*page.s,5*page.s))
    pairs=[(a,b) for a in range(4) for b in range(a+1,4)];colors=['#fa7194','#bd9b24','#4abc29','#28b1ac','#379dfa','#ed51f3']
    for (a,b),color in zip(pairs,colors):lines(p,rounds,[np.corrcoef(x,y)[0,1] for x,y in zip(mean[a],mean[b])],color,2.7*page.s)
    page.add_plot(p,box);page.key([(f'A{a+1}–A{b+1}',c) for (a,b),c in zip(pairs,colors)],838,427,size=15,row=19,columns=3,colwidth=102)
    page.text('d',1194,382,28,weight='bold');box=(1282,421,277,276)
    p=page.plot('d',box,(22,60),(2,11.7),list(range(25,61,5)),[2,4,6,8,10],xlabel='Unified landscape model T₅₀ (°C)',ylabel='Average landscape uncertainty\nat round 20 (GP σ, °C)',tick_size=17,label_size=19)
    temps=np.linspace(background.min(),background.max(),100);uncertainties=[]
    for level in [4,6,8,10]:p.line([(22,level),(60,level)],stroke='#bbbbbb',stroke_width=.8*page.s)
    for a,color in enumerate(AGENTS):
        vals=[std[a,20,(background>t-5)&(background<t+5)].mean() for t in temps];uncertainties.append(vals);lines(p,temps,vals,color,2.7*page.s)
    page.add_plot(p,box);page.key([(f'A{n+1}',c) for n,c in enumerate(AGENTS)],1286,679,size=15,row=20,columns=4,colwidth=63)
    page.text('e',0,799,28,weight='bold');percentiles=[]
    for a in range(4):
        box=(89+a*374,840,362,250);x,y,w,h=box
        p=page.plot(f'e{a+1}',box,(0,20),(0,1),list(range(0,20,2)),[0,.2,.4,.6,.8,1],xlabel='Bayesian optimization round',ylabel='Percentile rank of\nchosen sequences' if a==0 else None,ylabels=a==0)
        eucb=prob[a]*(mean[a]-mean[a].min(axis=1,keepdims=True)+2*std[a]);traces=[]
        for vals,color in zip([eucb,mean[a],std[a],prob[a]],['#e92724','#1d7fba','#ff780e','#29a82f']):
            ranks=pd.DataFrame(vals.T).rank(pct=True).to_numpy().T
            v=[np.mean([ranks[r,ids.index(k)] for k in choices[r][a*3:(a+1)*3]]) for r in range(20)];traces.append(v);lines(p,np.arange(1,21),v,color,2.7*page.s)
        percentiles.append(traces);page.add_plot(p,box);page.text(f'Agent {a+1}',x+w/2,813,20,align='center')
        if a==3:page.key(list(zip(['Expected UCB','GP stability','GP uncertainty','GP Pₐctive'],['#e92724','#1d7fba','#ff780e','#29a82f'])),x+194,y+55,size=16,row=22)
    page.text('f',0,1180,28,weight='bold');ramp=i.ramp(['#e4ff7a','#ffe800','#ffbd00','#ffa000','#fc7f00'])
    for a in range(4):
        box=(140+a*375,1224,290,289);x,y,w,h=box
        p=page.plot(f'f{a+1}',box,(10,70),(.1,.9),[20,40,60],[.2,.4,.6,.8],xlabel='Predicted thermostability (°C)',ylabel='Predicted probability active' if a==0 else None)
        ucb=mean[a,20]+2*std[a,20];eucb=(ucb-ucb.min())*prob[a,20];order=np.argsort(eucb,kind='stable')
        p.scatter(zip(mean[a,20,order],prob[a,20,order]),size=7.5*page.s,color=[ramp(float(v/30)) for v in eucb[order]],stroke='none',raster=False)
        if a==3:
            p.colorbar(source=ramp,scale=i.linear((0,30)),corner='sw',length=95*page.s,
                       thickness=20*page.s,pad=7*page.s,plate=True,title='Expected\nUCB',
                       ticks=[0,30],tick_font_size=15*page.s,font_family=page.font)
        page.add_plot(p,box);page.text(f'Agent {a+1}',x+w/2,1197,20,align='center')

    return page,{'axes':15,'agents':4,'sequences':len(ids),'rounds':21,'background_correlations':corrs,
                'uncertainty_windows':len(temps),'chosen_percentiles':percentiles,
                'scatter_color':'author code: (mean + 2*std - min(mean + 2*std))*Pactive',
                'percentile_eucb':'author code: (mean - min(mean) + 2*std)*Pactive'}
