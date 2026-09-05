"""Sankey layout: the promises a flow diagram makes about its own widths.

A Sankey is read quantitatively -- the reader takes a proportion straight off
the thickness of a band -- so the invariants worth pinning are the ones that
keep that reading true: one scale for the whole page, a bar as tall as what
goes through it, ribbons that tile a node face exactly, and an ordering pass
that is a pure function of the input. Millimetres move whenever a constant is
tuned and are not asserted; the promises are.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import resolve
from inklet.layout import Sankey, SankeyError, sankey

# Three ranks, a fan-in and a fan-out, dictated in an order that crosses:
# the glial branch is written before the two that feed the same two fates.
FLOWS = [
    ("pool", "ipc", 42), ("pool", "org", 25), ("pool", "glia", 21),
    ("glia", "astro", 13), ("glia", "oligo", 7),
    ("ipc", "deep", 15), ("ipc", "upper", 24),
    ("org", "upper", 17), ("org", "deep", 6),
]

# Four ranks, twelve nodes, three flows that skip a rank, dictated worst-first.
# The adversarial fixture: the ordering pass has to beat 34 crossings, and the
# numbers below are checked against an exhaustive search in
# `test_adversarial_fixture_reaches_the_brute_force_optimum`.
ADVERSARIAL = [
    ("feed", "b3", 30), ("feed", "b2", 45), ("feed", "b1", 60),
    ("b1", "c4", 12), ("b1", "c1", 30), ("b1", "c2", 18),
    ("b2", "c3", 20), ("b2", "c2", 15), ("b2", "c1", 10),
    ("b3", "c4", 18), ("b3", "c3", 12),
    ("c1", "d3", 22), ("c1", "d1", 18),
    ("c2", "d2", 20), ("c2", "d1", 13),
    ("c3", "d4", 17), ("c3", "d2", 15),
    ("c4", "d4", 20), ("c4", "d3", 10),
    ("b1", "d1", 8), ("b2", "d4", 9), ("b3", "d2", 7),
]


def build(flows=FLOWS, **kw) -> Sankey:
    kw.setdefault("length", 120)
    kw.setdefault("breadth", 60)
    return inklet.sankey(flows, **kw)


def drawn(sk):
    """Every band's four corners and every bar's rectangle, in figure space.

    A path prim is stored centred on its own origin with the offset in the
    transform, so the corners have to come back through `resolve` to be
    comparable with anything else. Reading the *drawn* geometry rather than
    the layout's own bookkeeping is the point: it is what a reader measures.
    """
    placed = resolve(sk.diagram)
    bands = {}
    for flow in sk.flows:
        world = placed[flow.diagram.id].world
        curves = flow.diagram.prim.subpaths[0].curves
        bands[flow] = tuple(world.apply(p) for p in
                            (curves[0][0], curves[2][3], curves[0][3], curves[2][0]))
    bars = {node.key: placed[node.diagram.id].bbox for node in sk.nodes}
    return bands, bars


def face_of(bands, key, outgoing, axis="y"):
    """The intervals one node's ribbons claim on one of its two faces."""
    spans = []
    for flow, (a0, a1, b0, b1) in bands.items():
        node = flow.source if outgoing else flow.target
        if node.key != key:
            continue
        lo, hi = (a0, a1) if outgoing else (b0, b1)
        lo, hi = getattr(lo, axis), getattr(hi, axis)
        spans.append((min(lo, hi), max(lo, hi)))
    return sorted(spans)


# -- the scale ------------------------------------------------------------


def test_one_scale_for_the_whole_page():
    """Two bars of the same value are the same height, whatever their rank."""
    sk = build()
    heights = {node.key: node.box.height for node in sk.nodes}
    values = {node.key: node.value for node in sk.nodes}
    for key, height in heights.items():
        assert height == pytest.approx(values[key] * sk.unit, abs=1e-9)


def test_bar_height_is_throughput_not_inflow():
    """A node that leaks -- more in than out -- is as tall as the larger side."""
    sk = build([("a", "b", 10), ("b", "c", 4)])
    assert sk.node("b").value == 10.0
    assert sk.node("b").box.height == pytest.approx(10.0 * sk.unit)


def test_the_tightest_column_fills_the_breadth():
    """The scale is the one that fits, so some column reaches the full height."""
    sk = build(breadth=48)
    span = max(node.box.y1 for node in sk.nodes) - min(node.box.y0 for node in sk.nodes)
    assert span == pytest.approx(48.0, abs=1e-6)


def test_ribbon_is_as_wide_as_its_value():
    """At both ends: the width of a band is the datum, not a decoration."""
    sk = build()
    bands, _ = drawn(sk)
    for flow, (a0, a1, b0, b1) in bands.items():
        assert abs(a1.y - a0.y) == pytest.approx(flow.value * sk.unit, abs=1e-9)
        assert abs(b1.y - b0.y) == pytest.approx(flow.value * sk.unit, abs=1e-9)


# -- the node face --------------------------------------------------------


def test_bands_tile_a_node_face_with_no_gap_and_no_overlap():
    """Adjacent bands share an edge *exactly*, not to within a tolerance.

    The stacking is a single running cursor per face for this reason: a face
    walked twice, or summed two different ways, leaves hairlines that survive
    into the PDF. In the layout's own frame the two edges are the same float;
    the tolerance here is only the two bands' separate centring transforms,
    and it is four orders of magnitude below anything a device pixel can show.
    """
    bands, _ = drawn(build(ADVERSARIAL))
    for key in {node.key for flow in bands for node in (flow.source, flow.target)}:
        for outgoing in (True, False):
            spans = face_of(bands, key, outgoing)
            for (_, end), (start, _) in zip(spans, spans[1:]):
                assert start == pytest.approx(end, abs=1e-12), \
                    f"{key}: {end!r} then {start!r}"


def test_a_face_is_centred_on_its_bar_and_no_taller():
    """A full face fills the bar; a partial one sits centred inside it."""
    bands, bars = drawn(build(ADVERSARIAL))
    for key, bar in bars.items():
        for outgoing in (True, False):
            spans = face_of(bands, key, outgoing)
            if not spans:
                continue
            lo, hi = spans[0][0], spans[-1][1]
            assert lo >= bar.y0 - 1e-9 and hi <= bar.y1 + 1e-9
            assert (lo + hi) / 2.0 == pytest.approx(bar.center.y, abs=1e-9)


def test_ribbons_run_bar_centre_to_bar_centre():
    """So the visible attachment is the opaque bar's own edge, with no seam."""
    bands, bars = drawn(build())
    for flow, (a0, _, b0, _) in bands.items():
        assert a0.x == pytest.approx(bars[flow.source.key].center.x, abs=1e-9)
        assert b0.x == pytest.approx(bars[flow.target.key].center.x, abs=1e-9)


def test_two_bands_out_of_one_bar_do_not_cross_each_other():
    """The face is ordered by where the far end sits, so the fan stays a fan."""
    sk = build(ADVERSARIAL)
    bands, _ = drawn(sk)
    for node in sk.nodes:
        out = [f for f in sk.flows if f.source.key == node.key]
        near = {f.target.key: bands[f][0].y for f in out}
        far = {f.target.key: bands[f][2].y for f in out}
        assert sorted(near, key=lambda k: near[k]) == sorted(far, key=lambda k: far[k])


# -- ordering -------------------------------------------------------------


def test_ordering_beats_the_order_the_author_typed():
    """The three-rank fixture: nine crossings dictated, one after the pass.

    One rather than none because one is the optimum -- checked against all 144
    arrangements of its two free columns in the same brute force the
    adversarial fixture gets.
    """
    assert (build(order="given").crossings, build().crossings) == (9, 1)


def optimum(flows, length=120, breadth=60):
    """The fewest crossings any arrangement of the free columns achieves.

    Exhaustive, and only affordable because the fixtures are small -- which is
    the point: the greedy's numbers are checked against the truth rather than
    against themselves.
    """
    from importlib import import_module
    from itertools import permutations, product

    impl = import_module("inklet.layout.sankey")
    keys, edges = impl._read(flows, ())
    ranks = impl._ranks(len(keys), edges)
    metrics = impl._Metrics(len(keys), edges, ranks, impl._values(len(keys), edges))
    names = impl._names(keys, None, None)
    sizes = impl._sizes(length, breadth, None, None, None, names, ranks, "right")
    columns = impl._columns(ranks)
    every = list(product(*(permutations(column) for column in columns)))
    best = min(impl._score(tuple(c), metrics, sizes, impl.DEFAULT_RELAX)
               for c in every)
    return best, len(every)


@pytest.mark.parametrize("flows, given, found, arrangements", [
    (FLOWS, 9, 1, 144),
    (ADVERSARIAL, 34, 9, 3456),
])
def test_the_ordering_pass_reaches_the_brute_force_optimum(flows, given, found,
                                                           arrangements):
    """Both fixtures, before and after, against every arrangement there is.

    The adversarial one is the case that matters: four ranks, twelve nodes and
    three flows that skip a rank, dictated worst-first. The greedy does not
    always land on the optimum -- `stress/flow.py` sits one crossing above it,
    three adjacent swaps away across two columns -- which is why this is a
    measurement and not a claim.
    """
    assert build(flows, order="given").crossings == given
    assert build(flows).crossings == found
    assert optimum(flows) == (found, arrangements)


def test_a_pass_is_offered_never_imposed():
    """No arrangement the layout picks is worse than the one it started from."""
    for flows in (FLOWS, ADVERSARIAL, [("a", "b", 1), ("a", "c", 2)]):
        assert build(flows).crossings <= build(flows, order="given").crossings


def test_sweeps_zero_leaves_only_the_swap_polish():
    """`sweeps=0` turns the barycentre passes off; the polish still runs.

    Which is worth pinning separately, because it is the split the two halves
    of the greedy get measured by: on the adversarial fixture the swaps alone
    take 34 down to 14, and the barycentre passes are what find the other 5.
    """
    assert build(ADVERSARIAL, sweeps=0).crossings == 14


def test_nodes_fixes_the_given_order():
    """`nodes=` is how an author pins an arrangement the greedy will not find."""
    order = ["pool", "ipc", "org", "glia", "deep", "upper", "astro", "oligo"]
    sk = build(nodes=order, order="given")
    assert [node.key for node in sk.nodes] == order


# -- determinism ----------------------------------------------------------


def test_the_same_input_gives_the_same_geometry():
    """Twice built, not twice rendered: node ids count up per process, so the
    property that actually holds is that every millimetre matches."""
    one, other = build(ADVERSARIAL, length=150), build(ADVERSARIAL, length=150)
    assert [node.box for node in one.nodes] == [node.box for node in other.nodes]
    assert one.crossings == other.crossings and one.unit == other.unit
    assert [drawn(one)[0][f] for f in one.flows] == \
        [drawn(other)[0][f] for f in other.flows]


def test_one_figure_renders_the_same_bytes_twice():
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE, theme="nature")
    fig.add(build(ADVERSARIAL, length=150).diagram)
    assert fig.to_svg() == fig.to_svg()


def test_key_order_not_dict_order_decides_the_layout():
    """Shuffling a labels/colour mapping cannot move a millimetre."""
    labels = {key: key.upper() for key in ("pool", "ipc", "org", "glia")}
    one = build(labels=labels)
    other = build(labels=dict(reversed(list(labels.items()))))
    assert [n.box for n in one.nodes] == [n.box for n in other.nodes]


# -- what the caller gets back --------------------------------------------


def test_handles_survive_the_layout():
    sk = build()
    assert sk["ipc"] is sk.node("ipc").diagram
    assert sk[0] is sk.nodes[0].diagram


def test_a_bar_can_be_annotated_after_the_fact():
    """`annotate` returns the target's whole tree, so the annotated drawing is
    what goes on the figure -- the bar handle still resolves inside it."""
    sk = build()
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE, margin=4)
    art = inklet.annotate(sk["upper"], "most of the cohort", side="e",
                       within=sk.diagram)
    fig.add(art)
    assert sk["upper"].id in resolve(art)
    assert fig.to_svg().count("<svg") == 1


def test_add_to_puts_the_drawing_on_a_figure():
    sk = build()
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE, margin=4)
    assert sk.add_to(fig) is sk.diagram
    assert "<path" in fig.to_svg()


def test_unknown_key_raises_key_error():
    sk = build()
    with pytest.raises(KeyError):
        sk["missing"]


def test_flows_resolve_to_their_nodes():
    sk = build()
    first = sk.flows[0]
    assert (first.source.key, first.target.key) in {(a, b) for a, b, _ in FLOWS}
    assert first.value == dict(((a, b), v) for a, b, v in FLOWS)[
        (first.source.key, first.target.key)]


# -- direction ------------------------------------------------------------


def test_down_stacks_across_x():
    """The same drawing turned a quarter turn: ranks in y, columns in x."""
    sk = build(direction="down", length=60, breadth=90)
    ranks = {}
    for node in sk.nodes:
        ranks.setdefault(node.rank, []).append(node)
    for column in ranks.values():
        assert len({round(node.box.center.y, 9) for node in column}) == 1
    tops = [min(n.box.center.y for n in ranks[r]) for r in sorted(ranks)]
    assert tops == sorted(tops)
    for node in sk.nodes:
        assert node.box.width == pytest.approx(node.value * sk.unit, abs=1e-9)


# -- fitting the column ---------------------------------------------------


def test_length_includes_the_end_labels():
    """`length=` is what the figure has room for, names and all."""
    sk = build(length=100, labels={k: "a rather long name" for k, _, _ in FLOWS})
    assert sk.width <= 100.0 + 1e-6


def test_no_room_for_the_flow_is_an_error():
    with pytest.raises(SankeyError, match="raise length="):
        build(length=30, labels={k: "an extremely long node name" for k, _, _ in FLOWS})


def test_a_column_that_cannot_fit_is_an_error():
    with pytest.raises(SankeyError, match="raise breadth="):
        build(breadth=4)


# -- the input ------------------------------------------------------------


@pytest.mark.parametrize("flows, message", [
    ([("a", "b", 1), ("b", "a", 1)], "cycle"),
    ([("a", "a", 1)], "cannot feed itself"),
    ([("a", "b", 1), ("a", "b", 2)], "repeats"),
    ([("a", "b")], "a flow is"),
    ([("a", "b", 0)], "has to be positive"),
    ([("a", "b", -3)], "has to be positive"),
    ([], "at least one flow"),
])
def test_bad_flows_say_what_is_wrong(flows, message):
    with pytest.raises(SankeyError, match=message):
        sankey(flows, length=80, breadth=40)


@pytest.mark.parametrize("kw, message", [
    ({"order": "spiral"}, "unknown sankey order"),
    ({"direction": "left"}, "unknown sankey direction"),
    ({"tint": "middle"}, "unknown sankey tint"),
    ({"opacity": 0.0}, "opacity must be"),
    ({"opacity": 1.5}, "opacity must be"),
    ({"sweeps": -1}, "cannot be negative"),
    ({"halo": -1.0}, "halo cannot be negative"),
])
def test_bad_options_say_what_is_wrong(kw, message):
    with pytest.raises(SankeyError, match=message):
        build(**kw)


def test_an_unhashable_key_is_named_in_the_error():
    with pytest.raises(SankeyError, match="not hashable"):
        sankey([(["a"], "b", 1)], length=80, breadth=40)


# -- on the page ----------------------------------------------------------


def test_a_sankey_lints_clean():
    """Bands touching bars, and each other, are declared -- not reported.

    The crossing rules do not fire on filled bands at all (PATH_CROSSES tests
    free strokes), so the only rule with anything to say here is OVERLAP,
    between a haloed name and the band beneath it. That is `inklet.abutting` on
    the group: these parts touch by design.
    """
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE, theme="nature", margin=2)
    fig.add(build(ADVERSARIAL, length=150, breadth=60).diagram)
    assert fig.lint() == []


def test_labels_false_draws_no_text():
    sk = build(labels=False)
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE)
    fig.add(sk.diagram)
    assert "<text" not in fig.to_svg()
