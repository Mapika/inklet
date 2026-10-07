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

__all__ = ["rule_label_unplaced", "rule_orphan_leader", "PLACER_NOTES"]

#: The notes a label placer leaves, and what to call the call that left it.
PLACER_NOTES = {
    "point_labels": "label_points",
    "line_labels": "label_lines",
    "place_labels": "place_labels",
    # `Panel.regression(equation=True)`, placed by `plot.regression.defer_equation`.
    "regression_equation": "regression",
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




def rule_orphan_leader(ctx: LintContext) -> list[Diagnostic]:
    """Leaders drawn to a label with no text in it.

    A leader is a line whose only job is to reach a label. When the label is
    empty (`annotate(target, '')`, or a `label_points` entry that is '') the
    line can still be drawn, and it ends at bare paper. Two shapes are checked,
    the two the library draws:

    * an `annotate` call: a `link` leader beside its `annotation-label`;
    * a `label_points` group: the `mark-line` leaders the placer recorded in its
      note, matched to the `label` children in the order the placer drew them.
      The match is only trusted when the counts agree.

    **Grade: warning.** The leader points at nothing, which misleads a reader
    but leaves the rest of the figure intact.
    """
    from ..draw.annotate import ANNOTATION_KIND, ANNOTATION_LABEL_KIND
    from ..links import LINK_KIND
    from ..plot.point_labels import LEADER_KIND, POINT_LABEL_KIND

    out: list[Diagnostic] = []
    for node in ctx.nodes.values():
        if node.kind == ANNOTATION_KIND:
            leaders = [c for c in node.children if c.kind == LINK_KIND]
            if not leaders:
                continue
            labels = [n for n in node.walk() if n.kind == ANNOTATION_LABEL_KIND]
            for leader in leaders:
                out.extend(_orphan(ctx, leader, labels[0] if labels else None))
        elif node.kind == "point-labels":
            note = node.notes.get("point_labels")
            if not isinstance(note, dict) or not note.get("leaders"):
                continue
            lines = [c for c in node.children if c.kind == LEADER_KIND]
            words = [c for c in node.children if c.kind == POINT_LABEL_KIND]
            if len(words) != note.get("count") or len(lines) != len(note["leaders"]):
                continue  # cannot say which label a leader belongs to
            for line, index in zip(lines, sorted(note["leaders"])):
                out.extend(_orphan(ctx, line, words[index]))
    return out


def _orphan(ctx: LintContext, leader, label) -> list[Diagnostic]:
    """The finding for one leader whose label is missing or has no ink."""
    from ..core import PhantomPrim, TextPrim
    from .rules import node_phrase

    if label is not None and any(_inked(step, PhantomPrim, TextPrim)
                                 for step in label.walk()):
        return []
    where = ctx.placements[leader.id].bbox if leader.id in ctx.placements else None
    hint = ("give the label its text, or leave the leader off: "
            "annotate(..., leader=False), or drop the label from the call")
    if label is None:
        message = f"{node_phrase(leader)} is drawn with no label at all"
    else:
        # Name the text node when there is one: that is the thing that is
        # empty, and the wrapper above it is only where the placer put it.
        text_node = next((step for step in label.walk()
                          if isinstance(step.prim, TextPrim)), label)
        message = (f"{node_phrase(leader)} is drawn for an empty label, "
                   f"{node_phrase(text_node, words='')}")
    return [Diagnostic(code="ORPHAN_LEADER", severity="warning", message=message,
                       targets=(leader.id,), where=where, hint=hint)]


def _inked(node, phantom, text) -> bool:
    """Whether a node paints anything: a non-blank word, or any drawn shape."""
    prim = node.prim
    if prim is None or isinstance(prim, phantom):
        return False
    if isinstance(prim, text):
        return bool(prim.text.strip())
    return True
