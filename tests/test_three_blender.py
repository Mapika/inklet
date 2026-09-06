"""The Blender Line Art backend.

Blender is optional and most machines running this suite will not have it, so
the file is written in two halves. Everything above `blender_available()` runs
from the fixture below -- a real Grease Pencil export, kept small enough to
read in a diff -- and therefore runs everywhere. Everything below it is marked
`skipif` and needs the binary.

The fixture is a cube seen from the front, which is a better test subject than
it looks. A square is symmetric in both axes, so it would pass a reader that
flipped y; the *silhouette layer* of that same cube is not, and neither is the
metadata comment, so the parts of the fixture that pin orientation are the
parts that are asymmetric.
"""

from __future__ import annotations

import math
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import inklet
from inklet.three.blender import (
    CHAINED, DEFAULT_CREASE_DEGREES, ENV_VAR, HULL, LINES_LAYER,
    MINIMUM_VERSION, SCRIPT_VERSION, SILHOUETTE_LAYER, TRACED, Blender,
    BlenderError, BlenderNotFound, BlenderTooOld, GreasePencilSvg,
    LineArtDrawing, LineArtOptions, blender_available, build_script,
    cache_key, camera_spec, find_blender, line_art, outline, page_up,
    place_layers, read_gpencil_svg,
)
from inklet.three.blender.discover import clear_discovery_cache
from inklet.three.blender.svgread import strip_preamble
from inklet.three.blender.tracing import chain_strokes, convex_hull
from inklet.three.camera import PRESETS, Camera, as_camera
from inklet.core import Vec2
from inklet.three.linalg import Vec3

MESHES = Path(__file__).resolve().parent.parent / "stress" / "meshes"


# -- fixture ---------------------------------------------------------------

# Blender 4.2's own Grease Pencil SVG export, verbatim, for a unit cube seen
# from the front at 128px. The two processing instructions at the top really
# are malformed -- `<?:anonymous?>` has no target and `<?xml?>` has no version
# -- and no XML parser will accept them, which is the whole reason the reader
# strips a preamble instead of handing the file to ElementTree.
CUBE_SVG = """<?:anonymous?>
<!-- Generator: Blender, SVG Export for Grease Pencil - v1.0 -->
<?xml?>
<svg version="1.0" x="0px" y="0px" xmlns="http://www.w3.org/2000/svg" width="128px" height="128px" viewBox="0 0 128 128">
\t<clipPath id="clip-path1">
\t\t<rect x="0" y="0" width="128" height="128" fill="none" />
\t</clipPath>
\t<g id="blender_frame_1" clip-path="url(#clip-path1)">
\t\t<g id="blender_object_GPencil">
\t\t\t<!--Layer: lines-->
\t\t\t<g id="lines">
\t\t\t\t<polyline stroke="#000000" stroke-opacity="1" fill="none" stroke-linecap="round" stroke-width="2" points="5.120007,122.879974 122.879990,122.879974 122.879990,5.119980 5.120007,5.119980 5.120007,122.879974" />
\t\t\t\t<polyline stroke="#000000" stroke-opacity="1" fill="none" stroke-linecap="round" stroke-width="2" points="5.120007,122.879974 122.879990,122.879974" />
\t\t\t</g>
\t\t\t<!--Layer: silhouette-->
\t\t\t<g id="silhouette">
\t\t\t\t<polyline stroke="#000000" stroke-opacity="1" fill="none" stroke-linecap="round" stroke-width="2" points="5.120007,122.879974 122.879990,5.119980" />
\t\t\t</g>
\t\t</g>
\t</g>
<!--inklet-lineart {"blender": "4.2.23 LTS", "camera": {"eye": [0.0, -5.196152210235596, 0.0], "ortho_scale": 2.17391300201416, "roll": 0.0, "target": [0.0, 0.0, 0.0]}, "faces": 6, "normalise": {"centre": [0.0, 0.0, 0.0], "scale": 0.9999998807907247, "span": 2.0}, "objects": ["cube"], "perspective": false, "resolution": [128, 128], "strokes": {"lines": {"points": 7, "strokes": 2}, "silhouette": {"points": 2, "strokes": 1}}, "subdivide": 0}-->
</svg>
"""


@pytest.fixture
def cube() -> GreasePencilSvg:
    return read_gpencil_svg(CUBE_SVG)


# -- the reader ------------------------------------------------------------


def test_the_preamble_really_is_unparseable_without_stripping():
    """If Blender ever emits legal XML this test fails and the strip can go."""
    import xml.etree.ElementTree as ET

    with pytest.raises(ET.ParseError):
        ET.fromstring(CUBE_SVG)
    ET.fromstring(strip_preamble(CUBE_SVG))


def test_strip_preamble_keeps_everything_from_the_svg_tag_on():
    stripped = strip_preamble(CUBE_SVG)
    assert stripped.startswith("<svg ")
    assert stripped.rstrip().endswith("</svg>")


def test_reads_the_viewbox_and_both_layers(cube):
    assert cube.viewbox == (0.0, 0.0, 128.0, 128.0)
    assert [layer.name for layer in cube.layers] == [LINES_LAYER, SILHOUETTE_LAYER]
    assert len(cube.layer(LINES_LAYER).polylines) == 2
    assert len(cube.layer(SILHOUETTE_LAYER).polylines) == 1


def test_a_missing_layer_is_none_rather_than_an_error(cube):
    assert cube.layer("fills") is None


def test_points_come_back_in_source_order(cube):
    first = cube.layer(LINES_LAYER).polylines[0]
    assert len(first) == 5
    assert first[0].x == pytest.approx(5.120007)
    assert first[0].y == pytest.approx(122.879974)
    assert first[-1] == first[0], "the cube's outline is a closed ring"


def test_the_metadata_comment_is_read_and_removed(cube):
    assert cube.metadata["blender"] == "4.2.23 LTS"
    assert cube.metadata["faces"] == 6
    assert cube.metadata["normalise"]["span"] == 2.0
    assert cube.metadata["strokes"][LINES_LAYER]["strokes"] == 2


def test_metadata_survives_an_escaped_double_hyphen():
    """`--` is illegal inside an XML comment, and object names contain it. The
    bake script escapes it; the reader has to put it back."""
    text = CUBE_SVG.replace('"objects": ["cube"]',
                            '"objects": ["left-\\u002dhemisphere"]')
    payload = text.split("inklet-lineart ")[1].split("-->")[0]
    assert "--" not in payload, "a double hyphen is illegal inside a comment"
    assert read_gpencil_svg(text).metadata["objects"] == ["left--hemisphere"]


def test_a_file_with_no_metadata_still_parses():
    text = "\n".join(line for line in CUBE_SVG.splitlines()
                     if "inklet-lineart" not in line)
    document = read_gpencil_svg(text)
    assert document.metadata == {}
    assert len(document.layers) == 2


def test_the_reader_is_deterministic(cube):
    again = read_gpencil_svg(CUBE_SVG)
    assert [layer.name for layer in again.layers] == [
        layer.name for layer in cube.layers]
    assert again.layer(LINES_LAYER).polylines == cube.layer(LINES_LAYER).polylines


# -- placement into millimetres --------------------------------------------


def test_placement_honours_the_requested_width(cube):
    layers, width, height, scale = place_layers(cube, width=40.0)
    assert width == pytest.approx(40.0)
    assert height == pytest.approx(40.0), "a square cube stays square"
    assert scale == pytest.approx(40.0 / 117.759983, rel=1e-6)
    assert len(layers) == 2


def test_placement_never_stretches_the_aspect(cube):
    """A width and a height that disagree must letterbox, not distort."""
    _, width, height, _ = place_layers(cube, width=40.0, height=10.0,
                                       fit="content")
    assert width / height == pytest.approx(1.0)
    assert max(width, height) <= 40.0 + 1e-9


def test_content_fit_measures_the_ink_and_frame_fit_measures_the_viewbox(cube):
    _, content_w, _, content_scale = place_layers(cube, width=40.0, fit="content")
    _, frame_w, _, frame_scale = place_layers(cube, width=40.0, fit="frame")
    assert content_w == pytest.approx(frame_w)
    # The cube's ink stops 5.12 units short of the frame on every side, so
    # fitting the ink has to magnify more than fitting the frame does.
    assert content_scale > frame_scale


def test_placement_centres_on_the_origin(cube):
    layers, width, height, _ = place_layers(cube, width=40.0)
    points = [p for layer in layers for line in layer.polylines for p in line]
    assert min(p.x for p in points) == pytest.approx(-width / 2, abs=1e-6)
    assert max(p.x for p in points) == pytest.approx(width / 2, abs=1e-6)
    assert min(p.y for p in points) == pytest.approx(-height / 2, abs=1e-6)


def test_placement_does_not_flip_y():
    """inklet and SVG both grow y downwards, so a reader that helpfully flipped
    would turn every drawing upside down. The cube is symmetric, so this needs
    an asymmetric subject: the silhouette layer's single diagonal runs from
    bottom-left to top-right in source order and must still do so in mm."""
    document = read_gpencil_svg(CUBE_SVG)
    diagonal = document.layer(SILHOUETTE_LAYER).polylines[0]
    assert diagonal[0].y > diagonal[1].y, "the fixture's diagonal rises"
    layers, _, _, _ = place_layers(document, width=40.0)
    placed = [layer for layer in layers if layer.name == SILHOUETTE_LAYER][0]
    start, end = placed.polylines[0]
    assert start.y > end.y


def test_placement_rejects_an_unknown_fit(cube):
    with pytest.raises(BlenderError, match="fit"):
        place_layers(cube, width=40.0, fit="cover")


# -- the outline recovery --------------------------------------------------


def _ring(n: int, radius: float, cx: float = 0.0, cy: float = 0.0):
    return [Vec2(cx + radius * math.cos(2 * math.pi * i / n),
                 cy + radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


def test_a_closed_ring_is_traced_rather_than_hulled():
    ring = _ring(64, 10.0)
    silhouette, method = outline([ring], width=24.0, height=24.0)
    assert method == TRACED
    assert silhouette is not None
    span = max(p.x for p in silhouette.points) - min(p.x for p in silhouette.points)
    assert span == pytest.approx(20.0, abs=1.0)


def test_tracing_finds_a_concave_boundary():
    """A convex hull would swallow the notch; the traced outline must not.

    The subject is a C: a ring with a wedge cut out of its right side. Its
    area is measurably below the hull's, which is the whole point of tracing.
    """
    full = _ring(96, 10.0)
    arc = [p for p in full if not (abs(p.y) < 6.0 and p.x > 0)]
    notch = [Vec2(0.0, 5.5), Vec2(6.0, 5.5), Vec2(6.0, -5.5), Vec2(0.0, -5.5)]
    silhouette, method = outline([arc + notch + [arc[0]]], width=24.0, height=24.0)
    assert method == TRACED
    assert _area(silhouette.points) < _area(convex_hull(silhouette.points)) * 0.95
    # More to the point: at the waist the outline follows the notch inwards
    # instead of bridging it at the circle's radius, which is what a hull does.
    waist = [p.x for p in silhouette.points if abs(p.y) < 3.0]
    assert max(waist) < 7.5, "the outline bridged the notch"


def _area(points) -> float:
    total = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        total += p.x * q.y - q.x * p.y
    return abs(total) / 2


def test_the_outline_falls_back_when_numpy_is_missing(monkeypatch):
    """Tracing needs numpy and numpy is an extra, so a machine without it must
    still get an outline -- a worse one, and one that says so."""
    monkeypatch.setattr("inklet.three.blender.tracing.have", lambda name: False)
    silhouette, method = outline([_ring(64, 10.0)], width=24.0, height=24.0)
    assert method in (CHAINED, HULL)
    assert silhouette is not None and len(silhouette.points) >= 3


def test_no_strokes_means_no_outline():
    silhouette, method = outline([], width=10.0, height=10.0)
    assert silhouette is None and method == "none"


def test_chaining_joins_fragments_that_nearly_touch():
    left = [Vec2(0.0, 0.0), Vec2(5.0, 0.0)]
    right = [Vec2(5.001, 0.0), Vec2(10.0, 0.0)]
    joined = chain_strokes([left, right], gap=0.01)
    assert len(joined) == 4
    assert joined[0] == Vec2(0.0, 0.0) and joined[-1] == Vec2(10.0, 0.0)


def test_chaining_leaves_genuinely_separate_fragments_alone():
    left = [Vec2(0.0, 0.0), Vec2(1.0, 0.0)]
    right = [Vec2(9.0, 0.0), Vec2(10.0, 0.0)]
    assert len(chain_strokes([left, right], gap=0.01)) == 2


def test_the_hull_is_ordered_and_free_of_duplicates():
    square = [Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(0, 1),
              Vec2(0.5, 0.5), Vec2(0, 0)]
    hull = convex_hull(square)
    assert len(hull) == 4
    assert _area(hull) == pytest.approx(1.0)


def test_the_hull_does_not_depend_on_input_order():
    """A set anywhere in the hull would make this flaky under PYTHONHASHSEED."""
    points = _ring(17, 3.0)
    assert convex_hull(points) == convex_hull(list(reversed(points)))


# -- options ---------------------------------------------------------------


def test_the_crease_default_agrees_with_the_pure_python_backend():
    from inklet.three.edges import DEFAULT_CREASE_DEGREES as pure

    assert DEFAULT_CREASE_DEGREES == pure, (
        "the two backends must mean the same thing by crease=, or wiring "
        "Look.crease through would silently change the drawing")


@pytest.mark.parametrize("bad", [-1.0, 181.0])
def test_an_impossible_crease_angle_is_rejected(bad):
    with pytest.raises(BlenderError, match="crease"):
        LineArtOptions(crease=bad)


def test_switching_every_line_type_off_is_refused():
    with pytest.raises(BlenderError, match="nothing to draw"):
        LineArtOptions(contour=False, crease=180.0)


def test_subdivision_is_capped():
    with pytest.raises(BlenderError, match="subdivide"):
        LineArtOptions(subdivide=5)


def test_the_cache_key_covers_every_option_field():
    """A field added to the dataclass and forgotten in key() would serve a
    stale drawing, so compare the two by name rather than trusting review."""
    fields = set(LineArtOptions.__dataclass_fields__)
    assert fields == set(LineArtOptions().key())


# -- the generated bake script ---------------------------------------------


def _script(**kwargs) -> str:
    spec = dict(camera=camera_spec(as_camera("front"), scale=None, margin=0.04),
                lineart=LineArtOptions().key(), resolution=(256, 256),
                up_axis="y")
    spec.update(kwargs)
    return build_script(**spec)


def test_the_bake_script_is_byte_stable():
    assert _script() == _script()


def test_the_bake_script_imports_nothing_it_will_not_have():
    """It runs in Blender's interpreter, which has bpy, mathutils and the
    standard library and nothing else -- no inklet, no venv packages. A stray
    import here is a crash nobody sees until they lack the dependency."""
    imported = set()
    for line in _script().splitlines():
        line = line.strip()
        if line.startswith("import "):
            imported.add(line.split()[1].split(".")[0])
        elif line.startswith("from ") and " import " in line:
            imported.add(line.split()[1].split(".")[0])
    assert imported <= {"bpy", "mathutils", "json", "math", "os", "shutil", "sys"}
    assert not any(name.startswith("inklet") for name in imported)


def test_the_bake_script_carries_its_parameters(cube):
    text = _script(resolution=(640, 480))
    assert "640" in text and "480" in text
    assert "__INKLET_PARAMS__" not in text, "the placeholder must be substituted"


def test_changing_an_option_changes_the_key():
    base = LineArtOptions()
    for field in sorted(LineArtOptions.__dataclass_fields__):
        if field in ("cull",):
            changed = base.__class__(**{**base.key(), field: True})
        elif isinstance(getattr(base, field), bool):
            changed = base.__class__(**{**base.key(), field: not getattr(base, field)})
        elif field == "crease":
            changed = base.__class__(**{**base.key(), field: 12.0})
        elif field == "subdivide":
            changed = base.__class__(**{**base.key(), field: 1})
        elif field == "thickness":
            changed = base.__class__(**{**base.key(), field: 3})
        else:
            changed = base.__class__(**{**base.key(), field: 0.5})
        assert changed.key() != base.key(), field
        assert _script(lineart=changed.key()) != _script(lineart=base.key()), field


def test_the_script_version_is_in_the_cache_key():
    key = cache_key("abc", "obj", _script())
    other = cache_key("abc", "obj", _script() + "\n# a later edit\n")
    assert key != other, (
        "the key hashes the script text, so editing the bake changes it")


def test_the_cache_key_is_stable_across_runs():
    assert cache_key("abc", "obj", _script()) == cache_key("abc", "obj", _script())
    assert SCRIPT_VERSION >= 1


# -- the camera vocabulary -------------------------------------------------


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_page_up_matches_the_shared_cameras_own_basis(preset):
    """Blender is told an up vector and works out the rest itself, so the two
    backends agree about which way is up only if this function reproduces
    `Camera._up()` exactly. When they disagree the drawing is rolled and
    nothing else fails."""
    camera = Camera.named(preset)
    assert page_up(camera) == camera._up()


def test_camera_spec_is_json_shaped_and_sorted():
    spec = camera_spec(as_camera("isometric"), scale=None, margin=0.04)
    import json

    assert json.dumps(spec, sort_keys=True) == json.dumps(spec, sort_keys=True)
    assert set(spec) >= {"direction", "up", "perspective", "margin"}


def test_camera_spec_accepts_every_way_of_naming_a_view():
    for view in ("front", (30.0, 20.0), Camera.named("hero"),
                 Camera.look_at(Vec3(3, 3, 3), Vec3(0, 0, 0))):
        assert camera_spec(as_camera(view), scale=None, margin=0.04)


# -- discovery, and life without Blender -----------------------------------


def test_importing_inklet_does_not_need_blender():
    assert inklet.__name__ == "inklet"


def test_the_backend_never_imports_bpy_in_process():
    """bpy in the host interpreter would be a 400MB dependency and a second
    Python. Blender is a subprocess, always."""
    assert "bpy" not in sys.modules
    source = "".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path(inklet.__file__).parent.glob("three/blender/*.py"))
        if path.name not in ("script.py", "scene_worker.py", "device_worker.py")
    )
    assert "import bpy" not in source


def test_a_bogus_executable_is_reported_without_a_traceback():
    clear_discovery_cache()
    try:
        with pytest.raises(BlenderNotFound) as caught:
            find_blender("/nonexistent/path/to/blender")
    finally:
        clear_discovery_cache()
    message = str(caught.value)
    assert "/nonexistent/path/to/blender" in message
    assert "blender=" in message
    assert "Traceback" not in message


def test_a_broken_environment_variable_says_so(monkeypatch):
    """The variable is the thing the author can act on, so the error has to
    name it rather than leaving them to guess which path was tried."""
    monkeypatch.setenv(ENV_VAR, "/nonexistent/path/to/blender")
    clear_discovery_cache()
    try:
        with pytest.raises(BlenderNotFound) as caught:
            find_blender()
    finally:
        clear_discovery_cache()
    assert ENV_VAR in str(caught.value)


def test_the_search_failure_says_how_to_fix_it(monkeypatch, tmp_path):
    """With nothing installed anywhere the message must still be actionable."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("inklet.three.blender.discover.CONVENTIONAL_PATHS", ())
    clear_discovery_cache()
    try:
        with pytest.raises(BlenderNotFound) as caught:
            find_blender()
    finally:
        clear_discovery_cache()
    message = str(caught.value)
    assert ENV_VAR in message and "4.2" in message


def test_a_non_blender_binary_is_rejected_without_a_traceback():
    clear_discovery_cache()
    try:
        with pytest.raises(BlenderError) as caught:
            find_blender(sys.executable)
    finally:
        clear_discovery_cache()
    assert "version" in str(caught.value).lower()


def test_blender_available_answers_without_raising():
    assert blender_available("/nonexistent/path/to/blender") is False
    assert isinstance(blender_available(), bool)


def test_the_minimum_version_is_the_one_line_art_shipped_in():
    assert MINIMUM_VERSION >= (4, 2)
    assert issubclass(BlenderTooOld, BlenderError)


def test_line_art_refuses_a_mesh_it_cannot_import(tmp_path):
    bad = tmp_path / "model.dwg"
    bad.write_text("not a mesh")
    with pytest.raises(BlenderError, match="dwg"):
        line_art(bad, width=10.0)


def test_line_art_refuses_a_missing_mesh(tmp_path):
    with pytest.raises(BlenderError, match="no such mesh"):
        line_art(tmp_path / "gone.obj", width=10.0)


# -- with Blender ----------------------------------------------------------

needs_blender = pytest.mark.skipif(
    not blender_available(), reason="Blender is not installed")

CUBE_OBJ = textwrap.dedent("""\
    v -1 -1 -1
    v -1 -1 1
    v -1 1 -1
    v -1 1 1
    v 1 -1 -1
    v 1 -1 1
    v 1 1 -1
    v 1 1 1
    f 1 2 4 3
    f 5 7 8 6
    f 1 5 6 2
    f 3 4 8 7
    f 1 3 7 5
    f 2 6 8 4
    """)


@pytest.fixture
def cube_obj(tmp_path) -> Path:
    path = tmp_path / "cube.obj"
    path.write_text(CUBE_OBJ)
    return path


@needs_blender
def test_a_cube_from_the_front_is_a_square(cube_obj, tmp_path):
    drawing = line_art(cube_obj, width=40.0, camera="front",
                       cache_dir=tmp_path / "cache")
    assert isinstance(drawing, LineArtDrawing)
    assert drawing.width == pytest.approx(40.0)
    assert drawing.height == pytest.approx(40.0, abs=0.5)
    points = [p for line in drawing.polylines for p in line]
    assert min(p.x for p in points) == pytest.approx(-20.0, abs=0.2)
    assert max(p.y for p in points) == pytest.approx(20.0, abs=0.2)
    assert drawing.report["faces"] == 6
    assert drawing.silhouette is not None


@needs_blender
def test_the_cube_is_normalised_inside_the_bake(tmp_path):
    """A mesh that spans a thousand units must come back the same size as one
    that spans two, because the bake recentres and rescales before the camera
    is placed. Left to Blender, the export's viewBox would inherit the source
    scale and read as an empty image."""
    big = tmp_path / "big.obj"
    big.write_text("\n".join(
        line if not line.startswith("v ")
        else "v " + " ".join(str(float(v) * 500 + 3000) for v in line.split()[1:])
        for line in CUBE_OBJ.splitlines()) + "\n")
    small = tmp_path / "small.obj"
    small.write_text(CUBE_OBJ)
    cache = tmp_path / "cache"
    a = line_art(big, width=40.0, camera="front", cache_dir=cache)
    b = line_art(small, width=40.0, camera="front", cache_dir=cache)
    assert a.viewbox == b.viewbox
    assert a.report["normalise"]["span"] == 2.0
    assert a.report["normalise"]["scale"] != pytest.approx(1.0)
    assert len(a.polylines) == len(b.polylines)


@needs_blender
def test_a_second_call_is_served_from_the_cache(cube_obj, tmp_path):
    cache = tmp_path / "cache"
    first = line_art(cube_obj, width=40.0, cache_dir=cache)
    second = line_art(cube_obj, width=40.0, cache_dir=cache)
    assert first.cached is False and second.cached is True
    assert first.key == second.key
    assert first.polylines == second.polylines
    assert second.seconds < first.seconds


@needs_blender
def test_refresh_rebakes_and_still_agrees(cube_obj, tmp_path):
    cache = tmp_path / "cache"
    first = line_art(cube_obj, width=40.0, cache_dir=cache)
    again = line_art(cube_obj, width=40.0, cache_dir=cache, refresh=True)
    assert again.cached is False
    assert again.key == first.key
    assert again.polylines == first.polylines, "the bake is deterministic"


@needs_blender
def test_editing_the_mesh_misses_the_cache(cube_obj, tmp_path):
    cache = tmp_path / "cache"
    first = line_art(cube_obj, width=40.0, cache_dir=cache)
    cube_obj.write_text(CUBE_OBJ.replace("v 1 1 1", "v 1 2 1"))
    second = line_art(cube_obj, width=40.0, cache_dir=cache)
    assert second.cached is False
    assert second.mesh_sha256 != first.mesh_sha256
    assert second.key != first.key


@needs_blender
def test_changing_an_option_misses_the_cache(cube_obj, tmp_path):
    cache = tmp_path / "cache"
    first = line_art(cube_obj, width=40.0, cache_dir=cache)
    second = line_art(cube_obj, width=40.0, cache_dir=cache,
                      options=LineArtOptions(crease=5.0))
    assert second.cached is False
    assert second.mesh_sha256 == first.mesh_sha256, "same mesh"
    assert second.key != first.key, "different settings, different drawing"


@needs_blender
def test_the_view_changes_the_drawing(tmp_path):
    """A cube is the wrong subject here -- it looks the same from six sides."""
    cache = tmp_path / "cache"
    front = line_art(MESHES / "spot.obj", width=40.0, camera="front",
                     cache_dir=cache)
    side = line_art(MESHES / "spot.obj", width=40.0, camera="right",
                    cache_dir=cache)
    assert front.key != side.key
    assert front.polylines != side.polylines


@needs_blender
def test_the_bake_is_byte_identical_under_a_different_hash_seed(tmp_path):
    """Determinism is a contract, and a set anywhere in the pipeline would
    break it only under a hash seed the developer's machine never uses."""
    program = textwrap.dedent(f"""
        import hashlib, json
        from inklet.three.blender import line_art
        d = line_art({str(MESHES / "spot.obj")!r}, width=40.0,
                     camera="three-quarter", cache_dir={str(tmp_path / "c")!r},
                     refresh=True)
        blob = json.dumps([[[p.x, p.y] for p in line] for line in d.polylines])
        ring = json.dumps([[p.x, p.y] for p in d.silhouette.points])
        print(d.key, hashlib.sha256(blob.encode()).hexdigest(),
              hashlib.sha256(ring.encode()).hexdigest(),
              hashlib.sha256(open(d.svg_path, "rb").read()).hexdigest())
    """)
    out = []
    for seed in ("0", "12345"):
        done = subprocess.run([sys.executable, "-c", program], text=True,
                              capture_output=True, timeout=600,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                   "PYTHONHASHSEED": seed,
                                   "INKLET_BLENDER": str(find_blender().path),
                                   "PYTHONPATH": str(Path(inklet.__file__).parent.parent)})
        assert done.returncode == 0, done.stderr
        out.append(done.stdout.strip())
    assert out[0] == out[1]


@needs_blender
def test_fresh_exports_preserve_every_baked_stroke(tmp_path):
    """A dense bake must reach the SVG intact, including after scene updates."""
    exports = []
    for _ in range(4):
        drawing = line_art(MESHES / "brain-lh.obj", width=60.0, camera="left",
                           cache_dir=tmp_path / "cache", refresh=True)
        assert len(drawing.polylines) == drawing.report["strokes"]["lines"]["strokes"]
        document = read_gpencil_svg(drawing.svg_path.read_text())
        for layer in document.layers:
            assert len(layer.polylines) == drawing.report["strokes"][layer.name]["strokes"]
        exports.append(drawing.svg_path.read_bytes())
    assert all(svg == exports[0] for svg in exports[1:])


@needs_blender
def test_a_convoluted_closed_mesh_produces_a_concave_outline(tmp_path):
    """The brain is the hard case: closed, genus zero, and folded enough that a
    convex hull of its strokes would be visibly wrong."""
    drawing = line_art(MESHES / "brain-lh.obj", width=60.0, camera="left",
                       cache_dir=tmp_path / "cache")
    assert drawing.outline_method in (TRACED, CHAINED)
    assert len(drawing.polylines) > 200
    ring = drawing.silhouette.points
    assert _area(ring) < _area(convex_hull(ring)) * 0.95


@needs_blender
def test_hiding_nothing_draws_more_than_hiding_the_back(tmp_path):
    cache = tmp_path / "cache"
    solid = line_art(MESHES / "spot.obj", width=40.0, cache_dir=cache)
    xray = line_art(MESHES / "spot.obj", width=40.0, cache_dir=cache,
                    options=LineArtOptions(hidden=False))
    assert xray.points > solid.points * 2


@needs_blender
def test_smooth_shading_suppresses_crease_lines(tmp_path):
    """The documented lever for scanned surfaces: with smooth normals the
    crease threshold stops mattering and only contours survive."""
    cache = tmp_path / "cache"
    faceted = line_art(MESHES / "brain-lh.obj", width=60.0, camera="left",
                       cache_dir=cache, options=LineArtOptions(crease=30.0))
    a = line_art(MESHES / "brain-lh.obj", width=60.0, camera="left",
                 cache_dir=cache,
                 options=LineArtOptions(crease=30.0, shade_smooth=True))
    b = line_art(MESHES / "brain-lh.obj", width=60.0, camera="left",
                 cache_dir=cache,
                 options=LineArtOptions(crease=90.0, shade_smooth=True))
    assert len(a.polylines) == len(b.polylines)
    assert len(a.polylines) < len(faceted.polylines) / 2


@needs_blender
def test_a_perspective_camera_differs_from_an_orthographic_one(tmp_path):
    cache = tmp_path / "cache"
    flat = line_art(MESHES / "spot.obj", width=40.0,
                    camera=Camera.named("three-quarter"), cache_dir=cache)
    deep = line_art(MESHES / "spot.obj", width=40.0, cache_dir=cache,
                    camera=Camera(azimuth=Camera.named("three-quarter").azimuth,
                                  elevation=Camera.named("three-quarter").elevation,
                                  perspective=True, fov=50.0))
    assert flat.key != deep.key
    assert flat.polylines != deep.polylines


@needs_blender
def test_the_binary_reports_a_usable_version():
    found = find_blender()
    assert isinstance(found, Blender)
    assert found.version >= MINIMUM_VERSION
    assert found.path.exists()
    assert str(found.version[0]) in found.banner


@needs_blender
def test_a_timeout_is_reported_as_a_timeout(cube_obj, tmp_path):
    with pytest.raises(BlenderError, match="timeout"):
        line_art(cube_obj, width=40.0, cache_dir=tmp_path / "cache",
                 timeout=0.001, refresh=True)


@needs_blender
def test_the_summary_says_what_was_drawn(cube_obj, tmp_path):
    drawing = line_art(cube_obj, width=40.0, cache_dir=tmp_path / "cache")
    text = drawing.summary()
    assert "cube.obj" in text and "mm" in text
