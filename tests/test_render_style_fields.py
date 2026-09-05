"""The style fields core added on 2026-08-23, in both backends.

`fill_rule`, `fill_opacity`, `stroke_opacity`, `font_style` and the text halo
were all in core before any backend read them, which is the state a field must
not stay in: a caller sets one, sees nothing, and concludes the library is
broken. One test per field per backend, and one that says the default is still
the default -- the corpus renders byte for byte what it rendered before,
because none of these is set anywhere in it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from inklet.core import Diagram, PathPrim, RectPrim, Style, Subpath, Vec2
from inklet.render import to_pdf, to_svg
from inklet.typeset import shape

SVG = "{http://www.w3.org/2000/svg}"
_STREAM = re.compile(rb"stream\n(.*?)\nendstream", re.S)


def content(pdf: bytes) -> str:
    return _STREAM.search(pdf).group(1).decode("latin-1")


def ops(node: Diagram, **kwargs) -> str:
    return content(to_pdf(node, compress=False, **kwargs))


def ring() -> PathPrim:
    """Two same-wound squares: a washer under even-odd, a solid one under
    nonzero. The rule is the only thing that can tell them apart."""
    def square(r: float) -> Subpath:
        return Subpath((Vec2(-r, -r), Vec2(r, -r), Vec2(r, r), Vec2(-r, r)),
                       closed=True)
    return PathPrim((square(10.0), square(4.0)), filled=True)


def label(text: str = "Halo", **style) -> Diagram:
    return Diagram(prim=shape(text, font="DejaVu Sans", size=4.0),
                   style=Style(**style))


# -- fill_rule -------------------------------------------------------------


def test_svg_writes_the_fill_rule_only_when_it_is_not_the_default():
    plain = ET.fromstring(to_svg(Diagram(prim=ring())))
    assert plain.find(f".//{SVG}path").get("fill-rule") is None

    holed = PathPrim(ring().subpaths, filled=True, fill_rule="evenodd")
    element = ET.fromstring(to_svg(Diagram(prim=holed))).find(f".//{SVG}path")
    assert element.get("fill-rule") == "evenodd"


def test_svg_leaves_the_fill_rule_off_an_unfilled_path():
    """A stroke has no interior to rule on, and the attribute inherits: on a
    `<g>`-folded leaf it would reach shapes that do have one."""
    stroked = PathPrim(ring().subpaths, filled=False, fill_rule="evenodd")
    element = ET.fromstring(to_svg(Diagram(prim=stroked))).find(f".//{SVG}path")
    assert element.get("fill-rule") is None


def test_pdf_paints_an_even_odd_path_with_the_starred_operator():
    node = Diagram(prim=ring(), style=Style(fill="#000000", stroke="#ff0000"))
    assert "\nB\n" in "\n" + ops(node) + "\n"

    holed = Diagram(prim=PathPrim(ring().subpaths, filled=True,
                                  fill_rule="evenodd"),
                    style=Style(fill="#000000", stroke="#ff0000"))
    assert "\nB*\n" in "\n" + ops(holed) + "\n"


def test_pdf_fills_an_even_odd_path_with_f_star():
    holed = Diagram(prim=PathPrim(ring().subpaths, filled=True,
                                  fill_rule="evenodd"),
                    style=Style(fill="#000000"))
    assert "\nf*\n" in "\n" + ops(holed) + "\n"


# -- fill_opacity / stroke_opacity -----------------------------------------


def band() -> Diagram:
    """A confidence band: a translucent fill under a solid line, which is the
    single node these two fields exist to make possible."""
    return Diagram(prim=RectPrim(20.0, 6.0),
                   style=Style(fill="#0072b2", stroke="#0072b2",
                               stroke_width=0.3, fill_opacity=0.2))


def test_svg_writes_the_two_paint_opacities():
    element = ET.fromstring(to_svg(band())).find(f".//{SVG}rect")
    assert element.get("fill-opacity") == "0.2"
    assert element.get("opacity") is None

    node = Diagram(prim=RectPrim(4, 4), style=Style(stroke="#000",
                                                    stroke_opacity=0.5))
    assert ET.fromstring(to_svg(node)).find(
        f".//{SVG}rect").get("stroke-opacity") == "0.5"


def test_pdf_gives_the_fill_and_the_stroke_their_own_alphas():
    pdf = to_pdf(band(), compress=False)
    assert "/ca 0.2 /CA 1" in pdf.decode("latin-1")
    assert "/GS0 gs" in content(pdf)


def test_pdf_multiplies_a_paint_opacity_into_the_group_opacity():
    """SVG and PDF both define these as multiplying, so a band inside a
    subtree faded to 50% is 10% and not 20%."""
    faded = Diagram(children=(band(),), style=Style(opacity=0.5))
    assert "/ca 0.1 /CA 0.5" in to_pdf(faded, compress=False).decode("latin-1")


def test_a_plain_group_opacity_still_writes_one_alpha_pair():
    """The state this backend has always written, unchanged: `ca` and `CA` the
    same number, which is what keeps the corpus PDFs byte-identical."""
    node = Diagram(prim=RectPrim(4, 4), style=Style(fill="#000", opacity=0.4))
    assert "/ca 0.4 /CA 0.4" in to_pdf(node, compress=False).decode("latin-1")


# -- font_style ------------------------------------------------------------


def test_svg_writes_font_style_on_live_text():
    node = label(font_style="italic")
    element = ET.fromstring(to_svg(node)).find(f".//{SVG}g")
    assert element.get("font-style") == "italic"


def test_font_style_is_dropped_once_the_text_is_geometry():
    """Nothing under an outlined node is text, so a type property on it is
    bytes addressing nobody -- the same rule the family and the size follow."""
    document = to_svg(label(font_style="italic"), text="outline")
    assert "font-style" not in document


# -- the halo --------------------------------------------------------------


def test_svg_haloes_live_text_with_paint_order():
    element = ET.fromstring(to_svg(label(halo=0.4))).find(f".//{SVG}text")
    assert element.get("paint-order") == "stroke"
    assert element.get("stroke") == "#ffffff"
    assert element.get("stroke-width") == "0.4"
    assert element.get("stroke-linejoin") == "round"


def test_an_unhaloed_label_still_refuses_the_stroke_it_inherits():
    element = ET.fromstring(to_svg(label())).find(f".//{SVG}text")
    assert element.get("stroke") == "none"
    assert element.get("paint-order") is None


def test_the_halo_takes_the_page_colour_and_then_its_own():
    document = to_svg(label(halo=0.4), background="#101010")
    assert ET.fromstring(document).find(f".//{SVG}text").get("stroke") == "#101010"

    document = to_svg(label(halo=0.4, halo_color="#c1121f"), background="#101010")
    assert ET.fromstring(document).find(f".//{SVG}text").get("stroke") == "#c1121f"


def test_outlined_text_haloes_in_a_pass_of_its_own():
    """Every halo before every fill. `paint-order` on the group would stroke
    and fill each `<use>` in turn, and one letter's halo would then bite into
    the ink of the one before it."""
    root = ET.fromstring(to_svg(label("AV", halo=0.4), text="outline"))
    groups = [g for g in root.iter(f"{SVG}g") if len(g)]
    halo, ink = groups[-2], groups[-1]
    assert halo.get("fill") == "none" and halo.get("stroke") == "#ffffff"
    assert ink.get("stroke") == "none"
    assert ([u.get(f"{{http://www.w3.org/1999/xlink}}href") for u in halo]
            == [u.get(f"{{http://www.w3.org/1999/xlink}}href") for u in ink])


def test_pdf_strokes_the_halo_under_the_glyphs():
    stream = ops(label(halo=0.4))
    assert "1 1 1 RG" in stream and "0.4 w" in stream
    # The stroke pass comes first, or it is not a halo but an outline.
    assert stream.index("0.4 w") < stream.index("\nf")


def test_a_pdf_halo_is_geometry_even_when_the_text_is_live():
    """`Tr 1` would put the halo in a second text object and the words would
    extract twice; the stroke pass is a path in both modes."""
    stream = ops(label(halo=0.4), text="embed")
    assert stream.count("BT") == 1
    assert "0.4 w" in stream and stream.index("0.4 w") < stream.index("BT")


def test_a_halo_of_zero_is_no_halo():
    assert ET.fromstring(to_svg(label(halo=0.0))).find(
        f".//{SVG}text").get("paint-order") is None


# -- nothing moved ---------------------------------------------------------


@pytest.mark.parametrize("mode", ["names", "outline"])
def test_a_tree_that_sets_none_of_them_renders_what_it_always_did(mode):
    """The whole reason each of these defaults to None: a figure that does not
    ask for one must not pay a byte for it."""
    node = Diagram(children=(
        Diagram(prim=RectPrim(10, 4), style=Style(fill="#eee", stroke="#333")),
        label("Caption"),
    ))
    document = to_svg(node, text=mode)
    for attribute in ("fill-rule", "fill-opacity", "stroke-opacity",
                      "font-style", "paint-order"):
        assert attribute not in document
