"""PolarPanel.radar, radar_grid and pie."""

from __future__ import annotations

import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import active_theme, as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import polar
from inklet.plot.axis import TICK_LABEL_KIND
from inklet.plot.furniture import GRID_KIND
from inklet.plot.wheel import pie_label_texts, radar_spokes


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def placements(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == kind]


def texts(p, kind=TICK_LABEL_KIND):
    return {x.diagram.prim.text: x for x in placements(p, kind)
            if getattr(x.diagram.prim, "text", None)}


def test_spokes_divide_the_turn_evenly() -> None:
    p = polar(20, r=(0, 1))
    assert radar_spokes(p, 4) == (0.0, 90.0, 180.0, 270.0)
    with pytest.raises(DiagramError):
        radar_spokes(p, 2)


def test_radar_vertices_sit_on_their_spokes() -> None:
    p = polar(20, r=(0, 1), zero="up", winding="cw")
    p.radar([1.0, 0.5, 1.0, 0.5], name="a", fill=False, markers=False)
    line, = placements(p, MARK_LINE_KIND)
    pts = [line.world.apply(v) for v in line.diagram.prim.subpaths[0].points]
    assert math.isclose(pts[0].x, 0, abs_tol=1e-6)
    assert math.isclose(pts[0].y, -20, abs_tol=1e-6)      # up, at the rim
    assert math.isclose(pts[1].x, 10, abs_tol=1e-6)       # clockwise: east
    assert [k.name for k in p.keys] == ["a"]


def test_radar_needs_a_whole_turn() -> None:
    p = polar(20, r=(0, 1), theta=(0, 180))
    with pytest.raises(DiagramError):
        p.radar([1, 2, 3])


def test_radar_grid_draws_rings_spokes_and_names() -> None:
    p = polar(20, r=(0, 1))
    p.radar_grid(["a", "b", "c", "d", "e"], rings=[0.5])
    grid = placements(p, GRID_KIND)
    assert len(grid) == 2 + 5            # ring at 0.5 and the rim, 5 spokes
    names = texts(p)
    assert sorted(names) == ["a", "b", "c", "d", "e"]
    for label in names.values():
        c = label.bbox.center
        assert math.hypot(c.x, c.y) > 20


def test_pie_slices_span_their_shares() -> None:
    p = polar(20, zero="up", winding="cw")
    p.pie([1, 3], labels=None, separator=False)
    wedges = placements(p, MARK_KIND)
    assert len(wedges) == 2
    # The first quarter is the north-east quadrant.
    small = min(wedges, key=lambda w: w.bbox.width * w.bbox.height)
    assert small.bbox.x0 >= -1e-6 and small.bbox.y1 <= 1e-6


def test_pie_labels_go_inside_or_outside_by_fit() -> None:
    p = polar(14, zero="up", winding="cw")
    p.pie([90, 8, 2], names=["big", "mid", "tiny"])
    node = p._content[-1]
    note = node.notes["pie_labels"]
    assert 0 in note["inside"] and 2 in note["outside"]
    labels = texts(p)
    tiny = labels["2%"].bbox.center
    assert math.hypot(tiny.x, tiny.y) > 14
    assert [k.name for k in p.keys] == ["big", "mid", "tiny"]


def test_pie_inside_label_contrasts_with_its_slice() -> None:
    p = polar(14)
    p.pie([1, 1], colors=["#000000", "#ffffff"])
    theme = active_theme()
    fills = {x.style.text_fill for x in placements(p, TICK_LABEL_KIND)
             if getattr(x.diagram.prim, "text", None)}
    assert fills == {theme.ink, theme.paper}


def test_pie_label_spellings() -> None:
    assert pie_label_texts("percent", [1, 3]) == ["25%", "75%"]
    assert pie_label_texts("value", [1, 3]) == ["1", "3"]
    assert pie_label_texts("{share:.1%}", [1, 3]) == ["25.0%", "75.0%"]
    assert pie_label_texts(lambda v, s: f"{v:g}", [1, 3]) == ["1", "3"]
    with pytest.raises(DiagramError):
        pie_label_texts(["a"], [1, 3])


def test_pie_refuses_negative_and_empty() -> None:
    p = polar(14)
    with pytest.raises(DiagramError):
        p.pie([1, -1])
    with pytest.raises(DiagramError):
        p.pie([0, 0])


def test_donut_and_radar_lint_clean_and_export() -> None:
    d = polar(14, hole=7, zero="up", winding="cw")
    d.pie([61, 39])
    r = polar(16, r=(0, 1), zero="up", winding="cw")
    r.radar_grid(["a", "b", "c", "d", "e"])
    r.radar([0.8, 0.6, 0.9, 0.4, 0.7])
    for node in (d.build(), r.build()):
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)


def _ink_outside(node, margin: float = 2.0, dpi: int = 600) -> list[str]:
    """Sides of the page margin that hold ink when `node` is laid out alone.

    The figure is made exactly as wide as the node's measured box plus the
    margin, so any ink the node draws past its own box lands in the margin.
    """
    import io

    from PIL import Image

    fig = inklet.figure(width=node.bbox.width + 2 * margin, theme="nature")
    fig.add(node)
    image = Image.open(io.BytesIO(fig.to_png(dpi=dpi))).convert("L")
    width, height = image.size
    band = int((margin - 0.25) * dpi / 25.4)
    pixels = image.load()
    sides = {"left": (range(band), range(height)),
             "right": (range(width - band, width), range(height)),
             "top": (range(width), range(band)),
             "bottom": (range(width), range(height - band, height))}
    return [side for side, (xs, ys) in sides.items()
            if any(pixels[x, y] < 250 for x in xs for y in ys)]


def test_pie_and_radar_ink_stays_inside_the_measured_panel() -> None:
    donut = polar(11, hole=5.5, zero="up", winding="cw")
    donut.pie([54, 28, 12, 4, 2], names=["a", "b", "c", "d", "e"],
              colors=["#24698c", "#1f6f60", "#a4532f", "#e6b93f", "#b9b8b4"])
    donut.legend(side="bottom")
    crowded = polar(10, zero="right")
    crowded.pie([70, 12, 8, 5, 3, 2])
    radar = polar(12, r=(0, 1), zero="up", winding="cw")
    radar.radar_grid(["speed", "accuracy", "recall", "depth", "range"])
    radar.radar([0.8, 1.0, 0.9, 0.4, 1.0])
    for panel in (donut, crowded, radar):
        assert _ink_outside(panel.build()) == []


def _breakout_panel(**kwargs):
    p = polar(11, zero="up", winding="cw")
    p.pie([24.8, 1.5, 73.7], colors=["#262626", "#e6b93f", "#ececec"],
          labels=None)
    p.breakout([0, 1], **kwargs)
    return p


def test_breakout_bar_renormalises_the_chosen_slices() -> None:
    p = _breakout_panel()
    node = p._content[-1]
    note = node.notes["pie_breakout"]
    assert note["slices"] == [0, 1] and note["parts"] == [24.8, 1.5]
    labels = texts(p)
    assert "94%" in labels and "6%" in labels
    bars = [x for x in placements(p, MARK_KIND) if x.bbox.x0 > 11]
    assert len(bars) == 2
    tall = max(bars, key=lambda b: b.bbox.height)
    assert math.isclose(sum(b.bbox.height for b in bars), 22, abs_tol=1e-6)
    assert math.isclose(tall.bbox.height / 22, 24.8 / 26.3, abs_tol=1e-6)
    assert tall.bbox.y0 < min(b.bbox.y0 for b in bars if b is not tall) + 1e-9
    # Its segments take the slices' own colours.
    assert tall.style.fill == "#262626"


def test_breakout_connectors_run_from_the_rim_to_the_bar_corners() -> None:
    p = _breakout_panel(labels=None)
    links = [x for x in placements(p, MARK_LINE_KIND)
             if x.diagram.style.stroke == active_theme().muted]
    assert len(links) == 2
    ends = []
    for link in links:
        a, b = (link.world.apply(v) for v in link.diagram.prim.subpaths[0].points)
        assert math.isclose(math.hypot(a.x, a.y), 11, abs_tol=1e-6)
        ends.append(b)
    near = 11 + 0.75 * 11
    assert all(math.isclose(e.x, near, abs_tol=1e-6) for e in ends)
    assert sorted(e.y for e in ends) == pytest.approx([-11, 11])


def test_breakout_parts_legend_and_left_side() -> None:
    p = polar(11, zero="up", winding="ccw")
    p.pie([30, 45, 25])
    p.breakout(0, [60, 25, 10, 5], names=["w", "x", "y", "z"], side="left")
    assert [k.name for k in p.keys] == ["w", "x", "y", "z"]
    labels = texts(p)
    for text in ("60%", "25%", "10%", "5%"):
        assert labels[text].bbox.x1 < -11
    note = p._content[-1].notes["pie_breakout"]
    # 10% and 5% sit on thin segments and are moved apart.
    assert note["moved"]
    boxes = sorted((labels[t].bbox for t in ("60%", "25%", "10%", "5%")),
                   key=lambda b: b.y0)
    assert all(a.y1 <= b.y0 for a, b in zip(boxes, boxes[1:]))


def test_breakout_needs_a_pie_and_adjacent_slices() -> None:
    p = polar(11)
    with pytest.raises(DiagramError):
        p.breakout(0)
    p.pie([1, 2, 3])
    with pytest.raises(DiagramError):
        p.breakout([0, 2])
    with pytest.raises(DiagramError):
        p.breakout(5)
    with pytest.raises(DiagramError):
        p.breakout(0, side="top")


def test_breakout_lints_clean_exports_and_stays_measured() -> None:
    p = _breakout_panel(title="without noise")
    q = polar(10, hole=5, zero="up", winding="cw")
    q.pie([30, 45, 25])
    q.breakout(0, [60, 25, 10, 5], names=["w", "x", "y", "z"], side="left")
    q.legend(side="bottom")
    for panel in (p, q):
        node = panel.build()
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
        assert _ink_outside(node) == []


def _middle_bearing(p, slices):
    """The page bearing of the middle of adjacent `slices`, from the pie's
    note."""
    angles = p._pie[0]["angles"]
    a0 = min(angles[i][0] for i in slices)
    a1 = max(angles[i][1] for i in slices)
    return ((a0 + a1) / 2) % 360


@pytest.mark.parametrize("side, facing", [("right", 0.0), ("left", 180.0)])
def test_breakout_turns_a_default_pie_to_face_the_bar(side, facing) -> None:
    p = polar(11)
    p.pie([24.8, 1.5, 73.7], labels=None)
    p.breakout([0, 1], side=side)
    note = p._content[-1].notes["pie_breakout"]
    assert note["turned"]
    assert p.theta.winding == ("cw" if side == "right" else "ccw")
    assert math.isclose(_middle_bearing(p, [0, 1]), facing, abs_tol=1e-6)
    # The first slice is the upper one, as the first part is on the bar.
    angles = p._pie[0]["angles"]
    first = math.sin(math.radians(sum(angles[0]) / 2))
    second = math.sin(math.radians(sum(angles[1]) / 2))
    assert first < second
    # The pie was drawn again, not twice.
    assert len(p._content) == 2
    links = [x for x in placements(p, MARK_LINE_KIND)
             if x.diagram.style.stroke == active_theme().muted]
    for link in links:
        a, b = (link.world.apply(v) for v in link.diagram.prim.subpaths[0].points)
        assert (a.x > 0) == (side == "right")


def test_breakout_keeps_a_given_zero_and_winding() -> None:
    p = _breakout_panel()
    assert (p.theta.zero % 360, p.theta.winding) == (270.0, "cw")
    assert not p._content[-1].notes["pie_breakout"]["turned"]
    # Only the free one changes: zero is kept, the winding follows the side.
    q = polar(11, zero="up")
    q.pie([30, 45, 25], labels=None)
    q.breakout(0, side="left")
    assert q.theta.zero % 360 == 270.0 and q.theta.winding == "ccw"
    # Only the winding given: zero turns the slice to the bar.
    r = polar(11, winding="ccw")
    r.pie([30, 45, 25], labels=None)
    r.breakout(1)
    assert r.theta.winding == "ccw"
    assert math.isclose(_middle_bearing(r, [1]), 0.0, abs_tol=1e-6)


def _svg(p) -> str:
    import re
    return re.sub(r'(id|href|clip-path|data-[a-z-]+)="[^"]*"', "",
                  inklet.to_svg(p.build()))


def _busy(p, order):
    values = [30, 45, 25]
    for step in order:
        if step == "grid":
            p.grid()
        elif step == "pie":
            p.pie(values, names=["a", "b", "c"])
        elif step == "text":
            p.text(45, 0.5, "note")
    return p


@pytest.mark.parametrize("order", [("grid", "pie"), ("pie", "text"),
                                   ("grid", "pie", "text")])
def test_breakout_turns_a_pie_drawn_with_other_content(order) -> None:
    p = _busy(polar(11), order)
    p.breakout(1)
    note = p._content[-1].notes["pie_breakout"]
    assert note["turned"]
    assert p.theta.winding == "cw"
    assert math.isclose(_middle_bearing(p, [1]), 0.0, abs_tol=1e-6)
    # Everything is drawn again under the turned angles: the page matches a
    # panel given the same zero and winding up front.
    given = _busy(polar(11, zero=p.theta.zero, winding=p.theta.winding), order)
    given.breakout(1)
    assert _svg(p) == _svg(given)
    if "text" not in order:              # the note is placed by hand
        assert lint(p.build()) == []


def test_breakout_keeps_a_pie_with_content_in_panel_coordinates() -> None:
    p = polar(11)
    p.draw(inklet.circle(width=1, height=1))
    p.pie([30, 45, 25], labels=None)
    p.breakout(1)
    assert (p.theta.zero, p.theta.winding) == (0.0, "ccw")
    assert not p._content[-1].notes["pie_breakout"]["turned"]


def test_breakout_connectors_clear_outside_pie_labels() -> None:
    from inklet.plot.wheel import _segment_hits, breakout_connectors
    from inklet.plot.wheel import pie as wheel_pie

    values = [3, 25, 4, 68]
    alone = polar(11, zero="up", winding="cw")
    node, _, note = wheel_pie(alone, values)
    links = breakout_connectors(alone, note["angles"], [1, 2])
    boxes = [x.bbox for x in resolve(as_drawn(node)).values()
             if getattr(x.diagram.prim, "text", None)]
    # Without the breakout in view, an outside label sits on a connector.
    assert any(_segment_hits(b, a, c) for b in boxes for a, c in links)
    p = polar(11, zero="up", winding="cw")
    p.pie(values)
    p.breakout([1, 2], labels=None)
    assert p._pie[0]["outside"] == [0, 2] and p._pie[0]["crossing"] == []
    links = [x for x in placements(p, MARK_LINE_KIND)
             if x.diagram.style.stroke == active_theme().muted]
    ends = [tuple(x.world.apply(v) for v in x.diagram.prim.subpaths[0].points)
            for x in links]
    for text in ("3%", "4%"):
        box = texts(p)[text].bbox
        assert not any(_segment_hits(box, a, b) for a, b in ends)
    node = p.build()
    assert lint(node) == []
    assert _ink_outside(node) == []


def _pie_note(p):
    return next(item.notes["pie_labels"] for item in p._content
                if "pie_labels" in item.notes)


def _leaders(p):
    theme = active_theme()
    return [x for x in placements(p, MARK_LINE_KIND)
            if x.diagram.style.stroke == theme.ink]


def _boxes_overlap(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def test_pie_labels_by_their_slice_need_no_leader() -> None:
    p = polar(14, zero="up", winding="cw")
    p.pie([54, 28, 12, 4, 2])
    note = _pie_note(p)
    assert note["outside"] == [3, 4]
    assert note["leaders"] == [] and _leaders(p) == []


def test_crowded_outside_pie_labels_get_leaders_back_to_their_slice() -> None:
    p = polar(12)
    p.pie([70, 12, 8, 5, 2, 1.5, 1, 0.5])
    note = _pie_note(p)
    assert note["leaders"] and note["crossing"] == []
    leaders = _leaders(p)
    assert len(leaders) == len(note["leaders"])
    for line in leaders:
        start, end = (line.world.apply(v)
                      for v in line.diagram.prim.subpaths[0].points)
        # From the rim outward.
        assert math.isclose(math.hypot(start.x, start.y), 12, abs_tol=1e-6)
        assert math.hypot(end.x, end.y) > 12
    labels = [x.bbox for x in placements(p, TICK_LABEL_KIND)]
    for k, a in enumerate(labels):
        for b in labels[k + 1:]:
            assert not _boxes_overlap(a, b)


def test_breakout_pie_leaders_keep_clear_of_the_connectors() -> None:
    from inklet.plot.point_labels import _segments_cross

    p = polar(11)
    p.pie([3, 2, 88, 2, 5])
    p.breakout([0, 1], labels="{share:.1%}")
    note = _pie_note(p)
    assert note["crossing"] == [] and note["leaders"]
    muted = active_theme().muted
    lines = placements(p, MARK_LINE_KIND)
    links = [[x.world.apply(v) for v in x.diagram.prim.subpaths[0].points]
             for x in lines if x.diagram.style.stroke == muted]
    for line in _leaders(p):
        a, b = (line.world.apply(v) for v in line.diagram.prim.subpaths[0].points)
        for c, d in links:
            assert not _segments_cross(a, b, c, d)
    assert lint(p.build()) == []


def test_breakout_title_keeps_the_pie_labels_off() -> None:
    from inklet.plot.wheel import breakout_title_box

    p = polar(7)
    p.pie([24.8, 1.5, 73.7], labels=["24.8%", "1.5%", "73.7%"])
    p.breakout([0, 1], labels="{share:.1%}", gap=4, title="without noise")
    heading = breakout_title_box(p, "without noise", gap=4)
    labels = [x for k, x in texts(p).items() if k in ("24.8%", "1.5%", "73.7%")]
    assert len(labels) == 3
    for label in labels:
        box = label.bbox
        assert (box.x1 <= heading.x0 or box.x0 >= heading.x1
                or box.y1 <= heading.y0 or box.y0 >= heading.y1)
    assert [d for d in lint(p.build()) if d.severity != "info"] == []


def test_radar_ring_values_keep_clear_of_the_data() -> None:
    p = polar(16, r=(0, 1), zero="up", winding="cw")
    p.radar_grid(list("ABCDEF"), values=True)
    p.radar([0.8, 0.7, 0.9, 0.6, 0.75, 0.85], name="a")
    p.radar([0.5, 0.95, 0.6, 0.9, 0.55, 0.7], name="b", fill=False)
    node = p.build()
    note = next(x.notes["radar_rings"] for x in node.children
                if "radar_rings" in x.notes)
    assert note["values"] and note["clearance"] > 0.5
    # The first gap has the second series' vertex on its outer ring, so
    # another gap is chosen.
    assert note["gap"] != 0
    # Only the two series' own vertices crowd each other.
    assert [d for d in lint(node) if d.severity != "info"] == []


def test_radar_ring_values_follow_the_first_spoke_without_data() -> None:
    p = polar(16, r=(0, 1), zero="up", winding="cw")
    p.radar_grid(list("ABCDE"), values=True)
    note = next(x.notes["radar_rings"] for x in p.build().children
                if "radar_rings" in x.notes)
    assert note["gap"] == 0 and note["clearance"] is None
    assert 1.0 in note["values"]
    q = polar(16, r=(0, 1))
    q.radar_grid(list("ABCDE"))
    assert not any("radar_rings" in x.notes for x in q.build().children)


def test_contrast_lint_reads_a_halo_and_a_translucent_fill() -> None:
    from inklet.draw.path import polyline
    from inklet.draw.place import place
    from inklet.core import Vec2

    square = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
    shade = polyline(square, closed=True, filled=True, fill="#000000",
                     fill_opacity=0.16, stroke="none")
    label = inklet.text("0.5", size=2, text_fill="#1a1a1a")
    node = place([shade, (Vec2(5, 5), label)], origin=(0, 0))
    assert [d.code for d in lint(node)] == []
    solid = polyline(square, closed=True, filled=True, fill="#000000",
                     stroke="none")
    dark = place([solid, (Vec2(5, 5), label)], origin=(0, 0))
    assert "LOW_CONTRAST" in [d.code for d in lint(dark)]
    haloed = inklet.text("0.5", size=2, text_fill="#1a1a1a", halo=0.5)
    ringed = place([solid, (Vec2(5, 5), haloed)], origin=(0, 0))
    assert "LOW_CONTRAST" not in [d.code for d in lint(ringed)]
