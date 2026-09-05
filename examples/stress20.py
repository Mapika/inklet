"""Twenty-panel, deterministic mixed-media stress figure for Inklet 2.5.

All observations are simulated. Meshes are generated locally, without downloads.
Run `python tools/stress20.py` for exports, edit/resize checks and measurements.
"""
from dataclasses import dataclass, replace
import math
import random

import inklet as i
from inklet.core import Diagram, Envelope, Rect
from inklet.three import Mesh, Vec3, build as mesh_solid

SEED = 20260905
COLORS = ('#176b9b', '#d66b45', '#198c83', '#8863ab', '#c79a34', '#687c90')
SOURCE = i.Source('Inklet twenty-panel stress test; seed 20260905', method='simulated')
PANEL_NAMES = (
    'surface', 'assembly', 'architecture', 'network', 'cloud', 'response', 'heatmap', 'contours',
    'violin', 'histogram', 'stacked', 'bars', 'survival', 'loglog', 'twins', 'forest',
    'polar', 'sankey', 'correlation', 'events',
)


def text_block(content, *, width, height, size=3.1, weight=None, color='#172d40'):
    text=i.text(content,width=width,size=size,weight=weight,markup=False,align='start',fill=color)
    text=text.translated(-text.bbox.x0,-text.bbox.y0)
    return Diagram(children=(text,),envelope_override=Envelope.from_rect(Rect(0,0,width,text.height)))


def surface(*, width, height):
    side=37
    vertices=[]
    for row in range(side):
        y=-2.5+5*row/(side-1)
        for col in range(side):
            x=-2.5+5*col/(side-1)
            z=1.4*math.exp(-((x-.8)**2+(y-.7)**2)/1.1)-math.exp(-((x+1)**2+(y+.6)**2)/.7)
            vertices.append(Vec3(x,y,z))
    faces=[];groups=[]
    for row in range(side-1):
        for col in range(side-1):
            a=row*side+col;b=a+1;c=a+side;d=c+1
            for face in ((a,b,d),(a,d,c)):
                faces.append(face)
                z=sum(vertices[v].z for v in face)/3
                groups.append(str(max(0,min(8,int((z+1)/2.4*9)))))
    mesh=Mesh(tuple(vertices),tuple(faces),tuple(groups),name='analytic-energy-surface')
    ramp=i.ramp(['#305a9b','#80c5c4','#f6e9ae','#d46542'])
    return i.model(mesh,width=width-5,height=min(height or 55,55)-4,view=(38,32),
                   style='shaded',colors={str(k):ramp(k/8) for k in range(9)},
                   crease=80,cull=False,stroke_width=.14,name='energy-surface')


def assembly(*, width, height):
    parts=[
        ('base',mesh_solid('box',size_x=2.8,size_y=2,size_z=.22),{'at':(0,0,-1),'color':'#c2d7e3'}),
        ('sample',mesh_solid('cylinder',radius=.58,height=.3,segments=40),{'at':(0,0,-.5),'color':COLORS[2]}),
        ('ring',mesh_solid('torus',radius=.85,tube=.14,segments=48,rings=16),{'at':(0,0,.3),'color':COLORS[1]}),
        ('lens',mesh_solid('sphere',radius=.7,subdivisions=3),{'at':(0,0,1.15),'scale':(1,1,.45),'color':COLORS[0]}),
    ]
    return i.scene(parts,width=width-7,height=min(height or 56,56)-4,view=(35,25),
                   style='shaded',order='exact',crease=65,stroke_width=.14,name='exploded-instrument')


def architecture():
    art=i.composition(76,54)
    style=dict(text_style={'size':2.6},box_style={'stroke':COLORS[0],'fill':'#f0f6f9'},pad=2)
    art.add('input',i.module('Input',min_width=15,min_height=10,**style),x=2,y=3)
    x,_=art.point('input','out')
    art.add('encoder',i.module('Encoder',min_width=21,min_height=10,**style),x=x+7,y=3)
    art.add('mean',i.module('Mean',min_width=16,min_height=10,**style),x=art.page_width-19,y=3)
    art.add('variance',i.module('Variance',min_width=21,min_height=10,**style),x=art.page_width-24,y=24)
    art.link('input:out','encoder:in',name='input-stream',stroke=COLORS[0])
    art.link('encoder:out','mean:in',name='mean-stream',stroke=COLORS[0])
    art.link('encoder:s','variance:in',route='orthogonal',name='variance-stream',stroke=COLORS[2])
    vx,_=art.point('variance','s');ix,_=art.point('input','s')
    art.link('variance:s','input:s',route='orthogonal',waypoints=[(vx,45),(ix,45)],
             label='recycle',label_offset=1.5,name='recycle',stroke=COLORS[1])
    return art


def network(*, width, height):
    nodes={f'{r}{c}':i.circle(f'{r}{c}',width=7,height=7,pad=0,
                            fill=COLORS[r],stroke='none',text_fill=i.current_theme().text_on(COLORS[r]),font_size=2.2)
           for r in range(4) for c in range(3)}
    edges=[(f'{r}{c}',f'{r+1}{d}',{'stroke':COLORS[r],'stroke_width':.22,'head':'none'})
           for r in range(3) for c in range(3) for d in range(3) if (c+d+r)%3!=1]
    graph=i.graph(nodes,edges,layout='layered',direction='right',gap=8,rank_gap=10,fit=width-3,name='layered-network')
    from inklet.links import route_all
    return Diagram(children=(route_all(graph.links,i.resolve(graph.diagram)),graph.diagram),name='network')


def polar(*, width, height):
    radius=min((width-16)/2,((height or 57)-14)/2)
    p=i.polar(radius,r=(0,30),zero='up',winding='cw')
    angles=list(range(0,360,10))
    values=[5+20*math.exp(2.4*(math.cos(math.radians(a-50))-1)) for a in angles]
    p.grid(r_count=3,theta_count=8)
    p.band(angles,[v-2 for v in values],[v+2 for v in values],fill='#badbd8')
    p.line(list(zip(angles,values)),stroke=COLORS[2],stroke_width=.4)
    p.mean_vector(angles,values,stroke=COLORS[1])
    p.theta_axis(count=8)
    p.r_axis(at=180,count=3,plate=False)
    return p.build()


def sankey(*, width, height):
    flows=[('A','M',24),('A','N',10),('B','M',8),('B','N',18),('C','N',14),
           ('M','X',20),('M','Y',12),('N','Y',22),('N','Z',20)]
    colors={name:COLORS[j%len(COLORS)] for j,name in enumerate('ABCMNXYZ')}
    return i.sankey(flows,length=width-3,breadth=min(height or 51,51)-6,gap=4,
                    node_width=2.7,label_gap=1.2,color=colors,opacity=.65,name='conserved-flow').diagram


def event_layer(events, *, width, height):
    """Disconnected native vector segments; one path per neuron, no bitmap."""
    from inklet.core import PathPrim, Subpath
    p=i.panel(width-13,(height or 56)-10,x=(0,10),y=(0,80))
    p.vspan(4,6,fill='#eaf0f5',stroke='none')
    for row,times in enumerate(events):
        commands=[]
        for t in times:
            a=p.point(t,row+.1);b=p.point(t,row+.8)
            commands.append(Subpath((a,b)))
        p.draw(Diagram(prim=PathPrim(tuple(commands)),kind='mark').styled(
            stroke=COLORS[(row//20)%4],stroke_width=.15,fill='none'))
    p.axes(x='Time / s',y='Neuron')
    return p.build()


@dataclass
class StressCase:
    document: object
    response: object
    cloud: object
    outcomes: object
    load: dict


def make_case(*, width=360, cloud_points=30000):
    rng=random.Random(SEED)
    cloud_rows=[]
    for k in range(cloud_points):
        group=k%3;x=rng.gauss((-1.5,1.4,.1)[group],(.8,.65,1)[group])
        y=.55*x+rng.gauss((.2,-.4,1.7)[group],.65)
        cloud_rows.append((x,y,COLORS[group]))
    cloud=i.dataset(dict(x=[r[0] for r in cloud_rows],y=[r[1] for r in cloud_rows],
                         color=[r[2] for r in cloud_rows]),name='embedding',source=SOURCE)
    t=[k/20 for k in range(241)]
    mean=[.4+2*(1-math.exp(-x/3))+.23*math.sin(x*1.8) for x in t]
    response=i.dataset(dict(time=t,mean=mean,lower=[y-.22 for y in mean],upper=[y+.22 for y in mean]),
                       name='response',source=SOURCE,units={'time':'s','mean':'a.u.','lower':'a.u.','upper':'a.u.'})
    outcomes=i.dataset(dict(condition=['Ctrl','A','B','A+B'],value=[2.6,4.3,5.6,7.2],error=[.35,.48,.42,.58]),
                       name='interventions',source=SOURCE)
    panels=[]
    def add(name,title,spec): panels.append((name,title,spec))
    def plot(**kw): return i.plot_spec(64,45,**kw)
    add('surface','3D energy landscape',i.component(surface,responsive=True))
    add('assembly','Exploded 3D instrument',i.component(assembly,responsive=True))
    add('architecture','Measured architecture',architecture())
    add('network','Layered interaction network',i.component(network,responsive=True))

    p=plot(x=(-4.5,4.5),y=(-4,5),clip=True)
    p.scatter(cloud.points('x','y'),color=cloud.column('color'),size=.38,stroke='none',raster=True,dpi=450)
    p.line([(-4,-2.2),(4,2.2)],stroke='#223547',stroke_dash=(1.5,1))
    p.axes(x='Embedding 1',y='Embedding 2')
    add('cloud',f'{cloud_points:,}-point hybrid scatter',p)

    p=plot(x=(0,12),y=(0,3.1))
    p.series(i.Series('Response',response.column('time'),response.column('mean'),COLORS[0],
                      response.column('lower'),response.column('upper')))
    p.axes(x='Time / s',y='Response / a.u.')
    p.annotate(5,mean[100]+.22,'Adaptation',side='nw',size=2.5,key='adaptation')
    detail= i.plot_spec(19,13,x=(8,12),y=(1.8,2.7),clip=True)
    detail.line(response.points('time','mean'),stroke=COLORS[0]).axes(count=3)
    p.inset(detail,corner='se',width=None,zoom=(8,12,1.8,2.7),pad=2)
    add('response','Live uncertainty + inset',p)

    field=[[math.sin(r/9)*math.cos(c/11)+.35*math.sin((r+c)/5) for c in range(96)] for r in range(96)]
    p=plot(x=(0,96),y=(0,96)).matrix(field,ramp=i.ramp('tol-sunset'),scale=i.linear((-1.4,1.4)),raster=True)
    p.axes(x='Position x',y='Position y').colorbar(side='right',label='Field')
    add('heatmap','9,216-cell scalar field',p)

    p=plot(x=(-3.5,3.5),y=(-3,3))
    for j,radius in enumerate((.4,.7,1,1.3,1.6,1.9,2.2)):
        p.line([(1.25*radius*math.cos(a)+.25*math.sin(2*a),.85*radius*math.sin(a))
                for a in [k*math.tau/200 for k in range(201)]],stroke=COLORS[j%4],stroke_width=.3)
    for x in range(-3,4):
        for y in range(-2,3):
            if x or y:p.arrow((x,y),(x-.13*x,y-.13*y),stroke='#7c8995',arrow_size=.7)
    p.axes(x='Coordinate x',y='Coordinate y')
    add('contours','Contours + vector field',p)

    groups={name:[rng.gauss(mu,sd) for _ in range(240)] for name,mu,sd in
            [('Ctrl',2,.4),('A',3,.65),('B',3.8,.55),('A+B',4.4,.5)]}
    p=plot(x=list(groups),y=(0,6.5),clip=True)
    p.violin(groups,colors=COLORS[:4],cut=0,median=True).boxplot(groups,width=.17,outliers=False,stroke='#243848')
    p.axes(y='Simulated expression')
    add('violin','Distribution shapes + quartiles',p)

    p=plot(x=(-3.5,5),y=(0,.65),clip=True)
    p.hist([rng.gauss(0,1) for _ in range(1500)],bins=30,density=True,name='Reference',fill=COLORS[0],fill_opacity=.6)
    p.hist([rng.gauss(1.5,.75) for _ in range(1500)],bins=30,density=True,name='Shifted',fill=COLORS[1],fill_opacity=.6)
    p.axes(x='Measurement',y='Density').legend(side='bottom',columns=2)
    add('histogram','3,000-observation mixture',p)

    x=list(range(61))
    layers=[[.25+.12*math.sin(v/12+j*1.7) for v in x] for j in range(4)]
    layers=[[layer[k]/sum(l[k] for l in layers) for k in range(len(x))] for layer in layers]
    p=plot(x=(0,60),y=(0,1)).stackarea(x,layers,colors=COLORS[:4],names=['I','II','III','IV'],stroke='none')
    p.axes(x='Time / min',y='Fraction').legend(side='bottom',columns=4)
    add('stacked','Compositional dynamics',p)

    p=plot(x=['Ctrl','A','B','A+B'],y=(0,10))
    p.bracket('Ctrl','A+B','***')
    p.bars(outcomes.column('condition'),outcomes.column('value'),bar_colors=COLORS[:4])
    p.errorbars(outcomes.points('condition','value'),yerr=outcomes.column('error'),stroke='#203648',cap=1)
    p.axes(y='Outcome / a.u.')
    add('bars','Interventions + significance',p)

    p=plot(x=(0,24),y=(0,1.05))
    for j,rate in enumerate((.027,.046,.075)):
        steps=[(x,math.exp(-rate*x)) for x in range(25)]
        p.step(steps,name=('A','B','Ctrl')[j],stroke=COLORS[j],stroke_width=.4)
        p.scatter(steps[4::5],size=1.1,marker='plus',color=COLORS[j])
    p.axes(x='Time / months',y='Survival fraction').legend(side='bottom',columns=3)
    add('survival','Step curves + censor marks',p)

    x=[10**(k/25) for k in range(101)]
    p=plot(x=i.log((1,1e4)),y=i.log((1e-5,2)))
    for j,slope in enumerate((.7,1,1.3)):
        p.line([(v,v**-slope) for v in x],stroke=COLORS[j],name=f'α = {slope:g}')
    p.axes(x='Scale',y='Probability').legend(side='bottom',columns=3)
    add('loglog','Four-decade scaling laws',p)

    hours=list(range(25));temperature=[18+6*math.sin((h-6)*math.pi/12) for h in hours]
    p=plot(x=(0,24),y=(0,5))
    p.bars(hours,[max(0,3*math.sin(h/4)+.8*math.cos(h)) for h in hours],width=.7,fill='#aacad9')
    p.axes(x='Hour',y='Rain / mm')
    p.twin_y((10,28),label='Temperature / °C',color=COLORS[1]).line(list(zip(hours,temperature)),stroke=COLORS[1])
    add('twins','Independent dual-axis scales',p)

    studies=[f'Cohort {j+1}' for j in range(7)];effects=[.62,.85,1.12,.7,1.28,.93,.77]
    p=plot(x=(.2,1.8),y=i.band(list(reversed(studies))))
    p.vline(1,stroke='#97a5b1',stroke_dash=(1,1))
    p.errorbars(list(zip(effects,studies)),xerr=[.14,.2,.18,.22,.3,.16,.12],cap=.8,stroke=COLORS[0])
    p.scatter(list(zip(effects,studies)),size=[1.8,2.4,1.6,2.2,1.7,2.6,3],color=COLORS[0],marker='square')
    p.axes(x='Relative effect')
    add('forest','Effect sizes + intervals',p)
    add('polar','Directional response',i.component(polar,responsive=True))
    add('sankey','Conserved flow across stages',i.component(sankey,responsive=True))

    labels=[f'G{j+1}' for j in range(10)]
    corr=[[math.exp(-abs(r-c)/2.8)*math.cos((r-c)*.52) for c in range(10)] for r in range(10)]
    p=plot(x=labels,y=list(reversed(labels)))
    p.matrix(corr,ramp=i.ramp('tol-sunset'),scale=i.linear((-1,1)),raster=False)
    p.axes().colorbar(side='right',label='r')
    add('correlation','100-cell vector correlation',p)
    events=[sorted([rng.random()*10 for _ in range(55)]+[rng.uniform(4,6) for _ in range(35)]) for _ in range(80)]
    add('events','7,200-event vector raster',i.component(event_layer,events,responsive=True))

    profile=i.publication('double-column',width=width,font_pt=8,small_font_pt=7,min_font_pt=6,dpi=150)
    doc=profile.document(columns=4,gap=7,row_gap=5,margin=8,
                         theme=replace(profile.theme,palette=COLORS,stroke=.22,hairline=.13,font_size_large=3.5))
    doc.add('heading',i.component(text_block,'INKLET  /  TWENTY-PANEL STRESS TEST',size=6,weight='bold',responsive=True),
            row=0,colspan=4,min_height=13)
    for index,(name,title,spec) in enumerate(panels):
        cell=i.subfigure(gap=2)
        cell.add('heading',i.component(text_block,f'{chr(97+index)}   {title}',weight='bold',responsive=True),min_height=5)
        cell.add('body',spec,min_width=40,min_height=58)
        doc.add(name,cell,row=1+index//4,column=index%4,min_width=65,min_height=74)
    doc.add('caption',i.component(text_block,
        'All data are deterministic simulations. Native 3D meshes, editable vector diagrams and charts; '
        'only the dense scatter and 96 × 96 field use raster layers. Seed 20260905. '
        'This plate tests rendering and layout, not scientific conclusions.',size=2.7,responsive=True),
        row=6,colspan=4,min_height=11)
    assert tuple(name for name,_,_ in panels)==PANEL_NAMES
    return StressCase(doc,response,cloud,outcomes,dict(panels=20,scatter_points=cloud_points,
        field_cells=9216,vector_matrix_cells=100,vector_events=7200,surface_triangles=2592,
        assembly_triangles=2988,
        distribution_samples=3960,network_nodes=12,network_edges=18))


def make_document():
    return make_case().document


if __name__=='__main__':
    print(make_document().export('out/stress20',name='stress20')['review'])
