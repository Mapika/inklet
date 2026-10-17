"""One axis name for a whole grid of cells, centred on the data it names.

A grid of small multiples repeats its numbers on every panel, but the name of
the quantity belongs once: under the bottom row, centred on the block of plot
areas, and once beside the left column. `Document.label(x=, y=)` asks for
that. The layout itself is unchanged. The labels are measured first, room is
taken from the page for them, the grid is laid out in what is left, and the
labels are then placed against the ink the cells drew.
"""
from __future__ import annotations

from ..core import Diagram, Rect
from ..draw.coords import plot_area
from ..plot.axis import AXIS_LABEL_KIND, text_node
from .spec import themed


def _cells(node: Diagram):
    """The placed cells of a laid-out grid, through its content wrappers only."""
    for child in node.children:
        if child.kind == "document-cell":
            yield child
        elif child.kind == "document-content":
            yield from _cells(child)


def _union(boxes: list[Rect]) -> Rect:
    out = boxes[0]
    for box in boxes[1:]:
        out = out.union(box)
    return out


def layout_with_labels(layout, labels: dict, theme, margin: float,
                       width: float, height: float | None):
    """Lay out the grid with `labels` placed beside it.

    `layout(width, height)` lays out the grid and returns a `LayoutResult`.
    Labels are measured in `theme` first, so the grid gets only the room they
    leave; the x name goes under the lowest ink and the y name left of the
    leftmost, both `theme.gap('s')` away. A fixed page height is kept, and
    the grid shares it with the x name.
    """
    gap = theme.gap("s")
    with themed(theme):
        x_node = (text_node(labels["x"], theme.font_size, AXIS_LABEL_KIND)
                  if labels.get("x") else None)
        y_node = (text_node(labels["y"], theme.font_size, AXIS_LABEL_KIND).rotated(-90.0)
                  if labels.get("y") else None)
    left = gap + y_node.bbox.width if y_node is not None else 0.0
    below = gap + x_node.bbox.height if x_node is not None else 0.0
    result = layout(width - left, None if height is None else height - below)
    content, boxes = result.content, result.boxes
    cells = list(_cells(content))
    if not cells:
        return result
    ink = _union([cell.bbox for cell in cells])
    # The block of data regions the names are centred on; a cell with no data
    # region, a picture say, counts by its ink.
    regions = []
    for cell in cells:
        area = plot_area(cell)
        regions.append(cell.bbox if area is None else area)
    region = _union(regions)
    placed: list[Diagram] = []
    bottom = 0.0
    if x_node is not None:
        box = x_node.bbox
        x0 = region.center.x - box.width / 2
        y0 = ink.y1 + gap
        placed.append(x_node.translated(x0 - box.x0 + left, y0 - box.y0))
        bottom = y0 + box.height
    if y_node is not None:
        box = y_node.bbox
        x1 = ink.x0 - gap
        y0 = region.center.y - box.height / 2
        placed.append(y_node.translated(x1 - box.width - box.x0 + left, y0 - box.y0))
    shifted = {name: Rect(box.x0 + left, box.y0, box.x1 + left, box.y1)
               for name, box in boxes.items()}
    page_height = result.page_height
    if height is None:
        page_height = max(page_height, bottom + margin)
    else:
        page_height = height
    grid = content.translated(left, 0.0)
    labelled = Diagram(children=(grid, *placed), kind="document-content")
    return result._replace(content=labelled, boxes=shifted, page_height=page_height)
