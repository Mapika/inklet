"""Hierarchical clustering without SciPy, and what a clustered matrix draws.

`linkage` builds the merge table SciPy's `scipy.cluster.hierarchy.linkage`
returns (one row `[a, b, distance, count]` per merge), so its output feeds
`Panel.dendrogram`, `dendrogram_layout` and `inklet.clustermap` exactly as a
SciPy linkage would. It is the plain O(n^3) agglomeration with the
Lance-Williams updates, which is fine for the few hundred rows a figure
shows and deterministic: ties go to the lowest-numbered pair.

`cut` turns a linkage into flat clusters, `correlation` computes a Pearson
matrix, and `clusters` draws the diagonal boxes of a clustered matrix
(`Panel.clusters`).
"""

from __future__ import annotations

import math
from typing import Callable, Hashable, Sequence

from ..core import Diagram, DiagramError, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from .axis import text_node
from .inset import INDICATOR_KIND

__all__ = ["linkage", "cut", "correlation", "distance_matrix", "blocks",
           "LINKAGE_METHODS", "LINKAGE_METRICS"]

#: Accepted `linkage(method=)` values, with SciPy's meanings.
LINKAGE_METHODS = ("single", "complete", "average", "weighted", "ward")
#: Accepted `linkage(metric=)` names; a callable or "precomputed" also works.
LINKAGE_METRICS = ("euclidean", "correlation", "cosine", "cityblock")


def _float_rows(rows, what: str) -> list[list[float]]:
    table = rows.tolist() if hasattr(rows, "tolist") else list(rows)
    out = []
    for row in table:
        line = [float(v) for v in (row.tolist() if hasattr(row, "tolist") else row)]
        if any(not math.isfinite(v) for v in line):
            raise DiagramError(f"{what} values must be finite")
        out.append(line)
    if not out:
        raise DiagramError(f"{what} has no rows")
    width = len(out[0])
    if any(len(r) != width for r in out):
        raise DiagramError(f"{what} rows differ in length")
    return out


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        return float("nan")
    return max(-1.0, min(1.0, sab / math.sqrt(saa * sbb)))


def correlation(rows, *, by: str = "rows") -> list[list[float]]:
    """The Pearson correlation between every pair of rows (or columns, with
    `by="columns"`) of a table, as a square list of lists. A constant row
    correlates as NaN with everything, itself included."""
    table = _float_rows(rows, "correlation")
    if by == "columns":
        table = [list(c) for c in zip(*table)]
    elif by != "rows":
        raise DiagramError(f'correlation by= is "rows" or "columns", not {by!r}')
    if len(table[0]) < 2:
        raise DiagramError("correlation needs at least two values per row")
    n = len(table)
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            out[i][j] = out[j][i] = _pearson(table[i], table[j])
    return out


def _metric(name) -> Callable[[Sequence[float], Sequence[float]], float]:
    if callable(name):
        return name
    if name == "euclidean":
        return lambda a, b: math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    if name == "cityblock":
        return lambda a, b: sum(abs(x - y) for x, y in zip(a, b))
    if name == "correlation":
        def one_minus_r(a, b):
            r = _pearson(a, b)
            if math.isnan(r):
                raise DiagramError("correlation distance is undefined for a constant row")
            return 1.0 - r
        return one_minus_r
    if name == "cosine":
        def cosine(a, b):
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                raise DiagramError("cosine distance is undefined for an all-zero row")
            return 1.0 - sum(x * y for x, y in zip(a, b)) / (na * nb)
        return cosine
    raise DiagramError(
        f"linkage metric is one of {', '.join(LINKAGE_METRICS)}, \"precomputed\" "
        f"or a function, not {name!r}")


def distance_matrix(rows, metric="euclidean") -> list[list[float]]:
    """The pairwise distances between the rows of a table."""
    table = _float_rows(rows, "distance_matrix")
    f = _metric(metric)
    n = len(table)
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            out[i][j] = out[j][i] = max(0.0, float(f(table[i], table[j])))
    return out


def linkage(rows, method: str = "average", metric="euclidean") -> list[list[float]]:
    """Agglomerative clustering of the rows of a table, as a SciPy-style
    linkage: one row `[a, b, distance, count]` per merge, where indices
    below n are original rows and `n + k` is the cluster made by merge k.

    `method` is "average" (UPGMA, default), "single", "complete",
    "weighted" (WPGMA) or "ward". `metric` is "euclidean" (default),
    "correlation" (1 - Pearson r), "cosine", "cityblock", a function of two
    rows, or "precomputed" when `rows` is already a square distance matrix.
    Ward's method assumes Euclidean distances, as SciPy's does.

        link = inklet.plot.linkage(expression, method="average", metric="correlation")
        order = inklet.plot.dendrogram_layout(link).order
    """
    if method not in LINKAGE_METHODS:
        raise DiagramError(
            f"linkage method is one of {', '.join(LINKAGE_METHODS)}, not {method!r}")
    if metric == "precomputed":
        dist = _float_rows(rows, "linkage")
        n = len(dist)
        if len(dist[0]) != n:
            raise DiagramError("a precomputed distance matrix must be square")
        for i in range(n):
            for j in range(n):
                if abs(dist[i][j] - dist[j][i]) > 1e-9 * max(1.0, abs(dist[i][j])):
                    raise DiagramError("a precomputed distance matrix must be symmetric")
                if dist[i][j] < 0:
                    raise DiagramError("distances cannot be negative")
        dist = [list(r) for r in dist]
    else:
        dist = distance_matrix(rows, metric)
    n = len(dist)
    if n < 2:
        raise DiagramError("linkage needs at least two rows")
    # Active clusters by id; `d[(a, b)]` with a < b.
    size = {i: 1 for i in range(n)}
    d: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            d[(i, j)] = dist[i][j]
    out: list[list[float]] = []

    def get(a: int, b: int) -> float:
        return d[(a, b) if a < b else (b, a)]

    for step in range(n - 1):
        (a, b), best = min(d.items(), key=lambda kv: (kv[1], kv[0]))
        new = n + step
        na, nb = size[a], size[b]
        out.append([float(a), float(b), float(best), float(na + nb)])
        others = [c for c in size if c not in (a, b)]
        for c in others:
            da, db, nc = get(a, c), get(b, c), size[c]
            if method == "single":
                v = min(da, db)
            elif method == "complete":
                v = max(da, db)
            elif method == "average":
                v = (na * da + nb * db) / (na + nb)
            elif method == "weighted":
                v = (da + db) / 2
            else:  # ward
                t = na + nb + nc
                v = math.sqrt(max(0.0, ((na + nc) * da * da + (nb + nc) * db * db
                                        - nc * best * best) / t))
            d[(c, new)] = v
        for key in [k for k in d if a in k or b in k]:
            del d[key]
        del size[a], size[b]
        size[new] = na + nb
    return out


def cut(link, k: int | None = None, *, height: float | None = None) -> list[int]:
    """Flat clusters from a linkage: `k` clusters, or every merge at or
    below `height` kept. Returns one cluster number per original row,
    numbered 1, 2, ... in the dendrogram's leaf order, so the clusters of a
    matrix reordered by that order are consecutive runs."""
    from .dendrogram import dendrogram_layout
    rows = [list(r) for r in (link.tolist() if hasattr(link, "tolist") else link)]
    n = len(rows) + 1
    if (k is None) == (height is None):
        raise DiagramError("cut() takes either k= or height=")
    if k is not None:
        if not 1 <= k <= n:
            raise DiagramError(f"cut k= must be from 1 to {n}, got {k}")
        keep = n - k
    else:
        keep = sum(1 for r in rows if r[2] <= height)
    parent = list(range(2 * n - 1))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    # Merges are in height order in a linkage; keep the lowest `keep`.
    for step, r in enumerate(rows[:keep]):
        parent[find(int(r[0]))] = n + step
        parent[find(int(r[1]))] = n + step
    order = dendrogram_layout(rows).order
    number: dict[int, int] = {}
    out = [0] * n
    for leaf in order:
        root = find(leaf)
        number.setdefault(root, len(number) + 1)
        out[leaf] = number[root]
    return out


def blocks(groups: Sequence[Hashable]) -> list[tuple[int, int, Hashable]]:
    """The runs of equal labels in `groups`: `(start, stop, label)` with
    `stop` exclusive. `None` labels form no block."""
    out: list[tuple[int, int, Hashable]] = []
    start = 0
    for i in range(1, len(groups) + 1):
        if i == len(groups) or groups[i] != groups[start]:
            if groups[start] is not None:
                out.append((start, i, groups[start]))
            start = i
    return out


def clusters(panel, groups, *, color: str | None = None, highlight=None,
             highlight_color: str | None = None, width: float | str | None = None,
             labels: bool = False, size: float | str | None = None,
             min_size: int = 1, **style) -> tuple[Diagram, dict]:
    """The diagonal cluster boxes of a matrix. See `Panel.clusters`."""
    theme = active_theme()
    labels_of = [None if g is None else g for g in
                 (groups.tolist() if hasattr(groups, "tolist") else list(groups))]
    n = len(labels_of)
    if n == 0:
        raise DiagramError("clusters() needs one group label per matrix row")
    runs = [b for b in blocks(labels_of) if b[1] - b[0] >= min_size]
    seen: dict = {}
    for start, stop, label in runs:
        if label in seen:
            raise DiagramError(
                f"cluster {label!r} is split into more than one run; reorder the "
                "matrix by the clustering first (see inklet.plot.cut)")
        seen[label] = (start, stop)
    lit = set()
    if highlight is not None:
        wanted = [highlight] if isinstance(highlight, (str, int)) else list(highlight)
        for h in wanted:
            if h not in seen:
                raise DiagramError(f"clusters highlight= names {h!r}, which is not a cluster")
            lit.add(h)
    area = panel.area
    sx, sy = area.width / n, area.height / n
    ink = theme.ink if color is None else color
    hot = "#c9352b" if highlight_color is None else highlight_color
    stroke = theme.thick if width is None else mm(width)
    font = theme.font_size_small if size is None else mm(size)
    items: list = []
    # Plain boxes first, highlighted ones over them.
    for start, stop, label in sorted(runs, key=lambda r: r[2] in lit):
        half = stroke / 2
        x0 = area.x0 + start * sx + half
        x1 = area.x0 + stop * sx - half
        y0 = area.y0 + start * sy + half
        y1 = area.y0 + stop * sy - half
        paint = {"stroke": hot if label in lit else ink, "stroke_width": stroke,
                 "fill": "none", "stroke_linejoin": "miter"}
        paint.update(style)
        items.append(polyline(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), closed=True,
                              kind=INDICATOR_KIND, **paint))
        if labels:
            t = text_node(str(label), font, "label", markup=False,
                          text_fill=paint["stroke"])
            b = t.bbox
            gap = theme.gap("xs")
            # Outside the matrix on the right, level with the box's middle,
            # where it reads as the name of those rows.
            items.append(draw_place([(Vec2(area.x1 + gap + stroke + b.width / 2, (y0 + y1) / 2), t)],
                                    origin=(0, 0)))
    node = draw_place(items, origin=(0, 0), kind=abutting("clusters"))
    note = {"blocks": [(s, e, lab) for s, e, lab in runs], "highlighted": sorted(map(str, lit)),
            "rows": n}
    node.notes["clusters"] = note
    return node, note
