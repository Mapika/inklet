"""`inklet.crossing` -- declaring one line through one part, and nothing else.

The shape under test is `figures/structure.py` panel (b): a close-up of a
buried pocket, a leader that has to cross the assembly in front of it to reach
the atom it names, and a label at the far end of that leader sitting on the
model. Two of those three are the figure working as intended; the third is a
finding. The whole point of this declaration is that it separates them, where
`inklet.abutting` round the same three nodes silences all three.

Built here rather than imported from `figures/structure.py`: the figure is
another agent's, the real one takes eight seconds to render, and the claim is
about the shape and not about that particular pocket.
"""

from __future__ import annotations

import inklet
from inklet.diagnostics.cross import CROSSES_NOTE, declared_crossings

PAGE = inklet.Rect(0.0, 0.0, 60.0, 40.0)


def at(node: inklet.Diagram, cx: float, cy: float) -> inklet.Diagram:
    """`node` with its box centred on (cx, cy). Primitives are centred on the
    local origin, so every fixture here would otherwise be off by half itself.
    """
    here = node.bbox.center
    return node.translated(cx - here.x, cy - here.y)


def blob(name: str, w: float = 18.0, h: float = 14.0) -> inklet.Diagram:
    return inklet.polygon([(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)],
                       fill="#cfd8dc", stroke="none").named(name)


def leader_line(length: float, name: str = "leader") -> inklet.Diagram:
    return inklet.polyline([(0.0, 0.0), (length, 0.0)], stroke="#37474f",
                        stroke_width=0.2, kind="leader").named(name)


def pocket(*, declared: str) -> inklet.Diagram:
    """A buried pocket: the leader crosses the assembly in front of it.

    `assembly` is the thing in the way, 18 x 14 in the middle of the page.
    `atom` is what the label names, behind it and to the west. The leader runs
    from the label's side of the page to a millimetre short of the atom, which
    means straight through the assembly and out the other side -- that is what
    "buried" means, and it is one PATH_CROSSES against the assembly. The
    millimetre of daylight at the west end is not decoration: a stroke that
    starts or ends *inside* a shape has arrived at it, and PATH_CROSSES says
    nothing about either shape then.

    `tag` is the label the leader carries, parked 0.15mm under the assembly's
    south edge. That is a genuine crowding finding, and it stays one under
    every declaration but `abutting`.

    `declared` is "none", "crossing" or "abutting".
    """
    assembly = at(blob("assembly"), 19.0, 17.0)               # 10..28 x
    atom = at(blob("atom", 4.0, 4.0), 5.0, 17.0)              # 3..7 x
    line = at(leader_line(37.0, "bond-leader"), 26.5, 17.0)   # 8..45 x
    tag = inklet.text("Thr766", size=2.0).named("bond-label")
    tag = at(tag, 19.0, 24.0 + 0.15 + tag.bbox.height / 2.0)

    if declared == "crossing":
        inklet.crossing(line, assembly)
    # `"g"`, a composing kind, and not `"group"`: `_composed_with` reads any
    # container that is *not* one of the layout kinds as a picture the stroke
    # was drawn into, and exempts it. A page composes; a drawing does not.
    kind = inklet.abutting("in-the-pocket") if declared == "abutting" else "g"
    return inklet.Diagram(children=(assembly, atom, line, tag), kind=kind)


def codes(root: inklet.Diagram) -> set[str]:
    return {d.code for d in inklet.lint(root, page=PAGE)}


def test_the_undeclared_pocket_reports_the_crossing_and_the_crowding():
    """The fixture, and the reason the figure needed a declaration at all."""
    root = pocket(declared="none")

    assert codes(root) >= {"PATH_CROSSES", "CROWDING"}


def test_a_declared_crossing_exempts_the_line_and_keeps_the_label_s_crowding():
    """The claim is "this one line is allowed to cross this one part".

    Not "stop looking at this corner of the figure": the label the leader
    carries is still 0.15mm off the model and still has to be reported, which
    is exactly what `figures/structure.py` panel (b) gave up to silence the
    crossing.
    """
    root = pocket(declared="crossing")

    found = inklet.lint(root, page=PAGE)
    assert "PATH_CROSSES" not in {d.code for d in found}
    crowded = [d.message for d in found if d.code == "CROWDING"]
    assert any("bond-label" in m and "assembly" in m for m in crowded), crowded


def test_abutting_silences_the_crowding_too_which_is_the_old_spelling():
    """What the declaration is narrower *than*. Same tree, same two defects,
    and the only spelling available before this reports neither."""
    root = pocket(declared="abutting")

    found = codes(root)
    assert "PATH_CROSSES" not in found
    assert "CROWDING" not in found


def test_a_declaration_names_one_part_and_not_the_next_one():
    """Scoped. A second blob the author did not name is still crossed."""
    named = at(blob("named-part", 10.0, 10.0), 14.0, 20.0)     # 9..19 x
    other = at(blob("other-part", 10.0, 10.0), 38.0, 20.0)     # 33..43 x
    line = at(leader_line(36.0), 26.0, 20.0)                   # 8..44 x
    inklet.crossing(line, named)

    root = inklet.Diagram(children=(named, other, line))
    reported = [d for d in inklet.lint(root, page=PAGE) if d.code == "PATH_CROSSES"]

    assert reported, "the fixture stopped crossing anything"
    assert all("other-part" in d.message for d in reported), [
        d.message for d in reported]


def test_a_declaration_reaches_into_the_part_it_names():
    """A leader declared through a scene is declared through its atoms.

    The author names two objects; making them name every triangle inside one
    of them would be a worse spelling than the `abutting` it replaces.
    """
    atom = at(blob("atom", 14.0, 12.0), 19.0, 20.0)            # 12..26 x
    scene = inklet.Diagram(children=(atom,), kind="model")
    line = at(leader_line(30.0), 19.0, 20.0)                   # 4..34 x
    inklet.crossing(line, scene)

    assert "PATH_CROSSES" not in codes(inklet.Diagram(children=(scene, line)))
    assert "PATH_CROSSES" in codes(inklet.Diagram(children=(
        at(blob("atom", 14.0, 12.0), 19.0, 20.0),
        at(leader_line(30.0), 19.0, 20.0))))


def test_the_declaration_is_directional():
    """A stroke says what it goes through; a shape never says what may go
    through it. Declaring it the wrong way round is not a licence."""
    assembly = at(blob("assembly", 14.0, 12.0), 19.0, 20.0)
    line = at(leader_line(30.0), 19.0, 20.0)
    inklet.crossing(assembly, line)          # backwards on purpose

    assert "PATH_CROSSES" in codes(inklet.Diagram(children=(assembly, line)))


def test_naming_a_part_twice_declares_it_once():
    line = inklet.polyline([(0.0, 0.0), (10.0, 0.0)], kind="leader")
    blob = inklet.polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)])
    other = inklet.polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)])

    inklet.crossing(line, blob)
    inklet.crossing(line, other, blob)

    assert declared_crossings(line) == (blob.id, other.id)
    assert line.notes[CROSSES_NOTE] == (blob.id, other.id)


def test_annotate_forwards_through_to_its_own_leader():
    """The library's leader is a routed link, so it could already declare a
    crossing through `leader_style={"through": ...}` -- which spends
    `attached_to`, and `CROWDING` reads that too. `through=` on `annotate`
    spends the narrow declaration instead."""
    target = inklet.box("site")
    art = inklet.annotate(target, "pocket", side="e", through=(target,))

    declared = [declared_crossings(n) for n in art.walk()]
    assert any(target.id in ids for ids in declared), declared


def test_an_undeclared_annotation_carries_no_note():
    target = inklet.box("site")
    art = inklet.annotate(target, "pocket", side="e")

    assert all(declared_crossings(n) == () for n in art.walk())
