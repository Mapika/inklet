"""`decorative(kind)` -- "this text is meant to recede".

A pale year behind the bubbles is the signature of the Gapminder chart; a
faint "DRAFT" across a panel, a large background numeral in an infographic,
are the same thing. They are *supposed* to fail a contrast test: legibility is
not what they are for, and `LOW_CONTRAST` reporting them asks the author to
make the watermark shout. The alternative was a translucent fill, which the
rule could not read and so did not check -- a loophole rather than a choice,
and one that also hid every translucent caption that genuinely was too faint.
`LOW_CONTRAST` now composites translucent text like any other
(ISSUES-medicine-econ 5), so the opt-out has to be said out loud.

It is spelled the way `inklet.abutting(kind)` is, as a suffix on the node's
kind, because that needs nothing from `core` and survives every combinator::

    p.text(30000, 33, "2007", size=inklet.pt(40), text_fill="#e6e8eb",
           kind=inklet.diagnostics.decorative(), front=False)

`Panel.text` hands `kind=` to the wrapper it places the words with, and the
declaration covers the whole subtree. A node can also carry the
`DECORATIVE_NOTE` note (any truthy value), which is how a builder that already
owns the kind -- `Panel.text(decorative=True)`, for one -- can say the same.

The claim is narrow on purpose: it exempts the text from `LOW_CONTRAST` and
nothing else. A decorative word that runs off the page, is set at 3 pt, or
sits on top of a data label is still reported.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["DECORATIVE_KIND_SUFFIX", "DECORATIVE_NOTE", "decorative",
           "is_decorative_kind", "is_decorative_node"]

#: Appended to the kind rather than replacing it, as `abutting` does.
DECORATIVE_KIND_SUFFIX = "-decorative"

#: The note a builder may set instead of changing the kind.
DECORATIVE_NOTE = "decorative"

#: What `decorative()` marks when the caller has no kind in mind: the kind
#: `Panel.text` gives its wrapper.
DEFAULT_KIND = "label"


def decorative(kind: str = DEFAULT_KIND) -> str:
    """Declare the text inside this subtree decorative: `LOW_CONTRAST` skips it.

        p.text(x, y, "2007", text_fill="#e6e8eb", kind=inklet.diagnostics.decorative())

    Idempotent, so wrapping an already-declared kind is harmless.
    """
    return kind if is_decorative_kind(kind) else kind + DECORATIVE_KIND_SUFFIX


def is_decorative_kind(kind: str | None) -> bool:
    """Whether a node's kind carries the decorative declaration.

    Anywhere in the kind, not only at the end, so it composes with the other
    suffix declarations: `abutting(decorative("label"))` is both.
    """
    return bool(kind) and DECORATIVE_KIND_SUFFIX in kind


def is_decorative_node(node) -> bool:
    """Whether this one node declares itself decorative, by kind or by note."""
    if node is None:
        return False
    if is_decorative_kind(getattr(node, "kind", None)):
        return True
    notes = getattr(node, "notes", None)
    return isinstance(notes, Mapping) and bool(notes.get(DECORATIVE_NOTE))
