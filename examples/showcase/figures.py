"""Curated, reproducible figure recipes. Data are mathematical or illustrative."""
import math
import inklet as i


CATALOG = (
    dict(id='interference', title='Interference', category='Mathematical plots',
         description='Two radial waves, one shared colour scale.',
         origin='Analytic field: cos(7 r1) + cos(7 r2); source separation 2.4 units.'),
    dict(id='attractor', title='Deterministic chaos', category='Mathematical plots',
         description='A continuous trajectory, coloured by elapsed time.',
         origin='Lorenz equations; sigma=10, rho=28, beta=8/3. RK4, dt=0.01, initial state (1,1,1).'),
    dict(id='wave-packets', title='Travelling wave packets', category='Mathematical plots',
         description='A sequence of Gaussian-windowed oscillations.',
         origin='Analytic signals at 18 parameter values; curves are vertically offset for comparison.'),
    dict(id='photonics', title='Integrated photonics', category='3D illustration',
         description='Gold waveguides, optical fibres and a silicon substrate.',
         origin='Original conceptual device illustration. The companion curve multiplies two analytic Lorentzian dips; it is not an optical simulation of the geometry.'),
    dict(id='lattice', title='Designed porosity', category='3D illustration',
         description='A lattice specimen between two compression plates.',
         origin='Original 3×3×3 body-centred strut lattice. No mechanical simulation is implied.'),
    dict(id='helix', title='Paired helices', category='3D illustration',
         description='Two continuous backbones with repeated connecting links.',
         origin='Original parametric illustration; not an atomistic molecular structure.'),
    dict(id='architecture', title='A room for daylight', category='Architecture',
         description='An open interior, warm timber and reusable furniture.',
         origin='Original conceptual room; Modern Arm Chair 01 by Vibrant Nordic / Poly Haven, CC0.'),
    dict(id='architecture-sketch', title='From scene to sketch', category='Architecture',
         description='The same room and camera, with matte surfaces and irregular outlines.',
         origin='Procedural sketch rendering of the architecture scene. Not a hand-drawn original.'),
)


def interference():
    n = 220
    axis = [-4 + 8*(k+.5)/n for k in range(n)]
    values = [[math.cos(7*math.hypot(x-1.2,y))+math.cos(7*math.hypot(x+1.2,y))
               for x in axis] for y in axis]
    panel = i.panel(120, 85, x=(-4,4), y=(-4,4))
    panel.matrix(values, x=axis, y=axis, raster=True,
        ramp=i.ramp(['#172b57','#258eaa','#f6f0d8','#e99352','#982f45']), scale=i.linear((-2,2)))
    panel.axes(x='x / relative units', y='y / relative units')
    panel.colorbar(side='right', label='Amplitude', count=5)
    return panel.build()


def attractor():
    def f(p):
        x,y,z=p
        return (10*(y-x), x*(28-z)-y, x*y-8*z/3)
    p=(1.,1.,1.);points=[]
    for step in range(6500):
        dt=.01;k1=f(p);k2=f(tuple(a+dt*b/2 for a,b in zip(p,k1)))
        k3=f(tuple(a+dt*b/2 for a,b in zip(p,k2)));k4=f(tuple(a+dt*b for a,b in zip(p,k3)))
        p=tuple(a+dt*(b+2*c+2*d+e)/6 for a,b,c,d,e in zip(p,k1,k2,k3,k4))
        if step>=500:points.append(p)
    panel=i.panel(137,85,x=(-22,22),y=(0,52))
    ramp=i.ramp(['#19355f','#25899b','#64b9b1','#d9bb71','#d85e45'])
    # Small consecutive segments retain an entirely vector trajectory.
    for start in range(0,len(points)-1,30):
        segment=points[start:start+31]
        panel.line([(x,z) for x,y,z in segment],stroke=ramp(start/(len(points)-1)),stroke_width=.20)
    panel.axes(x='x',y='z')
    return panel.build()


def wave_packets():
    panel=i.panel(137,85,x=(-5,5),y=(-.1/.52,10/.52))
    xs=[-5+k/40 for k in range(401)]
    ramp=i.ramp(['#285575','#318b9b','#80b4aa','#beaf91','#a45a59'])
    # Paint the upper, rear traces first so foreground peaks stay intact.
    for row in reversed(range(18)):
        t=row/17;offset=row
        ys=[offset+(.8/.52)*math.exp(-((x-(t-.5)*4)/1.5)**2)*(.55+.45*math.cos(5*x-7*t)) for x in xs]
        color=ramp(t)
        panel.fill(list(zip(xs,ys)),baseline=offset,fill=i.mix(color,'white',.65),stroke='none')
        panel.line(list(zip(xs,ys)),stroke=color,stroke_width=.24)
    panel.axis('bottom',label='Position / relative units',ticks=[-4,-2,0,2,4])
    panel.axis('left',label='Trace index (vertically offset)',ticks=[0,4,8,12,16])
    return panel.build()


def scene_art(scene, quality, *, sketch=False):
    return i.render_blend(scene,width=155,height=103,camera='Overview',engine='CYCLES',
                          quality=quality,style='sketch' if sketch else 'authored').diagram


def make_document(entry, *, scene=None, quality='final'):
    name=entry['id']
    art=({'interference':interference,'attractor':attractor,'wave-packets':wave_packets}[name]()
         if entry['category']=='Mathematical plots' else
         scene_art(scene,quality,sketch=name.endswith('-sketch')))
    doc=i.preset('scientific.general').document(width=190,margin=8,gap=5)
    doc.add('category',i.text('INKLET  /  '+entry['category'].upper(),size=i.pt(7),text_fill='#49647a'))
    doc.add('title',i.text(entry['title'],size=i.pt(20),text_fill='#172b42'))
    doc.add('description',i.text(entry['description'],size=i.pt(8),text_fill='#49647a'))
    doc.add('artwork',art)
    if name=='photonics':
        response=i.panel(130,22,x=(-3,3),y=(0,1.1))
        xs=[-3+k/100 for k in range(601)]
        ys=[(1-.85/(1+((x-.9)/.11)**2))*(1-.7/(1+((x+1.1)/.16)**2)) for x in xs]
        response.line(list(zip(xs,ys)),stroke='#248e9b',stroke_width=.35)
        response.axes(x='Detuning / relative units',y='Transmission')
        doc.add('illustrative-spectrum',response.build())
        doc.add('spectrum-note',i.text('Analytic illustration; not simulated from the device geometry',size=i.pt(6.5)))
    doc.add('provenance',i.text('Mathematical / simulated data' if entry['category']=='Mathematical plots'
                              else 'Illustrative scene · source and credits included',size=i.pt(6.5),text_fill='#49647a'))
    return doc
