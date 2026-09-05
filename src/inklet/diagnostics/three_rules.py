"""`DEPTH_ORDER` -- does a scene's paint order agree with its camera?

Everything else in `inklet.diagnostics` is pure geometry over the resolved tree,
and deliberately so. This rule is the one that cannot be: a drawing of a 3D
scene has thrown its third dimension away by the time there is a tree to read,
and "the objective is in front of the sample plane" is a claim about the
dimension that is gone. So this module asks `inklet.three` what it drew, and is
kept in a file of its own because that dependency is worth being able to see.

The hardest requirement in the blind-02 brief was that the objective be in
front of the sample plane. The agent got it right and nothing checked it, which
makes a correct figure indistinguishable from a lucky one -- and the same hole
had already been paid for twice on the electrolyser poster, where a nut
standing proud of an end plate sorted behind it and a rod threaded through nine
plates came out lying on a face it passes through.

Two questions, one measurement.

**Is any part painted over something it is behind?** `scene(order="parts")`
gives each part one depth, its centre's, and paints furthest first. Where a
part's centre is not where its geometry is, that answer is wrong, and the
picture shows a plate through a bolt. The rule rasterises each part's own near
and far surface into one shared page grid and reads the pair back: a finding
needs the later-painted part to be behind the earlier one at **every** cell the
two share, which is strict on purpose -- two solids that interleave are
ordinary, and a rule that fires on a well-formed figure teaches its reader to
ignore it.

**Does the drawing meet what the author said it must?** `scene(assert_order=
[("objective", "sample")])` is the positive form, and the only way a
requirement like that can survive being re-run against different data. It is
reported as an error rather than a warning, because unlike the finding above
there is no judgement in it: the author wrote down what the picture has to
show.

A part whose place the author set with `draw_order=`, `behind=` or
`in_front_of=` is not checked. Overriding the depth order is what those exist
for, and reporting the override as a mistake would be the rule arguing with the
answer it would itself have suggested.
"""

from __future__ import annotations

from ..core import Rect
from .rules import Diagnostic, LintContext, _mm

__all__ = ["rule_depth_order"]

#: The node kind `inklet.three` wraps a model or a scene in. Compared as a string
#: rather than imported, so that linting a figure with no 3D in it never pays
#: for importing the 3D package -- the same reason `_FUSED_KIND` is spelled out
#: in `rules.py`.
_MODEL_KIND = "model"


def rule_depth_order(ctx: LintContext) -> list[Diagnostic]:
    """A scene part painted over something it lies behind.

    Silent unless the figure contains a `inklet.scene`, and silent on
    `order="exact"` scenes except for an explicit `assert_order=`, because
    there depth is already settled facet by facet and there is no per-part
    order left to be wrong.
    """
    scenes = _scenes(ctx)
    if not scenes:
        return []
    from ..three.depth import behind_everywhere, depth_field

    out: list[Diagnostic] = []
    for node_id in sorted(scenes):
        paint = scenes[node_id]
        frame, span = _frame(paint)
        if frame is None:
            continue
        fields = [depth_field(mesh, paint.view, frame) for mesh in paint.meshes]
        label = ctx.label(node_id)
        if not paint.fused:
            out.extend(_misordered(ctx, paint, fields, label, span,
                                   behind_everywhere))
        out.extend(_asserted(ctx, paint, fields, label, span,
                             behind_everywhere))
    return out


def _scenes(ctx: LintContext) -> dict:
    """Every `inklet.scene` in this tree, by node id. Empty for a flat figure."""
    candidates = [node_id for node_id, node in ctx.nodes.items()
                  if node.kind == _MODEL_KIND]
    if not candidates:
        return {}
    from ..three.api import scene_paint

    found = {}
    for node_id in candidates:
        paint = scene_paint(ctx.nodes[node_id])
        if paint is not None:
            found[node_id] = paint
    return found


def _frame(paint) -> tuple[Rect | None, float]:
    """The page rectangle every part is rasterised into, and the depth range.

    One frame for the whole scene, so that two parts' grids line up cell for
    cell and comparing them is a dictionary lookup rather than a resampling.
    """
    box = None
    near = far = None
    for mesh in paint.meshes:
        if mesh.is_empty:
            continue
        points, depths = paint.view.project_all(mesh.vertices)
        here = Rect.hull(points)
        box = here if box is None else box.union(here)
        low, high = min(depths), max(depths)
        near = low if near is None else min(near, low)
        far = high if far is None else max(far, high)
    if box is None or box.width <= 0.0:
        return None, 0.0
    return box, (far - near) if near is not None else 0.0


def _misordered(ctx: LintContext, paint, fields, label: str, span: float,
                behind_everywhere) -> list[Diagnostic]:
    """Pairs where the painter and the camera disagree.

    Only the pairs the paint order actually decides: `front` is painted after
    `back`, so it covers it, and the finding is that it should not.
    """
    out: list[Diagnostic] = []
    for place, index in enumerate(paint.paint):
        if index in paint.declared or not fields[index]:
            continue
        for under in paint.paint[:place]:
            if under in paint.declared or not fields[under]:
                continue
            verdict = behind_everywhere(fields[index], fields[under], span=span)
            if verdict is None:
                continue
            _, clearance = verdict
            front, back = paint.names[index], paint.names[under]
            out.append(Diagnostic(
                code="DEPTH_ORDER",
                severity="warning",
                message=(
                    f"{label}: {front} is painted over {back}, but lies "
                    f"{_mm(clearance * paint.view.scale)} behind it everywhere "
                    f"the two overlap"),
                targets=_targets(paint, index, under),
                where=_where(fields[index], fields[under]),
                hint=('scene(order="exact") settles depth facet by facet '
                      'across the parts, which is what a part whose centre is '
                      'not where its geometry is needs; if the paint order is '
                      f'deliberate, say so with in_front_of={back!r} on '
                      f'{front} or draw_order='),
            ))
    return out


def _asserted(ctx: LintContext, paint, fields, label: str, span: float,
              behind_everywhere) -> list[Diagnostic]:
    """`assert_order=[("objective", "sample")]`, checked against the drawing.

    Three ways one claim can fail, and they want different sentences: the
    named part is painted first, so it is covered; the two do not meet on the
    page at all, so nothing in the picture says which is in front; or it is
    painted in front and is behind.
    """
    out: list[Diagnostic] = []
    for front, back in paint.claims:
        index, under = paint.names.index(front), paint.names.index(back)
        wrong = None
        if not paint.fused and paint.position(index) < paint.position(under):
            wrong = (f"{back} is painted over it", "check")
        elif not fields[index] or not fields[under] or _where(
                fields[index], fields[under]) is None:
            wrong = ("the two do not overlap on the page, so nothing in the "
                     "drawing says which is in front", "turn")
        else:
            verdict = behind_everywhere(fields[index], fields[under], span=span)
            if verdict is not None:
                wrong = (f"it lies {_mm(verdict[1] * paint.view.scale)} behind "
                         f"{back} everywhere the two overlap", "move")
        if wrong is None:
            continue
        why, fix = wrong
        out.append(Diagnostic(
            code="DEPTH_ORDER",
            severity="error",
            message=f"{label}: {front} was asserted in front of {back}, but {why}",
            targets=_targets(paint, index, under),
            where=_where(fields[index], fields[under]),
            hint=_ASSERT_HINTS[fix],
        ))
    return out


_ASSERT_HINTS = {
    "check": ("give the part the place you meant with in_front_of= or "
              "draw_order=, or drop the assertion if what it claims has "
              "stopped being true"),
    "turn": ("turn the camera until the two really do overlap, or drop the "
             "assertion -- it is not a claim this view can show"),
    "move": ("move the geometry: the assertion is about where the parts are, "
             "and no paint order can put a part in front of something it is "
             "behind. scene(order=\"exact\") will at least draw the truth"),
}


def _targets(paint, index: int, under: int) -> tuple[str, ...]:
    """The two part nodes, in id order, so the report sorts deterministically."""
    return tuple(sorted((paint.nodes[index], paint.nodes[under])))


def _where(front, back) -> Rect | None:
    if front.box is None or back.box is None:
        return None
    return front.box.overlap(back.box)
