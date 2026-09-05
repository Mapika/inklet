"""Two synthetic micrographs, generated rather than shipped.

The figure needs a raster to composite -- a scale bar over it, an ROI ring on
it, a leader clipped to a particle -- and a stress test should not depend on
someone's copyrighted SEM. These are simulated: nanocubes lit from the upper
left with the edge brightening a secondary-electron image has, and a lattice
image whose fringe spacing is the (111) spacing of Cu2O at the magnification
the caption claims. Deterministic, so the page is byte-identical run to run.

    .venv/bin/python stress/electro/micrograph.py --force
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent / "assets"

#: Field of view of the SEM frame, nanometres, and the pixel grid it is
#: sampled on. 1600 px over 900 nm is 1.8 px/nm: at 46mm on the page that is
#: 880 dpi, so the raster is never the limit and `LOW_DPI` stays quiet.
SEM_NM = 900.0
SEM_PX = 1600
TEM_NM = 12.0
TEM_PX = 900

#: Cu2O (111) spacing, nanometres. The fringes in the lattice image are drawn
#: at this spacing through the same nm-per-pixel scale as everything else, so
#: the number quoted in the panel is measurable off the image.
D111 = 0.246


def _cube_faces(centre, size, yaw, pitch):
    """The three visible faces of a cube, as 2D polygons in nanometres.

    An axonometric projection with the light and the camera both fixed: the
    top, and the two side faces that face the viewer. Enough to read as a
    cube, and cheap enough for four hundred of them.
    """
    cx, cy = centre
    half = size / 2.0
    ca, sa = math.cos(yaw), math.sin(yaw)
    lift = math.sin(pitch) * half
    # Top face: a rotated square, squashed vertically by the tilt.
    corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
    top = [(cx + x * ca - y * sa, cy + (x * sa + y * ca) * math.cos(pitch) - lift)
           for x, y in corners]
    faces = [(top, 1.0)]
    # The two front-facing sides hang off the two lower edges of the top.
    order = sorted(range(4), key=lambda i: -top[i][1])
    for a, b in ((order[0], order[1]),):
        pass
    lows = sorted(range(4), key=lambda i: top[i][1])[2:]
    lows.sort(key=lambda i: top[i][0])
    for index, i in enumerate(lows):
        j = (i + 1) % 4 if top[(i + 1) % 4][1] >= top[(i - 1) % 4][1] else (i - 1) % 4
        p, q = top[i], top[j]
        drop = size * math.cos(pitch) * 0.85
        side = [p, q, (q[0], q[1] + drop), (p[0], p[1] + drop)]
        faces.append((side, 0.52 if index == 0 else 0.34))
    return faces


def sem(path: Path) -> None:
    """A field of oxide nanocubes on a carbon support."""
    rng = np.random.default_rng(8_1_2026)
    scale = SEM_PX / SEM_NM
    image = Image.new("L", (SEM_PX, SEM_PX), 26)
    draw = ImageDraw.Draw(image)

    # Support: a coarse mottle, drawn as blurred blobs rather than as noise so
    # it survives the downsampling a printed figure does to it.
    for _ in range(320):
        x, y = rng.uniform(0, SEM_PX, 2)
        r = rng.uniform(18, 90)
        tone = int(rng.uniform(30, 58))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=tone)
    image = image.filter(ImageFilter.GaussianBlur(11))
    draw = ImageDraw.Draw(image)

    # Cubes, far to near, so a nearer one occludes what is behind it.
    cubes = []
    for _ in range(430):
        depth = rng.uniform(0.0, 1.0)
        size = rng.lognormal(math.log(34.0), 0.34) * (0.72 + 0.5 * depth)
        cubes.append((depth, rng.uniform(0, SEM_NM), rng.uniform(0, SEM_NM),
                      size, rng.uniform(0, math.pi / 2), rng.uniform(0.5, 0.8)))
    for depth, x, y, size, yaw, pitch in sorted(cubes):
        bright = 118 + 96 * depth
        for polygon, shade in _cube_faces((x * scale, y * scale), size * scale,
                                          yaw, pitch):
            tone = int(min(255, bright * shade + 22))
            draw.polygon(polygon, fill=tone, outline=int(min(255, tone * 1.5)))

    array = np.asarray(image, dtype=np.float32)
    # Secondary-electron edge brightening: the signal rises where the surface
    # turns away, which is what makes an SEM look like an SEM.
    edges = np.asarray(image.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    array = array + 0.45 * edges
    # Shot noise, then the faint horizontal streak of a slow scan.
    array += rng.normal(0.0, 7.0, array.shape)
    array += (rng.normal(0.0, 3.0, (SEM_PX, 1)) @ np.ones((1, SEM_PX)))
    out = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.GaussianBlur(0.8))
    out.save(path, optimize=True)


def tem(path: Path) -> None:
    """A lattice image of one particle's corner: two grains and their fringes."""
    rng = np.random.default_rng(2_2_2026)
    scale = TEM_PX / TEM_NM
    y, x = np.mgrid[0:TEM_PX, 0:TEM_PX].astype(np.float32)
    nm_x, nm_y = x / scale, y / scale

    # Two grains meeting on a boundary that runs top-left to bottom-right.
    boundary = nm_y - (0.55 * nm_x + 3.4)
    field = np.zeros_like(nm_x)
    for grain, angle in ((boundary < 0, math.radians(24.0)),
                         (boundary >= 0, math.radians(-51.0))):
        phase = 2 * math.pi * (nm_x * math.cos(angle) + nm_y * math.sin(angle)) / D111
        # A second set at 70.5 degrees to the first: the angle between {111}
        # planes in a cubic lattice, which is what makes it read as a lattice
        # rather than as a grating.
        second = 2 * math.pi * (nm_x * math.cos(angle + 1.23)
                                + nm_y * math.sin(angle + 1.23)) / D111
        field = np.where(grain, np.cos(phase) + 0.72 * np.cos(second), field)

    # The particle itself: fringes only inside it, amorphous carbon outside.
    # A cube corner, not a disc: the particle edge is two straight facets
    # meeting, which is the whole reason this material is called a nanocube.
    facet = np.maximum(np.abs(nm_x - 5.2) - 3.6, np.abs(nm_y - 5.6) - 3.9)
    inside = 1.0 / (1.0 + np.exp(facet / 0.22))
    # The support the particle sits on is amorphous: a speckle with no
    # periodicity, so the fringes read as the crystal and not as the image.
    amorphous = rng.normal(0.0, 1.0, field.shape).astype(np.float32)
    amorphous = np.asarray(
        Image.fromarray(((amorphous * 40 + 128).clip(0, 255)).astype(np.uint8))
        .filter(ImageFilter.GaussianBlur(2.4)), dtype=np.float32) - 128.0
    array = 122 + 54 * field * inside + 1.9 * amorphous * (1.0 - inside)
    array += rng.normal(0.0, 11.0, array.shape)
    image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
    image.filter(ImageFilter.GaussianBlur(1.1)).save(path, optimize=True)


def ensure(force: bool = False) -> tuple[Path, Path]:
    """Both micrographs, generated if they are not already on disk."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames = ASSETS / "sem.png", ASSETS / "tem.png"
    for path, build in zip(frames, (sem, tem)):
        if force or not path.exists():
            build(path)
    return frames


if __name__ == "__main__":
    paths = ensure(force="--force" in sys.argv)
    for path in paths:
        with Image.open(path) as image:
            print(f"{path.name}: {image.size[0]}x{image.size[1]} "
                  f"{path.stat().st_size // 1024} kB")
