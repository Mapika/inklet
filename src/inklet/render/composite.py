"""Explicit group blending and raster masks with recorded export provenance."""
import hashlib
from io import BytesIO

from ..core import Diagram, ImagePrim, Affine

BLEND_MODES = {'normal':'Normal', 'multiply':'Multiply', 'screen':'Screen',
               'overlay':'Overlay', 'darken':'Darken', 'lighten':'Lighten',
               'difference':'Difference', 'exclusion':'Exclusion'}


def blend(node, mode='multiply'):
    """Blend an isolated group with the artwork behind it, natively in SVG/PDF."""
    if mode not in BLEND_MODES: raise ValueError(f'Unknown blend mode {mode!r}; choose {", ".join(BLEND_MODES)}')
    return Diagram(children=(node,),kind='blend',notes={'blend_mode':mode})


def mask(content, stencil, *, mode='luminance', dpi=300):
    """Apply a same-coordinate stencil as a recorded raster layer.

    Luminance uses black to hide and white to reveal; alpha uses stencil alpha.
    Requires inklet[render]. SVG and PDF embed identical masked pixels. Keep
    editable annotations outside the masked layer.
    """
    from .raster import to_png
    from PIL import Image, ImageChops
    if mode not in ('alpha','luminance'): raise ValueError('mask mode must be alpha or luminance')
    box=content.bbox
    # An explicit envelope gives both renders the same viewport, even when the
    # stencil is smaller or translated away from the content.
    from ..core import Envelope
    def render(node):
        frame=Diagram(children=(node,),envelope_override=Envelope.from_rect(box))
        return Image.open(BytesIO(to_png(frame,dpi=dpi))).convert('RGBA')
    picture,alpha=render(content),render(stencil)
    coverage=alpha.getchannel('A')
    if mode=='luminance': coverage=ImageChops.multiply(coverage,alpha.convert('L'))
    picture.putalpha(ImageChops.multiply(picture.getchannel('A'),coverage))
    output=BytesIO();picture.save(output,format='PNG');data=output.getvalue()
    digest=hashlib.sha256(data).hexdigest()
    node=Diagram(prim=ImagePrim('masked-layer:'+digest,box.width,box.height,picture.size,data=data),
                 transform=Affine.translation(box.center.x,box.center.y),kind='raster-layer',
                 notes={'raster_layer':dict(dpi=dpi,reason=f'{mode} mask',sha256=digest,pixels=list(picture.size))})
    for name,point in content.anchors.items():node.anchor(name,content.transform.apply(point)-box.center)
    return node
