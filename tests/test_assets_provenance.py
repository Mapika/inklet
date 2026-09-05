"""Asset provenance lives on the node, not in a process-wide registry.

The record used to be held in `assets/provenance.py::_RECORDS`, keyed by
`Diagram.id`. Three consequences, and the tests below are them: it leaked for
the lifetime of the process, it did not survive `copy()` -- so the same picture
placed twice was credited once and the second placement had no record at all --
and it did not survive a deep copy. `Diagram.notes` (core M17) fixes all three
at once, because a note travels with the node.

The registry was kept for one round as a read-only fallback and is gone as of
this one, so the two tests that reached into it are gone with it and the leak
test below asserts the absence of the dict rather than that it stays empty.
"""

from __future__ import annotations

import copy

import inklet
from inklet.assets import provenance as module
from inklet.assets.provenance import (PROVENANCE_NOTE, Provenance, credit_lines,
                                   credits, provenance_of, record)


def a_record(source: str = "brain.png", digest: str = "a" * 64) -> Provenance:
    return Provenance(source=source, sha256=digest, pixel_size=(400, 300),
                      steps=("cutout:alpha", "harmonise"),
                      license="CC BY 4.0", attribution="R. Cajal")


def test_the_record_lands_on_the_node():
    node = inklet.box("micrograph")
    given = record(node, a_record())

    assert node.notes[PROVENANCE_NOTE] is given
    assert provenance_of(node) is given


def test_the_record_survives_a_copy():
    """The defect that moved it. `copy()` remints every id in the subtree, so
    a registry keyed on id answered for the original and not for the copy --
    and placing one asset twice is exactly what `copy()` is for."""
    node = inklet.box("micrograph")
    record(node, a_record())

    twin = node.copy()

    assert twin.id != node.id
    assert provenance_of(twin) is not None
    assert provenance_of(twin).source == "brain.png"


def test_the_record_survives_a_placement():
    """A note comes through a transform wrapper (M19), and a `Provenance` is
    not a `Rect`, so it rides across unchanged rather than being re-framed."""
    node = inklet.box("micrograph")
    given = record(node, a_record())

    moved = node.translated(10.0, 4.0)

    assert provenance_of(moved) is given


def test_the_record_survives_a_deep_copy():
    """`Diagram` itself does not pickle -- an envelope holds a closure -- so a
    deep copy is the strongest round trip there is, and the registry lost the
    record on it for the same reason it lost it on `copy()`."""
    node = inklet.box("micrograph")
    record(node, a_record())

    back = copy.deepcopy(node)

    assert provenance_of(back).credit() == "brain.png: R. Cajal, CC BY 4.0"


def test_credits_still_dedupe_on_the_hash_across_a_tree():
    same = a_record("brain.png", "a" * 64)
    other = a_record("cell.png", "b" * 64)
    first, second, third = inklet.box("a"), inklet.box("b"), inklet.box("c")
    record(first, same)
    record(second, same)               # the same file, placed twice
    record(third, other)

    tree = inklet.vstack([first, second, third], gap=1.0)

    assert [p.source for p in credits(tree)] == ["brain.png", "cell.png"]
    assert len(credit_lines(tree)) == 2


def test_a_node_with_no_record_answers_nothing():
    """The fallback used to answer here, off a module-wide dict keyed by id.
    With it gone the only place a record can live is the node."""
    node = inklet.box("micrograph")

    assert PROVENANCE_NOTE not in node.notes
    assert provenance_of(node) is None
    assert credits(node) == ()


def test_nothing_is_recorded_process_wide_any_more():
    """The leak, and the shim that outlived it. Recording a hundred assets
    used to grow a dict nobody ever emptied; the dict itself is gone now, so
    this asserts the module holds no such thing rather than that it stays
    empty."""
    for _ in range(20):
        record(inklet.box("x"), a_record())

    assert not hasattr(module, "_RECORDS")
    assert [name for name, value in vars(module).items()
            if isinstance(value, dict) and not name.startswith("__")] == []
