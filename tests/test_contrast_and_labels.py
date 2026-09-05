"""Regressions for three defects a rendered figure showed and the linter's
report alone would not have settled: unreadable text on a filled box, a link
label sitting on top of the shapes it joins, and the plate behind it."""

import inklet
from inklet import Vec2
from inklet.core.prims import TextPrim
from inklet.themes import theme


def text_fills(fig):
    root, places = fig.build()
    return [places[n.id].style.text_fill for n in root.walk()
            if isinstance(n.prim, TextPrim)]


# -- text on a filled box -------------------------------------------------


def test_text_on_a_dark_fill_turns_light():
    th = theme("nature")
    fig = inklet.figure(width=60)
    fig.add(inklet.box("laser", fill="#000000"))
    assert text_fills(fig) == [th.paper]


def test_text_on_paper_keeps_the_theme_ink():
    th = theme("nature")
    fig = inklet.figure(width=60)
    fig.add(inklet.box("laser"))
    assert text_fills(fig) == [th.ink]


def test_an_authored_text_fill_is_never_overridden():
    fig = inklet.figure(width=60)
    fig.add(inklet.box("laser", fill="#000000", text_fill="#ff0000"))
    assert text_fills(fig) == ["#ff0000"]


def test_every_palette_fill_gets_readable_text():
    th = theme("nature")
    for i in range(len(th.palette)):
        ratio = inklet.contrast_ratio(th.text_on(th.color(i)), th.color(i))
        assert ratio >= 4.5, f"palette[{i}] {th.color(i)} only reaches {ratio:.2f}:1"


def test_text_on_returns_ink_when_ink_is_readable():
    th = theme("nature")
    assert th.text_on(th.paper) == th.ink


# -- label placement ------------------------------------------------------


def _label_box(fig):
    root, places = fig.build()
    for n in root.walk():
        if n.kind == "link-label":
            return places[n.id].bbox
    raise AssertionError("no link label in the figure")


def test_label_dodges_the_shapes_a_branch_converges_from():
    """The midpoint of a converging branch is exactly where the two sources
    sit; the label has to leave it."""
    left, right = inklet.box("ROI segmentation"), inklet.box("neuropil mask")
    sink = inklet.box("dF/F")
    fig = inklet.figure(width=120)
    fig.add(inklet.vstack([inklet.hstack([left, right], gap=5), sink], gap=6))
    fig.link(left, sink)
    fig.link(right, sink, label="subtract")
    root, places = fig.build()
    label = _label_box(fig)
    for node in (left, right, sink):
        assert label.overlap(places[node.id].bbox) is None, \
            "label still lands on a box it is meant to describe"


def test_an_unobstructed_label_stays_on_the_midpoint():
    """Collision avoidance must not perturb figures that were already fine."""
    a, b = inklet.box("A"), inklet.box("B")
    fig = inklet.figure(width=80)
    fig.add(inklet.vstack([a, b], gap=30))
    fig.link(a, b, label="x")
    root, places = fig.build()
    label = _label_box(fig)
    mid_y = (places[a.id].bbox.y1 + places[b.id].bbox.y0) / 2
    assert abs(label.center.y - mid_y) < 0.75


def test_label_plate_is_opaque_and_sits_behind_the_text():
    th = theme("nature")
    a, b = inklet.box("A"), inklet.box("B")
    fig = inklet.figure(width=80)
    fig.add(inklet.vstack([a, b], gap=30))
    fig.link(a, b, label="x")
    root, _ = fig.build()
    plates = [n for n in root.walk() if n.kind == "label-plate"]
    assert len(plates) == 1
    assert plates[0].style.fill in (th.paper, None)


def test_label_plate_can_be_turned_off():
    a, b = inklet.box("A"), inklet.box("B")
    fig = inklet.figure(width=80)
    fig.add(inklet.vstack([a, b], gap=30))
    fig.link(a, b, label="x", label_plate=False)
    root, _ = fig.build()
    assert not [n for n in root.walk() if n.kind == "label-plate"]


def test_placement_is_deterministic():
    def build():
        left, right = inklet.box("left"), inklet.box("right")
        sink = inklet.box("sink")
        fig = inklet.figure(width=120)
        fig.add(inklet.vstack([inklet.hstack([left, right], gap=5), sink], gap=6))
        fig.link(right, sink, label="subtract")
        return _label_box(fig)
    first, second = build(), build()
    assert (first.x0, first.y0) == (second.x0, second.y0)


# -- LINK_CROSSES hints ---------------------------------------------------


def _crossing(fig):
    return next(d for d in fig.lint() if d.code == "LINK_CROSSES")


def test_elbow_is_not_suggested_when_it_would_not_help():
    """route="orthogonal" degenerates to the same straight line when the
    endpoints share a column, which is exactly when this rule fires most."""
    top, mid, bottom = inklet.box("top"), inklet.box("BYSTANDER"), inklet.box("bottom")
    fig = inklet.figure(width=90)
    fig.add(inklet.vstack([top, mid, bottom], gap=12))
    fig.link(top, bottom)
    assert "orthogonal" not in _crossing(fig).hint


def test_elbow_is_suggested_when_it_has_room_to_turn():
    a, mid, b = inklet.box("A"), inklet.box("BYSTANDER"), inklet.box("B")
    fig = inklet.figure(width=110)
    fig.add(inklet.vstack([inklet.hstack([a, inklet.spacer(30, 1)], gap=2),
                        mid,
                        inklet.hstack([inklet.spacer(30, 1), b], gap=2)], gap=10))
    fig.link(a, b)
    assert "orthogonal" in _crossing(fig).hint


def test_a_degenerate_elbow_really_does_repeat_the_straight_path():
    """The premise of the hint above, asserted rather than assumed."""
    paths = []
    for mode in ("straight", "orthogonal"):
        col = [inklet.box(n) for n in ("top", "mid", "bottom")]
        fig = inklet.figure(width=70)
        fig.add(inklet.vstack(col, gap=8))
        fig.link(col[0], col[2], route=mode)
        root, places = fig.build()
        shaft = next(n for n in root.walk() if n.kind == "connector")
        pts = [places[shaft.id].world.apply(p)
               for p in shaft.prim.subpaths[0].points]
        paths.append([(round(p.x, 6), round(p.y, 6)) for p in pts])
    assert paths[0] == paths[1]
