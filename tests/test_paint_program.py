import shutil
import pytest
import inklet as i
from inklet.core import Diagram, Style
from inklet.render.paint import resolve_paint


def specimen():
    a=i.box('H_{2}O',width=20,height=14,fill='#d86644',fill_opacity=.6,radius=2)
    b=i.circle('β',width=17,height=17,fill='#4477bb',stroke='#222',stroke_width=.7)
    group=i.hstack([a,b],gap=-5).styled(opacity=.45)
    return i.clip(group,i.Rect(-20,-12,20,12))


def test_paint_program_preserves_compositing_and_resolves_inheritance():
    child=Diagram(style=Style(fill='red'))
    group=Diagram(children=(child,),style=Style(opacity=.4,stroke_linecap='round'))
    program=resolve_paint(group)
    assert program.root.style.opacity==.4
    assert program.root.children[0].style.opacity is None
    assert program.root.children[0].style.stroke_linecap=='round'
    assert program.root.children[0].style.fill=='red'


def test_nested_opacity_stays_local_while_siblings_inherit_paint():
    branch = Diagram(children=(Diagram(style=Style(opacity=.6)), Diagram()),
                     style=Style(opacity=0., fill='blue'))
    root = Diagram(children=(branch, Diagram(style=Style(opacity=.8))),
                   style=Style(opacity=.4, fill='red', fill_opacity=.7))
    program = resolve_paint(root, stable_ids=True)
    nodes = list(program.root.walk())
    assert [node.style.opacity for node in nodes] == [.4, 0., .6, None, .8]
    assert [node.style.fill for node in nodes] == ['red', 'blue', 'blue', 'blue', 'red']
    assert all(node.style.fill_opacity == .7 for node in nodes)
    assert program.node_count == len(program.ids) == len(nodes) == 5
    assert branch.children[1].style == Style()


def test_resolved_paint_is_visually_identical_for_both_backends(tmp_path):
    Image=pytest.importorskip('PIL.Image')
    ImageChops=pytest.importorskip('PIL.ImageChops')
    if not shutil.which('pdftoppm') or not any(shutil.which(n) for n in ('google-chrome','chromium','chromium-browser')):
        pytest.skip('preview renderers required')
    from inklet.render.preview import svg_png,pdf_png
    from inklet.figure import apply_theme
    root=apply_theme(specimen(),i.current_theme())
    compiled=resolve_paint(root).root
    for ext,writer,renderer in [('svg',i.to_svg,svg_png),('pdf',i.to_pdf,pdf_png)]:
        images=[]
        for name,node in [('before',root),('after',compiled)]:
            path=tmp_path/f'{name}.{ext}'
            content=writer(node,text='embed',background='white')
            path.write_bytes(content.encode() if isinstance(content,str) else content)
            png=renderer(path,tmp_path/f'{name}-{ext}.png',dpi=150)
            with Image.open(png) as image:images.append(image.convert('RGB'))
        assert ImageChops.difference(*images).getbbox() is None
