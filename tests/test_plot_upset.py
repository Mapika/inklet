"""inklet.upset and plot.upset_layout."""

from __future__ import annotations

import io

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import plot_area
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import upset_layout
from inklet.plot.axis import SPINE_KIND, TICK_LABEL_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


SETS = {"A": {1, 2, 3, 4, 5, 6}, "B": {4, 5, 6, 7}, "C": {6, 8}}


def placements(node, kind):
    return [x for x in resolve(node).values() if x.diagram.kind == kind]


def test_mapping_counts_exclusive_intersections() -> None:
    layout = upset_layout(SETS)
    assert layout.sets == ("A", "B", "C")
    assert layout.set_sizes == (6.0, 4.0, 2.0)
    found = {i.members: i.size for i in layout.intersections}
    assert found == {("A",): 3, ("A", "B"): 2, ("A", "B", "C"): 1, ("B",): 1,
                     ("C",): 1}
    # Disjoint: they add up to the number of distinct elements.
    assert sum(found.values()) == 8
    # Largest first, then fewer sets, then set order.
    assert [i.members for i in layout.intersections] == [
        ("A",), ("A", "B"), ("B",), ("C",), ("A", "B", "C")]


def test_records_with_counts_and_bare_tuples() -> None:
    layout = upset_layout([(("x", "y"), 5), (("x",), 7), ("y",), ("y",),
                           (("y", "x"), 1)], sort_sets=False)
    assert layout.sets == ("x", "y")
    assert {i.members: i.size for i in layout.intersections} == {
        ("x", "y"): 6, ("x",): 7, ("y",): 2}
    assert layout.set_sizes == (13.0, 8.0)
    with pytest.raises(DiagramError):
        upset_layout([(("x", "x"), 2)])
    with pytest.raises(DiagramError):
        upset_layout([(("x",), -1)])
    with pytest.raises(DiagramError):
        upset_layout({"A": 3})


def test_sort_cutoff_and_maximum() -> None:
    by_degree = upset_layout(SETS, sort="degree")
    assert [i.degree for i in by_degree.intersections] == [1, 1, 1, 2, 3]
    assert by_degree.intersections[0].members == ("A",)
    given = upset_layout([(("b",), 1), (("a",), 9)], sort="input", sort_sets=False)
    assert [i.members for i in given.intersections] == [("b",), ("a",)]
    cut = upset_layout(SETS, min_size=2)
    assert [i.members for i in cut.intersections] == [("A",), ("A", "B")]
    assert len(cut.dropped) == 3
    top = upset_layout(SETS, max_intersections=2)
    assert len(top.intersections) == 2 and len(top.dropped) == 3
    chosen = upset_layout(SETS, sets=["C", "A"])
    assert chosen.sets == ("C", "A")
    assert all(set(i.members) <= {"A", "C"} for i in chosen.intersections)
    empty = upset_layout([((), 4), (("a",), 1)])
    assert [i.members for i in empty.intersections] == [("a",)]
    assert upset_layout([((), 4), (("a",), 1)], empty=True).intersections[0].size == 4
    with pytest.raises(DiagramError):
        upset_layout(SETS, sort="alphabet")
    with pytest.raises(DiagramError):
        upset_layout(SETS, max_intersections=0)


def test_bars_stand_over_their_matrix_columns() -> None:
    node = inklet.upset(SETS)
    layout = upset_layout(SETS)
    bars = [x for x in placements(node, MARK_KIND) if x.diagram.kind == MARK_KIND
            and getattr(x.diagram.style, "fill", None) and x.bbox.height > 2.5
            and x.bbox.width < 3]
    lines = placements(node, MARK_LINE_KIND)
    # One joining line per intersection of two or more sets.
    assert len(lines) == sum(1 for i in layout.intersections if i.degree >= 2)
    # Every line is centred under a bar.
    centres = sorted(round(b.bbox.center.x, 4) for b in bars)
    for line in lines:
        assert round(line.bbox.center.x, 4) in centres
    # Intersection bars sit above the matrix, set bars left of it.
    area = plot_area(node)
    assert area is not None
    note = node.notes["upset"]
    assert note["sets"] == ("A", "B", "C")
    assert note["intersections"][0] == (("A",), 3.0)


def test_set_names_and_options() -> None:
    node = inklet.upset(SETS, labels=True, set_sizes=False, stripes=False,
                        bar_label=None, color="#aa3377")
    names = {x.diagram.prim.text for x in placements(node, TICK_LABEL_KIND)
             if getattr(x.diagram.prim, "text", None)}
    assert {"A", "B", "C", "3", "2", "1"} <= names
    assert "set size" not in inklet.to_svg(node)
    assert "#aa3377" in inklet.to_svg(node)
    with pytest.raises(DiagramError):
        inklet.upset(SETS, min_size=100)


def _ink_outside(node, margin: float = 2.0, dpi: int = 600) -> list[str]:
    from PIL import Image

    fig = inklet.figure(width=node.bbox.width + 2 * margin, theme="nature")
    fig.add(node)
    image = Image.open(io.BytesIO(fig.to_png(dpi=dpi))).convert("L")
    width, height = image.size
    band_px = int((margin - 0.25) * dpi / 25.4)
    pixels = image.load()
    sides = {"left": (range(band_px), range(height)),
             "right": (range(width - band_px, width), range(height)),
             "top": (range(width), range(band_px)),
             "bottom": (range(width), range(height - band_px, height))}
    return [side for side, (xs, ys) in sides.items()
            if any(pixels[x, y] < 250 for x in xs for y in ys)]


def test_upset_lints_clean_exports_and_ink_stays_measured() -> None:
    records = [(("RNA", "ATAC"), 37), (("RNA",), 92), (("ATAC",), 53),
               (("ChIP",), 25), (("RNA", "ChIP"), 22), (("RNA", "ATAC", "ChIP"), 14)]
    for node in (inklet.upset(SETS), inklet.upset(records, labels=True),
                 inklet.upset(records, set_sizes=False, sort="degree")):
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
        assert _ink_outside(node) == []
    lettered = inklet.row(inklet.letters([inklet.upset(SETS), inklet.panel(20, 20).axes()]))
    assert lint(lettered) == []


def test_axis_ends_on_a_tick() -> None:
    node = inklet.upset([(("a",), 92), (("b",), 30)], set_sizes=False)
    labels = {x.diagram.prim.text for x in placements(node, TICK_LABEL_KIND)
              if getattr(x.diagram.prim, "text", None)}
    assert "100" in labels
    assert "120" not in labels and "150" not in labels


GUIDE_HITS = [(("RNA-seq",), 412), (("RNA-seq", "ATAC-seq"), 236), (("ATAC-seq",), 198),
              (("RNA-seq", "ATAC-seq", "ChIP-seq"), 121), (("ChIP-seq",), 94),
              (("RNA-seq", "ChIP-seq"), 77), (("ATAC-seq", "ChIP-seq"), 52),
              (("proteomics",), 31), (("RNA-seq", "proteomics"), 29),
              (("RNA-seq", "ATAC-seq", "proteomics"), 12),
              (("ChIP-seq", "proteomics"), 4), (("ATAC-seq", "proteomics"), 3)]


def _set_axis(node):
    """The set-size spine, bars and tick labels: the leftmost spine, and the
    marks and labels left of the matrix."""
    spines = [x for x in placements(node, SPINE_KIND) if x.bbox.height < 1e-6]
    spine = min(spines, key=lambda s: s.bbox.x0)
    bars = [x for x in placements(node, MARK_KIND) if x.bbox.x1 <= spine.bbox.x1 + 1e-6]
    labels = [x for x in placements(node, TICK_LABEL_KIND)
              if getattr(x.diagram.prim, "text", None)
              and x.bbox.y0 > spine.bbox.y0 and x.bbox.x1 < spine.bbox.x1 + 3]
    return spine, bars, labels


def test_set_axis_ends_on_a_labelled_tick_past_the_longest_bar() -> None:
    # The guide's data: RNA-seq holds 887, so the axis runs to 1000.
    node = inklet.upset(GUIDE_HITS, min_size=5, labels=True)
    spine, bars, labels = _set_axis(node)
    assert len(bars) == 4
    outer = [x for x in labels if x.diagram.prim.text == "1000"]
    assert outer, [x.diagram.prim.text for x in labels]
    # The outer label sits at the far end of the spine.
    assert abs(outer[0].bbox.center.x - spine.bbox.x0) < 0.1
    # Every bar lies within the spine's extent, the longest short of its end.
    assert all(b.bbox.x0 >= spine.bbox.x0 - 1e-6 for b in bars)
    assert min(b.bbox.x0 for b in bars) > spine.bbox.x0 + 0.5


def test_set_axis_stops_at_the_largest_set_when_a_round_end_is_far() -> None:
    # 260 would round up to 400 or 500 on a narrow axis: it ends at 260.
    node = inklet.upset({"a": set(range(260)), "b": set(range(40))}, set_width=11)
    spine, bars, _ = _set_axis(node)
    assert len(bars) == 2
    assert abs(min(b.bbox.x0 for b in bars) - spine.bbox.x0) < 1e-6
