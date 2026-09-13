"""Independently authored charts and diagrams. No bitmap input or tracing.

Literal arrays below are approximate manual readings of the supplied figures;
computed arrays come from the released connectome tables. All are exported.
"""
import json, math
import numpy as np
import pandas as pd
import inklet as i
from canvas import BLUE,GOLD,GREEN,PINK,BLACK,GRAY
from anatomy import paths
from inklet.core import RectPrim, TextPrim
from layout import LETTERS

TRANSCRIBED={
 'alpn_types':'VA1v_vPN M_lvPNm45 MZ_lv2PN M_vPNml67 VA1d_vPN M_vPNml76 M_vPNml63 VL2a_vPN AL-AST1 M_l2PN3t18 M_lvPNm44 M_vPNml55 DA1_lPN ALON3 VP5+VP3_l2PN VP3+_l2PN M_lvPNm46 M_adPNm5 M_adPNm7 CB3447'.split(),
 'alpn_specific':[20,38,35,9,8,5,8,17,7,13,13,12,11,10,4,2,2,1,1,5],
 'alpn_dimorphic':[36,9,12,30,23,31,20,7,14,5,3,2,2,3,9,11,10,10,10,5],
 'alpn_female':[31,8,2,1,10,1,14,2,17,2,7,2,0,0,21,14,0,9,14,1],
 'radar_high':[.9,.16,.16,.30,.51], 'radar_rest':[.3,.31,.40,.35,.45],
 'gustatory_totals':[[.35,0],[.50,.70],[.32,0],[.45,.85],[0,6.2],[5.0,6.1]],
 'grn_types':'PhG13 LB1a PhG9 LB2b PhG16 LB2c PhG5 PhG4 LB2d PhG12 PhG10 PhG15 LgAG8 LgAG3 LgAG1 LgAG4 LgLG6 LgLG5 LgLG8 LgLG7 LgLG2 WG1 LgLG1a WG4 WG2 LgLG1b WG3'.split(),
 'grn_specific':[15,1,1,1,0,0,0,0,0,0,0,0,3,1,0,0,43,32,9,6,0,0,0,0,0,0,0],
 'grn_dimorphic':[0,4,5,2,1,1,1,1,0,0,0,0,0,0,0,0,5,12,27,22,24,14,9,6,5,4,3],
 'grn_female':[9,0,0,0,0,0,0,0,0,0,0,0,2,3,1,1,None,None,None,None,None,None,None,None,None,None,None],
 'hierarchy_counts':[2,6,11,18,23,40,311], 'hierarchy_enriched':[1,1,1,1,2,4,12],
 'q_fractions':[[.285,.013,0,.702],[.554,.111,.174,.161]],
 'vpoen_bars':[[0,1],[0,1],[.48,.52],[.28,.72]],
 'pn_total':[187,189,188,190,187], 'pn_pheromone':[25,26,26,28,28]
}

def furniture(p):
    p.text('INKLET',142,114,30,weight='bold',color='#408fb1')
    title='Chemosensory dimorphism' if p.name=='chemosensory' else 'Connection and network dimorphism'
    p.text(title,142,158,24,weight='bold')
    p.text('Independent recreation · real anatomy · approximate and recomputed charts',142,193,12,color='#555')
    for letter,(x,y) in LETTERS[p.name].items():p.text(letter,x,y,20,weight='bold',name='panel-'+letter)
    if p.name=='chemosensory':
        p.label('olfaction',181,234,19);p.label('gustation',180,957,19)
        notes=[
            'A, C, E, I, J, M: released anatomy; reconstructed cameras and subsets. B: released bilateral ORN counts.',
            'D, F, G, H, K, L: approximate reference readings. G: r and fitted line recomputed from the displayed approximate points.',
            'C, F: sampled local synapses. E: contextual locators are separate from arbor close-ups. H: no bootstrap reanalysis.',
            'L: missing female observations are marked; no-data rows are not measured zeros.'
        ]
    else:
        notes=[
            'A, G, H, K, M, O: recomputed release-table views; selections and aggregations differ from the reference.',
            'D, F, I, J, Q: reference transcriptions/approximations. B, P: released anatomy with reconstructed cameras.',
            'K: male locations colored by relative connection weight; not a male–female spatial-density measurement.',
            'L: illustrative nested partitions; only the final community memberships are from the released analysis.'
        ]
    p.text('Recreation notes',142,1585,14,weight='bold')
    for k,line in enumerate(notes):p.text(line,142,1608+k*18,11,color='#444')
    p.text('Source: Cell (2026), doi:10.1016/j.cell.2026.08.015 · Full methods and audit resolutions in the source bundle.',142,1700,11,color='#555')


def legend(p,items,x,y,size=9,step=110):
    for k,(label,color) in enumerate(items):p.rect(x+k*step,y+3,9,7,color);p.text(label,x+12+k*step,y,size)

def chemosensory(p,a,d):
    t=TRANSCRIBED
    # B: keyed bilateral counts from the pinned male/female annotations.
    from chart_data import orn_counts
    rows=orn_counts(a.data,p.out/'chart-data');n=len(rows)
    male=np.array([r['male'] for r in rows]);female=np.array([r['female'] for r in rows])
    q=p.axes(209,484,565,118,(0,n-1),(0,220),[],[0,50,100,150,200],ylabel='# of neurons',size=9)
    for k,(m,f) in enumerate(zip(male,female)):p.line(q([k,k],[m,f]),'#b0b0ac',.7)
    p.dots(q(np.arange(n),male),GREEN,3);p.dots(q(np.arange(n),female),PINK,3)
    for k,row in enumerate(rows):p.text(row['glomerulus'],q([k],[0])[0,0]-3,609,9,angle=-90)
    legend(p,[('Male CNS',GREEN),('FAFB/FlyWire',PINK)],260,487,11,90)
    p.text('glomerulus · bilateral counts from released annotations',487,647,9,align='center')
    # C: count proportion and actual-ORN legend.
    p.text('proportion of RNs',754,238,12)
    p.line([(744,276),(880,276)],BLACK,.6)
    for v in [0,50,100]:p.text(f'{v}%',744+v*1.36,260,9,align='center')
    p.rect(744,284,101,13,'#aaa');p.rect(845,284,34,13,'#ebc0d2')
    p.text('pheromone\nresponsive',882,283,10);p.text('Left Antennal Lobe',754,313,10)
    p.line([(729,310),(883,310),(883,464),(729,464),(729,310)],BLACK,.8,dash=(2,3))
    p.text('pheromone-responsive RNs',551,430,11)
    legend(p,[('DA1','#9b71dd'),('VA1d','#c3e37e')],562,449,11,77)
    legend(p,[('VA1v','#86d5d9'),('DL3','#d69cdf')],562,466,11,77)
    # D: stacked neuronal counts.
    q=p.axes(1007,250,177,154,(0,5),(0,195),[],[0,50,100,150],ylabel='# of pheromone vs\nnon-pheromone ALPNs',size=10)
    for k,(total,ph) in enumerate(zip(t['pn_total'],t['pn_pheromone'])):
        x=1017+k*36;p.rect(x,404-total/195*154,22,(total-ph)/195*154,'#aaa');p.rect(x,404-ph/195*154,22,ph/195*154,'#ebc0d2')
    for k,label in enumerate(['hemibrain R','FlyWire L','FlyWire R','Male CNS L','Male CNS R']):p.text(label,990+k*36,421,9,angle=-45)
    p.line([(1017,247),(1111,247)],BLACK,2);p.line([(1125,247),(1184,247)],BLACK,2)
    p.text('♀',1063,223,21);p.text('♂',1155,223,21)
    # E: explicit authored edge diagram and counts.
    p.text('♀',887,486,24);p.text('♂',999,486,24);p.label('MZ lv2PN',920,648,13)
    p.text('DA1 ORNs',1121,490,11)
    for x,col,txt in [(1121,PINK,'L: 0, R: 0'),(1167,GREEN,'L: 498, R: 762')]:
        p.ellipse(x,516,9,9,'#b7b7b7','none');p.ellipse(x,645,9,9,col,'none');p.arrow([(x,528),(x,627)],'#aaa',1.4 if col==PINK else 2,10,dash=(3,4) if col==PINK else None)
        p.text(txt,x-12,548,9,angle=-90)
    p.text('# synapses from DA1 ORNs',1092,512,10,angle=-90);p.text('MZ_lv2PN',1119,663,10)
    # F: diverging percentages, each mark derived from explicit values.
    x0=307;y0=677;dy=12.15;scale=1.72
    for k,label in enumerate(t['alpn_types']):
        y=y0+k*dy;p.text(label,239,y,8,align='right')
        p.rect(x0-t['alpn_female'][k]*scale,y,t['alpn_female'][k]*scale,10,BLUE if k==1 else GOLD)
        p.rect(x0,y,t['alpn_dimorphic'][k]*scale,10,GOLD)
        p.rect(x0+t['alpn_dimorphic'][k]*scale,y,t['alpn_specific'][k]*scale,10,BLUE)
    p.line([(245,672),(245,922),(410,922)],BLACK,.8);p.line([(307,672),(307,922)],BLACK,1)
    for x in [301,314]:p.line([(x,672),(x,922)],BLACK,.5,dash=(2,2))
    for v in [-20,0,20,40,60]:p.text(str(abs(v)),x0+v*scale,926,10,align='center')
    p.text('% output',306,942,12,align='center');p.text('♀',289,652,20);p.text('♂',347,652,20)
    legend(p,[('to sex-spec. types',BLUE)],337,872,10);legend(p,[('to dimorphic types',GOLD)],337,887,10)
    p.text('··· means across all ALPNs',337,902,9)
    p.line([(438,741),(558,741),(558,862),(438,862),(438,741)],BLACK,.8,dash=(2,3));p.text('Lateral Horn',476,725,10)
    from refined_data import local_synapses
    observed=local_synapses(a.data,p.out/'chart-data')
    warped=a.warp(observed['lh_xyz_nm']);v=warped[:,:2]
    lo,hi=np.quantile(v,[.005,.995],axis=0)
    scale=min(106/(hi[0]-lo[0]),109/(hi[1]-lo[1]));xy=(v-(lo+hi)/2)*scale+[498,802]
    valid=np.all((xy>[440,743])&(xy<[555,859]),axis=1)
    for flag,col in [(0,'#a5a5a0'),(2,BLUE),(1,GOLD)]:
        selected=xy[valid & (observed['lh_category']==flag)]
        if flag==0:selected=selected[::2]
        p.dots(selected,col,1.25 if flag else .65,.9 if flag else .32)
    # G: each marker's approximate position and visual encodings are explicit.
    q=p.axes(626,678,232,229,(0,105),(0,55),[0,25,50,75,100],[0,20,40],xlabel='Σ % Pheromone Input\n(Direct & Two-Hop)',ylabel='% Output\nDimorphic/Sex-Specific',size=10)
    xy=np.array([[75,53],[88,43],[62,43],[7,39],[74,34],[65,30],[7,24],[100,13],[10,17],[21,16],[24,9],[48,15],[18,3],[14,1],[40,4],[22,0],[15,2],[12,4],[9,3],[8,1],[6,2],[4,0],[82,3],[89,2],[93,4],[81,3],
        [4,12],[6,10],[7,11],[8,9],[3,7],[5,6],[6,4],[4,3],[5,2],[7,1],[9,2],[11,1],[13,5],[15,4],[18,2],[21,3],[87,2],[92,1],[95,3]])
    # Shapes read from visible reference markers; colors indicate pheromone response.
    shapes=['s','o','s','s','s','s','s','o','o','o','s','s','o','o','o','s','o','o','o','o','o','o','s','o','o','s']+['o']*19
    filled={0,4,7,22,23,24,25,42,43,44}
    pheromone={0,1,2,4,5,7,8,9,10,11,14,22,23,24,25,42,43,44}
    # Reference reconstructions are exported with their per-point visual encoding.
    (p.out/'chart-data/scatter-g.json').write_text(json.dumps({'method':'Manually reconstructed reference coordinates and marker appearance; not recovered raw data.','points':[{'x':float(x),'y':float(y),'shape':shapes[k],'filled':k in filled,'pheromone':k in pheromone} for k,(x,y) in enumerate(xy)]},indent=2))
    slope,intercept=np.polyfit(xy[:,0],xy[:,1],1);correlation=float(np.corrcoef(xy.T)[0,1])
    p.line(q([0,100],intercept+slope*np.array([0,100])),'#aaa',1,dash=(4,4))
    (p.out/'chart-data/scatter-g-statistics.json').write_text(json.dumps({'pearson_r':correlation,'slope':float(slope),'intercept':float(intercept),'method':'OLS and Pearson correlation of displayed approximate coordinates; not paper reanalysis.'},indent=2))
    for k,(x,y) in enumerate(xy):p.dots(q([x],[y]),'#bd7ac4' if k in pheromone else '#d3d3d0',3.8,.85,shape=shapes[k],filled=k in filled)
    # Label placements and leaders are authored independently of data coordinates.
    for k,label,tx,ty in [(0,'VA1v_vPN',764,698),(1,'M_lvPNm45',804,722),(2,'MZ_lv2PN',748,741),(3,'M_vPNml67',700,763),(4,'VA1d_vPN',794,769),(5,'M_vPNml63',751,819),(6,'VL2a_vPN',675,812),(7,'DA1_lPN',817,854)]:
        point=q([xy[k,0]],[xy[k,1]])[0]
        label_node=i.tag(label,size=9,font='Arimo',pad=(1,.5),fill='white',color=BLACK,radius=.5,markup=False)
        box=label_node.bbox;label_node=label_node.translated(tx-box.x1,ty-box.y0)
        target=i.circle(width=.3,height=.3).translated(*point)
        p.nodes.append(i.connect(target,label_node,kind='line',standoff=.5,stroke='#8a7c8c',stroke_width=.6))
        p.nodes.append(label_node);p.labels+=1
    p.text(f"r = {correlation:.2f} · approximate points",635,680,9)
    # Rounded legend with explicit row spacing and compact group headings.
    x,y,w,h,r=874,718,87,190,8;outline=[]
    for cx,cy,start in [(x+w-r,y+r,-90),(x+w-r,y+h-r,0),(x+r,y+h-r,90),(x+r,y+r,180)]:
        theta=np.radians(np.linspace(start,start+90,10));outline.extend(np.c_[cx+r*np.cos(theta),cy+r*np.sin(theta)])
    p.poly(outline,'white');p.line(outline+[outline[0]],'#888',.8)
    p.text('NT type',881,726,9)
    for row,(shape,label) in enumerate([('o','excitatory'),('s','inhibitory'),('d','unclear')]):
        yy=747+row*15;p.dots([(884,yy)],'#333',3.5,shape=shape,filled=False);p.text(label,894,yy-6,8)
    p.text('ALPN morphology',881,795,8)
    for yy,fill,label in [(817,False,'mPN'),(833,True,'uPN')]:p.dots([(884,yy)],'#333',3.6,filled=fill);p.text(label,894,yy-6,8)
    p.text('Pheromone ALPN',881,855,8)
    for yy,col,label in [(877,'#bd7ac4','pheromone'),(895,'#d3d3d0','non-pheromone')]:p.dots([(883,yy)],col,3.7);p.text(label,891,yy-5,7)
    # H: authored radar polygons from approximate radial values.
    cx,cy,r=1100,784,70;angles=np.linspace(-np.pi/2,3*np.pi/2,6)[:-1]
    for f in [.2,.4,.6,.8,1]:p.ellipse(cx,cy,r*f,r*f,'none','#bbb',.45)
    for z in angles:p.line([(cx,cy),(cx+r*np.cos(z),cy+r*np.sin(z))],'#bbb',.5)
    for vals,col in [(t['radar_high'],BLUE),(t['radar_rest'],'#555')]:
        pts=np.c_[cx+r*np.array(vals)*np.cos(angles),cy+r*np.array(vals)*np.sin(angles)];p.poly(pts,col,.18);p.line(np.vstack([pts,pts[0]]),col,2);p.dots(pts,col,3)
    for label,x,y in [('pheromones',1100,698),('hygro/\nthermo',1191,745),('aversive',1150,845),('attractive',1040,845),('unclear',1010,754)]:p.text(label,x,y,11,align='center')
    legend(p,[('high sex-specific/dimorphic output',BLUE)],983,886,10);legend(p,[('remaining (reference approximation)', '#555')],983,909,10)
    # J: native headings for six reconstructed arbors.
    for label,x,y in [('labellar bristle',388,985),('pharyngeal sensilla',477,985),('taste peg',594,985),('leg bristle (ascending)',384,1114),('leg bristle (local)',494,1114),('wing bristle',603,1114)]:p.label(label,x,y,10)
    # K: aggregate output chart. Neutral tails represent the cropped axis range.
    q=p.axes(790,986,106,218,(0,12.5),(0,1),[0,10],[],xlabel='% output · 0–12.5%',size=9)
    for k,(name,yy) in enumerate(zip(['taste peg','pharyngeal sensillum','labellar bristle','leg bristle (ascending)','wing bristle','leg bristle (local)'],[997,1022,1047,1107,1166,1190])):
        p.text(name,785,yy-3,10,align='right');b,g=t['gustatory_totals'][k]
        for lo,hi,col in [(0,12.5,'#e4e4e4'),(0,b,BLUE),(b,b+g,GOLD)]:
            box=q.region(lo,0,hi,1);p.rect(box.x0,yy,box.width,9,col)
    for label,y in [('brain',981),('ascending',1088),('VNC (lower bound)',1140)]:p.text(label,842,y,10,align='center')
    p.text('♂',715,965,24)
    legend(p,[('sex-specific',BLUE),('sexually dimorphic',GOLD),('isomorphic','#ddd')],677,1241,10,99)
    # L: subtype-specific output bars.
    x0=1039;dy=7.55
    for k,label in enumerate(t['grn_types']):
        yy=986+k*dy+(13 if k>=12 else 0)+(14 if k>=16 else 0);p.text(label,1005,yy-1,8,align='right')
        b,g,f=[t[key][k] for key in ['grn_specific','grn_dimorphic','grn_female']]
        if f is not None:p.rect(x0-f*2.5,yy,f*2.5,6,BLUE)
        p.rect(x0,yy,b*2.5,6,BLUE);p.rect(x0+b*2.5,yy,g*2.5,6,GOLD)
    p.line([(1010,983),(1010,1214),(1166,1214)],BLACK,.8);p.line([(1039,983),(1039,1214)],BLACK,1)
    for v in [-10,0,10,20,30,40,50]:p.text(str(abs(v)),x0+v*2.5,1218,10,align='center')
    p.text('no\ndata',1024,1157,8,align='center',color='#777')
    p.text('% output',1100,1236,11,align='center');p.text('♀   ♂',1019,963,22)
    legend(p,[('to sex-specific types',BLUE)],1075,1021,10);legend(p,[('to dimorphic types',GOLD)],1075,1040,10)
    p.text('··· means across all GRNs\n      (per region)',1075,1059,9)
    for xx in [1043,1063]:p.line([(xx,1130),(xx,1211)],BLACK,.6,dash=(3,3))
    # M: complete native labels and quantitative color key.
    p.text('Top downstream partners of GRN subclasses',192,1265,14)
    for k,label in enumerate(['pharyngeal sensilla','labellar bristle','leg bristle (ascending)','leg bristle (local)','wing bristle']):
        p.label(label,201+k*188,1293,12)
        for j,s in enumerate(['sex-specific/\ndimorphic','isomorphic']):p.text(s,218+k*188+j*87,1516,10,align='center')
    ramp=['#6f397b','#b55c68','#ed9b45','#f1c555']
    ramp=i.ramp(ramp)
    for k in range(100):p.rect(1118,1373+k*1.3,14,1.4,ramp(1-k/99))
    p.text('% output\nof sensory class',1138,1345,11,align='center')
    for v,y in [(6,1372),(4,1435),(2,1495)]:p.text(str(v),1144,y,11)

def dimorphism(p,a,d):
    # A: exact cumulative weights from released data.
    q=p.axes(207,263,181,159,(1,1000),(1e4,4e6),[1,10,100,1000],[1e4,1e5,1e6],xlabel='weight (♂)',ylabel='no. of connections (cum.)',logx=True,logy=True,size=9)
    for k,col in enumerate([BLACK,GOLD,BLUE]):
        yy=np.clip(d[f'cdf{k}'],1e4,4e6);p.line(q(d['weight_grid'],yy),col,1.2)
        p.dots(q([1000],[yy[-1]]),col,3.6);p.text(f"{100*d[f'cdf{k}'][-1]/sum(d[f'cdf{j}'][-1] for j in range(3)):.1f}%",380,q([1000],[yy[-1]])[0,1]+5,10,align='right',color=col)
    p.text('noise verdict',197,222,10);p.text('non-noise verdict',305,222,10)
    p.text(f"{d['noise_connection_pct']:.1f}% of connections\n{d['noise_synapse_pct']:.1f}% of synapses",172,237,9)
    p.text(f"{100-d['noise_connection_pct']:.1f}% of connections\n{100-d['noise_synapse_pct']:.1f}% of synapses",283,237,9)
    for k,(label,col) in enumerate([('isomorphic',BLACK),('dimorphic',GOLD),('sex-specific',BLUE)]):p.dots([(404,426+k*12)],col,3);p.text(label,411,421+k*12,9)
    p.text('cell types',398,407,9)
    # B: live text around real vpoEN arbors.
    p.text('vpoEN (isomorphic)',457,231,12);p.text('♂',477,256,25,color=GREEN);p.text('♀',516,256,25,color=PINK)
    p.text('frontal\ndorsal',448,350,10,color='#777')
    # C: connection identities, arrows, and explicit observed weights.
    for x,symbol in [(779,'♂'),(805,'♀')]:p.text(symbol,x,242,22,align='center',valign='center',bounds='ink')
    alignment_checks=[]
    for label,sub,y in [('AVLP569','(female-specific)',270),('vpoEN','(isomorphic)',339),('aSP10C_a','(dimorphic)',410)]:
        p.text(label,759,y,12,align='right');p.text(sub,759,y+15,9,align='right')
    for x in [779,805]:
        for y,label,col in [(278,'s',BLUE),(346,'i',BLACK),(422,'d',GOLD)]:
            p.ellipse(x,y,9,9,col if not(x==779 and y==278) else 'white',col,.7)
            node=p.text(label,x,y,15,color='white' if not(x==779 and y==278) else BLUE,align='center',valign='center',bounds='ink')
            alignment_checks.append({'panel':'C','text':label,'target':[x,y],'actual':[node.bbox.center.x,node.bbox.center.y]})
        p.arrow([(x,290),(x,335)],GOLD,1.5,7,dash=(3,3) if x==779 else None);p.arrow([(x,358),(x,405)],GOLD,1.5,7)
    for s,x,y in [('0',755,303),('23',819,303),('420',750,375),('237',813,375)]:p.text(s,x,y,10)
    p.text('connection-level\ndimorphism',835,257,12)
    p.line([(838,286),(843,286),(843,335),(838,335)],GRAY,.8)
    p.text('connection\nby definition',857,295,10);p.text('dimorphic',857,319,10,color=GOLD)
    p.line([(838,353),(843,353),(843,405),(838,405)],GRAY,.8)
    p.text('connection\npotentially…',857,361,10);p.text('dimorphic',857,386,10,color=GOLD)
    # D: center visible glyphs within measured header/value rectangles.
    for label,y in [('vpoEN',253),('aSP10C_a',284)]:
        p.text(label,1016,y,11,align='right',valign='center',bounds='ink')
        p.ellipse(1024,y,2.5,2.5,BLACK,'none')
    p.arrow([(1024,258),(1024,279)],BLACK,1,4)
    for x,symbol,color in [(1084,'♂',GREEN),(1160,'♀',PINK)]:
        p.text(symbol,x,235,20,color=color,align='center',valign='center',bounds='ink')
    def centered(text,cx,cy,size=9,color=BLACK):
        node=p.text(str(text),cx,cy,size,color=color,align='center',valign='center',bounds='ink',line_align='center')
        alignment_checks.append({'panel':'D','text':str(text),'target':[cx,cy],'actual':[node.bbox.center.x,node.bbox.center.y]})
    def cells(x,y,labels,values,tint):
        table=i.value_table([values],headers=labels,font='Arimo',font_size=9.5,header_size=9,
                            pad=(2,1),min_cell_width=35,min_cell_height=15.5,
                            header_fill=tint,fill='white',color=BLACK,stroke='#aaa',stroke_width=.4)
        p.nodes.append(table.translated(x+table.width/2,y+table.height/2));p.labels+=4
        for k,label in enumerate(labels):
            for key,text in [(f'header-{k}',label),(f'cell-0-{k}',str(values[k]))]:
                at=table.anchor_point(key)+i.Vec2(x+table.width/2,y+table.height/2)
                placed=[v for v in i.resolve(table).values() if isinstance(v.diagram.prim,TextPrim) and v.diagram.prim.text==text]
                actual=min(placed,key=lambda v:(v.bbox.center-table.anchor_point(key)).length).bbox.center+i.Vec2(x+table.width/2,y+table.height/2)
                alignment_checks.append({'panel':'D','text':text,'target':[at.x,at.y],'actual':[actual.x,actual.y]})
    for x,values,color in [(1049,[202,218],'#e2ebdd'),(1125,[107,130],'#f2dbe9')]:cells(x,246,['left','right'],values,color)
    for x in [1084,1160]:p.arrow([(x,280),(x,298)],BLACK,.6,3)
    centered('scale\nweights',1122,289,8.5)
    for x,values,color in [(1049,[159.6,172.2],'#e2ebdd'),(1125,[107,130],'#f2dbe9')]:cells(x,301,['left','right'],values,color)
    for x in [1084,1160]:p.arrow([(x,335),(x,350)],BLACK,.6,3)
    centered('square\nroot',1122,343,8.5)
    for x,values,color in [(1049,[12.9,.35],'#e2ebdd'),(1125,[10.9,.75],'#f2dbe9')]:cells(x,353,['mean','std'],values,color)
    p.line([(1084,387),(1084,391),(1160,391),(1160,387)],BLACK,.6)
    p.arrow([(1122,391),(1122,399),(1078,399),(1078,405)],BLACK,.6,3)
    centered('t-statistics',1175,394,8.5)
    cells(1043,408,['t','p'],[3.44,.08],'#eee')
    p.arrow([(1116,429.5),(1173,429.5)],BLACK,.6,3)
    centered('FDR\ncorrection',1144,415,8.5)
    p.rect(1177,408,30,31,'#eee');centered('p',1192,415,9)
    p.rect(1177,423,30,13,'white','#b66',.7);centered('.55',1192,429.5,9.5)
    centered('connection\nisomorphic',1192,450,8.5)
    (p.out/'chart-data/text-alignment.json').write_text(json.dumps(alignment_checks,indent=2))
    # E: measured boxes and connectors attached to their boundaries.
    def box(text,x,y,w,h,fill='#e9e9e9',color=BLACK):
        node=i.tag(text,size=10,font='Arimo',pad=(5,4),fill=fill,color=color,radius=1,markup=False)
        node=node.translated(x+w/2-node.bbox.center.x,y+h/2-node.bbox.center.y)
        p.nodes.append(node);p.labels+=1
        return node
    threshold=box('conn. weight >\nnoise threshold',179,476,94,35)
    iso_types=box('conn. between\nisomorphic types',326,476,109,35)
    discard=box('discard',190,558,73,26,'white')
    b=discard.bbox;p.line([(b.x0,b.y0),(b.x1,b.y0),(b.x1,b.y1),(b.x0,b.y1),(b.x0,b.y0)],BLACK,.7,dash=(2,2))
    p.text('~80% of connections\n~10% of synapses',183,593,9)
    specific=box('conn. involves\nsex-specific type(s)',347,538,128,35)
    test=box('sex difference ≥ 30%\nand p ≤ 0.1',296,602,149,34)
    iso=box('isomorphic\nconnection',175,664,74,29,BLACK,'white')
    dim=box('dimorphic\nconnection',367,664,73,29,GOLD,BLACK)
    for source,target,via,label,x,y in [
        (threshold,iso_types,[],'yes',285,479),
        (threshold,discard,[],'no',206,516),
        (iso_types,iso,[(278,530),(278,677)],'yes',304,517),
        (iso_types,specific,[],'no',418,520),
        (specific,test,[],'no',376,581),
        (specific,dim,[(465,591),(465,679)],'yes',435,581),
        (test,dim,[],'yes',400,641),
        (test,iso,[(318,653),(318,680)],'no',322,641)]:
        p.nodes.append(i.connect(source,target,waypoints=via,arrow_size=4,standoff=1,stroke=BLACK,stroke_width=.8))
        p.label(label,x,y,10,fill='white')
    p.text('t-statistics',298,584,11,color='#999')
    # F: proportions transcribed from the worked example.
    q=p.axes(520,503,75,168,(0,1),(0,1),[],[0,.2,.4,.6,.8,1],ylabel='fraction of synapses',size=9)
    p.text('vpoEN',539,472,13);p.text('inputs',521,488,10,color='#73708c');p.text('outputs',563,488,10,color='#a26e68')
    for k,(gold,black) in enumerate(TRANSCRIBED['vpoen_bars']):
        x=527+k*15+(11 if k>=2 else 0);p.rect(x,503,11,168*gold,GOLD);p.rect(x,503+168*gold,11,168*black,BLACK)
        p.text('♂' if k%2==0 else '♀',x-1,680,17)
    p.text('in dimorphic\nconnections',608,503,10,color=GOLD,angle=-90);p.text('in isomorphic\nconnections',608,591,10,angle=-90)
    # G: released numeric edge sample; log axes and corrected-p categories.
    p.rect(690,480,14,195,'#ededed');p.rect(704,675,176,13,'#ededed')
    q=p.axes(704,480,176,195,(.3,1e5),(.3,1e5),[1,100,10000],[1,100,10000],xlabel='weight ♂ (scaled)',ylabel='weight ♀',logx=True,logy=True,size=8)
    s=d['scatter'];xy=q(np.maximum(s[:,0],.3),np.maximum(s[:,1],.3))
    xy[s[:,0]==0,0]=697;xy[s[:,1]==0,1]=682
    inside=np.all((xy>=[690,480])&(xy<=[880,688]),axis=1)
    for low,high,col in [(.1,2,'#aaa'),(.05,.1,'#81b89b'),(.01,.05,'#d3b249'),(-1,.01,'#c77276')]:
        flag=inside&(s[:,2]>low)&(s[:,2]<=high);p.dots(xy[flag],col,.6,.55)
    p.line(q([1,1e5],[1,1e5]),BLACK,.7)
    for factor in [.7,1.3]:p.line(q([1,7e4],[factor,7e4*factor]),BLACK,.5,dash=(2,2))
    p.text('type connections · stratified sample',704,463,10)
    p.text('0',697,692,8,align='center');p.text('0',685,678,8)
    p.text('zeros',655,685,8,color='#777')
    p.rect(830,573,46,60,'white','#ddd',.4);p.text('p-values\nFDR corrected',834,575,7)
    for k,(label,col) in enumerate([('> 0.1','#aaa'),('≤ 0.1','#81b89b'),('≤ 0.05','#d3b249'),('≤ 0.01','#c77276')]):p.text(label,836,594+k*9,7,color=col)
    # H: exact empirical cumulative distributions.
    q=p.axes(955,490,178,177,(1,0),(0,1),[1,.8,.6,.4,.2,0],[0,.2,.4,.6,.8,1],xlabel='f = max(dimorphic input, output fraction)',ylabel='fraction of types (cumulative)',size=9)
    h_curves=[]
    for flag,col in [(1,GOLD),(0,BLACK)]:
        for prefix,dash in [('type',None),('expr',(1,2))]:
            f=d[prefix+'_fraction_'+str(flag)];grid=np.linspace(0,1,201)
            y=1-np.searchsorted(f,grid,side='left')/max(len(f),1)
            points=q(grid,y);p.line(points,col,1,dash=dash);h_curves.append(points)
    p.text('Cell-type connectivity',955,469,11)
    color_key=i.legend([('dimorphic / sex-specific',GOLD),('isomorphic',BLACK)],
                       font_size=8.5,swatch=8,gap=5,row_gap=2,markup=False,text_fill=BLACK)
    line_key=i.legend([('all types',i.polyline([(0,0),(16,0)],stroke=BLACK,stroke_width=1)),
                       ('fru+ or dsx+ only',i.polyline([(0,0),(16,0)],stroke=BLACK,stroke_width=1,stroke_dash=(1,2)))],
                      font_size=8.5,swatch=8,gap=5,row_gap=2,markup=False,text_fill=BLACK)
    key=i.box(i.vstack([color_key,line_key],gap=5,align='left'),pad=5,radius=3,fill='white',stroke='#b0b0b0',stroke_width=.5)
    key=i.place_in_clear_space(key,within=i.Rect(955,490,1133,667),
        avoid=[i.as_drawn(i.polyline(curve,stroke=BLACK,stroke_width=1)) for curve in h_curves],
        pad=6,clearance=2)
    p.nodes.append(key);p.labels+=4
    bb=key.bbox
    (p.out/'chart-data/h-legend.json').write_text(json.dumps({'box':[bb.x0,bb.y0,bb.x1,bb.y1],'curves':[v.tolist() for v in h_curves]},indent=2))
    # Conditional summaries of precisely the displayed empirical samples.
    summaries=[]
    p.text('% types\nwith f ≥ .3',1174,489,9,align='center')
    for k,(prefix,flag,label) in enumerate([('type',0,'I'),('type',1,'N'),('expr',0,'I+'),('expr',1,'N+')]):
        values=d[prefix+'_fraction_'+str(flag)]
        pct=float(100*np.mean(values>=.3)) if len(values) else 0
        summaries.append({'prefix':prefix,'flag':flag,'n':len(values),'percent':pct})
        x=1146+k*15;height=pct/100*130;col=GOLD if flag else BLACK
        p.rect(x,667-height,9,height,col)
        p.text(f'{pct:.1f}',x+4,652-height,7,align='center');p.text(label,x+4,674,8,align='center')
    p.text('I: iso · N: non-iso\n+: fru+ or dsx+',1174,696,7,align='center')
    (p.out/'chart-data/cdf-h-summary.json').write_text(json.dumps(summaries,indent=2))
    # I/J: native pies were drawn alongside anatomy; now connect and annotate.
    for x,bar in [(241,365),(557,681)]:
        p.text('♂',x-53,715,26,color=GREEN)
        for yy in [777,881]:
            p.line([(x+27,yy-40),(bar,yy-58)],GRAY,.6,dash=(1,2));p.line([(x+27,yy+40),(bar,yy+46)],GOLD,.5,dash=(1,2))
            p.arrow([(x+68,yy+7),(bar-19,yy+7)],GRAY,.7,3);p.text('without\nnoise',x+88,yy-18,10,color='#777',align='center')
        for k,(s,col) in enumerate([('dimorphic',GOLD),('isomorphic',BLACK),('noise',GRAY)]):p.text(s,x-97,910+k*13,10,color=col)
    for txt,x,y,col in [('94.2%',382,761,BLACK),('5.8%',382,817,GOLD),('98.8%',382,876,BLACK),('1.2%',382,931,GOLD),('94.5%',697,761,BLACK),('5.5%',697,817,GOLD),('99.2%',697,876,BLACK),('0.8%',697,931,GOLD)]:p.text(txt,x,y,10,color=col)
    p.text('% of connections',159,758,13,angle=-90);p.text('% of synapses in connections',454,715,13,angle=-90)
    # K: actual male synapse sample, signed comparison reweighted at male locations.
    xyz=d['syn_xyz_nm'];signed=d['syn_signed']
    if len(xyz):
        warped=a.warp(xyz);frame=a.frame((752,714,390,206),pad=1);xy=frame(warped[:,:2])
        for low,high,col in [(-1.01,-.5,'#b44293'),(-.5,-.1,'#d697bd'),(-.1,.1,'#d6d1c6'),(.1,.5,'#b7ca76'),(.5,1.01,'#749a43')]:
            flag=(signed>=low)&(signed<high);p.dots(xy[flag],col,.95,.6)
    ramp=i.ramp(['#b44293','#fff','#749a43']);signed_scale=i.linear((-1,1),(923,729))
    for k in range(100):
        value=-1+2*k/99;p.rect(1182,signed_scale.map(value),7,2,ramp((value+1)/2))
    for value,label in [(1,'+1  ♂'),(0,'0'),(-1,'−1  ♀')]:p.text(label,1194,signed_scale.map(value)-5,10)
    p.text('relative connection weight',1164,752,10,angle=-90)
    p.text('male locations · (male − female)/(male + female)',808,927,10)
    p.text('dimorphic connections · not a spatial-density difference',808,943,8,color='#666')
    # L: authored illustrative hierarchy, true final community sizes and IDs.
    communities=pd.read_feather(a.data/'communities.feather').sort_values('community_id')
    final=np.array([len(v) for v in communities.types],float);final/=final.sum()
    enriched=communities.enriched.values
    p.text('illustrative partitions',163,972,11)
    p.text('(reconstructed)',184,1567,8,color='#888')
    # Intermediate partitions are a transparent diagram reconstruction, not recovered SBM inference.
    counts=TRANSCRIBED['hierarchy_counts'];levels=[]
    nested={311:np.arange(len(final)+1)}
    for n in reversed(counts[:-1]):
        children=nested[next(reversed(nested))]
        nested[n]=children[np.linspace(0,len(children)-1,n+1).round().astype(int)]
    for level,n in enumerate(counts):
        bounds=nested[n]
        sizes=np.array([final[bounds[k]:bounds[k+1]].sum() for k in range(n)])
        flags=np.array([enriched[bounds[k]:bounds[k+1]].any() for k in range(n)])
        levels.append((bounds,sizes,flags))
        x=159+level*24;p.text(str(level),x+5,990,11,align='center')
        cum=np.r_[0,sizes.cumsum()]
        for k,(sz,flag) in enumerate(zip(sizes,flags)):
            p.rect(x,1008+cum[k]*489,11,max(.25,sz*489-.3),'#c92d2b' if flag else '#c2dfe7')
        if level:
            oldb,oldsz,_=levels[level-1];oldcum=np.r_[0,oldsz.cumsum()]
            for k in range(n):
                mid=(bounds[k]+bounds[k+1])/2;parent=np.searchsorted(oldb,mid,side='right')-1
                p.line([(x-13,1008+(oldcum[parent]+oldsz[parent]/2)*489),(x,1008+(cum[k]+sizes[k]/2)*489)],'#bac9cc',.4,.45)
        p.text(str(n),x+5,1517,10,align='center');p.text(str(int(flags.sum())),x+5,1504,10,color='#b92727',align='center')
    cum=np.r_[0,final.cumsum()];ids=[79,81,89,102,103,116,153,185,186,249,250,270]
    column=i.label_column([i.text(str(cid),size=10,font='Arimo',text_fill='#b92727') for cid in ids],
        [(314,1008+(cum[cid]+final[cid]/2)*489) for cid in ids],x=322,bounds=(1008,1497),gap=3,leader_color='#b92727',leader_width=.5)
    p.nodes.append(column);p.labels+=len(ids)
    (p.out/'chart-data/hierarchy-labels.json').write_text(json.dumps(column.notes['label_column'],indent=2))
    p.text('no. of total clusters',194,1536,11);p.text('partitions with enriched leaves',159,1550,10,color='#b92727')
    # M: exact community-level adjacency in self-rendered native colored cells.
    mat=d['matrix'];colors=['#d0cfae','#d9d397','#91b57c','#b48cba','#d9b26b','#b0d4e1','#65625a']
    def heatmap(matrix,x,y,w,h,offset=0):
        rows,cols=matrix.shape;v=np.log1p(matrix);den=max(np.quantile(np.log1p(mat[mat>0]),.97),1)
        buckets={}
        for row,col in zip(*np.where(v>0)):
            opacity=min(.65,float(v[row,col]/den)*.6);bucket=int(opacity*12)
            if not bucket:continue
            key=(colors[d['community_class'][row+offset]],bucket);xx=x+col*w/cols;yy=y+row*h/rows
            buckets.setdefault(key,[]).append([(xx,yy),(xx+w/cols,yy),(xx+w/cols,yy+h/rows),(xx,yy+h/rows)])
        for (color,bucket),rects in buckets.items():p.nodes.append(paths(rects,color,fill=True,opacity=bucket/12,name='numeric-adjacency-cells'))
    p.text('community adjacency matrix',412,973,12);heatmap(mat,370,991,259,231)
    heatmap(mat[70:120,70:120],644,985,180,204,70)
    from canvas import PlotMap
    source=PlotMap(i.panel(259,231,x=(0,311),y=(311,0)),370+259/2,991+231/2)
    zoom=PlotMap(i.panel(180,204,x=(70,120),y=(120,70)),734,1087)
    selection=source.region(70,70,120,120)
    p.rect(644,985,180,204,'none','#b22',.9)
    p.rect(selection.x0,selection.y0,selection.width,selection.height,'none','#b22',.8)
    for start,end in [((selection.x1,selection.y0),(644,985)),((selection.x1,selection.y1),(644,1189))]:p.line([start,end],'#a44',.6,dash=(2,3))
    for cid in range(70,120):
        box=zoom.region(cid,cid,cid+1,cid+1);p.rect(box.x0,box.y0,box.width,box.height,'none',BLACK,.4)
    ids=[79,81,89,102,103,116]
    column=i.label_column([i.tag(str(cid),size=9,font='Arimo',color='#a22',fill='white',pad=.5) for cid in ids],
        [zoom([cid+.5],[cid+.5])[0] for cid in ids],x=853,bounds=(985,1189),gap=4,leader_color='#a22',leader_width=.5)
    p.nodes.append(column);p.labels+=len(ids)
    (p.out/'chart-data/matrix-zoom.json').write_text(json.dumps({'slice':[70,120],'source_box':[selection.x0,selection.y0,selection.width,selection.height],'labels':column.notes['label_column']},indent=2))
    p.text('source (presynaptic)',357,1094,9,angle=-90);p.text('target (postsynaptic)',407,1225,9)
    legend(p,[('CB-intrinsic',colors[0]),('ascending',colors[2]),('visual centrifugal',colors[4])],643,1197,8,83)
    legend(p,[('CB-sensory',colors[1]),('descending',colors[3]),('visual projection',colors[5])],643,1210,8,83)
    legend(p,[('other',colors[6])],643,1223,8)
    # N: native published bars already present; add labels and axis.
    p.text('enriched cluster ID',393,1241,12)
    legend(p,[('specific',BLUE),('dimorphic',GOLD),('isomorphic',GRAY)],393,1255,9,70)
    for k,cid in enumerate([102,79,81,116,186,153,250,249,103,89,185,270]):p.text(str(cid),387,1267+k*17.55,10,align='right')
    p.text('enriched\ntotal',387,1490,10,align='right');p.text('non-\nenriched',387,1520,10,align='right')
    for v in [0,.2,.4,.6,.8,1]:p.text(f'{v:g}',393+v*222,1543,10,align='center')
    p.text('proportion of cell types',434,1556,12)
    # O: aggregate graph from actual community weights, authored circular layout.
    ids=[102,79,81,116,186,153,250,249,103,89,185,270,302,1,280,189,206,257,258,135,216,107]
    angles=np.linspace(-np.pi/2,3*np.pi/2,len(ids),endpoint=False)
    pos={cid:np.array([757+110*np.cos(theta),1376+113*np.sin(theta)]) for cid,theta in zip(ids,angles)};pos[102]=np.array([740,1375])
    vals=[]
    for pre in ids:
        for post in ids:
            if pre!=post and mat[pre,post]>0:vals.append((mat[pre,post],pre,post))
    enrichedids=set(communities.loc[communities.enriched,'community_id'])
    nodes={cid:i.Diagram(prim=RectPrim(23,23)).styled(fill='#b62b27' if cid in enrichedids else '#ddd',stroke='none').translated(*pos[cid]) for cid in ids}
    selected=sorted(vals,reverse=True)[:80];edge_notes=[]
    for weight,pre,post in selected:
        share=float(d['dim_matrix'][pre,post]/weight)
        col=GOLD if share>.15 else '#555'
        width=float(np.clip(.4+3.6*(math.sqrt(weight)-math.sqrt(1000))/(math.sqrt(50000)-math.sqrt(1000)),.4,4))
        edge=i.connect(nodes[pre],nodes[post],offset=9,standoff=1,arrow_size=5,stroke=col,stroke_width=width)
        p.nodes.append(edge)
        tip=edge.anchor_point('end');edge_notes.append({'pre':pre,'post':post,'weight':float(weight),'dimorphic_share':share,'tip':[tip.x,tip.y]})
    p.nodes.extend(nodes.values())
    for cid in ids:
        x,y=pos[cid];p.text(str(cid),x,y-6,10,color='white' if cid in enrichedids else BLACK,align='center')
    (p.out/'chart-data/network.json').write_text(json.dumps({'selection':'top 80 male aggregate weights among displayed communities','node_size':'constant 23 units','nodes':{str(cid):[v.bbox.x0,v.bbox.y0,v.bbox.x1,v.bbox.y1] for cid,v in nodes.items()},'edges':edge_notes},indent=2))
    p.text('edge weight\n(no. of synapses)',908,1269,10,align='center')
    for k,w in enumerate([4,2,1,.4]):p.line([(891,1300+k*10),(928,1300+k*10)],BLACK,w)
    p.text('≥50,000',933,1294,8);p.text('1,000',933,1326,8)
    p.text('top 80 edges · equal-size nodes',655,1505,9,color='#666')
    legend(p,[('enriched','#b62b27'),('not enriched','#ddd')],655,1521,9,99)
    p.text('dimorphic share of aggregate weight:',655,1537,9)
    legend(p,[('≤15%','#555'),('>15%',GOLD)],655,1551,9,100)
    # P: native annotations for all 255 real neurons.
    p.text('cluster 102',1038,973,13);p.text('male-specific',1134,1388,12,color=BLUE);p.text('sexually dimorphic',1099,1404,12,color=GOLD)
    # Q: manually transcribed proportions, all cells editable.
    p.text('proportion of non-isomorphic cell types',971,1458,12)
    for k,vals in enumerate(TRANSCRIBED['q_fractions']):
        x=982;y=1495+k*29
        for value,col in zip(vals,[BLUE,'#bf4a5e','#985294','#e9e9e9']):p.rect(x,y,216*value,27,col);x+=216*value
        p.text('non-\nenriched' if k==0 else 'enriched',974,y,12,align='right',color=BLACK if k==0 else '#b22')
    for v in [0,.2,.4,.6,.8,1]:p.text(f'{v:g}',982+216*v,1478,10,align='center')
    for k,(label,col) in enumerate(zip(['fru+/dsx−','fru−/dsx+','fru+/dsx+','fru−/dsx−'],[BLUE,'#bf4a5e','#985294','#999'])):p.text(label,982+k*55,1554,10,color=col)
