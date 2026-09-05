"""`overlay=True`: one part of a fused scene, painted on top as itself.

`order="exact"` buys exact depth by giving up separate painting -- the parts
become one mesh, so only what the fused mesh can carry per face group may
still differ between them. `overlay=True` is the door out of that: the part is
left out of the mesh, drawn as its own `model()` in the scene's projection,
and composited over the result. It may then set anything `model()` takes, and
it pays for that with the thing fusing was bought for -- it is always on top.
The tests here pin both halves of that bargain, the freedom and the price.
"""

from __future__ import annotations

import itertools

import pytest

import inklet
from inklet.core import flatten
from inklet.three import Mat4, MeshError, Vec3, build
from inklet.three.api import scene_paint


def _ring_and_rod():
    """A rod through a ring: the shape that only comes out right when depth is
    settled facet by facet, so anything left in the fused pass still threads."""
    ring = build("torus", radius=4.0, tube=1.0, segments=40, rings=16).transformed(
        Mat4.rotation(Vec3(0.0, 1.0, 0.0), 90.0))
    rod = build("cylinder", radius=0.5, height=14.0).transformed(
        Mat4.rotation(Vec3(0.0, 1.0, 0.0), 90.0))
    return ring, rod


def _rig(**rod_options):
    ring, rod = _ring_and_rod()
    return inklet.scene([("ring", ring, {"color": "#ff0000"}),
                      ("rod", rod, {"color": "#0000ff", **rod_options})],
                     width=60.0, view="three-quarter", style="shaded",
                     order="exact")


def _fill_runs(scene):
    """Which part each painted facet came from, in paint order, repeats
    collapsed -- red is the ring, blue is the rod."""
    who = []
    for item in flatten(scene):
        fill = item.style.fill
        if not fill or fill == "none":
            continue
        who.append("ring" if int(fill[1:3], 16) > int(fill[5:7], 16) else "rod")
    return [name for name, _ in itertools.groupby(who)]


# -- the price: always on top ----------------------------------------------


def test_a_fused_part_threads_and_an_overlay_does_not():
    # The same two solids, the same projection: in the pass they interleave,
    # out of it the rod is one uninterrupted run at the end.
    assert len(_fill_runs(_rig())) > 2
    assert _fill_runs(_rig(overlay=True)) == ["ring", "rod"]


def test_the_overlay_is_last_however_it_was_declared():
    ring, rod = _ring_and_rod()
    scene = inklet.scene([("rod", rod, {"color": "#0000ff", "overlay": True}),
                       ("ring", ring, {"color": "#ff0000"})],
                      width=60.0, view="three-quarter", style="shaded",
                      order="exact")
    assert _fill_runs(scene) == ["ring", "rod"]


def test_two_overlays_are_painted_in_the_order_they_were_written():
    ring, rod = _ring_and_rod()
    paint = scene_paint(inklet.scene(
        [("ring", ring), ("rod", rod, {"overlay": True}),
         ("pin", rod, {"overlay": True})],
        width=60.0, view="three-quarter", order="exact"))
    assert paint.paint == (0, 1, 2)


def test_the_paint_record_says_the_author_chose_the_place():
    paint = scene_paint(_rig(overlay=True))
    assert paint.fused
    assert paint.paint[-1] == 1                  # the overlay, after the body
    assert paint.declared == frozenset({1})


def test_the_depth_rule_reads_an_overlay_as_a_declared_place():
    # `DEPTH_ORDER` reports a part painted over one in front of it. An overlay
    # is always over everything, so the only thing that keeps it quiet is the
    # rule knowing the place was chosen rather than computed.
    fig = inklet.figure(width=90.0)
    fig.add(_rig(overlay=True))
    assert fig.lint(rules=["DEPTH_ORDER"]) == []


# -- the freedom: it is a model() again -------------------------------------


def test_an_overlay_may_ask_for_the_look_a_fused_part_may_not():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="one pass"):
        inklet.scene([("ring", ring), ("rod", rod, {"style": "wire"})],
                  width=60.0, view="three-quarter", order="exact")
    scene = inklet.scene([("ring", ring),
                       ("rod", rod, {"style": "lineart", "overlay": True})],
                      width=60.0, view="three-quarter", style="shaded",
                      order="exact")
    assert flatten(scene.find("rod"))


@pytest.mark.parametrize("option", [{"opacity": 0.35}, {"cull": False},
                                    {"sort": "depth"}, {"hidden": "dashed"},
                                    {"occlusion": 0.4}])
def test_the_settings_a_pass_owns_are_an_overlays_to_set(option):
    scene = _rig(overlay=True, **option)
    assert flatten(scene.find("rod"))


def test_an_overlay_at_low_opacity_lets_the_scene_show_through():
    faint = [item.style.opacity for item in flatten(_rig(overlay=True,
                                                         opacity=0.35))
             if item.style.opacity not in (None, 1.0)]
    assert faint and all(value == pytest.approx(0.35) for value in faint)


def test_an_overlay_is_still_a_part_with_a_name_and_anchors():
    scene = _rig(overlay=True)
    assert scene.find("rod") is not None
    assert scene.anchor_point("rod") is not None
    # And it sits where the part sits, not at the scene's own centre: the rod
    # spans the scene, so its box is wider than the ring's.
    assert scene.anchor_point("rod.e").x > scene.anchor_point("ring.e").x


def test_an_overlay_paints_where_the_fused_drawing_would_have_painted_it():
    # It is drawn through the scene's own pinned camera and carried to the box
    # the fused mesh gave it, so switching a part to overlay moves nothing.
    loose, fused = _rig(overlay=True), _rig()
    assert loose.bbox.width == pytest.approx(fused.bbox.width, abs=1e-9)
    assert loose.bbox.height == pytest.approx(fused.bbox.height, abs=1e-9)


def test_an_overlay_scene_is_written_the_same_way_twice():
    # Node ids come from a process-wide counter, so two figures in one process
    # differ in their `id=` attributes and in nothing else -- the geometry is
    # what has to match.
    def paths():
        import re

        fig = inklet.figure(width=90.0)
        fig.add(_rig(overlay=True, opacity=0.4))
        return re.findall(r' d="([^"]+)"', fig.to_svg())

    assert paths() == paths()


# -- the refusals -----------------------------------------------------------


def test_the_scene_may_not_set_overlay_for_everyone():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="a part's to set"):
        inklet.scene([("ring", ring), ("rod", rod)], width=60.0,
                  view="three-quarter", order="exact", overlay=True)


def test_a_parts_scene_has_nothing_to_opt_out_of():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="nothing to opt out of"):
        inklet.scene([("ring", ring), ("rod", rod, {"overlay": True})],
                  width=60.0, view="three-quarter", order="parts")


def test_a_scene_of_nothing_but_overlays_is_a_parts_scene():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="nothing left to fuse"):
        inklet.scene([("ring", ring, {"overlay": True}),
                   ("rod", rod, {"overlay": True})],
                  width=60.0, view="three-quarter", order="exact")


def test_the_refusal_for_a_fused_part_points_at_the_way_out():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="overlay=True takes 'rod' out"):
        inklet.scene([("ring", ring), ("rod", rod, {"opacity": 0.5})],
                  width=60.0, view="three-quarter", order="exact")


def test_an_overlay_still_may_not_choose_its_place_in_the_order():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="nowhere to put"):
        inklet.scene([("ring", ring),
                   ("rod", rod, {"overlay": True, "draw_order": 0})],
                  width=60.0, view="three-quarter", order="exact")
