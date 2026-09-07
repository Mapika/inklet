"""Direct raster markers preserve the established tree renderer's semantics."""
import io
import pytest
import inklet as i
from inklet.core import ImagePrim
from inklet.draw.shapes import MARKER_KINDS
from inklet.plot import marks
from inklet.plot.scatter_raster import raster_scatter


@pytest.mark.parametrize('marker',MARKER_KINDS)
@pytest.mark.parametrize('clip',[True,False])
def test_direct_scatter_preserves_sizes_order_clipping_and_alpha(marker,clip):
    Image = pytest.importorskip('PIL.Image')
    ImageChops = pytest.importorskip('PIL.ImageChops')
    p = i.panel(24,18,x=(0,1),y=(0,1),clip=clip)
    points = [(-.02,.4),(.5,.5),(.5,.5),(.72,.81),(1.02,.95)]
    options = dict(marker=marker,size=[2,3,2.5,1,2],
                   color=['red','blue','green','orange','purple'],
                   opacity=.6,fill_opacity=.4,stroke='black',stroke_width=.2)
    expected = raster_scatter(marks.scatter(p,points,**options),dpi=254,clip=p.area if clip else None)
    p.scatter(points,**options,raster=True,dpi=254)
    actual = next(n.prim for n in p.build().walk() if isinstance(n.prim,ImagePrim))
    assert (actual.width,actual.height) == pytest.approx((expected.prim.width,expected.prim.height))
    a, b = Image.open(io.BytesIO(actual.data)),Image.open(io.BytesIO(expected.prim.data))
    assert a.size == b.size
    # Equivalent coordinate expressions can straddle a pixel boundary by an
    # ulp; only a small antialiasing fringe may differ.
    diff = ImageChops.difference(a,b)
    assert sum(sum(c.histogram()[16:]) for c in diff.split())/(a.width*a.height*4) < .001


def test_raster_scatter_does_not_construct_one_marker_per_point(monkeypatch):
    pytest.importorskip('PIL.Image')
    import inklet.draw.shapes as shapes
    original = shapes.marker
    calls = []
    def marker(*args,**kwargs):
        calls.append(args)
        return original(*args,**kwargs)
    monkeypatch.setattr(shapes,'marker',marker)
    p = i.panel(20,20,x=(0,1),y=(0,1))
    p.scatter(((j/1000,.5) for j in range(1000)),raster=True,size=1,color='red')
    assert len(calls) == 1


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-1,0])
def test_nonfinite_or_nonpositive_marker_size_is_rejected(bad):
    with pytest.raises(ValueError,match='positive size'):
        i.marker('circle',bad)


def test_explicit_placement_options_keep_raster_fallback_when_unclipped():
    pytest.importorskip('PIL.Image')
    p = i.panel(20,20,x=(0,1),y=(0,1))
    p.scatter([(.5,.5)],raster=True,clip=False,anchor='nw')
    assert any(isinstance(n.prim,ImagePrim) for n in p.build().walk())
