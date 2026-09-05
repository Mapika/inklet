"""`to_pdf(text="embed")`: the words stay words, and land where they landed.

The outlined default is right for a submission and wrong for everything that
wants to *read* the page -- a find box, a copy-paste, a crawler, a screen
reader. Embedding is the other trade, and it has two ways to be silently
wrong. The type can be in the wrong place, because a reader advances its pen
by an integer thousandth of the em while the layout was measured in font
units; and it can be unreadable anyway, because a `/Identity-H` string is
glyph ids and a reader without a `/ToUnicode` map extracts them as mojibake.
So the assertions here are the two joins: the glyph positions reconstructed
from the content stream against what `placed_glyphs` says, and the extracted
characters against the string that was set.

`pdftotext` checks the whole chain against something that is not inklet, where
poppler is installed; the stream is parsed here either way, because a test
that only runs on one machine is a test that does not run.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import zlib
from io import BytesIO

import pytest

import inklet
from inklet.core import Diagram, Style
from inklet.render import to_pdf
from inklet.render.fontembed import embeddable, sfnt_widths
from inklet.render.glyphs import placed_glyphs
from inklet.typeset import shape
from inklet.typeset.fonts import find_font

pytest.importorskip("fontTools", reason="embedding needs fontTools.subset")

_STREAM = re.compile(rb"stream\n(.*?)\nendstream", re.S)
_TEXT_OBJECT = re.compile(r"BT\n(.*?)\nET", re.S)
_TM = re.compile(r"1 0 0 -1 (-?[\d.]+) (-?[\d.]+) Tm")
_TJ = re.compile(r"\[(.*?)\] TJ", re.S)
_TOKEN = re.compile(r"<([0-9A-F]+)>|(-?\d+)")
_BFCHAR = re.compile(r"<([0-9A-F]{4})> <([0-9A-F]+)>")

SAMPLE = "AVATAR office 0123 Wave"


def content(pdf: bytes) -> str:
    return _STREAM.search(pdf).group(1).decode("latin-1")


def streams(pdf: bytes):
    """Every stream in the file, inflated where it was deflated.

    The tests below read objects the writer compresses by default, and reading
    them uncompressed would test a different file from the one that ships.
    """
    for match in _STREAM.finditer(pdf):
        body = match.group(1)
        try:
            yield zlib.decompress(body)
        except zlib.error:
            yield body


def block(text: str = SAMPLE, **kwargs) -> Diagram:
    return Diagram(prim=shape(text, font="sans", size=5.0, **kwargs))


def pen_positions(stream: str, widths) -> list[tuple[int, float]]:
    """(glyph id, x in millimetres) for every glyph of the first text object.

    The reader's own arithmetic, done here: start at the text matrix, advance
    by the `/W` width of each glyph, and subtract each `TJ` number as a
    thousandth of the type size. If this disagrees with `placed_glyphs`, the
    page is set in the wrong places.
    """
    body = _TEXT_OBJECT.search(stream).group(1)
    size = float(re.search(r"/F\d+ ([\d.]+) Tf", body).group(1))
    x = float(_TM.search(body).group(1))
    out = []
    for hex_run, number in _TOKEN.findall(_TJ.search(body).group(1)):
        if number:
            x -= int(number) / 1000.0 * size
            continue
        for start in range(0, len(hex_run), 4):
            gid = int(hex_run[start:start + 4], 16)
            out.append((gid, x))
            x += widths[gid] / 1000.0 * size
    return out


def unicode_map(pdf: bytes) -> dict[int, str]:
    """The `/ToUnicode` CMap, read back out of the file it was written into."""
    for body in streams(pdf):
        text = body.decode("latin-1", "replace")
        if "beginbfchar" not in text:
            continue
        return {int(code, 16): bytes.fromhex(value).decode("utf-16-be")
                for code, value in _BFCHAR.findall(text)}
    raise AssertionError("no /ToUnicode CMap in the document")


def font_program(pdf: bytes) -> bytes:
    """The `/FontFile2` payload: the one stream that begins like an sfnt."""
    for body in streams(pdf):
        if body[:4] in (b"\x00\x01\x00\x00", b"true"):
            return body
    raise AssertionError("no font program in the document")


# -- the mode itself -------------------------------------------------------


def test_the_default_is_still_outlined():
    node = block()
    assert to_pdf(node) == to_pdf(node, text="outline")
    assert "BT" not in content(to_pdf(node, compress=False))


def test_an_unknown_mode_names_itself_and_the_two_that_exist():
    with pytest.raises(ValueError, match="outline, embed"):
        to_pdf(block(), text="serif")


def test_names_mode_says_what_to_use_instead():
    """The SVG default spelled at a PDF, which is a reasonable thing to try
    and has an answer: `embed` is the searchable one."""
    with pytest.raises(ValueError, match="text='embed'"):
        to_pdf(block(), text="names")


def test_embedded_output_is_deterministic():
    node = block()
    assert to_pdf(node, text="embed") == to_pdf(node, text="embed")


# -- the font objects ------------------------------------------------------


def test_the_document_carries_a_type0_font_over_a_cid_font():
    pdf = to_pdf(block(), text="embed").decode("latin-1")
    assert "/Subtype /Type0" in pdf and "/Encoding /Identity-H" in pdf
    assert "/Subtype /CIDFontType2" in pdf
    # The line that makes the shaped glyph ids usable as codes.
    assert "/CIDToGIDMap /Identity" in pdf
    assert "/FontFile2" in pdf and "/ToUnicode" in pdf
    assert "/Registry (Adobe) /Ordering (Identity)" in pdf


def test_the_font_name_carries_a_subset_tag():
    pdf = to_pdf(block(), text="embed").decode("latin-1")
    name = re.search(r"/BaseFont /([A-Z]{6})\+(\S+)", pdf)
    assert name, "a subset must be tagged, or two of them collide in one reader"


def test_the_embedded_program_is_a_real_font_a_reader_could_open():
    from fontTools.ttLib import TTFont

    pdf = to_pdf(block(), text="embed")
    data = font_program(pdf)
    assert len(data) == int(re.search(rb"/Length1 (\d+)", pdf).group(1))
    assert "glyf" in TTFont(BytesIO(data), lazy=True)


def test_the_embedded_program_carries_no_clock():
    """`head.modified` is rewritten from the wall clock at save time unless the
    face is opened with `recalcTimestamp=False`, and three bytes of the clock
    in every subset is enough to break byte-identical output across processes.
    Read raw, because opening it any other way stamps it again."""
    from fontTools.ttLib import TTFont

    head = TTFont(BytesIO(font_program(to_pdf(block(), text="embed"))),
                  lazy=True).reader["head"]
    assert struct.unpack(">qq", head[20:36]) == (0, 0)


def test_every_glyph_the_stream_names_exists_in_the_subset():
    """`retain_gids` is what makes the ids in the content stream mean anything;
    without it the subsetter renumbers and the page draws other letters."""
    node = block()
    glyphs = placed_glyphs(node.prim)
    stream = content(to_pdf(node, compress=False, text="embed"))
    widths = sfnt_widths(glyphs[0].font_path, glyphs[0].font_index)
    assert [gid for gid, _ in pen_positions(stream, widths)] == [
        glyph.gid for glyph in glyphs]


def test_the_width_array_lists_every_glyph_that_is_used():
    node = block()
    glyphs = placed_glyphs(node.prim)
    widths = sfnt_widths(glyphs[0].font_path, glyphs[0].font_index)
    array = re.search(r"/W \[(.*?)\] /CIDToGIDMap",
                      to_pdf(node, text="embed").decode("latin-1")).group(1)
    listed: dict[int, int] = {}
    for start, run in re.findall(r"(\d+) \[([\d ]+)\]", array):
        for offset, value in enumerate(run.split()):
            listed[int(start) + offset] = int(value)
    for glyph in glyphs:
        assert listed[glyph.gid] == widths[glyph.gid]


# -- where the glyphs land -------------------------------------------------


def test_the_reader_lands_every_glyph_where_the_shaper_put_it():
    """The `TJ` chain against `placed_glyphs`, to within the half micrometre
    the stream's own number format rounds the text matrix to -- the same
    rounding the outlined path gets. Without the adjustments the error is not
    a rounding but an accumulation: `/W` is an integer thousandth of the em,
    so a forty-character label ends a visible fraction of a millimetre from
    where the outlined one ends."""
    node = block("Wave AVATAR office 0123456789 kerning")
    glyphs = placed_glyphs(node.prim)
    widths = sfnt_widths(glyphs[0].font_path, glyphs[0].font_index)
    stream = content(to_pdf(node, compress=False, text="embed"))
    for (gid, x), glyph in zip(pen_positions(stream, widths), glyphs):
        assert gid == glyph.gid
        assert abs(x - glyph.origin.x) < 6e-4


def test_a_second_line_is_a_second_text_object():
    """One `Tm` per baseline: a text object holds one line, because the y is
    in the matrix and not in the string."""
    stream = content(to_pdf(block("one\ntwo\nthree"), compress=False,
                            text="embed"))
    assert len(_TEXT_OBJECT.findall(stream)) == 3


# -- reading it back -------------------------------------------------------


def test_the_unicode_map_spells_the_string_that_was_set():
    node = block()
    pdf = to_pdf(node, text="embed")
    table = unicode_map(pdf)
    spelled = "".join(table.get(glyph.gid, "")
                      for glyph in placed_glyphs(node.prim))
    assert spelled == SAMPLE


def test_a_ligature_extracts_as_the_letters_it_replaced():
    """One glyph, two characters. Without the cluster text behind
    `/ToUnicode` a copied caption reads "of ce"."""
    node = block("office")
    table = unicode_map(to_pdf(node, text="embed"))
    assert "".join(table.get(g.gid, "") for g in placed_glyphs(node.prim)) == "office"


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="poppler's pdftotext is not installed")
def test_poppler_extracts_the_text(tmp_path):
    """The whole chain against something that is not inklet."""
    path = tmp_path / "live.pdf"
    path.write_bytes(to_pdf(block("Two-photon imaging"), text="embed"))
    out = subprocess.run(["pdftotext", str(path), "-"],
                         capture_output=True, text=True, check=True)
    assert "Two-photon imaging" in out.stdout.replace("\n", " ")


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="poppler's pdftotext is not installed")
def test_the_outlined_file_has_nothing_to_extract(tmp_path):
    """Stated as a fact about the default, not as a complaint: this is what
    `text="embed"` is for."""
    path = tmp_path / "outlined.pdf"
    path.write_bytes(to_pdf(block("Two-photon imaging")))
    out = subprocess.run(["pdftotext", str(path), "-"],
                         capture_output=True, text=True, check=True)
    assert "Two-photon" not in out.stdout


# -- sharing, and the faces that cannot come --------------------------------


def test_three_pages_in_one_family_embed_one_subset():
    pages = [block("page one"), block("page two"), block("page three")]
    pdf = to_pdf(pages, text="embed").decode("latin-1")
    assert pdf.count("/FontFile2") == 1
    assert pdf.count("/Subtype /Type0") == 1


def test_a_bold_run_is_a_second_face_and_a_second_subset():
    node = Diagram(prim=inklet.typeset.shape("plain **bold** plain", size=5.0))
    pdf = to_pdf(node, text="embed").decode("latin-1")
    assert pdf.count("/FontFile2") == 2


def _cff_family() -> str | None:
    """A family this machine resolves to a CFF face, or None."""
    for name in ("Nimbus Sans", "Roboto Slab", "TeX Gyre Cursor", "Z003"):
        try:
            face = find_font(name)
        except Exception:                                 # noqa: BLE001
            continue
        if not embeddable(face.path, face.index):
            return name
    return None


def test_a_face_that_cannot_be_a_fontfile2_is_outlined_instead():
    """A CFF face would need a CIDFontType0 and its own font program format.
    Outlining that one block is the same picture and only that block stops
    being selectable, which beats refusing to write the file."""
    family = _cff_family()
    if family is None:
        pytest.skip("no CFF face installed to fall back from")
    node = Diagram(prim=shape("Fallback", font=family, size=5.0))
    stream = content(to_pdf(node, compress=False, text="embed"))
    assert "BT" not in stream
    assert " c\n" in stream or " l\n" in stream       # it drew the outlines


# -- the halo, in the mode where it is not a stroked text object -------------


def test_a_haloed_label_still_extracts_once():
    node = Diagram(prim=shape("Halo", font="sans", size=5.0),
                   style=Style(halo=0.4))
    stream = content(to_pdf(node, compress=False, text="embed"))
    assert stream.count("BT") == 1
