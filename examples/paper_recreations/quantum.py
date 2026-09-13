"""Six native logarithmic response maps from released scalar samples."""
import io,zipfile
import numpy as np
import inklet as i
from canvas import Page

# Mathematica-style SolarColors, sampled at 65 positions from the published color key (style only).
COLORS=['#f3f4dc', '#eef0dd', '#e5ecde', '#dfe8df', '#d7e4e0', '#d0dfe1', '#c7dbe2', '#c0d6e3', '#b7d2e3', '#b1cde5', '#a8c9e6', '#a0c4e7', '#97c0e8', '#8fbbe8', '#86b7e9', '#7fb3eb', '#76afec', '#6daaed', '#63a6ed', '#5aa0ee', '#519cef', '#4797f0', '#4f95ec', '#5d94e7', '#6993e2', '#7592dd', '#7e91d8', '#8990d3', '#928fcd', '#9c8ec8', '#a68dc3', '#ae8cbe', '#b88bb9', '#bf8bb5', '#c989af', '#d089aa', '#d987a4', '#df879f', '#e98599', '#ef8595', '#fb838f', '#ff838b', '#ff8285', '#ff827f', '#ff8678', '#ff8a71', '#ff8e6b', '#ff9264', '#ff965d', '#ff9b55', '#ff9f4e', '#ffa346', '#ffa73e', '#ffac35', '#ffaf2c', '#ffb321', '#ffb712', '#ffbb00', '#ffbf00', '#ffc400', '#ffc800', '#ffcc00', '#ffd000', '#ffd400', '#ffd800']


def build(ref):
    page=Page(2050,1202,physical_width=210,font='Liberation Serif');records=[]
    with zipfile.ZipFile(ref/'quantum-41467_2024_55124_MOESM6_ESM.zip') as archive:
        for letter,col,row in [('a',0,0),('b',1,0),('c',0,1),('d',1,1),('e',2,0),('f',2,1)]:
            name=f'Source_Data/figure_5{letter}.txt';data=np.loadtxt(io.BytesIO(archive.read(name)))
            xs,ys=np.unique(data[:,1]),np.unique(data[:,2]);assert len(xs)*len(ys)==len(data)
            matrix=np.empty((len(ys),len(xs)));matrix[np.searchsorted(ys,data[:,2]),np.searchsorted(xs,data[:,1])]=data[:,0]
            maximum=float(matrix.max());values=matrix[::-1]/maximum
            box=(117+col*623,27+row*607,480,467);x,y,w,h=box
            p=page.plot(letter,box,i.log((1e-3,1e6)),i.log((1e-3,1e6)),[1e-3,1,1e3,1e6],
                [1e-3,1e-1,1e1,1e3,1e5],xlabel='kₛ / μs⁻¹' if row else None,ylabel='kₜ / μs⁻¹' if col==0 else None,
                tick_size=30,label_size=32)
            p.matrix(values,ramp=i.ramp(COLORS),scale=i.linear((0,1)),vector='seamless')
            p.guide((1e-3,1e-3),(1e6,1e6),label='k_{S} = k_{T}',at=.2,offset=12*page.s,
                label_style=dict(size=31*page.s,font='Liberation Serif',font_style='italic'),
                stroke='black',stroke_width=3*page.s,stroke_dash=(3*page.s,4*page.s))
            page.add_plot(p,box)
            page.text(letter+')',x-87,y-28,34,font='Arimo')
            label=f'{maximum:.1f}' if letter=='a' else f'{maximum:.2f}'
            page.text(f'S_{{MAX}} = {label}%',x+39,y+28,33,markup=True,italic=True)
            records.append(dict(panel=letter,rows=len(ys),columns=len(xs),maximum_percent=maximum,
                source=name,x_domain=[float(xs[0]),float(xs[-1])],y_domain=[float(ys[0]),float(ys[-1])]))
    page.line([(1267,26),(1267,1200)],width=3,dash=(7,8))
    # One normalized key serves six independently normalized maps, as published.
    ramp=i.ramp(COLORS)
    for n in range(256):page.rect(1899,70+n*995/256,28,995/256+1,ramp(1-n/255))
    page.rect(1899,70,28,995,stroke='black',width=2)
    page.text('%S_{MAX}',1939,52,31,markup=True,italic=True);page.text('0',1939,1055,31)
    return page,{'maps':records,'axes':6,'normalization':'each map divided by its own maximum, matching the published normalized key','interpolation':'native 200 × 200 cells with exact foreground boundaries and seamless underpaint; no synthetic points or raster image'}
