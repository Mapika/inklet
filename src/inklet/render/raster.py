"""Browser-free PNG output and explicit raster layers, using optional resvg."""
from functools import lru_cache
import hashlib
import math
import re
from pathlib import Path
import struct

from ..core import Diagram, DiagramError, ImagePrim, Affine


def _renderer():
    try:
        import resvg_py
    except ImportError:
        raise DiagramError('PNG rendering requires resvg-py; install inklet[render]') from None
    return resvg_py


@lru_cache(maxsize=8)
def _small_render(svg, width, height):
    return _renderer().svg_to_bytes(svg_string=_pixel_svg(svg,width,height),
                                    skip_system_fonts=True, dpi=96)


def _pixel_svg(svg,width,height):
    # Give resvg an integer pixel viewport. Its optional fit-to-size operation
    # can truncate a mathematically integral result by one pixel after scaling
    # an SVG whose width is in mm. The viewBox retains physical coordinates.
    match=re.search(r'<svg\b[^>]*>',svg)
    header=match.group()
    header=re.sub(r'\bwidth="[^"]+"',f'width="{width}"',header,count=1)
    header=re.sub(r'\bheight="[^"]+"',f'height="{height}"',header,count=1)
    return svg[:match.start()]+header+svg[match.end():]


def png_bytes(svg, width, height):
    """Rasterize outlined SVG; retain at most eight small layers in memory."""
    if width <= 0 or height <= 0 or width*height > 40_000_000:
        raise ValueError('PNG dimensions must be positive and at most 40 million pixels')
    if width*height <= 1_000_000 and len(svg) <= 1_000_000:
        return _small_render(svg, width, height)
    return _renderer().svg_to_bytes(svg_string=_pixel_svg(svg,width,height),
                                    skip_system_fonts=True, dpi=96)


def to_png(root, *, dpi=150, **options):
    """Return PNG bytes at physical DPI, without Chrome or a display server.

    Requires inklet[render]. Text uses the already shaped glyph outlines, so
    rasterization cannot substitute fonts. A missing background is transparent.
    Other options follow to_svg; text modes do not affect PNG appearance.
    """
    from .svg import to_svg, _canvas
    if not math.isfinite(dpi) or dpi <= 0: raise ValueError('dpi must be finite and positive')
    _, width, height = _canvas(root, options.get('width'), options.get('height'), options.get('margin', 0))
    pixels = (max(1, round(width*dpi/25.4)), max(1, round(height*dpi/25.4)))
    options['text'] = 'outline'
    data = png_bytes(to_svg(root, **options), *pixels)
    # PNG pHYs records intended print size, independently of viewer defaults.
    import zlib
    payload = struct.pack('>IIB', round(dpi/0.0254), round(dpi/0.0254), 1)
    kind = b'pHYs'
    chunk = struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    return data[:33]+chunk+data[33:]


def save_png(root, path, **options):
    """Save a Diagram as PNG; see to_png for physical DPI and backgrounds."""
    target = Path(path)
    data = to_png(root, **options)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def rasterize(node, *, dpi=300, reason='explicit raster layer'):
    """Freeze one expensive layer as pixels, preserving its size and anchors.

    Place labels outside this layer to retain vector text in SVG/PDF. The
    resulting node records its DPI, reason and source hash in export manifests.
    """
    box = node.bbox
    data = to_png(node, dpi=dpi)
    pixels = struct.unpack('>II', data[16:24])
    digest = hashlib.sha256(data).hexdigest()
    image = Diagram(prim=ImagePrim('raster-layer:'+digest, box.width, box.height,
                                   pixels, data=data),
                    transform=Affine.translation(box.center.x, box.center.y), kind='raster-layer',
                    notes={'raster_layer': dict(dpi=dpi, reason=str(reason), sha256=digest,
                                                pixels=list(pixels))})
    # ImagePrim uses a centred local coordinate frame.
    for name, point in node.anchors.items():
        image.anchor(name, node.transform.apply(point)-box.center)
    return image
