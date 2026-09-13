"""Hemisphere comparisons, local neuropil arbors and anatomical locator insets."""
import numpy as np
import inklet as i
from anatomy import paths
from canvas import BLUE,GOLD,GREEN,PINK

EXTRA_ROIS={'SIP-L':65,'SIP-R':66,'FLA-L':25,'FLA-R':26,'AVLP-L':11,'AVLP-R':12,'Leg-T1-L':105,'Leg-T1-R':106,'Leg-T2-L':107,'Leg-T2-R':108,'Leg-T3-L':109,'Leg-T3-R':110,'ANm':121,'GNG':29}

def clip(nodes,box):
    x,y,w,h=box
    return i.Diagram(children=tuple(nodes),clip_region=tuple(i.Vec2(*v) for v in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]))

def center(a,name,frame):return frame(a.mesh('roi-'+name)[0][:,:2].mean(0))

def panel_a(p,a):
    # One anatomical frame, split at the midline: detailed left, schematic right.
    frame=a.frame((165,254,322,192),pad=1)
    left=[];right=[]
    left+=a.surface('male-brain',frame,color='#c9c5c0',opacity=.45)
    right+=a.shell(frame,color='#eae7e7',outline=None)
    for name in ['AL-L','AL-R','CA-L','CA-R','LH-L','LH-R']:
        left+=a.surface('roi-'+name,frame,color='#bcb8b1',opacity=.7,target=2200)
        right+=a.roi(name,frame,color='#fff',outline='#aaa',width=.5)
    for group,col in [('KCab-s','#7fa5c1'),('LH008m','#6898ad'),('DA1_lPN','#66a486'),('ORN_DA1','#dcb052')]:
        left+=a.neurons_draw(a.ids(group)[:12],frame,color=col,width=.7,opacity=.85,depth_cue=.35)
    p.nodes.append(clip(left,(163,254,173,192)))
    p.nodes.append(clip(right,(339,254,149,192)))
    p.line([(336,255),(336,438)],'#aaa',.5,dash=(3,4))
    # Draw schematic routes in the physical right half of the same brain.
    rois={n:center(a,n,frame) for n in ['AL-L','AL-R','CA-L','CA-R','LH-L','LH-R']}
    al=max([rois['AL-L'],rois['AL-R']],key=lambda v:v[0]);ca=max([rois['CA-L'],rois['CA-R']],key=lambda v:v[0]);lh=max([rois['LH-L'],rois['LH-R']],key=lambda v:v[0])
    antenna=np.array([371,426]);p.arrow([antenna,antenna+[-11,-27],al+[0,13],al], '#deaa4e',2.6,7,smooth=.55)
    branch=al+[-2,-30];p.arrow([al,branch,ca+[0,10],ca],'#65a585',2.4,7,smooth=.6)
    p.arrow([branch,branch+[23,0],lh],'#65a585',2.4,7,smooth=.6)
    p.arrow([ca,ca+[-12,-17],ca+[-18,-42]],'#7ca4c2',2.4,7,smooth=.65)
    p.arrow([ca,ca+[13,-7],ca+[29,2],ca+[28,21]],'#7ca4c2',2.4,6,smooth=.65)
    for label,x,y,col in [('LH008m',209,273,'#739bb1'),('KCαβ-s',263,260,'#86a9c6'),('DA1 PN',229,323,'#78b399'),('DA1 ORN',241,359,'#dfaf53'),('CB intrinsic',380,248,'#85a6c5'),('ALPN',365,312,'#66ad83'),('sensory',348,383,'#e4ad4a')]:p.label(label,x,y,10,fill=col,color='white')
    for label,point,off in [('MB',ca,[-19,-21]),('LH',lh,[5,2]),('AL',al,[9,6])]:p.text(label,*(point+off),9)
    p.text('Antenna',374,426,9);p.fly(164,369,73,85)

def panel_c(p,a):
    # Actual presynaptic sites localize receptor-neuron glomerular terminals.
    # This avoids depicting long input axons as glomerular anatomy.
    from refined_data import local_synapses
    d=local_synapses(a.data,p.out/'chart-data');xyz=a.warp(d['al_xyz_nm'])
    colors=['#9b71dd','#86d5d9','#c3e37e','#d69cdf']
    frame=a.frame((505,239,220,188),central=True,pad=1)
    p.nodes+=a.surface('central-brain',frame,color='#c8c4bf',opacity=.45)
    for roi in ['AL-L','AL-R']:p.nodes+=a.surface('roi-'+roi,frame,color='#aaa8a2',opacity=.65,target=2200)
    for group,col in zip(['ORN_DA1','ORN_VA1v','ORN_VA1d','ORN_DL3'],colors):
        p.nodes+=a.neurons_draw(a.ids(group),frame,color=col,width=.6,opacity=.7)
    for k,col in enumerate(colors):p.dots(frame(xyz[d['al_type']==k,:2]),col,.6,.6)
    left=d['al_side']==1;local=xyz[left];types=d['al_type'][left]
    centers=np.array([np.median(local[types==k],axis=0) for k in range(4)])
    # Anatomically derived oblique camera: separates glomerular centers without
    # moving any data points independently. VA1d is below DA1 in this camera.
    vertical=centers[2]-centers[0];vertical/=np.linalg.norm(vertical)
    horizontal=centers[1]-centers[0];horizontal-=vertical*np.dot(horizontal,vertical);horizontal/=np.linalg.norm(horizontal)
    camera=np.column_stack([horizontal,vertical]);origin=local.mean(0)
    projected=(local-origin)@camera;v=(a.mesh('roi-AL-L')[0]-origin)@camera
    inset=a.frame((737,329,140,126),bounds=(v.min(0),v.max(0)),pad=2)
    # Convex outline comes from the true projected ROI vertices, not a reference.
    from scipy.spatial import ConvexHull
    shell=v[ConvexHull(v).vertices];p.poly(inset(shell),'#f4f4f4')
    for k,col in enumerate(colors):p.dots(inset(projected[types==k]),col,1.35,.85)
    c=center(a,'AL-L',frame);p.line([c+[10,-12],(729,310)],'#999',.6,dash=(2,3))


def panel_i(p,a):
    frame=a.frame((164,979,184,266),full=True,pad=0)
    left=a.surface('male-brain',frame,color='#c9c5c0',opacity=.4)+a.surface('male-vnc',frame,color='#c9c5c0',opacity=.4)
    right=a.shell(frame,full=True,color='#e9e7e7',outline=None)
    brain=a.mesh('male-brain')[0];mid=frame((brain.min(0)[:2]+brain.max(0)[:2])/2)[0]
    regions=['SIP-L','SIP-R','FLA-L','FLA-R','AVLP-L','AVLP-R','GNG','Leg-T1-L','Leg-T1-R','Leg-T2-L','Leg-T2-R','Leg-T3-L','Leg-T3-R','ANm','ProLN-L','ProLN-R','MesoLN-L','MesoLN-R','MetaLN-L','MetaLN-R','ADMN-L','ADMN-R']
    for roi in regions:
        left+=a.roi(roi,frame,color='#fff',outline='#8c8986',width=.45)
        right+=a.roi(roi,frame,color='#f9f8f5',outline='#b6b2ae',width=.4)
    for group,col in [('AN09B017d','#b984ab'),('LgLG1a','#d7ac57'),('pharyngeal','#aaa79e')]:left+=a.neurons_draw(a.ids(group)[:16],frame,color=col,width=.7,opacity=.8)
    p.nodes.append(clip(left,(163,979,mid-163,267)));p.nodes.append(clip(right,(mid+2,979,350-mid-2,267)))
    p.line([(mid+1,981),(mid+1,1241)],'#ccc',.5,dash=(2,3))
    # Distinct schematic information flow on the right, real arbors on the left.
    def rightmost(base):return max([center(a,base+'-L',frame),center(a,base+'-R',frame)],key=lambda v:v[0])
    t1=rightmost('Leg-T1');t2=rightmost('Leg-T2');t3=rightmost('Leg-T3');gng=center(a,'GNG',frame);avlp=rightmost('AVLP');sip=rightmost('SIP')
    p.arrow([t3,t3+[0,-11],t2,t1,gng,avlp], '#bc88b0',1.6,5,smooth=.5)
    p.arrow([t1+[17,9],t1+[3,9],t1], '#e0b15c',1.8,5,smooth=.5)
    p.arrow([gng+[15,5],gng,gng+[-3,-13],sip], '#d7ac57',1.6,5,smooth=.5)
    for label,roi,x,y in [('SIP','SIP-L',267,991),('FLA','FLA-L',249,1018),('AVLP','AVLP-L',288,1021),('GNG','GNG',287,1062),('ProLN','ProLN-R',180,1105),('ADMN','ADMN-R',183,1131),('MesoLN','MesoLN-R',180,1179),('MetaLN','MetaLN-R',185,1229)]:
        pt=center(a,roi,frame);p.line([(x+len(label)*3,y+9),pt],'#aaa',.45);p.text(label,x,y,8)
    for label,x,y,col in [('AN09B017d',201,1078,'#b781aa'),('ANs',267,1078,'#b781aa'),('sensory',294,1094,'#e0ae51'),('LgLG1a',294,1108,'#e0ae51')]:p.label(label,x,y,8,fill=col,color='white')
    p.fly(295,1156,76,89);p.wing(286,1115,88,36)

def panel_j(p,a):
    entries=[('labellar',(391,1002,67,74),'#66984e'),('pharyngeal',(480,1006,92,69),'#eeb954'),('taste-peg',(594,1001,61,75),'#c149c5'),('leg-ascending',(418,1133,54,103),'#81baea'),('leg-local',(490,1133,89,45),'#659cdf'),('wing',(592,1132,87,45),'#dc4b43')]
    for group,box,color in entries:
        ids=a.ids(group)
        if group=='leg-local':ids=[b for b in ids if a.neurons.loc[b,'entryNerve']=='ProLN' and a.neurons.loc[b,'rootSide']=='L']
        if group=='wing':ids=[b for b in ids if a.neurons.loc[b,'rootSide']=='L'] or ids
        if group in ['labellar','pharyngeal','taste-peg']:
            thumbbox=(box[0]+10,1077,35,32);full=False
        elif group=='leg-ascending':thumbbox=(384,1162,32,69);full=True
        else:thumbbox=(box[0]+23,1179,34,61);full=True
        # Source coordinates stay in 3D. Overview and detail share one camera;
        # Inklet derives the zoom fit and exact locator window.
        lines=[];points=[]
        for body in ids:
            xyz,index,parents=a.skeleton(body);lookup={int(value):k for k,value in enumerate(index)}
            points.extend(xyz)
            lines.extend([xyz[k],xyz[lookup[int(parent)]]] for k,parent in enumerate(parents) if int(parent) in lookup)
        surfaces=['central-brain']+(['male-vnc'] if full else [])
        reference=np.concatenate([a.mesh(name)[0] for name in surfaces]+[np.asarray(points)])
        camera=a.camera(a.frame((0,0,1,1),central=True,full=full))
        overview=i.anatomy_view(reference,width=thumbbox[2],height=thumbbox[3],camera=camera,pad=1)
        for name in surfaces:overview.surface(name,a.display_mesh(name,1000),color='#e4e2df',opacity=.7)
        overview.paths('neurons',lines,color=color,stroke_width=.45,opacity=.85,depth_cue=.15)
        detail=overview.zoom(points,width=box[2],height=box[3],pad=2,layers=['neurons'])
        # The same requested line size is used at either magnification.
        detail.style('neurons',stroke_width=.65,opacity=.75)
        thumb_center=i.Vec2(thumbbox[0]+thumbbox[2]/2,thumbbox[1]+thumbbox[3]/2)
        p.nodes.append(overview.build().translated(thumb_center.x,thumb_center.y))
        p.nodes.append(detail.build().translated(box[0]+box[2]/2,box[1]+box[3]/2))
        window=overview.window(detail)
        x0=max(window.x0,-thumbbox[2]/2)+thumb_center.x;y0=max(window.y0,-thumbbox[3]/2)+thumb_center.y
        x1=min(window.x1,thumbbox[2]/2)+thumb_center.x;y1=min(window.y1,thumbbox[3]/2)+thumb_center.y
        p.line([(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)],'#777',.55,dash=(1.3,1.8))
        p.line([((x0+x1)/2,y0),(box[0]+box[2]/2,box[1]+box[3]+1)],'#999',.5,dash=(1.5,2))
