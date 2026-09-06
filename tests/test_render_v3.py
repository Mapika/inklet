"""Renderer contracts: physical PNG, vector brushes, blends and raster masks."""
from io import BytesIO

import pytest
import inklet as i
from inklet.core import Diagram, RectPrim
from inklet.render.preview import pdf_png
from inklet.render.resources import rendering_manifest

pytest.importorskip('resvg_py')
from PIL import Image


def rect(width=40,height=20,fill='#ffffff'):
    return Diagram(prim=RectPrim(width,height),style=i.Style(fill=fill,stroke='none'))


def pixels(node,**options):
    return Image.open(BytesIO(i.to_png(node,**options))).convert('RGBA')


def test_png_physical_size_transparency_and_dpi():
    picture=Image.open(BytesIO(i.to_png(rect(25.4,12.7),dpi=200,margin=2.54)))
    assert picture.size==(240,140)
    assert picture.info['dpi'][0]==pytest.approx(200,abs=.02)
    assert picture.convert('RGBA').getpixel((0,0))[3]==0
    assert picture.convert('RGBA').getpixel((120,70))==(255,255,255,255)
    with pytest.raises(ValueError):i.to_png(rect(),dpi=0)
    with pytest.raises(ValueError):i.to_png(rect(),dpi=100000)


def test_raster_layer_preserves_transformed_bounds_and_anchors():
    original=rect().translated(13,-7).rotated(25)
    original.anchor('point',i.Vec2(2,3))
    result=i.rasterize(original,dpi=200)
    for a,b in zip(result.bbox.corners,original.bbox.corners):
        assert (a-b).length < 1e-8
    assert (result.transform.apply(result.anchor_point('point'))-
            original.transform.apply(original.anchor_point('point'))).length < 1e-8
    assert rendering_manifest(result)['raster_layers'][0]['reason']=='explicit raster layer'


@pytest.mark.parametrize('brush',[i.LinearGradient(((0,'#225588'),(.4,'#eeee99'),(1,'#cc5533'))),
    i.RadialGradient(((0,'white'),(1,'#334477'))),i.Hatch(background='#eeeeee')])
def test_brushes_are_vector_and_match_pdf_pixels(brush,tmp_path):
    node=i.paint(rect(),brush)
    svg=i.to_svg(node);pdf=i.to_pdf(node)
    assert 'data:image' not in svg and b'/Subtype /Image' not in pdf
    assert i.to_pdf(node)==pdf
    assert rendering_manifest(node)['paint_resources'][0]['type']==type(brush).__name__
    (tmp_path/'figure.pdf').write_bytes(pdf)
    pdf_png(tmp_path/'figure.pdf',tmp_path/'pdf.png',dpi=254)
    a=pixels(node,dpi=254).convert('RGB');b=Image.open(tmp_path/'pdf.png').convert('RGB')
    # Compare interiors to avoid independent antialiasing at the page boundary.
    for x,y in ((30,30),(60,40),(100,60),(160,70)):
        assert max(abs(u-v) for u,v in zip(a.getpixel((x,y)),b.getpixel((x,y)))) < 30
    from PIL import ImageChops, ImageStat
    assert max(ImageStat.Stat(ImageChops.difference(a,b).crop((3,3,197,97))).mean) < 5


def test_pdf_identity_includes_gradient_resources():
    import re
    def identity(color):
        node=i.paint(rect(),i.LinearGradient(((0,'white'),(1,color))))
        return re.search(rb'/ID \[<([^>]+)>',i.to_pdf(node))[1]
    assert identity('red') != identity('blue')


def test_mask_uses_world_alignment_and_records_rasterization():
    source=rect(40,20,'#336699')
    stencil=rect(20,20).translated(-10,0)
    result=i.mask(source,stencil,mode='alpha',dpi=127)
    picture=pixels(result,dpi=127)
    assert picture.getpixel((20,50))[3]==255
    assert picture.getpixel((180,50))[3]==0
    assert rendering_manifest(result)['raster_layers'][0]['reason']=='alpha mask'


@pytest.mark.parametrize('mode',['multiply','screen','difference'])
def test_group_blends_match_pdf(mode,tmp_path):
    node=Diagram(children=(rect(fill='#6688aa'),i.blend(rect(20,10,'#aa7744'),mode)))
    a=pixels(node,dpi=127).convert('RGB')
    (tmp_path/'figure.pdf').write_bytes(i.to_pdf(node))
    pdf_png(tmp_path/'figure.pdf',tmp_path/'pdf.png',dpi=127)
    b=Image.open(tmp_path/'pdf.png').convert('RGB')
    assert max(abs(u-v) for u,v in zip(a.getpixel((100,50)),b.getpixel((100,50))))<=3


def test_repeated_image_resources_are_shared():
    original=i.rasterize(rect(),dpi=50)
    node=i.hstack([original,original.copy()],gap=3)
    svg=i.to_svg(node);pdf=i.to_pdf(node)
    assert svg.count('data:image/png;base64,')==1
    assert pdf.count(b'/Subtype /Image')==2  # RGB image plus its alpha mask
    assert rendering_manifest(node)['image_resources'][0]['placements']==2


def test_save_and_bundle_support_browser_free_png(tmp_path):
    doc=i.document(width=89);doc.add('label',i.component(i.text,'Rendered text'))
    compiled=doc.compile()
    compiled.save(tmp_path/'figure.png')
    assert Image.open(tmp_path/'figure.png').width>0
    files=compiled.export(tmp_path/'bundle',compare_pdf=False)
    assert 'resvg' in files['manifest'].read_text()


@pytest.mark.parametrize('factory,args',[(i.LinearGradient,(((.1,'red'),(1,'blue')),)),
    (i.RadialGradient,(((0,'red'),(.7,'blue')),)),(i.Hatch,())])
def test_invalid_paints_are_rejected(factory,args):
    with pytest.raises(ValueError):
        factory(*args,**({'spacing':0} if factory is i.Hatch else {}))
