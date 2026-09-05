"""Separating a subject from its background.

Backends are registered by name, because a name is the only thing that can go
into a cache key. Passing a bare function would put its `repr` -- which
contains a memory address -- into the hash, and the same script would then
produce a different file on every run.

Which one to reach for:

``alpha``
    The image already carries transparency. Free, exact, and the right answer
    for anything exported from Illustrator, Blender or a PNG icon set.
``corner``
    Chroma key flooded inward from the frame. Pure Pillow and NumPy, and it
    handles the overwhelmingly common case of a subject photographed or drawn
    on white, on a light-box, or on a flat studio backdrop. It cannot cope with
    a background that is also *inside* the subject silhouette but disconnected
    from the frame, and it will eat a genuinely white part of the subject that
    touches the edge of the picture.
``auto`` (default)
    ``alpha`` when the file has meaningful transparency, otherwise ``corner``.
    The choice is recorded in the provenance chain, never silent.
``rembg``
    A learned matte (U^2-Net). The right tool for a subject on a busy or
    textured background -- an animal in grass, a rig on a bench. Optional, and
    deliberately never the default: the package pulls in ONNX Runtime and
    downloads a ~180 MB model on first use. That download is network access at
    diagram-build time, which this library otherwise forbids, so warm the model
    up once outside your build and treat it as a fixture.
``none``
    The whole canvas is the subject. Use it for a figure panel that really is
    rectangular.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from .deps import AssetError, numpy, require
from .mask import border_seeds, flood

__all__ = [
    "Cutout", "CutoutResult", "as_cutout", "run_cutout",
    "register_cutout", "cutout_backends",
]

# Alpha at or above this counts as subject when the mask drives geometry. Half
# coverage is the only defensible place to put the line on an antialiased edge.
SOLID = 128


@dataclass(frozen=True)
class Cutout:
    """How to key the background out.

    `tolerance` is a colour distance in 0..1, where 1 is the diagonal of the
    RGB cube. `feather` is the fraction of that tolerance below which a pixel
    is fully transparent; between the two, alpha ramps, which is what keeps a
    keyed edge from looking cut with scissors.
    """

    backend: str = "auto"
    tolerance: float = 0.08
    feather: float = 0.5
    options: tuple[tuple[str, Any], ...] = ()   # sorted; passed through to plugins

    def key(self) -> dict[str, Any]:
        return {"backend": self.backend, "tolerance": self.tolerance,
                "feather": self.feather, "options": list(self.options)}


@dataclass(frozen=True)
class CutoutResult:
    alpha: Any     # uint8 (h, w)
    backend: str   # what actually ran, after `auto` resolved


def as_cutout(spec: Cutout | str | bool | None, **overrides: Any) -> Cutout:
    """Coerce the `cutout=` argument. `False`/`None` mean "do not key"."""
    if spec is None or spec is False:
        base = Cutout(backend="none")
    elif spec is True:
        base = Cutout()
    elif isinstance(spec, Cutout):
        base = spec
    elif isinstance(spec, str):
        base = Cutout(backend=spec)
    else:
        raise AssetError(
            f"cutout must be a name, a Cutout or a boolean, not {type(spec).__name__}; "
            "register a custom backend with register_cutout(name, fn) so that it "
            "has a name to put in the cache key"
        )
    given = {k: v for k, v in overrides.items() if v is not None}
    return replace(base, **given) if given else base


def run_cutout(rgba: Any, spec: Cutout) -> CutoutResult:
    np = numpy()
    backend = _resolve(rgba, spec.backend)
    handler = _BACKENDS.get(backend)
    if handler is None:
        raise AssetError(
            f"unknown cutout backend {backend!r}; known backends are {cutout_backends()}"
        )
    alpha = handler(rgba, spec)
    if alpha.shape != rgba.shape[:2]:
        raise AssetError(
            f"cutout backend {backend!r} returned a {alpha.shape} mask "
            f"for a {rgba.shape[:2]} image"
        )
    return CutoutResult(alpha.astype(np.uint8), backend)


def _resolve(rgba: Any, backend: str) -> str:
    if backend != "auto":
        return backend
    return "alpha" if _has_transparency(rgba) else "corner"


def _has_transparency(rgba: Any) -> bool:
    return bool((rgba[:, :, 3] < SOLID).any())


# -- backends -------------------------------------------------------------


def _none(rgba: Any, spec: Cutout) -> Any:
    np = numpy()
    return np.full(rgba.shape[:2], 255, dtype=np.uint8)


def _alpha(rgba: Any, spec: Cutout) -> Any:
    if not _has_transparency(rgba):
        raise AssetError(
            "cutout='alpha' but the image is fully opaque; "
            "use cutout='corner' to key a flat background, or cutout=None to keep the frame"
        )
    return rgba[:, :, 3]


def _corner(rgba: Any, spec: Cutout) -> Any:
    """Flood a chroma key inward from the frame.

    The key colour is the *median* of the border ring rather than one corner
    pixel: a single corner can be a JPEG artefact or a vignette, while the
    median survives the subject touching one edge and needs no tie-break.

    Flooding rather than thresholding is what protects the subject's own light
    tones. A white belly keyed by threshold alone disappears; keyed by a flood
    that has to reach it from outside, it stays.
    """
    np = numpy()
    height, width = rgba.shape[:2]
    rgb = rgba[:, :, :3].astype(np.float64) / 255.0

    ring = np.concatenate([
        rgb[0, :, :], rgb[height - 1, :, :], rgb[:, 0, :], rgb[:, width - 1, :],
    ])
    key = np.median(ring, axis=0)

    # Normalised so `tolerance` means the same thing whatever the hue: 1.0 is
    # the full diagonal of the RGB cube.
    distance = np.sqrt(((rgb - key) ** 2).sum(axis=2) / 3.0)
    near = distance <= spec.tolerance
    background = flood(near, border_seeds(height, width))

    low = spec.tolerance * spec.feather
    span = max(spec.tolerance - low, 1e-6)
    ramp = np.clip((distance - low) / span, 0.0, 1.0)
    alpha = np.where(background, ramp * 255.0, 255.0)
    # Whatever transparency the file already had still applies; keying can only
    # remove coverage, never invent it.
    return np.minimum(alpha, rgba[:, :, 3].astype(np.float64)).round().astype(np.uint8)


def _rembg(rgba: Any, spec: Cutout) -> Any:
    np = numpy()
    rembg = require("rembg")
    Image = require("PIL.Image")
    options = dict(spec.options)
    cut = rembg.remove(Image.fromarray(rgba, mode="RGBA"), **options)
    return np.asarray(cut.convert("RGBA"), dtype=np.uint8)[:, :, 3]


_BACKENDS: dict[str, Callable[[Any, Cutout], Any]] = {
    "none": _none,
    "alpha": _alpha,
    "corner": _corner,
    "rembg": _rembg,
}


def register_cutout(name: str, handler: Callable[[Any, Cutout], Any]) -> None:
    """Add a backend. `handler(rgba, spec)` returns a uint8 alpha plane of the
    same height and width. The name is what lands in the cache key, so changing
    a handler's behaviour without changing its name will serve stale files --
    register it under a new name, or bump `cache.PIPELINE_VERSION`."""
    _BACKENDS[name] = handler


def cutout_backends() -> tuple[str, ...]:
    """Sorted, so anything that prints or iterates these stays deterministic."""
    return tuple(sorted(_BACKENDS))
