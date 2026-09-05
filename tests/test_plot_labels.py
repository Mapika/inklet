"""inklet.plot: what a label says -- data read literally, prose read as markup."""

from __future__ import annotations

import pytest

from inklet.core import resolve
from inklet.draw.coords import as_drawn
from inklet.plot import linear, log, panel
from inklet.plot.scale import Log
from inklet.plot.timescale import dates
from inklet import use_theme

DAYS = [f"2024-03-{day:02d}" for day in range(1, 20, 3)]
YEARS = [f"{year}-06-01" for year in range(2019, 2025)]


def words(node) -> list[str]:
    """Every string that reached the page, in document order."""
    return [placed.diagram.prim.text
            for placed in resolve(as_drawn(node)).values()
            if getattr(placed.diagram.prim, "text", None) is not None]


def said(node, text: str) -> bool:
    return any(text == word for word in words(node))


# --- data strings are not markup ---------------------------------------------


def test_a_category_keeps_its_asterisks() -> None:
    """`Notch1**` is a gene with a footnote, not a request for bold."""
    p = panel(40, 30, x=["Notch1**", "Dll4"], y=(0, 10))
    p.bars(["Notch1**", "Dll4"], [4.0, 6.0])
    p.axis("bottom")
    assert said(p.build(), "Notch1**")


def test_a_category_keeps_its_slashes() -> None:
    p = panel(40, 30, x=["//in vitro//", "in vivo"], y=(0, 10))
    p.bars(["//in vitro//", "in vivo"], [4.0, 6.0])
    p.axis("bottom")
    assert said(p.build(), "//in vitro//")


def test_a_legend_name_keeps_its_asterisks() -> None:
    """Still true after round 4 turned legend names into prose, and for a
    better reason than the old one: `Notch1**` has no closing pair, and an
    unpartnered delimiter is ordinary text in this grammar. See
    `tests/test_round4_plot.py` for the paired case, which is now italic."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.line([(0, 0), (10, 10)], name="Notch1**")
    p.legend()
    assert said(p.build(), "Notch1**")


def test_an_axis_name_is_still_prose() -> None:
    """The one string the author wrote for the reader keeps its markup."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.axis("bottom", label="//v// / mm s^{-1}")
    said_words = words(p.build())
    assert not any("//" in word or "^{" in word for word in said_words)
    assert any(word.startswith("v /") for word in said_words)


def test_panel_text_can_be_read_literally() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.text(5, 5, "//in vitro//", markup=False)
    assert said(p.build(), "//in vitro//")


def test_panel_text_is_prose_by_default() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.text(5, 5, "//in vitro//")
    assert not said(p.build(), "//in vitro//")


def test_a_log_axis_still_writes_its_powers() -> None:
    """The scale says its own labels are markup, so `10^{4}` still lifts."""
    p = panel(40, 30, x=log((1.0, 1e4)), y=(0, 10))
    p.axis("bottom")
    assert not said(p.build(), "10^{0}")
    assert Log.label_markup is True


# --- log powers --------------------------------------------------------------


def test_three_decades_stay_as_numbers() -> None:
    scale = log((1.0, 1e3))
    assert scale.tick_labels(scale.ticks(5)) == ("1", "10", "100", "1000")


def test_four_decades_become_powers() -> None:
    scale = log((1.0, 1e4))
    assert scale.tick_labels(scale.ticks(5))[0] == "10^{0}"


# --- the year on a date axis -------------------------------------------------


def test_a_single_year_is_written_once_at_the_end() -> None:
    p = panel(60, 30, x=dates((DAYS[0], DAYS[-1])), y=(0, 10))
    p.axis("bottom")
    written = words(p.build())
    assert written.count("2024") == 1
    assert written[-1] == "2024"


def test_an_axis_that_crosses_new_year_writes_years_on_the_ticks() -> None:
    p = panel(60, 30, x=dates((YEARS[0], YEARS[-1])), y=(0, 10))
    p.axis("bottom")
    written = words(p.build())
    assert written.count("2024") <= 1
    assert "2020" in written and "2022" in written


def test_the_offset_can_be_turned_off() -> None:
    p = panel(60, 30, x=dates((DAYS[0], DAYS[-1])), y=(0, 10))
    p.axis("bottom", offset=False)
    assert "2024" not in words(p.build())


def test_the_offset_can_be_dictated() -> None:
    p = panel(60, 30, x=dates((DAYS[0], DAYS[-1])), y=(0, 10))
    p.axis("bottom", offset="all of 2024")
    assert said(p.build(), "all of 2024")


# --- what the key rules read -------------------------------------------------


def test_a_raster_matrix_notes_its_ramp_and_domain() -> None:
    from inklet.plot.ramp import ramp

    heat = ramp("tol-sunset")
    p = panel(30, 20, x=(0, 3), y=(0, 3))
    p.matrix([[i + j for i in range(60)] for j in range(60)],
             ramp=heat, scale=linear((0.0, 118.0)))
    node = p.build()
    found = [n for n in _walk(as_drawn(node))
             if getattr(n, "notes", {}).get("ramp") is not None]
    assert len(found) == 1
    assert found[0].notes["scale_domain"] == (0.0, 118.0)
    assert found[0].notes["ramp_colours"][0] == heat(0.0)


def test_the_notes_survive_the_theme_being_applied() -> None:
    """`apply_theme` clones every node; a note the rules need must come along."""
    import inklet

    use_theme("nature")
    p = panel(30, 20, x=(0, 3), y=(0, 3))
    p.matrix([[i + j for i in range(60)] for j in range(60)],
             ramp=inklet.ramp("tol-sunset"), scale=linear((0.0, 118.0)))
    fig = inklet.figure(width=50)
    fig.add(p.build())
    built, _ = fig.build()
    assert any(getattr(n, "notes", {}).get("ramp_colours") for n in _walk(built))


def test_a_ramped_scatter_declares_the_domain_it_used() -> None:
    import inklet

    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.scatter([(x, x) for x in range(11)], color=list(range(11)),
              ramp=inklet.ramp("tol-sunset"))
    assert any(getattr(n, "notes", {}).get("scale_domain") == (0.0, 10.0)
               for n in _walk(as_drawn(p.build())))


def _walk(node):
    yield node
    for child in getattr(node, "children", ()) or ():
        yield from _walk(child)


# --- tabular figures ---------------------------------------------------------


def _features(node, text: str):
    for placed in resolve(as_drawn(node)).values():
        if getattr(placed.diagram.prim, "text", None) == text:
            return getattr(placed.diagram.prim, "features", ())
    raise AssertionError(f"no label said {text!r}")


def test_tick_labels_ask_for_tabular_figures() -> None:
    """A column of numbers is a table, and a table wants fixed-width digits."""
    p = panel(40, 30, x=(0, 1000), y=(0, 10))
    p.axis("bottom")
    assert ("tnum", 1) in _features(p.build(), "600")


def test_tabular_figures_can_be_turned_off() -> None:
    p = panel(40, 30, x=(0, 1000), y=(0, 10))
    p.axis("bottom", tnum=False)
    assert _features(p.build(), "600") == ()
