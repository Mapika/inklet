"""COINCIDENT_SHAFT and LABEL_COVERS_SHAFT: a link hiding behind itself.

Neither is a collision. In both the router did what it was asked, every
measurement is in range, and the page still shows fewer lines than the author
drew: two routes on one line, or a label plate over its own corner.

The near-miss cases matter more here than anywhere else in the linter. A
crossing is not a shared run, and a label beside the line it names is what a
label is -- fire on either and every flow diagram in the corpus lights up.
"""

from __future__ import annotations

import inklet


# -- builders -------------------------------------------------------------


def hub_and_spokes(*, anchored: bool = False) -> inklet.Figure:
    """One box left, two boxes right of it, both linked to the hub.

    Aimed at the shapes' centres the two orthogonal routes leave the hub along
    the same horizontal line and share it until they turn. Aimed at anchors
    they leave from different points and share nothing.
    """
    hub = inklet.box("hub").named("hub")
    up = inklet.box("up").named("up")
    down = inklet.box("down").named("down")
    fig = inklet.figure(width=90)
    fig.add(inklet.place([((0.0, 0.0), hub), ((40.0, -14.0), up),
                       ((40.0, 14.0), down)]))
    source = (hub.at("ne"), hub.at("se")) if anchored else (hub, hub)
    fig.link(source[0], up, route="orthogonal")
    fig.link(source[1], down, route="orthogonal")
    return fig


def two_boxes(dx: float, dy: float, *, label: str, side: str = "center",
              route: str = "orthogonal") -> inklet.Figure:
    a = inklet.box("A").named("A")
    b = inklet.box("B").named("B")
    fig = inklet.figure(width=90, height=80)
    fig.add(inklet.place([((0.0, 0.0), a), ((dx, dy), b)]))
    fig.link(a, b, label=label, label_side=side, route=route)
    return fig


def coded(fig, code: str) -> list:
    return [d for d in fig.lint() if d.code == code]


def only_coded(fig, code: str):
    found = coded(fig, code)
    assert len(found) == 1, [d.message for d in found]
    return found[0]


# -- COINCIDENT_SHAFT -----------------------------------------------------


def test_two_routes_leaving_a_box_centre_share_a_line():
    diag = only_coded(hub_and_spokes(), "COINCIDENT_SHAFT")

    assert diag.severity == "warning"
    assert "run along the same line for 14.2" in diag.message
    assert "one line wearing two arrowheads" in diag.message
    # Both links, in id order, so the finding is stable between runs.
    assert len(diag.targets) == 2
    assert diag.targets == tuple(sorted(diag.targets))
    assert ".at(" in diag.hint


def test_routes_leaving_from_anchors_are_silent():
    assert coded(hub_and_spokes(anchored=True), "COINCIDENT_SHAFT") == []


def test_two_links_that_merely_cross_are_silent():
    """The near miss. Two straight routes meeting at a point is ordinary --
    a reader resolves a crossing instantly, which is exactly what a shared run
    denies them."""
    hub = inklet.box("hub").named("hub")
    up = inklet.box("up").named("up")
    down = inklet.box("down").named("down")
    fig = inklet.figure(width=90)
    fig.add(inklet.place([((0.0, 0.0), hub), ((40.0, -14.0), up),
                       ((40.0, 14.0), down)]))
    fig.link(hub, down)
    fig.link(up, hub)

    assert coded(fig, "COINCIDENT_SHAFT") == []


def test_one_link_is_never_coincident_with_itself():
    """An orthogonal route doubling back has two of its own segments on one
    line. Segments are keyed by their owner so a link is never its own pair."""
    fig = two_boxes(-6.0, -24.0, label="", side="center")

    assert coded(fig, "COINCIDENT_SHAFT") == []


# -- LABEL_COVERS_SHAFT ---------------------------------------------------


def test_a_label_plate_over_an_elbow_leaves_a_ghost_stub():
    """The reported case: the plate swallows the corner of a short route.

    What the reader sees is a stub of line leaving A, a word, and an arrowhead
    under B with nothing joining them.
    """
    fig = two_boxes(12.0, -18.0, label="washing step done twice")

    diag = only_coded(fig, "LABEL_COVERS_SHAFT")

    assert diag.severity == "warning"
    assert "its own label plate covers 12.3" in diag.message
    assert "stub past the plate edge" in diag.message
    assert "label_side" in diag.hint


def test_a_label_beside_a_long_shaft_is_silent():
    """The exemption being kept: a label touching the line it names.

    The placer offsets a label along the route's normal, so on any route with
    room the plate sits beside the shaft and every millimetre of it stays
    visible.
    """
    fig = two_boxes(26.0, 12.0, label="washing step done twice")

    assert fig.lint() == []


def test_a_plate_grazing_the_end_of_its_own_shaft_is_below_the_threshold():
    """The near miss: 0.3mm of a 7mm shaft under the corner of the plate.

    The plate reaches the arrowhead, so the *stub* past its edge is nothing
    and the stub test alone would report it. `_MIN_COVERED_MM` is what keeps
    it quiet: a third of a millimetre is a plate touching the line it names,
    which is the exemption, not a plate hiding it.
    """
    fig = two_boxes(-6.0, -12.0, label="washing step done twice")

    assert coded(fig, "LABEL_COVERS_SHAFT") == []


def test_an_unplated_label_never_covers_anything():
    """Bare type over a line is ugly and the line is still there; only an
    opaque plate can remove a segment from the page."""
    a = inklet.box("A").named("A")
    b = inklet.box("B").named("B")
    fig = inklet.figure(width=90, height=80)
    fig.add(inklet.place([((0.0, 0.0), a), ((12.0, -18.0), b)]))
    fig.link(a, b, label="washing step done twice", label_plate=False,
             route="orthogonal")

    assert coded(fig, "LABEL_COVERS_SHAFT") == []


# -- LINK_CROSSES_LINK ----------------------------------------------------


def crossing_pair(*, target_port: float = 0.0) -> inklet.Figure:
    """Two boxes on the left, one on the right, both linked to it.

    With no port offset the two routes converge on the hub without meeting.
    Ports swap the arrival points, so the routes have to cross to reach them,
    and the size of the offset decides how far from the hub they do it.
    """
    a = inklet.box("a").named("a")
    b = inklet.box("b").named("b")
    hub = inklet.box("hub").named("hub")
    fig = inklet.figure(width=120)
    fig.add(inklet.place([((-40.0, -12.0), a), ((-40.0, 12.0), b),
                       ((40.0, 0.0), hub)]))
    fig.link(a, hub, target_port=target_port)
    fig.link(b, hub, target_port=-target_port)
    return fig


def test_two_routes_that_cross_are_one_info():
    """The case the linter could not see at all: `_pairable` drops unfilled
    paths, so two shafts meeting at a point were invisible to every rule."""
    a = inklet.box("A").named("A")
    b = inklet.box("B").named("B")
    c = inklet.box("C").named("C")
    d = inklet.box("D").named("D")
    fig = inklet.figure(width=120)
    fig.add(inklet.vstack([inklet.hstack([a, b], gap=30),
                        inklet.hstack([c, d], gap=30)], gap=25))
    fig.link(a, d)
    fig.link(b, c)

    found = only_coded(fig, "LINK_CROSSES_LINK")
    assert found.severity == "info"
    assert "A -> D" in found.message and "B -> C" in found.message
    assert "cross at" in found.message


def test_one_finding_per_pair_however_often_they_meet():
    """A route that weaves across another meets it three times and is one
    defect: the report names the pair once and counts the crossings."""
    left = inklet.box("left").named("left")
    right = inklet.box("right").named("right")
    top = inklet.box("top").named("top")
    bottom = inklet.box("bottom").named("bottom")
    fig = inklet.figure(width=120)
    fig.add(inklet.place([((-45.0, 0.0), left), ((45.0, 0.0), right),
                       ((0.0, -30.0), top), ((0.0, 30.0), bottom)]))
    fig.link(left, right)
    fig.link(top, bottom, route="orthogonal",
             waypoints=[(-20.0, 6.0), (0.0, -6.0), (20.0, 6.0)])

    found = only_coded(fig, "LINK_CROSSES_LINK")
    assert "at 3 points" in found.message, found.message


def test_a_fan_tangling_on_its_own_target_is_left_to_crowding():
    """Two arrows into one box arrive on different bearings, and the last
    millimetre of that is the box being too small for the fan -- which is a
    finding about the spacing, not about either connector."""
    assert coded(crossing_pair(target_port=1.0), "LINK_CROSSES_LINK") == []


def test_the_same_fan_crossing_clear_of_the_box_is_reported():
    """Far enough out and the two arrows have visibly swapped over, which is
    a defect the reader sees and the author can fix."""
    found = only_coded(crossing_pair(target_port=4.0), "LINK_CROSSES_LINK")
    assert "a -> hub" in found.message and "b -> hub" in found.message


def test_a_trunk_never_crosses_its_own_strands():
    """An orthogonal trunk's stem lands on the middle of its own rail, which
    is a T-junction between two of its segments. Segments are keyed by the
    link that owns them, and a trunk is one link."""
    a = inklet.box("a").named("a")
    b = inklet.box("b").named("b")
    c = inklet.box("c").named("c")
    fig = inklet.figure(width=120)
    fig.add(inklet.place([((-30.0, 0.0), a), ((30.0, -14.0), b),
                       ((30.0, 14.0), c)]))
    fig.link(a, [b, c], route="orthogonal")

    assert coded(fig, "LINK_CROSSES_LINK") == []


def test_a_self_loop_never_crosses_its_own_shaft():
    x = inklet.box("x").named("x")
    y = inklet.box("y").named("y")
    fig = inklet.figure(width=120)
    fig.add(inklet.place([((-20.0, 0.0), x), ((20.0, 0.0), y)]))
    fig.link(x, x, loop="n")
    fig.link(x, y)

    assert coded(fig, "LINK_CROSSES_LINK") == []


def test_collinear_routes_are_left_to_coincident_shaft():
    """Two lines lying along one another have no crossing point, and the
    worse of the two findings is the one that says they share a run."""
    fig = hub_and_spokes()

    assert coded(fig, "COINCIDENT_SHAFT") != []
    assert coded(fig, "LINK_CROSSES_LINK") == []


def test_a_crossing_under_a_label_plate_is_a_warning():
    """The plate is opaque, so the line under it disappears for as long as the
    plate is wide -- a reader sees an arrow that stops in a word.

    The router's label placer is good at dodging: it tries five spots along
    the shaft, each on both sides, and takes the least obstructed. Five posts
    across the line, one under each spot, is what it takes to leave it no
    clear choice -- which is also the honest measure of how rare the warning
    is on a routed figure.
    """
    a = inklet.box("A").named("A")
    b = inklet.box("B").named("B")
    fig = inklet.figure(width=140)
    posts, pairs = [], []
    for index, x in enumerate((-30.0, -19.0, -1.0, 17.0, 28.0)):
        top = inklet.box(" ").named(f"t{index}")
        foot = inklet.box(" ").named(f"u{index}")
        posts += [((x, -26.0), top), ((x, 26.0), foot)]
        pairs.append((top, foot))
    fig.add(inklet.place([((-50.0, 0.0), a), ((50.0, 0.0), b)] + posts))
    fig.link(a, b, label="binds tightly")
    for top, foot in pairs:
        fig.link(top, foot)

    found = coded(fig, "LINK_CROSSES_LINK")
    warned = [d for d in found if d.severity == "warning"]
    assert len(found) == 5, [d.message for d in found]
    assert len(warned) == 1, [d.message for d in found]
    assert "under a label plate" in warned[0].message
    assert warned[0].hint is not None and "label_side" in warned[0].hint



# -- CROWDING: arrowheads converging on one shape --------------------------


def fan(spokes: int, *, gap: float = 8.0) -> inklet.Figure:
    """`spokes` boxes in a column, each linked to one box on the right."""
    hub = inklet.box("hub").named("hub")
    sources = [inklet.box(f"s{n}").named(f"s{n}") for n in range(spokes)]
    figure = inklet.figure(width=90)
    figure.add(inklet.place(
        [((30.0, 0.0), hub)]
        + [((-30.0, (n - (spokes - 1) / 2.0) * gap), source)
           for n, source in enumerate(sources)]))
    for source in sources:
        figure.link(source, hub)
    return figure


def test_a_fan_of_arrows_is_one_finding_about_the_shape_they_hit():
    """Twenty-eight pairs of anonymous triangles say nothing an author can
    act on. The shape they all arrive at does."""
    found = [d for d in fan(8).lint() if d.code == "CROWDING"]

    assert len(found) == 1, [d.message for d in found]
    assert found[0].message.startswith("8 links arrive at hub; their heads are")
    assert "arrow_size=" in found[0].hint
    assert len(found[0].targets) == 8


def test_a_fan_with_room_around_its_heads_is_quiet():
    assert [d for d in fan(3, gap=20.0).lint() if d.code == "CROWDING"] == []
