"""The join: `inklet.model(..., backend="blender")`.

The registry and the bake were written by different hands and never saw each
other. What has to hold between them is not that the two renderers agree
stroke for stroke -- they will not, and should not -- but that they agree about
*where the model is*, so an arrow aimed at a 3D landmark lands on the ink
whichever one drew it.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.three import solids
from inklet.three.backend import Look, Rendering, Request, available_backends, backends
from inklet.three.blender_backend import (
    SUPPORTED_STYLES, _mesh_obj, _obj_text, _projected_box, align_error,
    render_with_blender,
)
from inklet.three.camera import as_camera
from inklet.three.mesh import MeshError

#: The thinnest line a journal will print is 0.088mm. Half of that is the
#: honest bound on "the two framings disagree by nothing you could see": the
#: measured worst case across cube, sphere and brain at three views is 0.024mm.
MAX_ALIGN_MM = 0.044

needs_blender = pytest.mark.skipif(
    "blender" not in available_backends(), reason="Blender is not installed")


def test_the_backend_is_registered_without_importing_blender():
    """Registration must not drag Blender's own package in behind it.

    In a subprocess because this module has already asked `available_backends`
    whether Blender is here, and that question loads it.
    """
    import subprocess
    import sys

    probe = subprocess.run(
        [sys.executable, "-c",
         "import inklet, sys;"
         "print('blender' in inklet.three.backends(),"
         " 'inklet.three.blender' in sys.modules)"],
        capture_output=True, text=True, check=True)

    assert probe.stdout.split() == ["True", "False"]


def test_a_mesh_serialises_the_same_way_twice():
    cube = solids.cube()

    body = _obj_text(cube)
    assert body == _obj_text(solids.cube())
    assert body.count("\nv ") == len(cube.vertices)
    assert body.count("\nf ") == len(cube.faces)


def test_the_written_mesh_is_named_by_its_contents(tmp_path):
    first = _mesh_obj(solids.cube(), tmp_path)
    again = _mesh_obj(solids.cube(), tmp_path)
    other = _mesh_obj(solids.sphere(), tmp_path)

    assert first == again
    assert first != other
    assert first.read_text() == _obj_text(solids.cube())


def test_asking_blender_for_a_shaded_solid_says_what_it_can_do():
    request = Request(solids.cube(), as_camera("front"), 20.0, None,
                      Look(style="shaded"))

    with pytest.raises(MeshError, match="lineart"):
        render_with_blender(request)
    assert "lineart" in SUPPORTED_STYLES


@needs_blender
@pytest.mark.parametrize("view", ["front", "isometric", "three-quarter"])
def test_blender_draws_into_inklets_own_frame(view):
    mesh = solids.sphere()
    camera = as_camera(view)
    request = Request(mesh, camera, 40.0, None, Look(style="lineart"))

    result = render_with_blender(request)

    # The view handed back is the one inklet computed, not one Blender chose, so
    # `View.project` still says where a 3D point went.
    assert result.view == camera.frame(mesh, 40.0, None)
    drawn = result.diagram.bbox
    wanted = _projected_box(mesh, result.view)
    assert drawn.width == pytest.approx(wanted.width, abs=MAX_ALIGN_MM)
    assert drawn.center.x == pytest.approx(wanted.center.x, abs=MAX_ALIGN_MM)
    assert drawn.center.y == pytest.approx(wanted.center.y, abs=MAX_ALIGN_MM)


@needs_blender
def test_the_two_backends_put_the_model_in_the_same_place():
    # `smooth=False` on both sides, because this is about *placement* and the
    # two backends draw different curves. Blender bakes the facet silhouette;
    # the builtin puts its outline on the surface those facets stand for, which
    # on a mesh as coarse as Spot sits up to one chord sagitta inside them --
    # a real difference, and not the one being measured here.
    kwargs = dict(width=40.0, view="three-quarter", crease=45.0, smooth=False)
    builtin = inklet.model("stress/meshes/spot.obj", backend="builtin", **kwargs)
    baked = inklet.model("stress/meshes/spot.obj", backend="blender", **kwargs)

    a, b = builtin.bbox, baked.bbox
    assert b.width == pytest.approx(a.width, abs=MAX_ALIGN_MM)
    assert b.height == pytest.approx(a.height, abs=MAX_ALIGN_MM)
    assert b.center.x == pytest.approx(a.center.x, abs=MAX_ALIGN_MM)
    assert b.center.y == pytest.approx(a.center.y, abs=MAX_ALIGN_MM)


@needs_blender
def test_an_arrow_clips_on_the_baked_silhouette():
    """The trace is the point of the whole exercise: an arrow has to stop on
    the outline of what Blender drew, in the same place the builtin would."""
    kwargs = dict(width=40.0, view="front", name="spot")
    baked = inklet.model("stress/meshes/spot.obj", backend="blender", **kwargs)
    builtin = inklet.model("stress/meshes/spot.obj", backend="builtin", **kwargs)

    box = baked.bbox
    # Fired from inside, because that is what a connector does: `link` shoots
    # from the centre toward the far end and clips where the ray gets out.
    east = inklet.Vec2(1.0, 0.0)
    hit = baked.trace.boundary_point(box.center, east)
    same = builtin.trace.boundary_point(builtin.bbox.center, east)

    assert hit is not None and same is not None
    assert box.center.x < hit.x <= box.x1 + 1e-6
    # Half a millimetre between two independent hidden-line solvers, on a 40mm
    # model whose outline they each traced their own way.
    assert hit.x == pytest.approx(same.x, abs=0.5)


@needs_blender
def test_the_framing_error_stays_under_a_fifth_of_a_hairline():
    from inklet.assets.cache import cache_root
    from inklet.three.blender import line_art
    from inklet.three.blender_backend import _options

    mesh = solids.cube()
    camera = as_camera("isometric")
    view = camera.frame(mesh, 40.0, None)
    box = _projected_box(mesh, view)
    drawing = line_art(_mesh_obj(mesh, cache_root(None) / "meshes"),
                       width=box.width, height=box.height, camera=camera,
                       up_axis="z", options=_options(Look(style="lineart")))

    assert align_error(drawing, mesh, view) < MAX_ALIGN_MM


@needs_blender
def test_the_bake_is_reported_as_the_backend_that_ran():
    request = Request(solids.cube(), as_camera("front"), 20.0, None, Look())

    result = inklet.three.render(request, backend="blender")

    assert isinstance(result, Rendering)
    assert result.backend == "blender"
