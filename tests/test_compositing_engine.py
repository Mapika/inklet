"""Image alpha, overlapping paints and page-scoped compositing geometry."""
from io import BytesIO
import shutil
import zlib

import pytest
import inklet as i
from inklet.core import Affine, Diagram, ImagePrim, RectPrim, Style
from inklet.render.analysis import CompositingAnalysis
from inklet.render.bounds import painted_bounds
from inklet.render.pdf import _image_object


def png_fixture(kind):
    Image = pytest.importorskip('PIL.Image')
    options = {}
    if kind.startswith('palette'):
        image = Image.new('P', (4, 1))
        image.putpalette([255,0,0, 0,255,0, 0,0,255, 255,255,0] + [0]*756)
        image.putdata([0,1,2,3])
        options['transparency'] = 0 if kind == 'palette-key' else bytes([0,85,170,255])
        alpha = [0,255,255,255] if kind == 'palette-key' else [0,85,170,255]
    elif kind == 'rgb-key':
        image = Image.new('RGB', (4, 1))
        image.putdata([(255,0,0),(0,255,0),(255,0,0),(0,0,255)])
        options['transparency'] = (255,0,0)
        alpha = [0,255,0,255]
    elif kind == 'gray-key':
        image = Image.new('L', (4,1))
        image.putdata([32,64,32,128])
        options['transparency'] = 32
        alpha = [0,255,0,255]
    elif kind == 'binary-key':
        image = Image.new('1', (4,1))
        image.putdata([0,255,0,255])
        options['transparency'] = 0
        alpha = [0,255,0,255]
    else:
        image = Image.new('LA' if kind == 'gray-alpha' else 'RGBA', (4,1))
        alpha = [0,85,170,255] if kind != 'opaque' else [255]*4
        image.putdata([(80,a) if kind == 'gray-alpha' else (120,60,200,a) for a in alpha])
    output = BytesIO()
    image.save(output,format='PNG',**options)
    return output.getvalue(), bytes(alpha)


@pytest.mark.parametrize('kind', ['palette-key','palette-alpha','rgb-key','gray-key',
                                  'binary-key','gray-alpha','rgba','opaque'])
@pytest.mark.parametrize('embedded', [False, True])
def test_pdf_preserves_png_transparency_metadata(kind, embedded, tmp_path):
    data, alpha = png_fixture(kind)
    path = tmp_path/'source.png'
    path.write_bytes(data)
    prim = ImagePrim(str(path),40,10,data=data if embedded else None)
    header, pixels, actual_alpha = _image_object(prim)
    assert actual_alpha == (None if kind == 'opaque' else alpha)
    assert len(zlib.decompress(pixels)) == 12
    assert b'/Width 4 /Height 1' in header


def compare_pdf(node, tmp_path, *, text='outline'):
    if shutil.which('pdftoppm') is None:
        pytest.skip('Poppler not installed')
    Image = pytest.importorskip('PIL.Image')
    pytest.importorskip('resvg_py')
    from inklet.render.preview import pdf_png
    options = dict(margin=5,background='white',text=text)
    path = tmp_path/'figure.pdf'
    path.write_bytes(i.to_pdf(node,**options))
    pdf_png(path,tmp_path/'pdf.png',dpi=254)
    svg = Image.open(BytesIO(i.to_png(node,dpi=254,**options))).convert('RGB')
    pdf = Image.open(tmp_path/'pdf.png').convert('RGB')
    return svg,pdf


@pytest.mark.parametrize('kind',['palette-key','palette-alpha','rgb-key','gray-key','binary-key'])
def test_png_transparency_matches_svg_over_colored_artwork(kind,tmp_path):
    data, _ = png_fixture(kind)
    root = Diagram(children=(
        Diagram(prim=RectPrim(40,10),style=Style(fill='#406080')),
        Diagram(prim=ImagePrim('fixture',40,10,data=data,smooth=False)),
    )).styled(opacity=.7)
    svg,pdf = compare_pdf(root,tmp_path)
    for x in (100,200,300,400):
        assert max(abs(a-b) for a,b in zip(svg.getpixel((x,100)),pdf.getpixel((x,100)))) <= 3


@pytest.mark.parametrize('outer', [False,True])
@pytest.mark.parametrize('fill_alpha,stroke_alpha',[(1,1),(.2,.6)])
def test_single_shape_fades_after_fill_and_stroke_overlap(outer,fill_alpha,stroke_alpha,tmp_path):
    shape = Diagram(prim=RectPrim(10,10),style=Style(fill='red',stroke='blue',
        stroke_width=4,fill_opacity=fill_alpha,stroke_opacity=stroke_alpha))
    root = Diagram(children=(shape,)) if outer else shape
    root = root.styled(opacity=.5)
    svg,pdf = compare_pdf(root,tmp_path)
    for point in ((40,100),(60,100),(100,100)):
        assert max(abs(a-b) for a,b in zip(svg.getpixel(point),pdf.getpixel(point))) <= 3


@pytest.mark.parametrize('text', ['outline','embed'])
@pytest.mark.parametrize('kind', ['halo','gradient','hatch'])
def test_single_complex_primitive_composites_once(kind,text,tmp_path):
    if kind == 'halo':
        node = i.text('M',size=10,halo=2,halo_color='red',text_fill='blue')
    else:
        shape = Diagram(prim=RectPrim(20,12),style=Style(stroke='blue',stroke_width=3))
        brush = i.LinearGradient(((0,'red'),(1,'yellow'))) if kind == 'gradient' else i.Hatch(
            color='red',background='yellow',spacing=3,stroke=1,angle=0)
        node = i.paint(shape,brush)
    svg,pdf = compare_pdf(node.styled(opacity=.5),tmp_path,text=text)
    # Compare uniform 7x7 source interiors, away from font hinting and
    # antialiasing differences between independent rasterizers.
    w,h = min(svg.width,pdf.width),min(svg.height,pdf.height)
    samples = 0
    for y in range(3,h-3,3):
        for x in range(3,w-3,3):
            patch = {svg.getpixel((x+dx,y+dy)) for dx in range(-3,4) for dy in range(-3,4)}
            expected = svg.getpixel((x,y))
            if len(patch) == 1 and min(expected) < 200:
                assert max(abs(a-b) for a,b in zip(expected,pdf.getpixel((x,y)))) <= 4
                samples += 1
    assert samples > 50


def test_cached_bounds_match_uncached_through_transform_and_style_changes():
    node = Diagram(children=(i.text('Italic',size=4,font_style='italic',halo=.7),
        Diagram(prim=RectPrim(8,6)).translated(12,0)))
    analysis = CompositingAnalysis()
    for transform in (Affine(),Affine.rotation(31) @ Affine.scaling(2,.5),Affine.translation(-10,8)):
        for style in (Style(),Style(stroke='red',stroke_width=2),Style(halo=3)):
            assert analysis.bounds(node,transform,style) == painted_bounds(node,transform,style)
            assert analysis.bounds(node,transform,style) == painted_bounds(node,transform,style)


def test_nested_group_bounds_are_evaluated_once_per_placement(monkeypatch):
    import inklet.render.analysis as module
    node = Diagram(children=(i.text('Bounds',size=3),Diagram(prim=RectPrim(20,8))))
    for _ in range(24):
        node = Diagram(children=(node,),style=Style(opacity=.98))
    calls = []
    original = module.primitive_bounds
    def measured(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(module,'primitive_bounds',measured)
    first = i.to_pdf(node)
    assert len(calls) == len(list(node.walk()))
    calls.clear()
    assert i.to_pdf(node) == first
    assert len(calls) == len(list(node.walk()))


def test_count_cache_distinguishes_inherited_fill_and_stroke():
    node = Diagram(prim=RectPrim(10,6))
    analysis = CompositingAnalysis()
    assert analysis.paint_count(node,Style(fill='none',stroke='red')) == 1
    assert analysis.paint_count(node,Style(fill='blue',stroke='red')) == 2
    assert analysis.paint_count(node,Style(fill='none',stroke='none')) == 0
