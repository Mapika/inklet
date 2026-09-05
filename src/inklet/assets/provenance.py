"""Where an asset came from and what was done to it.

A figure that contains someone else's illustration owes them a credit line, and
a figure that contains a photograph the pipeline has cut out, redrawn and
recoloured owes the reader a note that this is what happened. Both are the same
record, so both live here.

Two rules. Nothing is inferred: a file with no recorded licence is reported as
having no recorded licence, never as public domain, never as "unknown, probably
fine". And the transformation chain is recorded as it runs, so `credits()` on a
finished figure describes what the pixels actually went through rather than
what the arguments asked for.

The record lives on the node, as `notes["provenance"]` (core M17). It used to
be held in a module-level registry keyed by diagram id, because `Diagram` had
no place to hang metadata; the consequence was that the record leaked for the
process lifetime, and that it survived neither `copy()` -- which remints every
id in the subtree -- nor a deep copy, so an asset placed twice was credited
once and its second placement not at all. A note travels with the node through
both, and through a placement (M19), and is collected when the node is. The
registry survived one round as a read-only fallback and is now gone: nothing
in the library ever wrote it after the move, and a tree old enough to need it
cannot be built by this version.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from ..core.diagram import Diagram

__all__ = ["Provenance", "record", "provenance_of", "credits", "credit_lines",
           "PROVENANCE_NOTE"]


@dataclass(frozen=True)
class Provenance:
    """The audit trail for one placed asset."""

    source: str                       # the path as the author wrote it
    sha256: str                       # content hash of the source bytes
    pixel_size: tuple[int, int]       # of the source, after EXIF orientation
    subject_box: tuple[int, int, int, int] | None = None   # x0,y0,x1,y1 in source px
    steps: tuple[str, ...] = ()       # the pipeline, in the order it ran
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    notes: str | None = None

    @property
    def short_hash(self) -> str:
        return self.sha256[:12]

    def with_step(self, step: str) -> Provenance:
        return replace(self, steps=self.steps + (step,))

    def credit(self) -> str:
        """One line for a figure caption or a credits block.

        Says "no licence recorded" when there is none, which is the honest
        wording: the file might be public domain, might be a stock image nobody
        paid for, and this library has no way to tell.
        """
        parts = [self.attribution] if self.attribution else []
        parts.append(self.license or "no licence recorded")
        if self.source_url:
            parts.append(self.source_url)
        return f"{self.source}: " + ", ".join(parts)

    def describe(self) -> str:
        """Path, hash and pipeline -- what a methods section needs."""
        chain = " -> ".join(self.steps) if self.steps else "unmodified"
        return f"{self.source} [{self.short_hash}] {chain}"


#: The note an asset keeps its record on.
PROVENANCE_NOTE = "provenance"


def record(diagram: Diagram, provenance: Provenance) -> Provenance:
    """Attach the record to the node, so it travels with it.

    `Diagram.note` mutates and returns the node, which is what the one caller
    (`assets.asset`) wants: it has just built the node and nobody else holds
    it.
    """
    diagram.note(PROVENANCE_NOTE, provenance)
    return provenance


def _recorded(node: Diagram) -> Provenance | None:
    """One node's record, or `None`.

    Reads `notes` defensively rather than by attribute, because this walks
    whatever tree it is handed and a caller's own node type is not core's.
    """
    notes = getattr(node, "notes", None)
    found = notes.get(PROVENANCE_NOTE) if isinstance(notes, Mapping) else None
    return found if isinstance(found, Provenance) else None


def provenance_of(diagram: Diagram) -> Provenance | None:
    """The record for this node, or for the first asset beneath it.

    Walk order is the tree's, so a subtree holding several assets answers with
    the one that draws first. Use `credits()` when you want all of them.
    """
    for node in diagram.walk():
        found = _recorded(node)
        if found is not None:
            return found
    return None


def credits(root: Diagram) -> tuple[Provenance, ...]:
    """Every asset in a tree, in draw order, one entry per distinct file.

    Deduplicated on the content hash rather than on the path, so the same
    picture placed twice -- or reached by two different relative paths -- is
    credited once.
    """
    seen: set[str] = set()
    out = []
    for node in root.walk():
        found = _recorded(node)
        if found is None or found.sha256 in seen:
            continue
        seen.add(found.sha256)
        out.append(found)
    return tuple(out)


def credit_lines(root: Diagram) -> tuple[str, ...]:
    return tuple(p.credit() for p in credits(root))
