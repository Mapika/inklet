"""Metadata plot nodes carry for diagnostics and other tree readers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scale import Scale


def declare_domain(node, scale: "Scale | None") -> None:
    """Record on `node` the numeric domain its colours were mapped through.

    `inklet.diagnostics` checks a key against the picture beside it by comparing
    colours, and colour is blind to the one mismatch that matters most: a bar
    labelled 0..100 over a matrix mapped 0..10 draws exactly the same pixels.
    The rule reads the node's `scale_domain` note, so this is the plot layer
    leaving it. It is a note and nothing else: `Diagram.note` (core M17) is a
    real field, so `replace`, `apply_theme` and `build` all carry it, where the
    plain attribute this used to stamp beside it lived only as long as the node
    did and had to be hand-copied across the rebuild in `figure.py`.

    Silent when there is no scale, or when its domain is not two numbers -- a
    `Band` has categories, not a range, and two band scales cannot disagree
    about one.

    Silent for a `Broken` scale too, and that one is worth spelling out. Its
    `domain` is a pair of numbers and would be accepted here, but it is the two
    outer ends and not what the scale covers: a `broken((0, 400),
    breaks=[(45, 330)])` never maps anything to 200. Declaring `(0, 400)`
    would let a key and a picture that genuinely disagree agree on paper, which
    is the one failure `KEY_MISMATCH` exists to prevent, so the note is left
    off and the rule stays quiet instead of being lied to.
    """
    if scale is None or node is None:
        return
    if getattr(scale, "segments", None) is not None:
        return
    domain = getattr(scale, "domain", None)
    if not isinstance(domain, tuple) or len(domain) != 2:
        return
    try:
        low, high = float(domain[0]), float(domain[1])
    except (TypeError, ValueError):
        return
    annotate(node, "scale_domain", (low, high))


def annotate(node, key: str, value) -> None:
    """Leave `value` on `node` under `key`, as a note and only as a note.

    `Diagram.note` (core M17) is a real field, so `replace`, `apply_theme` and
    `build` all carry it and a rule reads it off the built tree -- the only
    tree a rule ever sees. This used to stamp a plain instance attribute
    beside the note as well, for readers written before M17; nothing reads one
    any more, and the attribute was the reason `figure.py::apply_theme` had to
    lift `scale_domain` across the rebuild by name.

    Silent on a node that cannot take a note, which is how this file goes on
    working against a core that predates the slot.
    """
    note = getattr(node, "note", None)
    if callable(note):
        note(key, value)
