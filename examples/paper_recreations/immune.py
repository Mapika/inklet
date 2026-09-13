"""Nature s41586-024-08477-8, Figure 4: all released daily data."""
import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
from canvas import Page,lines,runs

COUNTRIES=['Australia','Brazil','Canada','Denmark','France','Japan','Mexico','South Africa','Sweden','UK','USA']
BASE={'BA.5.all':'#f10b48','BQ.1.all':'#4864df','XBB.1.5.all':'#ff7e28','XBB.1.16.all':'#37b84b',
      'EG.5.1.all':'#9d16bc','EG.1.all':'#9e6526','BF.7.all':'#050505','BR.2.1':'#a93232',
      'XBF':'#ffd1ad','XBC.1.all':'#859107','HK.3':'#a80000','FE.1.all':'#dec0ff',
      'GK.1.all':'#36d0ef','BN.1.all':'#b7ed37','XBB.1.9.all':'#b4ffd5','BF.5.all':'#ef28ec',
      'EG.5.all':'#429e99','CH.1.all':'#ffb6d5'}


def build(ref):
    frame=pd.ExcelFile(ref/'immune-41586_2024_8477_MOESM5_ESM.xlsx')
    page=Page(1600,1608);records=[]
    dates=[dt.datetime(2022+(m>=13),(m-1)%12+1,1) for m in range(11,23)]
    origin=dt.datetime(2022,10,1);ticks=[(x-origin).days for x in dates]
    fmt={v:f'{d.day} {d.strftime("%b")}. {d.year}' for v,d in zip(ticks,dates)}
    for idx,country in enumerate(COUNTRIES):
        df=pd.read_excel(frame,f'Data_4{chr(97+idx)}');x=(pd.to_datetime(df.iloc[:,0],errors='coerce')-origin).dt.days.to_numpy()
        for c in df.columns[1:]:df[c]=pd.to_numeric(df[c],errors='coerce')
        freqmax=float(df.filter(regex='_proportion$').max().max())
        bounds=df.filter(regex='_gamma_(min|max)$')
        low,high=float(bounds.min().min()),float(bounds.max().max());pad=(high-low)*.05
        limits=(low-pad,high+pad)
        col,row=idx%3,idx//3;left=65+col*535;top=24+row*389
        freq_box=(left,top,441,143);fit_box=(left,top+191,441,143)
        page.text(chr(97+idx),col*535,top-24,27,weight='bold');page.text(country,left+220,top-18,16,align='center')
        p=page.plot(f'{chr(97+idx)}-frequency',freq_box,(0,364),(-freqmax*.05,freqmax*1.05),ticks,[0,25,50] if idx in (0,3,5,8,9) else [0,50],ylabel='Lineage frequency',xlabels=False,frame=False,tick_size=15,label_size=16)
        low,high=limits
        if idx==3:low,high=-.19,.22
        yticks=[0,.2] if idx==3 else ([-.2,0] if idx==5 else [-.1,0,.1])
        yticks=[v for v in yticks if low<=v<=high]
        q=page.plot(f'{chr(97+idx)}-fitness',fit_box,(0,364),(low,high),ticks,yticks,ylabel='Relative fitness',xlabels=idx>=8,rotate=45,xformat=lambda v:fmt.get(int(v),''),frame=False,tick_size=15,label_size=16)
        q.line([(0,0),(364,0)],stroke='#666666',stroke_width=.65*page.s,stroke_dash=(2*page.s,2*page.s))
        groups=[c[:-11] for c in df if c.endswith('_proportion')];extra=[]
        for g in groups:
            # Brazil annotates the grouped BE.9 and XBB.1.18.1 lineages in column names.
            normalized=g.split('+')[0]
            color=BASE.get(normalized)
            if color is None:raise ValueError(f'unmapped lineage: {g}')
            yy=df[g+'_proportion'].to_numpy();lines(p,x,yy,color,3*page.s)
            lo,hi,mean=(df[g+suffix].to_numpy() for suffix in ['_gamma_min','_gamma_max','_gamma_mean'])
            for xx,aa,bb in runs(x,lo,hi):q.band(xx,aa,bb,fill=color,opacity=.4,stroke='none')
            lines(q,x,mean,color,.8*page.s)
            if normalized not in list(BASE)[:7]:extra.append((normalized.replace('.all','.X'),color))
            records.append(dict(country=country,lineage=g,frequency_samples=int(np.isfinite(yy).sum()),fitness_samples=int(np.isfinite(mean).sum())))
        page.add_plot(p,freq_box);page.add_plot(q,fit_box)
        if extra:
            order={0:['BR.2.1','XBC.1.X','XBF','HK.3'],1:['FE.1.X','GK.1.X'],3:['BN.1.X','XBB.1.9.X'],5:['BF.5.X','EG.5.X','HK.3']}.get(idx,[v[0] for v in extra])
            extra.sort(key=lambda item:order.index(item[0]))
            page.key(extra,left+(100 if idx==0 else 270),top+12,size=15,row=25,columns=2 if idx==0 else 1,colwidth=110)
    page.key([(g.replace('.all','.X'),BASE[g]) for g in ['BA.5.all','XBB.1.16.all','BQ.1.all','XBB.1.5.all','EG.5.1.all','EG.1.all','BF.7.all']],1290,1260,size=16,row=27,patch=True)
    return page,{'daily_series':records,'countries':11,'axes':22,'missing_values':'preserved as gaps; no interpolation','source_workbook':'immune-41586_2024_8477_MOESM5_ESM.xlsx'}
