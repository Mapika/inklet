"""Path data in two spellings, and the fixed-point arithmetic under both.

`d` is where an SVG's bytes go. A shaded mesh is a few thousand paths and
almost nothing else: on `figures/drug_discovery.py` the path data is 88% of
the file, so what the numbers in it look like *is* what the file weighs.

Two spellings come out of here. The open one, `M 12.5 -3 L 14 -3 Z`, is what
someone opening the file in an editor wants to read. The packed one,
`m12.5-3h1.5z`, is the same curve in the same units, using three elisions the
grammar allows and one change of frame:

* a repeated command letter may be left out, and the pairs after a moveto are
  linetos, so a polygon needs one letter;
* no separator is needed before a minus sign;
* a coordinate under one may drop its leading zero -- `.5`, not `0.5`;
* and relative commands say where the next point is *from here*, which on any
  real drawing is a much smaller number than where it is from the origin.

The last one is the big one and it is the reason this module exists rather
than a `str.replace` over the open form. Relative coordinates are only safe if
they are exact, and floating-point differences are not: subtract rounded
millimetres one at a time and the error walks. So every coordinate is turned
into an integer count of 10**-precision millimetres *first*, and the deltas
are integer subtractions of those. Adding them back up reproduces the rounded
absolute coordinate exactly, digit for digit, at every point on the path.

What the packed spelling cannot promise is that the *renderer* adds them back
up exactly. Blink carries a path's pen in single precision, so a relative
command lands on `float32(pen) + float32(delta)` rather than on
`float32(absolute)`, and the two differ in the last bit. Measured on the
regression corpus at device scale 2: between 0.005% and 0.02% of the pixels
change, by a mean of 2 and a maximum of 35 out of 255, on the antialiased edge
of a shape and nowhere else -- a fraction of a device pixel, and no re-anchoring
interval avoids it, because the first relative step already has it. Where that
fraction is not acceptable, `compact=False` spells every coordinate out from
the origin and no renderer has anything to accumulate.
"""

from __future__ import annotations

#: One path command: its letter (`M L C Z`, absolute) and its coordinates as
#: integer counts of 10**-precision millimetres.
Command = tuple[str, tuple[int, ...]]

#: A path longer than this is packed even in the readable spelling. Nobody
#: reads a three-hundred-command outline; the shapes people do hand-edit --
#: a frame, an arrow, a callout leader -- are all far below it.
PACK_ABOVE = 32


class Fixed:
    """Millimetres as integers, and the shortest text for one.

    One instance per document, built from its `precision`. `text` is the
    formatter every number in the file goes through; `units` and `spell` are
    its two halves, exposed because the path packer needs to do arithmetic
    between them.
    """

    __slots__ = ("precision", "scale", "_spec", "_short")

    def __init__(self, precision: int) -> None:
        if precision < 0:
            raise ValueError(f"precision must not be negative: {precision}")
        self.precision = precision
        self.scale = 10 ** precision
        self._spec = f".{precision}f"
        # A drawing reuses its offsets: the 392,000 numbers in the packed
        # paths of `figures/drug_discovery.py` are 22,000 distinct strings,
        # because a mesh is built from a few thousand facets of much the same
        # size. Memoising the spelling turns eighteen out of nineteen of those
        # into a dict hit. Bounded, since a pathological figure should cost
        # time rather than memory.
        self._short: dict[int, str] = {}

    def text(self, value: float) -> str:
        """`value` rounded to `precision` decimals, as short as it goes.

        Fixed notation (never an exponent, which SVG cannot read), no trailing
        zeros, and no negative zero -- `-0` is a diff-noise generator and means
        nothing. The bounds check catches NaN as well as the infinities,
        because a NaN compares false against both of them.
        """
        if not -1e18 < value < 1e18:
            raise ValueError(f"cannot render non-finite length {value!r}")
        text = format(value, self._spec)
        if self.precision and text[-1] == "0":
            text = text.rstrip("0")
            if text[-1] == ".":
                text = text[:-1]
        return "0" if text in ("-", "-0") else text

    def units(self, value: float) -> int:
        """`value` as an integer count of 10**-precision millimetres.

        Deliberately routed through the same `format` call as `text` rather
        than through `round(value * scale)`: the two disagree on ties and on
        values a binary double cannot hold exactly, and a coordinate that
        rounds one way in the open spelling and the other in the packed one
        would make the two files different pictures.
        """
        if not -1e18 < value < 1e18:
            raise ValueError(f"cannot render non-finite length {value!r}")
        return int(format(value, self._spec).replace(".", ""))

    def spell(self, units: int) -> str:
        """The integer back to text: `12500` at precision 3 is `12.5`."""
        if units < 0:
            return "-" + self._positive(-units)
        return self._positive(units)

    def short(self, units: int) -> str:
        """`spell` with the leading zero dropped: `.5` rather than `0.5`.

        Only for path data. It is legal anywhere a number is, but in an
        attribute a reader has to look twice at it, and there it saves one
        byte in a file where nothing else does.
        """
        cache = self._short
        text = cache.get(units)
        if text is not None:
            return text
        sign, size = ("-", -units) if units < 0 else ("", units)
        whole, frac = divmod(size, self.scale)
        if frac:
            tail = str(frac).rjust(self.precision, "0").rstrip("0")
            text = f"{sign}{whole}.{tail}" if whole else f"{sign}.{tail}"
        else:
            text = f"{sign}{whole}"
        if len(cache) < 1 << 18:
            cache[units] = text
        return text

    def _positive(self, units: int) -> str:
        scale = self.scale
        if scale == 1:
            return str(units)
        whole, frac = divmod(units, scale)
        if frac == 0:
            return str(whole)
        return f"{whole}.{str(frac).rjust(self.precision, '0').rstrip('0')}"


def spell_open(commands: list[Command], fixed: Fixed) -> str:
    """`M 1 2 L 3 4 Z` -- every letter written, every coordinate absolute."""
    spell = fixed.spell
    return " ".join(
        " ".join([letter, *(spell(n) for n in numbers)]).strip()
        for letter, numbers in commands
    )


def spell_packed(commands: list[Command], fixed: Fixed) -> str:
    """`m1 2 2 2z` -- relative, elided, and the same curve.

    The cursor is tracked the way a renderer tracks it, including `Z` putting
    it back on the subpath's start, because that is what the deltas after a
    closed subpath are measured from.
    """
    short = fixed.short
    out: list[str] = []
    append = out.append
    cursor_x = cursor_y = start_x = start_y = 0
    implied = ""

    for letter, numbers in commands:
        if letter == "L":
            x, y = numbers
            dx, dy = x - cursor_x, y - cursor_y
            if dy == 0 and dx != 0:
                spelled = ("h", (short(dx),))
            elif dx == 0:
                spelled = ("v", (short(dy),))   # dy == 0 too keeps the point
            else:
                spelled = ("l", (short(dx), short(dy)))
            cursor_x, cursor_y = x, y
        elif letter == "C":
            x1, y1, x2, y2, x, y = numbers
            spelled = ("c", (short(x1 - cursor_x), short(y1 - cursor_y),
                             short(x2 - cursor_x), short(y2 - cursor_y),
                             short(x - cursor_x), short(y - cursor_y)))
            cursor_x, cursor_y = x, y
        elif letter == "M":
            x, y = numbers
            spelled = ("m", (short(x - cursor_x), short(y - cursor_y)))
            cursor_x = start_x = x
            cursor_y = start_y = y
        elif letter == "Z":
            spelled = ("z", ())
            cursor_x, cursor_y = start_x, start_y
        else:
            raise ValueError(f"unpackable path command {letter!r}")

        head, tokens = spelled
        if head != implied:
            append(head)
        # After a moveto the implied command is a lineto, which is what makes
        # a polygon one letter and n pairs; nothing may follow `z` implicitly.
        implied = "l" if head == "m" else "" if head == "z" else head
        for token in tokens:
            # `short` never ends a number in `.`, so a digit followed by
            # anything but a minus sign is the only case needing a separator.
            if out[-1][-1].isdigit() and token[0] != "-":
                append(" " + token)
            else:
                append(token)
    return "".join(out)
