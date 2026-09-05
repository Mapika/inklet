"""The axis: a spine, its ticks, their labels, and a name for the quantity.

Axes are built in the scale's own coordinates -- a tick for the value v sits at
`scale.map(v)` and nowhere else -- so an axis and the data it describes cannot
drift apart. The construction origin is the *start* of the scale for a
horizontal axis and the *bottom* of it for a vertical one, which is the plot
area's bottom-left corner in both cases; `place()` an x axis and a y axis
together and they meet there without either being nudged.

Two decisions are worth defending.

**Ticks are dropped, never squeezed.** When labels would collide, the axis
keeps every second or every third tick rather than shrinking the type or
rotating it. A publication figure is read at 89mm wide, where 5pt is already
the floor; the number of labels is the only variable left.

That holds only while the ticks are a rhythm. On a band scale each label names
one specific row, so a dropped label is a bar the reader cannot identify --
information gone, and gone silently. Enumerated scales therefore keep every
label and let it collide, because a collision is at least visible, and the
linter reports it. `thin=` overrides the choice either way.

**Sizes come from the type size, not from millimetres.** A tick is 0.55 of the
label height, its gap 0.35. Anything else and an axis retuned for a slide deck
grows its type without growing its furniture.
"""

from __future__ import annotations

import inspect
import math
from typing import Callable, Sequence

from ..core import Diagram, Vec2, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place
from ..typeset import shape
from .breaks import (BREAK_NOTE, axis_break_glyph, axis_breaks_note, gap_bands,
                     outside_breaks, spine_runs)
from .scale import Scale, si_labels

__all__ = ["SIDES", "axis", "text_node", "tick_texts", "tick_values"]

SIDES = ("bottom", "top", "left", "right")

AXIS_KIND = "axis"
SPINE_KIND = "spine"
TICK_KIND = "tick"
TICK_LABEL_KIND = "tick-label"
AXIS_LABEL_KIND = "axis-label"

_TICK_OF_TYPE = 0.55
_PAD_OF_TYPE = 0.35
_LABEL_PAD_OF_TYPE = 0.5
# A minor tick, as a fraction of a major one. Much shorter than a half and the
# two read as one comb; much longer and the reader starts looking for a number
# against it.
_MINOR_OF_MAJOR = 0.55
# The least room between two minor ticks, as a fraction of type size. Nine
# mantissa ticks in a 2mm decade is not a scale, it is a grey stripe along the
# spine; the scale coarsens its subdivision until they clear this.
_MINOR_CLEAR_OF_TYPE = 0.30
# Air between neighbouring tick labels, as a fraction of type size. Below about
# half an em two numbers read as one number with a gap in it.
_CLEAR_OF_TYPE = 0.7

_HORIZONTAL = {"bottom": 1.0, "top": -1.0}
_VERTICAL = {"left": -1.0, "right": 1.0}


def text_node(content: str, size: float, kind: str, *, align: str = "center",
              features: dict | None = None, markup: bool = True,
              **style) -> Diagram:
    """A shaped label. Text is measured here, as everywhere in inklet, by the one
    module that owns a font file.

    `features` are OpenType tags for `inklet.typeset.shape` -- `{"tnum": True}`
    for the tabular figures a column of numbers wants. Passed through
    defensively: a typesetter that does not take them yet gets the call without.

    `markup=False` sets the string exactly as given, which is what anything
    that came out of the caller's *data* needs: a gene called `Notch1**` is a
    gene, not a bold instruction. Prose the author wrote -- an axis name, a
    title, a caption -- keeps markup.
    """
    theme = active_theme()
    kwargs = dict(font=theme.font_family, size=size, align=align,
                  line_height=theme.line_height)
    if features and _TAKES_FEATURES:
        kwargs["features"] = features
    if not markup and _TAKES_MARKUP:
        kwargs["markup"] = False
    node = Diagram(prim=shape(content, **kwargs), kind=kind)
    return node.styled(**style) if style else node


#: Whether the typesetter takes OpenType feature tags. Asked of the signature
#: once rather than by catching `TypeError` around the call: a `TypeError`
#: raised *inside* `shape` would look identical, and swallowing it would turn
#: a real fault into silently unfeatured text.
_TAKES_FEATURES = "features" in inspect.signature(shape).parameters

#: Whether the typesetter reads inline markup at all, asked the same way. A
#: build without it sets every string literally, which is the behaviour
#: `markup=False` is asking for.
_TAKES_MARKUP = "markup" in inspect.signature(shape).parameters


def axis(scale: Scale, *, side: str = "bottom", label: str | Diagram | None = None,
         ticks: Sequence | None = None, count: int = 5,
         format: Callable[[object], str] | str | None = None,
         si: bool = False, length: float | str | None = None,
         tick_size: float | str | None = None, tick_pad: float | str | None = None,
         label_pad: float | str | None = None, spine: bool = True,
         thin: bool | None = None, labels: bool = True, rotate: float = 0.0,
         tnum: bool = True, markup: bool | None = None,
         offset: bool | str | None = None,
         minor: bool | int = False, minor_size: float | str | None = None,
         kind: str = AXIS_KIND, **style) -> Diagram:
    """One axis of a plot.

    `side` names where the furniture hangs: "bottom" and "top" run the scale
    along x, "left" and "right" along y. `length`, if given, re-ranges the
    scale to that many millimetres, running left to right or bottom to top.

    `ticks` overrides the values shown. `format` overrides how they are
    written, and takes any of three forms:

    * a callable, `value -> str`, for anything the others cannot say;
    * a string with a `{}` in it, used as a format spec -- `"{:.0f} Hz"`;
    * any other string, appended to the label the scale chose -- `"%"`, `"\u00b0"`.

    `si=True` puts one SI prefix on the whole set (`1.0 k`, `1.5 k`) rather
    than letting each number choose its own; a suffix `format` composes on top
    of it, so `si=True, format="W"` reads `1.5 kW`.

    `labels=False` keeps the spine and the ticks and drops the numbers -- what
    an inner panel of a shared-axis grid wants, and what `inklet.facets` uses.
    `minor=True` adds unlabelled subdivisions between the ticks, or pass an
    integer to say how many pieces each step divides into.

    A negative `tick_size` puts the ticks inside the plot area, which is the
    convention in several journals.

    `thin` says whether labels that would collide may be dropped. The default
    asks the scale: continuous ticks thin, a band scale's categories do not.

    `rotate` turns the tick labels, in degrees anticlockwise, which is the
    other answer to labels that do not fit and the only one available when
    every label has to stay -- eight named conditions along the bottom of a
    39mm panel. 45 is the conventional angle. A rotated label hangs from its
    trailing corner so the *end* of the word sits under its tick, and the
    thinning test switches from "how wide is it" to how far apart two parallel
    diagonal strips are, which is the spacing times the sine of the angle.

    `tnum=True` asks the font for tabular figures, so a column of numbers up
    a y axis lines its digits up, and it is **on** by default. A right-aligned
    column of y labels is the textbook case for tabular figures: with
    proportional ones the `1`s sit in a different place in every row and the
    column has no edge. The cost is that a font whose default digits are
    proportional sets every number to a different width once this is on, so a
    figure measured on one machine and set on another moves -- which is an
    argument for asking for the feature, not for leaving the choice to
    whichever face the reader has installed. `tnum=False` gets the font's own
    digits back.

    `offset` is the part of every tick label that the whole set has in common,
    written once past the last tick instead of on each of them: the year, on a
    date axis that sits inside one calendar year, or the date on an axis of
    clock times inside one day. The default asks the scale, which is the only
    object that knows; pass a string to write your own, or `False` for none.
    Without it a monthly axis reads `Jan Apr Jul Oct` and never says the year,
    and the author has to remember to put it in the axis name.

    `markup` says whether the tick labels are read as inklet's inline markup. The
    default asks the scale, and the answer is almost always no: a tick label is
    data -- a gene called `Notch1**`, a condition written `//in vitro//` -- and
    reading it as markup would silently restyle or eat it. A log scale is the
    exception, because `10^{3}` is markup it wrote itself. Pass `markup=True`
    for a `format=` of your own that writes markup, and `False` to be sure a
    label reaches the page exactly as given. The axis *name* is prose and
    always keeps its markup.
    """
    if side not in SIDES:
        raise ValueError(
            f"unknown axis side {side!r}; expected one of {', '.join(SIDES)}"
        )
    horizontal = side in _HORIZONTAL
    if length is not None:
        span = mm(length)
        # A vertical scale runs *up* the page, so its range ends negative.
        scale = (scale.with_range(0.0, span) if horizontal
                 else scale.with_range(0.0, -span))

    theme = active_theme()
    size = theme.font_size_small
    reach = _TICK_OF_TYPE * theme.font_size if tick_size is None else mm(tick_size)
    gap = _PAD_OF_TYPE * theme.font_size if tick_pad is None else mm(tick_pad)
    name_gap = (_LABEL_PAD_OF_TYPE * theme.font_size if label_pad is None
                else mm(label_pad))
    away = _HORIZONTAL[side] if horizontal else _VERTICAL[side]

    values, texts, extents = _tick_set(scale, count, ticks, format, si, size,
                                       horizontal=horizontal, rotate=rotate,
                                       tnum=tnum, markup=markup)
    positions = [scale.map(v) for v in values]
    keep = _keep(positions, extents, _CLEAR_OF_TYPE * theme.font_size,
                 _thins(scale, thin))

    if ticks is not None and thin is None and labels and len(keep) < len(values):
        import warnings
        warnings.warn(
            f"axis omitted {len(values)-len(keep)} of {len(values)} explicitly supplied ticks; "
            "use thin=False to preserve them or thin=True to request thinning",
            UserWarning, stacklevel=2)

    items: list = []
    gaps = gap_bands(scale)
    if spine:
        r0, r1 = scale.range
        for a, b in spine_runs(r0, r1, gaps):
            ends = ((a, 0.0), (b, 0.0)) if horizontal else ((0.0, a), (0.0, b))
            items.append(polyline(ends, kind=SPINE_KIND))
    # After the spine and before the ticks, so a tick that ends on the break --
    # the last value the axis draws -- is still the topmost thing there.
    for a, b in gaps:
        items.extend(axis_break_glyph(a, b, horizontal=horizontal, theme=theme))

    if minor:
        pieces = minor if isinstance(minor, int) and not isinstance(minor, bool) \
            else None
        small = (_MINOR_OF_MAJOR * reach if minor_size is None else mm(minor_size))
        clear = _MINOR_CLEAR_OF_TYPE * theme.font_size
        for value in scale.minor_ticks(values, pieces, clear):
            at = scale.map(value)
            tip = away * small
            items.append(polyline(((at, 0.0), (at, tip)) if horizontal
                                  else ((0.0, at), (tip, at)), kind=TICK_KIND))

    # A negative tick_size points into the plot, so the labels only have to
    # clear the gap, not a tick that is on the other side of the spine.
    edge = max(reach, 0.0) + gap
    written: list[int] = []          # where in `items` the labels ended up
    for index in keep:
        at = positions[index]
        tip = away * reach
        line = ((at, 0.0), (at, tip)) if horizontal else ((0.0, at), (tip, at))
        items.append(polyline(line, kind=TICK_KIND))
        if not labels:
            continue
        node = texts[index]
        target = Vec2(at, away * edge) if horizontal else Vec2(away * edge, at)
        box = node.bbox
        hangs = _hangs(box, horizontal, away, rotate)
        written.append(len(items))
        items.append((target + (box.center - hangs), node))

    if labels and offset is not False:
        tail = _offset_text(scale, values, offset)
        if tail is not None:
            written.append(len(items))
            items.append(_offset_label(tail, scale, positions, extents, keep,
                                       horizontal, away, edge, size, theme))
    _group_slanted(items, written, rotate, positions, extents, keep,
                   _CLEAR_OF_TYPE * theme.font_size)

    if label is not None:
        items.append(_axis_label(label, scale, texts, keep if labels else (),
                                 horizontal, away, edge, name_gap, theme))
    node = place(items, kind=kind, **style)
    breaks = axis_breaks_note(scale, horizontal=horizontal)
    if breaks is not None:
        # In this node's own frame, which is the scale's. `Diagram.note` is
        # core M17 and is read defensively everywhere else, so it is written
        # defensively here: an axis on a build without notes simply draws its
        # break and says nothing about it, and `BREAK_DISTORTS` stays quiet.
        note = getattr(node, "note", None)
        if callable(note):
            note(BREAK_NOTE, breaks)
    return node


def _group_slanted(items: list, written: Sequence[int], rotate: float,
                   positions: Sequence[float], extents: Sequence[float],
                   keep: Sequence[int], clear: float) -> None:
    """Declare slanted tick labels abutting, in place in `items`.

    A slanted label's bounding box is not the label: two 45-degree words that
    clear each other by a millimetre have boxes that overlap by a third of
    their area, and `OVERLAP` reports every neighbouring pair on the axis --
    four errors on a six-category panel whose picture is perfect. The linter is
    not wrong about the boxes; the boxes are the wrong shape.

    The axis is the one object that has measured the right thing: `_extent`
    spaces slanted labels as parallel diagonal strips, and `_keep` has already
    proved the kept ones clear. Where that proof holds, it is declared --
    `inklet.abutting` is exactly the mechanism, and it is scoped to the labels, so
    a label over a bar or over the axis name is still a finding. Where it does
    not hold -- `thin=False` over labels that genuinely collide -- nothing is
    declared and the linter reports them, which is the whole point of asking
    for that.
    """
    if not written or not rotate or not _clears(positions, extents, keep, clear):
        return                       # upright labels stay exactly where they were
    from ..diagnostics.abut import abutting

    labels = [items[i] for i in written]
    for i in reversed(written):
        del items[i]
    items.append(place(labels, kind=abutting(TICK_LABEL_KIND), origin=(0, 0)))


def _offset_text(scale: Scale, values: Sequence, offset) -> str | None:
    """What the whole tick set has in common, if anything does.

    Asked of the scale via `getattr` so that a caller's own scale needs to know
    nothing about this: no method, no offset, exactly as before.
    """
    if isinstance(offset, str):
        return offset
    reader = getattr(scale, "offset_label", None)
    return None if reader is None else reader(values)


def _offset_label(text: str, scale: Scale, positions: Sequence[float],
                  extents: Sequence[float], keep: Sequence[int],
                  horizontal: bool, away: float, edge: float, size: float,
                  theme):
    """The shared part of the labels, set once past the last tick.

    On the tick labels' own line -- it is one of them, in the sense that it
    completes every one of them -- and clear of the last, so the reader meets
    `Oct 2024` as two words rather than as a collision. Past the end of the
    scale as well as past the last label, so an axis whose last tick is short
    of the end does not pull the year inward.
    """
    # A tick label by kind as well as by role: it is set in the same face, at
    # the same size, on the same line, and every rule that reads a tick label
    # -- contrast, minimum type size -- should read this one too.
    node = text_node(text, size, TICK_LABEL_KIND, markup=False)
    box = node.bbox
    clear = _CLEAR_OF_TYPE * theme.font_size
    ends = scale.range
    if horizontal:
        reach = max([max(ends)]
                    + [positions[i] + extents[i] / 2 for i in keep])
        target = Vec2(reach + clear + box.width / 2, away * edge)
    else:
        reach = min([min(ends)]
                    + [positions[i] - extents[i] / 2 for i in keep])
        target = Vec2(away * edge, reach - clear - box.height / 2)
    return (target + (box.center - _hangs(box, horizontal, away, 0.0)), node)


def tick_values(scale: Scale, count: int = 5, *, horizontal: bool = True,
                ticks: Sequence | None = None,
                format: Callable[[object], str] | str | None = None,
                si: bool = False, thin: bool | None = None,
                rotate: float = 0.0, tnum: bool = True) -> tuple:
    """The values an axis would actually label, thinning included.

    Gridlines ask this so that a rule and a tick can never disagree about where
    a number is -- which means `thin` and `tnum` have to mean here what they
    mean there: both feed the collision test that decides what survives.
    """
    theme = active_theme()
    values, _labels, extents = _tick_set(scale, count, ticks, format, si,
                                         theme.font_size_small,
                                         horizontal=horizontal, rotate=rotate,
                                         tnum=tnum)
    positions = [scale.map(v) for v in values]
    keep = _keep(positions, extents, _CLEAR_OF_TYPE * theme.font_size,
                 _thins(scale, thin))
    return tuple(values[i] for i in keep)


def tick_texts(scale: Scale, values: Sequence, format=None,
               si: bool = False) -> tuple[str, ...]:
    """What a set of tick values is written as.

    The scale decides by default -- it is the only object that knows whether
    these are decades, categories or a linear lattice. `format` and `si` are
    the two overrides, and they compose: a suffix is appended to whatever the
    step before it produced.
    """
    if callable(format):
        return tuple(format(v) for v in values)
    base = si_labels(values) if si else scale.tick_labels(values)
    if isinstance(format, str):
        if "{" in format:
            return tuple(format.format(v) for v in values)
        return tuple(text + format for text in base)
    return tuple(base)


def _tick_set(scale: Scale, count: int, ticks, format, si: bool, size: float,
              *, horizontal: bool = True, rotate: float = 0.0,
              tnum: bool = False, markup: bool | None = None
              ) -> tuple[tuple, list[Diagram], list[float]]:
    """The tick values, their labels, and how much axis each label occupies.

    The extents are measured here rather than off the finished nodes because a
    rotated label's bounding box no longer answers the question the collision
    test asks. See `_extent`.
    """
    values = outside_breaks(
        scale, tuple(scale.ticks(count)) if ticks is None else tuple(ticks))
    texts = tick_texts(scale, values, format, si)
    features = {"tnum": True} if tnum else None
    # Read off the scale rather than assumed: only a scale that writes its own
    # labels -- a log axis and its `10^{3}` -- has markup in them.
    reads_markup = (getattr(scale, "label_markup", False) if markup is None
                    else markup)
    nodes = [text_node(t, size, TICK_LABEL_KIND, features=features,
                       markup=reads_markup)
             for t in texts]
    extents = [_extent(n.bbox, horizontal, rotate) for n in nodes]
    if rotate:
        nodes = [n.rotated(-rotate) for n in nodes]
        if not horizontal:
            extents = [n.bbox.height for n in nodes]
    return values, nodes, extents


def _extent(box, horizontal: bool, rotate: float) -> float:
    """How much of the axis one upright label needs to itself.

    Along a horizontal axis that is its width. Rotate it, and neighbouring
    labels become parallel diagonal strips: two of them whose ticks are d
    apart clear each other by d*sin(angle), so one line of type needs
    height/sin(angle) of axis, which for 45 degrees is about 1.4 line heights
    no matter how long the words are. That is the whole reason to slant them.
    """
    if not horizontal:
        return box.height
    if rotate:
        lean = abs(math.sin(math.radians(rotate)))
        if lean > 1e-6:
            return box.height / lean
    return box.width


def _hangs(box, horizontal: bool, away: float, rotate: float) -> Vec2:
    """The point on a tick label that sits against the spine.

    Unrotated, that is the middle of the edge facing the axis: the label is
    centred under its tick. Rotated, it is a *corner* -- the trailing one, so
    that the last letter of a slanted word ends under the tick it names and the
    word runs away from the plot. Which corner depends on which way it leans.
    """
    if not horizontal:
        return Vec2(box.x1 if away < 0 else box.x0, box.center.y)
    y = box.y0 if away > 0 else box.y1
    if not rotate:
        return Vec2(box.center.x, y)
    return Vec2(box.x1 if rotate > 0 else box.x0, y)


def _axis_label(label, scale: Scale, labels: Sequence[Diagram], keep: Sequence[int],
                horizontal: bool, away: float, edge: float, gap: float, theme):
    """The name of the quantity, clear of the widest tick label.

    A vertical axis label is rotated to read bottom-to-top -- the direction
    every journal sets it in, and the one that does not force the reader to
    tilt their head the wrong way.
    """
    node = (label if isinstance(label, Diagram)
            else text_node(label, theme.font_size, AXIS_LABEL_KIND))
    if not horizontal:
        node = node.rotated(-90.0)
    widest = max((labels[i].bbox.height if horizontal else labels[i].bbox.width)
                 for i in keep) if keep else 0.0
    box = node.bbox
    reach = edge + widest + gap + (box.height if horizontal else box.width) / 2
    middle = sum(scale.range) / 2
    centre = (Vec2(middle, away * reach) if horizontal
              else Vec2(away * reach, middle))
    return (centre, node)


def _thins(scale: Scale, thin: bool | None) -> bool:
    """Whether this axis may drop labels to make the rest fit.

    Asking the scale rather than looking for `Band` by name: a scale that
    enumerates its ticks is the general case, and a caller with their own is
    entitled to the same answer without subclassing ours.
    """
    return not getattr(scale, "enumerated", False) if thin is None else thin


def _keep(positions: Sequence[float], extents: Sequence[float],
          clear: float, thin: bool = True) -> tuple[int, ...]:
    """Indices of the ticks to draw: every stride-th one, for the smallest
    stride whose labels do not touch.

    Thinning by a stride rather than by dropping whichever label happens to
    collide is what keeps the 1/2/5 rhythm -- a reader counts the gaps between
    labels, and an irregular set breaks that count.

    `thin=False` keeps all of them and accepts the collision. See the module
    docstring for why an enumerated scale would rather be caught overlapping
    than quietly lose a row.
    """
    if not thin or len(positions) < 2:
        return tuple(range(len(positions)))
    for stride in range(1, len(positions) + 1):
        kept = tuple(range(0, len(positions), stride))
        if _clears(positions, extents, kept, clear):
            return kept
    return (0,)


def _clears(positions: Sequence[float], extents: Sequence[float],
            kept: Sequence[int], clear: float) -> bool:
    """Whether neighbouring kept labels leave `clear` between them.

    Along the axis, in the extents `_extent` measured -- which for a slanted
    label is the width of its diagonal strip and not the width of its box.
    """
    return all(abs(positions[b] - positions[a]) + 1e-9
               >= (extents[a] + extents[b]) / 2 + clear
               for a, b in zip(kept, kept[1:]))
