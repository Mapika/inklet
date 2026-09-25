"""The clustermap: a matrix reordered by clustering, with its dendrograms and
annotation colour strips, as one figure-level diagram.

Everything is composed from ordinary panels (`matrix`, `dendrogram`,
`clusters`, `colorbar`, `legend`) with `row` and `column`, so the pieces
line up on their plot areas and each carries its own notes.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from .cluster import blocks, cut, linkage
from .dendrogram import dendrogram_layout

__all__ = ["clustermap"]


def _standardized(rows: list[list[float]], by: str | None) -> list[list[float]]:
    if by is None:
        return rows
    if by not in ("rows", "columns"):
        raise DiagramError(f'clustermap standardize= is "rows", "columns" or None, not {by!r}')
    table = rows if by == "rows" else [list(c) for c in zip(*rows)]
    out = []
    for line in table:
        n = len(line)
        mean = sum(line) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in line) / max(1, n - 1))
        out.append([(v - mean) / sd if sd > 0 else 0.0 for v in line])
    return out if by == "rows" else [list(c) for c in zip(*out)]


def _threshold(link, k: int | None) -> float | None:
    """A height between the merges that leave `k` clusters, for colouring
    the dendrogram the same way `cut(link, k)` groups the rows."""
    if k is None or k <= 1:
        return None
    n = len(link) + 1
    lo = link[n - k - 1][2] if n - k - 1 >= 0 else 0.0
    hi = link[n - k][2]
    return (lo + hi) / 2 if hi > lo else None


def _strip_colors(values: Sequence, theme, taken: dict) -> list[str]:
    """Colours for one annotation track: colour strings pass through, other
    values are categories coloured from the palette (shared across tracks
    through `taken`, so one category keeps one colour)."""
    from .hierarchy_plots import branch_colors
    out = []
    for v in values:
        if isinstance(v, str) and v.startswith("#"):
            out.append(v)
            continue
        if v not in taken:
            taken[v] = branch_colors(len(taken) + 1, theme)[-1]
        out.append(taken[v])
    return out


def clustermap(values, *, rows: Sequence[str] | None = None,
               columns: Sequence[str] | None = None, method: str = "average",
               metric="euclidean", row_cluster: bool = True, col_cluster: bool = True,
               row_linkage=None, col_linkage=None, standardize: str | None = None,
               k: int | None = None, highlight=None, row_colors: Mapping | None = None,
               col_colors: Mapping | None = None, ramp=None, scale=None,
               center: float | None = None, width: float | str = 50,
               height: float | str | None = None, tree: float | str = 8,
               strip: float | str = 2.0, label: str | None = None,
               row_labels: bool | None = None, col_labels: bool | None = None,
               colorbar: bool = True, gap: float | str | None = None) -> Diagram:
    """A matrix reordered by hierarchical clustering, with row and column
    dendrograms, annotation strips and a colorbar.

        inklet.clustermap(expression, rows=genes, columns=samples,
                          metric="correlation", standardize="rows",
                          col_colors={"condition": conditions}, label="z-score")

    `values[r][c]` is a table (lists or a 2-D array). Rows and columns are
    clustered with `inklet.plot.linkage(method=, metric=)`, or taken from
    `row_linkage=` / `col_linkage=` (a SciPy linkage works too);
    `row_cluster=False` or `col_cluster=False` keeps the input order and
    drops that tree. `standardize="rows"` (or "columns") z-scores the values
    before clustering and drawing.

    `k=` cuts the row tree into that many clusters: the tree is coloured by
    cluster, and when the matrix is square with the same order on both
    axes (a correlation matrix) the clusters are boxed on the diagonal
    (`highlight=` cluster numbers are boxed in red); otherwise thin paper
    rules separate them.

    `row_colors=` and `col_colors=` map a track name to one value per row
    (column): a colour, or a category coloured from the palette and named in
    a legend below. `width` and `height` are the matrix size in mm (height
    defaults to keep square cells), `tree` the dendrograms' depth and
    `strip` each annotation strip's. Row and column names are written when
    there is room for them (or as `row_labels=` / `col_labels=` say).
    `ramp`, `scale` and `center` colour the matrix as `Panel.matrix` does;
    `label` titles the colorbar. The node carries a `clustermap` note with
    the row and column order and the row clusters.
    """
    from .cluster import _float_rows
    from .panel import column, panel, row
    from .scale import linear
    theme = active_theme()
    table = _float_rows(values, "clustermap")
    nr, nc = len(table), len(table[0])
    row_names = [str(i) for i in range(nr)] if rows is None else [str(v) for v in rows]
    col_names = [str(j) for j in range(nc)] if columns is None else [str(v) for v in columns]
    if len(row_names) != nr or len(col_names) != nc:
        raise DiagramError(
            f"clustermap has a {nr} x {nc} table but {len(row_names)} row and "
            f"{len(col_names)} column names")
    data = _standardized(table, standardize)
    space = theme.gap("xs") if gap is None else mm(gap)

    rlink = None
    if row_cluster and nr >= 2:
        rlink = row_linkage if row_linkage is not None else linkage(data, method, metric)
        rlink = [list(r) for r in (rlink.tolist() if hasattr(rlink, "tolist") else rlink)]
    clink = None
    if col_cluster and nc >= 2:
        cols_t = [list(c) for c in zip(*data)]
        clink = col_linkage if col_linkage is not None else linkage(cols_t, method, metric)
        clink = [list(r) for r in (clink.tolist() if hasattr(clink, "tolist") else clink)]
    rorder = list(dendrogram_layout(rlink).order) if rlink else list(range(nr))
    corder = list(dendrogram_layout(clink).order) if clink else list(range(nc))
    shown = [[data[i][j] for j in corder] for i in rorder]

    w = mm(width)
    h = w * nr / nc if height is None else mm(height)
    small = theme.font_size_small
    row_names_o = [row_names[i] for i in rorder]
    col_names_o = [col_names[j] for j in corder]
    if row_labels is None:
        row_labels = h / nr >= small * 1.15
    if col_labels is None:
        col_labels = w / nc >= small * 1.15

    heat = panel(w, h, x=col_names_o, y=list(reversed(row_names_o)))
    heat.matrix(shown, ramp=ramp, scale=scale, center=center)
    if row_labels:
        heat.axis("right", tick_size=0, tick_pad=theme.gap("xs"), spine=False, thin=False)
    if col_labels:
        heat.axis("bottom", tick_size=0, tick_pad=theme.gap("xs"), spine=False, thin=False,
                  rotate=90)
    clusters_of = None
    if k is not None:
        if rlink is None:
            raise DiagramError("clustermap k= needs the rows clustered")
        clusters_of = cut(rlink, k)
        groups = [clusters_of[i] for i in rorder]
        if nr == nc and rorder == corder:
            heat.clusters(groups, highlight=highlight)
        else:
            rules = []
            for start, _, _ in blocks(groups)[1:]:
                y = heat.area.y0 + start * h / nr
                rules.append(polyline(((heat.area.x0, y), (heat.area.x1, y)),
                                      kind="frame", stroke=theme.paper,
                                      stroke_width=theme.thick))
            if rules:
                heat.over(draw_place(rules, origin=(0, 0), kind=abutting("clustermap-rules")),
                          clip=False)

    taken: dict = {}

    def strips(tracks: Mapping | None, count: int, order: list[int], along_x: bool):
        if not tracks:
            return []
        out = []
        for name, vals in tracks.items():
            vals = list(vals)
            if len(vals) != count:
                raise DiagramError(f"clustermap track {name!r} has {len(vals)} values for {count}")
            # Categories take colours in input order, then follow the rows.
            _strip_colors(vals, theme, taken)
            fills = _strip_colors([vals[i] for i in order], theme, taken)
            if along_x:
                p = panel(w, mm(strip))
                step = w / count
                cells = [(Vec2(p.area.x0 + (q + 0.5) * step, 0.0),
                          Diagram(prim=_rect(step, mm(strip)), kind=MARK_KIND)
                          .styled(fill=f, stroke="none")) for q, f in enumerate(fills)]
            else:
                p = panel(mm(strip), h)
                step = h / count
                cells = [(Vec2(0.0, p.area.y0 + (q + 0.5) * step),
                          Diagram(prim=_rect(mm(strip), step), kind=MARK_KIND)
                          .styled(fill=f, stroke="none")) for q, f in enumerate(fills)]
            p.draw(draw_place(cells, origin=(0, 0), kind=abutting("clustermap-strip")))
            out.append((str(name), p))
        return out

    rstrips = strips(row_colors, nr, rorder, along_x=False)
    cstrips = strips(col_colors, nc, corder, along_x=True)
    # Track names: beside a column strip on the left, under a row strip.
    from .axis import text_node
    for name, p in cstrips:
        t = text_node(name, small, "label", markup=False)
        p.over(draw_place([(Vec2(p.area.x0 - space - t.bbox.width / 2, 0.0), t)],
                          origin=(0, 0)), clip=False)
    for name, p in rstrips:
        t = text_node(name, small, "label", markup=False).rotated(-90)
        p.over(draw_place([(Vec2(0.0, p.area.y1 + space + t.bbox.height / 2), t)],
                          origin=(0, 0)), clip=False)

    left: list = []
    if rlink:
        heights = max(r[2] for r in rlink) or 1.0
        tp = panel(mm(tree), h, x=linear((heights, 0.0)), y=linear((nr - 0.5, -0.5)))
        tp.dendrogram(rlink, orient="h", threshold=_threshold(rlink, k))
        left.append(tp)
    left.extend(p for _, p in rstrips)
    top: list = []
    if clink:
        heights = max(r[2] for r in clink) or 1.0
        tp = panel(w, mm(tree), x=linear((-0.5, nc - 0.5)), y=linear((0.0, heights)))
        same = nr == nc and rorder == corder
        tp.dendrogram(clink, orient="v", threshold=_threshold(clink, k) if same else None)
        top.append(tp)
    top.extend(p for _, p in cstrips)
    if taken:
        for cat, color in taken.items():
            heat._note(str(cat), "area", color=color)
        heat.legend(side="bottom", corner=None)
    if colorbar:
        heat.colorbar(side="right", title=label)

    middle = row(left + [heat], gap=space) if left else heat.build()
    node = column(top + [middle], gap=space, align="right") if top else middle
    if not isinstance(node, Diagram):
        node = node.build()
    note = {"rows": row_names_o, "columns": col_names_o,
            "row_order": rorder, "column_order": corder,
            "clusters": None if clusters_of is None else dict(zip(row_names, clusters_of))}
    node.notes["clustermap"] = note
    return node


def _rect(w: float, h: float):
    from ..core import RectPrim
    return RectPrim(w, h)
