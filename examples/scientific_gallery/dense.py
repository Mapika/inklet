"""Original full-page connectome plates, with coordinated multi-scale panels."""
import math
import numpy as np
import pandas as pd
import inklet as i
from inklet.core import Rect,Envelope
from helpers import AX,INK,TEAL,PURPLE,GOLD,BLUE,chart,caption,key,axes,ecdf,anatomy
from data import GROUPS,COLORS

COMM_COLORS=['#087f8c','#8055a5','#e58f29','#3b73b9','#be6479','#64895c','#836a52','#558d99','#a570ad','#cb9c49','#586783','#91a468']*2


def short(name):return name.replace('ORN_','').replace('_adPN',' aPN').replace('_lPN',' lPN')
def cloud_view(d,reference,w,h,lines,colors,camera=None,rois=()):
    a=i.anatomy_view(reference,width=w,height=h,camera=camera or d.camera,pad=.8)
    a.surface('brain',d.brain,color='#c9d0d1',opacity=.3)
    for name in rois:a.surface(name,d.rois[name],color='#86b1b2',opacity=.45)
    for k,(paths,color) in enumerate(zip(lines,colors)):a.paths(str(k),paths,color=color,stroke_width=.13,opacity=.72,depth_cue=.16)
    return a


def plate(title,subtitle,layout,panels,titles):
    body=i.panel_mosaic(layout,panels,width=240,height=289,gap=3.3,margin=5,label_size=3.1,label_gap=1.2,titles=titles)
    head=i.vstack([i.text(title,size=5.6,weight='bold',text_fill=INK),i.text(subtitle,size=2.5,text_fill='#60727b')],gap=1.4)
    head=head.translated(5-head.bbox.x0,3-head.bbox.y0)
    footer=i.text('INKLET  •  Original scientific gallery  /  Released anatomy and measurements; methods, selections and attribution accompany the source.',size=2,text_fill='#60727b')
    footer=footer.translated(5-footer.bbox.x0,307-footer.bbox.y0)
    return i.Diagram(children=(head,body.translated(0,15),footer),envelope_override=Envelope.from_rect(Rect(0,0,240,312)),notes=body.notes)


def olfactory(d):
    def overview(w,h):
        a=anatomy(d,w,h-32)
        detail=a.zoom(d.rois['AL-L'],width=22,height=22)
        view=a.inset(d.rois['AL-L'],width=22,height=22,side='bottom',gap=1.5,stroke='#6a7a83',stroke_width=.2)
        return caption(i.vstack([view,key(list(zip([short(g) for g in GROUPS],COLORS)),columns=3)],gap=1.5),'254 cached arbors • front camera • left AL detail')
    def pn_views(w,h):
        focus=np.concatenate([d.points[g] for g in GROUPS[4:]])
        views=[]
        for cam,label in [(d.camera,'front'),(d.dorsal,'dorsal')]:
            a=cloud_view(d,focus,w/2-1,h-9,[d.lines[g] for g in GROUPS[4:]],COLORS[4:],cam,rois=['AL-L','AL-R','LH-L','LH-R'])
            views.append(caption(a.build(),label))
        return caption(i.hstack(views,gap=2),'Projection pathways • DA1 lPN / MZ lv2PN')
    def type_network(w,h):
        weights=d.olfactory_weights;selected=set()
        for row in range(4):
            for col in np.argsort(-weights[row])[:5]:
                if weights[row,col]>0:selected.add((row,int(col)))
        for col in range(18):
            row=int(np.argmax(weights[:,col]))
            if weights[row,col]>0:selected.add((row,col))
        nodes={f's{k}':i.tag(short(g),size=2.1,pad=(1.4,1),fill=col,color='white',radius=2) for k,(g,col) in enumerate(zip(GROUPS[:4],COLORS))}
        for k,name in enumerate(d.partners):
            source=name.startswith('ORN_');nodes[f't{k}']=i.tag(short(name),size=2.1,pad=(1.1,.6),fill='#e1eaf0' if source else '#eee7e0',color=INK,radius=2 if source else 0)
        maximum=weights.max();edges=[(f's{a}',f't{b}',{'stroke':COLORS[a],'stroke_width':.75*math.sqrt(weights[a,b]/maximum),'arrow_size':.85,'opacity':.7}) for a,b in sorted(selected)]
        graph=i.graph(nodes,edges,direction='right',gap=.6,rank_gap=max(9,w*.36),ports=True).build()
        return caption(graph,'Measured type-level output • 18 leading targets\nTop five per source + strongest input per target\nRounded: ORN • square: other type • width ∝ √weight')
    def local_arbors(w,h):
        a=cloud_view(d,d.rois['AL-L'],w,h-9,[d.lines[g] for g in GROUPS[:4]],COLORS,d.camera,rois=['AL-L'])
        return caption(a.build(),'Left AL • four ORN types\nArbor colors: A')
    def records(w,h):
        a=i.anatomy_view(d.rois['AL-L'],width=w,height=h-9,camera=d.dorsal,pad=.7).surface('AL',d.rois['AL-L'],color='#c6d4d5',opacity=.4)
        for k,col in enumerate(COLORS[:4]):a.markers(str(k),d.al_xyz[d.al_type==k],color=col,radius=.15,opacity=.7)
        return caption(a.build(),'756 annotations • dorsal\nFour ORN colors: A')
    def downstream(w,h):
        focus=np.concatenate([d.points['LH008m'],d.points['DA1_lPN']]);a=cloud_view(d,focus,w-19,h-7,[d.lines['DA1_lPN'],d.lines['LH008m']],[COLORS[4],'#526b9a'],rois=['AL-L','AL-R','LH-L','LH-R'])
        locs=[];labels=[]
        for name in ['LH-L','LH-R','AL-L','AL-R']:
            verts=np.array([[v.x,v.y,v.z] for v in d.rois[name].vertices]);pos=a.view.project(i.Vec3(*verts.mean(0))).point
            locs.append(pos);labels.append(i.tag(name,size=1.9,pad=(.6,.35),fill='white',color=INK))
        column=i.label_column(labels,locs,x=a.area.x1+2,bounds=(a.area.y0+1,a.area.y1-1),gap=1,leader_color='#82929a',leader_width=.15)
        return caption(i.Diagram(children=(a.build(),column)),'DA1 lPN (rose) + LH008m (blue) • anatomy co-location')
    def branch_cdf(w,h):
        p=chart(w,h,(0,.22),(0,1))
        for g,col in zip(GROUPS,COLORS):
            v=np.sort([r['branch_nodes']/r['nodes'] for r in d.tree_stats if r['group']==g]);p.line(ecdf(v),stroke=col,stroke_width=.4)
        return caption(axes(p,'branch / SWC nodes','fraction',x_options={'ticks':[0,.1,.2]},y_options={'ticks':[0,.5,1]}).build(),'254 arbors • colors: A')
    def nodes(w,h):
        p=chart(w,h,i.log((100,20000)),i.symlog((0,1500),linthresh=1))
        for g,col in zip(GROUPS,COLORS):p.scatter([(r['nodes'],r['branch_nodes']) for r in d.tree_stats if r['group']==g],color=col,size=1.1,opacity=.65)
        return caption(axes(p,'SWC nodes','branch nodes',y_options={'ticks':[0,1,10,100,1000]}).build(),'254 arbors • symlog y')
    def depths(w,h):
        z=d.al_xyz[:,2];low,high=z.min(),z.max();p=chart(w,h,(0,1),(0,1))
        for k,col in enumerate(COLORS[:4]):
            v=np.sort((z[d.al_type==k]-low)/(high-low));p.line(ecdf(v),stroke=col,stroke_width=.4)
        return caption(axes(p,'relative depth','record fraction').build(),'Four ORN colors: A')
    def count_scatter(w,h):
        limit=220;p=chart(w,h,(0,limit),(0,limit));p.line([(0,0),(limit,limit)],stroke='#b7c1c6',stroke_width=.2)
        p.scatter([(r['female'],r['male']) for r in d.orn],size=1.4,color='#81969f',opacity=.75)
        for g,col in zip(GROUPS[:4],COLORS):
            r=next(r for r in d.orn if r['type']==g);p.scatter([(r['female'],r['male'])],size=2,color=col)
        return caption(axes(p,'female cells','male cells').build(),'All 53 annotated ORN types')
    def all_counts(w,h):
        parts=[]
        for records in [d.orn[:27],d.orn[27:]]:
            n=len(records);p=chart(w/2-2,h-8,(0,220),(n-.3,-.7))
            for k,r in enumerate(records):p.line([(r['female'],k),(r['male'],k)],stroke='#bac4c9',stroke_width=.28)
            for sex,col,mark in [('male',TEAL,'circle'),('female',GOLD,'square')]:p.scatter([(r[sex],k) for k,r in enumerate(records)],size=1.15,color=col,marker=mark)
            axes(p,'cells',y_options={'ticks':range(n),'format':lambda k,rows=records:short(rows[int(k)]['type']),'thin':False,'tick_font_size':1.8},x_options={'ticks':[0,100,200]});parts.append(p.build())
        return caption(i.hstack(parts,gap=2),'All 53 types, ranked by combined count • male ● / female ■\nBilateral annotations, including cells with unknown side')
    def output_matrix(w,h):
        vals=d.olfactory_weights;frac=vals/vals.sum(1,keepdims=True)
        p=chart(w,h,(0,18),(4,0)).matrix(frac,ramp=i.ramp(['#f3eee4',TEAL]),scale=i.linear((0,1)),vector="batched")
        axes(p,y_options={'ticks':np.arange(4)+.5,'format':lambda k:short(GROUPS[int(k)]),'thin':False},x_options={'ticks':np.arange(18)+.5,'format':lambda k:short(d.partners[int(k)]),'rotate':60,'thin':False,'tick_font_size':1.6})
        p.colorbar(side='right',length=18,thickness=1.5,ticks=[0,.5,1],tick_font_size=1.7)
        return caption(p.build(),'Fraction within the 18 displayed targets • source rows')
    def outputs(w,h):
        v=d.olfactory_weights.sum(0)[:12];p=chart(w,h,(0,float(v.max())*1.07),(11.6,-.6))
        for k,value in enumerate(v):p.bars([k],[value],orient='h',fill='#648d9f',width=.65,stroke='none')
        axes(p,'summed released male weight',y_options={'ticks':range(12),'format':lambda k:short(d.partners[int(k)]),'thin':False,'tick_font_size':1.85},x_options={'si':True})
        return p
    def count_ratio(w,h):
        p=chart(w-15,h,(1,400),(-1,1));p.line([(1,0),(400,0)],stroke='#b8c3c8',stroke_width=.2)
        pts=[(r['male']+r['female'],math.log2(r['male']/r['female'])) for r in d.orn]
        p.scatter(pts,size=1.5,color='#81969f');axes(p,'combined annotated count','log₂ male / female',y_options={'ticks':[-1,0,1]})
        selected=sorted(range(len(pts)),key=lambda k:abs(pts[k][1]),reverse=True)[:5]
        # Bound labels separately from data marks, with exact target leaders.
        labels=[i.tag(short(d.orn[k]['type']),size=1.8,pad=.35,fill='white',color=INK) for k in selected]
        column=i.label_column(labels,[p.point(*pts[k]) for k in selected],x=p.area.x1+2,bounds=(p.area.y0,p.area.y1),gap=1,leader_color='#84939b',leader_width=.15)
        p.over(column,clip=False);return p
    def morphology(w,h):
        values=[]
        for g in GROUPS:
            spans=np.array([r['span'] for r in d.tree_stats if r['group']==g]);relative=spans/spans.max(1,keepdims=True);values.append(np.median(relative,axis=0))
        p=chart(w,h,(0,3),(6,0)).matrix(values,ramp=i.ramp(['#f4efe4','#976d9e']),scale=i.linear((0,1)),vector="batched")
        for r,row in enumerate(values):
            for c,v in enumerate(row):p.place([((c+.5,r+.5),i.text(f'{v:.2f}',size=2.2,text_fill='white' if v>.65 else INK,bounds='ink'))])
        axes(p,x_options={'ticks':[.5,1.5,2.5],'format':lambda k:['x span','y span','z span'][int(k)],'thin':False},y_options={'ticks':np.arange(6)+.5,'format':lambda k:short(GROUPS[int(k)]),'thin':False,'tick_font_size':1.85})
        return caption(p.build(),'Median relative extent • each arbor / its longest axis')
    funcs=[overview,pn_views,type_network,local_arbors,records,downstream,branch_cdf,nodes,depths,count_scatter,all_counts,output_matrix,outputs,count_ratio,morphology]
    titles=['Olfactory anatomy','Projection routes in two views','Measured receptor-to-target network','Local arbors','Local records','Neuropils and downstream arbors','Branch sampling','Tree sizes','Depth profiles','Paired counts','Receptor-type census','Target allocation','Leading target weights','Abundance and count ratio','Anatomical extent profiles']
    names=list('ABCDEFGHIJKLMNO')
    return plate('Olfactory circuits across anatomical scales','Native meshes, 254 released arbors, local annotation records and type-level connectivity', ['A A B B C C','A A D E C C','F F G H I J','K K L L M M','K K N N O O'],dict(zip(names,funcs)),dict(zip(names,titles)))


def communities(d):
    matrix=d.matrix;top=np.argsort(-(d.strength_in+d.strength_out),kind='stable')[:24];all_ids=np.arange(len(matrix));colmap={int(t):COMM_COLORS[k] for k,t in enumerate(top)}
    def context(w,h):
        views=[];ref=np.vstack([np.array([[p.x,p.y,p.z] for p in d.brain.vertices]),np.array([[p.x,p.y,p.z] for p in d.vnc.vertices]),d.cluster_points])
        for cam,label in [(d.camera,'front'),(d.anatomy.camera(d.anatomy.frame((0,0,1,1),view='side'),view='side'),'side')]:
            a=i.anatomy_view(ref,width=w/2-1,height=h-9,camera=cam)
            a.surface('brain',d.brain,color='#c7d0d2',opacity=.38).surface('VNC',d.vnc,color='#c7d0d2',opacity=.38).paths('arbors',d.cluster_lines,color=PURPLE,stroke_width=.085,opacity=.6,depth_cue=.2)
            views.append(caption(a.build(),label))
        return caption(i.hstack(views,gap=2),'Community 102 • all 255 released cells')
    order=np.argsort(-(d.strength_in+d.strength_out),kind='stable')
    def full_matrix(w,h):
        vals=np.log10(1+matrix[np.ix_(order,order)]);p=chart(w,h,(0,311),(311,0)).matrix(vals,ramp=i.ramp(['#f5f1e8','#8eb9ba','#1d626f','#333d66']),scale=i.linear((0,6)),vector="batched")
        axes(p,'target strength rank','source strength rank',x_options={'ticks':[0,100,200,311]},y_options={'ticks':[0,100,200,311]})
        p.rect(0,0,24,24,front=True,fill='none',stroke=GOLD,stroke_width=.5)
        p.colorbar(side='bottom',length=35,thickness=2,ticks=[0,2,4,6],label='log₁₀(1 + weight)',tick_font_size=1.8,label_font_size=2)
        return caption(p.build(),'311 × 311 community pairs • gold window: top 24')
    def network(w,h):
        values=sorted([(matrix[a,b],int(a),int(b)) for a in top for b in top if a!=b and matrix[a,b]>0],reverse=True)[:64];maximum=values[0][0]
        nodes={str(t):(i.circle if d.sizes[t]<=10 else i.box)(i.text(str(t),size=2.3,bounds='ink',text_fill='white'),pad=1.2,fill=colmap[int(t)],stroke='white',stroke_width=.15) for t in top}
        edges=[(str(a),str(b),{'stroke':colmap[a],'stroke_width':.8*math.sqrt(v/maximum),'arrow_size':1.1,'opacity':.68}) for v,a,b in values]
        graph=i.graph(nodes,edges,layout='circular',gap=max(.6,w*.022),lane=.7).build()
        return caption(graph,'24 leading communities • 64 strongest non-self links\nCircle: ≤10 types • square: >10 • labels: community ID\nEdge color: source • width ∝ √weight')
    def rank(w,h):
        vals=np.sort(d.sizes)[::-1];p=chart(w,h,i.log((1,311)),i.log((1,100))).line(list(zip(range(1,312),vals)),stroke=PURPLE,stroke_width=.4)
        return axes(p,'rank','member types')
    def balance(w,h):
        low=1e3;high=2e6;p=chart(w,h,i.log((low,high)),i.log((low,high)));p.line([(low,low),(high,high)],stroke='#b9c2c7',stroke_width=.2)
        p.scatter(list(zip(d.strength_out,d.strength_in)),size=1.1,color='#9aaab2',opacity=.7)
        for t in top:p.scatter([(d.strength_out[t],d.strength_in[t])],size=1.6,color=colmap[int(t)])
        return axes(p,'outgoing','incoming')
    def sample_grid(w,h,camera):
        rows=[];items=list(d.community_arbors.items());view_h=(h-7)/3-1
        for row in range(3):
            cells=[]
            for t,(lines,points) in items[row*2:row*2+2]:
                a=cloud_view(d,d.brain,w/2-1,view_h,[lines],[colmap[t]],camera,rois=['AL-L','AL-R'])
                tag=i.tag(str(t),size=1.8,pad=(.5,.2),fill=colmap[t],color='white')
                tag=tag.translated(a.area.x0-tag.bbox.x0,a.area.y0-tag.bbox.y0)
                cells.append(i.Diagram(children=(a.build(),tag)))
            rows.append(i.hstack(cells,gap=2))
        return i.vstack(rows,gap=1)
    def sample_views(w,h):
        return caption(sample_grid(w,h,d.camera),'Six communities • n=16 each • same front camera')
    def detail_matrix(w,h):
        values=np.log10(1+matrix[np.ix_(top,top)]);p=chart(w,h,(0,24),(24,0)).matrix(values,ramp=i.ramp(['#f5f1e8','#8eb9ba','#1d626f','#333d66']),scale=i.linear((0,6)),vector="batched")
        ticks=np.arange(24)+.5;axes(p,x_options={'ticks':ticks,'format':lambda k:str(top[int(k)]),'rotate':60,'thin':False,'tick_font_size':1.5},y_options={'ticks':ticks,'format':lambda k:str(top[int(k)]),'thin':False,'tick_font_size':1.5})
        return caption(p.build(),'Gold window in B • identical log-weight color scale')
    def concentration(w,h):
        p=chart(w,h,(0,1),(0,1)).line([(0,0),(1,1)],stroke='#c1c9cc',stroke_width=.2)
        for v,col in [(d.strength_out,TEAL),(d.strength_in,PURPLE)]:
            vals=np.sort(v)[::-1];p.line([(0,0),*zip(np.arange(1,312)/311,np.cumsum(vals)/vals.sum())],stroke=col,stroke_width=.5)
        return caption(axes(p,'rank fraction','weight fraction').build(),'Output teal • input purple')
    def internal_hist(w,h):
        vals=np.diag(matrix)/d.strength_out;bins=np.linspace(0,1,16);counts,_=np.histogram(vals,bins);p=chart(w,h,(0,1),(0,counts.max()*1.1)).hist(vals,bins=bins,fill=PURPLE,stroke='white',stroke_width=.1)
        return axes(p,'internal output fraction','communities')
    def classes(w,h):
        # Released type classifications, one vote per member type.
        classified=d.annotations.assign(annotation_group=d.annotations['class'].fillna(d.annotations.superclass))
        typeclass=classified.dropna(subset=['type']).groupby('type')['annotation_group'].agg(lambda v:v.mode().iloc[0] if len(v.mode()) else 'unknown')
        rows=[]
        for t in top[:12]:rows.append(pd.Series(d.communities.iloc[t].types).map(typeclass).fillna('unknown').value_counts())
        allclasses=pd.concat(rows,axis=1).fillna(0).sum(1).nlargest(4).index.tolist();cols=[TEAL,GOLD,PURPLE,BLUE,'#aebbc1'];values=[]
        for r in rows:values.append([r.get(k,0) for k in allclasses]+[r.sum()-sum(r.get(k,0) for k in allclasses)])
        arr=np.array(values,dtype=float);arr/=arr.sum(1,keepdims=True)
        p=chart(w,h,(0,1),(11.6,-.6))
        for row in range(12):
            base=0
            for v,c in zip(arr[row],cols):p.bars([row],[base+v],orient='h',baseline=base,fill=c,stroke='none',width=.75);base+=v
        axes(p,'member-type fraction',y_options={'ticks':range(12),'format':lambda k:str(top[int(k)]),'thin':False,'tick_font_size':1.7});p.legend(entries=list(zip(allclasses+['other'],cols)),side='bottom',font_size=1.8,columns=3,markup=False)
        return p
    a,b=np.triu_indices(311,1);forward,reverse=matrix[a,b],matrix[b,a];paired=(forward>0)&(reverse>0);x,y=np.log10(forward[paired]),np.log10(reverse[paired]);contrast=(forward+reverse)>0
    def reciprocity(w,h):
        bins=np.linspace(0,6,33);hist,_,_=np.histogram2d(y,x,bins=(bins,bins));p=chart(w,h,(0,6),(0,6)).matrix(np.where(hist[::-1]>0,hist[::-1],np.nan),ramp=i.ramp(['#f5f1e8','#b6b5c9','#8055a5']),scale=i.log((1,max(2,hist.max()))),vector="batched",missing='#f5f1e8')
        p.line([(0,0),(6,6)],stroke='#91a1a7',stroke_width=.2)
        axes(p,'log₁₀ lower → higher ID','log₁₀ higher → lower ID');p.colorbar(side='right',length=20,thickness=1.6,tick_font_size=1.7,label='pairs / bin',label_font_size=1.8)
        return caption(p.build(),f'{int(paired.sum()):,} reciprocally connected community pairs')
    def asymmetry(w,h):
        v=(forward[contrast]-reverse[contrast])/(forward[contrast]+reverse[contrast]);bins=np.linspace(-1,1,41);counts,_=np.histogram(v,bins);p=chart(w,h,(-1,1),(0,counts.max()*1.1)).hist(v,bins=bins,fill='#648d9f',stroke='white',stroke_width=.1)
        return caption(axes(p,'(forward − reverse) / total','unordered pairs').build(),'Forward = lower community ID → higher ID')
    def more_views(w,h):
        return caption(sample_grid(w,h,d.dorsal),'Same 96 sampled cells • same dorsal camera')
    def size_weight(w,h):
        p=chart(w,h,i.log((1,100)),i.log((1e3,2e6)));p.scatter(list(zip(d.sizes,d.strength_out)),color=np.diag(matrix)/d.strength_out,ramp=i.ramp(['#d6dedf',TEAL]),scale=i.linear((0,1)),size=1.3)
        return caption(axes(p,'member types','output weight').build(),'Pale → teal: internal fraction 0–1')
    def edge_distribution(w,h):
        self_vals=np.log10(np.diag(matrix)[np.diag(matrix)>0]);other=matrix[~np.eye(311,dtype=bool)];other_vals=np.log10(other[other>0]);p=chart(w,h,(0,6),(0,1))
        for vals,c in [(self_vals,PURPLE),(other_vals,TEAL)]:p.line(ecdf(np.sort(vals)),stroke=c,stroke_width=.4)
        return caption(axes(p,'log₁₀ weight','pair fraction').build(),'Self purple • other teal')
    def degrees(w,h):
        connected=(matrix>0)&~np.eye(311,dtype=bool);out=connected.sum(1);inc=connected.sum(0);p=chart(w,h,(0,311),(0,311));p.line([(0,0),(311,311)],stroke='#b9c5ca',stroke_width=.2);p.scatter(list(zip(out,inc)),size=1.2,color=BLUE,opacity=.6)
        return caption(axes(p,'out-neighbors','in-neighbors').build(),'Self-links excluded')
    def coverage(w,h):
        ordered=np.argsort(-d.sizes,kind='stable');p=chart(w,h,(0,1),(0,1));p.line([(0,0),*zip(np.cumsum(d.sizes[ordered])/d.sizes.sum(),np.cumsum(d.strength_out[ordered])/matrix.sum())],stroke=TEAL,stroke_width=.5);p.line([(0,0),(1,1)],stroke='#b9c5ca',stroke_width=.2)
        return caption(axes(p,'type fraction','output fraction').build(),'Largest communities first')
    funcs=[context,i.PanelSpec(full_matrix,aspect=1),network,rank,balance,sample_views,detail_matrix,concentration,internal_hist,classes,reciprocity,asymmetry,more_views,size_weight,edge_distribution,degrees,coverage]
    titles=['Anatomy in two projections','The complete community matrix','A directed community network','Type counts','In / out weight','Leading-community anatomy','Linked top-24 detail','Concentration','Internal output','Composition by annotation group','Reciprocal weight density','Directional imbalance','Same samples, dorsal view','Size / weight','Weight profiles','Connectivity','Coverage']
    names=list('ABCDEFGHIJKLMNOPQ')
    return plate('Community structure from anatomy to connectivity','311 released communities • 8,231 member types • native vector matrices, graphs and sampled arbors', ['A A B B C C','D E B B C C','F F G G H I','J J K K L L','M M N O P Q'],dict(zip(names,funcs)),dict(zip(names,titles)))
