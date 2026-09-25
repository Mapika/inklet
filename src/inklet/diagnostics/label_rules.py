"""`LABEL_UNPLACED` -- a label the placer could not put down cleanly.

`Panel.label_points`, `Panel.label_lines` and `inklet.place_labels` never
drop a label and never shrink one. When no position is free of other labels,
labelled points, solid marks and crossing leaders, they draw the label at the
least bad position and record it in their note (`point_labels`,
`line_labels` or `place_labels`) under `unresolved`. This rule turns that
record into a finding, so a collision the placer knew about is reported by
name rather than left for `OVERLAP` or `CROWDING` to half-describe -- or,
when the collision is with a curve those rules exempt, not described at all.

**Grade: warning.** The figure prints, but something in it is covered.
"""

from __future__ import annotations

from .rules import Diagnostic, LintContext

__all__ = ["rule_label_unplaced", "PLACER_NOTES"]

#: The notes a label placer leaves, and what to call the call that left it.
PLACER_NOTES = {
    "point_labels": "label_points",
    "line_labels": "label_lines",
    "place_labels": "place_labels",
}


def rule_label_unplaced(ctx: LintContext) -> list[Diagnostic]:
    """Labels a placer reported it could not place without a collision."""
    out: list[Diagnostic] = []
    seen: set[int] = set()
    for node in ctx.root.walk():
        for key, call in PLACER_NOTES.items():
            note = node.notes.get(key)
            if not isinstance(note, dict):
                continue
            stuck = [str(name) for name in note.get("unresolved", ())]
            # A deferred call's holder and its result carry the same note.
            if not stuck or id(note) in seen:
                continue
            seen.add(id(note))
            here = ctx.placements.get(node.id)
            shown = ", ".join(repr(name) for name in stuck[:6])
            more = f" and {len(stuck) - 6} more" if len(stuck) > 6 else ""
            out.append(Diagnostic(
                code="LABEL_UNPLACED",
                severity="warning",
                message=(f"{call}() could not place {len(stuck)} of "
                         f"{note.get('count', len(stuck))} labels clear of "
                         f"everything else: {shown}{more}"),
                targets=(node.id,),
                where=here.bbox if here is not None else None,
                hint=("give the labels more room (a larger panel or plot "
                      "area, smaller type, fewer labels) or shorten them; "
                      "the note's `unresolved` list names them"),
            ))
    return out
