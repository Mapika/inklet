"""`inklet.asset()` -- a picture that composes like every other diagram.

The pipeline, in the order it runs:

1. **Cut out.** Alpha channel, chroma key, or a learned matte. Produces one
   alpha plane.
2. **Find the subject.** Fill interior holes, keep the largest connected blob,
   and take its tight bounding box. This step is the one that matters most: a
   mouse photographed with a 30% white margin must occupy the space of the
   *mouse*, not of the JPEG. Every later step, and every number the layout ever
   sees, is in terms of that box.
3. **Harmonise.** Optionally rotate hues onto the theme palette.
4. **Redraw.** Optionally reduce the photograph to XDoG line art, vectorised
   with potrace when it is available.
5. **Trace.** Simplify the mask boundary into `ImagePrim.outline`, which drives
   both the envelope and the trace, so the asset packs and catches arrows on
   its silhouette.

Everything derived is written to a content-addressed cache, so a second build
of the same figure decodes nothing and the SVG comes out byte-identical.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..core.diagram import Diagram
from ..core.geom import Vec2
from ..core.prims import ImagePrim, PathPrim
from ..core.units import mm
from .cache import cache_path, cache_root, cached_file, content_hash, derive_key
from .cutout import SOLID, Cutout, as_cutout, run_cutout
from .deps import AssetError, numpy
from .harmonise import Harmonise, as_harmonise, harmonise, palette_colors
from .lineart import (
    LineArt, as_lineart, parse_potrace_svg, potrace_available, potrace_svg,
    render_lineart,
)
from .mask import fill_holes, largest_component, tight_bounds
from .provenance import Provenance, record
from .raster import load_rgba, save_png
from .sidecar import Sidecar, coerce_anchors, load_sidecar
from .silhouette import (
    DEFAULT_MAX_POINTS, DEFAULT_RESOLUTION, DEFAULT_TOLERANCE, outline_from_mask,
)

__all__ = ["asset", "DEFAULT_WIDTH", "ASSET_KIND", "SILHOUETTE_KIND"]

# A figure is 89 mm wide. An inline illustration that has to sit beside a label
# and still read is about a fifth of that; anything else the author states.
DEFAULT_WIDTH = 20.0

ASSET_KIND = "asset"
SILHOUETTE_KIND = "silhouette"


def asset(path: str | Path, *,
          width: float | str | None = None,
          height: float | str | None = None,
          cutout: Cutout | str | bool | None = "auto",
          cutout_tolerance: float | None = None,
          lineart: LineArt | str | bool | None = False,
          palette: Harmonise | Sequence[str] | float | bool | None = None,
          palette_strength: float | None = None,
          anchors: Mapping[str, Sequence[float]] | None = None,
          outline: bool = True,
          outline_tolerance: float = DEFAULT_TOLERANCE,
          outline_max_points: int = DEFAULT_MAX_POINTS,
          outline_resolution: int = DEFAULT_RESOLUTION,
          license: str | None = None,
          attribution: str | None = None,
          source_url: str | None = None,
          sidecar: bool = True,
          cache_dir: str | Path | None = None,
          name: str | None = None) -> Diagram:
    """Place an image as a diagram that knows its own silhouette.

    `width` and `height` are millimetres or unit strings. Give one and the
    other follows the *subject's* aspect ratio; give neither and the width
    defaults to `DEFAULT_WIDTH`.

    Anchors come from `<name>.inklet.json` beside the image and from `anchors=`,
    both as (u, v) fractions of the subject's bounding box with (0, 0) at its
    top-left. `anchors=` wins where the two name the same point.

    `license`, `attribution` and `source_url` override the sidecar's. Nothing
    is inferred: an asset with none of them recorded says so in its credit line.
    """
    file = Path(path)
    source_hash = content_hash(file)
    card = load_sidecar(file) if sidecar else Sidecar()

    cut_spec = as_cutout(cutout, tolerance=cutout_tolerance)
    tone_spec = as_harmonise(palette, palette_strength)
    tone_colors = tuple(palette_colors(tone_spec)) if tone_spec else ()
    line_spec = as_lineart(lineart)

    root = cache_root(cache_dir)
    subject = _subject(file, source_hash, root, cut_spec, tone_spec, tone_colors)

    box_w, box_h = subject["subject_pixels"]
    size = _resolve_size(width, height, box_w, box_h)
    placed = _placed(subject, file.stem, root, size, line_spec, outline,
                     outline_tolerance, outline_max_points, outline_resolution)

    node = _build_node(placed, size, name or file.stem)
    _attach_anchors(node, card.anchors, coerce_anchors(anchors, "anchors="), size)
    record(node, _provenance(file, source_hash, card, subject, placed,
                             license, attribution, source_url))
    return node


@dataclass(frozen=True)
class _Size:
    width: float
    height: float


# -- stage 1: cut out and crop to the subject -----------------------------


def _subject(file: Path, source_hash: str, root: Path, cut: Cutout,
             tone: Harmonise | None, tone_colors: tuple[str, ...]) -> dict[str, Any]:
    """The cropped, keyed, harmonised subject. Independent of the placed size,
    so changing a figure's dimensions does not re-run the expensive half."""
    key = derive_key(source_hash, "subject", cut.key(),
                     tone.key() if tone else None, list(tone_colors))
    facts = cache_path(root, file.stem, key, ".json")
    png = cache_path(root, file.stem, key, ".png")

    if not (facts.exists() and png.exists()):
        data = _make_subject(file, cut, tone, tone_colors)
        image = data.pop("_rgba")
        cached_file(root, file.stem, key, ".png", lambda temp: save_png(image, temp))
        cached_file(root, file.stem, key, ".json",
                    lambda temp: _write_json(temp, data))
    subject = json.loads(facts.read_text(encoding="utf-8"))
    subject["png"] = str(png)
    subject["key"] = key
    return subject


def _make_subject(file: Path, cut: Cutout, tone: Harmonise | None,
                  tone_colors: tuple[str, ...]) -> dict[str, Any]:
    np = numpy()
    rgba = load_rgba(file)
    source_h, source_w = rgba.shape[:2]

    keyed = run_cutout(rgba, cut)
    solid = keyed.alpha >= SOLID
    clean = largest_component(fill_holes(solid))
    if clean is None:
        raise AssetError(
            f"the {keyed.backend!r} cutout of {str(file)!r} left no subject; "
            "raise cutout_tolerance, or pass cutout=None to keep the whole frame"
        )
    bounds = tight_bounds(clean)
    y0, x0, y1, x1 = bounds

    crop = rgba[y0:y1 + 1, x0:x1 + 1].copy()
    # Alpha carries both the key and the speck removal: anything outside the
    # chosen blob is background whatever its colour said.
    crop[:, :, 3] = np.where(clean[y0:y1 + 1, x0:x1 + 1],
                             keyed.alpha[y0:y1 + 1, x0:x1 + 1], 0)
    if tone is not None:
        crop = harmonise(crop, tone, tone_colors)

    return {
        "_rgba": crop,
        "backend": keyed.backend,
        "crop": [int(x0), int(y0), int(x1), int(y1)],
        "source_pixels": [int(source_w), int(source_h)],
        "subject_pixels": [int(x1 - x0 + 1), int(y1 - y0 + 1)],
        "harmonised": None if tone is None else
                      {"strength": tone.strength, "colors": list(tone_colors)},
    }


# -- stage 2: everything that depends on the placed size ------------------


def _placed(subject: dict[str, Any], stem: str, root: Path, size: _Size,
            line: LineArt | None, want_outline: bool, tolerance: float,
            max_points: int, resolution: int) -> dict[str, Any]:
    """Outline and, if asked for, line art. Keyed on the subject plus the size,
    because a stroke width in mm is a different number of pixels at every size."""
    key = derive_key(
        subject["key"], "placed", round(size.width, 6), round(size.height, 6),
        {"outline": want_outline, "tolerance": tolerance,
         "max_points": max_points, "resolution": resolution},
        line.key() if line else None,
        _ink(line) if line else None,
        None if line is None else _wants_vector(line),
    )
    facts = cache_path(root, stem, key, ".json")
    art = cache_path(root, stem, key, ".png")

    if not facts.exists() or (line is not None and not art.exists()):
        data = _make_placed(subject, size, line, want_outline, tolerance,
                            max_points, resolution)
        image = data.pop("_rgba", None)
        if image is not None:
            cached_file(root, stem, key, ".png", lambda temp: save_png(image, temp))
        cached_file(root, stem, key, ".json", lambda temp: _write_json(temp, data))

    placed = json.loads(facts.read_text(encoding="utf-8"))
    placed["png"] = str(art) if line is not None else subject["png"]
    placed["harmonised"] = subject["harmonised"]
    placed["backend"] = subject["backend"]
    return placed


def _make_placed(subject: dict[str, Any], size: _Size, line: LineArt | None,
                 want_outline: bool, tolerance: float, max_points: int,
                 resolution: int) -> dict[str, Any]:
    rgba = load_rgba(subject["png"])
    mask = rgba[:, :, 3] >= SOLID
    rows, cols = mask.shape

    silhouette = None
    if want_outline:
        silhouette = outline_from_mask(
            mask, size.width, size.height, tolerance=tolerance,
            max_points=max_points, resolution=resolution,
        )

    data: dict[str, Any] = {
        "pixels": [int(cols), int(rows)],
        "outline": ([[p.x, p.y] for p in silhouette.points]
                    if silhouette is not None else None),
        "silhouette": silhouette.summary() if silhouette is not None else None,
        "lineart": None,
        "potrace_svg": None,
    }
    if line is None:
        return data

    # mm per pixel is the bridge between a stroke width the author states in
    # print units and the blur radius the filter needs.
    sigma_px = line.sigma / (size.width / cols) if cols else 1.0
    art, strokes = render_lineart(rgba, rgba[:, :, 3], line, ink=_ink(line),
                                  sigma_px=sigma_px)
    data["_rgba"] = art
    data["lineart"] = {"sigma_px": sigma_px, "ink": _ink(line)}
    if _wants_vector(line):
        data["potrace_svg"] = potrace_svg(strokes)
    return data


def _wants_vector(line: LineArt) -> bool:
    """Unset means "vector if potrace is here". Whichever way it resolves goes
    into the cache key, so a machine that gains potrace re-derives rather than
    serving raster art from a stale entry."""
    return line.vector if line.vector is not None else potrace_available()


def _ink(line: LineArt) -> str:
    if line.ink is not None:
        return line.ink
    from .. import current_theme  # late: inklet imports this package, not the reverse

    return current_theme().ink


# -- assembling the diagram ----------------------------------------------


def _resolve_size(width: float | str | None, height: float | str | None,
                  pixel_w: int, pixel_h: int) -> _Size:
    """Aspect ratio comes from the subject, never from the canvas."""
    if pixel_w <= 0 or pixel_h <= 0:
        raise AssetError("the subject has no area")
    if width is None and height is None:
        width = DEFAULT_WIDTH
    if width is None:
        h = mm(height)
        return _Size(h * pixel_w / pixel_h, h)
    if height is None:
        w = mm(width)
        return _Size(w, w * pixel_h / pixel_w)
    return _Size(mm(width), mm(height))


def _build_node(placed: dict[str, Any], size: _Size, name: str) -> Diagram:
    points = tuple(Vec2(x, y) for x, y in (placed["outline"] or ()))
    svg = placed.get("potrace_svg")
    if svg:
        return _vector_node(svg, placed, points, size, name)
    prim = ImagePrim(
        source=placed["png"], width=size.width, height=size.height,
        pixel_size=tuple(placed["pixels"]), outline=points,
    )
    return Diagram(prim=prim, kind=ASSET_KIND, name=name)


def _vector_node(svg: str, placed: dict[str, Any], points: tuple[Vec2, ...],
                 size: _Size, name: str) -> Diagram:
    """Vector line art, with the silhouette carried by an unpainted path.

    Core has no primitive that contributes a trace without also carrying ink --
    `PhantomPrim` deliberately has an empty trace -- so the silhouette is a real
    `PathPrim` styled to draw nothing. `Trace.exit` takes the furthest crossing,
    so the arrows still land on the silhouette rather than on an interior
    stroke, and the extra `<path fill="none" stroke="none"/>` is inert.
    """
    pixel_w, pixel_h = placed["pixels"]
    strokes = parse_potrace_svg(svg, pixel_w, pixel_h, size.width, size.height)
    art = Diagram(prim=PathPrim(strokes, filled=True), kind="lineart")
    children = [art]
    if points:
        outline = Diagram(prim=PathPrim.polyline(points, closed=True),
                          kind=SILHOUETTE_KIND).styled(fill="none", stroke="none")
        children.append(outline)
    return Diagram(children=tuple(children), kind=ASSET_KIND, name=name)


def _attach_anchors(node: Diagram, from_sidecar: tuple, inline: tuple,
                    size: _Size) -> None:
    """(u, v) fractions of the subject box become local millimetres.

    Converted here rather than handed to `Diagram.anchor` as a tuple: that
    helper measures fractions of the local *bounding box*, which for a
    simplified silhouette can sit a fraction of a pixel inside the subject
    rectangle the author was looking at when they picked the point.
    """
    merged = dict(from_sidecar)
    merged.update(dict(inline))
    for anchor_name in sorted(merged):
        u, v = merged[anchor_name]
        node.anchor(anchor_name,
                    Vec2(u * size.width - size.width / 2,
                         v * size.height - size.height / 2))


def _provenance(file: Path, source_hash: str, card: Sidecar,
                subject: dict[str, Any], placed: dict[str, Any],
                license: str | None, attribution: str | None,
                source_url: str | None) -> Provenance:
    source_w, source_h = subject["source_pixels"]
    crop = subject["crop"]
    steps = [f"cutout:{subject['backend']}"]
    if crop != [0, 0, source_w - 1, source_h - 1]:
        steps.append("crop:{}x{} of {}x{}".format(*subject["subject_pixels"],
                                                  source_w, source_h))
    tone = subject.get("harmonised")
    if tone:
        steps.append(f"harmonise:{len(tone['colors'])} hues @ {tone['strength']:g}")
    art = placed.get("lineart")
    if art:
        kind = "vector" if placed.get("potrace_svg") else "raster"
        steps.append(f"lineart:xdog {kind}")
    if placed.get("silhouette"):
        steps.append(f"outline:{placed['silhouette']}")

    return Provenance(
        source=str(file),
        sha256=source_hash,
        pixel_size=(int(source_w), int(source_h)),
        subject_box=tuple(crop),
        steps=tuple(steps),
        license=license if license is not None else card.license,
        attribution=attribution if attribution is not None else card.attribution,
        source_url=source_url if source_url is not None else card.source_url,
        notes=card.notes,
    )


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8",
    )
