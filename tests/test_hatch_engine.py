"""Hatch fill opacity, resource reuse and transformed vector geometry."""
from __future__ import annotations

from io import BytesIO
import math
import shutil
import subprocess

import pytest
import inklet as i
from inklet.core import Affine, Diagram, PathPrim, Rect, RectPrim, Style, Subpath, Vec2


def shape(**style):
    return Diagram(prim=RectPrim(24,16),style=Style(**style))


def previews(node,tmp_path):
    Image=pytest.importorskip('PIL.Image')
    pytest.importorskip('resvg_py')
    if shutil.which('pdftoppm') is None:pytest.skip('Poppler not installed')
    path=tmp_path/'figure.pdf'
    path.write_bytes(i.to_pdf(node,margin=5,background='white'))
    subprocess.run(['pdftoppm','-r','254','-png','-singlefile',str(path),str(tmp_path/'pdf')],
                   check=True,capture_output=True)
    svg=Image.open(BytesIO(i.to_png(node,margin=5,background='white',dpi=254))).convert('RGB')
    pdf=Image.open(tmp_path/'pdf.png').convert('RGB')
    return svg,pdf


def pixel(node,point):
    box=node.bbox
    return round((point.x-box.x0+5)*10),round((point.y-box.y0+5)*10)


@pytest.mark.parametrize('background',[None,'red'])
@pytest.mark.parametrize('outer',[1,.5])
@pytest.mark.parametrize('border_alpha',[0,.8])
def test_hatch_fill_alpha_is_independent_of_border_and_applied_once(background,outer,border_alpha,tmp_path):
    node=i.paint(shape(stroke='black',stroke_width=1,stroke_dash=(1,2),stroke_linecap='round',
                       stroke_opacity=border_alpha,fill_opacity=.25),
                 i.Hatch(color='blue',background=background,spacing=4,stroke=1,angle=0))
    node=Diagram(children=(node,),style=Style(opacity=outer))
    svg,pdf=previews(node,tmp_path)
    for point,color in [(Vec2(0,0),(0,0,255)),(Vec2(0,2),(255,0,0) if background else (255,255,255))]:
        expected=tuple(round(255*(1-.25*outer)+v*.25*outer) for v in color)
        for image in (svg,pdf):
            assert max(abs(a-b) for a,b in zip(image.getpixel(pixel(node,point)),expected)) <= 3


def test_first_placement_style_cannot_change_later_hatch_resources(tmp_path):
    brush=i.Hatch(color='blue',background='red',spacing=4,stroke=1,angle=0)
    left=i.paint(shape(fill_opacity=.2,stroke_opacity=.1,stroke_dash=(1,3)),brush).translated(-15,0)
    right=i.paint(shape(fill_opacity=.8,stroke_opacity=.9),brush).translated(15,0)
    a=Diagram(children=(left,right));b=Diagram(children=(right,left))
    images_a=previews(a,tmp_path);images_b=previews(b,tmp_path)
    for image_a,image_b in zip(images_a,images_b):
        assert image_a.tobytes()==image_b.tobytes()


@pytest.mark.parametrize('angle', [0,37,90,-45])
@pytest.mark.parametrize('transform',[Affine.translation(11,-4),
    Affine.translation(-8,12) @ Affine.rotation(23) @ Affine.scaling(1.4,.7),
    Affine(a=-1,b=.2,c=.35,d=1.1,e=3,f=-5)])
def test_hatch_phase_and_spacing_follow_local_transform(angle,transform,tmp_path):
    brush=i.Hatch(color='blue',background='red',spacing=4,stroke=1,angle=angle)
    node=i.paint(shape(fill_opacity=.5,stroke_opacity=.2),brush).placed(transform)
    svg,pdf=previews(node,tmp_path)
    tangent=Vec2(math.cos(math.radians(angle)),math.sin(math.radians(angle)))
    normal=tangent.perp()
    for across in (-4,-2,0,2,4):
        for along in (-3,0,3):
            local=tangent*along+normal*across
            expected=(128,128,255) if across%4==0 else (255,128,128)
            xy=pixel(node,transform.apply(local))
            for image in (svg,pdf):
                assert max(abs(a-b) for a,b in zip(image.getpixel(xy),expected)) <= 4


@pytest.mark.parametrize('rule',['evenodd','nonzero'])
def test_hatch_paths_preserve_holes(rule,tmp_path):
    outer=tuple(Vec2(*p) for p in [(-12,-8),(12,-8),(12,8),(-12,8)])
    inner=tuple(Vec2(*p) for p in [(-4,-4),(4,-4),(4,4),(-4,4)])
    if rule=='nonzero':inner=inner[::-1]
    node=i.paint(Diagram(prim=PathPrim((Subpath(outer,True),Subpath(inner,True)),
                                      filled=True,fill_rule=rule)),
                 i.Hatch(color='blue',background='red',spacing=4,stroke=1,angle=0))
    for image in previews(node,tmp_path):
        assert image.getpixel(pixel(node,Vec2(0,0)))==(255,255,255)
        assert max(abs(a-b) for a,b in zip(image.getpixel(pixel(node,Vec2(8,0))),(0,0,255))) <= 2


def test_pdf_reuses_geometry_across_placements_styles_and_pages():
    brush=i.Hatch(spacing=.1,stroke=.02)
    nodes=[i.paint(shape(fill_opacity=.2+j*.1,stroke='red',stroke_opacity=.9-j*.1),brush).translated(j*30,0)
           for j in range(6)]
    pdf=i.to_pdf([Diagram(children=tuple(nodes)),i.paint(shape(stroke='blue'),brush)],compress=False)
    assert pdf.count(b'/Subtype /Form')==1
    assert pdf.count(b'/Fm0 Do')==7
    assert b'/Subtype /Image' not in pdf
    assert i.to_pdf([Diagram(children=tuple(nodes)),i.paint(shape(stroke='blue'),brush)],compress=False)==pdf


def test_pdf_can_share_fills_under_different_clips_but_keeps_brushes_separate():
    nodes=[i.paint(shape(corner_radius=radius),i.Hatch(spacing=spacing))
           for radius,spacing in ((0,2),(3,2),(0,3))]
    pdf=i.to_pdf(Diagram(children=tuple(nodes)),compress=False)
    assert pdf.count(b'/Subtype /Form')==2
    assert pdf.count(b'/Fm0 Do')==2


@pytest.mark.parametrize('spacing',[1e-5,1e-308])
@pytest.mark.parametrize('backend',[i.to_pdf,i.to_svg])
def test_backends_bound_hatch_work(spacing,backend):
    with pytest.raises(i.DiagramError,match='100,000 lines'):
        backend(i.paint(shape(),i.Hatch(spacing=spacing)))


def test_svg_reuses_fill_geometry_and_retains_separate_authored_outlines():
    import xml.etree.ElementTree as ET
    brush=i.Hatch(spacing=.1,stroke=.02)
    nodes=[i.paint(shape(stroke='red' if j%2 else 'blue'),brush).translated(j*30,0) for j in range(6)]
    root=Diagram(children=tuple(nodes));svg=i.to_svg(root)
    assert i.to_svg(root)==svg
    tree=ET.fromstring(svg);ns={'s':'http://www.w3.org/2000/svg'}
    assert len(tree.findall('.//s:use',ns))==6
    assert len(tree.findall('.//s:clipPath',ns))==1
    assert not tree.findall('.//s:pattern',ns) and not tree.findall('.//s:image',ns)


def test_nearby_sizes_share_coverage_without_changing_clip_geometry():
    brush=i.Hatch(spacing=.08,stroke=.015)
    root=Diagram(children=tuple(i.paint(Diagram(prim=RectPrim(48+j*.001,28)),brush).translated(j*55,0)
                                for j in range(8)))
    pdf=i.to_pdf(root,compress=False)
    assert pdf.count(b'/Subtype /Form')==1
    assert b'48.007 28 re' in pdf


def test_coverage_rounding_does_not_reject_an_existing_limit_case():
    from inklet.render.hatching import hatch_bounds
    box=Rect(0,.001,1,100.001)
    assert hatch_bounds(box,i.Hatch(spacing=.001,angle=0))==box


def test_coverage_never_shrinks_at_floating_point_grid_boundaries():
    from inklet.render.hatching import hatch_bounds
    for x in (-8.,-3.2,0.,3.2,8.):
        for toward in (-math.inf,math.inf):
            edge=math.nextafter(x,toward)
            box=Rect(edge,edge,edge+1,edge+2)
            for spacing in (.003,.08,.1,.37,1.5):
                cover=hatch_bounds(box,i.Hatch(spacing=spacing))
                assert cover.x0<=box.x0 and cover.y0<=box.y0
                assert cover.x1>=box.x1 and cover.y1>=box.y1
