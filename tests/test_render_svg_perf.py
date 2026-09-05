"""What the SVG backend does to keep the file small, and what it must not cost.

Every assertion here is a size or a count, which makes them the kind of test
that fails for a good reason as often as a bad one. That is the point: the
spellings in `render.pathdata` exist only because they are smaller, so a change
that quietly stops them being smaller is a regression even when the picture is
still right. The picture being still right is the other half, and it is checked
by reading the packed data back and comparing coordinates rather than by
comparing strings.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import pytest

from inklet.core.diagram import Diagram
from inklet.core.geom import Vec2
from inklet.core.prims import PathPrim, Subpath, TextPrim, TextLine
from inklet.render.pathdata import PACK_ABOVE, Fixed, spell_open, spell_packed
from inklet.render.svg import _fmt, to_svg

SVG = "{http://www.w3.org/2000/svg}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


# -- helpers --------------------------------------------------------------


_ARITY = {"M": 2, "L": 2, "C": 6, "Z": 0, "H": 1, "V": 1}


def absolute_points(data: str) -> list[tuple[str, list[float]]]:
    """Path data read back as absolute commands, whatever spelling it used.

    The same reader as `tests/test_svg.py`, kept here too because this file
    leans on it for the property that matters: two spellings of one path are
    the same path only if the pen visits the same points.
    """
    tokens = re.findall(r"[A-Za-z]|-?\d*\.\d+|-?\d+", data)
    out: list[tuple[str, list[float]]] = []
    letter, at = "", 0
    x = y = start_x = start_y = 0.0
    while at < len(tokens):
        if tokens[at].isalpha():
            letter, at = tokens[at], at + 1
        elif letter in ("M", "m"):
            letter = "L" if letter == "M" else "l"
        upper = letter.upper()
        take = _ARITY[upper]
        values = [float(v) for v in tokens[at:at + take]]
        at += take
        relative = letter.islower()
        if upper == "Z":
            out.append(("Z", []))
            x, y = start_x, start_y
            continue
        if upper in ("H", "V"):
            moved = values[0] + ((x if upper == "H" else y) if relative else 0.0)
            x, y = (moved, y) if upper == "H" else (x, moved)
            out.append(("L", [x, y]))
            continue
        points = []
        for index in range(0, take, 2):
            points += [values[index] + (x if relative else 0.0),
                       values[index + 1] + (y if relative else 0.0)]
        if upper == "M":
            start_x, start_y = points[0], points[1]
        x, y = points[-2], points[-1]
        out.append((upper, points))
    return out


def same_path(a: str, b: str) -> bool:
    """Two spellings visit the same points, to the precision they were written.

    The reader adds relative offsets back up in binary floating point, which
    is not what the file says: the file says decimal millimetres, and it is
    those that have to match.
    """
    def rounded(data: str):
        return [(letter, [round(n, 3) for n in values])
                for letter, values in absolute_points(data)]
    return rounded(a) == rounded(b)


def zigzag(count: int) -> Diagram:
    """A path of `count` linetos, long enough to be worth packing."""
    points = tuple(Vec2(i * 0.37, (i % 3) * 1.1) for i in range(count))
    return Diagram(prim=PathPrim((Subpath(points),)))


def paths_of(svg: str) -> list[str]:
    return [el.get("d", "") for el in ET.fromstring(svg).iter(f"{SVG}path")]


# -- numbers --------------------------------------------------------------


@pytest.mark.parametrize("precision", [0, 1, 3, 6])
def test_the_two_halves_of_the_formatter_agree(precision: int) -> None:
    """`spell(units(v))` and `text(v)` are one function written twice.

    The packed spelling does its arithmetic on `units` and the open one goes
    through `text`; if the two ever disagreed about how a number rounds, the
    same path would be two different curves depending on how it was spelled.
    """
    fixed = Fixed(precision)
    values = [0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 0.0005, -0.0004999,
              12.3456789, -98.7654321, 1e-9, -1e-9, 1234.5, 1e6]
    for value in values:
        assert fixed.spell(fixed.units(value)) == fixed.text(value)
        assert _fmt(value, precision) == fixed.text(value)


def test_no_number_is_ever_negative_zero_or_an_exponent() -> None:
    fixed = Fixed(3)
    assert fixed.text(-1e-9) == "0"
    assert fixed.short(0) == "0"
    assert "e" not in fixed.text(1e-12) and "e" not in fixed.text(1e15)


def test_short_drops_the_leading_zero_and_spell_keeps_it() -> None:
    fixed = Fixed(3)
    assert (fixed.spell(500), fixed.short(500)) == ("0.5", ".5")
    assert (fixed.spell(-500), fixed.short(-500)) == ("-0.5", "-.5")
    assert (fixed.spell(1500), fixed.short(1500)) == ("1.5", "1.5")


def test_a_non_finite_length_is_refused_rather_than_written() -> None:
    fixed = Fixed(3)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            fixed.text(bad)
        with pytest.raises(ValueError):
            fixed.units(bad)


# -- packed path data -----------------------------------------------------


def test_packing_a_path_visits_exactly_the_same_points() -> None:
    """The property the whole packed spelling rests on."""
    fixed = Fixed(3)
    units = fixed.units
    # A shape drawn where shapes are drawn: far from the origin, in small
    # steps. That is the case the relative frame is for, and the case where a
    # coordinate written from the origin is mostly leading digits.
    commands = [("M", (units(103.14159), units(-72.71828)))]
    x, y = 103.14159, -72.71828
    for step in range(60):
        x, y = x + 1.7, y + (step % 4) * 0.05
        commands.append(("L", (units(x), units(y))))
        commands.append(("C", (units(x + 0.3), units(y + 0.11),
                               units(x + 0.7), units(y - 0.21),
                               units(x + 1.3), units(y + 0.04))))
        x += 1.3
        y += 0.04
    commands.append(("Z", ()))
    commands.append(("M", (units(-40.0), units(17.5))))
    commands.append(("L", (units(-40.0), units(19.5))))     # a vertical
    commands.append(("L", (units(-12.25), units(19.5))))    # a horizontal
    commands.append(("Z", ()))

    packed = spell_packed(commands, fixed)
    assert same_path(packed, spell_open(commands, fixed))
    assert len(packed) < len(spell_open(commands, fixed)) * 0.7


def test_the_packed_spelling_uses_the_grammar_it_claims_to() -> None:
    fixed = Fixed(3)
    units = fixed.units
    square = [("M", (units(1.0), units(1.0))),
              ("L", (units(3.0), units(1.0))),
              ("L", (units(3.0), units(2.5))),
              ("L", (units(1.0), units(2.5))),
              ("Z", ())]
    assert spell_packed(square, fixed) == "m1 1h2v1.5h-2z"


def test_a_zero_length_segment_still_puts_a_command_in_the_data() -> None:
    """A repeated point is a command a round linecap can see; dropping it
    would be a change to the drawing, not to its spelling."""
    fixed = Fixed(3)
    units = fixed.units
    repeat = [("M", (units(2.0), units(2.0))), ("L", (units(2.0), units(2.0)))]
    assert spell_packed(repeat, fixed) == "m2 2v0"
    assert absolute_points("m2 2v0") == [("M", [2.0, 2.0]), ("L", [2.0, 2.0])]


# -- how much of the file each spelling is --------------------------------


def test_auto_packs_the_long_paths_and_leaves_the_short_ones_readable() -> None:
    figure = Diagram(children=(zigzag(4), zigzag(PACK_ABOVE + 40)))
    short, long = paths_of(to_svg(figure))
    assert short.startswith("M 0 0 L 0.37 1.1")     # spelled out, absolute
    assert long.startswith("m0 0")                  # packed, relative
    # And `compact=False` is the escape hatch that spells out both.
    short, long = paths_of(to_svg(figure, compact=False))
    assert short.startswith("M 0 0 L") and long.startswith("M 0 0 L")


def test_each_spelling_is_smaller_than_the_one_above_it() -> None:
    figure = Diagram(children=(zigzag(400),))
    spelled = to_svg(figure, compact=False)
    auto = to_svg(figure)
    packed = to_svg(figure, compact=True)
    assert len(packed) < len(auto) < len(spelled)
    # The packed data is worth well over a third of the spelled-out data.
    assert len(paths_of(packed)[0]) < 0.75 * len(paths_of(spelled)[0])


def test_every_spelling_draws_the_same_path() -> None:
    figure = Diagram(children=(zigzag(400),))
    reference = paths_of(to_svg(figure, compact=False))[0]
    for svg in (to_svg(figure), to_svg(figure, compact=True)):
        assert same_path(paths_of(svg)[0], reference)


# -- attributes -----------------------------------------------------------


def test_a_translation_is_written_as_one() -> None:
    box = Diagram(prim=PathPrim((Subpath((Vec2(0, 0), Vec2(1, 1))),)))
    assert 'transform="translate(4 9)"' in to_svg(box.translated(4, 9))
    assert 'transform="translate(4)"' in to_svg(box.translated(4, 0))
    assert 'transform="scale(2)"' in to_svg(box.scaled(2))
    # Anything with a rotation or a skew in it still needs all six numbers.
    assert "matrix(" in to_svg(box.rotated(30))


def _text_node(text: str, *, lines=None) -> Diagram:
    lines = lines or (TextLine(text, 8.0, 0.0),)
    return Diagram(prim=TextPrim(lines=lines, font_family="Inter",
                                 font_size=2.8, ascent=2.0, descent=0.6))


def test_a_one_line_label_is_one_element() -> None:
    """`x` and `y` are legal on `<text>`; a lone `<tspan>` holding them is a
    DOM node per label doing nothing."""
    root = ET.fromstring(to_svg(_text_node("Hello")))
    element = next(root.iter(f"{SVG}text"))
    assert list(element) == []
    assert element.text == "Hello"
    assert element.get("x") is not None and element.get("y") is not None


def test_two_lines_still_get_a_span_each() -> None:
    node = _text_node("", lines=(TextLine("one", 8.0, 0.0),
                                 TextLine("two", 8.0, 3.5)))
    element = next(ET.fromstring(to_svg(node)).iter(f"{SVG}text"))
    assert [child.tag for child in element] == [f"{SVG}tspan"] * 2


def test_xml_space_is_only_spent_where_the_spacing_needs_it() -> None:
    plain = next(ET.fromstring(to_svg(_text_node("one two"))).iter(f"{SVG}text"))
    assert plain.get(XML_SPACE) is None
    for risky in ("two  spaces", " leading", "trailing ", "a\tb"):
        element = next(ET.fromstring(to_svg(_text_node(risky))).iter(f"{SVG}text"))
        assert element.get(XML_SPACE) == "preserve", risky


def test_a_text_does_not_restate_the_family_its_group_already_says() -> None:
    node = _text_node("Hello").styled(font_family="Inter", font_size=2.8)
    element = next(ET.fromstring(to_svg(node)).iter(f"{SVG}text"))
    assert element.get("font-family") is None
    assert element.get("font-size") is None
    # A face the group does not name is still named, or it would not be used.
    other = _text_node("Hello").styled(font_family="Helvetica")
    element = next(ET.fromstring(to_svg(other)).iter(f"{SVG}text"))
    assert element.get("font-family") == "Inter"


# -- determinism ----------------------------------------------------------


@pytest.mark.parametrize("compact", [False, "auto", True])
def test_the_same_tree_renders_to_the_same_bytes_twice(compact) -> None:
    figure = Diagram(children=(zigzag(200).translated(3, 4),
                               _text_node("caption  spaced"),
                               zigzag(9).scaled(1.5)))
    first = to_svg(figure, compact=compact, title="t", background="#fff")
    second = to_svg(figure, compact=compact, title="t", background="#fff")
    assert first == second
    # And a second `Fixed` cache does not change the third rendering either.
    assert to_svg(figure, compact=compact, title="t", background="#fff") == first
