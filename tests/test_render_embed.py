"""`text="embed"`: the face travels inside the file, and the text stays text.

Outlining makes a figure font-independent by throwing the font away, which
costs the selection, the search and the accessibility tree along with it.
Embedding keeps all three: each face used is subset down to the characters
this document actually asked for, wrapped as a webfont, and installed under a
name of the document's own so it cannot be confused with -- or overridden by --
whatever the reader has locally under the same family.

The failure this guards against is silent: a `<text>` that names a family the
file does not carry falls back to something the layout was never measured
against, and every advance in the figure is then a lie. So the assertions here
are about the join between the two -- that the family the text names is the
family the `@font-face` declares.
"""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import replace
from io import BytesIO

import pytest

from inklet.core import Diagram
from inklet.render.svg import to_svg
from inklet.typeset import shape

pytest.importorskip("fontTools", reason="embedding needs fontTools.subset")

from fontTools.ttLib import TTFont           # noqa: E402

from inklet.render import fontembed              # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"
_FAMILY = re.compile(r'font-family:\s*"?([\w-]+)"?')
_SRC = re.compile(r"src:\s*url\(data:font/(\w+);base64,([A-Za-z0-9+/=]+)\)")


def block(text: str = "Embedded", **kwargs) -> Diagram:
    return Diagram(prim=shape(text, font="DejaVu Sans", size=4.0, **kwargs))


def style_of(document: str) -> str:
    root = ET.fromstring(document)
    found = root.find(f"{SVG}defs/{SVG}style") or root.find(f"{SVG}style")
    return found.text if found is not None else ""


# -- the join between the text and the face --------------------------------


def test_the_text_names_the_family_the_file_declares():
    document = to_svg(block(), text="embed")
    declared = _FAMILY.findall(style_of(document))
    assert len(declared) == 1
    element = ET.fromstring(document).find(f".//{SVG}text")
    assert element.get("font-family") == declared[0]


def test_the_embedded_name_is_not_the_installed_one():
    """A local face under the same name would otherwise win or lose by
    cascade order, and the reader would never know which they got."""
    document = to_svg(block(), text="embed")
    assert "DejaVu Sans" not in _FAMILY.findall(style_of(document))[0]


def test_text_stays_text():
    root = ET.fromstring(to_svg(block(), text="embed"))
    assert list(root.iter(f"{SVG}text"))
    assert list(root.iter(f"{SVG}use")) == []


def test_the_face_travels_as_a_webfont_data_uri():
    match = _SRC.search(style_of(to_svg(block(), text="embed")))
    assert match is not None
    flavour, payload = match.groups()
    assert flavour in ("woff", "woff2")
    assert len(payload) > 100


def test_a_face_used_twice_is_embedded_once():
    page = Diagram(children=(block("one"), block("two")))
    assert len(_SRC.findall(style_of(to_svg(page, text="embed")))) == 1


def test_the_declaration_precedes_the_text_that_needs_it():
    document = to_svg(block(), text="embed")
    assert document.index("@font-face") < document.index("<text")


# -- the subset ------------------------------------------------------------


def test_only_the_characters_the_figure_asked_for_come_along():
    small = fontembed.subset_face(_face_path(), 0, _points("ab"))
    large = fontembed.subset_face(_face_path(), 0, _points("abcdefghij"))
    assert small.glyphs < large.glyphs
    assert len(small.data) < len(large.data)


def test_the_subset_is_smaller_than_outlining_the_same_page():
    page = block("A caption of the length a real figure carries, twice over. "
                 * 4, width=80.0)
    embedded = len(to_svg(page, text="embed"))
    outlined = len(to_svg(page, text="outline"))
    assert embedded < outlined


def test_the_same_request_yields_the_same_bytes():
    """No build timestamp, no run-dependent glyph order: `head.modified` is
    zeroed and the codepoints are sorted before the subsetter sees them."""
    first = fontembed.subset_face(_face_path(), 0, _points("hello world"))
    fontembed._subset_face.cache_clear()
    second = fontembed.subset_face(_face_path(), 0, _points("dlrow olleh"))
    assert first.data == second.data


def test_the_embedded_face_carries_no_clock():
    """The regression behind the flake in the test above, pinned where it can
    be seen: `head.modified` is rewritten from the wall clock *at save time*
    unless the face is opened with `recalcTimestamp=False`, so zeroing the
    field after subsetting zeroed something that was then filled in again.
    Two renders in one second agreed and two renders either side of one did
    not, and the subset being memoised meant a single process rarely noticed.

    Read raw out of the reader: opening the table any other way recompiles it
    and stamps the clock into the answer.
    """
    subset = fontembed.subset_face(_face_path(), 0, _points("timestamp"))
    head = TTFont(BytesIO(subset.data), lazy=True).reader["head"]
    assert struct.unpack(">qq", head[20:36]) == (0, 0)


def test_the_document_is_byte_identical_on_a_second_render():
    page = block("Embedded twice")
    assert to_svg(page, text="embed") == to_svg(page, text="embed")


def test_the_rule_pins_the_whole_weight_range():
    """Otherwise a viewer asked for bold synthesises it by smearing the
    regular face, and the figure is measured in one weight and drawn in a
    fatter one."""
    assert "font-weight:100 900" in style_of(to_svg(block(), text="embed"))


# -- when it cannot be done ------------------------------------------------


def test_a_face_that_cannot_be_opened_keeps_its_real_family_name():
    """Better a `<text>` naming a family the reader may have than one naming
    a family that is nowhere in the file."""
    prim = shape("fallback", font="DejaVu Sans", size=4.0)
    broken = replace(prim, font_path="/nowhere/x.ttf")
    document = to_svg(Diagram(prim=broken), text="embed")
    element = ET.fromstring(document).find(f".//{SVG}text")
    assert element.get("font-family") == prim.font_family
    assert "@font-face" not in document


def _face_path() -> str:
    return shape("a", font="DejaVu Sans", size=4.0).font_path


def _points(text: str) -> frozenset[int]:
    return frozenset(ord(c) for c in text)
