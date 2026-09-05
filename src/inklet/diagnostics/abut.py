"""`inklet.abutting(kind)` -- "the parts in here are meant to touch".

Some figures are built out of pieces that share an edge on purpose. A Sankey
ribbon leaves its column exactly where its neighbour starts; a ball-and-stick
model draws a bond into the atom at each end; a chord diagram's feet tile the
rim with no gap at all. In every one of those the touching *is* the drawing,
and `OVERLAP` and `CROWDING` reporting it is not a finding but a description.

The alternative to a declaration is a tolerance, and a tolerance is the wrong
tool twice over: `min_clearance_mm=0` would silence the crystal in panel (b)
of `stress/electro_figure.py` and the tick label two tenths of a millimetre
off its axis with it, and it would do so for the whole page rather than for
the one object that means it.

So this is spelled the way `inklet.encoded(kind)` is -- a suffix on the node's
`kind`, which needs nothing from `core` and survives every combinator, since
combinators wrap rather than rewrite::

    inklet.place(feet, kind=inklet.abutting("chords"))

The claim is scoped to the subtree and it is symmetric: a pair is skipped when
*both* sides sit under the same declared node. A ribbon against a stray label
is still a finding, because the label was never part of the claim.
"""

from __future__ import annotations

__all__ = ["ABUTTING_KIND_SUFFIX", "abutting", "is_abutting_kind"]

#: Appended to the kind rather than replacing it, so every other rule still
#: sees a `chords` group and `inklet.encoded` can be layered on top.
ABUTTING_KIND_SUFFIX = "-abutting"

#: What `abutting()` marks when the caller has no kind of their own in mind.
DEFAULT_KIND = "group"


def abutting(kind: str = DEFAULT_KIND) -> str:
    """Declare that the parts inside this subtree touch by design.

    `OVERLAP` and `CROWDING` skip any pair whose two sides are both inside a
    node carrying the returned kind, and `PATH_CROSSES` skips a stroke against
    ink declared with it::

        inklet.place(ribbons, kind=inklet.abutting("sankey"))

    Idempotent, so wrapping an already-declared kind is harmless.
    """
    return kind if is_abutting_kind(kind) else kind + ABUTTING_KIND_SUFFIX


def is_abutting_kind(kind: str | None) -> bool:
    """Whether a node's kind carries the abutting declaration."""
    return bool(kind) and kind.endswith(ABUTTING_KIND_SUFFIX)
