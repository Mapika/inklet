"""Native editable chart marks for the summary pies and published clusters."""
import math
import numpy as np
import pandas as pd

from anatomy import paths

BLUE='#668fb8';GOLD='#e6b93f';GRAY='#92918d';BLACK='#252525'


def circle_points(x,y,r,start=0,stop=360):
    return [(x+r*math.cos(math.radians(t)),y+r*math.sin(math.radians(t))) for t in np.linspace(start,stop,max(3,int((stop-start)*1.5)))]


def pie(page,x,y,black_end,gold_end,*,start=-54,male=True):
    ring=circle_points(x,y,49)
    page.nodes.append(paths([ring],'#f5f5f3',fill=True,name='pie-noise'))
    page.nodes.append(paths([[(x,y)]+circle_points(x,y,49,start,black_end)+[(x,y)]],BLACK,fill=True,name='pie-isomorphic'))
    page.nodes.append(paths([[(x,y)]+circle_points(x,y,49,black_end,gold_end)+[(x,y)]],GOLD,fill=True,name='pie-dimorphic'))
    page.nodes.append(paths([ring+[ring[0]]],'#7c9870' if male else '#bd418f',width=.75,name='pie-sex-outline'))


def draw_pies(page):
    # Literal rounded values visible in the reference; no new inference.
    # Connection-count pies: start/end angles preserve the published rotation.
    pie(page,241,777,35.28,40.68,male=True)
    pie(page,241,881,35.28,36.36,male=False)
    # Synapse-count pies use their remainder for the black sector so the three
    # rounded labels (female total 100.1%) do not create overlapping geometry.
    pie(page,557,777,397.80,415.44,start=90,male=True)
    pie(page,557,881,408.60,411.12,start=90,male=False)
    for text,x,y,color in [
        ('73.7%',200,762,BLACK),('24.8%',254,769,'white'),('1.5%',268,819,GOLD),
        ('74.9%',200,866,BLACK),('24.8%',254,879,'white'),('0.3%',267,925,GOLD),
        ('85.5%',516,764,'white'),('4.9%',573,779,GOLD),('9.6%',574,822,GRAY),
        ('88.6%',516,867,'white'),('0.7%',573,883,GOLD),('10.8%',572,928,GRAY),
    ]:page.text(text,x,y,10,color=color)
    for x in [365,681]:
        for y,height,pct in [(718,104,5.8 if x==365 else 5.5),(832,102,1.2 if x==365 else .8)]:
            page.rect(x,y,11,height,BLACK)
            h=height*pct/100;page.rect(x,y+height-h,11,h,GOLD)
    page.text('♀',190,823,26,color='#bd418f')
    page.text('♀',505,823,26,color='#bd418f')


def draw_clusters(page,data):
    frame=pd.read_feather(data/'communities.feather').set_index('community_id')
    order=[102,79,81,116,186,153,250,249,103,89,185,270]
    bands=[(1267,1283),(1285,1300),(1303,1318),(1320,1335),(1338,1353),(1355,1370),
           (1372,1388),(1390,1405),(1407,1422),(1425,1440),(1442,1457),(1460,1475)]
    records=[]
    def bar(y0,y1,counts,label):
        x=393; total=sum(counts)
        for count,color in zip(counts,[BLUE,GOLD,GRAY]):
            w=222*count/total
            if w:
                page.rect(x,y0,w,y1-y0,color,stroke='#111111',width=.5)
                if w>10:
                    # Centre the native text by its measured width.
                    s=str(count);page.text(s,x+w/2-len(s)*2.45,y0+(y1-y0-8)/2,9,color='white')
            x+=w
        records.append(dict(cluster=label,specific=counts[0],dimorphic=counts[1],isomorphic=counts[2],total=total))
    for label,(y0,y1) in zip(order,bands):
        values=frame.loc[label,'type_iod']
        bar(y0,y1,[int(values[str(k)] or 0) for k in (2,1,0)],label)
    for flag,(y0,y1),label in [(True,(1490,1507),'enriched-total'),(False,(1521,1538),'non-enriched')]:
        rows=frame.loc[frame.enriched.eq(flag),'type_iod']
        counts=[sum(int(values[str(k)] or 0) for values in rows) for k in (2,1,0)]
        bar(y0,y1,counts,label)
    return records
