"""`inklet.graph(fit=...)`: slide whole ranks until a layered drawing fits.

The pass exists because compaction inside `_settle` and the sideways drift are
the same motion (section 5 of `graph_layered.py` says why), so narrowing has to
happen *after* the sweeps, as a rigid move that cannot disturb an order.

The graph here is `examples/graph.py`'s pipeline, because the slack the pass
lives on is the gap between the widest rank and the drawing -- ranks that are
individually narrow but offset from one another. A graph of equal-width boxes
has no such gap: every rank is already packed and there is nothing to slide.
"""
from __future__ import annotations

import pytest

import inklet
from inklet.layout.graph import GraphError

STEPS = {
    "fastq": "raw reads\n(FASTQ)", "sheet": "sample sheet", "genome": "GRCh38",
    "gtf": "GENCODE v44", "sets": "MSigDB\nhallmarks", "qc": "read QC",
    "trim": "adapter trim", "index": "genome index", "align": "STAR align",
    "dedup": "mark duplicates", "counts": "featureCounts",
    "matrix": "count matrix", "filter": "expression filter",
    "norm": "TMM normalise", "vst": "variance\nstabilise", "pca": "PCA",
    "corr": "sample\ncorrelation", "batch": "batch check", "de": "DESeq2 fit",
    "shrink": "LFC shrink", "call": "call DE genes", "gsea": "GSEA",
    "string": "STRING network", "volcano": "volcano plot", "heat": "heatmap",
    "table": "results table", "panels": "figure panels", "report": "report",
}
EDGES = [
    ("fastq", "qc"), ("qc", "trim"), ("trim", "align"),
    ("genome", "index"), ("index", "align"),
    ("align", "dedup"), ("dedup", "counts"), ("gtf", "counts"),
    ("counts", "matrix"), ("matrix", "filter"), ("sheet", "filter"),
    ("filter", "norm"), ("norm", "vst"), ("norm", "de"), ("sheet", "de"),
    ("vst", "pca"), ("vst", "corr"), ("pca", "batch"), ("corr", "batch"),
    ("de", "shrink"), ("shrink", "call"), ("call", "gsea"), ("sets", "gsea"),
    ("gsea", "string"), ("call", "volcano"), ("vst", "heat"),
    ("call", "table"), ("volcano", "panels"), ("heat", "panels"),
    ("string", "panels"), ("batch", "panels"), ("panels", "report"),
    ("table", "report"),
]


def placed(graph: inklet.Graph) -> list:
    """Where the boxes actually ended up.

    `graph[key]` hands back the very box it was given -- that is the point of
    the wrapper -- so its bbox is the local one, centred on the origin. The
    laid-out coordinates live on the diagram's children, in node order.
    """
    return [child.bbox for child in graph.diagram.children]


def pipeline(width: float, **kwargs) -> inklet.Graph:
    inklet.use_theme("nature")
    boxes = {key: inklet.box(text, width=width) for key, text in STEPS.items()}
    return inklet.graph(boxes, EDGES, direction="down", rank_gap=5, lane=4,
                     **kwargs)


def test_fit_is_off_by_default():
    """The default must not move a drawing: every corpus figure depends on it."""
    assert pipeline(15).width == pipeline(15, fit=None).width


def test_a_drawing_that_already_fits_is_untouched():
    """Not "close enough" -- the same millimetres, so the SVG bytes match.

    A drawing inside its column gains nothing from being narrower, and asking
    for it anyway costs crossings, so the pass declines to have an opinion.
    """
    loose = pipeline(15)
    assert loose.width < 89.0
    for limit in (89.0, 120.0, inklet.COLUMN_DOUBLE):
        assert pipeline(15, fit=limit).width == loose.width


def test_a_drawing_that_spills_is_brought_in():
    assert pipeline(20).width > 89.0
    assert pipeline(20, fit=89.0).width <= 89.0


def test_it_stops_when_it_fits_rather_than_going_on():
    """Overflow first, edge length second: once inside, nothing is left to win
    by being narrower, which is what keeps the pass from buying crossings."""
    assert pipeline(20, fit=89.0).width == pytest.approx(89.0, abs=1e-6)
    assert pipeline(15, fit=75.0).width == pytest.approx(75.0, abs=1e-6)


def test_asking_for_less_than_the_drawing_can_give_is_not_a_guarantee():
    """Sliding ranks cannot make one narrower than it is, and the pass says so
    by coming back wide rather than by overlapping boxes."""
    assert pipeline(24, fit=40.0).width > 40.0


def test_fitting_never_overlaps_two_boxes():
    """A rigid rank shift cannot break a separation -- this is the check that
    the shifts really are rigid. Same rank means same centre along the flow."""
    boxes = placed(pipeline(24, fit=89.0))
    for i, one in enumerate(boxes):
        for two in boxes[i + 1:]:
            if abs((one.y0 + one.y1) - (two.y0 + two.y1)) > 1e-6:
                continue                      # different ranks: free to overlap
            overlap = one.overlap(two)
            assert overlap is None or overlap.width <= 1e-9


def test_fitting_is_deterministic():
    assert pipeline(20, fit=89.0).width == pipeline(20, fit=89.0).width


def test_fitting_a_fitted_drawing_moves_nothing():
    """The pass has a fixed point, which is the whole reason it is a descent
    on rigid moves rather than another sweep."""
    once = pipeline(20, fit=89.0)
    was = [box.x0 for box in placed(once)]
    again = [box.x0 for box in placed(pipeline(20, fit=once.width))]
    assert again == pytest.approx(was, abs=1e-6)


def test_fit_must_be_positive():
    with pytest.raises(GraphError, match="fit must be positive"):
        pipeline(15, fit=0)


def test_fit_is_layered_only():
    """Force and circular have no ranks to slide, and a tree's are already
    packed against their parents; the parameter is accepted and ignored rather
    than raising, so swapping `layout=` does not break a script."""
    inklet.use_theme("nature")
    boxes = {key: inklet.box(text, width=20) for key, text in STEPS.items()}
    for layout in ("tree", "force", "circular"):
        plain = inklet.graph(boxes, EDGES, layout=layout, iterations=20)
        fitted = inklet.graph(boxes, EDGES, layout=layout, iterations=20, fit=40.0)
        assert plain.width == fitted.width


def test_fitting_clears_the_off_canvas_it_was_asked_to_clear():
    """The reason the parameter exists, measured the way a reader sees it."""
    def off_canvas(**kwargs) -> int:
        fig = inklet.figure(width=inklet.COLUMN_SINGLE, theme="nature")
        pipeline(20, **kwargs).add_to(fig)
        return sum(1 for note in fig.lint() if note.code == "OFF_CANVAS")

    assert off_canvas() == 2
    assert off_canvas(fit=inklet.COLUMN_SINGLE) == 0
