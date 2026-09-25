"""The plot area: a fixed-size region that data maps into.

A panel is a rectangle of a size you choose, two scales that map data onto it,
and the furniture that hangs off its edges. Everything drawn into it is
positioned by those scales and nothing else, which is what makes a scatter and
a violin and a heatmap of the same data line up exactly.

The area is centred on the panel's origin: x runs from -width/2 to +width/2 and
y from +height/2 *up* to -height/2, so data increases upward the way a reader
expects while the rest of the library keeps y growing downward. The two facts
meet in one place -- the y scale's range is simply given back to front -- and
nowhere else does anything need to know.

Axes are built in the same coordinates and moved onto the edge they belong to,
so a tick is over its data by construction rather than by an offset someone
tuned. The panel's `origin` anchor stays on the centre of the *area*, never on
the centre of the assembled furniture: that is what lets `row()` line up
panels whose y labels are different widths.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, RectPrim, Vec2, mm
from ..core.diagram import union_bounds as _union_box
from ..draw.clip import clip as draw_clip
from ..draw.coords import (active_theme, as_drawn, declare_area,
                           drawn_group, plot_area)
from ..draw.path import curve as draw_curve, polyline
from ..draw.place import place as draw_place
from ..themes.color import mix
from . import marks as _marks
from . import notes as _notes
from .axis import SIDES, SPINE_KIND, axis, text_node, tick_values
from .furniture import (AREA_KIND, GRID_KIND, PANEL_KIND, TITLE_KIND, beside,
                        into_corner as _into_corner, origin_of as _origin_of,
                        plated as _plated)
from .key import (SWATCH_OF_TYPE, colorbar as make_colorbar,
                  legend as make_legend)
from .line_labels import tag_series
from .matrix import (_RASTER_ABOVE_CELLS, matrix_centers, matrix_layer,
                     prepare_matrix, default_coloring)
from .scale import Band, Linear, Log, Scale, linear
from .metadata import declare_domain as _declare_domain
from .series import SeriesKey, merge_keys, series_color, series_names, swatch_for
from .._compat import renamed_keywords, resolve_renamed
from .timescale import dates, is_time_like

__all__ = ["Panel", "column", "panel", "row"]

_AXIS_SCALE = {"bottom": "x", "top": "x", "left": "y", "right": "y"}

#: A confidence band, as a blend towards paper. Pale enough to read the line
#: and the gridlines through, dark enough to have an edge on a 1x screen.
_BAND_TINT = 0.78

_ERROR_STYLES = ("band", "bars")

#: A censor tick on a survival curve, as a fraction of the type size.
_CENSOR_TICK_OF_TYPE = 0.4

#: How far past the plot area a node may reach and still count as inside it.
#: A micrometre: smaller than any printer, larger than the float error in
#: mapping a datum that sits exactly on the end of the domain.
_CLIP_SLACK = 1e-3


def _clip_flag(style: dict) -> bool | None:
    """`clip=` lifted out of a drawing call's style keywords.

    Every data method takes `**style` and hands it to something in `inklet.draw`,
    which would refuse `clip` as a paint property. Lifting it here rather than
    spelling it into fourteen signatures keeps `clip=` one word wherever it is
    written, and leaves the style keyword lists in `api.md` describing paint
    and nothing else.
    """
    return style.pop("clip", None)


@dataclass
class Panel:
    """A drawing region plus the scales that map data into it.

    Build it with `panel()`. Every method that adds something returns the panel
    itself, so a plot reads as a sentence; `build()` turns it into a `Diagram`.

    `clip` says whether data is cut to the plot area; see `panel()` for why it
    is off by default, and pass `clip=` to any single call to override it.
    """

    width: float
    height: float
    x: Scale
    y: Scale
    #: Whether data is cut to the plot area. Off by default -- see `panel()`.
    clip: bool = False
    _under: list[Diagram] = field(default_factory=list, repr=False)
    _content: list[Diagram] = field(default_factory=list, repr=False)
    _over: list[Diagram] = field(default_factory=list, repr=False)
    _title: tuple[Diagram, str, float] | None = field(default=None, repr=False)
    _built: Diagram | None = field(default=None, repr=False, compare=False)
    #: Set on the handle `twin_y`/`twin_x` return, so that drawing through the
    #: second scale invalidates the panel that will actually be built.
    _parent: "Panel | None" = field(default=None, repr=False, compare=False)
    #: The scale the last `matrix` mapped its colours through, so `build` can
    #: declare it on the panel node for `inklet.diagnostics`.
    _scale_domain: Scale | None = field(default=None, repr=False, compare=False)
    #: The ramp the last `matrix` coloured through, so `colorbar()` can explain
    #: the picture rather than a second ramp that agrees with it today.
    _ramp: object | None = field(default=None, repr=False, compare=False)
    #: Whether `matrix` has drawn here, so an axis with no ticks on a heatmap
    #: draws no spine along the cells' edge.
    _matrix: bool = field(default=False, repr=False, compare=False)
    #: Brackets already drawn, so the next one asked to place itself clears
    #: them as well as the data. Two significance bars over overlapping spans
    #: is the ordinary case, and they have to stack.
    _brackets: list[Diagram] = field(default_factory=list, repr=False,
                                     compare=False)
    #: How every named series was drawn, in the order the names first appeared.
    #: `legend()` is a rendering of this list; see `plot.series`.
    _keys: list[SeriesKey] = field(default_factory=list, repr=False,
                                   compare=False)

    _insets: list = field(default_factory=list, repr=False, compare=False)
    _inset_state: tuple = field(default=(), repr=False, compare=False)
    #: `label_points` calls waiting for `build`, by the id of the empty node
    #: that holds each call's place in `_over`. Placed at build time so the
    #: labels avoid marks drawn after the call too.
    _deferred: dict = field(default_factory=dict, repr=False, compare=False)
    #: The area scale the last `dotplot` sized its circles with, for
    #: `size_key()`.
    _sizes: object | None = field(default=None, repr=False, compare=False)
    #: The width scale the last `network` drew its edges with, for
    #: `width_key()`.
    _widths: object | None = field(default=None, repr=False, compare=False)
    _ternary: object | None = field(default=None, repr=False, compare=False)
    #: `(name, estimate, colour)` per curve `kaplan_meier` drew, for
    #: `at_risk()`.
    _survival: list = field(default_factory=list, repr=False, compare=False)

    # -- coordinates ------------------------------------------------------

    @property
    def area(self) -> Rect:
        """The plot area in panel coordinates."""
        return Rect.from_size(self.width, self.height)

    def point(self, x, y) -> Vec2:
        """One data point in panel coordinates, in millimetres."""
        return Vec2(self.x.map(x), self.y.map(y))

    def map(self, points: Iterable[Sequence]) -> tuple[Vec2, ...]:
        """`point()` over a sequence: data pairs in, millimetres out.

        The usual way to hand data to something in `inklet.draw`, which knows
        nothing about scales -- `inklet.polygon(p.map(corners))`.
        """
        return tuple(self.point(*p) for p in points)

    def region(self, x0, y0, x1, y1) -> Rect:
        """Map two data corners to a normalized rectangle in panel coordinates.

        Use the same transform for marks, selection outlines, and zoom source
        boxes. Reversed/log scales work without manual pixel arithmetic.
        Bounds are not clipped to the plot area. Matrix slices use their cell
        *edges* (e.g. 70 and 120), not the centers of the first/last cells.
        """
        import math
        a, b = self.point(x0, y0), self.point(x1, y1)
        if not all(math.isfinite(v) for v in (a.x, a.y, b.x, b.y)):
            raise ValueError('region corners must map to finite coordinates')
        return Rect(min(a.x,b.x), min(a.y,b.y), max(a.x,b.x), max(a.y,b.y))

    # -- content ----------------------------------------------------------

    def draw(self, *items: Diagram, clip: bool | None = None) -> "Panel":
        """Add content already expressed in panel coordinates.

        Anything from `inklet.draw` remembers the frame it was drawn in, so a path
        built from `panel.map(...)` lands where its data is.

        `clip=True` cuts it to the plot area, `clip=False` leaves it whole, and
        the default asks the panel. Every drawing method takes the same word.
        """
        return self._add(self._content,
                         [as_drawn(item) for item in items], clip)

    def _add(self, into: list[Diagram], nodes: Sequence[Diagram],
             clip: bool | None) -> "Panel":
        """Put drawn nodes into one of the three layers, clipped or not."""
        into.extend(self._to_area(nodes, clip))
        return self._touched()

    def _to_area(self, nodes: Sequence[Diagram],
                 clip: bool | None) -> list[Diagram]:
        """`nodes`, cut to the plot area when this panel clips.

        Anything already inside is passed through untouched rather than wrapped
        in a clip group that would cut nothing: a panel whose data stays in its
        domain then renders byte-identically whether or not it was asked to
        clip, and turning clipping on costs nodes only where it does something.

        `inklet.clip` cuts the geometry rather than emitting a `clipPath`, so what
        comes back measures as the *clipped* extent -- which is what makes the
        linter report the picture instead of the data behind it.
        """
        if not (self.clip if clip is None else clip):
            return list(nodes)
        area = self.area
        out = []
        for node in nodes:
            box = node.envelope.bbox()
            out.append(node if box is None or _inside(box, area)
                       else draw_clip(node, area))
        return out

    def place(self, items, *, clip: bool | None = None) -> "Panel":
        """`draw.place()` in data coordinates: `((x, y), diagram)` pairs, or
        bare diagrams that already know where they go."""
        mapped = [item if isinstance(item, Diagram) else (self.point(*item[0]), item[1])
                  for item in items]
        return self.draw(draw_place(mapped), clip=clip)

    def marks(self, item: Diagram, points: Iterable[Sequence], *,
              name: str | None = None, **style) -> "Panel":
        """A copy of `item` centred on every data point.

        Copies, not references: a `Diagram` may appear in a tree exactly once,
        and one marker per point is the shape of every scatter, swarm and
        rug plot there is.

        `name` remembers the series for `legend()`, and its swatch is another
        copy of this very shape -- the most honest swatch there is.
        """
        clip = _clip_flag(style)
        placed = [(self.point(*p), item.copy()) for p in points]
        self._note(name, "marker", node=item.copy())
        return self.draw(draw_place(placed, **style), clip=clip)

    def matrix(self, values: Sequence[Sequence[float]], *, ramp=None,
               scale: Scale | None = None, center: float | None = None,
               x: Sequence | None = None, y: Sequence | None = None,
               overlap: float | None = None, missing: str | None = None,
               vector: str = "cells",
               interpolation: str = "nearest", samples: int = 4,
               raster: bool | str = "auto", **style) -> "Panel":
        """A 2D array of values, one coloured cell each.

        `values` is row-major -- `values[r][c]` -- and by default row `r` spans
        the `r`th step of the y scale and column `c` the `c`th step of x, edge
        to edge across the whole area. Pass `x` and `y` to give the *centres*
        explicitly when the samples are not evenly spaced or the panel is wider
        than the data.

        **Unevenly spaced samples get unevenly sized cells.** Each cell runs to
        the midpoint of the gap on either side of its own sample, so a run of
        dense samples draws thin cells and a long gap draws one wide one, and
        the picture says what the sampling actually was. The alternative -- a
        band scale over the sample values -- puts them at equal pitch, which is
        a claim about the experiment that is not true.

        `ramp` turns a value into a colour and `scale` says how the value gets
        to the ramp. Give it the same scale object you gave the colorbar --
        passing two that merely agree today is how a key ends up describing a
        picture it no longer matches, and no rule can see it.

        **Leave `ramp` out for the defaults.** Data that stay on one side of
        zero get a sequential ramp (magma, pale yellow for low values to deep
        purple for high); data on both sides get a diverging blue-white-red
        ramp with white at zero. `center=` picks the diverging ramp and puts
        white at that value instead. Without `scale`, the colour scale spans
        the data, made symmetric about `center` when one is given; the
        colorbar reads the same scale. With an explicit `ramp` and no `scale`
        the values are fractions of the ramp, 0 to 1, as before.

        **A cell with no measurement is `None` or a NaN, and needs a colour of
        its own.** `missing="#dedede"` paints those cells a tone that is not on
        the ramp, which is what makes a hole read as an absence rather than as
        the low end of the scale -- or as a rendering failure, which is how a
        white cell in a coloured field reads. Left out, a missing value is an
        error rather than a guess.

        Cells are drawn a hair over their nominal size, for the reason
        `inklet.plot.key` overlaps a colorbar's bands: two rectangles that merely
        abut are antialiased independently, so a pixel on the join gets a
        fraction of each and a fraction of the background, and the result is a
        pale grid over the whole matrix. They also carry `kind="mark"`, because
        a cell's position is the data -- without it a heatmap is thousands of
        CROWDING findings about its own neighbours.

        **One node per cell, up to a point.** A 40 x 90 matrix is 3,600
        rectangles and roughly a megabyte of SVG; that is the honest cost of
        staying vector, and it is the right trade until the cells are too small
        to point at. Past `raster="auto"`'s threshold of about 2,000 cells the
        grid is encoded instead as a PNG one pixel per cell, sampled
        nearest-neighbour so the edges land exactly where the rectangles did --
        the same 60 x 60 matrix is then about a kilobyte rather than a
        megabyte. `raster=True` and `raster=False` force the choice.

        ``vector="batched"`` forces vector output and groups exact same-color
        cells into bounded compound paths, retaining uneven cell geometry and
        colorbar validation without per-cell nodes. It requires zero overlap;
        antialiased viewers can show joins. Colors are not quantized.

        ``vector="seamless"`` adds opaque underpaint behind the same exact
        foreground cells. This suppresses background-colored antialiasing joins
        without enlarging the data cells or quantizing colors. Both layers are
        editable compound paths (at most 512 cells per path). Opaque colors and
        zero overlap are required; the field remains piecewise constant, not
        interpolated. Apply whole-field transparency to a containing group.

        ``interpolation="linear", raster=True`` explicitly requests bilinear
        interpolation of scalar values before color mapping, at ``samples``
        pixels per input cell (2–16, default 4). Displayed sample spacing must
        be uniform. Missing values remain missing across the filter footprint.
        This smooth image gives up per-cell vector editing; source values are
        never altered. Nearest-cell rendering remains the default.

        The raster path needs evenly spaced samples, since a pixel cannot be
        wider than its neighbour, and it gives up two things: the cells stop
        being individually selectable in an editor, and `KEY_MISMATCH` can no
        longer compare their colours against a colorbar, because there are no
        mark fills left to sample. The declared domain still crosses over.
        """
        rows, raster, overlap, clip = prepare_matrix(
            values, vector=vector, interpolation=interpolation, raster=raster,
            overlap=overlap, style=style)
        ramp, scale = default_coloring(rows, ramp, scale, center)
        centres_x = self._centres(x, len(rows[0]), self.x, self.width)
        centres_y = self._centres(y, len(rows), self.y, self.height)
        unit = None if scale is None else scale.with_range(0.0, 1.0)
        self._ramp = ramp
        single_x = abs(self.x.map(x[1])-self.x.map(x[0])) if x is not None and len(x)==2 and len(centres_x)==1 else self.width
        single_y = abs(self.y.map(y[1])-self.y.map(y[0])) if y is not None and len(y)==2 and len(centres_y)==1 else self.height
        group = matrix_layer(
            rows, ramp, unit, centres_x, centres_y, single_x=single_x, single_y=single_y,
            scale=scale, interpolation=interpolation, samples=samples, raster=raster,
            vector=vector, overlap=overlap, missing=missing, style=style)
        # The group carries the domain for tree inspection; build() also records
        # it on the panel, where diagnostics pair the field with its colorbar.
        self._scale_domain = scale
        self._matrix = True
        return self.draw(group, clip=clip)

    def _centres(self, given: Sequence | None, count: int,
                 scale: Scale, extent: float) -> list[float]:
        return matrix_centers(given, count, scale, extent)

    def line(self, points: Iterable[Sequence], *, smooth: float = 0.0,
             closed: bool = False, name: str | None = None, err=None,
             err_style: str = "band", simplify: float | str | None = None,
             **style) -> "Panel":
        """A path through data points: straight by default, curved with
        `smooth`.

        `err=` draws the spread with it, in the data's own units, and takes the
        three spellings `errorbars` does -- one number, one per point, or
        `(down, up)` pairs. `err_style="band"` shades it as a continuous
        envelope, which is what a fitted curve or a mean over trials wants;
        `"bars"` puts a whisker on each point, which is what a handful of
        conditions wants. The band paints *before* the line, so the line stays
        on top of its own uncertainty.

        `name=` remembers the series for `legend()`, band included.

        `simplify=0.02` optionally reduces straight, open lines at a tolerance
        of 0.02 mm after scale mapping. Endpoints and global x/y extrema stay;
        raw data and uncertainty marks are unchanged. None or zero keeps every
        point. Reduction can change dash phase and sub-tolerance details.
        """
        from .simplify import simplify_points, tolerance_mm
        tolerance = tolerance_mm(simplify)
        if tolerance and (smooth != 0 or closed):
            raise ValueError('simplify supports straight, open lines only')
        clip = _clip_flag(style)
        data = [tuple(p) for p in points]
        stroke = self._series_color(name, style.get("stroke"))
        if stroke is not None:
            style["stroke"] = stroke
        if err is not None:
            self._spread_of(data, err, err_style, name, style, clip)
        self._note(name, "line", color=style.get("stroke"),
                   dash=style.get("stroke_dash"), width=style.get("stroke_width"))
        mapped = self.map(data)
        if smooth > 0:
            return self.draw(tag_series(draw_curve(
                mapped, smooth=smooth, closed=closed, **style), name), clip=clip)
        reduced = simplify_points(mapped,tolerance) if tolerance else mapped
        node = tag_series(polyline(reduced, closed=closed, **style), name)
        if tolerance:
            node.note('line_simplification',dict(tolerance_mm=tolerance,
                      input_points=len(mapped),output_points=len(reduced)))
        return self.draw(node, clip=clip)

    def band(self, x: Sequence, lo, hi, *, name: str | None = None,
             color: str | None = None, **style) -> "Panel":
        """The shaded envelope between two edges over shared x.

        The confidence interval that belongs under a line. `lo` and `hi` are
        each a sequence the length of `x` or a single number, exactly as
        `fill_between` takes them -- this is that call with the paint decided:
        a tint of `color` towards paper, pale enough that the line and the
        gridlines read through it.

            p.band(t, lower, upper, color=TH.color(0), name="wild type")
            p.line(mean, stroke=TH.color(0), name="wild type")

        Both calls under one name make one key entry, drawn as a band with the
        line across it.
        """
        clip = _clip_flag(style)
        theme = active_theme()
        color = self._series_color(name, color)
        style.setdefault("fill", mix(color if color is not None else theme.ink,
                                     theme.paper, _BAND_TINT))
        self._note(name, "area", fill=style["fill"], color=color)
        return self.draw(_marks.fill_between(self, x, lo, hi, **style),
                         clip=clip)

    def _spread_of(self, data: Sequence[Sequence], err, err_style: str,
                   name: str | None, style: dict,
                   clip: bool | None = None) -> None:
        """`line(err=)`, as either of the two things a spread can be."""
        if err_style not in _ERROR_STYLES:
            raise DiagramError(
                f'line(err_style=) is "band" or "bars", not {err_style!r}')
        if err_style == "bars":
            ink = style.get("stroke")
            self.errorbars(data, yerr=err, clip=clip,
                           **({} if ink is None else {"stroke": ink}))
            return
        pairs = _marks.error_pairs(err, len(data), "err")
        self.band([p[0] for p in data],
                  [p[1] - down for p, (down, _) in zip(data, pairs)],
                  [p[1] + up for p, (_, up) in zip(data, pairs)],
                  name=name, color=style.get("stroke"), clip=clip)

    # -- marks ------------------------------------------------------------
    #
    # Every method in this section takes DATA and maps it. The only two that
    # do not are `under` and `over`, immediately below, and they say so.

    def scatter(self, points: Iterable[Sequence], *, size=None, color=None,
                ramp=None, scale: Scale | None = None,
                marker: str = "circle", name: str | None = None,
                raster: bool = False, dpi: float = 300, **style) -> "Panel":
        """Markers at data points, with size and colour that may be data too.

        `marks()` places copies of one shape you built, which is right when
        every point is the same. `scatter` accepts per-point geometry, so
        `size=` and `color=` each take a value *or* a sequence and a bubble
        chart is one line:

            p.scatter(points, size=[0.5 + 2 * w for w in weight])

        `size` is a marker's diameter in millimetres. If the quantity should
        read as the *area* of the mark -- which is how a reader compares
        circles -- pass its square root.

        `ramp=` makes the colour a *third quantity*: `color=` is then a
        sequence of numbers, `scale=` says how they reach the ramp, and
        `p.colorbar()` afterwards explains the picture from the very ramp and
        scale used here -- the same contract `matrix` has with its key.

            p.scatter(points, color=depth, ramp=inklet.ramp("tol-sunset"),
                      scale=inklet.linear((0, 400)))
            p.colorbar(label="depth / um")

        Given no `scale`, the values' own range becomes one, so the bar reads
        over the data rather than over 0..1.

        Vector layers with at least 256 points use immutable packed marker
        records. All points and paint order are retained; axes with breaks and
        explicit placement anchors keep individually addressable nodes.

        `raster=True` embeds only this marker layer as an antialiased PNG
        at `dpi` (default 300). Axes and other layers remain vector. Requires
        the optional Pillow dependency (`inklet[images]`).

        `name=` remembers the series for `legend()`; the swatch is this marker
        in this colour, and a per-point `color=` sequence records nothing,
        since a legend row cannot stand for eighty colours.
        """
        clip = _clip_flag(style)
        if ramp is not None:
            color, scale = self._ramped(color, ramp, scale)
            # The pale end of a sequential ramp is paper: a point coloured
            # #ffffcc is a hole in the picture rather than a datum. An outline
            # costs nothing at the dark end and is the whole mark at the light
            # one, so a ramped scatter gets one unless the caller says not to.
            style.setdefault("stroke", active_theme().ink)
            style.setdefault("stroke_width", active_theme().hairline)
        elif color is None or isinstance(color, str):
            color = self._series_color(name, color)
        self._note(name, "marker", marker=marker,
                   color=color if isinstance(color, str) else None)
        if not isinstance(raster, bool):
            raise ValueError("scatter raster must be True or False")
        direct_raster = raster and not {'anchor', 'origin'}.intersection(style)
        if direct_raster:
            from .scatter_raster import raster_scatter_points
            node = raster_scatter_points(self, points, size=size, color=color,
                                         marker=marker, dpi=dpi,
                                         clip=self.area if (self.clip if clip is None else clip) else None,
                                         **style)
            clip = False
        else:
            node = _marks.scatter(self, points, size=size, color=color,
                                  marker=marker, **style)
        if raster and not direct_raster:
            from .scatter_raster import raster_scatter
            node = raster_scatter(node, dpi=dpi,
                                  clip=self.area if (self.clip if clip is None else clip) else None)
            clip = False  # Already clipped in pixels; preserve the image extent.
        _declare_domain(node, scale)
        return self.draw(node, clip=clip)

    def _ramped(self, values, ramp, scale: Scale | None) -> tuple[list, Scale]:
        """Per-point colours from per-point numbers, and the scale used.

        Remembered on the panel exactly as `matrix` remembers its own, so that
        `colorbar()` draws the ramp the points were actually coloured through
        instead of a second one that agrees with it today.
        """
        if values is None or isinstance(values, str):
            raise DiagramError(
                "scatter(ramp=) colours by a value per point: pass color= a "
                "sequence of numbers the length of the data"
            )
        from .ramp import as_ramp
        ramp = as_ramp(ramp)  # a palette name such as "viridis" works too
        numbers = [float(v) for v in values]
        if scale is None:
            low, high = min(numbers), max(numbers)
            scale = linear((low, high if high > low else low + 1.0))
        unit = scale.with_range(0.0, 1.0)
        self._ramp = ramp
        self._scale_domain = scale
        return [ramp(unit.map(v)) for v in numbers], scale

    @renamed_keywords(colors="color", names="name")
    def bars(self, at: Sequence, heights, *, width: float = 0.8,
             baseline: float = 0.0, orient: str = "v",
             stacked: bool | None = None, grouped: bool | None = None,
             gap: float = 0.12, color=None, bar_colors=None, name: str | Sequence[str] | None = None,
             labels=None, label_position: str = "auto",
             label_options: dict | None = None, normalize: bool = False,
             **style) -> "Panel":
        """A rectangle per value, standing on a baseline.

        `at` is one position per bar -- categories on a band scale, numbers on
        a continuous one -- and `heights` is either one value each or several
        series of them. Two or more series are drawn side by side; pass
        `stacked=True` to pile them instead, which is a claim that they sum to
        something worth reading and so is never the default.

            p.bars(["ctrl", "drug"], [12, 31])
            p.bars(days, [morning, evening], color=["#888", TH.accent])

        `orient="h"` lays the bars down: `at` is then a position on y and the
        heights run along x, which is the layout to use the moment the category
        names are longer than about six characters.

        `width` is a fraction of the slot on a band scale and a width in data
        units on a continuous one, and `gap` is the air between grouped bars as
        a fraction of their sub-slot. One series is drawn as a tint of the ink
        with a hairline edge; several take the theme's palette in order.

        `color=` is one colour for every series or a sequence of one colour per
        *series*. `bar_colors=` assigns one colour per *category* instead, as a
        sequence or a mapping keyed by the values in `at`; it requires one
        series. A mapping from `inklet.categories()` also supplies category
        legend entries.

        `name=` is one name per *series* (a string for a single series), not
        per bar -- the bars are named by the axis -- and gives `legend()` a
        swatch in each series' own colour.
        Unstacked values equal to the baseline draw no rectangle; stacked
        contributions of zero also draw nothing. If every bar has zero length,
        the series remains valid and retains axes and requested legend entries.

        `labels=` writes each value on its bar or segment: `True` for the
        number, a format such as `"{:.1f}%"`, a callable, or explicit strings
        in the shape of `heights`. `label_position` is `"auto"` (inside when
        the label fits with a margin, otherwise past the bar end; for stacked
        bars a segment label that does not fit is omitted), `"inside"` or
        `"end"`. Inside labels use the theme ink or paper, whichever contrasts
        more with the fill. `label_options` takes `size`, `fill`, `markup` and
        `font_weight`. Labels are never shrunk; omitted labels are listed in
        the label node's `bar_labels` note.

            p.bars(ids, [specific, dimorphic, isomorphic], stacked=True,
                   orient="h", labels=True)

        `normalize=True` draws 100% bars: each position's series become
        percentages of its total and are stacked, so the value axis runs 0
        to 100, and `labels=True` writes each share as `"{:.0f}%"`.
        """
        clip = _clip_flag(style)
        names = series_names(name)
        if normalize:
            from .percent import PERCENT_LABEL, percent_of_totals
            heights = percent_of_totals(heights)
            stacked = True if stacked is None else stacked
            if labels is True:
                labels = PERCENT_LABEL
        if names is not None and bar_colors is not None:
            raise DiagramError("a per-category colour set cannot have one series legend; omit name")
        if names is not None:
            self._note_series(
                names, _marks.series_colors(
                    style.get("fill") if color is None else color,
                    _marks.series_count(heights)))
        from .categories import CategorySet
        at = tuple(at)
        node = _marks.bars(
            self, at, heights, width=width, baseline=baseline, orient=orient,
            stacked=stacked, grouped=grouped, gap=gap, colors=color, bar_colors=bar_colors,
            **style)
        if isinstance(bar_colors, CategorySet):
            for label, entry in bar_colors.subset(at).legend_entries:
                self._note(label, "area", fill=entry, color=entry)
        self.draw(*(() if node is None else (node,)), clip=clip)
        if labels is not None and labels is not False:
            from .bar_labels import bar_labels
            count = _marks.series_count(heights)
            fills = _marks.series_colors(
                style.get("fill") if color is None else color, count)
            per_bar = None
            if bar_colors is not None:
                per_bar = ([bar_colors[a] for a in at]
                           if isinstance(bar_colors, Mapping)
                           else _marks._per_point(bar_colors, len(at),
                                                  "bar_colors"))
            written = bar_labels(
                self, at, heights, labels=labels, position=label_position,
                width=width, baseline=baseline, orient=orient, stacked=stacked,
                grouped=grouped, gap=gap, fills=fills, bar_fills=per_bar,
                options=label_options)
            if written is not None:
                self.over(written, clip=False)
        return self

    @renamed_keywords(colors="color")
    def hist(self, values: Sequence[float], bins: int | Sequence[float] = 10, *,
             range: tuple[float, float] | None = None, density: bool = False,
             baseline: float = 0.0, orient: str = "v", color=None,
             name: str | None = None, histtype: str | None = None,
             cumulative: bool = False, **style) -> "Panel":
        """Binned counts as touching rectangles.

        `bins` is a count -- the edges then land on round numbers and you get
        about that many -- or the edges themselves. `density=True` divides by
        the sample size and the bin width so the bars integrate to one.

        The panel's y domain has to exist before this is called, and only the
        counts can tell you what it should be. `inklet.plot.histogram(values,
        bins)` returns `(edges, heights)` without drawing anything, which is
        the call to make first:

            edges, counts = inklet.plot.histogram(latencies, 12)
            p = inklet.panel(60, 34, x=(edges[0], edges[-1]), y=(0, max(counts)))
            p.hist(latencies, 12)

        `color=` is the bar colour and `name=` the legend entry.

        `histtype="step"` draws the outline alone, `"stepfilled"` a filled
        outline with no edges between bins. `cumulative=True` draws running
        totals (with `density=True`, the fraction of observations up to
        each bin's upper edge). `values` may be a mapping of group name to
        values: every group is binned on the same edges, drawn as a
        translucent filled outline in its own colour (`color=` one per
        group) and named for `legend()`. `inklet.plot.cumulate` gives the
        running totals of `histogram`'s heights.
        """
        clip = _clip_flag(style)
        if (isinstance(values, Mapping) or cumulative
                or histtype not in (None, "bar")):
            from .histograms import hist_layer
            node, keys = hist_layer(self, values, bins, range=range,
                                    density=density, cumulative=cumulative,
                                    histtype=histtype, baseline=baseline,
                                    orient=orient, colors=color, **style)
            for group, (form, ink, fill) in keys:
                self._note(group if group is not None else name, form,
                           color=ink, fill=fill)
            return self.draw(node, clip=clip)
        self._note(name, "area", fill=_marks.series_colors(
            style.get("fill") if color is None else color, 1)[0])
        return self.draw(_marks.hist(
            self, values, bins, range=range, density=density,
            baseline=baseline, orient=orient, colors=color, **style),
            clip=clip)

    def errorbars(self, points: Iterable[Sequence], *, yerr=None, xerr=None,
                  cap: float | None = None, **style) -> "Panel":
        """Whiskers through each point, in the data's own units.

        `yerr` and `xerr` each take a number (one symmetric bar everywhere), a
        sequence of numbers (one per point), or a sequence of `(down, up)`
        pairs -- which is the shape a confidence interval actually has.

            p.errorbars(means, yerr=[(m - lo, hi - m) for m, lo, hi in ci])

        `cap` is the half-width of the end caps in millimetres; `cap=0` leaves
        them off. Draw these before the markers so the marker sits on top.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.errorbars(self, points, yerr=yerr, xerr=xerr,
                                          cap=cap, **style), clip=clip)

    def fill(self, points: Iterable[Sequence], *, baseline: float = 0.0,
             orient: str = "v", name: str | None = None, **style) -> "Panel":
        """The area between a series and a baseline.

        Named `fill` rather than `area` because `Panel.area` is the plot
        rectangle and has been since the first panel was drawn; renaming that
        to free the word would break every caller that measures the region.

        The default is a pale tint of the ink, unstroked -- an area chart is
        read *through*, and anything darker fights the line on top of it:

            p.fill(trace).line(trace)
        """
        clip = _clip_flag(style)
        self._note(name, "area",
                   fill=style.get("fill", _marks.default_area_fill()))
        return self.draw(_marks.area(self, points, baseline=baseline,
                                     orient=orient, **style), clip=clip)

    def fill_between(self, x: Sequence, y0, y1, *, name: str | None = None,
                     **style) -> "Panel":
        """The band between two curves over shared x -- a confidence envelope.

        `y0` and `y1` are each a sequence the length of `x`, or a single number
        for a flat edge, so a ribbon round a fit and a band above a threshold
        are the same call. `band()` is this with the paint already decided.
        """
        clip = _clip_flag(style)
        self._note(name, "area",
                   fill=style.get("fill", _marks.default_area_fill()))
        return self.draw(_marks.fill_between(self, x, y0, y1, **style),
                         clip=clip)

    @renamed_keywords(colors="color", names="name")
    def stackarea(self, x: Sequence, values, *, baseline=0.0, color=None,
                  name: str | Sequence[str] | None = None, **style) -> "Panel":
        """Stack non-negative series over shared x values, in supplied order.

        `values` is series-major. `baseline` is a scalar or one value per x;
        `color=` is one colour or one per series, and `name=` (one name per
        series) creates legend entries. Use `fill_between` for already
        cumulative boundaries. Returns this panel for chaining.
        """
        import math
        xs = tuple(x)
        rows = _marks._series(values)
        if not xs or len(rows[0]) != len(xs):
            raise DiagramError("stackarea needs one value per x in every series")
        if any(not math.isfinite(v) or v < 0 for row in rows for v in row):
            raise DiagramError("stackarea values must be finite and non-negative")
        lower = _marks._values(baseline, len(xs), "baseline")
        if any(not math.isfinite(v) for v in lower):
            raise DiagramError("stackarea baseline must be finite")
        names = series_names(name)
        if names is not None and len(names) != len(rows):
            raise DiagramError("stackarea needs one name per series")
        fills = _marks.series_colors(color, len(rows))
        for i, row in enumerate(rows):
            upper = tuple(a+b for a,b in zip(lower,row))
            paint = dict(style, fill=fills[i])
            self.fill_between(xs, lower, upper,
                              name=None if names is None else names[i], **paint)
            lower = upper
        return self

    def step(self, points: Iterable[Sequence], *, where: str = "post",
             name: str | None = None, **style) -> "Panel":
        """A staircase through the points, for a quantity that changes at
        instants rather than continuously.

        `where` says when the change happens: `"post"` holds each value until
        the next x, `"pre"` jumps at the previous one, and `"mid"` splits the
        difference. A survival curve is `"post"`; a binned rate is `"mid"`.

        `name=` remembers the series for `legend()`.
        """
        clip = _clip_flag(style)
        stroke = self._series_color(name, style.get("stroke"))
        if stroke is not None:
            style["stroke"] = stroke
        self._note(name, "line", color=style.get("stroke"),
                   dash=style.get("stroke_dash"), width=style.get("stroke_width"))
        return self.draw(tag_series(_marks.step(self, points, where=where,
                                                **style), name), clip=clip)

    @renamed_keywords(colors="color")
    def boxplot(self, groups, *, at=None, width: float = 0.6,
                orient: str = "v", whisker: float = 1.5,
                outliers: bool = True, color=None, **style) -> "Panel":
        """Quartile boxes with Tukey whiskers, one per group.

        `groups` is a mapping of position to samples -- the spelling that
        cannot get the labels out of order -- or a bare sequence of samples,
        which takes its positions from the band scale it is drawn against:

            p.boxplot({"wild type": wt, "mutant": ko})

        Each whisker stops on the furthest observation within `whisker` times
        the interquartile range; everything beyond is drawn as its own point.
        The box is unfilled by default, so the median is the only heavy line in
        it. `inklet.plot.box_stats(sample)` returns the same five numbers if you
        want them in the caption. `color=` fills the boxes: one colour, or one
        per group.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.boxplot(
            self, groups, at=at, width=width, orient=orient, whisker=whisker,
            outliers=outliers, colors=color, **style), clip=clip)

    @renamed_keywords(colors="color")
    def violin(self, groups, *, at=None, width: float = 0.8,
               orient: str = "v", bandwidth: float | None = None,
               samples: int = 64, cut: float = 2.0, median: bool = True,
               color=None, **style) -> "Panel":
        """Mirrored kernel densities, one per group.

        The shape a box plot cannot draw: two samples with the same quartiles
        and one of them bimodal look identical as boxes and obviously different
        as violins. The bandwidth is Silverman's robust rule unless you give
        one; `cut` is how many bandwidths past the extremes the outline runs,
        and `samples` how finely it is drawn.

        A violin claims the density is smooth, so it needs enough data to
        support the claim -- under about twenty points per group, draw the
        points. `color=` fills the violins: one colour, or one per group.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.violin(
            self, groups, at=at, width=width, orient=orient,
            bandwidth=bandwidth, samples=samples, cut=cut, median=median,
            colors=color, **style), clip=clip)

    # -- reference lines, in data coordinates ------------------------------

    def hline(self, y, *, span: tuple | None = None, front: bool = False,
              label: str | Diagram | None = None,
              label_side: str | None = None, **style) -> "Panel":
        """A horizontal rule at one **data** value of y.

        The reference a plot is read against: a zero line, a threshold, a
        control mean. `span=(x0, x1)` clips it to a range of x, also in data.
        It paints under the data unless `front=True`, because a rule is what
        the data is compared to and not what covers it.

            p.hline(0).hline(threshold, stroke_dash=(1.0, 0.8))

        `label=` names the line, set small at its right-hand end and clear of
        it -- above where there is room, below where there is not, which is the
        side logic `annotate` uses. `label_side="n"` or `"s"` forces it. A
        threshold with no word against it is a line the caption has to explain.

            p.hline(0.05, label="p = 0.05", stroke_dash=(1.0, 0.8))
        """
        clip = _clip_flag(style)
        self._layer(_marks.rule(self, y=y, span=span, **style), front, clip)
        return self._rule_label(label, y=y, span=span, side=label_side)

    def vline(self, x, *, span: tuple | None = None, front: bool = False,
              label: str | Diagram | None = None,
              label_side: str | None = None, **style) -> "Panel":
        """A vertical rule at one **data** value of x -- stimulus onset, a
        dose, a cut point. `span=(y0, y1)` clips it in data coordinates.

        `label=` names it, at the top end and to the right of the line unless
        the line is too near the right-hand edge, where it flips to the left.
        `label_side="e"` or `"w"` forces the choice.
        """
        clip = _clip_flag(style)
        self._layer(_marks.rule(self, x=x, span=span, **style), front, clip)
        return self._rule_label(label, x=x, span=span, side=label_side)

    def _rule_label(self, label, **kwargs) -> "Panel":
        """The word against a reference line, over the data and never clipped."""
        if label is None:
            return self
        return self.over(_notes.rule_label(self, label, **kwargs), clip=False)

    def vspan(self, x0, x1, *, front: bool = False, **style) -> "Panel":
        """A shaded stripe between two **data** values of x, full height.

        Named for the axis it is measured on, the way `hline` is: `vspan` is a
        vertical band covering a range of x. The default is the house tint --
        a shade of the ink pale enough to read type over, and greyscale-safe.
        """
        clip = _clip_flag(style)
        return self._layer(_marks.span_node(self, x=(x0, x1), **style), front,
                           clip)

    def hspan(self, y0, y1, *, front: bool = False, **style) -> "Panel":
        """A shaded stripe between two **data** values of y, full width."""
        clip = _clip_flag(style)
        return self._layer(_marks.span_node(self, y=(y0, y1), **style), front,
                           clip)

    def rect(self, x0, y0, x1, y1, *, front: bool = False, **style) -> "Panel":
        """A rectangle whose four sides are **data** values -- a gated region,
        the extent of an inset, a box round a cluster."""
        clip = _clip_flag(style)
        return self._layer(_marks.rect_node(self, x0, y0, x1, y1, **style),
                           front, clip)

    def _layer(self, node: Diagram, front: bool,
               clip: bool | None = None) -> "Panel":
        return (self.over(node, clip=clip) if front
                else self.under(node, clip=clip))

    def under(self, *items: Diagram, clip: bool | None = None) -> "Panel":
        """Content that paints beneath everything else -- a backdrop, anything
        the data should sit on top of.

        **In panel coordinates, not data coordinates.** See `over` for what
        that means and `hline`/`vspan`/`rect` for the data-coordinate versions
        of what this is usually reached for.
        """
        return self._add(self._under, [as_drawn(i) for i in items], clip)

    def over(self, *items: Diagram, clip: bool | None = None) -> "Panel":
        """Content that paints above everything else, like an annotation.

        **These take panel coordinates -- millimetres from the centre of the
        plot area -- not data.** They are the two methods here that do. `line`,
        `marks`, `bars`, `hline`, `vspan`, `rect`, `place` and `point` all
        speak data and map it for you; `over` and `under` take a finished
        diagram and set only its paint order, so there is nothing left for them
        to map.

        The line above is the whole hazard, and the fix is usually not to reach
        for these at all: what people came here to draw is a reference line or
        a shaded band, and `hline(y)`, `vline(x)`, `hspan(y0, y1)`,
        `vspan(x0, x1)` and `rect(x0, y0, x1, y1)` are those in data, with
        `front=True` when they belong on top. Reach for `over`/`under` for
        something with no data position of its own -- a scale bar, a key, a
        letter in the corner -- and run any datum through `point(x, y)` or
        `x.map(v)` first:

            at = p.x.map(0.0)                       # t = 0, in millimetres
            p.over(inklet.polyline([(at, p.area.y0), (at, p.area.y1)]))

        Passing the datum straight in is silent and wrong: on a panel spanning
        -1 to 3.5, `0.0` is not `t = 0`, it is the middle of the axis. Nothing
        in the linter can catch that, because a rule drawn in the wrong place is
        a rule drawn perfectly well.
        """
        return self._add(self._over, [as_drawn(i) for i in items], clip)

    # -- furniture --------------------------------------------------------

    def background(self, **style) -> "Panel":
        """Fill the plot area, beneath everything already in it.

        Distinct from the figure's paper: this is the area alone, so a tinted
        panel on a white page is one call and the axis furniture stays outside
        the tint.
        """
        node = Diagram(prim=RectPrim(self.width, self.height), kind=AREA_KIND)
        self._under.insert(0, node.styled(**style) if style else node)
        return self._touched()

    def outline(self, **style) -> "Panel":
        """A rectangle around the area, drawn over the data.

        Styled as a spine, not as the area: it is the four axes of the panel
        drawn at once, and it should match the ones that carry ticks.
        """
        box = self.area
        node = polyline(box.corners, closed=True, kind=SPINE_KIND, **style)
        self._over.append(as_drawn(node))
        return self._touched()

    def grid(self, *, x: bool = True, y: bool = True, count: int = 5,
             x_options: dict | None = None, y_options: dict | None = None,
             **style) -> "Panel":
        """Rules at the tick positions, under the data.

        The values come from the same thinning the axis uses, so a gridline
        always has a tick and a label on it -- a rule with no number against it
        is furniture pretending to be information.

        x_options and y_options accept tick_values options, such as ticks,
        format, rotate and font_size, to match custom axis thinning.
        """
        box = self.area
        lines: list[Diagram] = []
        if x:
            for value in tick_values(self.x, **({'count':count,'horizontal':True} | (x_options or {}))):
                at = self.x.map(value)
                lines.append(polyline(((at, box.y0), (at, box.y1)),
                                      kind=GRID_KIND, **style))
        if y:
            for value in tick_values(self.y, **({'count':count,'horizontal':False} | (y_options or {}))):
                at = self.y.map(value)
                lines.append(polyline(((box.x0, at), (box.x1, at)),
                                      kind=GRID_KIND, **style))
        self._under.extend(as_drawn(line) for line in lines)
        return self._touched()

    def axis(self, side: str = "bottom", *, at=None, **kwargs) -> "Panel":
        """Hang an axis off one edge, built from this panel's own scale.

        `at=` puts it at a **data value on the other scale** instead of on the
        edge: `p.axis("bottom", at=0)` draws the x axis through y = 0, which is
        the layout a residual or a log fold change wants, since a spine along
        the bottom of a panel whose data straddles zero is a rule the data is
        not measured against.

        Everything `plot.axis()` takes passes through -- `label`, `ticks`,
        `count`, `format`, `minor`, `rotate` for long category names.

        On a panel with a `matrix`, an axis with no ticks (`ticks=[]`) or with
        hidden ones (`labels=False` and `tick_size=0`) draws no spine unless
        `spine=True` is passed: the cells' own edge is the boundary.
        """
        if side not in SIDES:
            raise ValueError(
                f"unknown axis side {side!r}; expected one of {', '.join(SIDES)}"
            )
        if self._matrix and "spine" not in kwargs:
            ticks = kwargs.get("ticks")
            size = kwargs.get("tick_size")
            hidden = (kwargs.get("labels", True) is False and size is not None
                      and mm(size) == 0)
            if (ticks is not None and len(ticks) == 0) or hidden:
                kwargs["spine"] = False
        node = as_drawn(axis(getattr(self, _AXIS_SCALE[side]), side=side, **kwargs))
        offset = self._edge(side) if at is None else self._crossing(side, at)
        self._over.append(node.translated(offset.x, offset.y))
        return self._touched()

    def _crossing(self, side: str, at) -> Vec2:
        """Where an axis sits when it is placed at a data value.

        The value is read on the *perpendicular* scale, which is the only
        reading that makes sense: an x axis crosses at a y.
        """
        if side in ("bottom", "top"):
            return Vec2(0.0, self.y.map(at))
        return Vec2(self.x.map(at), 0.0)

    def axes(self, x: str | None = None, y: str | None = None, *,
             x_options: dict | None = None, y_options: dict | None = None,
             **kwargs) -> "Panel":
        """Bottom and left axes with shared and per-axis options.

        Common keyword options apply to both axes. x_options and y_options
        override them independently, including ticks, format, rotate, font_size
        and label. Their coordinate mappings and the data remain unchanged.
        """
        for options in (x_options, y_options):
            if options is not None and not isinstance(options, dict):
                raise TypeError('axis options must be dictionaries')
        self.axis("bottom", **({'label':x} | kwargs | (x_options or {})))
        return self.axis("left", **({'label':y} | kwargs | (y_options or {})))

    def twin_y(self, scale=None, *, side: str = "right",
               label: str | Diagram | None = None, color: str | None = None,
               axis: bool = True, **kwargs) -> "Panel":
        """A second y scale over the same area, and a handle that draws in it.

        Two quantities on one plot -- a current in mA and an efficiency in
        percent -- are two scales over one rectangle, and the handle returned
        here *is* a panel: it shares this one's content, so everything it draws
        lands in the same picture, mapped through the second scale.

            eff = p.twin_y((0, 100), label="Faradaic efficiency / %",
                           color=TH.color(1))
            eff.line(points).marks(inklet.marker("circle"), points)
            fig.add(p.build())              # build the parent, never the twin

        `scale` is a scale or the shorthand `panel()` takes. `color` tints the
        second axis -- its spine, ticks and numbers -- which is the only thing
        that tells a reader which curve to read against which side. Pick one
        dark enough to carry type: `inklet.lint` checks tick labels for contrast,
        and the paler half of the Okabe-Ito palette will not reach 4.5:1 on
        white. Build the panel this was called on: the twin has no content of
        its own.
        """
        if side not in ("left", "right"):
            raise ValueError(
                f'a twin y axis is on the "left" or the "right", not {side!r}'
            )
        twin = self._twin(y=_fit(scale, self.height / 2, -self.height / 2))
        if axis:
            twin.axis(side, label=label, **_tinted(color, kwargs))
        return twin

    def twin_x(self, scale=None, *, side: str = "top",
               label: str | Diagram | None = None, color: str | None = None,
               axis: bool = True, **kwargs) -> "Panel":
        """A second x scale over the same area -- wavelength above frequency,
        or a second time base. `twin_y` explains the shape of it."""
        if side not in ("top", "bottom"):
            raise ValueError(
                f'a twin x axis is on the "top" or the "bottom", not {side!r}'
            )
        twin = self._twin(x=_fit(scale, -self.width / 2, self.width / 2))
        if axis:
            twin.axis(side, label=label, **_tinted(color, kwargs))
        return twin

    def _twin(self, *, x: Scale | None = None, y: Scale | None = None) -> "Panel":
        """A panel sharing this one's three content lists.

        Sharing the lists rather than copying them is what makes every method
        on `Panel` work on the twin for free: paint order stays one order
        across both scales, and `build()` on the parent picks all of it up.
        """
        twin = Panel(width=self.width, height=self.height,
                     x=self.x if x is None else x,
                     y=self.y if y is None else y, clip=self.clip)
        twin._under = self._under
        twin._content = self._content
        twin._over = self._over
        twin._insets = self._insets
        twin._keys = self._keys
        twin._brackets = self._brackets
        twin._deferred = self._deferred
        twin._parent = self
        return twin

    def title(self, content: str | Diagram, *, align: str = "center",
              pad: float | str | None = None) -> "Panel":
        """A heading over the panel, clear of whatever is already in it."""
        node = (content if isinstance(content, Diagram)
                else text_node(content, active_theme().font_size, TITLE_KIND))
        gap = active_theme().gap("s") if pad is None else mm(pad)
        self._title = (node, align, gap)
        return self._touched()

    # -- keys, built from what was actually drawn --------------------------

    def _note(self, name: str | None, form: str, **fields) -> "Panel":
        """Remember that a series called `name` was drawn as `form`.

        One record per drawing call, merged by name at `legend()` time. Silent
        when there is no name: a series with nothing to call it has nothing to
        put in a key, and demanding one would make `name=` compulsory on every
        method here.
        """
        if name is not None:
            self._keys.append(SeriesKey(name=str(name),
                                        forms=frozenset((form,)), **fields))
        return self

    def _series_color(self, name: str | None, given: str | None) -> str | None:
        """The colour a named series is drawn in; see `plot.series`."""
        return series_color(self._keys, name, given)

    def _note_series(self, names: Sequence[str],
                     colors: Sequence[str]) -> "Panel":
        if len(names) != len(colors):
            raise DiagramError(
                f"names= has {len(names)} names for {len(colors)} series"
            )
        for name, color in zip(names, colors):
            self._note(name, "area", fill=color, color=color)
        return self

    @property
    def keys(self) -> tuple[SeriesKey, ...]:
        """The named series in this panel, one entry each, in drawing order.

        What `legend()` is built from. Readable so that a caller can check the
        key they are about to get -- or drop a series from it -- without
        rasterising anything.
        """
        return tuple(merge_keys(self._keys))

    def legend(self, *, corner: str | None = "ne", side: str | None = None,
               entries: Sequence[tuple[str, object]] | None = None,
               columns: int | str | None = None, max_width: float | str | None = None,
               swatch: float | str | None = None,
               pad: float | str | None = None, plate: bool | None = None,
               title: str | None = None, markup: bool = True, order: str = "row",
               col_gap: float | str | None = None, row_gap: float | str | None = None,
               **style) -> "Panel":
        """A key built from the series this panel actually drew.

        Every drawing method takes `name=`, and the panel remembers the
        appearance it drew under that name: colour, dash, marker, whether there
        was a band under the line. The key is a rendering of that record, so it
        cannot describe a picture it no longer matches -- which is the failure
        `inklet.lint` reports as `KEY_MISMATCH`, fixed at the source rather than
        detected afterwards.

            p.band(t, lo, hi, color=C, name="wild type")
            p.line(mean, stroke=C, name="wild type")
            p.scatter(points, color=C, name="wild type")
            p.legend(corner="ne")

        `corner="auto"` searches clear plot space against existing marks and
        raises if no sampled position fits; it never shrinks the key.
        `corner="best"` puts it in the emptiest spot inside the plot area
        (corners preferred among equally empty ones) and, when every spot
        would cover data, beside the plot on the right instead.
        Fixed `corner` puts it inside the plot area on a knocked-out plate; `side`
        ("right", "left", "top", "bottom") puts it outside, clear of whatever
        furniture is already there, and then no plate is needed. `entries=`
        overrides the record entirely, taking `(name, colour)` or
        `(name, diagram)` pairs, which is the escape hatch for a key that
        describes something this panel did not draw.

        Top/bottom legends fit their columns to the plot width by default,
        centred on the data. When that takes more rows than the whole panel
        width would, counting the axis furniture beside the data, the key is
        fitted to the panel width and left-aligned with the panel's outer
        edge. Pass `columns=1` to stack entries explicitly, or
        `columns='auto'` and `max_width=...` to choose another measured width.
        Text is never shrunk.

        A `name=` is prose the figure wrote about one curve, so it reads inline
        markup -- `p.line(mean, name="ChR2 (//n// = 12)")` sets that `n` in
        italic, which is the only spelling a style guide accepts. Pass
        `markup=False` for names lifted out of a data file.
        """
        theme = active_theme()
        if swatch is None and 'font_size' in style:
            swatch = SWATCH_OF_TYPE * mm(style['font_size'])
        rows = list(entries) if entries is not None else self._legend_rows(swatch)
        if not rows:
            raise DiagramError(
                "legend() found no named series: pass name= to line(), "
                "scatter(), marks(), hist() or band(), names= to bars(), or "
                "give legend(entries=[...]) directly"
            )
        if columns is None:
            columns = 'auto' if side in ('top', 'bottom') else 1

        def build(width):
            return make_legend(rows, columns=columns, max_width=width, swatch=swatch, title=title,
                               markup=markup, order=order, col_gap=col_gap, row_gap=row_gap, **style)

        gap = theme.gap("s") if pad is None else mm(pad)
        # Outside the plot the key is measured against the furniture's line
        # boxes, which already carry the type's leading; a further 's' step
        # parted it from the axis name it explains.
        beside_gap = theme.gap("xs") if pad is None else gap
        if side in ('top', 'bottom') and columns == 'auto' and max_width is None:
            self._over.append(self._across(build, side, beside_gap))
            return self._touched()
        if columns == 'auto' and max_width is None:
            max_width = self.width if side is not None else self.width - 2*gap
        node = build(max_width)
        if side is not None:
            self._over.append(self._beside(node, side, beside_gap))
            return self._touched()
        if plate is None:
            plate = True
        if plate:
            node = _plated(node, theme, theme.gap("xs"))
        if corner == 'best':
            from .key_place import best_spot
            placed = best_spot(self, node, gap)
            if placed is None:          # nowhere clear inside: beside it
                placed = self._beside(build(max_width), 'right', beside_gap)
            self._over.append(placed)
            return self._touched()
        if corner == 'auto':
            from ..layout.clear_space import place_in_clear_space
            node = place_in_clear_space(node, within=self.area,
                                        avoid=(*self._content,*self._over), pad=gap)
        else:
            node = _into_corner(node, self.area, corner or "ne", gap)
        self._over.append(node)
        return self._touched()

    def _across(self, build, side: str, gap: float) -> Diagram:
        """A top or bottom key, as wide as the whole panel when it needs to be.

        Fitted to the data width first and centred on the data. When the
        panel's furniture makes it wider than the data, the key is refitted
        to that full width and kept if it takes fewer rows (or fits only
        there); it is then centred on the data if it still fits within the
        data width, and otherwise left-aligned with the panel's outer edge.
        """
        box = _union_box(self._under + self._content + self._over) or self.area
        try:
            node, failure = build(self.width), None
        except ValueError as error:
            node, failure = None, error
        if box.width > self.width + 1e-9:
            try:
                wide = build(box.width)
            except ValueError:
                wide = None
            if wide is not None and (node is None or wide.bbox.height < node.bbox.height - 1e-9):
                placed = beside(wide, box, side, gap, Vec2(0.0, 0.0))
                if wide.bbox.width > self.width + 1e-9:
                    placed = placed.translated(box.x0 - placed.bbox.x0, 0.0)
                return placed
        if node is None:
            raise failure
        return beside(node, box, side, gap, Vec2(0.0, 0.0))

    def _legend_rows(self, swatch: float | str | None) -> list[tuple[str, object]]:
        """One (name, swatch) per series, the swatch mirroring how it was drawn.

        Sized from `plot.key`'s own constant, so a built key and a hand-written
        `legend(entries=[...])` beside it are the same size.
        """
        theme = active_theme()
        size = (SWATCH_OF_TYPE * theme.font_size_small if swatch is None
                else mm(swatch))
        return [(entry.name, swatch_for(entry, size)) for entry in self.keys]

    def colorbar(self, *, side: str = "right", source=None, corner: str | None = None,
                 scale: Scale | None = None, length: float | str | None = None,
                 pad: float | str | None = None, plate: bool = False, title: str | None = None, **kwargs) -> "Panel":
        """The ramp this panel's matrix was coloured through, as a key beside it.

        Built from the panel's own `ramp=` and `scale=`, not from a second pair
        that agrees with them today: `Panel.matrix`'s docstring asks the caller
        to share one scale object with the key, and this is that call making it
        impossible to do otherwise.

            p.matrix(field, ramp=shades, scale=heat)
            p.colorbar(label="ΔF/F")

        `side` is which edge of the panel it stands against, and the numbers
        face outward from there. It defaults to as long as the edge it runs
        along, which is what makes a bar and a panel look like one object.
        ``corner=`` places the complete measured key inside the data rectangle;
        supply a short ``length`` and optionally ``plate=True`` for an inset key.
        """
        bar = self._ramp if source is None else source
        if bar is None:
            raise DiagramError(
                "colorbar() has no ramp to draw: call matrix(ramp=...) first, "
                "or pass source= a ramp of your own"
            )
        theme = active_theme()
        vertical = side in ("left", "right")
        span = (self.height if vertical else self.width) if length is None \
            else mm(length)
        node = as_drawn(make_colorbar(
            bar, scale=self._scale_domain if scale is None else scale,
            side=side, length=span, **kwargs))
        gap = theme.gap("s") if pad is None else mm(pad)
        if corner is None and pad is None:
            # Beside the panel, like an outside legend: close to the furniture.
            gap = theme.gap("xs")
        if title is not None:
            from ..layout import vstack
            node=vstack([text_node(title,mm(kwargs.get('tick_font_size') or theme.font_size_small),'label',
                **{k:kwargs[k] for k in ('font_family','font_weight','font_style') if k in kwargs}),node],gap=theme.gap('xs'))
        if plate:
            node = _plated(node, theme, theme.gap('xs'))
        if corner is not None and (node.width>self.width-2*gap or node.height>self.height-2*gap):
            raise ValueError('inset colorbar does not fit; shorten length or reduce padding')
        if corner=='auto':
            from ..layout.clear_space import place_in_clear_space
            placed=place_in_clear_space(node,within=self.area,avoid=(*self._content,*self._over),pad=gap)
        else:
            placed=self._beside(node,side,gap) if corner is None else _into_corner(node,self.area,corner,gap)
        self._over.append(placed)
        return self._touched()

    def _beside(self, node: Diagram, side: str, gap: float) -> Diagram:
        """Put a key outside the panel, clear of the furniture already there.

        Measured against everything built so far rather than against the plot
        area, so a colorbar on the right of a panel whose right side is empty
        sits close in, and one on the left clears the y axis and its name.
        """
        if side not in SIDES:
            raise ValueError(
                f"unknown side {side!r}; expected one of {', '.join(SIDES)}"
            )
        box = _union_box(self._under + self._content + self._over) or self.area
        return beside(node, box, side, gap, Vec2(0.0, 0.0))

    # -- writing on the plot, in data coordinates --------------------------

    def text(self, x, y, content: str | Diagram, *, anchor: str = "center",
             offset: Sequence[float] = (0.0, 0.0),
             size: float | str | None = None, markup: bool = True,
             front: bool = True, **style) -> "Panel":
        """Words at one **data** point.

        `anchor` is the compass point of the *label* that lands on the datum,
        so `anchor="w"` writes eastward from it -- the same word `inklet.place`
        uses. `offset` is a nudge in millimetres afterwards, because a
        typographic clearance is a length and not a quantity.

            p.text(2020, 41.5, "onset", anchor="w", offset=(1, 0))

        `markup=False` sets the string exactly as typed, which is what a label
        that came out of the data needs -- `p.text(x, y, sample_id,
        markup=False)`. Prose keeps markup, as it does everywhere else.
        """
        # Writing is never clipped, whatever the panel does with its data: a
        # word cut in half at the spine is not a shorter word.
        return self._layer(_notes.text_at(self, x, y, content, anchor=anchor,
                                          offset=offset, size=size,
                                          markup=markup, **style),
                           front, clip=False)

    def arrow(self, a: Sequence, b: Sequence, *, head: str = "triangle",
              label: str | Diagram | None = None, front: bool = True,
              **style) -> "Panel":
        """An arrow from one **data** point to another.

        A `inklet.links` connector between two anchors, so the head, the dashes
        and the label are the ones the rest of the figure uses. Nothing is
        clipped: both ends are points, and the arrow lands on the coordinates
        given.

            p.arrow((3.2, 0.8), (4.0, 0.45), label="washout")
        """
        carrier, routed = _notes.arrow_between(self, a, b, head=head,
                                               label=label, **style)
        self._content.append(carrier)
        return self._layer(routed, front, clip=False)

    def annotate(self, x, y, text: str | Diagram, *, side: str = "n",
                 clear: float | str | None = None, leader: bool = True,
                 inside: bool = True, dot: bool = False, front: bool = True,
                 **kwargs) -> "Panel":
        """A callout on one **data** point: a label clear of it, with a leader.

        `inklet.annotate` places it, so `side` is a request -- a blocked one walks
        around the compass -- and the clearance is measured off the datum's
        envelope. The label is kept **inside the plot area** by default, since
        a callout that escapes over the spine reads as belonging to the panel
        above. `dot=True` marks the point itself, for a curve with no marker
        there already.

            p.annotate(peak_t, peak_v, "peak", side="ne")
        """
        return self._layer(
            _notes.callout(self, x, y, text, side=side, clear=clear,
                           leader=leader, inside=inside, dot=dot, **kwargs),
            front, clip=False)

    # -- output -----------------------------------------------------------

    def placed(self, x, y) -> Diagram:
        """Build with the data rectangle's top-left at page ``(x, y)`` in mm.

        Axis labels and legends remain outside that rectangle; their different
        sizes never shift its position. No scaling or mutation is performed.
        """
        node = self.build()
        area = plot_area(node)
        return node.translated(mm(x)-area.x0, mm(y)-area.y0)

    def guide(self, a, b, *, label=None, at=.5, offset=1., label_style=None,
              **style) -> "Panel":
        """A straight data guide with a label following its displayed direction.

        ``at`` is the fraction along the displayed segment; ``offset`` is the
        signed perpendicular clearance in mm. Log scales and panel aspect ratio
        are included in the angle. ``label_style`` accepts text() options.
        """
        import math
        import inklet as i
        if not math.isfinite(at) or not 0 <= at <= 1:
            raise ValueError('guide at must be between zero and one')
        clear = mm(offset)
        if not math.isfinite(clear):
            raise ValueError('guide offset must be finite')
        start, end = self.point(*a), self.point(*b)
        dx, dy = end.x-start.x, end.y-start.y
        length = math.hypot(dx,dy)
        if not length:
            raise ValueError('guide needs distinct displayed endpoints')
        self.line([a,b], **style)
        if label is not None:
            node = label if isinstance(label,Diagram) else i.text(str(label), **(label_style or {}))
            angle = math.atan2(dy,dx)
            if angle > math.pi/2: angle -= math.pi
            if angle < -math.pi/2: angle += math.pi
            node = node.rotated(math.degrees(angle))
            box = node.bbox
            self._over.append(node.translated(start.x+at*dx+dy/length*clear-box.center.x,
                                               start.y+at*dy-dx/length*clear-box.center.y))
        return self._touched()

    def build(self) -> Diagram:
        """The panel as a diagram, centred like everything else, with its
        `origin` anchor on the centre of the plot area.

        The rectangle itself comes too: `area-nw` and `area-se` anchors and a
        `plot_area` note. A built panel is otherwise just a box of ink, and
        every caller that wants to line panels up -- `facets` by their areas,
        `letters` by their top edges -- has to guess where the axes stop and
        the data starts. One panel with a legend over it then carries its
        letter 5mm higher than its neighbour, which is the first thing a
        reader notices about a multi-panel figure.

        The note and the anchors are in the frame the panel was *drawn* in,
        before `drawn_group` recentres the node -- `node.bbox` is on the far
        side of that recentring, so a reader must carry the rectangle through
        `node.transform` before comparing the two (`draw/annotate.py::
        _plot_area` is the worked example). Reading it raw against the bbox
        agrees only for a panel whose furniture happens to be symmetric.

        Cached, because building mints fresh node ids: rendering the same panel
        twice must not produce two different files.
        """
        inset_nodes = tuple(spec.sub.build() if hasattr(spec.sub, "build") else spec.sub
                            for spec in self._insets)
        if any(a is not b for a, b in zip(inset_nodes, self._inset_state)) or len(inset_nodes) != len(self._inset_state):
            self._built = None
        if self._built is not None:
            return self._built
        children = list(self._under) + list(self._content) + self._placed_over()
        if self._title is not None:
            children.append(self._titled(children))
        if self._insets:
            from .inset import external_parts
            for spec, node in zip(self._insets, inset_nodes):
                furniture = _union_box(children) or self.area
                children.extend(external_parts(self, node, furniture, **spec.options))
        self._inset_state = inset_nodes
        self._built = drawn_group(children, PANEL_KIND)
        declare_area(self._built, self.area)
        _declare_domain(self._built, self._scale_domain)
        return self._built

    def _titled(self, children: Sequence[Diagram]) -> Diagram:
        node, align, pad = self._title
        box = _union_box(children) or self.area
        text_box = node.bbox
        top = box.y0 - pad - text_box.height / 2
        if align == "start":
            at = Vec2(box.x0 + text_box.width / 2, top)
        elif align == "end":
            at = Vec2(box.x1 - text_box.width / 2, top)
        else:
            at = Vec2(0.0, top)          # over the area, not over the furniture
        centre = node.transform.apply(node.anchor_point("center"))
        return node.translated(at.x - centre.x, at.y - centre.y)

    def _edge(self, side: str) -> Vec2:
        box = self.area
        return {
            "bottom": Vec2(0.0, box.y1), "top": Vec2(0.0, box.y0),
            "left": Vec2(box.x0, 0.0), "right": Vec2(box.x1, 0.0),
        }[side]

    def _touched(self) -> "Panel":
        self._built = None
        # A twin shares the parent's content lists, so drawing through the
        # second scale changes what the parent will build. Without this the
        # parent would hand back a cached diagram missing everything the twin
        # added after it was first built.
        if self._parent is not None:
            self._parent._touched()
        return self

    # -- annotation, implemented in plot/inset.py and plot/ribbon.py -------
    # Imported inside the methods: those modules reach back into `draw` and
    # into this one, and a module-level import here would close the loop.

    def inset(self, sub, **kwargs) -> "Panel":
        """Put a smaller panel in a corner of this one. See `plot.inset`.

        `zoom=(x0, x1, y0, y1)` in this panel's data coordinates also draws the
        window the inset magnifies and joins it to the inset. Style keywords
        (`stroke=`, `stroke_width=`) paint the window and connectors;
        `connector={"stroke_dash": (1, 0.6)}` styles the connectors alone.
        """
        from .inset import inset as _inset

        return _inset(self, sub, **kwargs)

    def bracket(self, x0, x1, y=None, **kwargs) -> "Panel":
        """A grouping or significance bracket across a data span.

        `p.bracket("wt", "ko", "***")` is the significance case: the span is
        two categories, the text is the stars, and the height is left out --
        the bracket then clears whatever is drawn between the two ends, which
        is the number the author would otherwise recompute every time the data
        changed. `p.bracket(1, 3, 8.2, text="***")` still puts it at a data
        value of y. The span is data, the ticks are millimetres.

        `plot.panel_bracket` is the same thing as a Diagram, for a caller that
        wants to place it themselves.
        """
        from .inset import panel_bracket

        # Recorded in the frame it will be drawn in, not the one it was built
        # in: `draw_bracket` hands back a group centred on its own origin, and
        # a box measured there would put the next bracket over the data.
        node = as_drawn(panel_bracket(self, x0, x1, y, **kwargs))
        self._brackets.append(node)
        return self.over(node, clip=False)

    def ribbon(self, a, b, **kwargs) -> "Panel":
        """A Sankey band from data point `a` to data point `b`.

        `width0=` and `width1=` are data too, read on whichever axis the flow
        crosses, so the band tapers the way the numbers do. See `plot.ribbon`.
        """
        from .ribbon import panel_ribbon

        return self.draw(panel_ribbon(self, a, b, **kwargs))

    def break_marks(self) -> "Panel":
        """Draw the break glyph wherever a `inklet.broken` scale interrupts.

        On the axis line the axis draws its own; this is the second half a
        journal asks for -- the same mark across every filled data mark that
        runs *through* the break, because a bar drawn straight past one is a
        rectangle whose length stands for nothing:

            p = inklet.panel(60, 40, x=names,
                          y=inklet.broken((0, 400), breaks=[(45, 330)]))
            p.bars(names, counts).break_marks().axes(y="colonies")

        Call it after the marks it is meant to cross and before `build()`.
        Which marks those are is read off the picture, so a stack, a group and
        a histogram all work, and a panel with nothing across the break is left
        exactly as it was.

        Marking a bar does not make it honest -- `inklet.lint`'s `BREAK_DISTORTS`
        reports the crossing whether or not the glyph is there, which is the
        way round it has to be.
        """
        from .breaks import break_marks

        return break_marks(self)

    @renamed_keywords(colors="color")
    def swarm(self, groups, *, at=None, width: float = 0.8,
              max_width: float | str | None = None, orient: str = "v",
              size: float | str | None = None,
              gap: float | str | None = None, marker: str = "circle",
              hollow: bool = False, color=None, **style) -> "Panel":
        """Every observation as its own dot, nudged sideways until none hides
        another.

        `groups` is spelled the way `boxplot` and `violin` spell it -- a mapping
        of position to samples, or a bare sequence taking its positions from the
        band scale it is drawn against -- so a swarm can be laid over either:

            p.boxplot({"wild type": wt, "mutant": ko}, outliers=False)
            p.swarm({"wild type": wt, "mutant": ko})

        Under about twenty points a group this is the honest picture: a box
        claims quartiles a reader cannot check and a violin claims a smooth
        density that eleven animals do not support, while a swarm shows the
        eleven animals. The dots keep their exact values -- the layout moves
        them sideways only -- so a mean drawn over them lands where it should.

        `size` is the dot's diameter in millimetres and defaults to the box
        plot's outlier dot, `gap` the air between two neighbours. `hollow=True`
        draws them as rings on paper, which is worth it up to a dozen or so
        points and a thicket beyond that. `color=` takes one colour, or one per group.

        **Width.** `width=` is the slot, as a fraction of the band step, the
        same as every other categorical mark; `max_width=` is an absolute
        millimetre cap, and the narrower of the two wins. A swarm that does not
        fit loses its air first -- the gap is bisected away until the dots
        touch -- and only then its dot size, down to a floor of 0.4 mm. Size is
        the last thing to go because a dot too small to see is not a dot; a
        swarm that still overruns is left overrunning, for the panel to clip
        and the linter to report.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.swarm(
            self, groups, at=at, width=width, max_width=max_width,
            orient=orient, size=size, gap=gap, marker=marker, hollow=hollow,
            colors=color, **style), clip=clip)

    @renamed_keywords(colors="color", names="name")
    def dumbbell(self, at: Sequence, values, *, orient: str = "v",
                 size: float | str | None = None, color=None,
                 name: str | Sequence[str] | None = None, marker: str = "circle",
                 connector: dict | None = None, **style) -> "Panel":
        """Two or more dots per category joined by a line: a dumbbell plot.

        `values` holds one sequence per series, each with one value per
        position in `at`, the same shape `bars` takes for grouped bars. The
        dots of one category share its centre on the band scale, and a line
        runs from the smallest to the largest value present. `None` or NaN is
        a missing value: that dot is not drawn, and a category with only one
        value has no line.

            p.dumbbell(genes, [before, after], name=["before", "after"],
                       orient="h")

        `size` is the dot diameter in millimetres (default: the scatter
        marker). `color=` sets one colour, or one per series; the default is
        the theme palette. `connector=` overrides the line's style, which by
        default is a light grey at the theme's thick stroke. `name=` (one name
        per series) adds one marker entry per series to `legend()`.
        """
        from .paired import dumbbell as _dumbbell

        clip = _clip_flag(style)
        node, fills = _dumbbell(self, at, values, orient=orient, size=size,
                                colors=color, marker=marker,
                                connector=connector, **style)
        names = series_names(name)
        if names is not None:
            if len(names) != len(fills):
                raise DiagramError(
                    f"name= has {len(names)} names for {len(fills)} series")
            for entry, fill in zip(names, fills):
                self._note(entry, "marker", color=fill, marker=marker)
        return self.draw(node, clip=clip)

    def lollipop(self, at: Sequence, values: Sequence, *, baseline: float = 0.0,
                 orient: str = "v", size: float | str | None = None,
                 color: str | None = None, marker: str = "circle",
                 stem: dict | None = None, name: str | None = None,
                 **style) -> "Panel":
        """One value per category as a dot on a stem from `baseline`.

        A lighter alternative to a bar chart when there are many categories
        and the value, not the area, is what the reader compares. Positions
        come from the band scale, as for `bars`. `None` or NaN draws nothing
        for that category.

            p.lollipop(pathways, scores, orient="h", color=TH.color(1))

        `stem=` overrides the stem's style (default: the dot colour at the
        theme stroke width). `name=` adds a marker entry to `legend()`.
        """
        from .paired import lollipop as _lollipop

        clip = _clip_flag(style)
        color = self._series_color(name, color)
        node, ink = _lollipop(self, at, values, baseline=baseline,
                              orient=orient, size=size, color=color,
                              marker=marker, stem=stem, **style)
        self._note(name, "marker", color=ink, marker=marker)
        return self.draw(node, clip=clip)

    def ecdf(self, values: Sequence[float], *, weights: Sequence[float] | None = None,
             complementary: bool = False, normalize: bool = True,
             extend: bool = True, name: str | None = None,
             **style) -> "Panel":
        """The empirical cumulative distribution of `values` as a step line.

        Each distinct value raises the curve by the share of observations
        equal to it, so the curve reads "fraction of observations at or below
        x". `complementary=True` draws the share strictly above x instead
        (the survival curve), which is the form a heavy tail is read from on
        a log y axis. `weights=` weights each observation, and
        `normalize=False` plots counts (or weight sums) instead of fractions.

            p.ecdf(control, name="control")
            p.ecdf(treated, name="treated")

        `extend=True` runs the curve flat to both ends of a continuous x
        axis. On a log axis, points that cannot be mapped (zero or negative)
        are left out. `name=` adds a line entry to `legend()`.
        `inklet.plot.ecdf(values)` returns the steps without drawing them.
        """
        from .cumulative import ecdf as _ecdf, staircase

        values = list(values)
        weights = None if weights is None else list(weights)
        clip = _clip_flag(style)
        xs, ys = _ecdf(values, weights=weights, complementary=complementary,
                       normalize=normalize)
        # The level before the first step: nothing for the ECDF, everything
        # (the last cumulative value) for its complement.
        start = (_ecdf(values, weights=weights, normalize=normalize)[1][-1]
                 if complementary else 0.0)
        low = high = None
        domain = getattr(self.x, "domain", None)
        if (extend and not isinstance(self.x, Band) and domain is not None
                and all(isinstance(v, (int, float)) for v in domain)):
            low, high = min(domain), max(domain)
        points = staircase(xs, ys, start=start, low=low, high=high)
        points = [p for p in points
                  if _mappable(self.x, p[0]) and _mappable(self.y, p[1])]
        if len(points) < 2:
            raise DiagramError("ecdf() has fewer than two points this axis can show")
        stroke = self._series_color(name, style.get("stroke"))
        if stroke is not None:
            style["stroke"] = stroke
        self._note(name, "line", color=style.get("stroke"),
                   dash=style.get("stroke_dash"), width=style.get("stroke_width"))
        return self.draw(tag_series(polyline(self.map(points), **style), name),
                         clip=clip)

    @renamed_keywords(colors="color")
    def ridgeline(self, groups, *, at=None, overlap: float = 1.5,
                  bandwidth: float | None = None, samples: int = 96,
                  scale: str = "shared", fit: bool = True, color=None,
                  **style) -> "Panel":
        """Overlapping kernel densities, one per category: a ridgeline plot.

        The panel needs a band y scale (the categories) and a continuous x
        scale (the values), which every ridge shares. `groups` is spelled as
        for `violin`: a mapping of category to samples, or a sequence of
        samples in the order of the y categories.

            p = inklet.panel(50, 40, x=(0, 10), y=list(reversed(stages)))
            p.ridgeline({s: times[s] for s in stages})

        Each ridge's baseline is the lower edge of its category's step, and
        `overlap` is the height of the tallest ridge in steps; above 1 a
        ridge rises into the rows above it. Ridges are filled with an opaque
        colour and drawn from the top of the page down, so lower ridges cover
        the ones behind them. The density runs over the whole x domain.

        `scale="shared"` (default) uses one height scale for every ridge, so
        a narrow sample has a tall peak; `scale="each"` gives every ridge the
        same peak height. `bandwidth` defaults to Silverman's robust rule per
        group, as for `violin`, and `samples` is the number of points along
        x. `color=` sets one fill, or one per group (default: one tint for all);
        other keywords style the outline.

        `fit=True` (default) scales every ridge down by one common factor
        when the top ridges would otherwise rise above the plot area, so
        `overlap` is a maximum; the node's `ridgeline` note records the
        overlap drawn. With `fit=False` the ridges keep `overlap` and may
        rise above the area (the note's `above`, in mm).
        """
        from .ridgeline import ridgeline as _ridgeline

        clip = _clip_flag(style)
        node, _, _ = _ridgeline(self, groups, at=at, overlap=overlap,
                                bandwidth=bandwidth, samples=samples,
                                scale=scale, fit=fit, colors=color, **style)
        return self.draw(node, clip=clip)

    @renamed_keywords(colors="color")
    def raincloud(self, groups, *, at=None, orient: str = "h",
                  width: float = 0.9, bandwidth: float | None = None,
                  samples: int = 64, cut: float = 2.0, whisker: float = 1.5,
                  points: str | None = "jitter", size: float | str | None = None,
                  seed: int = 0, box: bool = True, color=None,
                  **style) -> "Panel":
        """A half violin, a narrow box and the observations, per group.

        `groups` is spelled as for `violin` and `swarm`: a mapping of
        position to samples, or a sequence taking its positions from the
        band scale. Each slot (`width` of the band step) is split into three
        lanes: the half violin stands on the category's centre line, the box
        sits just beside it, and the points fill the far half of the slot.
        With `orient="h"` (default; groups on y) the half violin rises up the
        page; with `orient="v"` it extends to the right.

            p = inklet.panel(50, 36, x=(0, 8), y=["treated", "control"])
            p.raincloud({"control": control, "treated": treated})

        The half violin uses the `violin` bandwidth rule, `bandwidth`,
        `samples` and `cut`. The box shows quartiles, the median and
        whiskers to the furthest observations within `whisker` interquartile
        ranges, without caps or separate outliers. `points="jitter"`
        (default) scatters the observations across their lane with a random
        generator seeded by `seed`, so the figure is the same on every run;
        `points="swarm"` packs them as `swarm` does; `None` leaves them out.
        `size` is the dot diameter in mm. `box=False` omits the box.

        `color=` sets one colour, or one per group: the points use it and the half
        violin a paler blend of it. The default is the ink for one group and
        the theme's ink palette for several. Other keywords style the points.
        """
        from .raincloud import raincloud as _raincloud

        clip = _clip_flag(style)
        node, _, _ = _raincloud(self, groups, at=at, orient=orient, width=width,
                                bandwidth=bandwidth, samples=samples, cut=cut,
                                whisker=whisker, points=points, size=size,
                                seed=seed, box=box, colors=color, **style)
        return self.draw(node, clip=clip)

    def label_points(self, points: Iterable[Sequence], labels: Sequence[str],
                     **kwargs) -> "Panel":
        """Label many data points at once, clear of the marks and each other.

        `points` are data coordinates and `labels` one string per point.
        Each label goes to the nearest free position around its point; a
        label that had to move further out gets a hairline leader back to
        the point. Placement waits for `build()`, so the labels avoid every
        mark in the panel's content and over layers, including marks drawn
        after this call. Several calls are placed in call order, each clear
        of the labels before it.

            p.scatter(cloud, color=TH.muted)
            p.label_points(hits, names)

        Keywords: `size` (type size, mm), `clear` (the smallest gap between a
        point and its label, mm), `reach` (how far out a label may go, mm),
        `leader=False` to never draw leaders, `markup`, `avoid=` (more
        diagrams to keep clear of), `leader_style=` and any text style such
        as `fill=`. The placement is deterministic. A label that could not be
        placed without overlap is still drawn at its best position and listed
        in the node's `point_labels` note under `unresolved`; the note is
        filled in when the panel is built. See `plot.point_labels`.
        """
        from .point_labels import PENDING_KIND, checked
        from .point_labels import label_points as _label_points

        data, names = checked(points, labels)
        theme = active_theme()

        def place(marks):
            import inklet
            token = inklet._theme_context.set(theme)
            try:
                return _label_points(self, data, names, marks=marks, **kwargs)
            finally:
                inklet._theme_context.reset(token)

        holder = Diagram(kind=PENDING_KIND)
        self._deferred[id(holder)] = place
        self._over.append(holder)
        return self._touched()

    def label_lines(self, names: Sequence[str] | None = None,
                    **kwargs) -> "Panel":
        """Name curves at the curves themselves instead of in a legend.

        Every `line`, `step` or `ecdf` drawn with `name=` (or those in
        `names`) gets its name in its own colour. `where="end"` (default)
        sets the names in a column just right of the curve ends, pushed
        apart when they would collide, with a hairline leader from a name
        moved off its end; `where="inside"` puts each name just above or
        below the last stretch of its own curve, chosen jointly so no name
        collides with another, is crossed by a curve or sits nearer a
        different curve.

            for g in groups:
                p.line(curves[g], name=g)
            p.label_lines()

        Keywords: `size`, `gap` (curve end to name, mm), `leader=False`,
        `color=False` (names in ink), `markup`, `leader_style=` and any text
        style. Placed at `build()`, like `label_points`; names that collide
        anyway are listed under `unresolved` in the `line_labels` note and
        reported by lint. See `plot.line_labels`.
        """
        from .line_labels import defer
        return defer(self, names, **kwargs)

    def _placed_over(self) -> list[Diagram]:
        """`_over` with each deferred `label_points` call placed.

        Calls are placed in order. Each sees the content layer and the over
        layer, with earlier calls already placed and later calls left out,
        so a call with nothing drawn after it places exactly as it would
        have at the time of the call.
        """
        if not self._deferred:
            return list(self._over)
        over = list(self._over)
        waiting = {n for n, node in enumerate(over) if id(node) in self._deferred}
        for n in sorted(waiting):
            holder = over[n]
            waiting.discard(n)
            marks = [*self._content,
                     *(node for m, node in enumerate(over) if m != n and m not in waiting)]
            node = self._deferred[id(holder)](marks)
            for key, value in holder.notes.items():
                node.notes.setdefault(key, value)
            # The holder carries the result's notes, so a caller holding
            # `_over` can read them once the panel is built.
            holder.notes.update(node.notes)
            over[n] = node
        return over

    @renamed_keywords(colors="color")
    def dendrogram(self, tree, *, labels: Sequence | None = None,
                   orient: str = "v", threshold: float | None = None,
                   color=None, **style) -> "Panel":
        """The merge tree of a hierarchical clustering, drawn as elbows.

        `tree` is a SciPy linkage matrix (rows `[a, b, distance, count]`) or
        a nested sequence of leaves such as `(("a", "b"), ("c", "d"))`.
        `labels` names the leaves of a linkage, one per original index. A
        nested tree has no distances: each merge is one unit above its
        tallest child.

        With `orient="v"` (default) the leaves run along x and merge heights
        on y; with `orient="h"` the leaves run along y and heights on x. The
        height axis must be continuous; reverse its domain to grow the tree
        the other way, for example `x=(height, 0)` to put the root on the
        left and the leaves on the right.

        On a continuous leaf axis the leaves are at 0, 1, ..., n-1. On a band
        leaf axis they are at the band positions, and the band's categories
        must be the leaf order, so a heatmap on the same band lines up with
        it; `inklet.plot.dendrogram_layout(tree, labels=...).leaves` gives
        that order. The first category is at the bottom of a y band.

            order = inklet.plot.dendrogram_layout(link, labels=genes).leaves
            tree = inklet.panel(12, 40, x=(3.2, 0), y=order)
            tree.dendrogram(link, labels=genes, orient="h")

        `threshold=` colours each subtree whose merges are all below that
        height in its own colour from the theme's ink palette (or `color=`)
        and draws the merges above it in the ink. Other keywords style the
        lines. The node carries a `dendrogram` note with the leaf order, the
        root height and the leaves of each coloured cluster.
        """
        from .dendrogram import dendrogram as _dendrogram

        clip = _clip_flag(style)
        node, _, _ = _dendrogram(self, tree, labels=labels, orient=orient,
                                 threshold=threshold, colors=color, **style)
        return self.draw(node, clip=clip)

    # -- clustered matrices (plot/cluster.py, plot/correlogram.py) -----------

    def clusters(self, groups: Sequence, *, color: str | None = None, highlight=None,
                 highlight_color: str | None = None, width: float | str | None = None,
                 labels: bool = False, size: float | str | None = None,
                 min_size: int = 1, **style) -> "Panel":
        """Boxes on the diagonal of a matrix, one per cluster.

        `groups` is one cluster label per matrix row, in the order the rows
        are drawn (top first), so each cluster is a run of equal labels;
        `inklet.plot.cut(link, k)` numbered in leaf order gives exactly that
        once the matrix is reordered by the dendrogram:

            link = inklet.plot.linkage(r, metric="precomputed")
            order = inklet.plot.dendrogram_layout(link).order
            groups = [inklet.plot.cut(link, 4)[i] for i in order]
            p.matrix([[r[i][j] for j in order] for i in order]).clusters(groups, highlight=2)

        Boxes span whole cells of an n x n matrix filling the plot area,
        drawn `width` mm thick (default the theme's thick stroke) in `color`
        (ink); `highlight=` clusters are drawn over the others in
        `highlight_color` (red). `labels=True` names each cluster outside
        the matrix on the right, level with its box. Runs shorter than `min_size` rows get no box,
        and a `None` label is never boxed. Other keywords style the boxes.
        The node carries a `clusters` note with each box's row span.
        """
        from .cluster import clusters as _clusters

        node, _ = _clusters(self, groups, color=color, highlight=highlight,
                            highlight_color=highlight_color, width=width, labels=labels,
                            size=size, min_size=min_size, **style)
        return self.over(node, clip=False)

    def correlogram(self, r, names: Sequence[str] | None = None, *,
                    triangle: str = "lower", shape: str = "circle", ramp=None,
                    values=False, labels: bool = True,
                    size: float | str | None = None, **style) -> "Panel":
        """A correlation matrix as a triangle of glyphs sized and coloured by r.

        `r` is a square matrix of correlations (`inklet.plot.correlation`
        computes one); `names` label its rows. Each glyph's area is
        proportional to |r| (a full cell less a margin at |r| = 1) and its
        colour is r on the diverging ramp from -1 (blue) to 1 (red), so
        `colorbar()` afterwards shows the fixed -1..1 scale.

            p = inklet.panel(40, 40)
            p.correlogram(inklet.plot.correlation(table), genes).colorbar(label="r")

        `triangle="lower"` (default) or `"upper"` draws each pair once and
        leaves out the diagonal; `"full"` draws everything. `shape` is
        "circle", "square" or "tile" (whole cells, the classic heatmap).
        `values=True` or a format such as `"{:.1f}"` writes r in each glyph.
        Names go outside the grid, left and below (above for "upper"),
        turned when they do not fit a column. Missing values (None or NaN)
        are left empty. The node carries a `correlogram` note.
        """
        from .correlogram import correlogram as _correlogram

        clip = _clip_flag(style)
        node, note = _correlogram(self, r, names, triangle=triangle, shape=shape,
                                  ramp=ramp, values=values, labels=labels, size=size,
                                  **style)
        self._ramp = note["ramp"]
        self._scale_domain = note["scale"]
        return self.draw(node, clip=clip)

    def ternary(self, points: Iterable[Sequence[float]], *, labels: Sequence[str] | None = None,
                ticks: int = 5, grid: bool = True, total: float = 100, format=None,
                color=None, size=None, marker: str = "circle", name: str | None = None,
                **style) -> "Panel":
        """Compositions of three parts as points in a triangle.

        `points` are `(a, b, c)` triples in any units; each is normalised to
        fractions of its sum. The first call draws the triangle, fitted into
        the plot area with component `labels[0]` at the top vertex,
        `labels[1]` bottom left and `labels[2]` bottom right, with `ticks`
        divisions whose inner gridlines are labelled as parts of `total`
        (100, so percentages; `format=` a function to write them) and a pale grid (`grid=False` to omit).
        Later calls on the same panel add points to the same triangle.

            p = inklet.panel(50, 45)
            p.ternary(soils, labels=("clay", "sand", "silt"), name="site 1")
            p.ternary(more, name="site 2").legend()

        The points are an ordinary `scatter`, so `color`, `size`, `marker`,
        `name` and other style keywords mean what they mean there (a
        sequence of colours or a ramp included). The triangle carries a
        `ternary` note with its vertices; `inklet.plot.ternary_frame` gives
        the geometry for drawing anything else in it.
        """
        from .ternary import ternary_frame

        if isinstance(self.x, Band) or isinstance(self.y, Band):
            raise DiagramError("ternary needs continuous x and y scales")
        if self._ternary is None:
            node, frame = ternary_frame(self, labels=labels or ("A", "B", "C"), ticks=ticks,
                                        grid=grid, total=total, format=format)
            self._ternary = frame
            self.under(node)
        elif labels is not None:
            raise DiagramError("this panel's ternary triangle is already drawn with its labels")
        frame = self._ternary
        at = [frame.point(*triple) for triple in points]
        data = [(self.x.invert(p.x), self.y.invert(p.y)) for p in at]
        return self.scatter(data, color=color, size=size, marker=marker, name=name,
                            clip=False, **style)

    # -- hierarchies (plot/hierarchy_plots.py) ------------------------------

    def treemap(self, data, *, colors=None, highlight=None,
                highlight_color: str | None = None,
                padding: float | str | None = None, header: bool | None = None,
                labels: bool = True, values=None, sort: bool = True,
                size: float | str | None = None, **style) -> "Panel":
        """A squarified treemap: each leaf a rectangle with area proportional
        to its value, filling the plot area.

        `data` is any input of `inklet.plot.hierarchy`: a nested mapping
        (`{"L5": {"ET": 40, "IT": 65}, "L6": 80}`), `(name, children)`
        tuples, or a `(name, parent[, value])` table. Nested groups are
        drawn as pale plates `padding` mm inside their parent (default about
        0.6 mm when the tree is more than one level deep) with the group's
        name in a header strip (`header=`). Siblings are laid out largest
        first unless `sort=False`.

        Colours follow the branch (child of the root): the theme's
        categorical palette, `colors=` a list per branch, a mapping of node
        name to colour (inherited by descendants) or one colour. `highlight=`
        names or paths get `highlight_color` (a red by default) and every
        other node a pale fill. Leaves are named in their top-left corner
        when the name fits (`labels=False` to omit); `values=True` or a
        format string such as `"{:.0f}"` adds the value on a second line.
        The panel's scales are not used. The node carries a `treemap` note
        with each cell's path and area in mm².
        """
        from .hierarchy_plots import treemap as _treemap

        clip = _clip_flag(style)
        node, _ = _treemap(self, data, colors=colors, highlight=highlight,
                           highlight_color=highlight_color, padding=padding,
                           header=header, labels=labels, values=values,
                           sort=sort, size=size, **style)
        return self.draw(node, clip=clip)

    def icicle(self, data, *, orient: str = "h", root: bool | None = None,
               gap: float | str | None = None, spacing: float | str | None = None,
               links: bool | None = None, colors=None, highlight=None,
               highlight_color: str | None = None, labels="fit",
               levels: bool = False, counts: bool = False, sort: bool = False,
               size: float | str | None = None, **style) -> "Panel":
        """An icicle (partition) chart: one band per level of a hierarchy,
        each node spanning its share of its parent.

        `data` is any input of `inklet.plot.hierarchy`. With `orient="h"`
        (default) the levels are columns from left to right and the nodes
        stack down each column; `"v"` puts the levels in rows from the top.
        The root is drawn as the first level when it has a name (`root=`
        overrides).

        `gap=` (mm) separates the levels and, by default, fills the gap with
        pale fans joining each node to its parent (`links=`); `spacing=` is
        the space between neighbouring nodes in a level, shrunk where a
        level has too many nodes to afford it. This is the "clustering
        levels" figure: with `highlight=` a set of node names or paths, those
        nodes are drawn in `highlight_color` and the rest pale,
        `labels="highlight"` names them beyond the last level with leader
        ticks, `levels=True` numbers the levels from 0 above them and
        `counts=True` writes the number of nodes per level beneath (the
        highlighted count above it, in the highlight colour).

        `labels="fit"` (default) writes a name inside every node where it
        fits; a list of names labels those nodes outside, like
        `"highlight"`; `False` writes none. Colours are as for `treemap`,
        blended towards paper one step per level. The node carries an
        `icicle` note with the node counts and highlighted counts per level
        and every node's span in mm.
        """
        from .hierarchy_plots import icicle as _icicle

        clip = _clip_flag(style)
        node, _ = _icicle(self, data, orient=orient, root=root, gap=gap,
                          spacing=spacing, links=links, colors=colors,
                          highlight=highlight, highlight_color=highlight_color,
                          labels=labels, levels=levels, counts=counts, sort=sort,
                          size=size, **style)
        return self.draw(node, clip=clip)

    def sunburst(self, data, *, inner: float = 0.3, start: float = -90.0,
                 colors=None, highlight=None, highlight_color: str | None = None,
                 labels: bool = True, center: str | None = None, sort: bool = False,
                 size: float | str | None = None, **style) -> "Panel":
        """A sunburst: an icicle chart bent into rings about the centre of
        the plot area, the first level innermost.

        `data` is any input of `inklet.plot.hierarchy`. The rings fill the
        largest circle in the area; `inner` is the radius of the central hole
        as a fraction of it, where `center=` (default: the root's name)
        is written. Angles run clockwise from `start` degrees (-90 is twelve
        o'clock), each node spanning its share of 360. A name is written in
        its segment only when its whole box fits inside. Colours and
        `highlight=` are as for `icicle`. The node carries a `sunburst` note
        with the radii and every node's angle.
        """
        from .hierarchy_plots import sunburst as _sunburst

        clip = _clip_flag(style)
        node, _ = _sunburst(self, data, inner=inner, start=start, colors=colors,
                            highlight=highlight, highlight_color=highlight_color,
                            labels=labels, center=center, sort=sort, size=size,
                            **style)
        return self.draw(node, clip=clip)

    # -- networks (plot/network.py, plot/chord.py) ---------------------------

    def network(self, nodes, edges, *, layout: str = "circular", order=None,
                sizes=None, top: float | None = None,
                diameter: float | str | None = None, floor: float | str | None = None,
                shape: str = "circle", shapes=None, groups=None, colors=None,
                color: str | None = None, labels="auto", size: float | str | None = None,
                weights=None, width: float | str | None = None,
                width_floor: float | str | None = None, edge_color: str | None = None,
                edge_colors=None, bend: float | None = None, arrows: bool = False,
                opacity: float = 0.85, gap: float | str | None = None,
                iterations: int = 300, **style) -> "Panel":
        """A weighted network: node area from a value, edge width from a
        weight, colours from categories, fitted into the plot area.

        `nodes` is a list of names, or a mapping of name to value. `edges`
        are `(source, target)`, `(source, target, weight)` or
        `(source, target, weight, category)` rows.

            p = inklet.panel(50, 50)
            p.network({"102": 36, "79": 12, "81": 9},
                      [("102", "79", 5e4, "dimorphic"), ("81", "102", 900, "isomorphic")],
                      shape="square", groups={"102": "enriched"}, arrows=True)
            p.width_key(title="synapses").legend(side="bottom")

        `layout="circular"` (default) puts the nodes on one ring, in input
        order or `order=`, starting at twelve o'clock, and bows every edge
        towards the centre by `bend` times its length (default 0.25).
        `"force"`, `"layered"` and `"tree"` take their positions from the
        solvers `inklet.graph` uses (`gap=` and `iterations=` pass through),
        stretched to fill the area, with straight edges unless `bend` is
        given. Two opposite directed edges bow to opposite sides.

        Node values (or `sizes=`, a mapping or one per node) set the area of
        each node: `top` is drawn `diameter` mm across (default: the largest
        value, 4 mm) and nothing is smaller than `floor` (1.2 mm). `shape` is
        "circle" or "square" (rounded), per node with `shapes=`. `groups=`
        maps nodes to categories coloured from the palette and named in
        `legend()`; `colors=` maps node or group names to colours, and
        `color` is the fill of ungrouped nodes. `labels="auto"` writes a name
        inside its node when it fits and outside (away from the centre)
        otherwise; "inside", "outside" or False force the choice.

        Edge widths are proportional to weight: the heaviest edge is `width`
        mm (default 1.6), and nothing is thinner than `width_floor` (a
        hairline); pass `weights=inklet.plot.width_scale(top, width)` to share
        a scale between panels. Edge categories are coloured from the palette
        (after the node groups) or by `edge_colors=` and named in `legend()`.
        Lighter edges are drawn first. `arrows=True` puts a head on each edge
        at its target. Other keywords style the edges. `width_key()` and
        `size_key()` explain the widths and areas actually used. The node
        carries a `network` note with positions, diameters and the number of
        edges drawn at the width floor.
        """
        from .network import network as _network
        from .series import SeriesKey

        clip = _clip_flag(style)
        node, note = _network(self, nodes, edges, layout=layout, order=order,
                              sizes=sizes, top=top, diameter=diameter, floor=floor,
                              shape=shape, shapes=shapes, groups=groups, colors=colors,
                              color=color, labels=labels, size=size, weights=weights,
                              width=width, width_floor=width_floor,
                              edge_color=edge_color, edge_colors=edge_colors, bend=bend,
                              arrows=arrows, opacity=opacity, gap=gap,
                              iterations=iterations, **style)
        self._widths = note["widths"]
        if note["sizes"] is not None:
            self._sizes = note["sizes"]
        for name, fill, kind in note["node_keys"]:
            self._keys.append(SeriesKey(name=name, forms=frozenset(("marker",)),
                                        color=fill, marker=kind))
        for name, ink in note["edge_keys"]:
            self._note(name, "line", color=ink, width=active_theme().thick)
        return self.draw(node, clip=clip)

    def width_key(self, source=None, *, side: str = "right", corner: str | None = None,
                  values: Sequence[float] | None = None, count: int = 3, format=None,
                  title: str | None = None, color: str | None = None,
                  length: float | str | None = None, pad: float | str | None = None,
                  plate: bool = False) -> "Panel":
        """Reference lines with their weights: the key to an edge-width
        encoding.

        Built from the `WidthScale` the last `network`, `chord` or
        `arc_diagram` call used, or `source=` (`inklet.plot.width_scale`).
        Placed like `size_key`: outside on `side`, or inside a `corner` of
        the plot area. `values`, `count` and `format` choose and write the
        reference weights, `length` is the line length in mm and `color`
        its ink.
        """
        from .network import width_key as _width_key

        scale = getattr(self, "_widths", None) if source is None else source
        if scale is None:
            raise DiagramError(
                "width_key() has no widths to explain: call network() first, or "
                "pass source= an inklet.plot.width_scale")
        node = as_drawn(_width_key(scale, values=values, count=count, format=format,
                                   title=title, color=color, length=length))
        theme = active_theme()
        gap = theme.gap("xs") if pad is None else mm(pad)
        if plate:
            node = _plated(node, theme, theme.gap("xs"))
        if corner is None:
            # Beside the plot area as well as the drawing: a ring of nodes
            # leaves the area's corners empty, and a key tucked into one
            # would straddle the frame.
            box = _union_box(self._under + self._content + self._over) or self.area
            box = Rect(min(box.x0, self.area.x0), min(box.y0, self.area.y0),
                       max(box.x1, self.area.x1), max(box.y1, self.area.y1))
            if side not in SIDES:
                raise ValueError(f"unknown side {side!r}; expected one of {', '.join(SIDES)}")
            placed = beside(node, box, side, gap, Vec2(0.0, 0.0))
        else:
            placed = _into_corner(node, self.area, corner, gap)
        self._over.append(placed)
        return self._touched()

    def chord(self, matrix, names: Sequence[str] | None = None, *, colors=None,
              gap: float = 2.0, start: float = -90.0, directed: bool = False,
              sort: bool = False, thickness: float | str | None = None,
              pad: float | str | None = None, labels: bool = True,
              opacity: float = 0.72, color_by: str = "source",
              size: float | str | None = None, **style) -> "Panel":
        """A chord diagram: groups as arcs around a ring, flows between them
        as ribbons through the middle, fitted into the plot area.

        `matrix[i][j]` is the flow from group i to group j (a list of rows
        or a 2-D array; zeros draw nothing).

            p = inklet.panel(50, 50)
            p.chord([[0, 5, 3], [5, 0, 2], [3, 2, 1]], ["V1", "LM", "AL"])

        Undirected (the default), a group's arc is its row sum and the ribbon
        between i and j is `matrix[i][j]` wide at i and `matrix[j][i]` wide
        at j. `directed=True` gives each group its row plus column sum,
        outgoing flows first, and points each ribbon at its target. `gap` is
        the angle between groups in degrees; `start` is where the first
        group begins (-90, twelve o'clock); `sort=True` orders each group's
        flows largest first. `colors` is one colour, a list, or a mapping of
        group name to colour (default: the palette); ribbons take the colour
        of their source (`color_by="source"`), target, or larger end, at
        `opacity`. `thickness` is the ring's radial width in mm, and group
        names go outside the ring, `pad` mm clear of it. Other keywords style
        the ribbons. The node carries a `chord` note with the group angles
        and values and the ring radius.
        """
        from .chord import chord as _chord

        clip = _clip_flag(style)
        node, _ = _chord(self, matrix, names, colors=colors, gap=gap, start=start,
                         directed=directed, sort=sort, thickness=thickness, pad=pad,
                         labels=labels, opacity=opacity, color_by=color_by, size=size,
                         **style)
        return self.draw(node, clip=clip)

    def arc_diagram(self, nodes, edges, *, sizes=None, top: float | None = None,
                    diameter: float | str | None = None, floor: float | str | None = None,
                    shape: str = "circle", shapes=None, groups=None, colors=None,
                    color: str | None = None, labels: bool = True,
                    rotate: float | None = None, weights=None,
                    width: float | str | None = None,
                    width_floor: float | str | None = None,
                    edge_color: str | None = None, edge_colors=None,
                    directed: bool = False, opacity: float = 0.8,
                    size: float | str | None = None, **style) -> "Panel":
        """An arc diagram: nodes in a row, each edge a half-ellipse arc
        above them whose width is the edge weight.

        `nodes` and `edges` read as in `network()` (names or a mapping of
        name to value; `(source, target[, weight[, category]])` rows), and
        node sizes, shapes, group colours, edge widths and edge categories
        are encoded the same way, so `size_key()`, `width_key()` and
        `legend()` work after it.

            p = inklet.panel(80, 30)
            p.arc_diagram(["a", "b", "c", "d"], [("a", "c", 4), ("b", "d", 1)])

        Nodes keep their input order, evenly spaced across the plot area,
        with names below them (turned by `rotate` degrees; by default 90
        when they would collide). Arcs are as tall as half their span, all
        scaled down together to fit. `directed=True` draws edges running
        right to left below the row instead, so direction reads as side.
        Lighter edges are drawn first; other keywords style the arcs. The
        node carries an `arc_diagram` note with the node x positions.
        """
        from .chord import arc_diagram as _arc_diagram
        from .series import SeriesKey

        clip = _clip_flag(style)
        node, note = _arc_diagram(self, nodes, edges, sizes=sizes, top=top,
                                  diameter=diameter, floor=floor, shape=shape,
                                  shapes=shapes, groups=groups, colors=colors,
                                  color=color, labels=labels, rotate=rotate,
                                  weights=weights, width=width, width_floor=width_floor,
                                  edge_color=edge_color, edge_colors=edge_colors,
                                  directed=directed, opacity=opacity, size=size, **style)
        self._widths = note["widths"]
        if note["sizes"] is not None:
            self._sizes = note["sizes"]
        for name, fill, kind in note["node_keys"]:
            self._keys.append(SeriesKey(name=name, forms=frozenset(("marker",)),
                                        color=fill, marker=kind))
        for name, ink in note["edge_keys"]:
            self._note(name, "line", color=ink, width=active_theme().thick)
        return self.draw(node, clip=clip)

    @renamed_keywords(colors="color", names="name")
    def volcano(self, fold: Sequence[float], p: Sequence[float], *,
                labels: Sequence[str] | None = None, top: int = 10,
                fold_threshold: float = 1.0, p_threshold: float = 0.05,
                color=None, name=None, size: float | None = None,
                thresholds: bool = True, label_options: dict | None = None,
                **style) -> "Panel":
        """A volcano plot: log2 fold change on x against -log10 p on y.

        `fold` are log2 fold changes and `p` the p-values, one per feature.
        Points with p below `p_threshold` and a fold change of at least
        `fold_threshold` in either direction are "up" or "down"; the rest
        are "ns" and drawn first, in a pale grey, so the significant points
        sit on top.

            p = inklet.panel(60, 50, x=(-5, 5), y=(0, 12))
            p.volcano(fold, pvalues, labels=genes, top=8)
            p.axes(x="log2 fold change", y="-log10 p")

        `thresholds=True` (default) draws dashed rules at `±fold_threshold`
        and at `-log10(p_threshold)`, under the points. With `labels=` (one
        string per feature), the `top` significant points with the smallest
        p-values are named with `label_points`, clear of the points and of
        each other; points outside the plot area are not labelled.
        `label_options=` passes keywords to `label_points`. A p-value of 0
        is drawn at the smallest positive p-value in the data.

        `color=` is a mapping with keys "up", "down" and "ns", or three
        colours in the order down, ns, up. The default is red for up and blue
        for down, from the Tol sunset diverging palette. `name=` (the same
        shapes) names the classes in `legend()`; a class with no name has no
        legend row. `size` is the dot diameter in mm; other keywords style
        the points. The last layer drawn carries a `volcano` note with the
        classes, the ranked significant indices, the labelled indices and the
        capped and skipped indices. `inklet.plot.volcano_points` does the
        same classification without drawing.
        """
        import math

        from ..themes.palettes import palette as _palette
        from .volcano import VOLCANO_CLASSES, volcano_points

        if isinstance(self.x, Band) or isinstance(self.y, Band):
            raise DiagramError("volcano needs continuous x and y scales")
        if top < 0:
            raise DiagramError(f"volcano top must be 0 or more, got {top!r}")
        result = volcano_points(fold, p, fold_threshold=fold_threshold,
                                p_threshold=p_threshold)
        theme = active_theme()
        sunset = _palette("tol-sunset").colors
        paint = {"down": sunset[1], "ns": mix(theme.muted, theme.paper, 0.55),
                 "up": sunset[9]}
        paint.update(_volcano_triple(color, "color"))
        named = _volcano_triple(name, "name")
        if thresholds:
            rule = {"stroke": theme.muted, "stroke_width": theme.hairline,
                    "stroke_dash": (1.0, 0.8)}
            if fold_threshold > 0:
                self.vline(-fold_threshold, **rule)
                self.vline(fold_threshold, **rule)
            else:
                self.vline(0, **rule)
            self.hline(-math.log10(p_threshold), **rule)
        dot = {} if size is None else {"size": size}
        for kind in VOLCANO_CLASSES:
            chosen = [pt for pt, c in zip(result["points"], result["classes"])
                      if c == kind]
            if chosen:
                self.scatter(chosen, color=paint[kind], name=named.get(kind),
                             **dot, **style)
        labelled: list[int] = []
        if labels is not None:
            labels = list(labels)
            if len(labels) != len(result["points"]):
                raise DiagramError(
                    f"volcano needs one label per point, got {len(labels)} labels "
                    f"for {len(result['points'])} points")
            # A point outside the plot area has nowhere to put its label.
            area = self.area
            inside = [i for i in result["ranked"]
                      if area.x0 - 1e-9 <= self.x.map(result["points"][i][0]) <= area.x1 + 1e-9
                      and area.y0 - 1e-9 <= self.y.map(result["points"][i][1]) <= area.y1 + 1e-9]
            labelled = inside[:top]
            if labelled:
                self.label_points([result["points"][i] for i in labelled],
                                  [labels[i] for i in labelled],
                                  **(label_options or {}))
        last = (self._over or self._content)[-1] if (self._over or self._content) else None
        note = {"classes": result["classes"], "ranked": result["ranked"],
                "labelled": labelled, "capped": result["capped"],
                "skipped": result["skipped"]}
        if last is not None:
            last.notes["volcano"] = note
        return self

    def ma(self, mean: Sequence[float], fold: Sequence[float],
           p: Sequence[float] | None = None, *, labels: Sequence[str] | None = None,
           top: int = 10, fold_threshold: float = 1.0, p_threshold: float = 0.05,
           colors=None, names=None, size: float | None = None, log: bool = True,
           zero: bool = True, **style) -> "Panel":
        """An MA plot: mean expression on x against log2 fold change on y.

        `mean` is each feature's mean expression (normalised counts), drawn
        as log2(mean + 1) unless `log=False` says it is already on the axis
        scale; `fold` are log2 fold changes and `p` the (adjusted) p-values.
        Points are classed exactly as `volcano` classes them -- "up" and
        "down" need p below `p_threshold` and |fold| of at least
        `fold_threshold` -- and without `p` by fold change alone. The "ns"
        points are pale grey and drawn first.

            p = inklet.panel(60, 45, x=(0, 16), y=(-6, 6))
            p.ma(base_mean, log2fc, padj, labels=genes, top=6)
            p.axes(x="log2 mean expression", y="log2 fold change")

        `zero=True` draws a hairline at a fold change of 0. `labels=` names
        the `top` significant points with the smallest p (or the largest
        |fold| without `p`) with `label_points`. `colors=` and `names=` take
        the same shapes as in `volcano`; `size` is the dot diameter (0.9 mm) and
        other keywords style the points. The last layer carries an `ma` note
        with the classes and labelled indices.
        """
        from .genomics import ma as _ma

        if isinstance(self.x, Band) or isinstance(self.y, Band):
            raise DiagramError("ma needs continuous x and y scales")
        note = _ma(self, mean, fold, p, labels=labels, top=top,
                   fold_threshold=fold_threshold, p_threshold=p_threshold, colors=colors,
                   names=names, size=size, log=log, zero=zero, **style)
        last = (self._over or self._content)[-1] if (self._over or self._content) else None
        if last is not None:
            last.notes["ma"] = note
        return self

    @renamed_keywords(sizes="size", colors="color")
    def dotplot(self, sizes: Sequence[Sequence[float]] | None = None, colors=None, *,
                x: Sequence | None = None, y: Sequence | None = None,
                top: float | None = None, diameter: float | str | None = None,
                ramp=None, scale: Scale | None = None,
                center: float | None = None, color=None,
                size: Sequence[Sequence[float]] | None = None,
                **style) -> "Panel":
        """A dot plot: a circle per cell, its area one value, its colour another.

        `size` (the first positional argument) is row-major like `matrix`:
        `size[r][c]` is drawn at the `r`th y category and the `c`th x
        category, both band scales (or `x=` and `y=` naming a position per
        column and row). A circle's area is proportional to its value; `top`
        is the value drawn at the full `diameter` (defaults: the largest
        value, and 0.9 of the smaller band step). `color` (the second
        positional argument) is either one colour for every circle (default:
        a grey) or values of the same shape, which colour each circle through
        the default matrix ramps, or `ramp=`, `scale=` and `center=` exactly
        as `matrix` takes them -- the same rule as `scatter(color=)`. A cell
        whose size or colour is missing (None or NaN) draws nothing, and so
        does a size of 0.

        The positional slots keep their 4.x names `sizes` and `colors`;
        passing those names as keywords is deprecated.

            p = inklet.panel(40, 30, x=genes, y=clusters)
            p.dotplot(fraction, mean_expression)
            p.axis("bottom", rotate=90).axis("left")
            p.colorbar(label="mean expression").size_key(title="fraction")

        On the same band categories as a `dendrogram`, the circles line up
        with its leaves. `size_key()` and `colorbar()` afterwards explain the
        circles from the very area scale and ramp used. Other keywords style
        the circles (default: an ink hairline outline). The node carries a
        `dotplot` note with the top value, the full diameter and the missing
        and empty cells.
        """
        from .dotplot import dotplot as _dotplot

        clip = _clip_flag(style)
        values = resolve_renamed("Panel.dotplot", "size", size, "sizes", sizes)
        if values is None:
            raise TypeError("Panel.dotplot() missing the size values")
        # A colour string paints every circle; anything else is data for a ramp.
        # 4.x callers could pass both, and the data won.
        shades, paint = colors, None
        if isinstance(color, str):
            paint = color
        elif color is not None:
            shades = resolve_renamed("Panel.dotplot", "color", color, "colors", colors)
        node, note = _dotplot(self, values, shades, x=x, y=y, top=top,
                              diameter=diameter, ramp=ramp, scale=scale,
                              center=center, color=paint, **style)
        self._sizes = note["sizes"]
        if note["ramp"] is not None:
            self._ramp = note["ramp"]
            self._scale_domain = note["scale"]
        return self.draw(node, clip=clip)

    def size_key(self, source=None, *, side: str = "right",
                 corner: str | None = None, values: Sequence[float] | None = None,
                 count: int = 3, format=None, title: str | None = None,
                 orient: str | None = None, pad: float | str | None = None,
                 plate: bool = False, **style) -> "Panel":
        """Reference circles with their values: the key to a size encoding.

        Built from the `AreaScale` the last `dotplot` used, or `source=` for
        a scatter sized by hand:

            sizes = inklet.plot.area_scale(500, 3)
            p.scatter(points, size=[sizes(v) for v in counts])
            p.size_key(sizes, title="cells")

        `side` and `corner` place it as `colorbar` places a bar: outside the
        panel, clear of the furniture already there, or inside a corner of
        the plot area (`plate=True` knocks out what it covers). `values`,
        `count` and `format` choose and write the reference values. `orient`
        is "v" (a column; default on the left and right) or "h" (a row;
        default on the top and bottom). Other keywords go to
        `inklet.plot.size_key`.
        """
        from .dotplot import size_key as _size_key

        sizes = self._sizes if source is None else source
        if sizes is None:
            raise DiagramError(
                "size_key() has no sizes to explain: call dotplot() first, or "
                "pass source= an inklet.plot.area_scale")
        if orient is None:
            orient = "h" if side in ("top", "bottom") and corner is None else "v"
        node = as_drawn(_size_key(sizes, values=values, count=count, format=format,
                                  title=title, orient=orient, **style))
        theme = active_theme()
        gap = theme.gap("s") if pad is None else mm(pad)
        if corner is None and pad is None:
            gap = theme.gap("xs")
        if plate:
            node = _plated(node, theme, theme.gap("xs"))
        if corner is None:
            placed = self._beside(node, side, gap)
        elif corner == "auto":
            from ..layout.clear_space import place_in_clear_space
            placed = place_in_clear_space(node, within=self.area,
                                          avoid=(*self._content, *self._over), pad=gap)
        else:
            placed = _into_corner(node, self.area, corner, gap)
        self._over.append(placed)
        return self._touched()

    @renamed_keywords(colors="color")
    def kaplan_meier(self, data, *, confidence: float = 0.95,
                     band: str | None = "log-log", shade: bool = True,
                     censors: bool = True, color=None,
                     pvalue: float | str | None = None,
                     pvalue_corner: str = "sw", **style) -> "Panel":
        """Kaplan-Meier survival curves, with censor ticks and confidence bands.

        `data` is a mapping of group name to `(durations, events)`, or one
        `(durations, events)` pair; `events` flags an observed event (truthy)
        or a censored subject (falsy), and may be None when every event was
        observed. A group may also be a `SurvivalEstimate` computed already.
        The names go to `legend()` and to `at_risk()`.

            p = inklet.panel(60, 40, x=(0, 36), y=(0, 1))
            p.kaplan_meier({"placebo": (t0, e0), "drug": (t1, e1)}, pvalue=0.004)
            p.axes(x="time / months", y="survival")
            p.at_risk()

        Each curve is a post step from 1 at time 0 to the last observed
        time, with a short vertical tick at every censoring time
        (`censors=False` leaves them out). `band` is the confidence band:
        `"log-log"` (default), `"linear"` or None, at `confidence`;
        `shade=False` computes it without drawing it. `color=` sets one
        colour, or one per group (default: the ink for one group, the theme
        palette for several). Other keywords style the curves.

        There is no significance test: `pvalue=` writes a p-value computed
        elsewhere, as "P = 0.004" with an italic P, in `pvalue_corner` of the
        plot area. `inklet.plot.kaplan_meier` returns the estimate without
        drawing. The last curve carries a `kaplan_meier` note with each
        group's name, median survival and number of subjects.
        """
        from .survival import (band_edges, censor_ticks, curve_points,
                               estimates, pvalue_text)

        if isinstance(self.x, Band) or isinstance(self.y, Band):
            raise DiagramError("kaplan_meier needs continuous x and y scales")
        clip = _clip_flag(style)
        groups = estimates(data, confidence=confidence, band=band)
        theme = active_theme()
        if color is None:
            inks = ((theme.ink,) if len(groups) == 1
                    else tuple(theme.color(i) for i in range(len(groups))))
        else:
            inks = _marks.series_colors(color, len(groups))
        tick = _CENSOR_TICK_OF_TYPE * theme.font_size
        drawn: list[Diagram] = []
        for (name, estimate), ink in zip(groups, inks):
            if shade and estimate.band is not None:
                xs, lo, hi = band_edges(estimate)
                if len(xs) >= 2:
                    self.band(xs, lo, hi, name=name, color=ink, clip=clip)
            self.step(curve_points(estimate), where="post", name=name,
                      **{"stroke": ink, **style, "clip": clip})
            drawn.append(self._content[-1])
            if censors and estimate.censored:
                width = style.get("stroke_width", theme.stroke)
                self.draw(*censor_ticks(self, estimate, tick, stroke=ink,
                                        stroke_width=width), clip=clip)
            self._survival.append((name, estimate, ink))
        if pvalue is not None:
            label = as_drawn(pvalue_text(pvalue, theme.font_size_small))
            self._over.append(_into_corner(label, self.area, pvalue_corner,
                                           theme.gap("s")))
        drawn[-1].notes["kaplan_meier"] = {
            "groups": [name for name, _ in groups],
            "medians": [estimate.median for _, estimate in groups],
            "subjects": [len(estimate.durations) for _, estimate in groups],
            "band": band, "confidence": confidence}
        return self._touched()

    def at_risk(self, *, ticks: Sequence | None = None, count: int = 5,
                title: str | None = "Number at risk",
                font_size: float | str | None = None,
                pad: float | str | None = None, **kwargs) -> "Panel":
        """The number-at-risk table under the x axis of a `kaplan_meier` plot.

        Call it after `axes()`: like an outside legend it goes below
        everything already built. One column per x tick, centred under it
        (the ticks the axis draws, or `ticks=` and `count=` as `axis` takes
        them), and one row per curve, named on the left and set in the
        curve's colour (darkened where needed so the numbers read). The
        number at a time is the subjects whose follow-up reaches it.
        `title` goes above the rows; None leaves it out. The node carries an
        `at_risk` note with the times and the counts.
        """
        from .survival import at_risk_table

        if not self._survival:
            raise DiagramError("at_risk() has no curves: call kaplan_meier() first")
        theme = active_theme()
        node, _ = at_risk_table(self, self._survival, ticks=ticks, count=count,
                                title=title, font_size=font_size,
                                readable=lambda c: _readable(c, theme.paper),
                                **kwargs)
        node = as_drawn(node)
        box = _union_box(self._under + self._content + self._over) or self.area
        gap = theme.gap("s") if pad is None else mm(pad)
        self._over.append(node.translated(0.0, box.y1 + gap - node.bbox.y0))
        return self._touched()
    @renamed_keywords(colors="color", names="name")
    def split_violin(self, first, second, *, at=None, orient: str = "v",
                     width: float = 0.8, bandwidth: float | None = None,
                     samples: int = 64, cut: float = 2.0, scale: str = "shared",
                     median: bool = True, quartiles: bool = False, color=None,
                     name: Sequence[str] | None = None, **style) -> "Panel":
        """Two conditions per category as the two halves of one violin.

        `first` and `second` are spelled as `violin` groups: mappings of
        category to samples, or sequences in the order of the band scale.
        The first condition is the left half (with `orient="h"`, the upper
        half) and the second the right (lower) half.

            p = inklet.panel(50, 36, x=["CA1", "CA3", "DG"], y=(0, 12))
            p.split_violin(control, treated, name=["control", "treated"],
                           quartiles=True)

        Each half is the `violin` kernel density, with the same bandwidth
        rule, `bandwidth`, `samples` and `cut`. `scale="shared"` (default)
        scales both halves of a category by the larger of their peaks, so
        their areas are equal; `scale="each"` gives each half the full
        width. `median=True` draws each half's median as a solid line and
        `quartiles=True` its quartiles as dashed lines, from the centre to
        the outline. A half with fewer than two values is left out and listed
        under `empty` in the node's `split_violin` note.

        `color=` gives the two fills; the default is two pale theme
        colours. `name=` (two names) adds both to `legend()`.
        """
        from .split_violin import split_violin as _split

        clip = _clip_flag(style)
        node, fills, _ = _split(self, first, second, at=at, orient=orient,
                                width=width, bandwidth=bandwidth, samples=samples,
                                cut=cut, scale=scale, median=median,
                                quartiles=quartiles, colors=color, **style)
        if name is not None:
            if isinstance(name, str) or len(name) != 2:
                raise DiagramError(f"split_violin name= takes two names, got {name!r}")
            self._note_series(list(name), list(fills))
        return self.draw(node, clip=clip)

    @renamed_keywords(colors="color", centre="center")
    def embedding(self, points: Iterable[Sequence], clusters: Sequence, *,
                  color=None, size=None, labels: bool = True,
                  center: str = "median", label_size: float | str | None = None,
                  arrows=None, shuffle: bool = True, seed: int = 0,
                  raster: bool = False, outline=None,
                  outline_core: float = 0.8, **style) -> "Panel":
        """A UMAP or t-SNE style scatter, coloured and named by cluster.

        `points` are `(x, y)` pairs and `clusters` one cluster name per
        point. The points are drawn with one `scatter` call (a packed marker
        batch from 256 points up, or a raster layer with `raster=True`), in a
        random order seeded by `seed` so no cluster hides another because it
        came later in the table; `shuffle=False` keeps the input order.

            p = inklet.panel(50, 50, x=(-8, 8), y=(-8, 8))
            p.embedding(umap, cell_types, arrows="UMAP", size=0.5)

        `labels=True` writes each cluster's name at its centre, on a paper
        halo. The centre is on the data: by default the member point nearest
        the cluster's median (`center="median"`), or `"medoid"` or `"mean"`;
        see `inklet.plot.cluster_centers`. A name that would overlap one
        already placed, or the points of another cluster, moves to the
        nearest free spot around its centre. It may cover its own cluster.
        Names that could not clear other clusters' points are listed under
        `covering` in the note.

        `outline="line"` (or `True`) draws a smooth outline round each
        cluster's core, thin and in the cluster's colour, over the points;
        `outline="fill"` draws the core as a light tint under them. The core
        is the densest `outline_core` share of the cluster's points (default
        0.8), found as a density threshold, so stray points do not enlarge
        it. Names keep off other clusters' outlines, and with `"fill"` off
        the edge of their own tint too, so a name wider than its core sits
        beside it. The note records the style, the core share and the rings.

        `arrows="UMAP"` draws two short arrows in the lower-left corner,
        labelled UMAP1 and UMAP2, instead of axes; a pair of names sets both
        labels. Do not also call `axes`.

        `color=` is a mapping of cluster to colour, or a sequence in cluster
        order (first seen, or ascending for numbers). The default is Paul
        Tol's muted, bright and vibrant colours. Each cluster is recorded
        for `legend()`. `size` is the dot diameter in mm; other keywords
        style the points. The last layer carries an `embedding` note with
        the clusters, colours, centres and label positions.
        """
        from .embedding import embedding as _embedding

        note = _embedding(self, points, clusters, colors=color, size=size,
                          labels=labels, centre=center, label_size=label_size,
                          arrows=arrows, shuffle=shuffle, seed=seed,
                          raster=raster, outline=outline,
                          outline_core=outline_core, **style)
        last = (self._over or self._content)[-1]
        last.notes["embedding"] = note
        return self

    def brackets(self, comparisons: Sequence, *, format="stars",
                 hide_ns: bool = False, stars=None, ns: str = "ns",
                 **kwargs) -> "Panel":
        """Significance brackets for many pairs of groups, stacked clear of
        each other.

        `comparisons` is a list of `(group_a, group_b, value)`, where value
        is a p-value or the text to write. The brackets are drawn with
        `bracket`, shortest span first. Each clears the data between its
        ends by `clear` and the brackets already drawn there by `clear` plus
        the tick length, so nested spans stack upward, ticks at a shared end
        never touch, and a short span sits just over its own data.

            p.brackets([("wt", "het", 0.21), ("wt", "ko", 3e-4),
                        ("het", "ko", 0.004)])

        `format="stars"` (default) writes `****`, `***`, `**`, `*` or `ns`
        for p below 0.0001, 0.001, 0.01, 0.05 and above; `format="p"` writes
        "P = 0.004" or "P < 0.001"; a function of p writes what it returns.
        `stars=` replaces the star bounds, as `(bound, text)` pairs from the
        most significant, and `ns` the text above them. `hide_ns=True` leaves
        out comparisons whose p is at or above the largest star bound (0.05)
        and those whose text is `ns`. No test is run here: the p-values
        are the author's. Other keywords go to `bracket` (`side`, `tick`,
        `clear`, `size`, ...). `inklet.plot.format_p` formats one p-value.
        """
        from .significance import STARS, comparisons_in_order, label_of, level

        side = kwargs.get("side", "n")
        clear = active_theme().gap("xs") if kwargs.get("clear") is None \
            else mm(kwargs["clear"])
        tick = mm(kwargs.get("tick", 1.0))
        options = {"stars": STARS if stars is None else tuple(stars), "ns": ns}
        drawn = []
        for a, b, value in comparisons_in_order(self, comparisons, side):
            text = label_of(value, format, **options)
            numeric = not isinstance(value, (str, Diagram))
            if hide_ns and (text == ns or (numeric and float(value) >= max(
                    bound for bound, _ in options["stars"]))):
                continue
            self.bracket(a, b, level(self, a, b, side, clear, tick), text=text,
                         **kwargs)
            drawn.append((a, b, text if isinstance(text, str) else None))
        if drawn:
            self._over[-1].notes["brackets"] = drawn
        return self

    # -- statistical plots: density, regression, probability, agreement ----
    #
    # Thin wrappers. The arithmetic and geometry live in plot/kernel_density.py,
    # density.py, regression.py, probability.py, agreement.py,
    # letter_values.py and strip.py.

    def kde(self, values, *, bandwidth="scott", adjust: float = 1.0,
            cut: float = 3.0, samples: int = 200, fill: bool = False,
            stat: str = "density", orient: str = "v", color=None,
            name: str | None = None, baseline: float = 0.0,
            **style) -> "Panel":
        """A kernel density curve, or one per group.

        `values` is one sample, or a mapping of group name to samples; each
        group gets its own curve, colour (the theme's ink palette, or
        `color=` one colour or a sequence) and legend entry. Values run
        along x and density up y; `orient="h"` swaps them.

            grid, density = inklet.plot.kde_curve(control)
            p = inklet.panel(50, 30, x=(0, 10), y=(0, 0.5))
            p.kde({"control": control, "treated": treated}, fill=True)

        `bandwidth` is `"scott"` (R's `bw.nrd`, the default), `"silverman"`
        (R's `bw.nrd0`) or a number in data units, times `adjust`. The curve
        runs `cut` bandwidths past the extreme values, stopping at the axis
        domain, in `samples` points. `fill=True` shades under each curve at
        25% opacity so overlapping groups stay visible. `stat="count"`
        multiplies each density by its sample size, so the areas compare
        group sizes. On a log value axis the density is estimated in
        ``log10`` units, so it is per decade and a log-normal sample is a
        symmetric bump. A single named curve takes the next series colour,
        so repeated calls stay apart. Other keywords style the lines. The
        node carries a
        `kde` note with each group's bandwidth and peak;
        `inklet.plot.kde_curve` computes a curve without drawing it.
        """
        from .kernel_density import kde_layer

        clip = _clip_flag(style)
        if color is None and not isinstance(values, Mapping):
            color = self._series_color(name, None)
        node, drawn, _ = kde_layer(self, values, bandwidth=bandwidth,
                                   adjust=adjust, cut=cut, samples=samples,
                                   fill=fill, stat=stat, orient=orient,
                                   color=color, baseline=baseline, **style)
        for group, ink in drawn:
            label = group if group is not None else name
            if fill:
                self._note(label, "area", color=ink,
                           fill=mix(ink, active_theme().paper, 0.75))
            self._note(label, "line", color=ink)
        return self.draw(node, clip=clip)

    def kde2d(self, points: Iterable[Sequence], *, levels=5, fill: bool = False,
              bandwidth="scott", adjust: float = 1.0, gridsize: int = 96,
              color=None, ramp=None, name: str | None = None,
              **style) -> "Panel":
        """Contours of a 2D kernel density: lines, or filled levels.

        Each contour encloses a share of the estimated probability mass:
        `levels=5` (default) draws five, holding 19%, 38%, 57%, 76% and 95%;
        a sequence such as `levels=(0.5, 0.95)` gives the shares directly.
        `fill=True` fills the regions between them, palest outside, from
        the density ramp or tints of `color=`; lines are `color` (default:
        the ink) or a colour per level, outermost first.

            p = inklet.panel(50, 50, x=(-3, 3), y=(-3, 3))
            p.scatter(points, size=0.5, color="#bbbbbb")
            p.kde2d(points, levels=(0.5, 0.8, 0.95))

        The density uses a Gaussian product kernel with `bandwidth` per axis
        (`"scott"`: ``sd * n ** (-1/6)``; a number or an `(x, y)` pair in
        data units), times `adjust`, estimated on a lattice of at least
        `gridsize` points a side. On a log axis it is estimated in log
        units. Contours are cut to the plot area unless `clip=False`. The
        node carries a `kde2d` note with the masses, their
        density thresholds and the bandwidth; `inklet.plot.kde2d` returns
        the lattice without drawing it.
        """
        from .kernel_density import kde2d_layer

        clip = _clip_flag(style)
        node, note = kde2d_layer(self, points, levels=levels, fill=fill,
                                 bandwidth=bandwidth, adjust=adjust,
                                 gridsize=gridsize, color=color, ramp=ramp,
                                 **style)
        if name is not None:
            ink = color if isinstance(color, str) else active_theme().ink
            self._note(name, "line", color=ink)
        return self.draw(node, clip=True if clip is None else clip)

    def hexbin(self, points: Iterable[Sequence], *, gridsize: int = 24,
               min_count: int = 1, ramp=None, scale: Scale | None = None,
               log: bool = False, **style) -> "Panel":
        """Points counted in hexagons, each coloured by its count.

        `gridsize` hexagons span the plot area's width; they are regular on
        the page whatever the axes, log axes included. Hexagons with fewer
        than `min_count` points are left empty. The colour runs through
        `ramp` (default: magma without its palest end, so a hexagon of one
        point still shows) over `scale`, by default 0 to the largest count,
        or a log scale from the smallest with `log=True`. `colorbar()`
        afterwards explains the colours:

            p.hexbin(points, gridsize=30).colorbar(label="points")

        Hexagons at the edge are cut to the plot area unless `clip=False`.
        The node carries a `hexbin` note with the hexagon diameter in mm and
        the largest count.
        """
        from .density import hexbin_layer

        clip = _clip_flag(style)
        node, ramp, scale, _ = hexbin_layer(self, points, gridsize=gridsize,
                                            min_count=min_count, ramp=ramp,
                                            scale=scale, log=log, **style)
        self._ramp, self._scale_domain = ramp, scale
        return self.draw(node, clip=True if clip is None else clip)

    def hist2d(self, points: Iterable[Sequence], bins=20, *, range=None,
               density: bool = False, min_count: float = 1, ramp=None,
               scale: Scale | None = None, log: bool = False,
               **style) -> "Panel":
        """A 2D histogram: points counted in rectangular bins on continuous
        axes, each bin coloured by its count.

        `bins` is a count or a list of edges, for both axes or as an
        `(x, y)` pair. A count gives round edges over the data or, with
        `range=((x0, x1), (y0, y1))`, even ones over that range; on a log
        axis the bins have equal ratios. Bins with fewer than `min_count`
        points are left empty. `density=True` colours by count per unit
        area over the total. `ramp`, `scale` and `log` choose the colours
        as for `hexbin`, and `colorbar()` explains them. Bins at the edge
        are cut to the plot area unless `clip=False`.
        `inklet.plot.histogram2d` returns the edges and counts.
        """
        from .density import hist2d_layer

        clip = _clip_flag(style)
        node, ramp, scale, _ = hist2d_layer(self, points, bins=bins, range=range,
                                            density=density, min_count=min_count,
                                            ramp=ramp, scale=scale, log=log,
                                            **style)
        self._ramp, self._scale_domain = ramp, scale
        return self.draw(node, clip=True if clip is None else clip)

    def density_scatter(self, points: Iterable[Sequence], *,
                        bandwidth: float | None = None, ramp=None,
                        size=None, sort: bool = True, raster: bool = False,
                        dpi: float = 300, marker: str = "circle",
                        **style) -> "Panel":
        """A scatter coloured by how crowded each point's neighbourhood is.

        The density is estimated on the page: points are smoothed with a
        Gaussian of `bandwidth` millimetres (default: a normal-reference
        rule on the page coordinates), so it works the same on log axes
        and shows where marks actually overlap. Colours run through `ramp`
        (default: magma without its palest end) from 0 to the densest
        point, and `sort=True` draws the densest points last so they are
        not buried. `raster=True` embeds the markers as one image, which
        keeps 100,000 points small; `colorbar(label="relative density")`
        explains the colours. Markers have no outline unless `stroke=` is
        given. `inklet.plot.point_density` returns the densities.
        """
        from .density import DENSITY_RAMP, point_density

        kept, density, h = point_density(self, points, bandwidth=bandwidth)
        order = (sorted(range(len(kept)), key=lambda k: (density[k], k))
                 if sort else list(range(len(kept))))
        style.setdefault("stroke", "none")
        self.scatter([kept[k] for k in order], color=[density[k] for k in order],
                     ramp=DENSITY_RAMP if ramp is None else ramp,
                     scale=linear((0.0, 1.0)), size=size, marker=marker,
                     raster=raster, dpi=dpi, **style)
        last = self._content[-1]
        last.notes["density_scatter"] = {"bandwidth_mm": h, "points": len(kept)}
        return self

    def regression(self, points: Iterable[Sequence], *, method: str = "linear",
                   confidence: float | None = 0.95, prediction: bool = False,
                   scatter: bool = True, frac: float = 2 / 3,
                   iterations: int = 3, span: tuple | None = None,
                   color: str | None = None, size=None, name: str | None = None,
                   **style) -> "Panel":
        """Points with a fitted line and its confidence band.

        `method="linear"` fits y on x by least squares and shades the
        `confidence` band for the mean response (Student's t on n - 2
        degrees of freedom); `prediction=True` shades the wider interval for
        a new observation instead, and `confidence=None` draws no band.
        The line spans the data's x range, or `span=(x0, x1)`. On a log x
        axis the fit is of y on ``log10(x)``, so the line is straight on
        the page and the slope is per decade.
        `method="lowess"` draws R's `lowess()` smoother with `frac` and
        `iterations`, without a band.

            p.regression(points, color="#24698c", name="wild type")

        The line and band are cut to the plot area unless `clip=False`.
        `scatter=False` leaves the points out. The points are a pale tint of
        `color` (default: the ink), `size` their diameter in mm; the line is
        `color` and the band a paler tint. Other keywords style the line.
        The line's node carries a `regression` note with the slope,
        intercept, r2, p-value and n; `inklet.plot.linear_fit` and
        `inklet.plot.lowess` compute them without drawing.
        """
        from .regression import regression_curve

        clip = _clip_flag(style)
        clip = True if clip is None else clip
        theme = active_theme()
        data = [tuple(p) for p in points]
        ink = self._series_color(name, color) or theme.ink
        curve = regression_curve(data, method=method, confidence=confidence,
                                 prediction=prediction, span=span, frac=frac,
                                 iterations=iterations,
                                 log_x=isinstance(self.x, Log))
        if scatter:
            from .strip import _dots
            dots = {"color": mix(ink, theme.paper, 0.45), "size": _dots(theme, size)}
            self.scatter([p for p in data if len(p) >= 2 and _mappable(self.x, p[0])
                          and _mappable(self.y, p[1])], **dots)
        if curve["band"] is not None:
            grid, lo, hi = curve["band"]
            self.band(grid, lo, hi, color=ink, name=name, clip=clip)
        line = {"stroke": ink, "stroke_width": theme.thick * 0.7, "clip": clip}
        line.update(style)
        self.line(curve["line"], name=name, **line)
        fit = curve["fit"]
        note = {"method": method, "confidence": confidence,
                "prediction": prediction}
        if fit is not None:
            note.update(slope=fit.slope, intercept=fit.intercept, r2=fit.r2,
                        p=fit.p, n=fit.n)
        self._content[-1].notes["regression"] = note
        return self

    def residuals(self, points: Iterable[Sequence], *, method: str = "linear",
                  frac: float = 2 / 3, iterations: int = 3,
                  smooth: bool = False, color: str | None = None, size=None,
                  name: str | None = None, **style) -> "Panel":
        """The residuals of a fit against x, with a zero line.

        The companion to `regression`: the same `method`, `frac` and
        `iterations` fit the points, and each point is drawn at
        `(x, y - fitted)`. Structure left in the residuals -- a curve, a
        funnel -- is what the fit missed. `smooth=True` adds a LOWESS line
        through the residuals to make a trend visible. Find the y domain
        first with `inklet.plot.linear_fit(points).residuals(points)`.
        Other keywords style the points.
        """
        from .regression import linear_fit, lowess

        theme = active_theme()
        data = [tuple(p) for p in points]
        if method == "linear":
            fitted = linear_fit(data).residuals(
                [p for p in data if p[0] is not None and p[1] is not None])
        elif method == "lowess":
            smooth_line = dict(lowess(data, frac=frac, iterations=iterations))
            fitted = [(float(p[0]), float(p[1]) - smooth_line[float(p[0])])
                      for p in data if p[0] is not None and p[1] is not None
                      and float(p[0]) in smooth_line]
        else:
            raise DiagramError(f'residuals method is "linear" or "lowess", not {method!r}')
        fitted = [p for p in fitted if math.isfinite(p[0]) and math.isfinite(p[1])]
        self.hline(0, stroke=theme.muted, stroke_width=theme.hairline,
                   stroke_dash=(1.0, 0.8))
        ink = self._series_color(name, color) or theme.ink
        from .strip import _dots
        dots = {"color": ink, "size": _dots(theme, size)}
        dots.update(style)
        self.scatter(fitted, name=name, **dots)
        self._content[-1].notes["residuals"] = {"method": method, "n": len(fitted)}
        if smooth and len(fitted) >= 3:
            self.line(lowess(fitted, frac=frac, iterations=iterations),
                      stroke=theme.accent, stroke_width=theme.stroke)
        return self

    def qq(self, values: Sequence[float], *, dist="normal",
           line: str | None = "quartiles", color: str | None = None,
           size=None, name: str | None = None, **style) -> "Panel":
        """A normal quantile-quantile plot: sample against theoretical
        quantiles, with a reference line.

        Each sorted value is drawn against the standard normal quantile at
        its plotting position (R's `ppoints`), so a normal sample lies on a
        straight line and heavy tails bend away from it at the ends.
        `dist=` takes a `statistics.NormalDist` or any quantile function
        instead. `line="quartiles"` (default) passes through the first and
        third quartiles, as R's `qqline` does; `"fit"` uses the sample mean
        and standard deviation, `"identity"` is ``y = x``, and `None` omits
        it. `inklet.plot.qq_points` returns the points without drawing.
        """
        from .probability import qq_line, qq_points

        theme = active_theme()
        pts = qq_points(values, dist)
        if line is not None:
            intercept, slope = qq_line(values, dist, line)
            xs = [pts[0][0], pts[-1][0]]
            domain = getattr(self.x, "domain", None)
            if domain is not None and not isinstance(self.x, Band):
                xs = [min(domain), max(domain)]
            self.line([(x, intercept + slope * x) for x in xs], stroke=theme.accent,
                      stroke_width=theme.stroke, clip=True)
        ink = self._series_color(name, color) or theme.ink
        from .strip import _dots
        dots = {"color": ink, "size": _dots(theme, size)}
        dots.update(style)
        self.scatter(pts, name=name, **dots)
        self._content[-1].notes["qq"] = {"line": line, "n": len(pts)}
        return self

    def pp(self, values: Sequence[float], *, dist="normal",
           color: str | None = None, size=None, name: str | None = None,
           **style) -> "Panel":
        """A probability-probability plot against a fitted normal.

        Each sorted value is drawn at (the normal CDF at that value, its
        empirical probability), with the diagonal ``y = x`` a perfect fit
        would follow. The normal takes the sample's mean and standard
        deviation unless `dist=` gives a `statistics.NormalDist` or any
        CDF. A PP plot is most sensitive in the middle of the distribution,
        a QQ plot in the tails. Draw it on `x=(0, 1), y=(0, 1)`.
        """
        from .probability import pp_points

        theme = active_theme()
        self.line([(0.0, 0.0), (1.0, 1.0)], stroke=theme.accent,
                  stroke_width=theme.stroke)
        pts = pp_points(values, dist)
        ink = self._series_color(name, color) or theme.ink
        from .strip import _dots
        dots = {"color": ink, "size": _dots(theme, size)}
        dots.update(style)
        self.scatter(pts, name=name, **dots)
        self._content[-1].notes["pp"] = {"n": len(pts)}
        return self

    def bland_altman(self, a: Sequence[float], b: Sequence[float], *,
                     z: float = 1.96, percent: bool = False,
                     confidence: float | None = None, labels: bool = True,
                     format: str = "{:.2f}", color: str | None = None,
                     size=None, name: str | None = None, **style) -> "Panel":
        """A Bland-Altman (mean-difference) plot of two methods' agreement.

        Each pair of measurements is drawn at (their mean, `a - b`) -- or
        the difference as a percentage of the mean with `percent=True` --
        with a solid line at the bias (the mean difference) and dashed lines
        at the limits of agreement, `bias ± z × sd`. `labels=True` names
        each line and its value just outside the plot area on the right,
        formatted with `format`, so the labels never sit on the data.
        `confidence=0.95` also shades the confidence interval of the bias
        and of each limit. Find the y domain first with
        `inklet.plot.bland_altman(a, b)`, which returns the same numbers;
        the points' node carries them as a `bland_altman` note.
        """
        from .agreement import bland_altman as _agreement
        from .strip import _dots

        theme = active_theme()
        result = _agreement(a, b, z=z, percent=percent, confidence=confidence)
        if confidence is not None:
            tint = mix(theme.ink, theme.paper, 0.9)
            for low, high in (result.lower_ci, result.bias_ci, result.upper_ci):
                self.hspan(low, high, fill=tint, stroke="none")
        self.hline(result.bias, stroke=theme.ink, stroke_width=theme.stroke)
        rule = {"stroke": theme.muted, "stroke_width": theme.stroke,
                "stroke_dash": (1.2, 0.8)}
        self.hline(result.upper, **rule)
        self.hline(result.lower, **rule)
        ink = self._series_color(name, color) or mix(theme.ink, theme.paper, 0.3)
        dots = {"color": ink, "size": _dots(theme, size)}
        dots.update(style)
        self.scatter(result.points, name=name, **dots)
        self._content[-1].notes["bland_altman"] = {
            "bias": result.bias, "sd": result.sd, "lower": result.lower,
            "upper": result.upper, "n": result.n, "bias_ci": result.bias_ci,
            "lower_ci": result.lower_ci, "upper_ci": result.upper_ci}
        if labels:
            from .agreement import margin_labels
            unit = "%" if percent else ""

            def format(value, spec=format):
                return spec.format(value).replace("-", "\u2212")
            words = [(result.upper, f"+{z:g} SD", format(result.upper) + unit),
                     (result.bias, "Mean", format(result.bias) + unit),
                     (result.lower, f"\u2212{z:g} SD", format(result.lower) + unit)]
            self.over(margin_labels(self, words), clip=False)
        return self

    def boxen(self, groups, *, at=None, width: float = 0.8, orient: str = "v",
              depth="tukey", outliers: bool = True, color=None, size=None,
              **style) -> "Panel":
        """Letter-value (boxen) plots: nested boxes out into the tails.

        For large samples, where a box plot's whiskers leave hundreds of
        ordinary tail values drawn as "outliers". The inner box spans the
        quartiles, the next the eighths (the middle 75%), then the
        sixteenths, and so on; each is narrower and paler than the one
        inside it, and the median is a paper-coloured line. `depth="tukey"`
        (default) draws ``floor(log2 n) - 3`` boxes, `"trustworthy"` as many
        as have non-overlapping 95% confidence intervals, or give a number.
        Values beyond the outermost box are drawn as dots when `outliers`.
        `groups` is spelled as for `boxplot`; `color=` is one colour or one
        per group. `inklet.plot.letter_values` returns the boxes.
        """
        from .letter_values import boxen_layer

        clip = _clip_flag(style)
        node, _ = boxen_layer(self, groups, at=at, width=width, orient=orient,
                              depth=depth, outliers=outliers, color=color,
                              size=size, **style)
        return self.draw(node, clip=clip)

    def strip(self, groups, *, at=None, width: float = 0.8, jitter: float = 0.5,
              orient: str = "v", size=None, seed: int = 0, color=None,
              marker: str = "circle", **style) -> "Panel":
        """A strip plot: each group's observations, jittered across its slot.

        The points spread uniformly over `jitter` of the slot (`width` of
        the band step), using a random generator seeded by `seed`, so the
        same call draws the same figure every time; `jitter=0` puts them on
        the centre line. `groups` is spelled as for `boxplot`, and a strip
        drawn after `boxplot(..., outliers=False)` shows the points over the
        summary. `size` is the dot diameter in mm; `color=` one colour or
        one per group (default: the ink, or the ink palette).
        """
        from .strip import strip_layer

        clip = _clip_flag(style)
        node, _ = strip_layer(self, groups, at=at, width=width, jitter=jitter,
                              orient=orient, size=size, seed=seed, color=color,
                              marker=marker, **style)
        return self.draw(node, clip=clip)

    def sina(self, groups, *, at=None, width: float = 0.8, orient: str = "v",
             bandwidth="scott", adjust: float = 1.0, size=None, seed: int = 0,
             color=None, marker: str = "circle", **style) -> "Panel":
        """A sina plot: points jittered within their group's density.

        Each point moves sideways by a seeded random share of the group's
        kernel density at its own value, scaled so the densest value spans
        the slot, so the points take the outline of a violin while every
        observation stays visible. `bandwidth` and `adjust` are as for
        `kde`; the other arguments as for `strip`.
        """
        from .strip import sina_layer

        clip = _clip_flag(style)
        node, _ = sina_layer(self, groups, at=at, width=width, orient=orient,
                             bandwidth=bandwidth, adjust=adjust, size=size,
                             seed=seed, color=color, marker=marker, **style)
        return self.draw(node, clip=clip)

    # -- categorical, composition, comparison and time plots ----------------
    #
    # Thin wrappers: the drawing lives in one module per plot family.

    def waterfall(self, at: Sequence, values: Sequence, *, totals=(),
                  baseline: float = 0.0, orient: str = "v", width: float = 0.6,
                  color=None, connectors: bool = True, labels=None,
                  names: Sequence[str] | None = None, **style) -> "Panel":
        """A waterfall chart: signed changes as bars floating on a running total.

        `values` are the changes, one per position in `at`. Each bar runs
        from the total before it to the total after it and is coloured by
        its direction. `totals` names the positions (values in `at`, or
        indices) that are totals instead: the bar stands on `baseline` at the
        running total. A total given None shows the running total; a total
        given a number resets the running total to that number.

            p.waterfall(["Start", "Sales", "Costs", "Tax", "End"],
                        [120, 45, -30, -12, None], totals=["Start", "End"])

        `color=` is one colour, three colours (increase, decrease, total) or
        a mapping with those keys; the default is Okabe-Ito bluish green for
        increases, vermillion for decreases and a grey for totals.
        `connectors=True` draws a dashed hairline from each bar's end to the
        next bar's start. `labels=True` writes each change (`+45`, `-30`) past
        the end it moved to, and each total's value; a format string or a
        callable writes something else. `names=` gives `legend()` one entry
        per kind, as (increase, decrease, total) names. `inklet.plot.waterfall_steps`
        returns the running totals without drawing, for choosing the y range.
        The node carries a `waterfall` note with every bar's start, end and kind.
        """
        from .waterfall import WATERFALL_KINDS, waterfall as _waterfall

        clip = _clip_flag(style)
        node, _, fills = _waterfall(self, at, values, totals=totals,
                                    baseline=baseline, orient=orient, width=width,
                                    color=color, connectors=connectors,
                                    labels=labels, **style)
        if names is not None:
            if len(names) != 3:
                raise DiagramError(
                    "waterfall names= is three names: (increase, decrease, total)")
            for kind, name in zip(WATERFALL_KINDS, names):
                if name is not None:
                    self._note(name, "area", fill=fills[kind], color=fills[kind])
        return self.draw(node, clip=clip)

    def slope(self, values: Mapping[str, Sequence[float]], *, at: Sequence | None = None,
              labels: str = "both", format=None, color=None, highlight=None,
              size: float | str | None = None, names: bool = True,
              **style) -> "Panel":
        """A slope chart: each series' values at a few time points, joined.

        `values` maps a series name to one value per time point. The time
        points are `at` (x positions), or the categories of a band x scale.
        Each series is a straight line with a dot per value; `labels="both"`
        writes the name and value at both ends (`"left"`, `"right"` or
        `"none"` for fewer), moved apart vertically just enough not to
        overlap. `format` writes the values (a format string such as
        `"{:.0f}%"` or a callable); `names=False` writes the values alone.

            p = inklet.panel(30, 40, x=["2015", "2025"], y=(0, 80))
            p.slope({"Denmark": [42, 61], "Spain": [30, 28]}, format="{:.0f}%")

        `highlight=` names the series to emphasise: they take the palette in
        order and every other series is drawn in light grey underneath.
        `color=` is one colour, one per series or a mapping by name. A slope
        chart usually has no y axis; the end labels carry the values.
        """
        from .slope import slope as _slope

        clip = _clip_flag(style)
        node, _ = _slope(self, values, at=at, labels=labels, format=format,
                         color=color, highlight=highlight, size=size,
                         names=names, **style)
        return self.draw(node, clip=clip)

    def bump(self, values: Mapping[str, Sequence[float]], *, at: Sequence | None = None,
             ranked: bool = False, labels: str = "both", color=None,
             highlight=None, size: float | str | None = None,
             numbers: bool = False, **style) -> "Panel":
        """A bump chart: the rank of each series at each time point.

        `values` maps a series name to one value per time point; each time
        point is ranked, 1 for the largest value (`inklet.plot.ranks`).
        Pass `ranked=True` when the values are ranks already. Ranks are
        joined by S-shaped curves with a dot at every rank, and the names are
        written at both ends (`labels=` as for `slope`). Make the y scale run
        from the last rank down to 1 so rank 1 is at the top:

            p = inklet.panel(50, 30, x=years, y=(len(teams) + 0.5, 0.5))
            p.bump(points_by_team, highlight=["Lyon"])

        `numbers=True` writes the rank inside each dot. `highlight=` and
        `color=` work as for `slope`. A missing value (None) breaks the line.
        The node carries a `bump` note with the ranks drawn.
        """
        from .slope import bump as _bump

        clip = _clip_flag(style)
        node, _, _ = _bump(self, values, at=at, ranked=ranked, labels=labels,
                           color=color, highlight=highlight, size=size,
                           numbers=numbers, **style)
        return self.draw(node, clip=clip)

    def stem(self, points: Iterable[Sequence], *, baseline: float = 0.0,
             orient: str = "v", color: str | None = None, marker: str = "circle",
             size: float | str | None = None, hollow: bool = False,
             rule: bool = True, name: str | None = None, **style) -> "Panel":
        """A stem plot: a stem from `baseline` to a dot at each `(x, y)`.

        For a sampled signal on a continuous scale -- an impulse response,
        a sequence, a line spectrum. `rule=True` draws the baseline across
        the plot area. `size` is the dot diameter in millimetres (0 for bare
        stems) and `hollow=True` draws rings. `orient="h"` swaps the axes:
        points are then `(value, position)`. Missing values (None, NaN) are
        skipped. Other stroke keywords style the stems.

            p.stem([(n, h[n]) for n in range(32)], color=TH.color(5))

        For one value per category use `lollipop`. `name=` adds a marker
        entry to `legend()`.
        """
        from .stem import stem as _stem

        clip = _clip_flag(style)
        color = self._series_color(name, color)
        if orient == "h":
            points = [(b, a) for a, b in points]
        node, ink = _stem(self, points, baseline=baseline, orient=orient,
                          color=color, marker=marker, size=size, hollow=hollow,
                          rule=rule, **style)
        self._note(name, "marker", color=ink, marker=marker)
        return self.draw(node, clip=clip)

    def likert(self, at: Sequence, counts: Sequence[Sequence[float]], *,
               neutral: int | None = None, normalize: bool = True,
               orient: str = "h", width: float = 0.7, color=None,
               names: Sequence[str] | None = None, labels=None,
               zero: bool = True, **style) -> "Panel":
        """Diverging stacked bars for Likert-scale responses, centred on neutral.

        `counts[r]` holds the count of each response level for the question
        at `at[r]`, ordered from the most negative level to the most
        positive. Each row is normalised to percentages (`normalize=False`
        keeps the counts) and placed so that the negative levels lie left of
        zero, the positive ones right, and the neutral level straddles zero.
        `neutral` is the neutral level's index (default: the middle of an
        odd number of levels; none for an even number).

            levels = ["Strongly disagree", "Disagree", "Neutral", "Agree",
                      "Strongly agree"]
            p = inklet.panel(60, 30, x=(-100, 100), y=questions)
            p.likert(questions, counts, names=levels)
            p.axis("bottom", format=inklet.plot.unsigned).legend(side="top")

        The default colours run from vermillion through a light grey neutral
        to blue (`inklet.plot.likert_colors`); `color=` sets one per level.
        `names=` gives `legend()` one entry per level. `labels=True` writes
        each segment's percentage inside it where it fits. `zero=True`
        draws the zero line. `inklet.plot.likert_spans` returns the segments
        without drawing; the node's `likert` note holds them too.
        """
        from .diverging import likert as _likert

        clip = _clip_flag(style)
        node, fills, _ = _likert(self, at, counts, neutral=neutral,
                                 normalize=normalize, orient=orient, width=width,
                                 color=color, labels=labels, zero=zero, **style)
        if names is not None:
            self._note_series(names, fills)
        return self.draw(node, clip=clip)

    def diverging_bars(self, at: Sequence, left, right, *, orient: str = "h",
                       width: float = 0.7, color=None,
                       names: Sequence[str] | None = None, reference=None,
                       titles: Sequence[str] | None = None, zero: bool = True,
                       **style) -> "Panel":
        """Two quantities per category, back to back: left of zero and right.

        `left` and `right` hold positive values, one per position in `at`:
        the left bar runs from zero towards negative x and the right bar
        towards positive x, so two groups (female and male, before and
        after, input and output) are compared on one category axis. Either
        side may be several series (series-major, as `bars` takes them),
        stacked outward from zero in order, with the same series on both
        sides sharing a colour:

            p = inklet.panel(50, 45, x=(-30, 60), y=types)
            p.diverging_bars(types, [f_specific, f_dimorphic],
                             [m_specific, m_dimorphic],
                             names=["sex-specific", "dimorphic"],
                             reference=(6.1, 8.4), titles=("♀", "♂"))
            p.axis("bottom", format=inklet.plot.unsigned, label="% output")

        `color=` is one colour per series; with a single series per side it
        is the pair (left, right). `names=` names the series (or the two
        sides) for `legend()`. `reference=` draws dashed reference lines at
        a value on each side -- one number for both, or a `(left, right)`
        pair, such as the means over all categories. `titles=` writes a
        heading above each side, next to the zero line. The axis shows
        negative numbers on the left unless formatted with
        `inklet.plot.unsigned`. `orient="v"` stands the bars up, with the
        left side below zero.
        """
        from .diverging import diverging_bars as _diverging

        clip = _clip_flag(style)
        node, left_fills, right_fills = _diverging(
            self, at, left, right, orient=orient, width=width, color=color,
            reference=reference, titles=titles, zero=zero, **style)
        if names is not None:
            fills = (left_fills + right_fills if left_fills != right_fills
                     else left_fills)
            self._note_series(names, fills)
        return self.draw(node, clip=clip)

    def pyramid(self, at: Sequence, left, right, *, titles: Sequence[str] | None = None,
                color=None, width: float = 0.92, **kwargs) -> "Panel":
        """A population pyramid: `diverging_bars` with touching bars.

        `at` is the age groups on a band y scale (the first at the bottom),
        `left` and `right` the counts or percentages of the two groups.
        `titles=("Female", "Male")` writes the group names over the two
        halves. Everything else passes to `diverging_bars`.

            ages = ["0-9", "10-19", "20-29", ...]
            p = inklet.panel(50, 40, x=(-8, 8), y=ages)
            p.pyramid(ages, female, male, titles=("Female", "Male"))
            p.axes(x="population / %", x_options={"format": inklet.plot.unsigned})
        """
        return self.diverging_bars(at, left, right, titles=titles, color=color,
                                   width=width, **kwargs)

    def waffle(self, values: Sequence[float], *, rows: int = 10, columns: int = 10,
               total: float | None = None, color=None,
               names: Sequence[str] | None = None, gap: float = 0.18,
               order: str = "column", **style) -> "Panel":
        """A waffle chart: shares of a whole as cells of a grid.

        Each value gets a whole number of the `rows` x `columns` cells in
        proportion to its share of the sum (or of `total`, which leaves the
        remaining cells empty and pale), rounded by the largest-remainder
        method so the counts add up. Cells are filled column by column from
        the bottom left (`order="row"` fills rows instead). The grid is
        centred in the plot area with square cells, whatever the scales;
        `gap` is the air between cells as a fraction of a cell.

            p = inklet.panel(30, 30)
            p.waffle([46, 31, 15, 8], names=["neurons", "glia", "vascular", "other"])
            p.legend(side="right")

        `names=` gives `legend()` one entry per value. The node carries a
        `waffle` note with the cell counts; `inklet.plot.waffle_cells`
        computes them without drawing.
        """
        from .waffle import waffle as _waffle

        clip = _clip_flag(style)
        node, fills, _ = _waffle(self, values, rows=rows, columns=columns,
                                 total=total, color=color, gap=gap, order=order,
                                 **style)
        if names is not None:
            self._note_series(names, fills)
        return self.draw(node, clip=clip)

    def mosaic(self, at: Sequence, values, *, color=None,
               names: Sequence[str] | None = None, gap: float | str = 0.6,
               labels=None, categories: bool = True, **style) -> "Panel":
        """A mosaic (Marimekko) chart: stacked bars as wide as their totals.

        `values` is series-major, like `bars`: `values[s][c]` is series `s`
        in category `at[c]`. Each category is a column whose width is its
        share of the grand total, split from the bottom up into each series'
        share of the column, so every cell's area is its value. Columns run
        across the panel's x domain and cells up its y domain:

            p = inklet.panel(60, 40, x=(0, 100), y=(0, 100))
            p.mosaic(regions, [[30, 12, 8], [20, 30, 10]], names=["A", "B"])
            p.axis("left", format="%").legend(side="right")

        `gap` is the space between columns in millimetres. `labels=True`
        writes each cell's share of its column where it fits (or a format
        string or callable of the share). `categories=True` writes the
        category names under the columns as a bottom axis. `names=` names
        the series for `legend()`. `inklet.plot.mosaic_layout` returns the
        geometry without drawing.
        """
        from .mosaic import mosaic as _mosaic

        clip = _clip_flag(style)
        node, fills, columns = _mosaic(self, at, values, color=color, gap=gap,
                                       labels=labels, **style)
        if names is not None:
            self._note_series(names, fills)
        self.draw(node, clip=clip)
        if categories:
            lo, hi = self.x.domain[0], self.x.domain[-1]
            centres = [lo + (hi - lo) * c.centre for c in columns if c.total > 0]
            named = [c.category for c in columns if c.total > 0]

            def written(value, _c=centres, _n=named):
                return str(_n[min(range(len(_c)), key=lambda i: abs(_c[i] - value))])

            self.axis("bottom", ticks=centres, format=written, thin=False,
                      spine=False, tick_size=0, markup=False)
        return self

    def streamgraph(self, x: Sequence, values, *, offset: str = "wiggle",
                    order: str = "input", color=None,
                    names: Sequence[str] | None = None, smooth: float = 0.5,
                    **style) -> "Panel":
        """A streamgraph: stacked areas around a moving baseline.

        `values` is series-major with one value (0 or more) per `x`.
        `offset` places the stack: `"wiggle"` (default) minimises the
        layers' change in slope, `"silhouette"` centres the stack on zero,
        `"zero"` stacks from zero like `stackarea` and `"expand"` scales every
        x to a total of 1. `order="inside-out"` puts the series that peak
        earliest in the middle. `smooth` is the curve tension (0 draws
        straight segments between samples). Layers are separated by a paper
        hairline.

            layers = inklet.plot.stream_layers(counts, offset="wiggle")
            low = min(min(lo) for lo, _ in layers)
            high = max(max(hi) for _, hi in layers)
            p = inklet.panel(80, 30, x=(0, 52), y=(low, high))
            p.streamgraph(weeks, counts, names=genres).legend(side="right")

        Use the same `offset` and `order` for `stream_layers` and the plot.
        The y axis of a wiggle or silhouette stream has no meaningful zero;
        label thickness with a scale bar or leave the axis out. `names=`
        names the series for `legend()`.
        """
        from .stream import streamgraph as _streamgraph

        clip = _clip_flag(style)
        node, fills, _ = _streamgraph(self, x, values, offset=offset, order=order,
                                      color=color, smooth=smooth, **style)
        if names is not None:
            self._note_series(names, fills)
        return self.draw(node, clip=clip)

    def parallel(self, rows, *, dimensions: Sequence | None = None, ranges=None,
                 color=None, groups: Sequence | None = None, count: int = 4,
                 format=None, labels: bool = True, **style) -> "Panel":
        """Parallel coordinates: an axis per variable and a line per record.

        The variables are the categories of a band x scale (or `dimensions=`
        naming positions on x); each `rows` record has one value per
        variable, as a sequence or a mapping in variable order. Every
        variable gets its own vertical axis over the full plot height, with
        round ticks over `ranges` (default: the data's extent widened to
        round numbers; a mapping by variable sets some of them, and a
        reversed pair flips an axis). Records are polylines; a missing value
        (None) breaks the line.

            dims = ["length", "width", "depth", "mass"]
            p = inklet.panel(70, 35, x=dims)
            p.parallel(records, groups=species)
            p.legend(side="right")

        `groups=` colours records by group, with one `legend()` entry per
        group; `color=` is one colour, one per record, or with `groups` one
        per group. `count` and `format` shape the ticks (`format` may be one
        per axis). `labels=True` writes the variable names under the axes,
        so the panel needs no bottom axis. The node carries a `parallel`
        note with the ranges used.
        """
        from .parallel import parallel as _parallel

        clip = _clip_flag(style)
        node, palette = _parallel(self, rows, dimensions=dimensions, ranges=ranges,
                                  color=color, groups=groups, count=count,
                                  format=format, labels=labels, **style)
        for group, ink in palette.items():
            self._note(str(group), "line", color=ink)
        return self.draw(node, clip=clip)

    def bullet(self, at: Sequence, values: Sequence[float], *, targets=None,
               ranges=None, baseline: float = 0.0, orient: str = "h",
               width: float = 0.7, color: str | None = None, **style) -> "Panel":
        """Bullet charts: a measure bar against a target and qualitative ranges.

        One row per position in `at`. `values` are the measures, drawn as a
        narrow bar from `baseline`; `targets` (one number or one per row)
        are short thick rules across it; `ranges` are the upper bounds of
        the qualitative bands behind it, in grey, darkest for the lowest --
        one list shared by every row or one list per row.

            p = inklet.panel(60, 18, x=(0, 300), y=["Revenue", "Profit"])
            p.bullet(["Revenue", "Profit"], [270, 22], targets=[250, 26],
                     ranges=[[150, 225, 300], [20, 25, 30]])

        Rows with different units belong on panels of their own. `color=`
        colours the measure and the target (default: the ink).
        """
        from .bullet import bullet as _bullet

        clip = _clip_flag(style)
        return self.draw(_bullet(self, at, values, targets=targets, ranges=ranges,
                                 baseline=baseline, orient=orient, width=width,
                                 color=color, **style), clip=clip)

    def gantt(self, tasks: Sequence[Sequence], *, groups: Sequence | None = None,
              color=None, width: float = 0.6, labels: bool = False,
              **style) -> "Panel":
        """A Gantt chart: a bar per task from its start to its end.

        Each task is `(row, start, end)` or `(row, start, end, text)`: `row`
        is a category of the band y scale (several tasks may share one) and
        `start` and `end` are values of the x scale -- dates, datetimes or
        ISO strings on a date axis, numbers on a linear one. A task that
        ends where it starts is a milestone, drawn as a diamond.

            p = inklet.panel(80, 30, x=("2025-01-01", "2025-07-01"), y=rows)
            p.gantt([("Design", "2025-01-06", "2025-02-14"),
                     ("Build", "2025-02-10", "2025-05-02"),
                     ("Review", "2025-05-05", "2025-05-05")])
            p.axes()

        `groups=` gives each task a group; tasks are coloured by group and
        `legend()` gets one entry per group. `color=` is one colour, one per
        task, or with `groups` one per group or a mapping. `labels=True`
        writes each task's `text` inside its bar when it fits and after the
        bar when it does not. List the rows of the y scale in reverse to read
        the first task at the top.
        """
        from .gantt import gantt as _gantt

        clip = _clip_flag(style)
        node, palette = _gantt(self, tasks, groups=groups, color=color,
                               width=width, labels=labels, **style)
        for group, fill in palette.items():
            self._note(str(group), "area", fill=fill, color=fill)
        return self.draw(node, clip=clip)

    def timeline(self, events: Sequence[Sequence], *, at: float | None = None,
                 color: str | None = None, size: float | str | None = None,
                 levels: Sequence[int] | None = None, line: bool = True,
                 **style) -> "Panel":
        """An event timeline: labelled stems off a base line.

        Each event is `(when, label)`, with `when` a value of the x scale
        (a date on a date axis). Stems alternate above and below the base
        line and step outward only as far as needed to keep neighbouring
        labels apart; `levels=` sets them instead (+1, +2, ... above; -1,
        -2, ... below). The base line runs through the middle of the plot
        area, or at the y value `at`. The y scale is otherwise unused, so
        size the panel's height for the levels the events need.

            p = inklet.panel(90, 30, x=("2020-01-01", "2025-01-01"))
            p.timeline([("2020-03-11", "pandemic declared"),
                        ("2020-12-08", "first vaccine"), ...])
            p.axis("bottom")

        `line=False` leaves out the base line, for an axis drawn through it
        with `p.axis("bottom", at=...)`. The node's `timeline` note records
        the levels used.
        """
        from .gantt import timeline as _timeline

        clip = _clip_flag(style)
        node, _ = _timeline(self, events, at=at, color=color, size=size,
                            levels=levels, line=line, **style)
        return self.draw(node, clip=clip)

    def calendar(self, values: Mapping, *, start=None, end=None, ramp=None,
                 scale: Scale | None = None, center: float | None = None,
                 week_start: str | int = "monday", gap: float | str = 0.25,
                 labels: bool = True, **style) -> "Panel":
        """A calendar heatmap: a square per day, a column per week.

        `values` maps days (dates, datetimes or ISO strings) to numbers.
        The calendar runs from `start` to `end` (default: the first and last
        day given), with one row per weekday starting at `week_start` and
        one column per week. Days in the range without a value are pale;
        the colour of the others comes from the matrix ramps, or `ramp=`,
        `scale=` and `center=` as `matrix` takes them, so `colorbar()`
        explains it afterwards.

            weeks = inklet.plot.calendar_weeks("2025-01-01", "2025-12-31")
            p = inklet.panel(weeks * 2.2, 7 * 2.2)
            p.calendar(steps_per_day, start="2025-01-01", end="2025-12-31")
            p.colorbar(side="bottom", label="steps")

        The grid fills the plot area from its top-left corner with square
        cells; `gap` is the space between cells in millimetres. `labels=True`
        writes the month names above and every other weekday at the left.
        """
        from .calendar import calendar as _calendar

        clip = _clip_flag(style)
        node, note = _calendar(self, values, start=start, end=end, ramp=ramp,
                               scale=scale, center=center, week_start=week_start,
                               gap=gap, labels=labels, **style)
        self._ramp = note["ramp"]
        self._scale_domain = note["scale"]
        return self.draw(node, clip=clip)

    def barplot(self, at: Sequence, data, *, estimator: str = "mean",
                error="sem", points: bool = True, width: float = 0.8,
                gap: float = 0.12, orient: str = "v", color=None,
                names: Sequence[str] | None = None,
                size: float | str | None = None, cap: float | str | None = None,
                baseline: float = 0.0, **style) -> "Panel":
        """Bars of the mean with error bars and every observation as a dot.

        `data` holds one sample (a list of observations) per position in
        `at`; for grouped bars, a list of such series, dodged within each
        category like `bars(grouped=True)`:

            p = inklet.panel(40, 35, x=["ctrl", "drug"], y=(0, 12))
            p.barplot(["ctrl", "drug"], [[wt_ctrl, wt_drug], [ko_ctrl, ko_drug]],
                      names=["WT", "KO"])
            p.axes(y="response").legend(side="top")

        Each bar is the `estimator` ("mean" or "median") of its sample. The
        error bar is `error`: "sem" (default), "sd", "ci95" (1.96 standard
        errors, a normal approximation), "iqr", None, or a function of the
        sample returning a half-width or `(down, up)`. With `points=True`
        each observation is a dot swarmed inside its bar at its exact
        value. `size` is the dot diameter and `cap` the error-bar cap's half
        width, both in millimetres.

        One series is drawn as light grey bars with ink dots; several take
        blue, vermillion, green, ... as dark dots on tinted bars. `color=`
        is one colour per series, or for a single series one per category.
        `names=` names the series for `legend()`. The node's `barplot` note
        holds each bar's `(centre, down, up, n)`;
        `inklet.plot.summary_stats` computes one without drawing.
        """
        from .barplot import barplot as _barplot

        clip = _clip_flag(style)
        node, inks, _ = _barplot(self, at, data, estimator=estimator, error=error,
                                 points=points, width=width, gap=gap,
                                 orient=orient, color=color, size=size, cap=cap,
                                 baseline=baseline, **style)
        if names is not None:
            from ..themes.color import mix as _mix
            theme = active_theme()
            if len(names) != len(inks):
                raise DiagramError(f"names= has {len(names)} names for {len(inks)} series")
            for name, ink in zip(names, inks):
                self._note(name, "area", fill=_mix(ink, theme.paper, 0.55), color=ink)
        return self.draw(node, clip=clip)


def _volcano_triple(given, what: str) -> dict:
    """`colors=` or `names=` of `Panel.volcano` as a mapping by class."""
    if given is None:
        return {}
    if isinstance(given, Mapping):
        unknown = set(given) - {"up", "down", "ns"}
        if unknown:
            raise DiagramError(
                f'volcano {what} keys are "up", "down" and "ns", not {sorted(unknown)}')
        return dict(given)
    if isinstance(given, str) or len(given) != 3:
        raise DiagramError(
            f"volcano {what} is a mapping or three values (down, ns, up), got {given!r}")
    return dict(zip(("down", "ns", "up"), given))


def _mappable(scale, value) -> bool:
    """False for a value a log scale cannot place (zero or negative)."""
    if isinstance(scale, Log):
        return value > 0
    return True


def panel(width: float | str, height: float | str, *, x=None, y=None,
          nice: bool = False, clip: bool = False) -> Panel:
    """A plot area of a fixed size, with scales fitted to it.

    `x` and `y` are scales, or the shorthands a scale would be built from: a
    `(low, high)` pair of numbers becomes a linear scale, and any other
    sequence becomes a band scale over those categories.

    `nice=True` rounds a continuous domain out to whole ticks, so the ends of
    the axis are themselves labelled -- `(0, 9.4)` becomes `(0, 10)`. It is off
    by default because it moves the data on the page, and a panel whose limits
    were chosen to match the one beside it must keep them.

    `clip=True` cuts every data mark to the plot area, which is what every
    plotting library the reader has used does. It is **off** by default here,
    and that is a considered choice: data drawn outside the domain is data the
    domain is wrong for, and painting it over the tick labels is a visible
    fault that `inklet.lint` reports, where a silent truncation is a picture that
    lies about its own extent. Turn it on when the overspill is the point --
    a fitted curve deliberately run past its data, a band whose lower edge is
    below the axis -- and the linter then sees the *clipped* extent, because
    `inklet.clip` cuts the geometry rather than emitting a `clipPath`.

    Any drawing call may override the panel with `clip=True` or `clip=False`;
    writing on the plot -- `text`, `arrow`, `annotate`, `bracket` -- is never
    clipped, because half a word is not a shorter word.
    """
    w, h = mm(width), mm(height)
    if w <= 0 or h <= 0:
        raise ValueError(f"a panel needs a positive size, got {w} x {h}")
    return Panel(
        width=w, height=h, clip=clip,
        x=_fit(x, -w / 2, w / 2, nice),
        # Data grows upward: the top of the area is -height/2 because y grows
        # downward everywhere else in inklet, and this is the one line that knows.
        y=_fit(y, h / 2, -h / 2, nice),
    )


def _fit(spec, lo: float, hi: float, nice: bool = False) -> Scale:
    if spec is None:
        return linear((0.0, 1.0), (lo, hi))
    if isinstance(spec, Scale):
        scale = spec.with_range(lo, hi)
    else:
        values = tuple(spec)
        if len(values) == 2 and all(isinstance(v, (int, float)) for v in values):
            scale = Linear((float(values[0]), float(values[1])), (lo, hi))
        elif len(values) == 2 and all(is_time_like(v) for v in values):
            # Two instants are a time domain and not two categories. A pair of
            # bare numbers deliberately is not: `(0, 10)` is a linear domain,
            # and reading it as 1970 would be an expensive kindness.
            scale = dates(values, (lo, hi))
        else:
            return Band(values, (lo, hi))
    # Only a scale that can say what round bounds mean gets rounded; a band
    # scale has no bounds and a log one's are already powers.
    return scale.nice() if nice and hasattr(scale, "nice") else scale


def _tinted(color: str | None, kwargs: dict) -> dict:
    """Give a twin's axis its series colour, unless the caller set one.

    Both channels, because an axis is a stroked spine and set numbers, and the
    renderer colours glyphs from `text_fill` alone -- but not the *same* value
    in both. A spine is a graphical object and clears WCAG at 3:1; type needs
    4.5:1, and half of any CVD-safe palette is nowhere near it. Okabe-Ito's
    orange is 2.25:1 on white, so a twin axis labelled in it is a colour
    swatch rather than a number. `readable` walks its lightness until the
    words can be read while holding the hue, so the axis still says which
    curve it belongs to.
    """
    if color is not None:
        theme = active_theme()
        kwargs.setdefault("stroke", color)
        kwargs.setdefault("text_fill", _readable(color, theme.paper))
    return kwargs


def _readable(color: str, on: str, min_ratio: float = 4.5) -> str:
    """`themes.readable`, if this build of inklet has it."""
    try:
        from ..themes import readable
    except ImportError:                                  # pragma: no cover
        return color
    return readable(color, on, min_ratio)


# -- composing panels -----------------------------------------------------


def row(panels: Iterable[Panel | Diagram], gap: float | str | None = None,
        align: str = "center") -> Diagram:
    """Panels side by side, their plot areas on one line.

    Stacking panels by their bounding boxes would align the *furniture* -- so
    one panel's y labels being wider than another's would shove its area out of
    line with its neighbour, which is exactly the misalignment that makes a
    multi-panel figure look homemade. So it is the plot *areas* that are lined
    up, and `align` says which of their edges:

        inklet.row([a, b, c])                  # area centres on one line
        inklet.row([a, b, column([d, e])], align="top")

    "center" (the default, "centre" too) is right for panels of equal area
    height and wrong the moment one member is taller than the rest: a `column`
    of two panels 44.1mm tall beside neighbours 34.0mm tall is centred, which
    lifts it (44.1 - 34.0) / 2 = 5.1mm up the page and hangs its panel letter
    five millimetres clear of its neighbours' -- the one misalignment a reader
    of a multi-panel figure sees instantly. `align="top"` puts the areas' top
    edges on one line instead, which is what a row of unequal panels wants,
    and leaves the ragged edge at the bottom where the reader is not comparing
    anything. `"bottom"` for the mirror case, a row read off a shared x axis.

    A member that declares no plot area is aligned on its bounding box, the
    same fallback `align="center"` has always taken.
    """
    return _lay_out(panels, gap, horizontal=True, align=align)


def column(panels: Iterable[Panel | Diagram],
           gap: float | str | None = None, align: str = "center") -> Diagram:
    """Panels stacked, their plot areas on one vertical line.

    `align` is "left", "center"/"centre" (the default) or "right", and picks
    which edge of the areas is lined up -- see `row`, whose argument this is
    the quarter turn of. "left" is the one to reach for when the members'
    areas differ in width, since it puts the y axes on one line and leaves the
    ragged edge on the right.
    """
    return _lay_out(panels, gap, horizontal=False, align=align)


#: What `row` and `column` accept, mapped onto the edge of the area to line up.
#: "centre" beside "center" because the prose in this codebase is British and
#: the API is not; refusing the spelling the docstrings use is a poor trade.
_ROW_ALIGN = {"top": "start", "n": "start", "start": "start",
              "center": "center", "centre": "center", "c": "center",
              "bottom": "end", "s": "end", "end": "end"}
_COLUMN_ALIGN = {"left": "start", "w": "start", "start": "start",
                 "center": "center", "centre": "center", "c": "center",
                 "right": "end", "e": "end", "end": "end"}


def _lay_out(panels: Iterable[Panel | Diagram], gap: float | str | None,
             horizontal: bool, align: str = "center") -> Diagram:
    table = _ROW_ALIGN if horizontal else _COLUMN_ALIGN
    if align not in table:
        what = "row" if horizontal else "column"
        raise ValueError(
            f"{align!r} is not an alignment for a {what} of panels; use one "
            f"of: {', '.join(sorted(table))}"
        )
    mode = table[align]
    step = active_theme().gap("l") if gap is None else mm(gap)
    placed: list[Diagram] = []
    areas: list[Rect] = []
    cursor = 0.0
    for item in panels:
        node = item.build() if isinstance(item, Panel) else item
        box = node.envelope.bbox()
        if box is None:
            placed.append(node)
            continue
        across = _across(node, box, mode, horizontal)
        if horizontal:
            offset = Vec2(cursor - box.x0, -across)
            cursor += box.width + step
        else:
            offset = Vec2(-across, cursor - box.y0)
            cursor += box.height + step
        member = node.translated(offset.x, offset.y)
        placed.append(member)
        area = plot_area(member)
        if area is not None:
            areas.append(area)
    group = drawn_group(placed, "panels")
    # The union of the members' areas is the row's own -- and it is the answer
    # to "where does a stack of two panels put its letter", which is the top
    # panel's area top edge, not the box top the x labels of the panel above
    # pushed out. Without it a `column` standing in a `row` is placed by its
    # box while its neighbours are placed by their areas, and `letters` hangs
    # its letter a centimetre low. The rectangle is in the frame the children
    # were laid out in, which is the pre-recentring frame `drawn_group` leaves
    # on the group's transform -- the same convention `Panel.build` follows.
    if areas:
        declare_area(group, Rect.hull([Vec2(a.x0, a.y0) for a in areas]
                                      + [Vec2(a.x1, a.y1) for a in areas]))
    return group


def _across(node: Diagram, box: Rect, mode: str, horizontal: bool) -> float:
    """The coordinate across the run that this member must put on the line.

    "center" is `_origin_of`, unchanged and still the default, because a panel
    with no declared area has an `origin` anchor worth more than its box
    centre. The edges are read off the declared area where there is one and
    off the bounding box where there is not -- a member with no area to line
    up has only its box, and lining up the boxes is what a caller asking for
    "top" would have written by hand.
    """
    if mode == "center":
        origin = _origin_of(node)
        return origin.y if horizontal else origin.x
    area = plot_area(node) or box
    if horizontal:
        return area.y0 if mode == "start" else area.y1
    return area.x0 if mode == "start" else area.x1


def _inside(box: Rect, area: Rect) -> bool:
    """Whether a node's box is already within the plot area, to a micrometre.

    The tolerance is there because a mark placed exactly on the domain's edge
    lands on the boundary to the last bit of a float, and clipping it would
    rewrite geometry to no purpose.
    """
    return (box.x0 >= area.x0 - _CLIP_SLACK and box.x1 <= area.x1 + _CLIP_SLACK
            and box.y0 >= area.y0 - _CLIP_SLACK
            and box.y1 <= area.y1 + _CLIP_SLACK)
