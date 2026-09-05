"""Raster marker coverage agrees with the independently rendered vector PDF."""
import io
import shutil
import subprocess

import pytest
import inklet
from inklet.core import ImagePrim

MARKERS = ('circle', 'square', 'diamond', 'triangle', 'star', 'cross', 'plus')


def panel(marker, raster, dpi=254, **style):
    p = inklet.panel(12.7, 12.7, x=(0, 1), y=(0, 1), clip=True)
    p.under(inklet.box(width=12.7, height=12.7, pad=0, radius=0, fill='white', stroke='none'))
    p.scatter([(.5, .5)], size=4, marker=marker, color='red', stroke='blue',
              stroke_width=1, raster=raster, dpi=dpi, **style)
    return p


def test_circle_outline_straddles_boundary_and_keeps_fill():
    Image = pytest.importorskip('PIL.Image')
    p = panel('circle', True)
    prim = next(n.prim for n in p.build().walk() if isinstance(n.prim, ImagePrim))
    im = Image.open(io.BytesIO(prim.data))
    bounds = im.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
    assert bounds[2]-bounds[0] == pytest.approx(50, abs=1)
    assert bounds[3]-bounds[1] == pytest.approx(50, abs=1)
    assert im.getpixel((63, 63)) == (255, 0, 0, 255)
    assert im.getpixel((84, 63))[:3] == (0, 0, 255)
    assert im.getpixel((84, 63))[3] >= 250


@pytest.mark.skipif(shutil.which('pdftoppm') is None, reason='Poppler not installed')
@pytest.mark.parametrize('marker', MARKERS)
@pytest.mark.parametrize('join,cap', [('round','round'), ('bevel','butt'), ('miter','square')])
def test_raster_matches_vector_coverage_and_colours(tmp_path, marker, join, cap):
    Image = pytest.importorskip('PIL.Image')
    p = panel(marker, False, dpi=508, stroke_linejoin=join, stroke_linecap=cap)
    f = inklet.figure(width=12.7, height=12.7, margin=0)
    f.add(p.build())
    f.save(tmp_path/'vector.pdf')
    subprocess.run(['pdftoppm', '-r', '508', '-png', '-singlefile',
                    str(tmp_path/'vector.pdf'), str(tmp_path/'vector')],
                   check=True, capture_output=True)
    expected = Image.open(tmp_path/'vector.png').convert('RGB')
    p = panel(marker, True, dpi=508, stroke_linejoin=join, stroke_linecap=cap)
    prim = next(n.prim for n in p.build().walk() if isinstance(n.prim, ImagePrim))
    rgba = Image.open(io.BytesIO(prim.data))
    actual = Image.new('RGB', rgba.size, 'white')
    actual.paste(rgba, mask=rgba.getchannel('A'))
    assert actual.size == expected.size
    # Ignore antialiasing fringe while requiring the same filled/stroked shape.
    a = list(zip(*[iter(actual.tobytes())]*3)); b = list(zip(*[iter(expected.tobytes())]*3))
    for channel in ('ink', 'red', 'blue'):
        def member(c):
            if channel == 'ink': return min(c) < 128
            if channel == 'red': return c[0] > 180 and c[2] < 80
            return c[2] > 180 and c[0] < 80
        aa, bb = [member(c) for c in a], [member(c) for c in b]
        union = sum(x or y for x,y in zip(aa,bb))
        if union:
            assert sum(x and y for x,y in zip(aa,bb))/union > .9, channel
