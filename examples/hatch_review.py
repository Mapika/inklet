"""Hatched plots, inherited opacity, transformed sections and shared fills."""
from __future__ import annotations

import argparse
from pathlib import Path

import inklet as i
from inklet.core import Affine, Diagram, Envelope, PathPrim, Rect, RectPrim, Style, Subpath, Vec2

ROOT=Path(__file__).resolve().parents[1]
CAPTION='''Hatch rendering checks with original simulated data and artwork.
(a) Supplied simulated yields of 28, 46, 37 and 62 percent, with 30 percent
fill opacity and independent solid outlines. (b) The same hatch brush under
inherited fill opacities of 25 and 70 percent, with independent dashed outlines.
(c) A section with an even-odd hole under rotation and nonuniform scaling;
hatch spacing is measured in local millimetres. (d) Sixteen boxes whose widths
differ by 0.01 mm, sharing hatch coverage while retaining their exact clips.
All hatches, borders, axes and text are vector. No measured data or fitted
uncertainty is shown. Recipe and artwork: MIT, Mark Marosi.
'''


def frame(children):
    return Diagram(children=tuple(children),envelope_override=Envelope.from_rect(Rect(-37,-23,37,23)))


def make_document():
    doc=i.preset('scientific.general').customize(width=190,margin=6,gap=10).document(
        columns=2,row_gap=10).letters()
    brush=i.Hatch(color='#245b8a',background='#dce9ed',spacing=1.4,stroke=.28)
    p=i.panel(58,38,x=('A','B','C','D'),y=(0,80))
    p.bars(('A','B','C','D'),(28,46,37,62),fill_opacity=.3,stroke='#245b8a',stroke_opacity=1)
    p.axes(x='Treatment',y='Yield / %')
    doc.add('bars',i.paint(p.build(),brush),row=0,column=0,align='nw')
    samples=[]
    comparison_brush=i.Hatch(color='#245b8a',background='#dce9ed',spacing=1.5,stroke=.3)
    for x,alpha in ((-18,.25),(18,.7)):
        shape=Diagram(prim=RectPrim(28,28))
        painted=i.paint(shape,comparison_brush)
        samples.append(Diagram(children=(painted,),style=Style(fill_opacity=alpha,
            stroke='#245b8a',stroke_opacity=.9,stroke_width=.6,stroke_dash=(2,1))).translated(x,0))
    doc.add('opacity',frame(samples),row=0,column=1,align='nw')
    outer=tuple(Vec2(*p) for p in ((-23,-15),(23,-15),(23,15),(-23,15)))
    hole=tuple(Vec2(*p) for p in ((-7,-7),(7,-7),(7,7),(-7,7)))
    section=i.paint(Diagram(prim=PathPrim((Subpath(outer,True),Subpath(hole,True)),filled=True,fill_rule='evenodd'),
        style=Style(stroke='#245b8a',stroke_width=.5,fill_opacity=.6)),brush)
    section=section.placed(Affine.rotation(16) @ Affine.scaling(1.1,.8))
    doc.add('section',frame([section]),row=1,column=0,align='nw')
    tiles=[]
    for j in range(16):
        shape=Diagram(prim=RectPrim(14+j*.01,8),style=Style(stroke='#245b8a',stroke_width=.3))
        tiles.append(i.paint(shape,brush).translated((j%4-1.5)*17,(j//4-1.5)*11))
    doc.add('shared',frame(tiles),row=1,column=1,align='nw')
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/hatch-review')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    compiled=make_document().compile()
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('%',r'\%').replace('\n',' ').strip()+'}\n')
    print(args.output/'figure.svg')


if __name__=='__main__':main()
