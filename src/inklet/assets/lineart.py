"""Line art: turning a photograph into strokes.

This is the feature that stops an asset from looking pasted in. A figure made
of flat boxes and hairlines has one visual grammar -- solid colour, uniform
line weight, no texture -- and dropping a photograph into it breaks that
grammar no matter how good the cutout is. Reducing the photograph to lines puts
it back in the same drawing.

The filter is XDoG (Winnemoller, Kyprianidis & Olsen, "XDoG: An eXtended
difference-of-Gaussians compendium including advanced image stylization",
Computers & Graphics 36(6), 2012). A difference of two Gaussians finds edges;
subtracting a fraction `tau` of the wider blur rather than all of it leaves a
small positive bias proportional to the local tone, and thresholding below zero
then inks the dark side of every edge and nothing else. That bias is what keeps
a dark but *flat* region -- a shadow, a black patch of fur -- from filling in
solid, which is the difference between a line drawing and a posterisation.

`sigma` is in millimetres at final size, not in pixels. That is the whole point
of the mm-native contract: the same parameter gives the same line weight from a
600 px icon and a 6000 px photograph, because a stroke is a physical thing.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from typing import Any

from ..core.geom import Affine, Vec2
from ..core.prims import Subpath
from ..themes.color import parse_color
from .cutout import SOLID
from .deps import AssetError, have_binary, numpy
from .raster import blur, luminance

__all__ = [
    "LineArt", "as_lineart", "xdog", "render_lineart", "potrace_available",
    "potrace_svg", "vector_paths", "parse_potrace_svg",
]

# Below this the two blurs are the same picture and XDoG returns noise.
_MIN_SIGMA_PX = 0.5


@dataclass(frozen=True)
class LineArt:
    """XDoG parameters, plus how the result is painted.

    `sigma` is the narrow blur, in mm at final size; `k` the ratio to the wide
    one. `tau` under 1 leaves a bias of `(1 - tau)` times the local tone in the
    response: raise it towards 1 for heavier, more sensitive lines, lower it to
    keep only the strongest edges. `epsilon` shifts where the soft threshold
    cuts and `phi` decides how abruptly.
    """

    sigma: float = 0.06
    k: float = 1.6
    tau: float = 0.98
    epsilon: float = 0.0
    phi: float = 200.0
    threshold: float = 0.5
    ink: str | None = None       # None -> the active theme's ink
    fill: str | None = None      # paint under the strokes; None -> transparent
    vector: bool | None = None   # None -> vector when potrace is on PATH

    def key(self) -> dict[str, Any]:
        return {
            "sigma": self.sigma, "k": self.k, "tau": self.tau,
            "epsilon": self.epsilon, "phi": self.phi,
            "threshold": self.threshold, "ink": self.ink, "fill": self.fill,
        }


def as_lineart(spec: LineArt | str | bool | None, **overrides: Any) -> LineArt | None:
    """Coerce the `lineart=` argument. None/False mean "keep the photograph"."""
    if spec is None or spec is False:
        return None
    if spec is True or spec == "auto":
        base = LineArt()
    elif spec == "raster":
        base = LineArt(vector=False)
    elif spec == "vector":
        base = LineArt(vector=True)
    elif isinstance(spec, LineArt):
        base = spec
    else:
        raise AssetError(
            f"lineart must be one of True, 'auto', 'raster', 'vector' or a "
            f"LineArt, not {spec!r}"
        )
    given = {k: v for k, v in overrides.items() if v is not None}
    return replace(base, **given) if given else base


# -- the filter -----------------------------------------------------------


def xdog(gray: Any, spec: LineArt, sigma_px: float) -> Any:
    """Extended difference-of-Gaussians. Returns a boolean ink mask."""
    np = numpy()
    sigma = max(sigma_px, _MIN_SIGMA_PX)
    narrow = blur(gray, sigma)
    wide = blur(gray, sigma * spec.k)
    # Deliberately not renormalised by (1 - tau). That division is the right
    # move for XDoG's tone-shading mode, where flat regions are meant to come
    # back as their own lightness; here it would turn every mid-grey area into
    # solid ink instead of leaving it blank.
    response = narrow - min(spec.tau, 0.999) * wide
    shaped = np.where(
        response >= spec.epsilon,
        1.0,
        1.0 + np.tanh(spec.phi * (response - spec.epsilon)),
    )
    return np.clip(shaped, 0.0, 1.0) < spec.threshold


def render_lineart(rgba: Any, alpha: Any, spec: LineArt, *, ink: str,
                   sigma_px: float) -> tuple[Any, Any]:
    """Paint the subject as strokes. Returns (rgba, ink mask).

    The picture is flattened onto white before filtering. Texture in a keyed-out
    background would otherwise produce lines outside the subject, while the
    silhouette edge itself still gives the strong gradient that draws the
    subject's contour -- which is the line you most want.
    """
    np = numpy()
    coverage = (alpha.astype(np.float64) / 255.0)[:, :, None]
    flat = rgba[:, :, :3].astype(np.float64) * coverage + 255.0 * (1.0 - coverage)
    strokes = xdog(luminance(flat), spec, sigma_px)

    ink_rgb = np.array(parse_color(ink), dtype=np.float64)
    out = np.zeros(rgba.shape, dtype=np.float64)
    if spec.fill is not None:
        fill_rgb = np.array(parse_color(spec.fill), dtype=np.float64)
        inside = alpha >= SOLID
        out[inside, :3] = fill_rgb
        out[inside, 3] = alpha[inside]
    out[strokes, :3] = ink_rgb
    out[strokes, 3] = 255.0
    return out.round().astype(np.uint8), strokes


# -- vectorisation --------------------------------------------------------


def potrace_available() -> bool:
    return have_binary("potrace")


def potrace_svg(strokes: Any) -> str:
    """Run potrace over an ink mask and hand back its SVG, unparsed.

    Raster line art at 300 dpi prints perfectly well; vector line art is for
    when the figure will be scaled after the fact, or when a designer wants to
    recolour the strokes in Illustrator without touching a pixel editor.

    The SVG text is what gets cached, rather than the parsed paths: it is small,
    it is exactly what potrace produced, and re-parsing it is free.
    """
    if not potrace_available():
        raise AssetError(
            "potrace is not on PATH; install it (apt install potrace, "
            "brew install potrace) or use lineart='raster'"
        )
    result = subprocess.run(
        ["potrace", "-b", "svg", "-t", "2", "-o", "-", "-"],
        input=_pbm(strokes), capture_output=True, check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise AssetError(f"potrace failed: {detail or result.returncode}")
    return result.stdout.decode("utf-8")


def vector_paths(strokes: Any, width: float, height: float) -> tuple[Subpath, ...]:
    """Trace an ink mask into local-mm subpaths with potrace."""
    rows, cols = strokes.shape
    return parse_potrace_svg(potrace_svg(strokes), cols, rows, width, height)


def _pbm(mask: Any) -> bytes:
    """Binary PBM (P4). Written by hand rather than through Pillow so the byte
    layout -- and therefore what potrace sees -- is not a Pillow version away
    from changing."""
    np = numpy()
    rows, cols = mask.shape
    packed = np.packbits(mask.astype(np.uint8), axis=1)
    return f"P4\n{cols} {rows}\n".encode("ascii") + packed.tobytes()


_TRANSFORM = re.compile(
    r"translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)\s*"
    r"scale\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)"
)
_VIEWBOX = re.compile(r'viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"')
_PATH_D = re.compile(r'<path[^>]*\bd="([^"]*)"')
_TOKEN = re.compile(r"[MmLlCcZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def parse_potrace_svg(svg: str, pixel_width: int, pixel_height: int,
                      width: float, height: float) -> tuple[Subpath, ...]:
    """Read potrace's SVG back into local-mm subpaths.

    potrace works in a y-up frame and emits a `translate(...) scale(...)` on the
    group that flips it. Reading that transform out of the file rather than
    reproducing it from the manual is the difference between code that survives
    a potrace release and code that silently draws everything upside down.
    """
    flip = _TRANSFORM.search(svg)
    if flip is None:
        raise AssetError("potrace output has no group transform; cannot place its paths")
    tx, ty, sx, sy = (float(v) for v in flip.groups())
    to_user = Affine(a=sx, d=sy, e=tx, f=ty)

    box = _VIEWBOX.search(svg)
    # The viewBox is in points at whatever resolution potrace chose, so rescale
    # it onto the bitmap grid instead of assuming one point per pixel.
    span_x = float(box.group(3)) if box else float(pixel_width)
    span_y = float(box.group(4)) if box else float(pixel_height)
    to_mm = Affine(
        a=width / span_x, d=height / span_y, e=-width / 2, f=-height / 2,
    )
    place = to_mm @ to_user

    subpaths = []
    for data in _PATH_D.findall(svg):
        subpaths.extend(_subpaths(data, place))
    return tuple(subpaths)


def _subpaths(data: str, place: Affine) -> list[Subpath]:
    """Flatten one `d` attribute into closed subpaths.

    Every segment becomes a cubic, straight runs included, because
    `Subpath.curves` must cover the subpath tip to tip: a renderer draws from
    `curves` alone when it is present, so a list holding only the real curves
    would drop the lines between them.
    """
    tokens = _TOKEN.findall(data)
    linear = Affine(a=place.a, b=place.b, c=place.c, d=place.d)
    result: list[Subpath] = []
    points: list[Vec2] = []
    curves: list[tuple[Vec2, Vec2, Vec2, Vec2]] = []
    cursor = Vec2(0.0, 0.0)
    command = ""
    index = 0

    def point(relative: bool) -> Vec2:
        nonlocal index
        x, y = float(tokens[index]), float(tokens[index + 1])
        index += 2
        return cursor + linear.apply_vector(Vec2(x, y)) if relative \
            else place.apply(Vec2(x, y))

    def flush() -> None:
        if len(points) >= 2:
            result.append(Subpath(tuple(points), True, tuple(curves)))
        points.clear()
        curves.clear()

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in "Zz":
                if points and (points[0] - cursor).length > 1e-9:
                    curves.append(_line(cursor, points[0]))
                cursor = points[0] if points else cursor
                flush()
                continue
        if not command:
            raise AssetError("potrace path data does not start with a command")
        relative = command.islower()
        if command in "Mm":
            target = point(relative)
            flush()
            cursor = target
            points.append(cursor)
        elif command in "Ll":
            target = point(relative)
            curves.append(_line(cursor, target))
            cursor = target
            points.append(cursor)
        elif command in "Cc":
            c1, c2, end = point(relative), point(relative), point(relative)
            curves.append((cursor, c1, c2, end))
            points.extend(_flatten(cursor, c1, c2, end))
            cursor = end
        else:
            raise AssetError(f"unsupported path command {command!r} in potrace output")
    flush()
    return result


def _line(a: Vec2, b: Vec2) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    """A straight segment as a degenerate cubic, with the controls on the line."""
    return (a, a + (b - a) * (1 / 3), a + (b - a) * (2 / 3), b)


def _flatten(p0: Vec2, c1: Vec2, c2: Vec2, p3: Vec2,
             steps: int = 8) -> list[Vec2]:
    """Fixed subdivision. Geometry -- envelopes and traces -- reads `points`, and
    a fixed step count keeps that geometry identical run to run."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append(
            p0 * (u * u * u) + c1 * (3 * u * u * t) + c2 * (3 * u * t * t) + p3 * (t ** 3)
        )
    return out
