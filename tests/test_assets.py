"""The image pipeline, checked against geometry rather than against pixels.

Every fixture is drawn here with Pillow. Committing a PNG would make the tests
depend on a binary nobody can review in a diff, and the interesting inputs are
shapes with a property -- an asymmetric silhouette, a margin that must not
become layout space -- which are easier to state in code than to find in a
photograph.

The asymmetric fixture is an L, deliberately. A circle or a square passes an
outline test that is flipped in y, mirrored in x, or off by the DPI; an L fails
all three, and those are exactly the mistakes this module is prone to.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

np = pytest.importorskip("numpy", reason="the image pipeline needs inklet[images]")
Image = pytest.importorskip("PIL.Image", reason="the image pipeline needs inklet[images]")

import inklet
from inklet.assets import (
    AssetError, Cutout, Harmonise, LineArt, asset, credit_lines, credits,
    cutout_backends, potrace_available, provenance_of, register_cutout,
    sidecar_path,
)
from inklet.assets.deps import MissingDependency, require
from inklet.assets.lineart import parse_potrace_svg, xdog
from inklet.assets.silhouette import is_simple, simplify_ring
from inklet.core import Vec2, resolve
from inklet.themes.color import parse_color
from inklet.links import FLAG_SOURCE_MISSED, link, route

WHITE = (255, 255, 255)
BLUE = (30, 60, 200)

# The L, in source pixels. Canvas 200x200, subject 100 wide by 120 tall at
# (40, 40): a 25% margin on the left and right and a 20% one top and bottom,
# none of which the asset may claim.
ELL_CANVAS = 200
ELL_X0, ELL_Y0 = 40, 40
ELL_W, ELL_H = 100, 120
ELL_BAR = 30          # width of the upright
ELL_FOOT = 30         # height of the foot


# -- fixtures -------------------------------------------------------------


def ell_array(background=WHITE, alpha: bool = False, bar: int = ELL_BAR):
    """An L with its upright on the left and its foot along the bottom."""
    shape = (ELL_CANVAS, ELL_CANVAS)
    filled = np.zeros(shape, dtype=bool)
    filled[ELL_Y0:ELL_Y0 + ELL_H, ELL_X0:ELL_X0 + bar] = True
    filled[ELL_Y0 + ELL_H - ELL_FOOT:ELL_Y0 + ELL_H, ELL_X0:ELL_X0 + ELL_W] = True

    out = np.zeros((*shape, 4), dtype=np.uint8)
    out[:, :, :3] = background
    out[filled, :3] = BLUE
    out[:, :, 3] = np.where(filled, 255, 0) if alpha else 255
    return out


def disc_array(radius: int = 60, size: int = 240):
    rows, cols = np.mgrid[0:size, 0:size]
    inside = (rows - size // 2) ** 2 + (cols - size // 2) ** 2 < radius ** 2
    out = np.zeros((size, size, 4), dtype=np.uint8)
    out[:, :, :3] = WHITE
    out[inside, :3] = (200, 40, 40)
    out[:, :, 3] = 255
    return out


def save(tmp_path: Path, name: str, array) -> Path:
    path = tmp_path / name
    mode = "RGBA" if array.shape[2] == 4 else "RGB"
    Image.fromarray(array, mode=mode).save(path)
    return path


@pytest.fixture
def ell(tmp_path):
    return save(tmp_path, "ell.png", ell_array())


@pytest.fixture
def wide_ell(tmp_path):
    """The same L with a 60 px upright, so its bounding-box centre lands inside
    the silhouette and a ray fired from there has something to cross."""
    return save(tmp_path, "wide.png", ell_array(bar=60))


@pytest.fixture
def disc(tmp_path):
    return save(tmp_path, "disc.png", disc_array())


@pytest.fixture
def cache(tmp_path):
    return tmp_path / "cache"


# -- helpers --------------------------------------------------------------


def contains(polygon, point: Vec2) -> bool:
    """Even-odd point-in-polygon, written out so the assertion does not lean on
    the same `Trace` code the outline is being fed to."""
    inside = False
    count = len(polygon)
    for i in range(count):
        a, b = polygon[i], polygon[(i + 1) % count]
        if (a.y > point.y) != (b.y > point.y):
            cross = a.x + (point.y - a.y) / (b.y - a.y) * (b.x - a.x)
            if cross > point.x:
                inside = not inside
    return inside


def bbox_of(points):
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


# -- sizing ---------------------------------------------------------------


def test_width_only_derives_height_from_the_subject(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    assert node.prim.width == pytest.approx(25.0)
    # 120/100 from the L, not 1.0 from the square canvas it was drawn on.
    assert node.prim.height == pytest.approx(30.0)


def test_height_only_derives_width(ell, cache):
    node = asset(ell, height=30, cache_dir=cache)
    assert node.prim.width == pytest.approx(25.0)


def test_both_given_are_obeyed(ell, cache):
    node = asset(ell, width=25, height=25, cache_dir=cache)
    assert (node.prim.width, node.prim.height) == pytest.approx((25.0, 25.0))


def test_neither_given_uses_the_default_width(ell, cache):
    node = asset(ell, cache_dir=cache)
    assert node.prim.width == pytest.approx(inklet.assets.DEFAULT_WIDTH)


def test_units_are_parsed(ell, cache):
    node = asset(ell, width="1cm", cache_dir=cache)
    assert node.prim.width == pytest.approx(10.0)


# -- subject bounds, not canvas bounds ------------------------------------


def test_the_margin_is_not_layout_space(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    box = node.local_bbox
    assert (box.width, box.height) == pytest.approx((25.0, 30.0))
    # The canvas was square; had the margin survived, the envelope would be too.
    assert box.height > box.width


def test_pixel_size_is_the_subject_crop(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    assert node.prim.pixel_size == (ELL_W, ELL_H)


def test_dpi_is_measured_against_the_crop(ell, cache):
    node = asset(ell, width=25.4, cache_dir=cache)
    assert node.prim.effective_dpi() == pytest.approx(ELL_W)


def test_cutout_none_keeps_the_whole_frame(ell, cache):
    node = asset(ell, width=25, cutout=None, cache_dir=cache)
    assert node.prim.pixel_size == (ELL_CANVAS, ELL_CANVAS)
    assert node.prim.height == pytest.approx(25.0)


def test_alpha_backend_is_chosen_when_the_file_has_transparency(tmp_path, cache):
    path = save(tmp_path, "cut.png", ell_array(background=(9, 9, 9), alpha=True))
    node = asset(path, width=25, cache_dir=cache)
    assert provenance_of(node).steps[0] == "cutout:alpha"
    # A dark background would defeat a chroma key tuned for white; the alpha
    # channel is what makes this crop correct.
    assert node.prim.pixel_size == (ELL_W, ELL_H)


def test_a_cutout_that_finds_nothing_says_so(tmp_path, cache):
    blank = np.full((64, 64, 4), 255, dtype=np.uint8)
    path = save(tmp_path, "blank.png", blank)
    with pytest.raises(AssetError, match="left no subject"):
        asset(path, width=10, cache_dir=cache)


def test_specks_do_not_define_the_bounding_box(tmp_path, cache):
    array = ell_array()
    array[4:7, 190:193, :3] = BLUE      # a speck of dust in the top-right corner
    path = save(tmp_path, "speck.png", array)
    node = asset(path, width=25, cache_dir=cache)
    assert node.prim.pixel_size == (ELL_W, ELL_H)


# -- the outline's coordinate frame ---------------------------------------


def test_outline_is_in_local_millimetres(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    x0, y0, x1, y1 = bbox_of(node.prim.outline)
    assert (x0, y0, x1, y1) == pytest.approx((-12.5, -15.0, 12.5, 15.0), abs=1e-9)


def test_outline_is_not_flipped_in_y(ell, cache):
    """The foot of the L is at the *bottom*, and y grows downward."""
    node = asset(ell, width=25, cache_dir=cache)
    outline = node.prim.outline
    # Bottom-right of the local frame is inside the foot.
    assert contains(outline, Vec2(9.0, 12.0))
    # Top-right is the notch of the L: empty, and the mirror of the point above.
    assert not contains(outline, Vec2(9.0, -12.0))


def test_outline_is_not_mirrored_in_x(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    outline = node.prim.outline
    assert contains(outline, Vec2(-9.0, -12.0))     # the upright, top-left
    assert not contains(outline, Vec2(9.0, -12.0))


def test_outline_survives_a_rotated_upright(tmp_path, cache):
    """The same L reflected: the notch moves to the top-left."""
    path = save(tmp_path, "ell-mirror.png", ell_array()[:, ::-1].copy())
    node = asset(path, width=25, cache_dir=cache)
    outline = node.prim.outline
    assert contains(outline, Vec2(9.0, -12.0))
    assert not contains(outline, Vec2(-9.0, -12.0))


def test_outline_is_closed_and_simple(ell, cache):
    outline = asset(ell, width=25, cache_dir=cache).prim.outline
    assert len(outline) >= 3
    # `Trace.from_polygon(closed=True)` adds the closing edge itself, so a
    # repeated first point would be a zero-length edge.
    assert outline[0] != outline[-1]
    assert is_simple(outline)


def test_outline_is_simplified_hard(disc, cache):
    outline = asset(disc, width=20, cache_dir=cache).prim.outline
    assert 8 <= len(outline) <= 40    # tens of points, not the traced hundreds


def test_tolerance_trades_points_for_fidelity(disc, cache):
    coarse = asset(disc, width=20, outline_tolerance=1.5, cache_dir=cache)
    fine = asset(disc, width=20, outline_tolerance=0.05, cache_dir=cache)
    assert len(coarse.prim.outline) < len(fine.prim.outline)


def test_point_budget_is_respected(disc, cache):
    node = asset(disc, width=20, outline_tolerance=0.001, outline_max_points=12,
                 cache_dir=cache)
    assert len(node.prim.outline) <= 12


def test_outline_can_be_turned_off(ell, cache):
    node = asset(ell, width=25, outline=False, cache_dir=cache)
    assert node.prim.outline == ()
    # Without an outline the envelope is the frame -- but still the subject's.
    assert node.local_bbox.height == pytest.approx(30.0)


def test_simplify_keeps_the_extreme_vertices():
    ring = [Vec2(0, 0), Vec2(5, 0.01), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
    kept = simplify_ring(ring, tolerance=1.0)
    assert Vec2(0, 0) in kept and Vec2(10, 10) in kept
    assert Vec2(5, 0.01) not in kept


# -- arrows clip to the silhouette ----------------------------------------


def test_arrow_lands_on_the_silhouette_not_the_bounding_box(disc, cache):
    """A disc placed at the origin, a box on the diagonal.

    The disc's bbox corner is 14.14 mm from its centre and its edge is 10 mm.
    An arrow fired at 45 degrees has to stop at the edge.
    """
    circle = asset(disc, width=20, cache_dir=cache)
    target = inklet.box("V1").translated(40, 40)
    tree = inklet.Diagram(children=(circle, target))

    routed = route(link(circle, target), resolve(tree))
    tip = routed.anchor_point("start")

    radius = math.hypot(tip.x, tip.y)
    assert radius == pytest.approx(10.0, abs=0.25)   # polygon chord, not the bbox
    assert radius < 14.14 - 1.0
    assert tip.x > 0 and tip.y > 0                   # heading towards the target


def test_arrow_clips_on_a_concave_silhouette(wide_ell, cache):
    """The upright of this L is 15 mm wide; its bounding box is 25 mm.

    Firing up and to the right, the arrow has to leave through the side of the
    upright, nowhere near the corner of the frame.
    """
    node = asset(wide_ell, width=25, cache_dir=cache)
    target = inklet.box("x").translated(60, -60)
    tree = inklet.Diagram(children=(node, target))

    tip = route(link(node, target), resolve(tree)).anchor_point("start")
    assert tip.x == pytest.approx(2.5, abs=0.3)      # the upright's right edge
    assert tip.x < node.local_bbox.x1 - 9.0
    assert contains(node.prim.outline, Vec2(tip.x - 0.5, tip.y + 0.5))


def test_a_centre_outside_the_silhouette_is_flagged(ell, cache):
    """A limitation of `links`, recorded here rather than papered over.

    Connectors fire from a shape's bounding-box centre, and the centre of a
    narrow L is in its notch -- outside the silhouette. The ray then crosses
    nothing and the endpoint falls back to the centre. That is flagged on the
    routed diagram rather than silently wrong, but it is why an L-shaped asset
    wants an anchor rather than a plain `link()`.
    """
    node = asset(ell, width=25, cache_dir=cache)
    assert not contains(node.prim.outline, Vec2(0.0, 0.0))

    target = inklet.box("x").translated(60, -60)
    tree = inklet.Diagram(children=(node, target))
    routed = route(link(node, target), resolve(tree))
    assert FLAG_SOURCE_MISSED in (routed.name or "")


def test_the_whole_figure_still_builds(disc, cache):
    node = asset(disc, width=18, cache_dir=cache)
    area = inklet.box("V1")
    fig = inklet.figure(width=80)
    fig.add(inklet.hstack([node, area], gap=8))
    fig.link(node, area)
    assert "<image" in fig.to_svg()


# -- determinism ----------------------------------------------------------


def _figure_svg(path: Path, cache: Path) -> str:
    node = asset(path, width=18, cache_dir=cache)
    fig = inklet.figure(width=60)
    fig.add(node)
    return fig.to_svg()


def test_rendering_the_same_figure_twice_is_byte_identical(disc, cache):
    node = asset(disc, width=18, lineart=True, cache_dir=cache)
    fig = inklet.figure(width=60)
    fig.add(node)
    assert fig.to_svg() == fig.to_svg()


def test_the_embedded_raster_is_identical_across_builds(disc, cache):
    """Two independently built figures embed the same bytes.

    Node ids come off a process-wide counter, so two figures in one session do
    not serialise identically -- that is core's business and is what the
    cross-process test below covers. What has to hold here is that nothing in
    the image pipeline is a source of difference.
    """
    payloads = [_payload(_figure_svg(disc, cache)) for _ in range(2)]
    assert payloads[0] == payloads[1]
    assert payloads[0].startswith("data:image/png;base64,")


def _payload(svg: str) -> str:
    start = svg.index('xlink:href="') + len('xlink:href="')
    return svg[start:svg.index('"', start)]


def test_same_input_same_svg_across_processes(disc, cache):
    script = textwrap.dedent(f"""
        import sys
        import inklet
        from inklet.assets import asset
        node = asset({str(disc)!r}, width=18, lineart=True,
                     palette=True, cache_dir={str(cache)!r})
        fig = inklet.figure(width=60)
        fig.add(node)
        sys.stdout.write(fig.to_svg())
    """)
    runs = [subprocess.run([sys.executable, "-c", script], capture_output=True,
                           check=True, text=True).stdout for _ in range(2)]
    assert runs[0] == runs[1]
    assert len(runs[0]) > 500


def test_the_cache_is_reused_rather_than_rewritten(disc, cache):
    asset(disc, width=18, cache_dir=cache)
    stamps = {p: p.stat().st_mtime_ns for p in sorted(cache.iterdir())}
    assert stamps
    asset(disc, width=18, cache_dir=cache)
    assert {p: p.stat().st_mtime_ns for p in sorted(cache.iterdir())} == stamps


def test_the_cache_key_covers_the_parameters(disc, cache):
    asset(disc, width=18, cache_dir=cache)
    before = set(cache.iterdir())
    asset(disc, width=18, cutout=Cutout(tolerance=0.3), cache_dir=cache)
    assert set(cache.iterdir()) > before


# -- anchors --------------------------------------------------------------


def write_sidecar(image: Path, data: dict) -> Path:
    path = sidecar_path(image)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_anchors_come_from_the_sidecar(ell, cache):
    write_sidecar(ell, {"anchors": {"toe": [1.0, 1.0], "top": [0.0, 0.0]}})
    node = asset(ell, width=25, cache_dir=cache)
    assert node.anchor_point("toe") == Vec2(12.5, 15.0)
    assert node.anchor_point("top") == Vec2(-12.5, -15.0)


def test_anchors_are_fractions_of_the_subject_not_the_canvas(ell, cache):
    write_sidecar(ell, {"anchors": {"middle": [0.5, 0.5]}})
    node = asset(ell, width=25, cache_dir=cache)
    assert node.anchor_point("middle") == Vec2(0.0, 0.0)


def test_inline_anchors_win(ell, cache):
    write_sidecar(ell, {"anchors": {"toe": [1.0, 1.0]}})
    node = asset(ell, width=25, anchors={"toe": [0.0, 0.0]}, cache_dir=cache)
    assert node.anchor_point("toe") == Vec2(-12.5, -15.0)


def test_an_anchor_can_be_linked_to(ell, cache):
    write_sidecar(ell, {"anchors": {"toe": [1.0, 1.0]}})
    node = asset(ell, width=25, cache_dir=cache)
    target = inklet.box("x").translated(40, 40)
    tree = inklet.Diagram(children=(node, target))
    tip = route(link(node.at("toe"), target), resolve(tree)).anchor_point("start")
    assert tip == Vec2(12.5, 15.0)      # an anchor is used verbatim, not clipped


def test_a_broken_sidecar_is_reported(ell, cache):
    sidecar_path(ell).write_text("{ not json", encoding="utf-8")
    with pytest.raises(AssetError, match="sidecar"):
        asset(ell, width=25, cache_dir=cache)


def test_a_malformed_anchor_is_reported(ell, cache):
    write_sidecar(ell, {"anchors": {"toe": "over there"}})
    with pytest.raises(AssetError, match="two numbers"):
        asset(ell, width=25, cache_dir=cache)


def test_the_sidecar_can_be_ignored(ell, cache):
    write_sidecar(ell, {"anchors": {"toe": [1.0, 1.0]}})
    node = asset(ell, width=25, sidecar=False, cache_dir=cache)
    with pytest.raises(inklet.DiagramError):
        node.anchor_point("toe")


# -- provenance -----------------------------------------------------------


def test_provenance_records_the_source_and_a_content_hash(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    found = provenance_of(node)
    assert found.source == str(ell)
    assert len(found.sha256) == 64
    assert found.pixel_size == (ELL_CANVAS, ELL_CANVAS)
    assert found.subject_box == (ELL_X0, ELL_Y0,
                                 ELL_X0 + ELL_W - 1, ELL_Y0 + ELL_H - 1)


def test_provenance_records_the_transformation_chain(ell, cache):
    node = asset(ell, width=25, palette=0.5, lineart="raster", cache_dir=cache)
    chain = provenance_of(node).steps
    assert chain[0].startswith("cutout:")
    assert any(step.startswith("crop:") for step in chain)
    assert any(step.startswith("harmonise:") for step in chain)
    assert any(step.startswith("lineart:") for step in chain)
    assert any(step.startswith("outline:") for step in chain)


def test_no_licence_is_invented(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    found = provenance_of(node)
    assert found.license is None and found.attribution is None
    assert "no licence recorded" in found.credit()


def test_licence_comes_from_the_sidecar(ell, cache):
    write_sidecar(ell, {"license": "CC BY 4.0", "attribution": "R. Cajal"})
    node = asset(ell, width=25, cache_dir=cache)
    assert provenance_of(node).credit() == f"{ell}: R. Cajal, CC BY 4.0"


def test_arguments_override_the_sidecar(ell, cache):
    write_sidecar(ell, {"license": "CC BY 4.0"})
    node = asset(ell, width=25, license="CC0", cache_dir=cache)
    assert provenance_of(node).license == "CC0"


def test_credits_are_deduplicated_by_content(ell, disc, cache):
    tree = inklet.Diagram(children=(
        asset(ell, width=10, cache_dir=cache),
        asset(ell, width=20, cache_dir=cache),      # same file, different size
        asset(disc, width=10, cache_dir=cache),
    ))
    assert len(credits(tree)) == 2
    assert len(credit_lines(tree)) == 2


# -- line art -------------------------------------------------------------


def test_lineart_draws_strokes_in_theme_ink(disc, cache):
    node = asset(disc, width=20, lineart=True, cache_dir=cache)
    art = np.asarray(Image.open(node.prim.source).convert("RGBA"))
    ink = art[art[:, :, 3] == 255][:, :3]
    assert len(ink) > 50                     # there is line work
    assert (art[:, :, 3] == 0).mean() > 0.5  # and it is mostly transparent
    assert (ink == np.array(parse_color(inklet.current_theme().ink))).all()


def test_lineart_keeps_the_silhouette(disc, cache):
    photo = asset(disc, width=20, cache_dir=cache)
    drawn = asset(disc, width=20, lineart=True, cache_dir=cache)
    assert len(drawn.prim.outline) == len(photo.prim.outline)
    assert drawn.local_bbox.width == pytest.approx(photo.local_bbox.width)


def test_lineart_fill_occludes(disc, cache):
    node = asset(disc, width=20, lineart=LineArt(fill="#ffffff"), cache_dir=cache)
    art = np.asarray(Image.open(node.prim.source).convert("RGBA"))
    assert (art[:, :, 3] > 0).mean() > 0.5   # the body is painted, not just the edge


@pytest.mark.parametrize("tone", [0.05, 0.5, 0.95])
def test_xdog_leaves_a_flat_field_blank(tone):
    """Including a dark one: a black patch of fur is not an edge."""
    assert not xdog(np.full((64, 64), tone), LineArt(), sigma_px=1.0).any()


def test_xdog_inks_the_dark_side_of_an_edge():
    step = np.zeros((64, 64))
    step[:, 32:] = 1.0
    found = xdog(step, LineArt(), sigma_px=1.0)
    assert found.any()
    assert found[:, :24].sum() == 0 and found[:, 40:].sum() == 0
    assert found[:, 24:32].sum() > found[:, 32:40].sum()


def test_vector_lineart_says_how_to_get_potrace(disc, cache):
    if potrace_available():
        pytest.skip("potrace is installed; the raise is unreachable")
    with pytest.raises(AssetError, match="potrace"):
        asset(disc, width=20, lineart="vector", cache_dir=cache)


@pytest.mark.skipif(
    not potrace_available(),
    reason="potrace is not installed: apt install potrace, "
           "brew install potrace")
def test_vector_lineart_builds_paths(disc, cache):
    node = asset(disc, width=20, lineart="vector", cache_dir=cache)
    assert node.prim is None and node.children
    assert node.local_bbox.width == pytest.approx(20.0, abs=0.5)


# potrace's own SVG shape, for a 4x4 bitmap inked in its lower-left quarter.
# potrace works in a y-up frame at ten units per pixel, and states the flip in
# the group transform: internal y=0 is the *bottom* of the picture.
POTRACE_SVG = """<?xml version="1.0" standalone="no"?>
<svg version="1.0" xmlns="http://www.w3.org/2000/svg"
 width="4.000000pt" height="4.000000pt" viewBox="0 0 4.000000 4.000000"
 preserveAspectRatio="xMidYMid meet">
<g transform="translate(0.000000,4.000000) scale(0.010000,-0.010000)"
fill="#000000" stroke="none">
<path d="M0 0 l0 200 200 0 0 -200 -200 0z"/>
</g>
</svg>
"""


def test_potrace_output_is_placed_the_right_way_up():
    """The flip has to be read out of potrace's own transform, not assumed."""
    subpaths = parse_potrace_svg(POTRACE_SVG, 4, 4, width=8.0, height=8.0)
    assert len(subpaths) == 1
    xs = [p.x for p in subpaths[0].points]
    ys = [p.y for p in subpaths[0].points]
    # Ink in potrace's lower-left is ink in the lower-left of an 8x8 mm frame
    # centred on the origin -- which, with y downward, is positive y.
    assert (min(xs), max(xs)) == pytest.approx((-4.0, 0.0))
    assert (min(ys), max(ys)) == pytest.approx((0.0, 4.0))


# -- palette harmonisation ------------------------------------------------


def test_harmonisation_is_off_by_default(disc, cache):
    plain = asset(disc, width=20, cache_dir=cache)
    body = np.asarray(Image.open(plain.prim.source).convert("RGBA"))
    core = body[body[:, :, 3] == 255][:, :3]
    assert (core == (200, 40, 40)).all()


def test_harmonisation_moves_hue_and_keeps_lightness(disc, cache):
    from inklet.themes.color import to_lab

    plain = asset(disc, width=20, cache_dir=cache)
    tuned = asset(disc, width=20, palette=1.0, cache_dir=cache)

    before = np.asarray(Image.open(plain.prim.source).convert("RGBA"))
    after = np.asarray(Image.open(tuned.prim.source).convert("RGBA"))
    solid = before[:, :, 3] == 255

    was = tuple(int(v) for v in before[solid][0][:3])
    now = tuple(int(v) for v in after[solid][0][:3])
    assert was != now

    lab_before, lab_after = to_lab(was), to_lab(now)
    assert lab_after[0] == pytest.approx(lab_before[0], abs=1.0)   # L* preserved

    # The hue has landed on a palette swatch, to within the rounding that
    # getting back into 8-bit channels costs.
    swatches = [math.atan2(s[2], s[1]) for s in map(to_lab, inklet.current_theme().palette)]
    moved_to = min(abs(math.atan2(lab_after[2], lab_after[1]) - h) for h in swatches)
    came_from = min(abs(math.atan2(lab_before[2], lab_before[1]) - h) for h in swatches)
    assert moved_to < 0.06
    assert moved_to < came_from


def test_strength_zero_changes_nothing(disc, cache):
    plain = asset(disc, width=20, cache_dir=cache)
    tuned = asset(disc, width=20, palette=Harmonise(strength=0.0), cache_dir=cache)
    before = np.asarray(Image.open(plain.prim.source).convert("RGBA"))
    after = np.asarray(Image.open(tuned.prim.source).convert("RGBA"))
    assert (before == after).all()


def test_an_explicit_palette_is_used(disc, cache):
    node = asset(disc, width=20, palette=["#0000ff"], palette_strength=1.0,
                 cache_dir=cache)
    art = np.asarray(Image.open(node.prim.source).convert("RGBA"))
    core = art[art[:, :, 3] == 255][0][:3]
    assert core[2] > core[0]     # the red disc now leans blue


# -- failure modes --------------------------------------------------------


def test_a_missing_file_is_named(tmp_path, cache):
    with pytest.raises(AssetError, match="no such image"):
        asset(tmp_path / "absent.png", width=10, cache_dir=cache)


def test_a_corrupt_file_is_reported_as_such(tmp_path, cache):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage" * 20)
    with pytest.raises(AssetError, match="cannot decode"):
        asset(broken, width=10, cache_dir=cache)


def test_a_directory_is_not_an_image(tmp_path, cache):
    with pytest.raises(AssetError, match="no such image"):
        asset(tmp_path, width=10, cache_dir=cache)


def test_an_unknown_cutout_backend_lists_the_known_ones(ell, cache):
    with pytest.raises(AssetError, match="known backends"):
        asset(ell, width=10, cutout="magic", cache_dir=cache)


def test_a_bare_callable_cutout_is_refused(ell, cache):
    with pytest.raises(AssetError, match="register_cutout"):
        asset(ell, width=10, cutout=lambda rgba, spec: None, cache_dir=cache)


def test_a_registered_backend_can_be_used(ell, cache):
    def top_half(rgba, spec):
        alpha = np.zeros(rgba.shape[:2], dtype=np.uint8)
        alpha[: rgba.shape[0] // 2, :] = 255
        return alpha

    register_cutout("test-top-half", top_half)
    assert "test-top-half" in cutout_backends()
    node = asset(ell, width=20, cutout="test-top-half", cache_dir=cache)
    assert node.prim.pixel_size == (ELL_CANVAS, ELL_CANVAS // 2)


def test_a_missing_optional_dependency_names_the_extra():
    with pytest.raises(MissingDependency, match=r"inklet\[images\]"):
        require("a_module_that_is_not_installed")


# -- integration with the rest of the library ------------------------------


def test_the_linter_sees_the_asset_resolution(disc, cache):
    node = asset(disc, width=40, cache_dir=cache)
    fig = inklet.figure(width=60)
    fig.add(node)
    codes = {d.code for d in fig.lint()}
    assert "LOW_DPI" in codes      # 119 px over 40 mm is 76 dpi


def test_a_stack_packs_against_the_silhouette(disc, cache):
    node = asset(disc, width=20, cache_dir=cache)
    stacked = inklet.hstack([node, inklet.box("V1")], gap=0)
    assert stacked.width < 20 + inklet.box("V1").width + 1e-6


def test_the_asset_survives_a_transform(ell, cache):
    node = asset(ell, width=25, cache_dir=cache)
    turned = node.rotated(90)
    box = turned.bbox
    assert (box.width, box.height) == pytest.approx((30.0, 25.0), abs=1e-6)
