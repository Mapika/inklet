"""Reading Blender's Grease Pencil SVG back into millimetres.

The exporter writes one `<polyline>` per stroke and never a `<path>`, so there
are no curves to flatten and no `d` grammar to parse: the whole file is a list
of point lists in one flat group per Grease Pencil layer. What it also writes,
before the root element, is two malformed processing instructions --
`<?:anonymous?>` and `<?xml?>` -- neither of which is legal XML and both of
which stop a strict parser dead. Everything before `<svg` is dropped rather
than repaired, which is safe because `<svg` is the root element and nothing
above it carries meaning.

The mapping into millimetres is the other half. With the viewport forced into
camera view (see `script.py`) the viewBox *is* the camera frame, so two things
are expressible and both are wanted: `fit="frame"` puts the camera frame into
the requested box, which keeps several views of the same subject at one scale,
and `fit="content"` puts the ink's own bounding box there, which is what an
author means by "make this bunny 40 mm wide". Aspect ratio is never stretched.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from typing import Any, Sequence

from ...core.geom import Rect, Vec2
from .discover import BlenderError
from .options import FITS

__all__ = [
    "Layer", "GreasePencilSvg", "read_gpencil_svg", "place_layers",
    "strip_preamble", "SVG_NS",
]

SVG_NS = "http://www.w3.org/2000/svg"

_METADATA = re.compile(r"<!--\s*inklet-lineart\s*(\{.*?\})\s*-->", re.DOTALL)
_NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class Layer:
    """One Grease Pencil layer's worth of strokes, in the source's own units."""

    name: str
    polylines: tuple[tuple[Vec2, ...], ...]
    stroke_width: float          # source units, from the first stroke that says

    @property
    def points(self) -> int:
        return sum(len(p) for p in self.polylines)


@dataclass(frozen=True)
class GreasePencilSvg:
    """A parsed export: the camera frame, the layers, and the bake report."""

    viewbox: tuple[float, float, float, float]
    layers: tuple[Layer, ...]
    metadata: dict[str, Any]

    def layer(self, name: str) -> Layer | None:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    @property
    def frame(self) -> Rect:
        x, y, width, height = self.viewbox
        return Rect(x, y, x + width, y + height)

    def content_box(self) -> Rect | None:
        """Tight bounds of every stroke in every layer, or None when empty."""
        points = [p for layer in self.layers for line in layer.polylines for p in line]
        if not points:
            return None
        return Rect(
            min(p.x for p in points), min(p.y for p in points),
            max(p.x for p in points), max(p.y for p in points),
        )


def strip_preamble(text: str) -> str:
    """Everything from `<svg` onwards.

    Blender's two malformed processing instructions live above the root, as
    does its generator comment. None of it is XML a parser will accept and none
    of it is information, so the cheapest correct fix is to start reading at
    the root element.
    """
    index = text.find("<svg")
    if index < 0:
        raise BlenderError(
            "this does not look like an SVG export: no <svg element found"
        )
    return text[index:]


def read_gpencil_svg(text: str) -> GreasePencilSvg:
    """Parse an export. Coordinates come back exactly as written."""
    metadata: dict[str, Any] = {}
    match = _METADATA.search(text)
    if match:
        try:
            metadata = json.loads(match.group(1))
        except ValueError:
            metadata = {}
        # Removed before parsing rather than trusted to be a legal comment: the
        # report quotes object names, and a name with a double hyphen in it
        # would be a comment no XML parser is allowed to accept.
        text = text[: match.start()] + text[match.end():]

    try:
        root = ElementTree.fromstring(strip_preamble(text))
    except ElementTree.ParseError as exc:
        raise BlenderError(f"cannot parse the Grease Pencil SVG export: {exc}") from exc

    viewbox = _viewbox(root)
    layers = []
    for index, group in enumerate(root.iter(f"{{{SVG_NS}}}g")):
        polylines = []
        widths = []
        for child in group:
            if child.tag != f"{{{SVG_NS}}}polyline":
                continue
            points = _points(child.get("points", ""))
            if len(points) >= 2:
                polylines.append(points)
                widths.append(_float(child.get("stroke-width"), 1.0))
        if polylines:
            layers.append(Layer(
                name=group.get("id") or f"layer{index}",
                polylines=tuple(polylines),
                # One thickness per Line Art modifier, so the first stroke
                # speaks for the layer; taking the max rather than the first
                # keeps a hand-edited file from reporting a hairline.
                stroke_width=max(widths),
            ))
    return GreasePencilSvg(viewbox, tuple(layers), metadata)


def place_layers(document: GreasePencilSvg, *, width: float,
                 height: float | None = None,
                 fit: str = "content") -> tuple[tuple[Layer, ...], float, float, float]:
    """Rescale into origin-centred millimetres.

    Returns the placed layers, the width and height in mm of the box they were
    fitted into, and the millimetres-per-source-unit factor a caller needs to
    turn the exporter's stroke width into a line weight.

    y is *not* flipped: SVG and inklet both grow y downward, so a stroke that
    Blender put at the top of the frame stays at the top.
    """
    if fit not in FITS:
        raise BlenderError(f"fit must be one of {', '.join(FITS)}, not {fit!r}")
    if width <= 0 or (height is not None and height <= 0):
        raise BlenderError("width and height must be positive millimetre sizes")

    source = document.frame if fit == "frame" else document.content_box()
    if source is None or source.width <= 0 or source.height <= 0:
        raise BlenderError(
            "the export contains no strokes with any extent, so there is "
            "nothing to scale into millimetres"
        )

    scale = width / source.width
    if height is not None:
        # Both sizes given means "inside this box", never "stretched to it".
        scale = min(scale, height / source.height)
    centre = source.center
    placed = tuple(
        Layer(
            name=layer.name,
            polylines=tuple(
                tuple(Vec2((p.x - centre.x) * scale, (p.y - centre.y) * scale)
                      for p in line)
                for line in layer.polylines
            ),
            stroke_width=layer.stroke_width * scale,
        )
        for layer in document.layers
    )
    return placed, source.width * scale, source.height * scale, scale


def _viewbox(root: ElementTree.Element) -> tuple[float, float, float, float]:
    raw = root.get("viewBox")
    if raw:
        numbers = [float(n) for n in _NUMBER.findall(raw)]
        if len(numbers) == 4 and numbers[2] > 0 and numbers[3] > 0:
            return (numbers[0], numbers[1], numbers[2], numbers[3])
    width = _float(root.get("width"), 0.0)
    height = _float(root.get("height"), 0.0)
    if width > 0 and height > 0:
        return (0.0, 0.0, width, height)
    raise BlenderError("the SVG export has no usable viewBox")


def _points(raw: str) -> tuple[Vec2, ...]:
    """`points="x,y x,y ..."`. Read by pulling numbers in pairs rather than by
    splitting on the separators, because SVG allows commas, spaces or both and
    Blender's choice is not something to depend on."""
    numbers = [float(n) for n in _NUMBER.findall(raw)]
    return tuple(Vec2(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2))


def _float(raw: str | None, fallback: float) -> float:
    if raw is None:
        return fallback
    match = _NUMBER.search(raw)
    return float(match.group()) if match else fallback
