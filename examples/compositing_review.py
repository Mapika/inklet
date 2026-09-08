"""Original artwork for image transparency and nested vector compositing."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path

import inklet as i
from inklet.core import Diagram, Envelope, ImagePrim, Rect, RectPrim

ROOT = Path(__file__).resolve().parents[1]
CAPTION = '''Compositing checks using original artwork, with no measured data.
(a) A palette PNG with transparent, partially transparent and opaque entries
over blue and orange vector blocks. (b) Individual filled-and-stroked shapes
at 50 percent group opacity: each border overlaps its fill. (c) Italic text
and its red halo faded together at 50 percent opacity. (d) Labeled vector
blocks inside 32 groups, each at 99 percent opacity. All text and shape
layers remain vector in SVG/PDF; only panel a contains an image.
Recipe and artwork: MIT, Mark Marosi.
'''


def palette_art():
    from PIL import Image
    image = Image.new('P',(48,24))
    image.putpalette([255,255,255, 25,80,110, 25,80,110, 25,80,110]+[0]*756)
    values = []
    for y in range(24):
        for x in range(48):
            radius = ((x-23.5)/2)**2+(y-11.5)**2
            values.append(3 if radius<20 else 2 if radius<55 else 1 if radius<100 else 0)
    image.putdata(values)
    output=BytesIO()
    image.save(output,format='PNG',transparency=bytes([0,85,170,255]))
    return output.getvalue()


def panel(children):
    return Diagram(children=tuple(children),envelope_override=Envelope.from_rect(Rect(0,0,74,42)))


def specimens():
    def box(x,y,fill,opacity=1):
        return Diagram(prim=RectPrim(24,22)).styled(fill=fill,stroke='#245b8a',
            stroke_width=3,opacity=opacity).translated(x,y)
    image = panel([
        Diagram(prim=RectPrim(28,26)).styled(fill='#b8d4df',stroke='none').translated(23,22),
        Diagram(prim=RectPrim(28,26)).styled(fill='#edc5a9',stroke='none').translated(51,22),
        Diagram(prim=ImagePrim('original palette artwork',56,28,data=palette_art(),smooth=False)).translated(37,22),
    ])
    shapes = panel([box(20,22,'#d55e00',.5),box(54,22,'#edbf55',.5)])
    halo = panel([i.text('f(x)',size=13,font_style='italic',text_fill='#245b8a',
                        halo=2,halo_color='#d55e00').styled(opacity=.5).translated(37,23)])
    blocks = []
    for row in range(2):
        for column in range(3):
            x,y=15+22*column,13+18*row
            blocks.extend([
                Diagram(prim=RectPrim(19,13)).styled(fill='#d5e9f4',stroke='#245b8a',
                    stroke_width=.6).translated(x,y),
                i.text(f'{row*3+column+1}',size=3,halo=.3).translated(x,y),
            ])
    nested=Diagram(children=tuple(blocks))
    for _ in range(32):
        nested=Diagram(children=(nested,),style=i.Style(opacity=.99))
    return image,shapes,halo,panel([nested])


def make_document():
    doc=i.preset('scientific.general').customize(width=180,margin=6,gap=8).document(columns=2).letters()
    for index,(name,node) in enumerate(zip(('palette','overlap','halo','nested'),specimens())):
        doc.add(name,node,row=index//2,column=index%2,align='nw')
    return doc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/compositing-review')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    compiled=make_document().compile()
    if any(d.severity in ('error','warning') for d in compiled.diagnostics):
        raise RuntimeError(compiled.report())
    compiled.save(args.output/'figure.svg',args.output/'figure.pdf',args.output/'figure.png')
    (args.output/'caption.tex').write_text('\\caption{'+CAPTION.replace('\n',' ').strip()+'}\n')
    (args.output/'caption.txt').write_text(CAPTION)
    (args.output/'report.json').write_text(json.dumps(dict(version=i.__version__,
        width_mm=compiled.root.width,height_mm=compiled.root.height,
        stats=dict(compiled.stats)),indent=2)+'\n')
    print(args.output/'figure.svg')


if __name__=='__main__':main()
