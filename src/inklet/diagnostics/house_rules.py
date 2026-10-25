"""House rules: a figure set's own style, checked like any other lint rule.

A journal states limits (`min_font_pt`, `max_font_pt`, `expected_fonts`); a lab
or a project adds rules of its own on top -- two line weights, filled markers
without outlines, no grey annotation text, bold only for panel letters, no keys
inside panels. Written down only in a style guide, those rules drift: the
weights get restated in every script, and literal widths creep in that
disagree with them.

`HouseRules` states them once. `lint(..., house=HouseRules(...))` (and
`Figure.lint`, `CompiledFigure.lint`) then runs five more codes, each a
warning naming the node and the value that broke the rule:

* ``STROKE_TIER`` -- an author's stroke inside a plot panel whose width is not
  one of `stroke_tiers` (mm). Axis, key and colour-bar strokes are the
  library's and are not counted; nor are widths declared as data
  (`inklet.encoded`) or marker outlines (see ``MARKER_OUTLINE``).
* ``MARKER_OUTLINE`` -- a filled data marker drawn with an outline in another
  colour, when `marker_outlines=False`. An open marker (paper or no fill, a
  ring in the series colour) is not an outline.
* ``MUTED_TEXT`` -- text in a grey (OKLab chroma under `muted_chroma`)
  lighter than `muted_lightness` (OKLab L, 0..1; 0.45 lets a near-black
  slate ink through and catches mid greys), or in one of `muted_colors`,
  when `muted_text=False`.
* ``BOLD_TEXT`` -- bold text (weight 600 or more, by style or by the face it
  was shaped in) that is not a panel letter, when `bold="letters"`.
* ``KEY_IN_PANEL`` -- a key (legend, size key, colour bar) inside a plot panel,
  when `keys="outside"`.

Every rule is off unless its field is set, so `HouseRules()` checks nothing,
and none of these codes runs without `house=`.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..core import EllipsePrim, MarkerBatchPrim, PathPrim, RectPrim, Rect, TextPrim
from ..draw.annotate import LETTER_KIND
from ..draw.clip import MARKERS_NOTE
from ..draw.coords import AREA_NOTE
from ..draw.shapes import MARK_KIND
from ..plot.key import COLORBAR_KIND, LEGEND_KIND
from .color import parse_color
from .rules import Diagnostic, LintContext, _effective_stroke, _mm

__all__ = ["HouseRules", "rule_stroke_tier", "rule_marker_outline",
           "rule_muted_text", "rule_bold_text", "rule_key_in_panel", "HOUSE_CODES"]

#: A hand-placed `inklet.marker` is a small MARK_KIND shape; bars are too, but
#: larger. A mark no wider or taller than this is treated as a marker.
_MARKER_MAX_MM = 3.0
from .rules import KEY_KINDS as _KEY_KINDS  # noqa: E402  legend, colour bar, size and width keys
_BOLD = 600
#: Axes, keys and colour bars are furniture: their weight is the axis tier,
#: set once by the theme, even where a call restates it.
from ..plot.axis import AXIS_KIND  # noqa: E402
_FURNITURE = (AXIS_KIND, LEGEND_KIND, COLORBAR_KIND)


@dataclass(frozen=True)
class HouseRules:
    """A figure set's own rules for `lint(house=...)`. Unset fields check nothing.

    `stroke_tiers` are the allowed stroke widths in millimetres for an
    author's strokes inside plot panels, matched within `stroke_tolerance`
    (mm). `marker_outlines=False` forbids outlined filled markers.
    `muted_text=False` forbids grey text (OKLab chroma below `muted_chroma`)
    lighter than `muted_lightness` (OKLab L) and any text in `muted_colors`. `bold="letters"` allows
    bold only for panel letters. `keys="outside"` forbids keys inside plot
    panels. `inklet.Suite.lint_rules()` builds one from a house style.
    """
    stroke_tiers: tuple[float, ...] | None = None
    stroke_tolerance: float = 0.005
    marker_outlines: bool = True
    muted_text: bool = True
    muted_lightness: float = 0.45
    muted_chroma: float = 0.04
    muted_colors: tuple[str, ...] = ()
    bold: str = "any"
    keys: str = "any"

    def __post_init__(self):
        if self.stroke_tiers is not None:
            tiers = tuple(sorted(float(w) for w in self.stroke_tiers))
            if not tiers or any(w <= 0 for w in tiers):
                raise ValueError("stroke_tiers must be positive widths in mm")
            object.__setattr__(self, "stroke_tiers", tiers)
        if self.bold not in ("any", "letters"):
            raise ValueError("bold must be 'any' or 'letters'")
        if self.keys not in ("any", "outside"):
            raise ValueError("keys must be 'any' or 'outside'")
        if not 0.0 <= self.muted_lightness <= 1.0:
            raise ValueError("muted_lightness is an OKLab lightness in 0..1")
        object.__setattr__(self, "muted_colors",
                           tuple(c.lower() for c in self.muted_colors))


def _house(ctx: LintContext) -> HouseRules | None:
    return getattr(ctx, "house", None)


def _in_panel(ctx: LintContext, node_id: str) -> str | None:
    for step in ctx.ancestors(node_id):
        node = ctx.nodes.get(step)
        if node is not None and node.kind == "panel":
            return step
    return None


def _under(ctx: LintContext, node_id: str, kinds) -> bool:
    return any(getattr(ctx.nodes.get(step), "kind", None) in kinds
               for step in ctx.chain(node_id))


def _is_marker(ctx: LintContext, item) -> bool:
    if isinstance(item.prim, MarkerBatchPrim):
        return True
    if any(MARKERS_NOTE in getattr(ctx.nodes.get(step), "notes", {})
           for step in ctx.chain(item.id)):
        return isinstance(item.prim, (EllipsePrim, RectPrim, PathPrim))
    return (item.node.kind == MARK_KIND
            and isinstance(item.prim, (EllipsePrim, RectPrim, PathPrim))
            and item.bbox.width <= _MARKER_MAX_MM and item.bbox.height <= _MARKER_MAX_MM)


def _hex(value) -> str | None:
    rgb = parse_color(value) if isinstance(value, str) else None
    if rgb is None:
        return None
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in rgb)


# -- STROKE_TIER -------------------------------------------------------------


def rule_stroke_tier(ctx: LintContext) -> list[Diagnostic]:
    """An author's stroke in a plot panel at a width the house does not use."""
    house = _house(ctx)
    if house is None or house.stroke_tiers is None:
        return []
    from .plot_rules import library_stroke, stroke_role
    tiers = house.stroke_tiers
    by_width: dict[float, list[str]] = {}
    for item in ctx.items:
        width = _effective_stroke(item)
        if width is None or item.encodes_width or _in_panel(ctx, item.id) is None:
            continue
        if (library_stroke(ctx, item.id) or _under(ctx, item.id, _FURNITURE)
                or _is_marker(ctx, item)):
            continue
        if min(abs(width - t) for t in tiers) <= house.stroke_tolerance:
            continue
        by_width.setdefault(round(width, 3), []).append(item.id)
    allowed = ", ".join(_mm(t) for t in tiers)
    out = []
    for width in sorted(by_width):
        ids = sorted(by_width[width])
        nearest = min(tiers, key=lambda t: abs(t - width))
        roles = sorted({stroke_role(ctx, i) for i in ids})
        out.append(Diagnostic(
            code="STROKE_TIER", severity="warning",
            message=(f"{len(ids)} stroke(s) at {_mm(width)} ({', '.join(roles[:3])}"
                     f"{', ...' if len(roles) > 3 else ''}); the house weights are {allowed}"),
            targets=tuple(ids), where=ctx.placements[ids[0]].bbox if ids[0] in ctx.placements else None,
            hint=f"use stroke_width={nearest:.3f} (the nearest house weight)"))
    return out


# -- MARKER_OUTLINE -----------------------------------------------------------


def rule_marker_outline(ctx: LintContext) -> list[Diagnostic]:
    """A filled marker with an outline in another colour."""
    house = _house(ctx)
    if house is None or house.marker_outlines:
        return []
    paper = _hex(ctx.page_fill)
    found: list[str] = []
    for item in ctx.items:
        if not item.draws or not _is_marker(ctx, item):
            continue
        if _effective_stroke(item) is None:
            continue
        fill, stroke = _hex(item.style.fill), _hex(item.style.stroke)
        if fill is None or fill in (paper, "#ffffff") or stroke is None or stroke == fill:
            continue          # open marker: a ring in its own colour
        if isinstance(item.prim, MarkerBatchPrim) and item.prim.palette != (None,):
            pass              # per-point fills under one outline: still outlined
        found.append(item.id)
    if not found:
        return []
    found.sort()
    first = ctx.item(found[0])
    return [Diagnostic(
        code="MARKER_OUTLINE", severity="warning",
        message=(f"{len(found)} filled marker(s) drawn with an outline, e.g. "
                 f"{first.phrase} (fill {_hex(first.style.fill)}, stroke "
                 f"{_hex(first.style.stroke)}); house markers have no outline"),
        targets=tuple(found), where=first.bbox,
        hint="pass stroke='none' (or let the suite's marker style set it); "
             "draw an open marker as a ring in the series colour instead")]


# -- MUTED_TEXT ---------------------------------------------------------------


def _muted(color: str | None, house: HouseRules) -> bool:
    hexed = _hex(color)
    if hexed is None:
        return False
    if hexed in house.muted_colors:
        return True
    from ..themes.color import to_oklab
    lightness, a, b = to_oklab(hexed)
    return (a * a + b * b) ** 0.5 < house.muted_chroma and lightness > house.muted_lightness


def rule_muted_text(ctx: LintContext) -> list[Diagnostic]:
    """Text in a grey lighter than ink, or in a colour the house calls muted."""
    house = _house(ctx)
    if house is None or house.muted_text:
        return []
    out = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        prim = item.prim
        fills = [item.style.text_fill]
        fills += [getattr(run, "fill", None) for line in prim.lines for run in line.runs]
        bad = sorted({_hex(f) for f in fills if f is not None and _muted(f, house)})
        if bad:
            out.append(Diagnostic(
                code="MUTED_TEXT", severity="warning",
                message=f"{item.described} is set in grey ({', '.join(bad)})",
                targets=(item.id,), where=item.bbox,
                hint="set annotation text in ink, or in its series' own colour "
                     "(Suite.text_color); explanations belong in the legend"))
    return out


# -- BOLD_TEXT ----------------------------------------------------------------


def _weight(path: str | None, index: int = 0) -> int:
    if not path:
        return 400
    from ..typeset.fonts import load_face
    try:
        return load_face(path, index).weight
    except Exception:                                     # noqa: BLE001
        return 400


def _style_weight(value) -> int:
    if value is None:
        return 400
    if isinstance(value, (int, float)):
        return int(value)
    from ..typeset.fonts import weight_number
    try:
        return weight_number(str(value))
    except ValueError:
        return 400


def rule_bold_text(ctx: LintContext) -> list[Diagnostic]:
    """Bold anywhere but a panel letter."""
    house = _house(ctx)
    if house is None or house.bold != "letters":
        return []
    out = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        if item.node.kind == LETTER_KIND or (item.block is not None and item.block.kind == LETTER_KIND):
            continue
        prim: TextPrim = item.prim
        heavy = max([_style_weight(item.style.font_weight), _weight(prim.font_path)]
                    + [_weight(run.font_path, run.font_index)
                       for line in prim.lines for run in line.runs if run.font_path])
        if heavy >= _BOLD:
            out.append(Diagnostic(
                code="BOLD_TEXT", severity="warning",
                message=f"{item.described} is bold (weight {heavy}); only panel letters are bold",
                targets=(item.id,), where=item.bbox,
                hint="drop weight='bold' and **markup**; emphasise by position or colour"))
    return out


# -- KEY_IN_PANEL -------------------------------------------------------------


def rule_key_in_panel(ctx: LintContext) -> list[Diagnostic]:
    """A key drawn as part of a plot panel rather than outside every panel."""
    house = _house(ctx)
    if house is None or house.keys != "outside":
        return []
    out = []
    for node_id, node in sorted(ctx.nodes.items()):
        if node.kind not in _KEY_KINDS:
            continue
        if any(getattr(ctx.nodes.get(s), "kind", None) in _KEY_KINDS for s in ctx.ancestors(node_id)):
            continue
        panel = _in_panel(ctx, node_id)
        if panel is None:
            continue
        placed = ctx.placements.get(node_id)
        box = None if placed is None else placed.bbox
        where = "over the data" if _over_area(ctx, panel, box) else "beside the plot"
        out.append(Diagnostic(
            code="KEY_IN_PANEL", severity="warning",
            message=f"{node.kind} {ctx.label(node_id)!r} is drawn inside panel {ctx.label(panel)!r} ({where})",
            targets=(node_id,), where=box,
            hint="label the series directly (Panel.label_lines, Suite.end_labels) or put one "
                 "shared key outside the panels"))
    return out


def _over_area(ctx: LintContext, panel_id: str, box: Rect | None) -> bool:
    node = ctx.nodes.get(panel_id)
    notes = getattr(node, "notes", None)
    area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
    placed = ctx.placements.get(panel_id)
    if box is None or not isinstance(area, Rect) or placed is None:
        return False
    return box.overlap(area.transform(placed.world)) is not None


HOUSE_CODES = ("STROKE_TIER", "MARKER_OUTLINE", "MUTED_TEXT", "BOLD_TEXT", "KEY_IN_PANEL")
