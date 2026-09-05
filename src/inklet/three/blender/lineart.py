"""The entry point: a mesh file in, millimetre polylines out.

Everything expensive happens in another process and is cached on disk, so the
second build of a figure costs a file read. The cache is the one in
`inklet.assets.cache` -- same helpers, same atomic rename, same rule that a hit is
provably the file the pipeline would have written, because the key is a hash of
the mesh bytes and of the bake program itself. Freezing the parameters into the
generated script (see `script.py`) is what makes that airtight: there is no
second list of "things that affect the output" to keep in sync.

Determinism is a hard contract here. Blender's Line Art is deterministic given
the same scene, and the scene is built by a program with no dictionary
iteration, no set iteration and no clock in it; the subprocess additionally
runs under `PYTHONHASHSEED=0` and `LC_ALL=C` so that neither hash randomisation
nor a comma-decimal locale can reach the numbers in the SVG.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ...assets.cache import cache_root, canonical, content_hash, slug
from ...assets.silhouette import Silhouette
from ...core.geom import Vec2
from ..camera import Camera, as_camera
from ..linalg import Vec3
from .discover import Blender, BlenderError, find_blender
from .options import LineArtOptions, UP_AXES
from .tracing import NONE, outline
from .script import IMPORTERS, METADATA_MARKER, SCRIPT_VERSION, build_script
from .svgread import Layer, place_layers, read_gpencil_svg

__all__ = [
    "LineArtDrawing", "line_art", "bake_svg", "cache_key", "camera_spec",
    "page_up", "LINES_LAYER", "SILHOUETTE_LAYER",
    "DEFAULT_RESOLUTION", "DEFAULT_TIMEOUT", "DEFAULT_MARGIN", "POLE_DEGREES",
]

LINES_LAYER = "lines"
SILHOUETTE_LAYER = "silhouette"

#: Pixels on the long side of the camera frame. This is the grid the exporter
#: quantises stroke coordinates onto, so it is a precision setting and not a
#: quality one: 1024 puts the quantisation at a thousandth of the drawing,
#: which is a twentieth of a printer's dot at 50 mm wide.
DEFAULT_RESOLUTION = 1024

#: Seconds. Line Art on a 70k-face scan takes a fifth of a second; this is
#: sized for a CAD assembly on a loaded machine, not for the common case.
DEFAULT_TIMEOUT = 300.0

#: How many times to run Blender before giving up. More than one only because
#: Line Art occasionally segfaults on a heavily folded surface; see `bake_svg`.
ATTEMPTS = 3

#: Threads to give Blender, pinned rather than left to the core count.
#:
#: Line Art's output depends on how many threads it ran with. The same bake of
#: `stress/meshes/brain-lh.obj` gives three different files at one, two and
#: four threads -- same stroke count, different order and values -- and is
#: stable from four upwards; two other meshes agree from three upwards. Left
#: alone, Blender takes the core count, so the same script would draw one
#: picture on a laptop and another on a build machine, which is exactly the
#: promise this package makes it does not do. Eight is inside the stable band
#: with room to spare, and is where Line Art stops getting faster anyway:
#: 278k faces took 1.6s at eight threads and 2.3s at sixteen. Oversubscribing
#: a small machine costs little -- the same bake confined to two cores took
#: 2.9s and produced identical bytes.
THREADS = 8

#: Fraction of the camera frame left empty on each side when the framing is
#: automatic. Only visible with `fit="frame"`; with `fit="content"` it simply
#: keeps the subject clear of the clip that `use_clip_camera` applies.
DEFAULT_MARGIN = 0.04

#: An elevation within this of straight up leaves the world's up parallel to
#: the view. `inklet.three.camera` uses the same half-degree band and the same
#: replacement, and `test_three_blender` asserts the two still agree.
POLE_DEGREES = 89.5


@dataclass(frozen=True)
class LineArtDrawing:
    """What Blender drew, in origin-centred millimetres with y downward.

    `polylines` are open strokes; feeding them to `PathPrim` with `filled=False`
    is the intended use. `silhouette` is the subject's outer outline as a
    closed polygon, ready for `ImagePrim.outline` or `Trace.from_polygon`, or
    None when Line Art found no outline to close.

    There is deliberately no stroke width. Blender exports one -- two units
    against a hundred-unit frame, which is two per cent of the figure and
    renders as a row of blobs -- and rescaling it would be dressing up a number
    that was never a line weight. Weight belongs to the theme, as it does for
    every other primitive in inklet.

    `report` is the bake's own account of itself: the Blender version, the face
    count, the camera framing, and the recentre-and-scale that was applied to
    the model before any of it. `mm_per_pixel` closes the loop from that report
    back to the page, so a caller can work out where a named 3D point landed.
    """

    polylines: tuple[tuple[Vec2, ...], ...]
    silhouette: Silhouette | None
    width: float                 # mm actually occupied
    height: float                # mm actually occupied
    viewbox: tuple[float, float, float, float]   # source frame, for provenance
    source: str                  # the mesh path as the author wrote it
    mesh_sha256: str             # content hash of the mesh bytes
    key: str                     # cache key: the mesh and every render setting
    mm_per_pixel: float          # source frame units to millimetres
    # Metadata, deliberately outside equality: two drawings that differ only in
    # whether they came from the cache are the same drawing.
    report: dict[str, Any] = field(default_factory=dict, compare=False)
    outline_method: str = field(default=NONE, compare=False)
    svg_path: Path | None = field(default=None, compare=False)
    cached: bool = field(default=False, compare=False)
    seconds: float = field(default=0.0, compare=False)

    @property
    def points(self) -> int:
        return sum(len(line) for line in self.polylines)

    def summary(self) -> str:
        shape = (f"{self.silhouette.summary()} {self.outline_method}"
                 if self.silhouette else "no outline")
        return (
            f"{Path(self.source).name}: {len(self.polylines)} strokes, "
            f"{self.points} pts, {self.width:.3g}x{self.height:.3g}mm, {shape}"
        )


def line_art(mesh: str | Path, *, width: float, height: float | None = None,
             camera: Camera | str | tuple[float, float] | None = None,
             options: LineArtOptions | None = None,
             up_axis: str = "y", fit: str = "content",
             scale: float | None = None, margin: float = DEFAULT_MARGIN,
             resolution: int = DEFAULT_RESOLUTION,
             cache_dir: str | Path | None = None,
             blender: str | Path | None = None,
             timeout: float = DEFAULT_TIMEOUT,
             refresh: bool = False) -> LineArtDrawing:
    """Draw `mesh` as hidden-line-removed vector line art.

    `width` and `height` are millimetres. With only `width`, the drawing takes
    that width and whatever height its aspect ratio implies; with both, it is
    fitted inside the box and never stretched, and the reported size is what it
    actually came to occupy.

    `camera` is anything `inklet.three.camera.as_camera` accepts -- a `Camera`, a
    preset name, or an `(azimuth, elevation)` pair -- so the same camera draws
    the same view through either backend.

    `options` is a `LineArtOptions`. Its `crease` default of 30 degrees suits a
    modelled object, where the folds are designed and a contour alone would
    miss every fillet. A scanned surface is the opposite case -- 30 degrees
    inks its triangulation -- and wants `shade_smooth=True` instead, which
    stops Line Art creasing at all and leaves the contours, which on a folded
    surface are most of the drawing anyway. `LineArtOptions` documents the
    measurements behind that.

    `up_axis` names the mesh file's own up axis, `"y"` (the OBJ convention, and
    the default) or `"z"`. Model space downstream of it is z-up, as
    `inklet.three.camera` documents. Getting it wrong lays the subject on its side
    and makes every named view mean something else.

    The mesh is recentred and scaled into a two-unit cube before the camera is
    placed, because Line Art's own constants are absolute world distances and a
    surface exported at 177 units draws differently from the same surface at
    0.02. `scale` is then the width of the camera frame in those normalised
    units -- give it when several figures must be at one scale, leave it None
    to fit each drawing on its own. `margin` is the fraction of the frame left
    empty when fitting.

    `fit` is `"content"` -- scale the ink to the requested box -- or `"frame"`,
    which scales the camera frame instead and so keeps several views of one
    subject at a single scale. `refresh=True` re-bakes even on a cache hit,
    which is only useful when debugging this backend.

    Raises `BlenderError` (`BlenderNotFound`, `BlenderTooOld`) for anything
    that cannot be done, including the absence of Blender itself.
    """
    started = time.perf_counter()
    path = Path(mesh).expanduser()
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in IMPORTERS:
        raise BlenderError(
            f"{path.name}: this backend imports "
            f"{', '.join('.' + s for s in IMPORTERS)}, not .{suffix}"
        )
    if not path.is_file():
        raise BlenderError(
            f"no such mesh: {str(path)!r}"
            + ("; it is a directory" if path.is_dir() else "")
        )
    if up_axis not in UP_AXES:
        raise BlenderError(
            f"up_axis must be one of {', '.join(UP_AXES)}, not {up_axis!r}")
    if scale is not None and scale <= 0:
        raise BlenderError(f"scale must be a positive width, not {scale}")
    if not -1.0 < margin < 0.9:
        raise BlenderError(f"margin must be a small fraction, not {margin}")
    if resolution < 64:
        raise BlenderError(
            f"resolution is the camera frame in pixels and quantises every "
            f"stroke; {resolution} is too coarse to draw with"
        )

    chosen = options or LineArtOptions()
    frame = _frame_pixels(resolution, width, height)
    script = build_script(
        camera=camera_spec(as_camera(camera), scale=scale, margin=margin),
        lineart=chosen.key(), resolution=frame, up_axis=up_axis,
    )

    digest = content_hash(path)
    key = cache_key(digest, suffix, script)
    root = cache_root(cache_dir)
    target = root / f"{slug(path.stem)}-{key}.svg"
    hit = target.exists() and not refresh
    if not hit:
        _write_atomically(target, lambda temp: bake_svg(
            path, temp, script=script, blender=blender, timeout=timeout))

    document = read_gpencil_svg(target.read_text(encoding="utf-8"))
    placed, box_width, box_height, scale_factor = place_layers(
        document, width=width, height=height, fit=fit)
    lines = _named(placed, LINES_LAYER)
    rim = _named(placed, SILHOUETTE_LAYER)
    shape, method = outline(
        rim.polylines if rim else (),
        lines.polylines if lines else (),
        width=box_width, height=box_height,
    )
    return LineArtDrawing(
        polylines=lines.polylines if lines else (),
        silhouette=shape,
        width=box_width, height=box_height,
        viewbox=document.viewbox, mm_per_pixel=scale_factor,
        source=str(mesh), mesh_sha256=digest, key=key,
        report=document.metadata, outline_method=method,
        svg_path=target, cached=hit, seconds=time.perf_counter() - started,
    )


def camera_spec(camera: Camera, *, scale: float | None,
                margin: float) -> dict[str, Any]:
    """`inklet.three.camera.Camera` as the flat dictionary the bake script reads.

    Only the parts Blender needs, and all of them already resolved: the unit
    direction from the subject towards the eye, the page-up vector past the
    pole rule, the roll, and any pinned eye or target.
    """
    up = page_up(camera)
    direction = camera.direction
    return {
        "direction": [direction.x, direction.y, direction.z],
        "up": [up.x, up.y, up.z],
        "roll": camera.roll,
        "eye": _vector(camera.eye),
        "target": _vector(camera.target),
        "perspective": bool(camera.perspective),
        "fov": camera.fov,
        "scale": scale,
        "margin": margin,
    }


def page_up(camera: Camera) -> Vec3:
    """Which way is up on the page for this camera.

    This reproduces `inklet.three.camera.Camera._up`, whose rule is that world z
    is up until the view is within half a degree of the pole, at which point
    +y takes over and a plan view comes out with north at the top. Reproduced
    rather than called because it is private to that module; the two are
    pinned together by a test that renders both and compares the bases.
    """
    if camera.up is not None:
        return camera.up
    if abs(camera.elevation) > POLE_DEGREES:
        return Vec3(0.0, 1.0, 0.0)
    return Vec3(0.0, 0.0, 1.0)


def _vector(value: Vec3 | None) -> list[float] | None:
    return None if value is None else [value.x, value.y, value.z]


def cache_key(source_hash: str, suffix: str, script: str) -> str:
    """Everything the bake depends on, in one hash.

    The bake program carries its own parameters as a literal, so hashing its
    text covers the camera, the line-art options, the resolution and the code
    itself in one go. The suffix is separate because it is not in the bytes:
    the same vertices as `.obj` and as `.ply` go through different importers,
    and so is the thread count, which is not in the script but does change what
    Line Art draws.
    """
    digest = hashlib.sha256()
    digest.update(f"inklet.three.blender/{SCRIPT_VERSION}/t{THREADS}\n".encode())
    digest.update(source_hash.encode())
    digest.update(canonical(suffix).encode())
    digest.update(hashlib.sha256(script.encode("utf-8")).hexdigest().encode())
    return digest.hexdigest()[:32]


def bake_svg(mesh: Path, out: Path, *, script: str,
             blender: str | Path | None = None,
             timeout: float = DEFAULT_TIMEOUT) -> Blender:
    """Run one bake. Writes the SVG to `out` and returns the binary that did it.

    `--factory-startup` keeps a user's add-ons and preferences out of the
    scene, which is a determinism requirement rather than a nicety: an add-on
    that registers a depsgraph handler would be running inside our bake.
    `--python-exit-code` is what makes a traceback in the bake script a
    non-zero return code; without it Blender reports success having done
    nothing.
    """
    found = find_blender(blender)
    with tempfile.TemporaryDirectory(prefix="inklet-lineart-") as workspace:
        program = Path(workspace) / "bake.py"
        program.write_text(script, encoding="utf-8")
        command = [
            str(found.path), "--background", "--factory-startup", "-noaudio",
            "--threads", str(THREADS),
            "--python-exit-code", "3", "--python", str(program),
            "--", str(mesh), str(out),
        ]
        # A fixed hash seed and the C locale, because the bake script sorts and
        # formats numbers and the result has to be byte-identical between two
        # machines that disagree about decimal commas.
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = "0"
        environment["LC_ALL"] = "C"
        environment["LANG"] = "C"
        for attempt in range(ATTEMPTS):
            try:
                done = subprocess.run(
                    command, capture_output=True, text=True, timeout=timeout,
                    check=False, env=environment,
                )
            except subprocess.TimeoutExpired as exc:
                raise BlenderError(
                    f"Blender did not finish baking {mesh.name} within "
                    f"{timeout:g}s. Line Art cost grows with the face count "
                    "and with how much of the frame the subject fills; raise "
                    "timeout= or simplify the mesh."
                ) from exc
            except OSError as exc:
                raise BlenderError(f"cannot run {found.path}: {exc}") from exc
            if done.returncode >= 0 or _finished(out) or attempt == ATTEMPTS - 1:
                break
            # Blender 4.2's Line Art can die of a signal on a convoluted mesh,
            # rarely and without a pattern. Retrying is safe precisely because
            # the bake is deterministic: a second run either writes the same
            # bytes the first would have, or fails again and is reported.

    # The exit status is not the last word. Blender can also die in CPython's
    # finalisation, after the export has been written and closed -- the bake
    # script leaves before finalisation for exactly that reason, but a crash
    # anywhere downstream of `annotate` would be equally harmless. So a
    # completed artifact overrules a bad status: `_finished` insists on the
    # metadata comment, which is written last of all and which nothing but a
    # complete bake can produce.
    if done.returncode != 0 and not _finished(out):
        raise BlenderError(
            f"{found.banner} failed to bake {mesh.name} "
            f"(exit {done.returncode}).\n{_diagnosis(done)}"
        )
    if not out.exists() or out.stat().st_size == 0:
        raise BlenderError(
            f"{found.banner} reported success but wrote no SVG for "
            f"{mesh.name}.\n{_diagnosis(done)}"
        )
    return found


def _finished(out: Path) -> bool:
    """Whether `out` carries the end-of-bake marker the script appends last."""
    try:
        tail = out.read_bytes()[-4096:]
    except OSError:
        return False
    return METADATA_MARKER.encode("utf-8") in tail and tail.rstrip().endswith(
        b"</svg>")


# -- plumbing -------------------------------------------------------------


def _named(layers: Sequence[Layer], name: str) -> Layer | None:
    for layer in layers:
        if layer.name == name:
            return layer
    return None


def _frame_pixels(resolution: int, width: float,
                  height: float | None) -> tuple[int, int]:
    """The camera frame in pixels, shaped like the box the caller asked for.

    Matching the frame to the requested aspect matters for `fit="frame"`, where
    the frame is what gets scaled into the box: a square frame fitted into a
    wide box would leave the drawing marooned in the middle of it.
    """
    if height is None or height <= 0 or width <= 0:
        return (resolution, resolution)
    if width >= height:
        return (resolution, max(64, int(round(resolution * height / width))))
    return (max(64, int(round(resolution * width / height))), resolution)


def _write_atomically(target: Path, build) -> None:
    """`inklet.assets.cache.cached_file`'s discipline, without its existence check:
    the caller has already decided to build, because `refresh=True` must be able
    to overwrite a hit."""
    target.parent.mkdir(parents=True, exist_ok=True)
    # The `.svg` has to survive on the end: Blender's exporter appends the
    # extension itself when the path it is given does not have it, and would
    # write next to the temp file rather than to it.
    temp = target.with_name(f"{target.name}.{os.getpid()}.part.svg")
    try:
        build(temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


def _diagnosis(done: subprocess.CompletedProcess) -> str:
    """What to show a caller when a bake fails.

    Blender writes a great deal to stdout that is not about their mesh, so the
    bake script's own `inklet-lineart-error:` lines come first when there are any;
    only when there are none is the raw tail worth showing.
    """
    lines = [line for line in (done.stderr or "").splitlines()
             if line.startswith("inklet-lineart-error:")]
    if lines:
        return "\n".join(line.split(":", 1)[1].strip() for line in lines)
    tail = (done.stderr or "").strip().splitlines()[-12:]
    if not tail:
        tail = (done.stdout or "").strip().splitlines()[-12:]
    return "\n".join(tail) or "(Blender said nothing)"
