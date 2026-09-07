"""Physical layout regressions and large-grid allocation invariants."""
import pytest
import inklet as i
from inklet.core import RectPrim
from inklet.document.compiler import _tracks


def test_nested_fixed_drawings_keep_letter_space_and_unequal_rows():
    inner = i.subfigure(columns=2).letters()
    for name, height, row, column in [('a',40,0,0), ('b',15,0,1), ('c',12,1,0)]:
        inner.add(name, i.Diagram(prim=RectPrim(30,height)), row=row, column=column)
    outer = i.document(width=100)
    outer.add('group', inner)
    first = outer.compile()
    positions = first.build()[1]
    a, c = (positions[f'cell-group/cell-{name}'].bbox for name in ('a','c'))
    assert a.height > 40 and c.height > 12
    assert c.y0-a.y1 >= inner.row_gap-1e-6
    assert not any(d.code in ('OFF_CANVAS','RULE_FAILED') for d in first.diagnostics)
    outer.configure(width=120)
    assert outer.compile().root.height == pytest.approx(first.root.height)


def test_fixed_factory_builds_once_across_measurement_and_resize():
    calls = []
    def factory():
        calls.append(1)
        return i.box('Fixed geometry',width=32,height=18)
    doc = i.document(width=100).letters()
    doc.add('box',i.component(factory))
    first = doc.compile()
    doc.configure(width=140)
    assert doc.compile() is not first
    assert len(calls) == 1


def test_responsive_factory_still_receives_new_dimensions():
    calls = []
    def factory(width, height):
        calls.append((width,height))
        return i.box(width=width,height=height,pad=0)
    doc = i.document(width=80,height=40,margin=0)
    doc.add('box',i.component(factory,responsive=True))
    doc.compile()
    doc.configure(width=100,height=50)
    doc.compile()
    assert calls == [(80,40),(100,50)]


def test_simple_track_projection_preserves_weights_until_minima_bind():
    constraints = [(0,1,30,'a'),(1,1,0,'b'),(2,1,0,'c')]
    assert _tracks(3,(1,2,3),constraints,60,0,'width') == pytest.approx([30,10,20])
    assert _tracks(3,(1,2,3),constraints,180,0,'width') == pytest.approx([30,60,90])
    assert _tracks(3,(1,2,3),constraints,None,0,'width') == pytest.approx([30,0,0])


def test_thousand_tracks_respect_every_minimum_and_total():
    count = 1000
    floors = [1+(j%9) for j in range(count)]
    available = sum(floors)+1000+2*(count-1)
    tracks = _tracks(count,tuple(1+(j%3) for j in range(count)),
                     [(j,1,floor,str(j)) for j,floor in enumerate(floors)],available,2,'width')
    assert sum(tracks)+2*(count-1) == pytest.approx(available)
    assert all(a >= b-1e-8 for a,b in zip(tracks,floors))


@pytest.mark.parametrize('align,x,y',[('nw',0,0),('n',.5,0),('ne',1,0),('w',0,.5),
                                     ('center',.5,.5),('e',1,.5),('sw',0,1),('s',.5,1),('se',1,1)])
def test_fixed_cell_compass_alignment_preserves_artwork(align,x,y):
    doc = i.document(width=80,height=50,margin=0)
    doc.add('shape',i.Diagram(prim=RectPrim(20,10)),align=align)
    result = doc.compile()
    box = result.build()[1]['cell-shape'].bbox
    assert (box.x0,box.y0,box.width,box.height) == pytest.approx((60*x,40*y,20,10))
    assert result.metadata['cells']['shape']['align'] == align


def test_invalid_cell_alignment_is_rejected():
    with pytest.raises(ValueError,match='cell align'):
        i.document().add('shape',i.box('Shape'),align='diagonal')
