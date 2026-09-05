"""inklet.plot: colour ramps, colorbars and legends."""

from __future__ import annotations

import math

import pytest

from inklet.core import resolve
from inklet.draw import marker
from inklet.draw.coords import as_drawn
from inklet.plot import colorbar, legend, log, ramp
from inklet.plot.axis import TICK_LABEL_KIND
from inklet.plot.key import BAND_KIND, LEGEND_LABEL_KIND
from inklet.plot.ramp import Ramp
from inklet.themes import ColorError, interpolate, interpolate_lab, mix_lab
from inklet.themes.color import parse_color, to_lab


def lightness(color: str) -> float:
    return to_lab(parse_color(color))[0]


def chroma(color: str) -> float:
    _, a, b = to_lab(parse_color(color))
    return math.hypot(a, b)


def placed(node, kind: str):
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


# --- interpolation -----------------------------------------------------------


def test_a_ramp_returns_its_ends_exactly() -> None:
    bar = ramp(("#000000", "#ff8800", "#ffffff"))
    assert bar(0.0) == "#000000"
    assert bar(1.0) == "#ffffff"


def test_lab_interpolation_is_monotone_in_lightness() -> None:
    """A sequential ramp exists to encode magnitude as lightness. A dip in L
    anywhere along it reads as a feature of the data."""
    bar = ramp("tol-ylorbr")
    levels = [lightness(bar(i / 64)) for i in range(65)]
    for before, after in zip(levels, levels[1:]):
        assert after <= before + 1e-9


def test_lab_steps_are_more_even_than_srgb_steps() -> None:
    """The point of interpolating in CIELAB: equal steps in t look like equal
    steps to a reader."""
    def steps(space):
        bar = ramp(("#000000", "#ffffff"), space=space)
        levels = [lightness(bar(i / 8)) for i in range(9)]
        return [b - a for a, b in zip(levels, levels[1:])]

    lab, srgb = steps("lab"), steps("srgb")
    assert max(lab) - min(lab) < max(srgb) - min(srgb)


def test_lab_keeps_the_chroma_srgb_throws_away() -> None:
    """Blue to red through the middle of the sRGB cube passes through a muddy
    grey-purple; the same blend in CIELAB stays a colour."""
    ends = ("#0000ff", "#ff0000")
    assert chroma(interpolate_lab(ends, 0.5)) > chroma(interpolate(ends, 0.5)) + 5
    assert lightness(interpolate_lab(ends, 0.5)) > lightness(interpolate(ends, 0.5))


def test_a_lab_midpoint_is_the_midpoint_of_the_lightnesses() -> None:
    grey = mix_lab("#222222", "#dddddd", 0.5)
    assert lightness(grey) == pytest.approx(
        (lightness("#222222") + lightness("#dddddd")) / 2, abs=0.5)


def test_a_ramp_samples_end_to_end() -> None:
    stops = ramp("tol-sunset").sample(5)
    assert len(stops) == 5
    assert stops[0] == ramp("tol-sunset")(0.0)
    assert stops[-1] == ramp("tol-sunset")(1.0)


def test_a_ramp_reverses() -> None:
    bar = ramp("tol-ylorbr")
    assert bar.reversed()(0.0) == bar(1.0)


def test_a_ramp_takes_a_palette_a_name_or_a_list() -> None:
    assert isinstance(ramp("tol-sunset"), Ramp)
    assert ramp(("#000000", "#ffffff")).stops == ("#000000", "#ffffff")
    assert ramp(ramp("tol-sunset")).stops == ramp("tol-sunset").stops


def test_an_unknown_colour_space_is_refused() -> None:
    with pytest.raises(ColorError, match="unknown colour space"):
        ramp(("#000000", "#ffffff"), space="hsv")


def test_a_ramp_needs_a_stop() -> None:
    with pytest.raises(ColorError, match="at least one stop"):
        Ramp(())


# --- colorbars ---------------------------------------------------------------


def test_a_colorbar_paints_one_band_per_step() -> None:
    bar = colorbar("tol-sunset", steps=24, length=40.0)
    assert len(placed(bar, BAND_KIND)) == 24


def test_the_bands_run_low_value_to_high_up_the_page() -> None:
    source = ramp("tol-ylorbr")
    bands = placed(colorbar(source, steps=16, length=40.0), BAND_KIND)
    assert bands[0].bbox.y0 > bands[-1].bbox.y0     # first band is at the bottom
    assert bands[0].style.fill == source(0.5 / 16)
    assert bands[-1].style.fill == source(15.5 / 16)


def test_bands_overlap_so_no_seam_shows() -> None:
    """Two rectangles that merely abut are antialiased independently and leave
    a pale rule between them, once per band, all the way up the bar."""
    bands = [p.bbox for p in placed(colorbar("tol-sunset", steps=16, length=40.0),
                                    BAND_KIND)]
    for lower, upper in zip(bands, bands[1:]):
        assert upper.y1 > lower.y0      # the upper band reaches past the join


def test_a_colorbar_covers_exactly_its_own_length() -> None:
    bands = [p.bbox for p in placed(colorbar("tol-sunset", steps=32, length=40.0),
                                    BAND_KIND)]
    top = min(box.y0 for box in bands)
    bottom = max(box.y1 for box in bands)
    assert bottom - top == pytest.approx(40.0, abs=1e-9)


def test_a_colorbar_carries_an_axis() -> None:
    bar = colorbar("tol-sunset", domain=(0.0, 100.0), length=40.0, count=5)
    labels = [p.diagram for p in placed(bar, TICK_LABEL_KIND)]
    assert len(labels) >= 3


def test_a_colorbar_takes_any_scale() -> None:
    """A log colorbar is a log scale, not a special case."""
    bar = colorbar("tol-sunset", scale=log((1.0, 1000.0)), length=40.0)
    assert len(placed(bar, TICK_LABEL_KIND)) >= 3


def test_a_horizontal_colorbar_lies_down() -> None:
    bar = colorbar("tol-sunset", side="bottom", length=40.0, steps=16)
    box = bar.bbox
    assert box.width > box.height
    bands = [p.bbox for p in placed(bar, BAND_KIND)]
    assert bands[0].x0 < bands[-1].x0     # low value at the left


def labels_of(bar) -> list[str]:
    return [" ".join(line.text for line in p.diagram.prim.lines)
            for p in placed(bar, TICK_LABEL_KIND)]


def test_a_colorbar_labels_the_values_it_is_given() -> None:
    """Without this a nonlinear key cannot say where its numbers go.

    blind-02 needed the baseline, the linthresh and the maximum on a symlog
    key and had to subclass the scale to get them; the automatic choice gave
    it two labels, neither of which was 0 or the top of the bar.
    """
    named = [-0.4, 0.0, 0.5, 1.0, 2.8]
    bar = colorbar("tol-ylorbr", domain=(-0.4, 2.8), length=32.0,
                   ticks=named, thin=False, format=lambda v: f"{v:g}")

    assert labels_of(bar) == ["-0.4", "0", "0.5", "1", "2.8"]


def test_named_ticks_are_still_thinned_by_default() -> None:
    """Documented, and the reason `thin=False` is worth naming in the docstring:
    asking for a label is not the same as keeping it."""
    named = [-0.4, 0.0, 0.5, 1.0, 2.8]
    bar = colorbar("tol-ylorbr", domain=(-0.4, 2.8), length=32.0,
                   ticks=named, format=lambda v: f"{v:g}")

    assert 0 < len(labels_of(bar)) < len(named)


def test_a_colorbar_needs_a_band() -> None:
    with pytest.raises(ValueError, match="at least one band"):
        colorbar("tol-sunset", steps=0)


# --- legends -----------------------------------------------------------------


ENTRIES = (("wild type", "#e69f00"), ("knockout", "#0072b2"))


def test_a_legend_has_a_row_per_entry() -> None:
    node = legend(ENTRIES)
    assert len(placed(node, LEGEND_LABEL_KIND)) == len(ENTRIES)
    swatches = placed(node, "mark")
    assert [s.style.fill for s in swatches] == [c for _, c in ENTRIES]


def test_a_swatch_may_be_the_very_mark_the_plot_used() -> None:
    node = legend((("measured", marker("triangle", fill="#009e73")),))
    assert len(placed(node, "mark")) == 1


def test_a_legend_row_reads_left_to_right() -> None:
    node = legend(ENTRIES)
    swatch = placed(node, "mark")[0].bbox
    label = placed(node, LEGEND_LABEL_KIND)[0].bbox
    assert swatch.x1 <= label.x0
    assert abs(swatch.center.y - label.center.y) < 1.0


def test_legend_entries_stack_downward() -> None:
    labels = [p.bbox for p in placed(legend(ENTRIES), LEGEND_LABEL_KIND)]
    assert labels[0].y1 <= labels[1].y0


def test_a_legend_can_run_in_columns() -> None:
    entries = tuple((f"series {i}", "#333333") for i in range(6))
    wide = legend(entries, columns=3)
    tall = legend(entries, columns=1)
    assert wide.bbox.width > tall.bbox.width
    assert wide.bbox.height < tall.bbox.height


def test_a_legend_needs_an_entry() -> None:
    with pytest.raises(ValueError, match="at least one entry"):
        legend(())
