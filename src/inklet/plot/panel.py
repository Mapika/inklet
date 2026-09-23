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
from .matrix import (_RASTER_ABOVE_CELLS, matrix_centres, matrix_layer,
                     prepare_matrix)
from .scale import Band, Linear, Log, Scale, linear
from .metadata import declare_domain as _declare_domain
from .series import SeriesKey, merge_keys, series_color, swatch_for
from .timescale import dates, is_time_like

__all__ = ["Panel", "column", "panel", "row"]

_AXIS_SCALE = {"bottom": "x", "top": "x", "left": "y", "right": "y"}

#: A confidence band, as a blend towards paper. Pale enough to read the line
#: and the gridlines through, dark enough to have an edge on a 1x screen.
_BAND_TINT = 0.78

_ERROR_STYLES = ("band", "bars")

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

    def matrix(self, values: Sequence[Sequence[float]], *, ramp,
               scale: Scale | None = None,
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
        return self.draw(group, clip=clip)

    def _centres(self, given: Sequence | None, count: int,
                 scale: Scale, extent: float) -> list[float]:
        return matrix_centres(given, count, scale, extent)

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
            return self.draw(draw_curve(mapped, smooth=smooth, closed=closed,
                                        **style), clip=clip)
        reduced = simplify_points(mapped,tolerance) if tolerance else mapped
        node = polyline(reduced, closed=closed, **style)
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
        numbers = [float(v) for v in values]
        if scale is None:
            low, high = min(numbers), max(numbers)
            scale = linear((low, high if high > low else low + 1.0))
        unit = scale.with_range(0.0, 1.0)
        self._ramp = ramp
        self._scale_domain = scale
        return [ramp(unit.map(v)) for v in numbers], scale

    def bars(self, at: Sequence, heights, *, width: float = 0.8,
             baseline: float = 0.0, orient: str = "v",
             stacked: bool | None = None, grouped: bool | None = None,
             gap: float = 0.12, colors=None, bar_colors=None, names: Sequence[str] | None = None,
             labels=None, label_position: str = "auto",
             label_options: dict | None = None,
             **style) -> "Panel":
        """A rectangle per value, standing on a baseline.

        `at` is one position per bar -- categories on a band scale, numbers on
        a continuous one -- and `heights` is either one value each or several
        series of them. Two or more series are drawn side by side; pass
        `stacked=True` to pile them instead, which is a claim that they sum to
        something worth reading and so is never the default.

            p.bars(["ctrl", "drug"], [12, 31])
            p.bars(days, [morning, evening], colors=["#888", TH.accent])

        `orient="h"` lays the bars down: `at` is then a position on y and the
        heights run along x, which is the layout to use the moment the category
        names are longer than about six characters.

        `width` is a fraction of the slot on a band scale and a width in data
        units on a continuous one, and `gap` is the air between grouped bars as
        a fraction of their sub-slot. One series is drawn as a tint of the ink
        with a hairline edge; several take the theme's palette in order.

        `bar_colors=` assigns one colour per category, as a sequence or a
        mapping keyed by the values in `at`. It requires one series. A mapping
        from `inklet.categories()` also supplies category legend entries.

        `names=` is one name per *series*, not per bar -- the bars are named by
        the axis -- and gives `legend()` a swatch in each series' own colour.
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
        """
        clip = _clip_flag(style)
        if names is not None and bar_colors is not None:
            raise DiagramError("a per-category colour set cannot have one series legend; omit names")
        if names is not None:
            self._note_series(
                names, _marks.series_colors(
                    style.get("fill") if colors is None else colors,
                    _marks.series_count(heights)))
        from .categories import CategorySet
        at = tuple(at)
        node = _marks.bars(
            self, at, heights, width=width, baseline=baseline, orient=orient,
            stacked=stacked, grouped=grouped, gap=gap, colors=colors, bar_colors=bar_colors,
            **style)
        if isinstance(bar_colors, CategorySet):
            for label, color in bar_colors.subset(at).legend_entries:
                self._note(label, "area", fill=color, color=color)
        self.draw(*(() if node is None else (node,)), clip=clip)
        if labels is not None and labels is not False:
            from .bar_labels import bar_labels
            count = _marks.series_count(heights)
            fills = _marks.series_colors(
                style.get("fill") if colors is None else colors, count)
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

    def hist(self, values: Sequence[float], bins: int | Sequence[float] = 10, *,
             range: tuple[float, float] | None = None, density: bool = False,
             baseline: float = 0.0, orient: str = "v", colors=None,
             name: str | None = None, **style) -> "Panel":
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
        """
        clip = _clip_flag(style)
        self._note(name, "area", fill=_marks.series_colors(
            style.get("fill") if colors is None else colors, 1)[0])
        return self.draw(_marks.hist(
            self, values, bins, range=range, density=density,
            baseline=baseline, orient=orient, colors=colors, **style),
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

    def stackarea(self, x: Sequence, values, *, baseline=0.0, colors=None,
                  names: Sequence[str] | None = None, **style) -> "Panel":
        """Stack non-negative series over shared x values, in supplied order.

        `values` is series-major. `baseline` is a scalar or one value per x;
        `names` creates legend entries. Use `fill_between` for already
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
        if names is not None and len(names) != len(rows):
            raise DiagramError("stackarea needs one name per series")
        fills = _marks.series_colors(colors, len(rows))
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
        return self.draw(_marks.step(self, points, where=where, **style),
                         clip=clip)

    def boxplot(self, groups, *, at=None, width: float = 0.6,
                orient: str = "v", whisker: float = 1.5,
                outliers: bool = True, colors=None, **style) -> "Panel":
        """Quartile boxes with Tukey whiskers, one per group.

        `groups` is a mapping of position to samples -- the spelling that
        cannot get the labels out of order -- or a bare sequence of samples,
        which takes its positions from the band scale it is drawn against:

            p.boxplot({"wild type": wt, "mutant": ko})

        Each whisker stops on the furthest observation within `whisker` times
        the interquartile range; everything beyond is drawn as its own point.
        The box is unfilled by default, so the median is the only heavy line in
        it. `inklet.plot.box_stats(sample)` returns the same five numbers if you
        want them in the caption.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.boxplot(
            self, groups, at=at, width=width, orient=orient, whisker=whisker,
            outliers=outliers, colors=colors, **style), clip=clip)

    def violin(self, groups, *, at=None, width: float = 0.8,
               orient: str = "v", bandwidth: float | None = None,
               samples: int = 64, cut: float = 2.0, median: bool = True,
               colors=None, **style) -> "Panel":
        """Mirrored kernel densities, one per group.

        The shape a box plot cannot draw: two samples with the same quartiles
        and one of them bimodal look identical as boxes and obviously different
        as violins. The bandwidth is Silverman's robust rule unless you give
        one; `cut` is how many bandwidths past the extremes the outline runs,
        and `samples` how finely it is drawn.

        A violin claims the density is smooth, so it needs enough data to
        support the claim -- under about twenty points per group, draw the
        points.
        """
        clip = _clip_flag(style)
        return self.draw(_marks.violin(
            self, groups, at=at, width=width, orient=orient,
            bandwidth=bandwidth, samples=samples, cut=cut, median=median,
            colors=colors, **style), clip=clip)

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
        """
        if side not in SIDES:
            raise ValueError(
                f"unknown axis side {side!r}; expected one of {', '.join(SIDES)}"
            )
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
        Fixed `corner` puts it inside the plot area on a knocked-out plate; `side`
        ("right", "left", "top", "bottom") puts it outside, clear of whatever
        furniture is already there, and then no plate is needed. `entries=`
        overrides the record entirely, taking `(name, colour)` or
        `(name, diagram)` pairs, which is the escape hatch for a key that
        describes something this panel did not draw.

        Top/bottom legends fit their columns to the plot width by default.
        Pass `columns=1` to stack entries explicitly, or `columns='auto'` and
        `max_width=...` to choose another measured width. Text is never shrunk.

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
        if columns == 'auto' and max_width is None:
            max_width = self.width if side is not None else self.width - 2*(theme.gap('s') if pad is None else mm(pad))
        node = make_legend(rows, columns=columns, max_width=max_width, swatch=swatch, title=title,
                           markup=markup, order=order, col_gap=col_gap, row_gap=row_gap, **style)
        gap = theme.gap("s") if pad is None else mm(pad)
        if side is not None:
            # Outside the plot the key is measured against the furniture's
            # line boxes, which already carry the type's leading; a further
            # 's' step parted it from the axis name it explains.
            beside_gap = theme.gap("xs") if pad is None else gap
            self._over.append(self._beside(node, side, beside_gap))
            return self._touched()
        if plate is None:
            plate = True
        if plate:
            node = _plated(node, theme, theme.gap("xs"))
        if corner == 'auto':
            from ..layout.clear_space import place_in_clear_space
            node = place_in_clear_space(node, within=self.area,
                                        avoid=(*self._content,*self._over), pad=gap)
        else:
            node = _into_corner(node, self.area, corner or "ne", gap)
        self._over.append(node)
        return self._touched()

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
        children = list(self._under) + list(self._content) + list(self._over)
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
        window the inset magnifies and joins it to the inset.
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

    def swarm(self, groups, *, at=None, width: float = 0.8,
              max_width: float | str | None = None, orient: str = "v",
              size: float | str | None = None,
              gap: float | str | None = None, marker: str = "circle",
              hollow: bool = False, colors=None, **style) -> "Panel":
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
        points and a thicket beyond that. `colors=` takes one colour per group.

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
            colors=colors, **style), clip=clip)

    def dumbbell(self, at: Sequence, values, *, orient: str = "v",
                 size: float | str | None = None, colors=None,
                 names: Sequence[str] | None = None, marker: str = "circle",
                 connector: dict | None = None, **style) -> "Panel":
        """Two or more dots per category joined by a line: a dumbbell plot.

        `values` holds one sequence per series, each with one value per
        position in `at`, the same shape `bars` takes for grouped bars. The
        dots of one category share its centre on the band scale, and a line
        runs from the smallest to the largest value present. `None` or NaN is
        a missing value: that dot is not drawn, and a category with only one
        value has no line.

            p.dumbbell(genes, [before, after], names=["before", "after"],
                       orient="h")

        `size` is the dot diameter in millimetres (default: the scatter
        marker). `colors=` sets one colour per series; the default is the
        theme palette. `connector=` overrides the line's style, which by
        default is a light grey at the theme's thick stroke. `names=` adds one
        marker entry per series to `legend()`.
        """
        from .paired import dumbbell as _dumbbell

        clip = _clip_flag(style)
        node, fills = _dumbbell(self, at, values, orient=orient, size=size,
                                colors=colors, marker=marker,
                                connector=connector, **style)
        if names is not None:
            if len(names) != len(fills):
                raise DiagramError(
                    f"names= has {len(names)} names for {len(fills)} series")
            for name, fill in zip(names, fills):
                self._note(name, "marker", color=fill, marker=marker)
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
        return self.draw(polyline(self.map(points), **style), clip=clip)

    def ridgeline(self, groups, *, at=None, overlap: float = 1.5,
                  bandwidth: float | None = None, samples: int = 96,
                  scale: str = "shared", fit: bool = True, colors=None,
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
        x. `colors=` sets one fill per group (default: one tint for all);
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
                                scale=scale, fit=fit, colors=colors, **style)
        return self.draw(node, clip=clip)

    def raincloud(self, groups, *, at=None, orient: str = "h",
                  width: float = 0.9, bandwidth: float | None = None,
                  samples: int = 64, cut: float = 2.0, whisker: float = 1.5,
                  points: str | None = "jitter", size: float | str | None = None,
                  seed: int = 0, box: bool = True, colors=None,
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

        `colors=` sets one colour per group: the points use it and the half
        violin a paler blend of it. The default is the ink for one group and
        the theme's ink palette for several. Other keywords style the points.
        """
        from .raincloud import raincloud as _raincloud

        clip = _clip_flag(style)
        node, _, _ = _raincloud(self, groups, at=at, orient=orient, width=width,
                                bandwidth=bandwidth, samples=samples, cut=cut,
                                whisker=whisker, points=points, size=size,
                                seed=seed, box=box, colors=colors, **style)
        return self.draw(node, clip=clip)

    def label_points(self, points: Iterable[Sequence], labels: Sequence[str],
                     **kwargs) -> "Panel":
        """Label many data points at once, clear of the marks and each other.

        `points` are data coordinates and `labels` one string per point.
        Each label goes to the nearest free position around its point; a
        label that had to move further out gets a hairline leader back to
        the point. Draw the marks first and call this last: it avoids what
        the panel holds at the time of the call.

            p.scatter(cloud, color=TH.muted)
            p.label_points(hits, names)

        Keywords: `size` (type size, mm), `clear` (the smallest gap between a
        point and its label, mm), `reach` (how far out a label may go, mm),
        `leader=False` to never draw leaders, `markup`, `avoid=` (more
        diagrams to keep clear of), `leader_style=` and any text style such
        as `fill=`. The placement is deterministic. A label that could not be
        placed without overlap is still drawn at its best position and listed
        in the node's `point_labels` note under `unresolved`. See
        `plot.point_labels`.
        """
        from .point_labels import label_points as _label_points

        node = _label_points(self, list(points), labels, **kwargs)
        return self.over(node, clip=False)


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
