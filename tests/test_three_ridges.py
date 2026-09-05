"""Per-group ridge suppression on a synthetic bevel.

Four planar strips form parallel folds of 50, 60 and 50 degrees. The central
fold suppresses both shallower neighbours. Assigning the first strip to the
cut group must preserve its 50-degree boundary without restoring the other
suppressed surface fold. Geometry is generated here without atlas assets.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.three.backend import Look, ridges_for
from inklet.three.camera import Camera
from inklet.three.edges import CREASE, chain_edges, feature_edges
import math
from inklet.three import Mesh, Vec3
from inklet.three.solids import cylinder

@pytest.fixture(scope="module")
def sectioned():
    vertices = []
    x = z = 0.0
    for angle in (None, 0, 50, 110, 160):
        if angle is not None:
            x += math.cos(math.radians(angle))
            z += math.sin(math.radians(angle))
        vertices.extend((Vec3(x, -1, z), Vec3(x, 1, z)))
    faces, groups = [], []
    for strip in range(4):
        a = 2 * strip
        faces.extend(((a, a + 2, a + 3), (a, a + 3, a + 1)))
        groups.extend(["cut" if strip == 0 else "surface"] * 2)
    return Mesh(tuple(vertices), tuple(faces), tuple(groups), "sectioned-bevel")


def _inked(mesh, ridges, cut_degrees=8.0, surface_degrees=45.0):
    """The creases the sectioned bevel inks, split into rim and interior.

    "Rim" is every inked fold with a face in the `cut` group -- the flat cap is
    flat, so its only folds are where it meets the surface.
    """
    view = Camera.named("right").frame(mesh, width=60.0)
    angles = [cut_degrees if group == "cut" else surface_degrees
              for group in mesh.groups]
    found = feature_edges(mesh, view, crease_degrees=angles,
                          ridges=ridges_for(mesh, ridges))
    rim, inner = set(), set()
    for edge in found:
        if edge.kind != CREASE:
            continue
        key = (edge.a, edge.b)
        if any(mesh.groups[face] == "cut" for face in mesh.edge_faces[key]):
            rim.add(key)
        else:
            inner.add(key)
    return rim, inner


def _chains(edges):
    return chain_edges(sorted(edges))


# -- what the per-group flag buys ------------------------------------------


def test_the_shallower_cut_fold_is_suppressed_with_ridges_on(sectioned):
    rim, inner = _inked(sectioned, True)
    assert rim == set()
    assert inner == {(4, 5)}


def test_disabling_cut_suppression_preserves_its_fold_only(sectioned):
    off_everywhere = _inked(sectioned, False)
    per_group = _inked(sectioned, {"cut": False})
    all_on = _inked(sectioned, True)
    assert per_group[0] == off_everywhere[0] == {(2, 3)}
    assert per_group[1] == all_on[1] == {(4, 5)}
    assert off_everywhere[1] == {(4, 5), (6, 7)}
    chains = _chains(per_group[0])
    assert len(chains) == 1
    assert chains[0][0] == (2, 3)


def test_a_group_the_mapping_does_not_name_keeps_suppression(sectioned):
    # The mapping form is for the exception. Naming nothing is ridges-on.
    assert _inked(sectioned, {}) == _inked(sectioned, True)
    assert _inked(sectioned, {"surface": True}) == _inked(sectioned, True)


def test_naming_every_group_is_the_same_as_turning_it_off(sectioned):
    assert _inked(sectioned, {"cut": False, "surface": False}) == \
        _inked(sectioned, False)


def test_suppression_still_sees_the_unsuppressed_folds_as_rivals(sectioned):
    from dataclasses import replace
    # The 60-degree fold now touches the cut group; its 50-degree neighbour
    # belongs only to surface faces and must still be suppressed.
    mesh = replace(sectioned, groups=("cut", "cut", "cut", "cut",
                                     "surface", "surface", "surface", "surface"))
    per_group = _inked(mesh, {"cut": False})
    all_on = _inked(mesh, True)
    assert per_group[1] == all_on[1] == set()
    assert _inked(mesh, False)[1] == {(6, 7)}
    assert all_on[0] < per_group[0]


# -- the plumbing ----------------------------------------------------------


def test_model_takes_the_mapping_and_draws_the_difference(sectioned):
    dotted = inklet.model(sectioned, width=60.0, view="right",
                       style="lineart", crease=45.0, ridges=True)
    whole = inklet.model(sectioned, width=60.0, view="right",
                      style="lineart", crease=45.0, ridges={"cut": False})
    assert _svg(dotted) != _svg(whole)


def test_a_mesh_with_no_groups_ignores_the_mapping():
    # Nothing for the mapping to select, so it takes the rule that applies to
    # everything it did not name -- which is suppression.
    plain = cylinder(segments=24)
    assert not plain.groups
    assert ridges_for(plain, {"anything": False}) is True
    assert _svg(inklet.model(plain, width=30.0, view="right",
                          ridges={"anything": False})) == \
        _svg(inklet.model(plain, width=30.0, view="right", ridges=True))


def test_the_look_carries_the_mapping_as_sorted_pairs():
    # Hashable, and in one order however the caller wrote the dict, for the
    # same reason `colors` and `creases` are.
    one = inklet.model(cylinder(segments=12), width=20.0,
                    ridges={"b": False, "a": False})
    assert one is not None
    look = Look(ridge_groups=(("a", False), ("b", False)))
    assert hash(look) == hash(Look(ridge_groups=(("a", False), ("b", False))))


def test_a_flag_per_face_must_be_one_per_face(sectioned):
    view = Camera.named("front").frame(sectioned, width=30.0)
    with pytest.raises(ValueError, match="one ridges flag per face"):
        feature_edges(sectioned, view, ridges=[True, False])


def test_the_scene_default_is_unchanged(sectioned):
    # Everything above is additive: a caller who says nothing gets exactly the
    # edges they got before the mapping existed.
    assert _inked(sectioned, True) == _inked(sectioned, ridges_for(sectioned, True))


def _svg(node):
    import re

    fig = inklet.figure()
    fig.add(node)
    return re.sub(r' id="[^"]*"', "", fig.to_svg())
