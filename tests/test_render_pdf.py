"""The PDF backend.

A PDF that a viewer silently declines to open looks exactly like one that was
never written, so half of this file is about the file *structure* -- the
cross-reference table has to point at real objects, at real byte offsets -- and
the other half about the content stream saying what the SVG backend says. Where
`pdftoppm` is installed the last test rasterises the thing and looks at it,
which is the only assertion that covers the two together.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess

import pytest

import inklet
from inklet.core import Diagram, Rect, Vec2
from inklet.core.prims import (
    EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Prim, RectPrim, Subpath,
)
from inklet.render import save_pdf, to_pdf
from inklet.render.pdf import PT_PER_MM
from inklet.typeset import shape

_STREAM = re.compile(rb"stream\n(.*?)\nendstream", re.S)
_XREF_ENTRY = re.compile(rb"^(\d{10}) 00000 n $")


# -- helpers --------------------------------------------------------------


def content(pdf: bytes) -> str:
    """The page's operator stream. Only meaningful with `compress=False`."""
    return _STREAM.search(pdf).group(1).decode("latin-1")


def figure() -> inklet.Figure:
    fig = inklet.figure(width="89mm")
    top = inklet.box("Two-photon\nimaging")
    bottom = inklet.box("ROI extraction")
    fig.add(inklet.vstack([top, bottom], gap=6))
    fig.link(top, bottom, label="dF/F")
    return fig


def pdf_of(node: Diagram, **kwargs) -> str:
    return content(to_pdf(node, compress=False, **kwargs))


# -- file structure --------------------------------------------------------


def test_the_cross_reference_table_points_at_real_objects():
    """A wrong offset here is the difference between a file and a coaster, and
    every viewer reports it as one unhelpful line."""
    pdf = to_pdf(figure().build()[0])
    assert pdf.startswith(b"%PDF-1.4\n") and pdf.endswith(b"%%EOF\n")

    start = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    table = pdf[start:].split(b"trailer")[0].split(b"\n")
    assert table[0] == b"xref"
    count = int(table[1].split()[1])
    assert table[2] == b"0000000000 65535 f "

    for number, row in enumerate(table[3:3 + count - 1], start=1):
        match = _XREF_ENTRY.match(row)
        assert match, f"malformed xref row {row!r}"
        offset = int(match.group(1))
        assert pdf[offset:].startswith(f"{number} 0 obj\n".encode("ascii"))

    assert f"/Size {count}".encode("ascii") in pdf.rsplit(b"trailer", 1)[1]


def test_output_is_deterministic():
    root, _ = figure().build()
    assert to_pdf(root) == to_pdf(root)
    # Nothing dated and nothing random: the two obvious ways to break that.
    assert b"CreationDate" not in to_pdf(root)


def test_the_file_id_distinguishes_two_documents():
    a = re.search(rb"/ID \[<([0-9A-F]+)>", to_pdf(figure().build()[0])).group(1)
    b = re.search(rb"/ID \[<([0-9A-F]+)>", to_pdf(inklet.figure().build()[0])).group(1)
    assert a != b


def test_the_page_is_the_size_the_svg_says_it_is():
    fig = inklet.figure(width="183mm", height="60mm")
    fig.add(inklet.box("panel"))
    root, _ = fig.build()
    box = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", to_pdf(root))
    assert float(box.group(1)) == pytest.approx(183 * PT_PER_MM, abs=1e-3)
    assert float(box.group(2)) == pytest.approx(60 * PT_PER_MM, abs=1e-3)


def test_saving_writes_a_pdf(tmp_path):
    target = tmp_path / "figure.pdf"
    save_pdf(figure().build()[0], target)
    assert target.read_bytes().startswith(b"%PDF-1.4")


# -- the page transform ----------------------------------------------------


def test_millimetres_go_in_and_points_come_out():
    """One `cm` sets the whole page up: 1 user unit = 1 mm, y down, content
    origin top-left. Everything after it -- including stroke widths -- is mm."""
    fig = inklet.figure(width="50mm", height="40mm")
    fig.add(inklet.box("x"))
    stream = pdf_of(fig.build()[0])
    matrix = [float(v) for v in stream.split(" cm")[0].split()[-6:]]
    assert matrix[0] == pytest.approx(PT_PER_MM, abs=1e-4)
    assert matrix[3] == pytest.approx(-PT_PER_MM, abs=1e-4)
    assert matrix[5] == pytest.approx(40 * PT_PER_MM, abs=1e-3)


def test_a_hairline_is_a_hairline():
    node = inklet.polyline([(0, 0), (10, 0)], stroke="#000000", stroke_width=0.25)
    assert "0.25 w" in pdf_of(node)


# -- prims -----------------------------------------------------------------


def test_a_rectangle_is_a_rectangle_and_a_rounded_one_is_not():
    plain = pdf_of(Diagram(prim=RectPrim(10, 6)).styled(fill="#ff0000"))
    assert "-5 -3 10 6 re" in plain and " c\n" not in plain
    round_ = pdf_of(Diagram(prim=RectPrim(10, 6, radius=1)).styled(fill="#ff0000"))
    assert " re" not in round_ and " c" in round_


def test_colours_become_device_rgb():
    stream = pdf_of(Diagram(prim=RectPrim(4, 4)).styled(fill="#ff0000",
                                                        stroke="#0000ff"))
    assert "1 0 0 rg" in stream and "0 0 1 RG" in stream
    assert stream.strip().endswith("Q")
    assert "\nB\n" in stream               # filled and stroked in one operator


def test_an_unfilled_path_is_only_stroked():
    stream = pdf_of(inklet.polyline([(0, 0), (5, 5)], stroke="#000000"))
    assert stream.rstrip().splitlines()[-2] == "S"


def test_a_path_with_no_paint_still_gets_consumed():
    """PDF has no implicit path discard: leaving one on the stack merges it
    into whatever the next operator paints."""
    assert "\nn\n" in pdf_of(inklet.polyline([(0, 0), (5, 5)], fill="none",
                                          stroke="none"))


def test_every_contour_of_a_path_is_laid_in():
    """`any()` short-circuits, and a version of this backend that used it drew
    the first letter of every label and nothing else."""
    node = Diagram(prim=PathPrim(
        (Subpath((Vec2(0, 0), Vec2(1, 0), Vec2(1, 1)), closed=True),
         Subpath((Vec2(3, 3), Vec2(4, 3), Vec2(4, 4)), closed=True)), filled=True))
    assert pdf_of(node).count(" m\n") == 2


def test_a_phantom_leaves_no_ink():
    node = Diagram(prim=PhantomPrim(Rect(0, 0, 10, 10)))
    assert pdf_of(node).count("q\n") == 0


def test_an_unknown_primitive_is_named_rather_than_skipped():
    class Sprite(Prim):
        def envelope(self):
            return RectPrim(1, 1).envelope()

        def trace(self):
            return RectPrim(1, 1).trace()

    with pytest.raises(NotImplementedError, match="Sprite"):
        to_pdf(Diagram(prim=Sprite()))


# -- style -----------------------------------------------------------------


def test_dashes_caps_and_joins_reach_the_stream():
    node = inklet.polyline([(0, 0), (10, 0)], stroke="#000000", stroke_dash=(1.2, 0.8),
                        stroke_linecap="round", stroke_linejoin="bevel")
    stream = pdf_of(node)
    assert "[1.2 0.8] 0 d" in stream and "1 J" in stream and "2 j" in stream


def test_opacity_becomes_an_extended_graphics_state():
    pdf = to_pdf(Diagram(prim=EllipsePrim(3, 3)).styled(fill="#ff0000", opacity=0.4),
                 compress=False)
    assert b"/ExtGState << /GS0 << /ca 0.4 /CA 0.4 >> >>" in pdf
    assert "/GS0 gs" in content(pdf)


def test_a_transform_is_written_once_per_item():
    node = Diagram(prim=RectPrim(2, 2)).translated(7, 3)
    assert "1 0 0 1 7 3 cm" in pdf_of(node)
    assert pdf_of(Diagram(prim=RectPrim(2, 2))).count(" cm") == 1  # the page's own


# -- text ------------------------------------------------------------------


def test_text_is_outlined_and_no_font_is_embedded():
    stream = pdf_of(Diagram(prim=shape("Encoder", size=inklet.pt(8))))
    assert "/Font" not in stream and " Tj" not in stream and " BT" not in stream
    # One `m` per contour: seven letters have more contours than letters.
    assert stream.count(" m\n") >= 7


def test_the_text_colour_wins_over_the_shape_fill():
    node = Diagram(children=(Diagram(prim=shape("x", size=inklet.pt(8))),)) \
        .styled(fill="#ff0000", text_fill="#ffffff")
    stream = pdf_of(node)
    assert "1 1 1 rg" in stream and "1 0 0 rg" not in stream


def test_glyphs_are_filled_and_never_stroked():
    node = Diagram(children=(Diagram(prim=shape("x", size=inklet.pt(8))),)) \
        .styled(stroke="#000000", stroke_width=0.5)
    stream = pdf_of(node)
    assert "RG" not in stream and stream.rstrip().splitlines()[-2] == "f"


def test_a_straight_glyph_segment_is_written_as_a_line():
    """Glyph contours arrive with their straight parts as degenerate cubics,
    because `Subpath.curves` is all-or-nothing. Writing those back out as `c`
    would be three times the numbers for the same ink."""
    stream = pdf_of(Diagram(prim=shape("H", size=inklet.pt(12))))
    assert " c\n" not in stream and stream.count(" l\n") >= 11


# -- images ----------------------------------------------------------------


def png(path, size=(8, 6), mode="RGBA"):
    image = pytest.importorskip("PIL.Image")
    picture = image.new(mode, size, (200, 30, 30, 128))
    picture.save(path)
    return str(path)


def test_a_png_is_decoded_and_its_alpha_becomes_a_soft_mask(tmp_path):
    source = png(tmp_path / "dot.png")
    node = Diagram(prim=ImagePrim(source, width=10, height=7.5))
    pdf = to_pdf(node, compress=False)
    assert b"/Subtype /Image /Width 8 /Height 6" in pdf
    assert b"/ColorSpace /DeviceRGB" in pdf and b"/SMask" in pdf
    assert b"/ColorSpace /DeviceGray" in pdf
    assert "/Im0 Do" in content(pdf)


def test_an_opaque_png_carries_no_soft_mask(tmp_path):
    source = png(tmp_path / "flat.png", mode="RGB")
    assert b"/SMask" not in to_pdf(Diagram(prim=ImagePrim(source, 10, 7.5)))


def test_a_jpeg_is_passed_through_rather_than_re_encoded(tmp_path):
    source = png(tmp_path / "photo.jpg", mode="RGB")
    pdf = to_pdf(Diagram(prim=ImagePrim(source, 10, 7.5)))
    assert b"/DCTDecode" in pdf
    assert open(source, "rb").read() in pdf


def test_an_image_lands_the_right_way_up(tmp_path):
    """A PDF image fills the unit square with its first row at the *top*, and
    inklet's y grows down. Get the sign wrong and every photograph is mirrored."""
    source = png(tmp_path / "dot.png")
    stream = pdf_of(Diagram(prim=ImagePrim(source, width=10, height=8)))
    assert "10 0 0 -8 -5 4 cm" in stream


def test_the_same_raster_placed_twice_is_embedded_once(tmp_path):
    source = png(tmp_path / "dot.png")
    node = Diagram(children=(Diagram(prim=ImagePrim(source, 5, 4)),
                             Diagram(prim=ImagePrim(source, 5, 4)).translated(6, 0)))
    pdf = to_pdf(node, compress=False)
    assert content(pdf).count("/Im0 Do") == 2
    assert pdf.count(b"/Subtype /Image") == 2      # the raster and its soft mask


# -- against the SVG -------------------------------------------------------


def test_clipping_is_geometry_and_needs_no_clip_operator():
    """`inklet.clip` cuts the points, so neither backend emits a clip path. If
    that ever changes, this backend has to grow a `W n`."""
    node = inklet.clip(inklet.polyline([(-10, 0), (10, 0)], stroke="#000000"),
                    Rect(-5, -5, 5, 5))
    stream = pdf_of(node)
    assert " W" not in stream
    assert "-5 0 m" in stream and "5 0 l" in stream


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="poppler not installed")
def test_the_file_actually_renders(tmp_path):
    """The end of the chain: a real PDF consumer opens it and draws ink."""
    pillow = pytest.importorskip("PIL.Image")
    target = tmp_path / "figure.pdf"
    fig = figure()
    save_pdf(fig.build()[0], target, background="#ffffff")
    subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile",
                    str(target), str(tmp_path / "out")], check=True,
                   capture_output=True)

    raster = pillow.open(tmp_path / "out.png").convert("L")
    page = fig.page_rect(fig.build()[0].bbox)
    assert raster.width == pytest.approx(page.width * 150 / 25.4, abs=2)
    dark = sum(raster.histogram()[:128])
    assert dark > 500, "the page rendered blank"


# -- nested opacity --------------------------------------------------------


def translucent_pair() -> Diagram:
    """Two overlapping translucent shapes inside a translucent group -- the
    one arrangement where multiplying alpha down the tree and compositing the
    group as a unit give visibly different answers."""
    left = Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000", opacity=0.5)
    right = (Diagram(prim=RectPrim(10, 10)).translated(5, 0)
             .styled(fill="#0000ff", opacity=0.5))
    return Diagram(children=(left, right)).styled(opacity=0.5)


def test_a_translucent_group_is_composited_as_a_group():
    """SVG's `opacity` paints the subtree into a buffer and fades the buffer,
    so the overlap of two half-transparent children does not darken twice.
    Multiplying the alphas down the tree gets that wrong; a transparency
    group is the PDF spelling of the same thing."""
    pdf = to_pdf(translucent_pair(), compress=False)
    assert b"/S /Transparency" in pdf
    assert b"/Subtype /Form" in pdf


def test_a_group_that_is_only_opaque_costs_no_form():
    plain = Diagram(children=(Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000"),))
    assert b"/Subtype /Form" not in to_pdf(plain, compress=False)


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="poppler not installed")
def test_nested_opacity_matches_what_the_svg_backend_paints(tmp_path):
    """The assertion that actually settles it: rasterise both backends and
    look at the colour in the overlap."""
    pillow = pytest.importorskip("PIL.Image")
    node = translucent_pair()

    target = tmp_path / "pair.pdf"
    save_pdf(node, target, margin=2, background="#ffffff")
    subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile",
                    str(target), str(tmp_path / "pdf")], check=True,
                   capture_output=True)
    raster = pillow.open(tmp_path / "pdf.png").convert("RGB")
    # Dead centre of the page is inside both rectangles.
    got = raster.getpixel((raster.width // 2, raster.height // 2))

    # What SVG's group opacity means: the two children composite against each
    # other inside the group's own buffer, and the finished buffer -- colour
    # and accumulated alpha together -- is then faded to 50% over the page.
    # Source-over of blue at 0.5 onto red at 0.5:
    alpha = 0.5 + 0.5 * (1 - 0.5)                      # 0.75
    inner = [(b * 0.5 + r * 0.5 * (1 - 0.5)) / alpha
             for r, b in zip((255, 0, 0), (0, 0, 255))]
    faded = alpha * 0.5                                # the group's own opacity
    want = [round(c * faded + 255 * (1 - faded)) for c in inner]
    assert list(got) == pytest.approx(want, abs=4)

    # And the wrong answer -- multiplying 0.5 into each child and painting
    # them straight onto the page -- is far enough away to be caught: red at
    # 0.25 over white, then blue at 0.25 over that.
    over = [0.25 * c + 0.75 * 255 for c in (255, 0, 0)]
    naive = [round(0.25 * c + 0.75 * under) for c, under in zip((0, 0, 255), over)]
    assert list(got) != pytest.approx(naive, abs=4)


# -- more than one page ----------------------------------------------------


def test_a_list_of_roots_becomes_a_list_of_pages():
    one = Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000")
    two = Diagram(prim=EllipsePrim(8, 8)).styled(fill="#0000ff")
    pdf = to_pdf([one, two], compress=False)
    assert pdf.count(b"/Type /Page /Parent") == 2
    assert b"/Count 2" in pdf


def test_a_bare_root_is_still_one_page():
    """The single-diagram call is the common one and must not have grown a
    list wrapper in its output."""
    node = Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000")
    assert to_pdf([node], compress=False) == to_pdf(node, compress=False)


def test_pages_share_one_raster(tmp_path):
    """The reason multi-page is a backend feature and not a `cat` of two
    files: eighteen panels of heatmap embedded twice is the whole document."""
    source = png(tmp_path / "dot.png")
    page = Diagram(prim=ImagePrim(source, 5, 4))
    pdf = to_pdf([page, page], compress=False)
    assert pdf.count(b"/Subtype /Image") == 2      # the raster and its mask
    assert content(pdf).count("/Im0 Do") == 1      # ...per page stream


def test_saving_a_list_writes_one_file(tmp_path):
    target = tmp_path / "two.pdf"
    node = Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000")
    save_pdf([node, node], target)
    assert target.read_bytes().startswith(b"%PDF-")
    assert target.read_bytes().count(b"/Type /Page /Parent") == 2


def test_two_pages_are_deterministic():
    node = Diagram(prim=RectPrim(10, 10)).styled(fill="#ff0000")
    assert to_pdf([node, node]) == to_pdf([node, node])


# -- per-run text colour ---------------------------------------------------


def test_a_recoloured_run_changes_the_fill_mid_line():
    stream = pdf_of(Diagram(prim=shape("plain {#cc0000|red} plain",
                                       size=inklet.pt(8))))
    assert "0.8 0 0 rg" in stream          # #cc0000
    # ...and the colour goes back, rather than staining the rest of the line.
    assert stream.index("0.8 0 0 rg") < stream.rindex("0 0 0 rg")


def test_an_uncoloured_line_sets_its_fill_once():
    stream = pdf_of(Diagram(prim=shape("plain words here", size=inklet.pt(8))))
    assert stream.count(" rg\n") == 1


# -- a raster with no file behind it ---------------------------------------


def test_a_prim_carrying_its_own_bytes_never_touches_the_filesystem(tmp_path):
    """`source` is then a label: what to call the image in a diagnostic, not
    where to find it. A path that does not exist must not matter."""
    image = pytest.importorskip("PIL.Image")
    buffer = io.BytesIO()
    image.new("RGB", (8, 6), (200, 30, 30)).save(buffer, format="PNG")
    prim = ImagePrim("panel c matrix", width=10, height=7.5,
                     data=buffer.getvalue())
    pdf = to_pdf(Diagram(prim=prim), compress=False)
    assert b"/Subtype /Image /Width 8 /Height 6" in pdf
    assert "/Im0 Do" in content(pdf)


def test_two_prims_carrying_the_same_bytes_are_embedded_once():
    """Keyed on the bytes, because generated rasters have no path to key on
    and eighteen panels of the same colour bar is the case that matters."""
    image = pytest.importorskip("PIL.Image")
    buffer = io.BytesIO()
    image.new("RGB", (8, 6), (200, 30, 30)).save(buffer, format="PNG")
    raw = buffer.getvalue()
    node = Diagram(children=(
        Diagram(prim=ImagePrim("a", 5, 4, data=raw)),
        Diagram(prim=ImagePrim("b", 5, 4, data=raw)).translated(6, 0)))
    pdf = to_pdf(node, compress=False)
    assert content(pdf).count("/Im0 Do") == 2
    assert pdf.count(b"/Subtype /Image") == 1


def test_a_raster_is_nearest_neighbour_unless_it_asks_otherwise(tmp_path):
    """PDF's own default, and the right one for a figure: a heatmap drawn one
    pixel per cell is data, and interpolating it invents values between the
    cells."""
    source = png(tmp_path / "dot.png")
    assert b"/Interpolate" not in to_pdf(Diagram(prim=ImagePrim(source, 5, 4)),
                                         compress=False)
    assert b"/Interpolate" not in to_pdf(
        Diagram(prim=ImagePrim(source, 5, 4, smooth=False)), compress=False)


def test_a_photograph_can_ask_to_be_resampled_smoothly(tmp_path):
    source = png(tmp_path / "dot.png")
    pdf = to_pdf(Diagram(prim=ImagePrim(source, 5, 4, smooth=True)), compress=False)
    assert b"/Interpolate true" in pdf


def test_the_same_bytes_sampled_two_ways_are_two_xobjects(tmp_path):
    """`/Interpolate` lives in the image dictionary, so the dedup key has to
    carry it or the second placement silently takes the first one's sampling."""
    source = png(tmp_path / "dot.png")
    node = Diagram(children=(
        Diagram(prim=ImagePrim(source, 5, 4, smooth=True)),
        Diagram(prim=ImagePrim(source, 5, 4, smooth=False)).translated(6, 0)))
    pdf = to_pdf(node, compress=False)
    # One raster and its mask smoothed, one raster and its mask not.
    assert pdf.count(b"/Interpolate true") == 2
    assert pdf.count(b"/ColorSpace /DeviceRGB") == 2
