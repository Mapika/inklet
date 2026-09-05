"""inklet.plot: keys built from what the panel actually drew.

The point of the auto legend is that a key cannot describe a picture that is no
longer there, so most of these tests are about the *record* -- what colour,
dash and marker a named series was remembered with -- rather than about the
geometry of the finished block.
"""

from __future__ import annotations

import pytest

from inklet.core import DiagramError, resolve
from inklet.draw import marker
from inklet.draw.coords import as_drawn
from inklet.plot import panel, ramp
from inklet.plot.key import LEGEND_LABEL_KIND
from inklet.plot.scale import Linear
from inklet.themes import theme as get_theme

LINE = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.5)]


def texts(node, kind: str = LEGEND_LABEL_KIND) -> list[str]:
    found = []
    for placed in resolve(as_drawn(node)).values():
        if placed.diagram.kind == kind:
            prim = placed.diagram.prim
            if prim is not None and hasattr(prim, "text"):
                found.append(prim.text)
    return found


# --- the record --------------------------------------------------------------


def test_a_named_line_is_remembered_as_a_line() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1)).line(LINE, name="wt")
    (entry,) = p.keys
    assert entry.name == "wt"
    assert entry.forms == frozenset({"line"})


def test_nothing_is_remembered_without_a_name() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1)).line(LINE)
    assert p.keys == ()


def test_two_calls_under_one_name_make_one_entry() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.band([0, 1, 2], [0, 0.5, 0], [1, 1.5, 1], name="wt")
    p.line(LINE, name="wt")
    (entry,) = p.keys
    assert entry.forms == frozenset({"area", "line"})


def test_entries_keep_the_order_they_were_first_drawn_in() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="b").line(LINE, name="a").line(LINE, name="b")
    assert [e.name for e in p.keys] == ["b", "a"]


def test_a_named_series_takes_the_next_palette_colour() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="one").line(LINE, name="two")
    palette = [get_theme("nature").color(i) for i in range(2)]
    assert [e.color for e in p.keys] == palette


def test_an_explicit_colour_is_never_overridden() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="one", stroke="#123456")
    assert p.keys[0].color == "#123456"


def test_a_band_takes_the_colour_its_line_was_given() -> None:
    """The two calls share a name, so the caller does not hold the value."""
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="wt", stroke="#008800")
    p.band([0, 1, 2], [0, 0.5, 0], [1, 1.5, 1], name="wt")
    (entry,) = p.keys
    assert entry.color == "#008800"
    assert entry.fill is not None and entry.fill != "#008800"


def test_a_dash_is_part_of_the_record() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="model", stroke_dash=(1.0, 1.0))
    assert p.keys[0].dash == (1.0, 1.0)


def test_a_marker_series_records_its_shape() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.scatter(LINE, name="obs", marker="square")
    (entry,) = p.keys
    assert entry.forms == frozenset({"marker"})
    assert entry.marker == "square"


def test_marks_records_the_shape_it_was_handed() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.marks(marker("triangle"), LINE, name="obs")
    (entry,) = p.keys
    assert entry.node is not None


def test_bars_name_their_series() -> None:
    p = panel(40, 30, x=["a", "b"], y=(0, 3))
    p.bars(["a", "b"], [[1, 2], [2, 1]], names=["ctrl", "drug"])
    assert [e.name for e in p.keys] == ["ctrl", "drug"]
    assert all(e.fill is not None for e in p.keys)


def test_a_mismatch_between_names_and_series_is_refused() -> None:
    p = panel(40, 30, x=["a", "b"], y=(0, 3))
    with pytest.raises(DiagramError, match="names="):
        p.bars(["a", "b"], [[1, 2], [2, 1]], names=["only one"])


def test_a_twin_axis_shares_the_key() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="left")
    p.twin_y((0, 100)).line([(0, 10), (2, 90)], name="right")
    assert [e.name for e in p.keys] == ["left", "right"]


# --- the block ---------------------------------------------------------------


def test_the_legend_names_every_series() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="wt").line(LINE, name="mutant").legend()
    assert set(texts(p.build())) == {"wt", "mutant"}


def test_a_legend_with_nothing_to_say_explains_itself() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1)).line(LINE)
    with pytest.raises(DiagramError, match="name="):
        p.legend()


def test_entries_override_the_record() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="wt").legend(entries=[("something else", "#ff0000")])
    assert texts(p.build()) == ["something else"]


def test_a_corner_legend_stays_inside_the_plot_area() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="wt").legend(corner="ne")
    area = p.area
    box = p.build().bbox
    assert box.x1 <= area.x1 + 1e-6
    assert box.y0 >= area.y0 - 1e-6


def test_a_side_legend_stands_outside_it() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 1))
    p.line(LINE, name="wt").legend(side="right")
    assert p.build().bbox.x1 > p.area.x1


def test_the_corner_can_be_chosen() -> None:
    corners = {}
    for corner in ("ne", "nw", "se", "sw"):
        p = panel(40, 30, x=(0, 2), y=(0, 1))
        p.line(LINE, name="wt").legend(corner=corner)
        corners[corner] = p._over[-1].bbox.center
    assert corners["nw"].x < corners["ne"].x
    assert corners["nw"].y < corners["sw"].y


# --- the colorbar ------------------------------------------------------------


def test_a_colorbar_comes_from_the_matrix_that_was_drawn() -> None:
    field = [[0.0, 0.5], [1.0, 0.25]]
    scale = Linear((0.0, 1.0), (0.0, 1.0))
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.matrix(field, ramp=ramp("tol-sunset"), scale=scale).colorbar()
    assert p.build().bbox.x1 > p.area.x1


def test_a_colorbar_without_a_matrix_says_what_to_do() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match="matrix"):
        p.colorbar()
