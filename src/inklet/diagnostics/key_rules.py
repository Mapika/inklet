"""Does the colour key describe the marks beside it?

A key is the one part of a figure that can be *completely* wrong and still look
perfect. A colorbar built from one ramp beside a heatmap built from another is
two well-drawn objects with nothing between them to collide, overflow or run
off the page; a legend listing a category nobody in the cohort had is a tidy row
of type. Every other rule here asks whether the ink is where it should be. This
one asks whether it means what it says.

The comparison is made in colour, because colour is what both sides actually
put on the page and what the reader compares. A `Scale` is a Python object that
leaves no trace in the tree -- `Panel.matrix(scale=)` and `colorbar(scale=)`
both take one and neither records which one it was -- so a rule that wanted to
compare *scales* would have to be handed them. What it can compare, exactly and
today, is the set of colours in the key against the set of colours in the panel
next to it, and that catches both of the failures actually observed:

* a bar and a matrix drawn from two different ramps (an error: the numbers
  under the bar name colours the picture does not contain), and
* a legend swatch for a colour drawn nowhere, or a mark colour with no swatch
  (a warning: the key and the picture disagree about what is in the figure).

What it cannot see is two *domains* over one ramp -- a bar reading 0..100 over
a matrix mapped 0..10 -- because both draw the same colours. `_declared_domain`
is the hook for that: a `scale_domain` note carrying `(low, high)` on the key
node and on the marks group makes the mismatch visible without any colour
arithmetic, and `inklet.plot` now leaves one -- see
`plot/scale.py::_declare_domain`.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

from ..core import Rect
# The kinds the plot layer stamps on its own furniture. Reading them from
# there rather than restating the strings is the difference between a rule
# that follows a rename and one that goes quiet after it.
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..plot.axis import (AXIS_KIND, AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND,
                         TICK_LABEL_KIND)
from ..plot.key import BAND_KIND, COLORBAR_KIND, LEGEND_KIND
from ..plot.panel import AREA_KIND, GRID_KIND, PANEL_KIND, TITLE_KIND
from ..plot.raster import MATRIX_KIND
from ..themes.color import ColorError, parse_color, to_hex, to_lab
from .rules import Diagnostic, Item, LintContext, _gap, _opaque_fill

__all__ = ["rule_key_mismatch"]

#: CIE76 distance at which two colours are the same colour. Just-noticeable is
#: about 2.3; both sides of every comparison here come from the same arithmetic
#: on the same stops, so a real match is 0 and this is rounding slack.
_SAME_DE = 2.0

#: How far off the bar's ramp a colour has to fall to count as not on it. Wider
#: than `_SAME_DE` because the ramp is sampled at 128 points rather than
#: continuous, and a colour genuinely on it can land between two samples.
_OFF_RAMP_DE = 5.0

#: A colorbar is only contradicted when *most* of the marks disagree with it.
#: One odd cell -- a "not measured" grey over a heatmap -- is an annotation,
#: not a different scale, and reporting it would teach an author to ignore the
#: rule on the figures where it is right.
_OFF_RAMP_FRACTION = 0.5

#: Above this many distinct mark fills the panel is showing a continuous field,
#: not a set of categories, and "this colour has no swatch" stops being a
#: sentence anyone can act on.
_CATEGORICAL_MAX = 12

#: Distinct mark colours a panel needs before a colorbar beside it is taken to
#: be *its* key. A continuous field paints a colour per value, so two or fewer
#: says the marks are categorical and the bar belongs to something else on the
#: sheet -- `stress/draw_probe.py` parks a z-score bar next to two line panels,
#: and calling that an error would be the linter guessing at layout intent.
#: The legend half has no such guard: a legend beside a one-colour panel really
#: is claiming to describe it.
_MIN_RAMPED_COLOURS = 3

#: Panel parts that are furniture rather than data. A tinted plot area, a
#: gridline and a spine are all opaque ink in the panel, and none of them is
#: something a key would ever have an entry for.
_FURNITURE_KINDS = frozenset({
    AXIS_KIND, AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND, TICK_LABEL_KIND,
    AREA_KIND, GRID_KIND, TITLE_KIND,
})

_KEY_KINDS = (COLORBAR_KIND, LEGEND_KIND)


def rule_key_mismatch(ctx: LintContext) -> list[Diagnostic]:
    """A colour key that does not describe the marks it stands next to.

    Each key is paired with one panel -- the one sharing the deepest ancestor
    with it, nearest first on a tie, so `vstack([panel, legend])` and
    `hstack([panel, colorbar])` both pair the way they read. A key with no
    panel anywhere near it, or a panel with nothing coloured in it, is left
    alone: there is nothing to compare and inventing a pairing across a
    seven-panel sheet would produce a finding about two unrelated things.

    A colorbar against marks is an **error**. The bar is a claim that these
    colours mean these numbers, and when the marks are drawn from a different
    ramp the claim is false -- the reader takes a value off the bar and gets an
    answer the figure never encoded.

    A legend against marks is a **warning**, in both directions, because the
    honest reasons exist: a swatch for a series that happens to be empty in
    this cohort is a mistake nine times out of ten and a deliberate constant
    key across a facet grid the tenth.
    """
    keys = [node_id for node_id, node in ctx.nodes.items()
            if node.kind in _KEY_KINDS]
    if not keys:
        return []
    panels = [node_id for node_id, node in ctx.nodes.items()
              if node.kind == PANEL_KIND]
    if not panels:
        return []

    # `Placement.bbox` unions a whole subtree's envelope and is recomputed on
    # every read, so a sheet with four keys and seven panels would build the
    # same twenty-eight boxes over and over. Once each.
    boxes: dict[str, Rect | None] = {}
    paired = [(key_id, _nearest_panel(ctx, key_id, panels, boxes))
              for key_id in sorted(keys)]
    paired = [(key_id, panel_id) for key_id, panel_id in paired
              if panel_id is not None]
    if not paired:
        return []
    members = _members(ctx, {node_id for pair in paired for node_id in pair})

    out: list[Diagnostic] = []
    for key_id, panel_id in paired:
        key, panel = members[key_id], members[panel_id]      # type: ignore[index]
        where = _union(boxes.get(key_id), boxes.get(panel_id))
        if ctx.nodes[key_id].kind == COLORBAR_KIND:
            out.extend(_colorbar_findings(ctx, key_id, panel_id, key, panel, where))
        else:
            out.extend(_legend_findings(ctx, key_id, panel_id, key, panel, where))
    return out


# -- pairing --------------------------------------------------------------


def _nearest_panel(ctx: LintContext, key_id: str, panels: Sequence[str],
                   boxes: dict[str, "Rect | None"]) -> str | None:
    """The panel a key belongs to, chosen the same way every time.

    Structure first: the panel and its key are almost always stacked together,
    so the deepest common ancestor picks the right one on a sheet of seven
    without any geometry at all. Distance breaks the tie for a figure that
    composes them side by side under one group, and the node id breaks that.
    """
    key_box = _box(ctx, key_id, boxes)
    if key_box is None:
        return None
    best: tuple[int, float, str] | None = None
    for panel_id in panels:
        if ctx.is_related(key_id, panel_id):
            continue        # a key drawn inside its own panel needs no pairing
        panel_box = _box(ctx, panel_id, boxes)
        if panel_box is None:
            continue
        shared = len(_common_prefix(ctx.chain(key_id), ctx.chain(panel_id)))
        score = (-shared, _gap(key_box, panel_box), panel_id)
        if best is None or score < best:
            best = score
    if best is None or _has_own_subject(ctx, key_id, best[2]):
        return None
    return best[2]


def _has_own_subject(ctx: LintContext, key_id: str, panel_id: str) -> bool:
    """True when the key already sits beside ink of its own.

    Below the ancestor the key shares with the panel, the key's side of the
    split is either the key alone (stacked under the panel it describes) or a
    composite that brought its own subject -- a 3D cell with a streams key
    in its margin, a graph with a key for its edge widths. In the second case
    the nearest *plot panel* on the sheet is the wrong partner, and pairing
    them reports a key for colours the panel never had any business drawing.
    Text does not count as a subject: a caption stacked under the key is
    still just a key.
    """
    key_chain, panel_chain = ctx.chain(key_id), ctx.chain(panel_id)
    shared = len(_common_prefix(key_chain, panel_chain))
    if shared >= len(key_chain):
        return False
    branch = key_chain[shared]
    if branch == key_id:
        return False
    own = {item.node.id for item in _members(ctx, (key_id,)).get(key_id, ())}
    for item in _members(ctx, (branch,)).get(branch, ()):
        if item.node.id not in own and not item.is_text:
            return True
    return False


def _common_prefix(a: Sequence[str], b: Sequence[str]) -> list[str]:
    shared: list[str] = []
    for mine, theirs in zip(a, b):
        if mine != theirs:
            break
        shared.append(mine)
    return shared


def _box(ctx: LintContext, node_id: str,
         boxes: dict[str, "Rect | None"]) -> Rect | None:
    if node_id not in boxes:
        placement = ctx.placements.get(node_id)
        boxes[node_id] = None if placement is None else placement.bbox
    return boxes[node_id]


def _union(a: Rect | None, b: Rect | None) -> Rect | None:
    if a is None:
        return b
    return a if b is None else a.union(b)


# -- colours in a subtree -------------------------------------------------


def _members(ctx: LintContext, roots: Iterable[str]) -> dict[str, list[Item]]:
    """{root id: the drawable items under it}, in document order.

    Downward from each root rather than upward from every item. The upward
    spelling is one line shorter and asks 3,770 nodes whether they are inside
    a 200-node panel; on a seven-panel sheet that made this the second most
    expensive rule in the linter, behind OVERLAP and ahead of everything the
    figure actually has.

    Furniture subtrees are pruned rather than filtered, which is both faster
    and the correct test: an axis is a group of ticks and text, and only the
    group says what it is.
    """
    found: dict[str, list[Item]] = {}
    for root in roots:
        node = ctx.nodes.get(root)
        if node is None:
            continue
        items: list[Item] = []
        stack = [node]
        while stack:
            current = stack.pop()
            item = ctx.item(current.id)
            if item is not None and item.draws:
                items.append(item)
            stack.extend(reversed([child for child in current.children
                                   if child.kind not in _FURNITURE_KINDS]))
        found[root] = items
    return found


def _paints(items: Iterable[Item], *, fills_only: bool = False,
            kinds: frozenset[str] | None = None) -> dict[str, int]:
    """{normalised colour: how many nodes are painted in it}.

    Strokes count as well as fills unless asked otherwise, because a legend for
    a set of *lines* lists the colours those lines are stroked in and nothing
    in the panel is filled with them at all. Counting the reverse direction --
    an unlisted colour -- is fills only, since a resolved stroke is inherited
    from the theme by everything that did not set one.
    """
    found: dict[str, int] = {}
    for item in items:
        if item.is_text:
            continue
        if kinds is not None and item.node.kind not in kinds:
            continue
        values = [item.style.fill]
        if not fills_only:
            values.append(item.style.stroke)
        for value in values:
            if not _opaque_fill(value):
                continue
            name = _normal(str(value))
            if name is not None:
                found[name] = found.get(name, 0) + 1
    return found


def _normal(value: str) -> str | None:
    """A colour as `#rrggbb`, or None when it is not a colour this can read."""
    try:
        return to_hex(parse_color(value))
    except (ColorError, ValueError, TypeError):
        return None


#: Lab coordinates of every colour this rule has seen. A 128-band ramp against
#: forty cell colours is five thousand comparisons of a few dozen distinct
#: strings, and the parse is the whole of the cost.
_LAB: dict[str, tuple[float, float, float] | None] = {}


def _lab(colour: str) -> tuple[float, float, float] | None:
    if colour not in _LAB:
        try:
            _LAB[colour] = to_lab(colour)
        except (ColorError, ValueError, TypeError):
            _LAB[colour] = None
    return _LAB[colour]


def _nearest(colour: str, others: Iterable[str]) -> float:
    """CIE76 distance to the closest of `others`, inf when nothing compares."""
    mine = _lab(colour)
    if mine is None:
        return float("inf")
    best = float("inf")
    for other in others:
        theirs = _lab(other)
        if theirs is None:
            continue
        squared = sum((a - b) ** 2 for a, b in zip(mine, theirs))
        if squared < best:
            best = squared
    return math.sqrt(best) if best < float("inf") else best


def _listed(colours: Iterable[str], limit: int = 4) -> str:
    ordered = sorted(colours)
    shown = ", ".join(ordered[:limit])
    if len(ordered) > limit:
        shown += f", +{len(ordered) - limit} more"
    return shown


# -- (a) a colorbar against the marks it stands beside --------------------


def _colorbar_findings(ctx: LintContext, key_id: str, panel_id: str,
                       key: Sequence[Item], panel: Sequence[Item],
                       where: Rect | None) -> list[Diagnostic]:
    ramp = _ramp_colours(key)
    marks = _paints(panel, fills_only=True, kinds=frozenset({MARK_KIND}))
    marks.update(_matrix_colours(panel))
    if len(ramp) < 2 or len(marks) < _MIN_RAMPED_COLOURS:
        return []

    declared = _domain_clash(ctx, key_id, panel_id)
    off = sorted(colour for colour in marks
                 if _nearest(colour, ramp) > _OFF_RAMP_DE)
    if declared is None and len(off) <= len(marks) * _OFF_RAMP_FRACTION:
        return []

    low, high = ramp[0], ramp[-1]
    if declared is not None:
        detail = (f"the bar is labelled over {declared[0]} and the cells were "
                  f"mapped over {declared[1]}")
    else:
        detail = (f"{len(off)} of the {len(marks)} colours in "
                  f"{ctx.label(panel_id)} are not on it ({_listed(off)})")
    return [Diagnostic(
        code="KEY_MISMATCH",
        severity="error",
        message=(f"{ctx.label(key_id)} ramps {low} -> {high} but {detail}; the "
                 f"numbers under the bar name colours the panel does not use"),
        targets=tuple(sorted((key_id, panel_id))),
        where=where,
        hint=("give colorbar() and matrix()/marks() the same ramp= and the "
              "same scale= object -- two that merely agree today is how a key "
              "ends up describing a picture it no longer matches"),
    )]


def _ramp_colours(key: Sequence[Item]) -> list[str]:
    """The bar's bands, low value first.

    Ordered along the bar rather than by id, because the message quotes the two
    ends and a bar that reported them the wrong way round would send an author
    looking for a reversed ramp that is not there. `_bands` paints low value at
    the bottom of a vertical bar, which is why the y order is inverted.
    """
    bands = [item for item in key if item.node.kind == BAND_KIND]
    if not bands:
        return []
    span_x = max(b.bbox.center.x for b in bands) - min(b.bbox.center.x for b in bands)
    span_y = max(b.bbox.center.y for b in bands) - min(b.bbox.center.y for b in bands)
    if span_y > span_x:
        bands.sort(key=lambda b: (-b.bbox.center.y, b.id))
    else:
        bands.sort(key=lambda b: (b.bbox.center.x, b.id))
    ordered: list[str] = []
    for band in bands:
        name = _normal(str(band.style.fill)) if _opaque_fill(band.style.fill) else None
        if name is not None and (not ordered or ordered[-1] != name):
            ordered.append(name)
    return ordered


def _matrix_colours(panel: Sequence[Item]) -> dict[str, int]:
    """The colours a rasterised matrix painted, read off the note it leaves.

    A vector matrix is a grid of filled rectangles and `_paints` can read it
    straight off the tree. A rasterised one is a single `ImagePrim`, and its
    cell colours are inside a PNG -- so the bar beside it could ramp anything
    at all and the colour test had nothing to compare. `plot.raster` leaves
    them behind for exactly this: `ramp_colours`, the distinct colours the
    matrix actually painted, low value first.

    The count is one per colour rather than one per cell, which is what
    `_OFF_RAMP_FRACTION` wants: "most of the colours are off the ramp", not
    "most of the pixels are", so a 60 x 60 matrix does not outvote itself.
    """
    found: dict[str, int] = {}
    for item in panel:
        if item.node.kind != MATRIX_KIND:
            continue
        for colour in _note(item.node, "ramp_colours") or ():
            name = _normal(str(colour))
            if name is not None:
                found[name] = found.get(name, 0) + 1
    return found


def _note(node, key: str):
    """A value the plot layer left on a node, or None if it left none.

    `Diagram.notes` (core M17) is a field, so a note survives `replace`,
    `apply_theme` and `build` -- which matters because a rule only ever sees
    the built tree. Read through `getattr` so that a hand-built node, or one
    from a core that predates the slot, simply has nothing to say.
    """
    notes = getattr(node, "notes", None)
    return notes.get(key) if isinstance(notes, Mapping) else None


def _domain_clash(ctx: LintContext, key_id: str,
                  panel_id: str) -> tuple[str, str] | None:
    """The two numeric domains, when both sides bothered to record one.

    `plot/scale.py::_declare_domain` notes `scale_domain` on the colorbar and
    on the marks group, and `Diagram.notes` is a field, so the rebuild carries
    it without anyone copying it by name: a bar built over `linear((0, 100))`
    beside a matrix mapped through `linear((0, 10))` reports the mismatch even
    though both draw the same colours, which is the one case the colour test
    above cannot see.

    `None` when either side is silent -- a `Band` has categories rather than a
    range and never records one.
    """
    key = _declared_domain(ctx.nodes.get(key_id))
    marks = _declared_domain(ctx.nodes.get(panel_id))
    if key is None or marks is None or key == marks:
        return None
    return (f"{key[0]:g}..{key[1]:g}", f"{marks[0]:g}..{marks[1]:g}")


def _declared_domain(node) -> tuple[float, float] | None:
    value = _note(node, "scale_domain")
    try:
        low, high = value            # type: ignore[misc]
        return (float(low), float(high))
    except (TypeError, ValueError):
        return None


# -- (b) a legend against the marks it stands beside ----------------------


def _legend_findings(ctx: LintContext, key_id: str, panel_id: str,
                     key: Sequence[Item], panel: Sequence[Item],
                     where: Rect | None) -> list[Diagnostic]:
    swatches = _swatches(ctx, key_id, key)
    if not swatches:
        return []
    ink = _paints(panel)
    if not ink:
        return []

    out: list[Diagnostic] = []
    absent = {colour: names for colour, names in swatches.items()
              if _nearest(colour, ink) > _SAME_DE}
    if absent:
        named = ", ".join(f"{colour} ({names})" if names else colour
                          for colour, names in sorted(absent.items()))
        out.append(Diagnostic(
            code="KEY_MISMATCH",
            severity="warning",
            message=(f"{ctx.label(key_id)} has {len(absent)} entr"
                     f"{'y' if len(absent) == 1 else 'ies'} for colours drawn "
                     f"nowhere in {ctx.label(panel_id)}: {named}"),
            targets=tuple(sorted((key_id, panel_id))),
            where=where,
            hint=("build the key from the values actually plotted -- "
                  "{classify(v) for v in data} -- rather than from the full "
                  "set of categories, or drop the entries that are empty here"),
        ))

    marks = _paints(panel, fills_only=True,
                    kinds=frozenset({MARK_KIND, MARK_LINE_KIND}))
    if 0 < len(marks) <= _CATEGORICAL_MAX:
        unlisted = sorted(colour for colour in marks
                          if _nearest(colour, swatches.keys()) > _SAME_DE)
        if unlisted:
            out.append(Diagnostic(
                code="KEY_MISMATCH",
                severity="warning",
                message=(f"{ctx.label(panel_id)} draws marks in "
                         f"{len(unlisted)} colour"
                         f"{'' if len(unlisted) == 1 else 's'} "
                         f"{ctx.label(key_id)} does not list: "
                         f"{_listed(unlisted)}"),
                targets=tuple(sorted((key_id, panel_id))),
                where=where,
                hint=("add an entry for each, or colour those marks with one "
                      "of the classes the key already names"),
            ))
    return out


def _swatches(ctx: LintContext, key_id: str,
              key: Sequence[Item]) -> dict[str, str]:
    """{colour: the entry text beside it}, for one legend.

    The name is worth the walk: "#1b5e20 (complete)" tells an author which row
    to delete, where a bare hex tells them to go and look.
    """
    rows = _entry_rows(ctx, key_id, key)
    found: dict[str, str] = {}
    for item in key:
        if item.is_text:
            continue
        for value in (item.style.fill, item.style.stroke):
            if not _opaque_fill(value):
                continue
            name = _normal(str(value))
            if name is None:
                continue
            found.setdefault(name, _row_text(ctx, item.id, key_id, rows))
    return found


def _entry_rows(ctx: LintContext, key_id: str,
                key: Sequence[Item]) -> dict[str, str]:
    """{group id: the words under it}, for every group inside one legend.

    Built in one pass over the key's own type so that finding a swatch's row is
    a walk up its chain rather than another scan of the whole figure.
    """
    rows: dict[str, str] = {}
    for item in key:
        if not item.is_text:
            continue
        chain = ctx.chain(item.id)
        words = " ".join(item.prim.text.split())[:40]   # type: ignore[union-attr]
        for step in chain[chain.index(key_id):]:
            rows.setdefault(step, words)
    return rows


def _row_text(ctx: LintContext, swatch_id: str, key_id: str,
              rows: Mapping[str, str]) -> str:
    """The words in the smallest group holding both this swatch and some type.

    A legend row is `hstack([swatch, text])`, so walking up from the swatch
    until a group with type in it appears finds that row and stops before the
    whole key -- whose own entry names the first row and is never reached.
    """
    chain = ctx.chain(swatch_id)
    for step in reversed(chain[chain.index(key_id) + 1:]):
        words = rows.get(step)
        if words:
            return words
    return ""
