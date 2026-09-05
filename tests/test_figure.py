"""The integration layer: page placement, theming, and link composition.

Every bug pinned here was found by rendering a figure and looking at it, which
is the one check the linter cannot perform.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

import inklet
from inklet.core import resolve
from inklet.links import route

SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(autouse=True)
def nature():
    inklet.use_theme("nature")


def pipeline():
    a, b = inklet.box("Two-photon\nimaging"), inklet.box("ROI extraction")
    fig = inklet.figure(width="89mm")
    fig.add(inklet.vstack([a, b], gap=6))
    return fig, a, b


# -- the page -------------------------------------------------------------


def test_content_is_moved_onto_the_page():
    """Combinators centre their results on the origin, which is not where a
    page starts. Everything must end up inside (0, 0)..(width, height)."""
    fig, _, _ = pipeline()
    root, placements = fig.build()
    page = root.bbox
    assert (page.x0, page.y0) == (0.0, 0.0)
    assert page.width == pytest.approx(89.0)
    for placement in placements.values():
        box = placement.bbox
        if box is None:
            continue
        assert box.x0 >= -1e-9 and box.y0 >= -1e-9
        assert box.x1 <= page.width + 1e-9 and box.y1 <= page.height + 1e-9


def test_a_well_formed_figure_lints_clean():
    """If the rules fire on good input they are worthless."""
    fig, _, _ = pipeline()
    assert [d for d in fig.lint() if d.severity == "error"] == []


def test_content_is_centred_in_the_column():
    fig, a, _ = pipeline()
    _, placements = fig.build()
    assert placements[a.id].bbox.center.x == pytest.approx(89.0 / 2)


# -- links ----------------------------------------------------------------


def test_connectors_are_not_displaced_from_what_they_connect():
    """Regression: composing links over content with `overlay` re-centred each
    on its own bbox, so every arrow drifted away from its boxes."""
    fig, a, b = pipeline()
    fig.link(a, b)
    root, placements = fig.build()

    routed = [n for n in root.walk() if n.kind == "link"]
    assert len(routed) == 1
    start = placements[routed[0].id].world.apply(routed[0].anchor_point("start"))
    end = placements[routed[0].id].world.apply(routed[0].anchor_point("end"))

    assert start.y == pytest.approx(placements[a.id].bbox.y1)
    assert end.y == pytest.approx(placements[b.id].bbox.y0)
    assert start.x == pytest.approx(placements[a.id].bbox.center.x)


def test_a_string_label_is_shaped_by_the_figure():
    """The links module works in geometry alone and cannot shape text itself."""
    fig, a, b = pipeline()
    link = fig.link(a, b, label="dF/F")
    assert isinstance(link.label, inklet.Diagram)
    assert link.label.width > 0
    root, _ = fig.build()
    assert "dF/F" in inklet.to_svg(root)


def test_arrowheads_are_filled_by_the_theme():
    """The shaft is stroked and the head is filled, so they cannot share a role;
    an unmapped `arrowhead` kind renders as a hollow caret."""
    fig, a, b = pipeline()
    fig.link(a, b)
    root, placements = fig.build()
    heads = [n for n in root.walk() if n.kind == "arrowhead"]
    assert heads
    for head in heads:
        assert placements[head.id].style.fill not in (None, "none")


# -- rendering ------------------------------------------------------------


def test_glyphs_are_never_stroked():
    """Text inside a group that strokes its shapes must not inherit that stroke,
    or every letter is outlined and reads as a clumsy fake bold."""
    fig, a, b = pipeline()
    fig.link(a, b, label="dF/F")
    tree = ET.fromstring(fig.to_svg())
    texts = list(tree.iter(SVG + "text"))
    assert texts
    for element in texts:
        assert element.get("stroke") == "none"


def test_svg_page_matches_the_declared_column():
    fig, _, _ = pipeline()
    tree = ET.fromstring(fig.to_svg())
    assert tree.get("width") == "89mm"
    assert tree.get("viewBox").split()[:3] == ["0", "0", "89"]


def test_output_is_deterministic():
    fig, a, b = pipeline()
    fig.link(a, b, label="dF/F")
    assert fig.to_svg() == fig.to_svg()


def test_saving_an_unsupported_format_says_so(tmp_path):
    fig, _, _ = pipeline()
    with pytest.raises(NotImplementedError, match=r"\.eps"):
        fig.save(tmp_path / "figure.eps")
    fig.save(tmp_path / "figure.svg", tmp_path / "figure.pdf")
    assert (tmp_path / "figure.svg").read_text().startswith("<?xml")
    assert (tmp_path / "figure.pdf").read_bytes().startswith(b"%PDF-1.4")


# -- theming --------------------------------------------------------------


def test_theme_slides_under_explicit_style():
    fig = inklet.figure(width="89mm")
    plain, loud = inklet.box("plain"), inklet.box("loud", stroke="#ff0000")
    fig.add(inklet.vstack([plain, loud], gap=4))
    _, placements = fig.build()

    def shape_style(node):
        rect = next(n for n in node.walk() if n.kind == "box")
        return placements[rect.id].style

    assert shape_style(loud).stroke == "#ff0000"
    assert shape_style(plain).stroke == inklet.theme("nature").ink


def test_ids_survive_theming_so_handles_keep_working():
    """apply_theme rebuilds the tree; if it minted new ids, every caller handle
    and every link reference would break."""
    fig, a, b = pipeline()
    fig.link(a, b)
    _, placements = fig.build()
    assert a.id in placements and b.id in placements


# -- the theme a figure starts with ---------------------------------------


def test_a_new_figure_uses_whatever_use_theme_last_set():
    """The bug: `Figure` defaulted to a fresh `nature` whatever the author had
    chosen, so a script that opened with `inklet.use_theme("slides")` built its
    content at slide sizes and then rendered it in Nature's type."""
    inklet.use_theme("slides")
    try:
        assert inklet.figure().theme.name == "slides"
        assert inklet.Figure().theme.name == "slides"
    finally:
        inklet.use_theme("nature")


def test_the_theme_is_read_when_the_figure_is_made_not_when_it_is_saved():
    """A default factory, not a live lookup: two figures in one script keep
    the themes they were opened with."""
    first = inklet.figure()
    inklet.use_theme("slides")
    try:
        second = inklet.figure()
        assert first.theme.name == "nature"
        assert second.theme.name == "slides"
    finally:
        inklet.use_theme("nature")


def test_an_explicit_theme_still_wins():
    inklet.use_theme("slides")
    try:
        assert inklet.figure(theme=inklet.theme("notebook")).theme.name == "notebook"
    finally:
        inklet.use_theme("nature")


def test_the_default_is_still_nature_when_nobody_has_chosen():
    assert inklet.figure().theme.name == "nature"


def test_the_chosen_theme_reaches_the_page():
    inklet.use_theme("slides")
    try:
        fig = inklet.figure(width="120mm")
        fig.add(inklet.box("Result"))
        assert inklet.theme("slides").font_family.split(",")[0] in fig.to_svg()
    finally:
        inklet.use_theme("nature")


# -- text= reaches the PDF branch of save() ----------------------------------

def test_save_forwards_the_text_mode_to_the_pdf(tmp_path):
    """`save` filtered `text=` off the PDF branch, so `save("f.pdf",
    text="embed")` silently outlined -- the user asked for a searchable file
    and got the opposite, with nothing said."""
    fig = inklet.figure(width="60mm")
    fig.add(inklet.box("hello"))
    fig.save(tmp_path / "a.svg", tmp_path / "a.pdf", text="embed")
    assert b"/FontFile" in (tmp_path / "a.pdf").read_bytes()
    assert "font-family" in (tmp_path / "a.svg").read_text()


def test_the_pdf_default_is_still_outlined(tmp_path):
    fig = inklet.figure(width="60mm")
    fig.add(inklet.box("hello"))
    fig.save(tmp_path / "b.pdf")
    assert b"/FontFile" not in (tmp_path / "b.pdf").read_bytes()


def test_an_svg_only_text_mode_leaves_the_pdf_outlined(tmp_path):
    """PDF has no font-name mode. `text="names"` is an SVG answer to a
    question PDF does not ask, so the PDF takes the safe reading rather than
    refusing a call that is perfectly sensible about the SVG beside it."""
    fig = inklet.figure(width="60mm")
    fig.add(inklet.box("hello"))
    fig.save(tmp_path / "c.svg", tmp_path / "c.pdf", text="names")
    assert b"/FontFile" not in (tmp_path / "c.pdf").read_bytes()
    assert "font-family" in (tmp_path / "c.svg").read_text()


def test_an_unknown_text_mode_is_refused_before_anything_is_written(tmp_path):
    """Checked once, up front: otherwise which file exists afterwards depends
    on the order the paths happened to be listed in."""
    fig = inklet.figure(width="60mm")
    fig.add(inklet.box("hello"))
    with pytest.raises(ValueError, match="unknown text mode"):
        fig.save(tmp_path / "d.svg", tmp_path / "d.pdf", text="nope")
    assert not (tmp_path / "d.svg").exists()
