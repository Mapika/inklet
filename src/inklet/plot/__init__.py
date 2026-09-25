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
from .statistics import BoxStats, box_stats, histogram, kde, quantile
from .cumulative import ecdf
from .volcano import volcano_points
from .dendrogram import DendrogramLayout, DendrogramLink, dendrogram_layout
from .upset import Intersection, UpSetLayout, upset, upset_layout
from .hierarchy import (
    Hierarchy, HierarchyNode, PartitionCell, hierarchy, partition_layout, squarify,
    treemap_layout,
)
from .network import WidthScale, width_scale
from .chord import ChordGroup, ChordLayout, ChordRibbon, chord_layout
from .cluster import correlation, cut, distance_matrix, linkage
from .clustermap import clustermap
from .genomics import ManhattanLayout, chromosome_key, manhattan, manhattan_layout
from .ternary import TernaryFrame, ternary_frame
from .dotplot import AreaScale, area_scale, size_key
from .survival import SurvivalEstimate, kaplan_meier
from .forest import ForestLayout, ForestRow, forest, forest_layout
from .embedding import cluster_centers, cluster_centres
from .significance import format_p
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
from .kernel_density import BANDWIDTH_RULES, Density2D, kde2d, kde_curve, mass_levels
from .kernel_density import bandwidth as kde_bandwidth
from .density import histogram2d, point_density
from .regression import LinearFit, linear_fit, lowess, t_cdf, t_quantile
from .probability import plotting_positions, pp_points, qq_line, qq_points
from .agreement import Agreement, bland_altman
from .letter_values import LetterValues, letter_values
from .histograms import HISTTYPES, cumulate
from .percent import percent_of_totals
from .pairs import MARGINAL_KINDS, PAIR_KINDS, jointplot, pairplot

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
    "histogram", "box_stats", "BoxStats", "kde", "quantile", "ecdf",
    "volcano_points", "dendrogram_layout", "DendrogramLayout", "DendrogramLink",
    "upset", "upset_layout", "UpSetLayout", "Intersection",
    "hierarchy", "Hierarchy", "HierarchyNode", "squarify", "treemap_layout",
    "partition_layout", "PartitionCell", "width_scale", "WidthScale",
    "chord_layout", "ChordLayout", "ChordGroup", "ChordRibbon",
    "linkage", "cut", "correlation", "distance_matrix", "clustermap",
    "manhattan", "manhattan_layout", "ManhattanLayout", "chromosome_key",
    "ternary_frame", "TernaryFrame",
    "area_scale", "AreaScale", "size_key", "kaplan_meier", "SurvivalEstimate",
    "forest", "forest_layout", "ForestLayout", "ForestRow",
    "cluster_centers", "cluster_centres", "format_p",
    # statistical plots
    "kde_curve", "kde_bandwidth", "BANDWIDTH_RULES", "kde2d", "Density2D",
    "mass_levels", "histogram2d", "point_density", "linear_fit", "LinearFit",
    "lowess", "t_cdf", "t_quantile", "qq_points", "qq_line", "pp_points",
    "plotting_positions", "bland_altman", "Agreement", "letter_values",
    "LetterValues", "HISTTYPES", "cumulate", "percent_of_totals",
    "pairplot", "jointplot", "PAIR_KINDS", "MARGINAL_KINDS",
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

# categorical, composition, comparison and time plots
from .waterfall import WaterfallStep, waterfall_steps
from .slope import ranks
from .diverging import likert_colors, likert_spans, unsigned
from .waffle import waffle_cells
from .mosaic import MosaicColumn, mosaic_layout
from .stream import STREAM_OFFSETS, STREAM_ORDERS, stream_layers
from .parallel import parallel_ranges
from .bullet import bullet_shades
from .calendar import WEEKDAYS, calendar_weeks
from .barplot import summary_stats

__all__ += [
    "WaterfallStep", "waterfall_steps", "ranks", "likert_colors", "likert_spans",
    "unsigned", "waffle_cells", "MosaicColumn", "mosaic_layout", "STREAM_OFFSETS",
    "STREAM_ORDERS", "stream_layers", "parallel_ranges", "bullet_shades",
    "WEEKDAYS", "calendar_weeks", "summary_stats",
]
