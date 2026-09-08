"""Eight-panel clipping review: curves, bands, images, text and transformed windows."""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import inklet as i
from inklet.core import Affine, Diagram, Envelope, PathPrim, Rect, RectPrim, Style, Subpath, Vec2

ROOT=Path(__file__).resolve().parents[1]
CAPTION='''Clipping checks using original simulated data and artwork.
(a) Geometrically clipped smooth response curves, retaining cubic segments.
(b) A dense signal with a narrow peak and an explicit missing-data gap; physical
simplification tolerance 0.02 mm. (c) Filled uncertainty-like bands representing
supplied simulated intervals, cropped with their outlines. (d) Large boundary
markers and thick strokes cropped by a painted window. (e) A synthetic scalar
image under a rotated convex window. (f) Glyphs and halos cropped together.
(g) Rounded rectangles and an even-odd hole, cropped without changing their
source geometry. (h) Nested windows with group opacity beside an unclipped
sibling. Letter labels identify checks; the artwork contains no panel titles.
Recipe and artwork: MIT, Mark Marosi. No measured data or inferred uncertainty.
'''


def frame(node):
    return Diagram(children=(node,),kind='clipping-review-panel',envelope_override=Envelope.from_rect(Rect(-36,-22,36,22)))


def outline():
    return i.polyline([(-30,-16),(30,-16),(30,16),(-30,16),(-30,-16)],stroke='#87939c',stroke_width=.25)


def make_document(asset_dir):
    from PIL import Image
    asset_dir.mkdir(parents=True,exist_ok=True)
    bitmap=Image.new('RGB',(960,640))
    bitmap.putdata([(round(35+170*x/959),round(60+140*y/639),round(130+70*math.sin(x/100)*math.cos(y/85)))
                    for y in range(640) for x in range(960)])
    image_path=asset_dir/'field.png';bitmap.save(image_path)
    doc=i.preset('scientific.general').customize(width=190,margin=6,gap=10).document(columns=2,row_gap=8).letters()
    box=Rect(-30,-16,30,16)
    curves=[i.curve([(x,18*math.sin(x/10+phase)) for x in range(-40,41,4)],
                    stroke=color,stroke_width=.65) for phase,color in ((0,'#245b8a'),(1,'#d17839'))]
    doc.add('curves',frame(Diagram(children=(i.clip(curves,box),outline()))),row=0,column=0)
    p=i.panel(60,32,x=(0,10),y=(-1.2,2),clip=True)
    points=[(k/1000,math.sin(k/700)+2*math.exp(-((k/1000-4.25)/.025)**2))
            for k in range(10001)]
    p.line(points[:6500],stroke='#245b8a',simplify=.02)
    p.line(points[6900:],stroke='#245b8a',simplify=.02)
    p.axes()
    doc.add('dense',p.build(),row=0,column=1)
    xs=[x/5 for x in range(-200,201)]
    band=i.polygon([(x,10*math.sin(x/12)-5) for x in xs]+
                   [(x,10*math.sin(x/12)+5) for x in reversed(xs)],
                   fill='#80b5c7',fill_opacity=.45,stroke='#245b8a',stroke_width=.7)
    doc.add('band',frame(Diagram(children=(i.window(band,box),outline()))),row=1,column=0)
    marks=[i.marker('circle',9,fill='#d17839',stroke='white',stroke_width=.8).translated(x,0)
           for x in (-30,-15,0,15,30)]
    marks.append(i.polyline([(-40,-20),(40,20)],stroke='#245b8a',stroke_width=3))
    doc.add('markers',frame(Diagram(children=(i.window(marks,box),outline()))),row=1,column=1)
    image=i.asset(image_path,width=80,cutout=None)
    doc.add('image',frame(i.window(image,[(-28,-16),(27,-13),(22,15),(-23,17)]).rotated(7)),row=2,column=0)
    text=i.text('Inklet / Aa 0123456789',size=10,fill='#245b8a',halo=1.2,halo_color='#c3dde4')
    doc.add('glyphs',frame(Diagram(children=(i.window(text,Rect(-29,-3,29,3)),outline()))),row=2,column=1)
    outer=Rect(-17,-13,17,13).corners;inner=Rect(-7,-7,7,7).corners
    hole=Diagram(prim=PathPrim((Subpath(outer,True),Subpath(inner,True)),True,'evenodd'),
                 style=Style(fill='#245b8a',stroke='#16354a',stroke_width=.6)).translated(14,0)
    rounded=Diagram(prim=RectPrim(30,28,8),style=Style(fill='#d17839',stroke='#794321',stroke_width=1)).translated(-21,0)
    doc.add('shapes',frame(Diagram(children=(i.window([rounded,hole],box),outline()))),row=3,column=0)
    tiles=[Diagram(prim=RectPrim(30,25,4),style=Style(fill=c,stroke='none')).translated(x,0)
           for x,c in ((-10,'#245b8a'),(10,'#d17839'))]
    nested=i.window(i.window(tiles,Rect(-25,-12,25,12)),[(-25,-16),(24,-12),(5,18)],opacity=.55)
    sibling=i.marker('circle',5,fill='#245b8a',stroke='none').translated(29,11)
    doc.add('nested',frame(Diagram(children=(nested,sibling))),row=3,column=1)
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/clipping-review')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    compiled=make_document(args.output).compile()
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    print(compiled.report());print(args.output/'figure.svg')


if __name__=='__main__':main()
