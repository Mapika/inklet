"""What a named series looked like, so its key can be built from it.

A legend written by hand is a second description of the picture, kept in step
with the first by hand, and `inklet.lint`'s `KEY_MISMATCH` exists because that
does not happen: a series is recoloured, or dropped, and the swatch beside it
goes on claiming what used to be true.

So a series says its name where it is drawn -- `p.line(trace, name="wild
type")` -- and the panel remembers the *appearance* it was drawn with. The key
is then a rendering of that record rather than a parallel list, and the two
cannot disagree without the drawing call itself being wrong.

The record is an appearance, not a diagram: one entry per name, merged across
calls. `p.band(...)` , `p.line(..., name="wt")` and `p.scatter(..., name="wt")`
are three calls describing one series, and the swatch that stands for it is a
tinted band with a line across it and the marker on top -- which is what the
reader is looking at.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable

from ..core import Diagram, RectPrim
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.shapes import MARK_KIND, marker as make_marker

__all__ = ["SeriesKey", "merge_keys", "select_keys", "swatch_for"]

#: A swatch is wider than it is tall, because most of them carry a line and a
#: line needs length to show its dash pattern. 1.9 is enough for two dashes of
#: the house pattern; much more and the names stop reading as a column.
_SWATCH_ASPECT = 1.9


@dataclass(frozen=True, slots=True)
class SeriesKey:
    """How one named series was drawn: enough to redraw it at swatch size.

    `forms` is a set of the marks the name was used for -- "area", "line",
    "marker" -- because one series is often several calls and the key should
    show all of it.
    """

    name: str
    forms: frozenset[str] = frozenset()
    color: str | None = None
    fill: str | None = None
    marker: str = "circle"
    dash: tuple[float, ...] | None = None
    width: float | None = None
    #: The marker's diameter in mm when the series gave one size for every
    #: point; None draws the swatch's own default marker.
    marker_size: float | None = None
    #: The marker's own paint when it was not simply `color` all over: a
    #: hollow ring is a paper fill inside a coloured outline, and a marker
    #: given `stroke=` is outlined in that. None falls back to `color`.
    marker_fill: str | None = None
    marker_stroke: str | None = None
    marker_stroke_width: float | None = None
    #: A swatch the caller built themselves -- `marks(item, ...)` passes the
    #: very shape it placed, which is the most honest swatch there is.
    node: Diagram | None = field(default=None, compare=False)

    def merged(self, other: "SeriesKey") -> "SeriesKey":
        """This entry updated by a later call under the same name.

        First writer wins on every field it set: a series is normally drawn
        band first, then line, then markers, and the band's pale tint is not
        the colour the reader should see in the key.
        """
        return replace(
            self,
            forms=self.forms | other.forms,
            color=self.color if self.color is not None else other.color,
            fill=self.fill if self.fill is not None else other.fill,
            marker=self.marker if "marker" in self.forms else other.marker,
            marker_size=(self.marker_size if "marker" in self.forms
                         else other.marker_size),
            marker_fill=(self.marker_fill if "marker" in self.forms
                         else other.marker_fill),
            marker_stroke=(self.marker_stroke if "marker" in self.forms
                           else other.marker_stroke),
            marker_stroke_width=(self.marker_stroke_width if "marker" in self.forms
                                 else other.marker_stroke_width),
            dash=self.dash if self.dash is not None else other.dash,
            width=self.width if self.width is not None else other.width,
            node=self.node if self.node is not None else other.node,
        )


def series_color(entries: Iterable[SeriesKey], name: str | None,
                 given: str | None) -> str | None:
    """Use an explicit colour, an existing series colour, or its palette slot.

    Slots follow first appearance, including records without a colour. Scan
    all records until a colour is found: an area can precede its coloured line.
    Unnamed series keep the theme's ink instead of claiming a palette entry.
    """
    if given is not None or name is None:
        return given
    name = str(name)
    positions: dict[str, int] = {}
    for key in entries:
        if key.name == name and key.color is not None:
            return key.color
        if key.name not in positions:
            positions[key.name] = len(positions)
    return active_theme().color(positions.get(name, len(positions)))


def series_names(name) -> list | None:
    """`name=` of a multi-series mark as a list: one string means one series."""
    if name is None:
        return None
    return [name] if isinstance(name, str) else list(name)


def swatch_for(entry: SeriesKey, size: float) -> Diagram:
    """The little picture that stands for one series.

    Built out of the same three things a plot is: a filled area, a stroked
    line, a marker. Whichever the series actually used are stacked in that
    order, so a line over a confidence band comes out as a line over a band.
    """
    if entry.node is not None:
        return entry.node
    theme = active_theme()
    wide = size * _SWATCH_ASPECT
    parts: list[Diagram] = []

    if "area" in entry.forms:
        parts.append(Diagram(prim=RectPrim(wide, size), kind=MARK_KIND)
                     .styled(fill=entry.fill or entry.color or theme.ink,
                             stroke="none"))
    if "line" in entry.forms:
        style: dict = {"stroke": entry.color or theme.ink}
        if entry.width is not None:
            style["stroke_width"] = entry.width
        if entry.dash is not None:
            style["stroke_dash"] = entry.dash
        parts.append(polyline(((-wide / 2, 0.0), (wide / 2, 0.0)),
                              kind="mark-line", **style))
    if "marker" in entry.forms:
        node = make_marker(entry.marker, _swatch_marker(entry.marker_size, size))
        # The marker as it was drawn: its own fill and outline where the
        # series gave them (a hollow ring, a white dot with an ochre edge),
        # otherwise the series colour all over.
        paint = {}
        fill = entry.marker_fill or entry.color
        stroke = entry.marker_stroke or entry.color
        if fill is not None:
            paint["fill"] = fill
        if stroke is not None:
            paint["stroke"] = stroke
        if entry.marker_stroke_width is not None:
            paint["stroke_width"] = entry.marker_stroke_width
        if paint:
            node = node.styled(**paint)
        parts.append(node)
    if not parts:
        parts.append(Diagram(prim=RectPrim(size, size), kind=MARK_KIND)
                     .styled(fill=entry.fill or entry.color or theme.ink,
                             stroke="none"))
    if len(parts) == 1:
        return _centred(parts[0])
    return Diagram(children=tuple(_centred(p) for p in parts), kind="swatch")


#: A marker swatch drawn at the series' own size stays within these fractions
#: of the swatch height: a bubble series does not stretch the key's rows, and
#: a dust-fine scatter still shows its colour.
_MARKER_SWATCH_RANGE = (1 / 3, 1.0)


def _swatch_marker(given: float | None, size: float) -> float:
    """The diameter of a marker swatch `size` tall: the series' marker when
    it had one size, clamped to `_MARKER_SWATCH_RANGE`, else the default."""
    if given is None:
        return size * 0.9
    low, high = _MARKER_SWATCH_RANGE
    return min(max(given, low * size), high * size)


def _centred(node: Diagram) -> Diagram:
    """Everything in a swatch is built around (0, 0); `polyline` recentres on
    its own box, which for a horizontal rule is the same point. This puts back
    anything that was not."""
    box = node.bbox
    if box is None:
        return node
    centre = box.center
    if abs(centre.x) < 1e-12 and abs(centre.y) < 1e-12:
        return node
    return node.translated(-centre.x, -centre.y)


def merge_keys(entries) -> list[SeriesKey]:
    """One entry per name, in the order the names were first drawn.

    Order is the paint order and not the alphabet: a reader matches the key to
    the picture top to bottom, and the top curve should be the top row.
    """
    out: dict[str, SeriesKey] = {}
    for entry in entries:
        here = out.get(entry.name)
        out[entry.name] = entry if here is None else here.merged(entry)
    return list(out.values())


def select_keys(keys: Iterable[SeriesKey], names=None) -> list[SeriesKey]:
    """`keys` chosen and ordered by `names` -- `legend(names=)` -- or all of
    them in drawing order when `names` is None. A name not among the keys,
    or one listed twice, raises."""
    from ..core import DiagramError

    keys = list(keys)
    if names is None:
        return keys
    if isinstance(names, str):
        names = [names]
    by_name = {entry.name: entry for entry in keys}
    wanted = [str(name) for name in names]
    unknown = [name for name in wanted if name not in by_name]
    if unknown:
        raise DiagramError(
            f"legend(names=) lists {unknown} but this panel drew {list(by_name)}")
    if len(set(wanted)) != len(wanted):
        raise DiagramError(f"legend(names=) repeats a name: {wanted}")
    return [by_name[name] for name in wanted]
