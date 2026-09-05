"""Data to geometry: scales, axes, plot areas, and the two colour keys.

This layer knows nothing about scatters or violins. It knows how to turn a
number into a millimetre and back, how to choose tick values a reader can
divide in their head, and how to hang the furniture off a drawing region of a
fixed size. Modalities are built on top of it, in their own modules.

    import inklet

    points = [(t / 2.0, (t % 7) / 7.0 - 0.5) for t in range(21)]
    p = inklet.panel(60, 40, x=(0, 10), y=(-1, 1))
    p.grid().marks(inklet.marker("circle"), points).axes(x="time / s", y="signal")

    fig = inklet.figure(width=80)
    fig.add(p.build())
    fig.save("plot.svg")

`panel` sizes the drawing *region*; the ticks, the axis names and any colorbar
hang outside it, so the finished node is always wider than the numbers you
passed. `inklet.fit` is how you go the other way and hit a column width exactly.
"""

from .axis import AXIS_KIND, SIDES, axis, text_node, tick_texts, tick_values
from .facets import facets
from .key import BANDS, SWATCH_OF_TYPE, colorbar, legend
from .marks import BoxStats, box_stats, histogram, kde, quantile
from .inset import INDICATOR_KIND, INSET_KIND, inset, panel_bracket
from .panel import Panel, column, panel, row
from .polar import (
    PolarPanel, THETA_UNITS, Theta, WINDINGS, ZERO_DIRECTIONS,
    circular_histogram, circular_mean, polar, theta_ticks,
)
from .ribbon import (
    RIBBON_EASE, eased_cubic, panel_ribbon, ribbon, ribbon_between,
    ribbon_cubics,
)
from .ramp import Ramp, ramp
from .raster import LEVELS, MATRIX_KIND, raster_matrix
from .breaks import AxisBreaks, BREAK_KIND, BREAK_NOTE
from .scale import (
    Band, GroupedBand, Broken, Linear, Log, Scale, ScaleError, SymLog, band, grouped_band, broken,
    format_number, linear,
    log, log_ticks, nice_bounds, nice_ticks, power_label, si_labels, symlog,
)
from .series import SeriesKey, swatch_for
from .timescale import Time, TimeStep, dates, time_ticks, to_time

__all__ = [
    # scales
    "Scale", "ScaleError", "Linear", "Log", "SymLog", "Band", "GroupedBand", "Broken",
    "linear", "log", "symlog", "band", "grouped_band", "broken",
    "AxisBreaks", "BREAK_KIND", "BREAK_NOTE",
    "nice_ticks", "nice_bounds", "log_ticks", "format_number",
    "si_labels", "power_label",
    # furniture
    "axis", "tick_values", "tick_texts", "text_node", "SIDES", "AXIS_KIND",
    "Panel", "panel", "row", "column", "facets",
    "PolarPanel", "polar", "Theta", "theta_ticks",
    "circular_mean", "circular_histogram",
    "ZERO_DIRECTIONS", "WINDINGS", "THETA_UNITS",
    # what a dataset is before it is a shape
    "histogram", "box_stats", "BoxStats", "kde", "quantile",
    "inset", "panel_bracket", "INSET_KIND", "INDICATOR_KIND",
    "ribbon", "ribbon_between", "ribbon_cubics", "eased_cubic",
    "panel_ribbon", "RIBBON_EASE",
    # time
    "Time", "TimeStep", "dates", "to_time", "time_ticks",
    # keys, built from what was drawn
    "SeriesKey", "swatch_for",
    # colour
    "Ramp", "ramp", "colorbar", "legend", "BANDS", "SWATCH_OF_TYPE",
    "raster_matrix", "MATRIX_KIND", "LEVELS",
]
