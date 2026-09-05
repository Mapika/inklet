"""`inklet.crossing(stroke, part)` -- "this one line goes through that one part".

A callout into a buried pocket has to cross the assembly in front of it. That
is what *buried* means, and `PATH_CROSSES` reporting it is a description of the
figure rather than a finding about it. Until now there were two ways to say so
and both said more than the author meant:

* `inklet.abutting(kind)` round the leader and the model silences the crossing --
  and `OVERLAP` and `CROWDING` with it, for every pair inside, so the *label*
  at the far end of that leader stops being measured against the thing it is
  naming. `figures/structure.py` panel (b) does this: five leaders and five
  dashes and one scene under `abutting("in-the-pocket")`, and no report of the
  labels at all.
* `fig.link(..., through=)` says the narrow thing but only a *routed link* can
  say it: the declaration rides on `Diagram.attached_to`, which nothing but the
  router writes. A hand-drawn leader -- `figures/annot.py::leader`, which is
  what the corpus actually uses -- is a free `PathPrim` with no way to declare
  anything. And `attached_to` is read by `CROWDING` too, so even the link
  spelling gives away more than the crossing.

So this is a third channel, deliberately narrower than either: a note listing
the nodes this one stroke was drawn through, read by the two crossing rules and
by nothing else. `OVERLAP`, `CROWDING` and the stroke near-miss half of
`CROWDING` go on measuring the declared pair exactly as before, which is the
point -- the claim is "this line may cross that part", not "stop looking here".

    line, tag = annot.leader("Thr766", middle, (x, y))
    inklet.crossing(line, scene)         # or annot.leader(..., through=(scene,))

Scoped and directional. Declaring a leader through a scene exempts the leader
against that scene and against everything drawn inside it, and nothing else:
the second leader in the same figure is still checked, and so is the first
against every part the author did not name. It is *not* symmetric the way
`abutting` is -- a stroke declares what it goes through; a shape never declares
what may go through it -- because the asymmetry is what keeps the declaration
from growing into a licence.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:                                        # pragma: no cover
    from ..core.diagram import Diagram

__all__ = ["CROSSES_NOTE", "crossing", "declared_crossings"]

#: The note a stroke keeps its declared crossings on: a tuple of node ids, in
#: the order the author named them.
#:
#: Ids rather than node references because that is what the reader has -- the
#: linter works from a `{id: node}` table -- and because holding the object
#: would keep a whole subtree alive off a note. The cost is that `copy()`
#: remints ids and does not rewrite this note, so a declared crossing inside a
#: copied subtree goes quiet and the finding comes back. That fails in the safe
#: direction (a false positive returns; nothing is silenced that should not be)
#: and `Diagram.copy` already does exactly this rewrite for `attached_to`, so
#: the fix is core's when someone needs it.
CROSSES_NOTE = "crosses"


def crossing(stroke: "Diagram", *through: "Diagram") -> "Diagram":
    """Declare that `stroke` is drawn through `through` on purpose.

    `PATH_CROSSES` and `LINK_CROSSES` then skip that stroke against those
    shapes and against anything drawn inside them. Every other rule is
    untouched: the stroke and its label are still measured for crowding and
    overlap against the very same parts, because "allowed to cross it" and
    "allowed to sit on top of it" are different claims and a figure usually
    means only the first::

        inklet.crossing(leader, scene)

    Mutating and self-returning, like `Diagram.note` and `Diagram.anchor`: the
    caller has just drawn the stroke and nobody else is holding it. Repeated
    calls add to the declaration rather than replacing it, so a leader through
    two parts can name them one at a time.
    """
    put = getattr(stroke, "note", None)
    if not callable(put):                                # pragma: no cover
        return stroke                                    # pre-M17 core
    named = tuple(node.id for node in through)
    already = declared_crossings(stroke)
    put(CROSSES_NOTE, already + tuple(i for i in named if i not in already))
    return stroke


def declared_crossings(node: "Diagram") -> tuple[str, ...]:
    """The ids this node was declared to be drawn through; empty for most."""
    notes = getattr(node, "notes", None)
    if not isinstance(notes, Mapping):
        return ()
    listed = notes.get(CROSSES_NOTE)
    if isinstance(listed, str) or not isinstance(listed, Iterable):
        return ()
    return tuple(i for i in listed if isinstance(i, str))
