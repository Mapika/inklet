"""LOW_CONTRAST over a photograph, which has no `fill` to read.

Paper-white type on a dark micrograph is the universal journal style, and
before this the rule judged it against the page and reported the one
annotation the figure was certain to have got right. Reading the pixels needs
Pillow, which is optional, so the module has two behaviours and this file
pins both: with Pillow, the mean colour under the text; without it, silence.

The source image is half near-black and half near-white, so the same caption
is a defect on one side of it and correct on the other -- which is also the
proof that the mapping from world millimetres to pixels is the right way up.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import Affine, Diagram, ImagePrim, Rect
from inklet.diagnostics import image as di

Image = pytest.importorskip("PIL.Image")

PIXELS = (400, 200)
DARK = (17, 17, 17)
LIGHT = (250, 250, 250)


@pytest.fixture
def half_and_half(tmp_path):
    """A raster whose left half is #111111 and whose right half is #fafafa."""
    img = Image.new("RGB", PIXELS, DARK)
    img.paste(Image.new("RGB", (PIXELS[0] // 2, PIXELS[1]), LIGHT),
              (PIXELS[0] // 2, 0))
    path = tmp_path / "micrograph.png"
    img.save(path)
    di.clear_cache()
    yield str(path)
    di.clear_cache()


def sheet(source: str, dx: float, colour: str) -> inklet.Figure:
    """A 100x50mm raster with a caption `dx` millimetres from its centre."""
    picture = Diagram(prim=ImagePrim(source=source, width=100.0, height=50.0,
                                     pixel_size=PIXELS), name="micrograph")
    caption = inklet.text("2 um", size=7).styled(text_fill=colour).named("cap")
    fig = inklet.figure(width=120, height=70)
    fig.add(inklet.place([((0.0, 0.0), picture), ((dx, 0.0), caption)]))
    return fig


def contrast(fig) -> list:
    return [d for d in fig.lint() if d.code == "LOW_CONTRAST"]


def test_white_type_on_the_bright_half_is_reported(half_and_half):
    diag, = contrast(sheet(half_and_half, 30.0, "#ffffff"))

    assert diag.severity == "warning"
    # The backdrop is named, and so is the fact that it is an average.
    assert "micrograph, averaging #fafafa under the text" in diag.message
    assert "1.0" in diag.message
    assert "a plate" in diag.hint


def test_white_type_on_the_dark_half_is_silent(half_and_half):
    assert contrast(sheet(half_and_half, -30.0, "#ffffff")) == []


def test_dark_type_on_the_dark_half_is_reported(half_and_half):
    diag, = contrast(sheet(half_and_half, -30.0, "#111111"))

    assert "averaging #111111" in diag.message


def test_dark_type_on_the_bright_half_is_silent(half_and_half):
    assert contrast(sheet(half_and_half, 30.0, "#111111")) == []


def test_without_pillow_the_rule_says_nothing(half_and_half, monkeypatch):
    """The documented second behaviour. A guess about a photograph nobody can
    open is worth less than silence -- and in particular it must not fall back
    to the page colour, which is what produced the false positive."""
    monkeypatch.setattr(di, "_pillow", lambda: None)
    di.clear_cache()

    assert not di.available()
    assert contrast(sheet(half_and_half, 30.0, "#ffffff")) == []


def test_an_unreadable_source_is_not_guessed_at(tmp_path):
    di.clear_cache()
    missing = str(tmp_path / "not-here.png")

    assert contrast(sheet(missing, 30.0, "#ffffff")) == []


def test_a_file_that_is_not_an_image_is_read_once_and_forgotten(tmp_path):
    broken = tmp_path / "truncated.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n not really")
    di.clear_cache()

    assert di.average_colour(
        ImagePrim(source=str(broken), width=10.0, height=10.0,
                  pixel_size=(10, 10)),
        Affine(), Rect(-5.0, -5.0, 5.0, 5.0)) is None
    # Memoised as a failure rather than retried per caption.
    assert any(value is None for value in di._THUMBS.values())


def test_a_caption_smaller_than_a_few_pixels_is_not_averaged(half_and_half):
    """Below `_MIN_SAMPLES` thumbnail pixels the mean is noise, not a
    measurement, so the rule is told nothing rather than something thin."""
    prim = ImagePrim(source=half_and_half, width=100.0, height=50.0,
                     pixel_size=PIXELS)
    sliver = Rect(0.0, 0.0, 0.05, 0.05)

    assert di.average_colour(prim, Affine(), sliver) is None
