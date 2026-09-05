"""PATH_CROSSES, and the `inklet.abutting` declaration that quiets a drawing.

`OVERLAP` compares areas and a stroke has none, so a leader through a protein
and a hand-drawn arrow through a mesh both reported nothing. `LINK_CROSSES`
covers what the router built; `PATH_CROSSES` covers everything the author drew
themselves, and almost all of the work is in *not* reporting the seven hundred
strokes the corpus draws as part of its pictures. The tests below are one per
exemption, because each of them was a false positive first.
"""

from __future__ import annotations

import inklet
from inklet import Mat4, Vec3
from inklet.core import Diagram, PathPrim, RectPrim, Vec2
from inklet.diagnostics.rules import build_context
from inklet.three.solids import build as build_mesh


def crossings(node: inklet.Diagram) -> list:
    fig = inklet.figure(width=120)
    fig.add(node)
    return [d for d in fig.lint() if d.code == "PATH_CROSSES"]


def stroke(points, **style) -> inklet.Diagram:
    """A path at absolute coordinates, the way `figures/annot.py` draws one."""
    prim = PathPrim.polyline([Vec2(*p) for p in points])
    return Diagram(prim=prim, kind=style.pop("kind", "path")).styled(
        fill="none", stroke="#000000", stroke_width=0.2, **style)


def blob(x: float, y: float, w: float = 20.0, h: float = 12.0,
         name: str = "blob") -> inklet.Diagram:
    """A plain filled rectangle, at absolute coordinates."""
    node = Diagram(prim=RectPrim(w, h), kind="box").styled(fill="#cccccc")
    return (node.named(name) if name else node).translated(x, y)


# -- the finding ----------------------------------------------------------


def test_a_leader_through_a_shape_on_its_way_somewhere_else_is_reported():
    picture = blob(0.0, 0.0, 30.0, 20.0, name="protein")
    leader = stroke([(-40.0, 0.0), (40.0, 0.0)], kind="leader")

    found = crossings(inklet.place([picture, leader]))

    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "protein" in found[0].message
    assert "30.00mm" in found[0].message


def test_a_line_through_a_word_is_an_error():
    word = inklet.label("legible")
    line = stroke([(-30.0, 0.0), (30.0, 0.0)])

    found = crossings(inklet.place([word, line]))

    assert [d.severity for d in found] == ["error"]


# -- what is not a crossing -----------------------------------------------


def test_a_leader_that_lands_on_what_it_names_is_silent():
    """The distinction the rule turns on. Arriving means the last millimetre
    is inside the surface being named; going through means coming out again."""
    picture = blob(0.0, 0.0, 30.0, 20.0, name="protein")
    leader = stroke([(-40.0, 0.0), (0.0, 0.0)], kind="leader")

    assert crossings(inklet.place([picture, leader])) == []


def test_a_line_with_both_ends_on_one_object_is_drawn_on_it():
    """A dashed hydrogen bond between two atoms of one molecule skips over
    whatever lies between them, and what lies between them is the molecule."""
    atoms = tuple(blob(x, 0.0, 10.0, 10.0, name="") for x in (-20.0, 0.0, 20.0))
    molecule = Diagram(children=atoms, kind="place").named("molecule")
    bond = stroke([(-20.0, 0.0), (20.0, 0.0)], kind="hbond")

    assert crossings(inklet.place([molecule, bond])) == []


def test_a_stroke_drawn_inside_a_picture_is_part_of_it():
    """Composition is not membership. A `place` arranges two finished things;
    anything else holding both is a drawing the stroke belongs to."""
    inside = Diagram(
        children=(blob(0.0, 0.0, 30.0, 20.0, name="body"),
                  stroke([(-40.0, 0.0), (40.0, 0.0)])),
        kind="panel", name="scene")

    assert crossings(inside) == []


def test_a_stroke_that_disappears_under_opaque_ink_is_not_a_crossing():
    """A marker sits on the line it belongs to and a knockout plate goes under
    a tick label precisely so the gridline stops there. Both are painted after
    the stroke, so there is nothing on the page to see."""
    line = stroke([(-30.0, 0.0), (30.0, 0.0)])
    marker = blob(0.0, 0.0, 6.0, 6.0, name="marker")

    over = inklet.place([line, marker])       # marker painted last: hidden
    under = inklet.place([marker, line])      # line painted last: visible

    assert crossings(over) == []
    assert len(crossings(under)) == 1


def test_a_shape_that_contains_the_whole_stroke_is_not_crossed():
    frame = blob(0.0, 0.0, 60.0, 40.0, name="card")
    inside = stroke([(-10.0, 0.0), (10.0, 0.0)])

    assert crossings(inklet.place([frame, inside])) == []


def test_a_declared_crossing_is_silent():
    picture = blob(0.0, 0.0, 30.0, 20.0, name="protein")
    leader = stroke([(-40.0, 0.0), (40.0, 0.0)], kind="leader")
    honest = inklet.place([picture, leader])

    assert len(crossings(honest)) == 1

    declared = inklet.place([picture, leader], kind=inklet.abutting("annotated"))

    assert crossings(declared) == []


# -- inklet.abutting ---------------------------------------------------------


def test_abutting_marks_a_kind_and_is_idempotent():
    assert inklet.abutting("sankey") == "sankey-abutting"
    assert inklet.abutting(inklet.abutting("sankey")) == "sankey-abutting"
    assert inklet.abutting() == "group-abutting"


def touching(kind: str | None) -> list:
    """Two boxes sharing an edge, wrapped in a group of the given kind."""
    left = blob(0.0, 0.0, 20.0, 10.0, name="left")
    right = blob(20.0, 0.0, 20.0, 10.0, name="right")
    node = Diagram(children=(left, right), kind=kind or "place")
    fig = inklet.figure(width=90)
    fig.add(node)
    return [d for d in fig.lint() if d.code in ("OVERLAP", "CROWDING")]


def test_touching_parts_are_reported_until_they_are_declared():
    assert touching(None)
    assert touching(inklet.abutting("ribbons")) == []


def test_the_declaration_only_covers_what_is_inside_it():
    """Symmetric and scoped: the claim is that the parts of *this* thing touch
    each other, not that this thing may touch anything else."""
    ribbons = Diagram(
        children=(blob(0.0, 0.0, 20.0, 10.0, name="a"),
                  blob(20.0, 0.0, 20.0, 10.0, name="b")),
        kind=inklet.abutting("ribbons"))
    stray = inklet.label("caption").named("caption").translated(0.0, 5.6)

    fig = inklet.figure(width=90)
    fig.add(inklet.place([ribbons, stray]))
    found = fig.lint()

    assert [d.code for d in found] == ["OVERLAP"]
    assert "caption" in found[0].message


def homes(node: inklet.Diagram) -> dict:
    """Every named part of a built figure, mapped to its abutting home."""
    fig = inklet.figure(width=90)
    fig.add(node)
    root, placements = fig.build()
    ctx = build_context(root, placements, page=root.bbox)
    return {n.name: ctx.abutting_home(i) for i, n in ctx.nodes.items() if n.name}


def test_a_scene_declares_itself():
    """`inklet.scene` needs no declaration: an atom and the bond drawn into it
    are one object's geometry, and 66 of those pairs on
    `stress/electro_figure.py` offered to move half a crystal off the other."""
    mesh = build_mesh("box", size_x=1.0, size_y=1.0, size_z=1.0)
    shifted = mesh.transformed(Mat4.translation(Vec3(0.9, 0.0, 0.0)))
    one = inklet.scene([("a", mesh, {}), ("b", shifted, {})],
                    width=40.0, name="pair")

    inside = homes(one)

    assert inside["a"] == inside["b"] == inside["pair"]


def test_two_scenes_are_two_objects():
    """The outermost model wins, not the nearest: a crystal built out of
    per-atom sub-models is one thing. Two crystals are two things, and one
    laid over the other is still worth saying."""
    mesh = build_mesh("box", size_x=1.0, size_y=1.0, size_z=1.0)
    left = inklet.scene([("a", mesh, {})], width=20.0, name="left")
    right = inklet.scene([("b", mesh, {})], width=20.0, name="right")

    apart = homes(inklet.place([left, right]))

    assert apart["a"] == apart["left"] != apart["right"] == apart["b"]


# -- CROWDING inside a plot panel -----------------------------------------


def wedge(panel, x: float, y: float) -> inklet.Diagram:
    """A filled shape at data coordinates, the way `Panel.draw` takes one."""
    corners = [panel.point(x, y), panel.point(x + 1.0, y),
               panel.point(x + 0.5, y + 1.0)]
    return inklet.polygon(corners).styled(fill="#888888")


def test_two_shapes_drawn_at_data_coordinates_are_not_crowded():
    """A `Panel.draw` shape is at the scales' mercy exactly as a `mark` is,
    and it carries no `mark` kind to say so. One panel of
    `stress/mega_figure.py` drew 120 of them and reported 416 pairs
    "0.26mm apart, add 0.74mm of separation" -- of a measurement."""
    panel = inklet.panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 10.0))
    panel.draw(wedge(panel, 0.0, 0.0), wedge(panel, 1.05, 0.0))

    fig = inklet.figure(width=90)
    fig.add(panel.build())

    assert [d for d in fig.lint() if d.code == "CROWDING"] == []


def test_a_label_near_a_drawn_shape_is_still_crowded():
    """The exemption is about geometry the data placed, not about the panel:
    an annotation inside one is furniture and can always be moved."""
    panel = inklet.panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 10.0))
    panel.draw(wedge(panel, 0.0, 0.0))
    panel.place([((1.95, 0.5), inklet.label("annotation"))])

    fig = inklet.figure(width=90)
    fig.add(panel.build())

    assert [d.code for d in fig.lint() if d.code == "CROWDING"] == ["CROWDING"]


# -- near misses: the millimetre before a crossing -------------------------
#
# `_pairable` drops unfilled paths from `CROWDING`, so until now a hairline
# that stopped a tenth of a millimetre short of a word was reported by
# nothing: too far for `PATH_CROSSES`, invisible to a bbox comparison.


def crowding(node: inklet.Diagram) -> list:
    fig = inklet.figure(width=120)
    fig.add(node)
    return [d for d in fig.lint() if d.code == "CROWDING"]


def test_a_hairline_that_stops_short_of_a_word_is_crowding():
    word = inklet.label("legible").named("word")
    height = word.bbox.height
    line = stroke([(-30.0, height / 2.0 + 0.1), (30.0, height / 2.0 + 0.1)])

    found = crowding(inklet.place([word, line]))

    assert len(found) == 1, [d.message for d in found]
    assert found[0].severity == "info"
    assert "passes within 0.10mm of" in found[0].message
    assert "'legible'" in found[0].message
    assert crossings(inklet.place([word, line])) == []


def test_a_stroke_that_keeps_its_distance_says_nothing():
    word = inklet.label("legible").named("word")
    height = word.bbox.height
    line = stroke([(-30.0, height / 2.0 + 1.2), (30.0, height / 2.0 + 1.2)])

    assert crowding(inklet.place([word, line])) == []


def test_a_leader_that_arrives_at_what_it_names_is_not_a_near_miss():
    """`_through` exempts a line whose last millimetre is inside the thing it
    points at. Stopping a hundredth of a millimetre short of the same surface
    is the same leader, and the corpus draws eight of them."""
    picture = blob(0.0, 0.0, 20.0, 12.0, name="protein")
    leader = stroke([(-30.0, 0.0), (-10.04, 0.0)], kind="leader")

    assert crowding(inklet.place([picture, leader])) == []


def test_a_line_along_the_side_of_a_shape_is_reported_once():
    """Whole millimetres of a box's edge under a hairline is one finding
    naming the box, not one per segment of the line."""
    picture = blob(0.0, 0.0, 20.0, 12.0, name="protein")
    line = stroke([(-9.0, 6.3), (0.0, 6.3), (9.0, 6.3)])

    found = crowding(inklet.place([picture, line]))

    assert len(found) == 1, [d.message for d in found]
    assert "passes within 0.30mm of protein" in found[0].message
    assert found[0].targets == tuple(sorted(found[0].targets))


def test_a_declared_touch_stays_quiet():
    """`inklet.abutting` covers the near miss as it covers the crossing: the
    stroke and the shape are declared to meet."""
    picture = blob(0.0, 0.0, 20.0, 12.0, name="protein")
    line = stroke([(-9.0, 6.2), (9.0, 6.2)])
    together = Diagram(children=(picture, line), kind=inklet.abutting("molecule"))

    assert crowding(together) == []
