"""`inklet.diagnostics` -- deterministic geometry diagnostics for a diagram.

The point of this module is that an agent generating a figure never sees it.
Every finding therefore carries node ids, a direction and a millimetre number,
so the fix is mechanical:

    import inklet
    from inklet.core import Rect
    from inklet.diagnostics import format_report, lint

    figure = inklet.vstack([inklet.box("read"), inklet.box("write")], gap=6)
    print(format_report(lint(figure, page=Rect(0, 0, 89, 50))))

`Figure.report()` is the same thing with the page already known, and is what
almost every caller wants.

Results are sorted by (severity, code, targets, message), so two runs over the
same tree produce an identical list and a fix loop can diff them.

One rule depends on an optional package. `LOW_CONTRAST` reads the pixels under
a caption when the backdrop is a raster, which needs Pillow; without it that
one case is skipped silently rather than guessed at, and every other rule is
unaffected. `inklet.diagnostics.image.available()` says which of the two you are
getting.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from ..core import Diagram, Placement, Rect, resolve
from .abut import abutting, is_abutting_kind
from .cross import crossing, declared_crossings
from .color import contrast_ratio, parse_color, relative_luminance
from .report import format_report
from .rules import (
    DEFAULT_MAX_STROKE_WIDTHS, DEFAULT_MIN_CLEARANCE_MM,
    DEFAULT_MIN_OVERLAP_FRACTION, DEFAULT_PAGE_FILL, RULE_FAILED, RULES,
    SEVERITIES, Diagnostic, Item, LintContext, Rule, build_context, run_rules,
)

__all__ = [
    "abutting", "is_abutting_kind",
    "crossing", "declared_crossings",
    "Diagnostic", "Item", "LintContext", "Rule", "RULES", "SEVERITIES",
    "RULE_FAILED", "lint", "format_report", "build_context",
    "parse_color", "relative_luminance", "contrast_ratio",
    "DEFAULT_MIN_CLEARANCE_MM", "DEFAULT_MIN_OVERLAP_FRACTION",
    "DEFAULT_MAX_STROKE_WIDTHS", "DEFAULT_PAGE_FILL",
]


def _select(rules: Iterable[str] | Mapping[str, Rule] | None) -> dict[str, Rule]:
    if rules is None:
        return dict(RULES)
    if isinstance(rules, Mapping):
        return dict(rules)
    selected: dict[str, Rule] = {}
    for code in rules:
        if code not in RULES:
            known = ", ".join(sorted(RULES))
            raise ValueError(f"unknown lint rule {code!r}; known rules: {known}")
        selected[code] = RULES[code]
    return selected


def lint(
    root: Diagram,
    *,
    page: Rect | None = None,
    rules: Iterable[str] | Mapping[str, Rule] | None = None,
    min_font_pt: float = 5.0,
    min_stroke_mm: float = 0.088,
    min_dpi: float = 300.0,
    placements: Mapping[str, Placement] | None = None,
    page_fill: str = DEFAULT_PAGE_FILL,
    min_clearance_mm: float = DEFAULT_MIN_CLEARANCE_MM,
    min_overlap_fraction: float = DEFAULT_MIN_OVERLAP_FRACTION,
    max_stroke_widths: int = DEFAULT_MAX_STROKE_WIDTHS,
    max_font_pt: float | None = None,
    max_height_mm: float | None = None,
) -> list[Diagnostic]:
    """Check a figure and return its diagnostics, deterministically ordered.

    `page` enables OFF_CANVAS and gives LOW_CONTRAST a backdrop. `rules` is
    either an iterable of codes to run or a full {code: callable} mapping;
    omit it for all of `RULES`. `placements` lets a caller that has already
    called `core.resolve()` avoid paying for it twice.

    The extra keyword arguments beyond the four thresholds in the brief
    (`page_fill`, `min_clearance_mm`, `min_overlap_fraction`,
    `max_stroke_widths`) are the knobs for LOW_CONTRAST, CROWDING, OVERLAP and
    INCONSISTENT_STROKE respectively; the defaults are what the rule docs
    quote.

    Optional max_font_pt and max_height_mm enforce publication limits at final
    physical size. Neither upper limit is applied unless explicitly supplied.
    """
    _must_be_a_diagram(root)
    if placements is None:
        placements = resolve(root)
    ctx = build_context(
        root, placements, page=page, page_fill=page_fill,
        min_font_pt=min_font_pt, min_stroke_mm=min_stroke_mm, min_dpi=min_dpi,
        min_clearance_mm=min_clearance_mm,
        min_overlap_fraction=min_overlap_fraction,
        max_stroke_widths=max_stroke_widths,
        max_font_pt=max_font_pt, max_height_mm=max_height_mm,
    )
    return run_rules(ctx, _select(rules))


def _must_be_a_diagram(root: object) -> None:
    """Refuse anything but a node, naming the method that does what was meant.

    `inklet.lint(fig)` is the natural thing to write and it used to die deep in
    `resolve()` with `'Figure' object has no attribute 'transform'`, which
    says nothing about the mistake. A figure is not a node: it holds the page
    and the paper colour, and lints its own built tree with both -- so the
    answer is not to unwrap it here (that would silently drop OFF_CANVAS and
    mis-colour LOW_CONTRAST) but to say which call knows them.
    """
    if isinstance(root, Diagram):
        return
    what = type(root).__name__
    if callable(getattr(root, "lint", None)):
        raise TypeError(
            f"inklet.lint() takes a Diagram; call {what}.lint() instead -- it "
            f"knows the page and the paper colour, which OFF_CANVAS and "
            f"LOW_CONTRAST need"
        )
    raise TypeError(f"inklet.lint() takes a Diagram, not {what}")
