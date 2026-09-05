"""KEY_MISMATCH: does the colour key describe the marks beside it?

Two defects with one code, because an author reads them the same way -- "the
key is lying" -- and fixes them in the same place:

* a colorbar whose ramp is not the ramp the cells were painted with (error:
  every number under the bar is wrong),
* a legend with an entry for a colour that is nowhere in the panel, or a mark
  colour with no entry (warning: the picture is right and the key is stale).

The legend half is the bug `figures/drug_discovery.py` shipped with -- a
response key written out by hand with all four RECIST classes on it while the
waterfall only ever drew three. `test_a_hand_written_key_with_an_empty_class`
is that figure, reduced.
"""

from __future__ import annotations

from types import SimpleNamespace

import inklet
from inklet.diagnostics.key_rules import _declared_domain

# The four RECIST classes and their colours, as the figure had them.
RESPONSE = {"complete": "#1b5e20", "partial": "#0072b2",
            "stable": "#9a9a9a", "progressive": "#b8860b"}

#: Per-patient change, and the class each one falls into. No patient is a
#: complete responder, which is the whole point of the reduction.
CHANGES = [-62.0, -48.0, -31.0, -12.0, 4.0, 18.0, 33.0, 51.0]
CLASSES = ["partial", "partial", "partial", "stable",
           "stable", "progressive", "progressive", "progressive"]

MATRIX = [[4.8, 5.6, 6.4], [7.1, 7.9, 8.6], [5.2, 9.1, 6.0]]


# -- builders -------------------------------------------------------------


def waterfall(classes: list[str], width: float = 66.0) -> inklet.Diagram:
    """A response waterfall: one bar per patient, coloured by its class."""
    p = inklet.panel(width, 40.0, x=(-0.6, len(CHANGES) - 0.4), y=(-100.0, 55.0))
    bars = [inklet.polygon(p.map([(i - 0.42, 0.0), (i + 0.42, 0.0),
                               (i + 0.42, change), (i - 0.42, change)]),
                        fill=RESPONSE[cls], stroke="none", kind="mark")
            for i, (change, cls) in enumerate(zip(CHANGES, classes))]
    p.draw(*bars)
    p.axis("left", ticks=[-100, -50, 0, 50], label="change (%)")
    return p.build()


def keyed_waterfall(entries, classes=None, width=66.0):
    """A waterfall with a legend under it, as a built figure."""
    key = inklet.legend([(name, RESPONSE[name]) for name in entries],
                     swatch=1.5, columns=2, title="best response")
    fig = inklet.figure(width=90)
    fig.add(inklet.vstack([waterfall(classes or CLASSES, width), key],
                       gap=2.4, align="center"))
    return fig


def heatmap(bar_ramp, cell_ramp, values=MATRIX):
    """A 3x3 matrix beside a colorbar, each with its own ramp."""
    scale = inklet.linear((4.5, 9.5))
    p = inklet.panel(30.0, 30.0, x=["a", "b", "c"], y=["x", "y", "z"])
    p.matrix(values, ramp=cell_ramp, scale=scale)
    p.axis("bottom", ticks=["a", "b", "c"])
    key = inklet.colorbar(bar_ramp, domain=(4.5, 9.5), scale=scale,
                       length=26.0, thickness=2.4, label="pIC50")
    fig = inklet.figure(width=70)
    fig.add(inklet.hstack([p.build(), key], gap=3.0, align="center"))
    return fig


def rastered(bar_ramp, cell_ramp, values=MATRIX, domain=(4.5, 9.5)):
    """The same heatmap with the cells rasterised into one PNG."""
    scale = inklet.linear(domain)
    p = inklet.panel(30.0, 30.0, x=["a", "b", "c"], y=["x", "y", "z"])
    p.matrix(values, ramp=cell_ramp, scale=scale, raster=True)
    p.axis("bottom", ticks=["a", "b", "c"])
    key = inklet.colorbar(bar_ramp, domain=(4.5, 9.5), scale=inklet.linear((4.5, 9.5)),
                       length=26.0, thickness=2.4, label="pIC50")
    fig = inklet.figure(width=70)
    fig.add(inklet.hstack([p.build(), key], gap=3.0, align="center"))
    return fig


def mismatches(fig) -> list:
    return [d for d in fig.lint() if d.code == "KEY_MISMATCH"]


def only_mismatch(fig):
    found = mismatches(fig)
    assert len(found) == 1, [d.message for d in found]
    return found[0]


# -- (a) a colorbar against the cells it stands beside --------------------


def test_a_colorbar_on_a_different_ramp_than_its_matrix():
    fig = heatmap(inklet.ramp("tol-ylorbr"), inklet.ramp("tol-sunset"))

    diag = only_mismatch(fig)

    assert diag.severity == "error"
    # Both ends of the bar, so the author can see which ramp it is.
    assert "#ffffe4" in diag.message and "#682506" in diag.message
    assert "9 of the 9 colours" in diag.message
    assert "ramp=" in diag.hint and "scale=" in diag.hint


def test_a_colorbar_on_the_same_ramp_is_silent():
    assert heatmap(inklet.ramp("tol-ylorbr"), inklet.ramp("tol-ylorbr")).lint() == []


def test_cells_using_only_the_bottom_of_the_ramp_are_not_a_mismatch():
    """The near miss: same ramp, but the data never reaches the top of it.

    Every cell colour is a sample of the bar, taken from its first third. A
    rule that compared coverage rather than membership would call this a
    mismatch, and it is the commonest honest heatmap there is.
    """
    dull = [[4.6, 4.9, 5.2], [5.4, 5.6, 5.0], [4.7, 5.5, 5.1]]

    assert heatmap(inklet.ramp("tol-ylorbr"), inklet.ramp("tol-ylorbr"), dull).lint() == []


def test_a_colorbar_beside_a_two_colour_panel_is_not_its_key():
    """The other near miss, and the one the corpus found.

    `stress/draw_probe.py` parks a z-score bar in a row with two line panels
    it does not describe. A continuous field paints a colour per value, so a
    panel with one or two mark colours is categorical and the bar belongs to
    something else on the sheet; calling that an error would be the linter
    guessing at layout intent.
    """
    p = inklet.panel(30.0, 30.0, x=(0.0, 4.0), y=(0.0, 4.0))
    p.marks(inklet.marker("circle", 1.8, fill="#0072b2"), [(1.0, 1.0), (2.0, 2.0)])
    p.marks(inklet.marker("triangle", 1.8, fill="#009e73"), [(3.0, 1.0)])
    p.axis("bottom", ticks=[0, 2, 4])
    bar = inklet.colorbar(inklet.ramp("tol-sunset"), domain=(-2.0, 2.0),
                       length=26.0, thickness=2.4, label="z-score")
    fig = inklet.figure(width=70)
    fig.add(inklet.hstack([p.build(), bar], gap=3.0, align="center"))

    assert mismatches(fig) == []


def test_a_colorbar_beside_a_rasterised_matrix_is_still_checked():
    """The cells are pixels inside a PNG, so there is nothing in the tree to
    read their colours off. `plot.raster` leaves them on the node instead."""
    diag = only_mismatch(rastered(inklet.ramp("tol-ylorbr"),
                                  inklet.ramp("tol-sunset")))

    assert diag.severity == "error"
    assert "#ffffe4" in diag.message and "#682506" in diag.message
    assert "of the 9 colours" in diag.message


def test_a_rasterised_matrix_on_the_bars_own_ramp_is_silent():
    assert rastered(inklet.ramp("tol-ylorbr"), inklet.ramp("tol-ylorbr")).lint() == []


def test_a_rasterised_matrix_on_a_different_domain_clashes():
    # One ramp, two domains: the pixels are identical either way and only the
    # declared domain says the bar is lying.
    shades = inklet.ramp("tol-sunset")
    fig = rastered(shades, shades, domain=(0.0, 100.0))

    found = only_mismatch(fig)

    assert found.severity == "error"
    assert "labelled over 4.5..9.5" in found.message
    assert "mapped over 0..100" in found.message


# -- (b) a legend against the marks it stands beside ----------------------


def test_a_hand_written_key_with_an_empty_class():
    """`figures/drug_discovery.py`'s waterfall, as it shipped.

    The key was written from the list of RECIST classes rather than from the
    classes present, so it carried a green swatch for "complete" that no bar
    in the panel used. Nothing in the linter could see it.
    """
    fig = keyed_waterfall(("complete", "partial", "stable", "progressive"))

    diag = only_mismatch(fig)

    assert diag.severity == "warning"
    assert "1 entry" in diag.message
    assert "#1b5e20 (complete)" in diag.message
    assert diag.targets == tuple(sorted(diag.targets))


def test_a_key_built_from_the_values_plotted_is_silent():
    assert keyed_waterfall(sorted(set(CLASSES))).lint() == []


def test_a_mark_colour_with_no_swatch_is_reported():
    fig = keyed_waterfall(("partial", "stable"))

    diag = only_mismatch(fig)

    assert diag.severity == "warning"
    assert "1 colour " in diag.message and "#b8860b" in diag.message


def test_the_nearest_panel_is_the_one_the_key_stands_beside():
    """Two panels, one key. The finding must name the adjacent panel.

    Nearest is (shared ancestry, then gap, then id): all three are laid out
    as siblings here, so the gap decides, and the key is hard against the
    right-hand panel.
    """
    plain = waterfall(["partial"] * len(CHANGES), width=30.0)
    mixed = waterfall(CLASSES, width=30.0)
    key = inklet.legend([(name, RESPONSE[name]) for name in RESPONSE],
                     swatch=1.5, columns=1, title="best response")
    fig = inklet.figure(width=140)
    fig.add(inklet.hstack([plain, mixed, key], gap=4.0, align="center"))

    diag = only_mismatch(fig)

    named = [t for t in diag.targets if t.startswith("panel")]
    assert named and named[0] in diag.message
    assert plain.id not in diag.targets


def test_a_legend_with_no_panel_beside_it_is_silent():
    fig = inklet.figure(width=60)
    fig.add(inklet.legend([(name, RESPONSE[name]) for name in RESPONSE],
                       swatch=1.5, columns=2))

    assert mismatches(fig) == []


def test_a_key_that_belongs_to_a_drawing_is_not_paired_with_a_panel():
    """A streams key in the margin of a 3D cell, beside a plot panel.

    The key's colours are link strokes in the scene and nothing in the plot
    panel next door ever draws them -- which is correct, not a finding. The
    rule must see that the key's own branch already carries a subject and
    leave the plot panel out of it. `stress/electro_figure.py` panel (a), reduced.
    """
    cell = inklet.solid("box", width=24, view="isometric", style="shaded")
    key = inklet.legend(
        [("gas", inklet.polyline([(0, 0), (5.5, 0)], stroke="#0072b2",
                              stroke_width=0.5)),
         ("liquid", inklet.polyline([(0, 0), (5.5, 0)], stroke="#009e73",
                                 stroke_width=0.5, stroke_dash="1.2,0.8"))],
        title="streams")
    drawing = inklet.vstack([cell, key], gap=3.0)
    plot = waterfall(CLASSES, width=40.0)
    fig = inklet.figure(width=120)
    fig.add(inklet.hstack([drawing, plot], gap=4.0, align="center"))

    assert mismatches(fig) == []

    # The same key stacked under the panel instead *is* that panel's key.
    fig = inklet.figure(width=120)
    fig.add(inklet.hstack([cell, inklet.vstack([waterfall(CLASSES, width=40.0),
                                          key.copy()], gap=3.0)],
                       gap=4.0, align="center"))
    found = mismatches(fig)
    assert found and all(d.code == "KEY_MISMATCH" for d in found)


# -- the domain hook ------------------------------------------------------


def test_a_bar_and_a_matrix_on_different_domains_clash():
    """The one case colour cannot see, now that `inklet.plot` records the domain.

    Two ramps that agree draw the same colours whatever their domains, so a
    bar reading 0..100 over a matrix mapped 0..10 is invisible to the colour
    test -- and is the most misleading key a figure can carry, because every
    number under it is wrong by a factor of ten.
    """
    shades = inklet.ramp("tol-sunset")
    field = [[c / 9.0 * 10.0 for c in range(10)] for _ in range(6)]
    p = inklet.panel(60.0, 40.0)
    p.matrix(field, ramp=shades, scale=inklet.linear((0.0, 10.0)))
    key = inklet.colorbar(shades, scale=inklet.linear((0.0, 100.0)), length=40.0,
                       label="score")
    fig = inklet.figure(width=120)
    fig.add(inklet.hstack([p.build(), key], gap=4.0))

    found = only_mismatch(fig)

    assert found.severity == "error"
    assert "labelled over 0..100" in found.message
    assert "mapped over 0..10" in found.message


def test_a_declared_domain_is_read_when_the_plot_layer_sets_one():
    """The contract `_declared_domain` expects of whoever leaves the note:
    two numbers under `scale_domain`, and silence for anything else.

    A note and only a note. The plain `scale_domain` attribute the plot layer
    used to stamp beside it is gone, and a node carrying one is not a
    declaration -- which is what keeps `figure.py` out of the business of
    copying annotations across a restyle by name.
    """
    assert _declared_domain(
        SimpleNamespace(notes={"scale_domain": (0, 100)})) == (0.0, 100.0)
    assert _declared_domain(SimpleNamespace(notes={})) is None
    assert _declared_domain(SimpleNamespace()) is None
    assert _declared_domain(
        SimpleNamespace(notes={"scale_domain": "0..100"})) is None
    assert _declared_domain(SimpleNamespace(scale_domain=(0, 100))) is None
    assert _declared_domain(None) is None
