"""Paint bounds and export-local resource reuse."""
import io
import shutil
import subprocess
from dataclasses import replace
import pytest
import inklet as i
from inklet.core import Affine, Diagram, Envelope, ImagePrim, Rect, RectPrim, Style
from inklet.render.bounds import painted_bounds


def test_painted_bounds_ignore_layout_override_and_include_transformed_strokes():
    child = Diagram(prim=RectPrim(10,6),style=Style(fill='none',stroke='red',stroke_width=2),
                    transform=Affine.scaling(2,3))
    root = Diagram(children=(child,),envelope_override=Envelope.from_rect(Rect(0,0,1,1)))
    box = painted_bounds(root,Affine(),Style())
    assert box.x0 <= -12 and box.x1 >= 12
    assert box.y0 <= -12 and box.y1 >= 12
    assert root.bbox.width == 1


@pytest.mark.skipif(shutil.which('pdftoppm') is None,reason='Poppler not installed')
@pytest.mark.parametrize('kind',['stroke','halo'])
def test_pdf_transparency_keeps_ink_outside_layout_bounds(tmp_path,kind):
    Image = pytest.importorskip('PIL.Image')
    pytest.importorskip('resvg_py')
    if kind == 'stroke':
        content = Diagram(children=(
            Diagram(prim=RectPrim(10,8)).styled(fill='none',stroke='black',stroke_width=3),
            Diagram(prim=RectPrim(2,2)).translated(8,0).styled(fill='red',stroke='none')))
    else:
        content = i.hstack([i.text('f',size=10,font_style='italic',halo=3,halo_color='black'),
                            i.text('j',size=10,halo=3,halo_color='black')],gap=4)
    content = content.styled(opacity=.6).rotated(12)
    options = dict(margin=8,background='white')
    expected = Image.open(io.BytesIO(i.to_png(content,dpi=254,**options))).convert('RGB')
    path = tmp_path/'group.pdf'
    path.write_bytes(i.to_pdf(content,**options))
    subprocess.run(['pdftoppm','-r','254','-png','-singlefile',str(path),str(tmp_path/'group')],check=True,capture_output=True)
    actual = Image.open(tmp_path/'group.png').convert('RGB')
    # Compare coverage, including ink beyond the geometric box. Independent
    # rasterizers may differ on the antialiasing fringe and page rounding.
    w,h = min(actual.width,expected.width),min(actual.height,expected.height)
    a = [min(p)<220 for p in zip(*[iter(actual.crop((0,0,w,h)).tobytes())]*3)]
    b = [min(p)<220 for p in zip(*[iter(expected.crop((0,0,w,h)).tobytes())]*3)]
    assert sum(x and y for x,y in zip(a,b))/sum(x or y for x,y in zip(a,b)) > .96


def test_svg_encodes_repeated_payload_once_per_export(monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    import inklet.render.svg as svg
    data = io.BytesIO();Image.new('RGB',(8,8),'red').save(data,format='PNG')
    prim = ImagePrim('test',10,10,data=data.getvalue())
    root = Diagram(children=tuple(Diagram(prim=replace(prim,width=10+j)).translated(j*15,0) for j in range(8)))
    original = svg._data_uri
    calls = []
    def encoded(prim):
        calls.append(prim)
        return original(prim)
    monkeypatch.setattr(svg,'_data_uri',encoded)
    first = svg.to_svg(root)
    assert len(calls) == 1 and first.count('data:image/png;base64,') == 1
    assert svg.to_svg(root) == first and len(calls) == 2


def test_image_file_edits_are_visible_on_the_next_export(tmp_path):
    Image = pytest.importorskip('PIL.Image')
    path = tmp_path/'image.png'
    Image.new('RGB',(8,8),'red').save(path)
    root = Diagram(prim=ImagePrim(str(path),10,10))
    before = i.to_svg(root)
    Image.new('RGB',(8,8),'blue').save(path)
    assert i.to_svg(root) != before


def test_renumbered_geometry_reuses_measurements_without_sharing_annotations():
    original = i.box('Geometry',width=30,height=20)
    box, trace = original.bbox, original.trace
    copied = original.copy()
    assert copied.id != original.id
    assert copied.envelope is original.envelope and copied.trace is trace
    copied.note('changed',True).anchor('extra',(1,2))
    assert 'changed' not in original.notes and 'extra' not in original.anchors
    assert copied.translated(7,3).bbox == box.transform(Affine.translation(7,3))
