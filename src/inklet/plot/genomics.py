"""Genome-wide plots: the Manhattan plot and the MA plot.

`manhattan_layout` does the arithmetic and draws nothing: it orders the
chromosomes naturally (1, 2, ..., 10, ..., X, Y, MT, with or without a "chr"
prefix), lays them end to end on one genome axis with a small gap between
them, and finds the lead hit of each significant locus. `inklet.manhattan`
draws it as a panel with its axes, ready for more layers.

`Panel.ma` draws an MA plot (mean expression against log2 fold change) with
the classification `volcano_points` makes.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence

from ..core import DiagramError
from ..draw.coords import active_theme
from ..themes.color import mix

__all__ = ["ManhattanLayout", "manhattan_layout", "manhattan", "chromosome_key", "ma"]

_FLOOR = 1e-300


def chromosome_key(name) -> tuple:
    """A sort key that puts chromosomes in their natural order: numbered ones
    by number, then X, Y, M/MT, then anything else by name."""
    text = str(name)
    bare = re.sub(r"^chr", "", text, flags=re.IGNORECASE)
    if bare.isdigit():
        return (0, int(bare), "")
    special = {"X": 1, "Y": 2, "M": 3, "MT": 3}
    if bare.upper() in special:
        return (special[bare.upper()], 0, "")
    return (4, 0, bare)


@dataclass(frozen=True)
class ManhattanLayout:
    """`x` and `y` per input point (None where skipped), the chromosome
    `order`, each chromosome's `spans` `(start, end)` and `centres` on the
    genome axis, the axis `length`, the `leads` (indices of the lead hits,
    smallest p first) and the `skipped` indices."""
    x: tuple
    y: tuple
    order: tuple[str, ...]
    spans: dict
    centres: dict
    length: float
    leads: tuple[int, ...]
    skipped: tuple[int, ...]


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def manhattan_layout(chromosome: Sequence, position: Sequence[float], p: Sequence[float], *,
                     order: Sequence[str] | None = None, gap: float = 0.008,
                     threshold: float = 5e-8, window: float = 1e6) -> ManhattanLayout:
    """Place association results on one genome axis, without drawing.

    `chromosome`, `position` (base pairs) and `p` are one per variant.
    Chromosomes run in natural order (or `order=`), each as long as its
    largest position, with `gap` of the genome's length between them. A
    variant's y is -log10 p (a p of 0 is drawn at the smallest positive p).
    Lead hits are the variants below `threshold` that have the smallest p
    within `window` base pairs on their chromosome, best first.
    """
    chromosome, position, p = list(chromosome), list(position), list(p)
    if not len(chromosome) == len(position) == len(p):
        raise DiagramError(
            f"manhattan needs one chromosome, position and p-value per variant, got "
            f"{len(chromosome)}, {len(position)} and {len(p)}")
    skipped = [i for i in range(len(p)) if _missing(p[i]) or _missing(position[i])
               or chromosome[i] is None]
    bad = set(skipped)
    for i in range(len(p)):
        if i in bad:
            continue
        if not 0 <= float(p[i]) <= 1:
            raise DiagramError(f"a p-value must be between 0 and 1, got {p[i]!r}")
        if float(position[i]) < 0:
            raise DiagramError(f"a position cannot be negative, got {position[i]!r}")
    names = sorted({str(chromosome[i]) for i in range(len(p)) if i not in bad},
                   key=chromosome_key)
    if order is not None:
        given = [str(c) for c in order]
        missing = [c for c in names if c not in given]
        if missing:
            raise DiagramError(f"manhattan order= leaves out chromosomes {missing}")
        names = given
    if not names:
        raise DiagramError("manhattan has no variants to draw")
    size = {c: 0.0 for c in names}
    for i in range(len(p)):
        if i not in bad:
            c = str(chromosome[i])
            size[c] = max(size[c], float(position[i]))
    total = sum(size.values()) or 1.0
    step = gap * total
    spans, centres = {}, {}
    at = 0.0
    for c in names:
        spans[c] = (at, at + size[c])
        centres[c] = at + size[c] / 2
        at += size[c] + step
    length = at - step
    positive = [float(v) for i, v in enumerate(p) if i not in bad and float(v) > 0]
    floor = min(positive) if positive else _FLOOR
    xs, ys = [], []
    for i in range(len(p)):
        if i in bad:
            xs.append(None)
            ys.append(None)
            continue
        xs.append(spans[str(chromosome[i])][0] + float(position[i]))
        ys.append(-math.log10(max(float(p[i]), floor)))
    hits = sorted((i for i in range(len(p)) if i not in bad and float(p[i]) < threshold),
                  key=lambda i: (float(p[i]), i))
    leads: list[int] = []
    for i in hits:
        c, x = str(chromosome[i]), float(position[i])
        if all(str(chromosome[j]) != c or abs(float(position[j]) - x) > window for j in leads):
            leads.append(i)
    return ManhattanLayout(tuple(xs), tuple(ys), tuple(names), spans, centres, length,
                           tuple(leads), tuple(skipped))


def manhattan(chromosome: Sequence, position: Sequence[float], p: Sequence[float], *,
              labels: Sequence[str] | None = None, top: int = 5,
              threshold: float | None = 5e-8, suggestive: float | None = 1e-5,
              window: float = 1e6, order: Sequence[str] | None = None,
              colors: Sequence[str] | None = None, highlight=None,
              highlight_color: str | None = None, bands: bool = False,
              width: float | str = 120, height: float | str = 40,
              ymax: float | None = None, size: float | None = None,
              gap: float = 0.008, raster: bool = False, **style):
    """A Manhattan plot as a panel with its axes, ready for more layers.

        p = inklet.manhattan(chrom, pos, pvalues, labels=snp_ids, top=6)
        fig.add(p)

    `chromosome`, `position` (bp) and `p` are one per variant; chromosomes
    run in natural order (1..22, X, Y, MT; "chr" prefixes are fine) or
    `order=`. Points alternate between two shades per chromosome
    (`colors=` for others; `bands=True` also shades every other
    chromosome's span). `threshold` draws the genome-wide significance line
    (5e-8) and `suggestive` a fainter one (1e-5); either may be None.

    With `labels=` (one per variant), the `top` lead hits -- the variants
    below `threshold` with the smallest p within `window` bp -- are named
    with `label_points`. `highlight=` indices (or a set of labels) are drawn
    in `highlight_color` over the rest. `raster=True` rasterises the points,
    which a million-variant study needs. The panel is `width` x `height` mm,
    its y axis from 0 to `ymax` (default: a round value past the top hit).
    Other keywords style the points. The points' layer carries a
    `manhattan` note with the chromosome order and spans and the lead hits.
    """
    from .panel import panel as make_panel
    from .scale import linear, nice_ticks
    theme = active_theme()
    layout = manhattan_layout(chromosome, position, p, order=order, gap=gap,
                              threshold=5e-8 if threshold is None else threshold,
                              window=window)
    shown = [y for y in layout.y if y is not None]
    high = max(shown) if shown else 1.0
    if threshold is not None:
        high = max(high, -math.log10(threshold))
    if ymax is None:
        ticks = nice_ticks(0.0, high * 1.05, 5)
        ymax = ticks[-1] if ticks[-1] >= high else high * 1.05
    pan = make_panel(width, height, x=linear((-layout.length * 0.005, layout.length * 1.005)),
                     y=linear((0.0, float(ymax))))
    if colors is None:
        dark = theme.accent
        colors = (dark, mix(dark, theme.paper, 0.55))
    colors = list(colors)
    if not colors:
        raise DiagramError("manhattan colors= is empty")
    if bands:
        tint = mix(theme.muted, theme.paper, 0.9)
        for k, c in enumerate(layout.order):
            if k % 2:
                a, b = layout.spans[c]
                pan.rect(a, 0, b, float(ymax), fill=tint, stroke="none")
    rule = {"stroke_width": theme.hairline, "stroke_dash": (1.0, 0.8)}
    if suggestive is not None:
        pan.hline(-math.log10(suggestive), stroke=theme.muted, **rule)
    if threshold is not None:
        pan.hline(-math.log10(threshold), stroke="#c9352b", **rule)
    lit: set[int] = set()
    if highlight is not None:
        wanted = set(highlight)
        names = list(labels) if labels is not None else []
        lit = {i for i in range(len(layout.x))
               if i in wanted or (names and names[i] in wanted)}
    by_chrom: dict[int, list] = {}
    chrom = list(chromosome)
    rank = {c: k for k, c in enumerate(layout.order)}
    for i, (x, y) in enumerate(zip(layout.x, layout.y)):
        if x is None or i in lit:
            continue
        by_chrom.setdefault(rank[str(chrom[i])] % len(colors), []).append((x, y))
    dot = {"size": 0.9 if size is None else size}
    for k in sorted(by_chrom):
        pan.scatter(by_chrom[k], color=colors[k], raster=raster, **dot, **style)
    if lit:
        pan.scatter([(layout.x[i], layout.y[i]) for i in sorted(lit) if layout.x[i] is not None],
                    color="#c9352b" if highlight_color is None else highlight_color,
                    **dot, **style)
    labelled: list[int] = []
    if labels is not None:
        labels = list(labels)
        if len(labels) != len(layout.x):
            raise DiagramError(
                f"manhattan needs one label per variant, got {len(labels)} for {len(layout.x)}")
        labelled = [i for i in layout.leads if layout.y[i] <= ymax][:top]
        if labelled:
            pan.label_points([(layout.x[i], layout.y[i]) for i in labelled],
                             [labels[i] for i in labelled])
    centres = [layout.centres[c] for c in layout.order]
    names = {layout.centres[c]: re.sub(r"^chr", "", c, flags=re.IGNORECASE)
             for c in layout.order}
    pan.axis("bottom", ticks=centres, format=lambda v: names.get(v, ""), tick_size=0,
             label="chromosome", thin=True)
    pan.axis("left", label="−log_{10} //P//")
    last = pan._content[-1] if pan._content else None
    note = {"order": layout.order, "spans": layout.spans, "leads": layout.leads,
            "labelled": labelled, "skipped": layout.skipped, "length": layout.length}
    if last is not None:
        last.notes["manhattan"] = note
    return pan


def ma(panel, mean: Sequence[float], fold: Sequence[float], p: Sequence[float] | None = None, *,
       labels: Sequence[str] | None = None, top: int = 10, fold_threshold: float = 1.0,
       p_threshold: float = 0.05, colors=None, names=None, size: float | None = None,
       log: bool = True, zero: bool = True, **style):
    """An MA plot on `panel`. See `Panel.ma`."""
    from ..themes.palettes import palette as _palette
    from .volcano import VOLCANO_CLASSES, volcano_points
    theme = active_theme()
    mean, fold = list(mean), list(fold)
    if len(mean) != len(fold):
        raise DiagramError(f"ma needs one mean per fold change, got {len(mean)} and {len(fold)}")
    pv = [0.0 if not _missing(f) else None for f in fold] if p is None else list(p)
    result = volcano_points(fold, pv, fold_threshold=fold_threshold,
                            p_threshold=p_threshold if p is not None else 1.0)
    xs: list = []
    for m in mean:
        if _missing(m):
            xs.append(None)
            continue
        m = float(m)
        if log:
            if m < 0:
                raise DiagramError(f"ma mean expression must be 0 or more with log=True, got {m!r}")
            m = math.log2(m + 1.0)
        xs.append(m)
    sunset = _palette("tol-sunset").colors
    paint = {"down": sunset[1], "ns": mix(theme.muted, theme.paper, 0.55), "up": sunset[9]}
    if isinstance(colors, dict):
        paint.update(colors)
    elif colors is not None:
        paint.update(zip(("down", "ns", "up"), colors))
    named = dict(names) if isinstance(names, dict) else (
        dict(zip(("down", "ns", "up"), names)) if names is not None else {})
    if zero:
        panel.hline(0, stroke=theme.muted, stroke_width=theme.hairline)
    dot = {"size": 0.9 if size is None else size}
    points = [None if x is None or pt is None else (x, pt[0])
              for x, pt in zip(xs, result["points"])]
    for kind in VOLCANO_CLASSES:
        chosen = [pt for pt, c in zip(points, result["classes"]) if c == kind and pt is not None]
        if chosen:
            panel.scatter(chosen, color=paint[kind], name=named.get(kind), **dot, **style)
    labelled: list[int] = []
    if labels is not None:
        labels = list(labels)
        if len(labels) != len(points):
            raise DiagramError(f"ma needs one label per point, got {len(labels)} for {len(points)}")
        area = panel.area
        ranked = result["ranked"] if p is not None else sorted(
            (i for i, c in enumerate(result["classes"]) if c in ("up", "down")),
            key=lambda i: -abs(float(fold[i])))
        inside = [i for i in ranked if points[i] is not None
                  and area.x0 - 1e-9 <= panel.x.map(points[i][0]) <= area.x1 + 1e-9
                  and area.y0 - 1e-9 <= panel.y.map(points[i][1]) <= area.y1 + 1e-9]
        labelled = inside[:top]
        if labelled:
            panel.label_points([points[i] for i in labelled], [labels[i] for i in labelled])
    return {"classes": result["classes"], "ranked": result["ranked"], "labelled": labelled,
            "skipped": [i for i, pt in enumerate(points) if pt is None]}
