"""Every rule gets a figure that trips it and a near-miss that must stay quiet.

The near-miss half is the important half: a linter that fires on good input
teaches an agent to ignore it, so most negative cases assert the *whole*
diagnostic list is empty rather than merely lacking one code.
"""

from __future__ import annotations

import re

import pytest

from inklet.core import (
    Diagram, EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Rect, RectPrim,
    TextLine, TextPrim, Vec2, group, pt, resolve,
)
from inklet.diagnostics import RULES, Diagnostic, format_report, lint
from inklet.diagnostics.rules import _candidate_pairs
from inklet.draw import encoded, polygon
from inklet.links import HEAD_KIND, link as make_link, route, route_all
from inklet.render import to_svg
from inklet.plot.raster import MATRIX_KIND

PAGE = Rect(0.0, 0.0, 89.0, 50.0)


# -- builders -------------------------------------------------------------


def text(content: str, width: float, size_pt: float = 8.0,
         name: str | None = None, **style) -> Diagram:
    """A pre-shaped single-line TextPrim of an exact world width."""
    size = pt(size_pt)
    node = Diagram(
        prim=TextPrim(lines=(TextLine(content, width, 0.0),), font_family="Inter",
                      font_size=size, ascent=size * 0.8, descent=size * 0.2),
        kind="text",
    )
    if style:
        node = node.styled(**style)
    return node.named(name) if name else node


def box(w: float, h: float, *children: Diagram, name: str | None = None,
        **style) -> Diagram:
    node = Diagram(prim=RectPrim(w, h), children=tuple(children), kind="box")
    if style:
        node = node.styled(**style)
    return node.named(name) if name else node


def text_height(size_pt: float = 8.0) -> float:
    return pt(size_pt)


def codes(diags) -> list[str]:
    return [d.code for d in diags]


def only(diags, code: str) -> Diagnostic:
    matching = [d for d in diags if d.code == code]
    assert len(matching) == 1, f"expected one {code}, got {codes(diags)}"
    return matching[0]


def only_one(items: list) -> Diagram:
    assert len(items) == 1, f"expected exactly one, got {len(items)}"
    return items[0]


def numbers(message: str) -> list[float]:
    return [float(m) for m in re.findall(r"-?\d+\.?\d*", message)]


def sides(message: str) -> dict[str, float]:
    """The `N.NNmm on the <side>` pairs a message reports."""
    return {side: float(value)
            for value, side in re.findall(r"([\d.]+)mm on the (\w+)", message)}


# -- 1. TEXT_OVERFLOW -----------------------------------------------------


def test_text_overflow_reports_millimetres_per_side():
    label = text("Encoder (ViT-B/16)", 23.0, name="label")
    frame = box(20.0, 10.0, label, name="enc")

    diag = only(lint(frame), "TEXT_OVERFLOW")

    assert diag.severity == "error"
    assert diag.targets == (label.id, frame.id)
    assert sides(diag.message) == pytest.approx({"left": 1.5, "right": 1.5}, abs=0.01)
    assert "widen enc by 3.00mm" in diag.hint
    assert diag.where.width == pytest.approx(23.0)


def test_text_overflow_reports_the_vertical_side_too():
    label = text("two lines worth", 10.0, size_pt=12.0, name="label")
    frame = box(20.0, 2.0, label, name="enc")

    diag = only(lint(frame), "TEXT_OVERFLOW")

    # 12pt block is 4.233mm tall in a 2mm box: 1.1165mm out of each side.
    assert sides(diag.message) == pytest.approx({"top": 1.12, "bottom": 1.12}, abs=0.01)


def test_text_that_fits_its_box_is_silent():
    label = text("Encoder", 17.0, name="label")
    frame = box(20.0, 10.0, label, name="enc")

    assert lint(frame) == []


def test_text_overflow_uses_the_nearest_shape_ancestor():
    label = text("wide label", 25.0, name="label")
    inner = box(20.0, 10.0, label, name="inner")
    outer = box(60.0, 40.0, inner, name="outer")

    diag = only(lint(outer), "TEXT_OVERFLOW")
    assert diag.targets == (label.id, inner.id)


def test_text_overflow_ignores_a_label_with_no_shape_ancestor():
    # A free-floating caption belongs to no box, so nothing can be overflowed.
    assert [d for d in lint(group([text("caption", 40.0)])) if d.code == "TEXT_OVERFLOW"] == []


# -- 2. OFF_CANVAS --------------------------------------------------------


def test_off_canvas_reports_the_excess():
    node = box(20.0, 10.0, name="wanderer").translated(85.0, 25.0)

    diag = only(lint(node, page=PAGE), "OFF_CANVAS")

    assert diag.severity == "error"
    assert diag.targets == (node.children[0].id,)
    assert "runs off the page by 6.00mm on the right" in diag.message


def test_off_canvas_flags_a_fully_absent_item():
    node = box(10.0, 10.0, name="gone").translated(200.0, 25.0)

    diag = only(lint(node, page=PAGE), "OFF_CANVAS")
    assert "entirely off the page" in diag.message


def test_item_inside_the_page_is_silent():
    node = box(20.0, 10.0, name="fine").translated(44.5, 25.0)
    assert lint(node, page=PAGE) == []


def test_off_canvas_needs_a_page():
    node = box(20.0, 10.0, name="wanderer").translated(850.0, 25.0)
    assert [d for d in lint(node) if d.code == "OFF_CANVAS"] == []


# -- 3. TINY_TEXT ---------------------------------------------------------


def test_tiny_text_accounts_for_group_scale():
    label = text("7pt in a half-scale group", 20.0, size_pt=7.0, name="label")
    figure = group([label]).scaled(0.5)

    diag = only(lint(figure), "TINY_TEXT")

    assert diag.severity == "error"
    assert diag.targets == (label.id,)
    assert "3.5pt" in diag.message
    assert "7.0pt at 0.5x scale" in diag.message
    assert "10.0pt" in diag.hint  # 5pt floor / 0.5 scale


def test_seven_point_text_at_full_scale_is_silent():
    label = text("7pt unscaled", 20.0, size_pt=7.0, name="label")
    assert lint(group([label])) == []


def test_tiny_text_threshold_is_configurable():
    label = text("7pt unscaled", 20.0, size_pt=7.0, name="label")
    diag = only(lint(group([label]), min_font_pt=8.0), "TINY_TEXT")
    assert "7.0pt" in diag.message


# -- 4. HAIRLINE ----------------------------------------------------------


def test_hairline_stroke_is_reported():
    node = box(20.0, 10.0, name="rule", stroke="#000000", stroke_width=0.05)

    diag = only(lint(node), "HAIRLINE")

    assert diag.severity == "warning"
    assert diag.targets == (node.id,)
    assert "0.05mm stroke" in diag.message
    assert "0.088mm print minimum" in diag.message
    assert "at least 0.088mm" in diag.hint


def test_quarter_millimetre_stroke_is_silent():
    node = box(20.0, 10.0, name="rule", stroke="#000000", stroke_width=0.25)
    assert lint(node) == []


def test_hairline_accounts_for_scale():
    node = box(20.0, 10.0, name="rule", stroke="#000000", stroke_width=0.2)
    diag = only(lint(group([node]).scaled(0.25)), "HAIRLINE")
    assert "0.05mm stroke" in diag.message
    assert "0.20mm at 0.25x scale" in diag.message


def test_stroke_width_without_a_stroke_colour_is_silent():
    node = box(20.0, 10.0, name="rule", stroke="none", stroke_width=0.01)
    assert [d for d in lint(node) if d.code == "HAIRLINE"] == []


# -- 5. LOW_CONTRAST ------------------------------------------------------


def test_mid_grey_on_white_is_low_contrast():
    label = text("mid grey", 20.0, name="label", text_fill="#808080")

    diag = only(lint(group([label])), "LOW_CONTRAST")

    assert diag.severity == "warning"
    assert diag.targets == (label.id,)
    ratio = float(re.search(r"([\d.]+):1", diag.message).group(1))
    assert ratio == pytest.approx(3.95, abs=0.05)
    assert "4.5:1" in diag.message


def test_near_black_on_white_is_silent():
    label = text("near black", 20.0, name="label", text_fill="#222222")
    assert lint(group([label])) == []


def test_contrast_is_measured_against_the_enclosing_shape_fill():
    label = text("on navy", 20.0, name="label", text_fill="#333333")
    frame = box(40.0, 10.0, label, name="card", fill="#000080")

    diag = only(lint(frame), "LOW_CONTRAST")
    assert diag.targets == (label.id, frame.id)
    assert "card's #000080" in diag.message


def test_contrast_finds_a_sibling_frame_not_only_an_ancestor():
    label = text("on grey", 20.0, name="label", text_fill="#777777")
    frame = box(40.0, 10.0, name="card", fill="#ffffff")
    figure = group([frame, label])

    diag = only(lint(figure), "LOW_CONTRAST")
    assert diag.targets == (label.id, frame.id)


def test_unknown_colour_is_not_guessed_at():
    label = text("mystery", 20.0, name="label", text_fill="var(--brand)")
    assert [d for d in lint(group([label])) if d.code == "LOW_CONTRAST"] == []


def test_a_label_inheriting_its_box_fill_is_not_reported():
    # The label inherits fill="#eeeeee" from the box it sits in, and with no
    # theme in the tree the SVG cascade really does paint it in that colour.
    # It is not reported anyway: see `rule_low_contrast` on the one divergence
    # from the renderer this rule keeps on purpose.
    label = text("Encoder", 20.0, name="label")
    frame = box(40.0, 10.0, label, name="card", fill="#eeeeee")
    assert lint(frame) == []


def test_the_renderer_really_does_paint_that_label_in_the_box_fill():
    """The other half of the divergence, pinned from the renderer's side.

    Two rules disagree with each other here and both are right, so the pair
    has to be held still: `render/svg.py` writes `fill` on the wrapping `<g>`
    and writes nothing on the `<text>` unless a `text_fill` is in scope, which
    means the glyphs above are #eeeeee on #eeeeee and invisible. If this test
    starts failing the renderer has changed, and `rule_low_contrast` should
    stop diverging rather than be adjusted to keep matching.
    """
    label = text("Encoder", 20.0, name="label")
    frame = box(40.0, 10.0, label, name="card", fill="#eeeeee")

    svg = to_svg(frame)

    assert 'fill="#eeeeee"' in svg
    assert re.search(r"<text[^>]*>", svg), svg
    assert not re.search(r"<text[^>]*fill=", svg), svg


def test_a_text_fill_in_scope_ends_the_divergence():
    # Every theme sets `text_fill` on the page, and once anything does the
    # glyphs stop inheriting: the rule and the renderer are asking the same
    # question again, and a pale label on a pale box is reported.
    label = text("Encoder", 20.0, name="label")
    frame = box(40.0, 10.0, label, name="card", fill="#eeeeee")
    page = group([frame]).styled(text_fill="#eeeeee")

    diag = only(lint(page), "LOW_CONTRAST")

    assert "in #eeeeee" in diag.message
    assert "card's #eeeeee" in diag.message


def test_a_fill_set_directly_on_the_text_is_honoured():
    label = text("faint", 20.0, name="label", fill="#aaaaaa")
    frame = box(40.0, 10.0, label, name="card", fill="#ffffff")
    assert only(lint(frame), "LOW_CONTRAST")


def test_translucent_text_is_not_guessed_at():
    # What is behind a 50%-alpha glyph is a rendering question, not a geometry
    # one, so the rule declines rather than inventing a luminance.
    label = text("half there", 20.0, name="label", text_fill="#00000080")
    assert [d for d in lint(group([label])) if d.code == "LOW_CONTRAST"] == []


def test_large_text_gets_the_wcag_large_allowance():
    # 3.95:1 fails at 4.5 but passes the 3:1 bar large type is held to.
    label = text("display", 60.0, size_pt=20.0, name="label", text_fill="#808080")
    assert [d for d in lint(group([label])) if d.code == "LOW_CONTRAST"] == []


# -- 5a. TEXT_FILL_IGNORED ------------------------------------------------
#
# Glyph colour is `text_fill`, and `fill` on a text node goes to the wrapping
# group. `inklet.label("x", fill="red")` therefore prints in the theme's ink, with
# nothing raised and nothing overlapping. See `rule_text_fill_ignored`.


def test_fill_on_a_text_node_under_a_text_fill_is_a_warning():
    label = text("caption", 20.0, name="label", fill="#c1121f")
    page = group([label]).styled(text_fill="#1a1a1a")

    diag = only(lint(page), "TEXT_FILL_IGNORED")

    assert diag.severity == "warning"
    assert "sets fill='#c1121f'" in diag.message
    assert "renders in #1a1a1a" in diag.message
    assert diag.hint == "write text_fill='#c1121f' instead of fill='#c1121f'"
    assert diag.targets == (label.id,)


def test_fill_on_a_text_node_with_no_text_fill_anywhere_is_info():
    """It works, by accident of the SVG cascade, until the figure gets a theme.

    Worth saying out loud because the linter's other divergence from the
    renderer lives here too: `LOW_CONTRAST` deliberately does not report the
    inherited colour, so this is the only rule that mentions it at all.
    """
    label = text("caption", 20.0, name="label", fill="#c1121f")

    diag = only(lint(group([label])), "TEXT_FILL_IGNORED")

    assert diag.severity == "info"
    assert "take back" in diag.message


def test_text_fill_on_its_own_is_silent():
    label = text("caption", 20.0, name="label", text_fill="#c1121f")

    assert lint(group([label])) == []


def test_a_text_node_setting_both_is_not_reported():
    """`fill` beside an explicit `text_fill` is how you colour a highlight
    behind a word. The author has said which channel they meant."""
    label = text("caption", 20.0, name="label",
                 fill="#ffe066", text_fill="#1a1a1a")

    assert [d for d in lint(group([label]))
            if d.code == "TEXT_FILL_IGNORED"] == []


def test_fill_on_a_shape_is_never_reported():
    frame = box(20.0, 10.0, name="frame", fill="#c1121f")

    assert [d for d in lint(group([frame]))
            if d.code == "TEXT_FILL_IGNORED"] == []


# -- 6. LOW_DPI -----------------------------------------------------------


def test_low_dpi_reports_the_pixel_width_that_would_fix_it():
    node = Diagram(prim=ImagePrim("scan.png", 40.0, 30.0, (400, 300)),
                   kind="img").named("scan")

    diag = only(lint(node), "LOW_DPI")

    assert diag.severity == "warning"
    assert diag.targets == (node.id,)
    assert "400px wide at 40.00mm = 254dpi" in diag.message
    assert "473px-wide source" in diag.hint


def test_sufficient_dpi_is_silent():
    node = Diagram(prim=ImagePrim("scan.png", 40.0, 30.0, (600, 450)),
                   kind="img").named("scan")
    assert lint(node) == []


def test_low_dpi_accounts_for_scale():
    # 254dpi locally, but printed at half the width it is 508dpi.
    node = Diagram(prim=ImagePrim("scan.png", 40.0, 30.0, (400, 300)), kind="img")
    assert [d for d in lint(group([node]).scaled(0.5)) if d.code == "LOW_DPI"] == []


def test_image_without_pixel_size_is_silent():
    node = Diagram(prim=ImagePrim("vector.pdf", 40.0, 30.0), kind="img")
    assert [d for d in lint(node) if d.code == "LOW_DPI"] == []


def test_a_matrix_of_measurements_is_not_under_resolved():
    # 60 x 60 samples printed at 40mm is 38dpi and is not a defect: the fix
    # LOW_DPI would ask for is 472 measurements across that nobody took.
    node = Diagram(prim=ImagePrim("matrix", 40.0, 40.0, (60, 60)),
                   kind=MATRIX_KIND).named("field")

    assert [d for d in lint(node) if d.code == "LOW_DPI"] == []


def test_an_author_can_say_the_same_with_smooth_false():
    # `smooth=False` is the statement "these pixels are the data" made by
    # someone who built the ImagePrim themselves rather than through
    # `inklet.plot`; the back ends already read it to turn resampling off.
    node = Diagram(prim=ImagePrim("field.png", 40.0, 30.0, (60, 45),
                                  smooth=False), kind="img").named("field")

    assert [d for d in lint(node) if d.code == "LOW_DPI"] == []


def test_a_photograph_that_merely_asks_for_smoothing_is_still_checked():
    node = Diagram(prim=ImagePrim("scan.png", 40.0, 30.0, (400, 300),
                                  smooth=True), kind="img").named("scan")

    assert only(lint(node), "LOW_DPI").severity == "warning"


# -- 7. OVERLAP -----------------------------------------------------------


def test_two_overlapping_labels_collide():
    a = text("first label", 20.0, name="a")
    b = text("second label", 20.0, name="b").translated(12.0, 0.0)
    figure = group([a, b])

    diag = only(lint(figure), "OVERLAP")

    assert diag.severity == "error"
    assert diag.targets == tuple(sorted((a.id, b.children[0].id)))
    assert "40% of the smaller box" in diag.message
    assert numbers(diag.message)[0] == pytest.approx(22.58, abs=0.05)


def test_text_inside_its_own_nested_frame_never_collides():
    label = text("inside", 20.0, name="label")
    frame = box(30.0, 10.0, label, name="frame")
    assert lint(frame) == []


def test_text_beside_its_frame_in_the_tree_never_collides():
    # The frame-and-label-as-siblings idiom: an ancestor test alone misses this,
    # which is why containment is checked geometrically.
    label = text("inside", 20.0, name="label")
    frame = box(30.0, 10.0, name="frame")
    assert lint(group([frame, label])) == []


def test_two_overlapping_shapes_without_text_are_not_reported():
    a = box(20.0, 20.0, name="a")
    b = box(20.0, 20.0, name="b").translated(5.0, 5.0)
    assert [d for d in lint(group([a, b])) if d.code == "OVERLAP"] == []


def test_a_grazing_overlap_is_below_the_area_threshold():
    a = text("first", 20.0, name="a")
    b = text("second", 20.0, name="b").translated(19.0, 0.0)  # 1mm of 20mm = 5%
    assert [d for d in lint(group([a, b])) if d.code == "OVERLAP"] == []


def test_a_diagonal_connector_bbox_does_not_count_as_a_collision():
    # The whole reason unfilled paths are excluded: this line passes nowhere
    # near the label, but its bounding box swallows it.
    line = Diagram(prim=PathPrim.polyline([Vec2(-20.0, -20.0), Vec2(20.0, 20.0)]),
                   kind="path").named("edge")
    label = text("label", 12.0, name="label").translated(-12.0, 12.0)
    assert [d for d in lint(group([line, label])) if d.code == "OVERLAP"] == []


def test_text_over_a_shape_is_a_warning_not_an_error():
    label = text("stray", 20.0, name="label").translated(15.0, 0.0)
    shape = box(20.0, 20.0, name="shape")
    diag = only(lint(group([shape, label])), "OVERLAP")
    assert diag.severity == "warning"


def test_phantom_padding_never_collides():
    phantom = Diagram(prim=PhantomPrim(Rect(-20.0, -20.0, 20.0, 20.0)), kind="pad")
    label = text("label", 10.0, name="label")
    assert [d for d in lint(group([phantom, label])) if d.code == "OVERLAP"] == []


CUTOUT = (Vec2(-20.0, 10.0), Vec2(20.0, 10.0), Vec2(-20.0, -10.0))


def photo(name: str = "mouse") -> Diagram:
    """A 40x20mm picture whose subject fills only the lower-left triangle of
    it -- the ordinary shape of a cutout, and of `stress/assets/mouse.png`."""
    return Diagram(prim=ImagePrim("mouse.png", 40.0, 20.0, (800, 400),
                                  outline=CUTOUT), kind="asset").named(name)


def test_a_label_in_a_cutouts_empty_corner_is_not_an_overlap():
    """A photograph's box is the frame's and `outline` is the subject. An
    animal lying along one edge leaves the far corner empty, and a caption set
    there is not on the animal."""
    caption = text("titanium headplate", 12.0, name="tag").translated(12.0, -9.5)

    assert "OVERLAP" not in codes(lint(group([photo(), caption])))


def test_a_label_on_the_subject_itself_is_still_an_overlap():
    caption = text("titanium headplate", 12.0, name="tag").translated(-12.0, 9.5)

    diag = only(lint(group([photo(), caption])), "OVERLAP")

    assert "mouse overlaps tag 'titanium headplate'" in diag.message


# -- 8. INCONSISTENT_STROKE -----------------------------------------------


def stroke_row(*widths: float) -> tuple[Diagram, list[Diagram]]:
    rects = [box(10.0, 6.0, name=f"r{i}", stroke="#000000", stroke_width=w)
             for i, w in enumerate(widths)]
    row = group([r.translated((i + 1) * 20.0, 0.0) for i, r in enumerate(rects)])
    return row, rects


def test_four_stroke_widths_are_reported():
    figure, rects = stroke_row(0.1, 0.2, 0.3, 0.5)

    diag = only(lint(figure), "INCONSISTENT_STROKE")

    assert diag.severity == "info"
    assert "4 distinct stroke widths" in diag.message
    for width in ("0.10mm", "0.20mm", "0.30mm", "0.50mm"):
        assert width in diag.message
    assert diag.targets == tuple(r.id for r in rects)


def test_three_stroke_widths_are_fine():
    figure, _ = stroke_row(0.1, 0.2, 0.3)
    assert lint(figure) == []


def test_stroke_width_budget_is_configurable():
    figure, _ = stroke_row(0.1, 0.2, 0.3)
    diag = only(lint(figure, max_stroke_widths=2), "INCONSISTENT_STROKE")
    assert "3 distinct stroke widths" in diag.message


def ribbon_row(*widths: float) -> Diagram:
    """A width scale: each edge's weight is the datum it carries."""
    ribbons = [Diagram(prim=RectPrim(10.0, 6.0), kind=encoded("connector"))
               .styled(stroke="#000000", stroke_width=w).named(f"e{i}")
               for i, w in enumerate(widths)]
    return group([r.translated((i + 1) * 20.0, 0.0) for i, r in enumerate(ribbons)])


def test_a_declared_width_scale_is_not_an_inconsistency():
    figure = ribbon_row(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
    assert [d for d in lint(figure) if d.code == "INCONSISTENT_STROKE"] == []


def test_chosen_widths_are_still_counted_beside_a_scale():
    chosen, _ = stroke_row(0.1, 0.2, 0.3, 0.5)
    figure = group([chosen, ribbon_row(0.8, 0.9, 1.0).translated(0.0, 40.0)])

    diag = only(lint(figure), "INCONSISTENT_STROKE")

    assert "4 distinct stroke widths" in diag.message
    assert "3 further width(s) carry data" in diag.message
    assert "0.80mm" not in diag.message


def test_a_scale_width_shared_with_a_chosen_one_is_not_double_reported():
    chosen, _ = stroke_row(0.1, 0.2, 0.3, 0.5)
    figure = group([chosen, ribbon_row(0.1, 0.2).translated(0.0, 40.0)])

    diag = only(lint(figure), "INCONSISTENT_STROKE")

    assert "further width(s)" not in diag.message


def ribbon(name: str = "ribbon", **style) -> Diagram:
    """A diagonal band, the shape a Sankey flow makes between two rows.

    It fills 40% of its own 30x18mm bounding box, which is the whole reason
    this rule cannot answer with boxes: most of that box is white.
    """
    node = polygon([(0.0, 0.0), (30.0, 14.0), (30.0, 18.0), (0.0, 4.0)], **style)
    return node.named(name)


def beside(node: Diagram, label: Diagram, dx: float, dy: float) -> Diagram:
    return group([node, label.translated(dx, dy)])


def box_overlap(figure: Diagram, a: Diagram, b: Diagram) -> float:
    """The area a box-against-box test would have claimed."""
    placed = resolve(figure)
    hit = placed[a.id].bbox.overlap(placed[b.id].bbox)
    return 0.0 if hit is None else hit.width * hit.height


def reported_area(diag: Diagnostic) -> float:
    return float(re.search(r"over ([\d.]+)mm\^2", diag.message).group(1))


def test_a_label_on_a_drawn_bar_is_measured_against_the_bar():
    """Everything `inklet.draw` emits is a PathPrim. Before this, white text on a
    filled blue bar was contrast-checked against the page and reported at
    1.00:1 -- the draw layer was penalised for not being a RectPrim."""
    bar = polygon([(0.0, 0.0), (40.0, 0.0), (40.0, 12.0), (0.0, 12.0)],
                  fill="#0072b2").named("bar")
    label = text("35 %", 10.0, name="pct", text_fill="#ffffff")

    assert [d for d in lint(group([bar, label])) if d.code == "LOW_CONTRAST"] == []


def test_a_label_only_half_on_a_drawn_shape_gets_no_backdrop():
    """Half a backdrop is not a backdrop: there is no single colour behind the
    text to measure against, so the page stays the answer."""
    curve, label = ribbon(fill="#0072b2"), text("100 %", 12.0, name="pct",
                                                text_fill="#ffffff")
    figure = beside(curve, label, -12.0, -3.0)

    assert only(lint(figure), "LOW_CONTRAST").targets == (label.id,)


def test_a_label_in_the_white_part_of_a_curves_box_does_not_overlap_it():
    """31mm^2 of box against box, and not one square millimetre of ink."""
    curve, label = ribbon(), text("100 %", 12.0, name="pct")
    figure = beside(curve, label, -10.0, 6.0)

    assert box_overlap(figure, curve, label) > 30.0
    assert [d for d in lint(figure) if d.code == "OVERLAP"] == []


def test_a_label_on_the_ink_still_overlaps():
    curve, label = ribbon(), text("100 %", 12.0, name="pct")

    diag = only(lint(beside(curve, label, -12.0, -3.0)), "OVERLAP")

    assert "pct" in diag.message and "ribbon" in diag.message


def test_the_reported_area_is_the_ink_not_the_box():
    curve, label = ribbon(), text("100 %", 12.0, name="pct")
    figure = beside(curve, label, -12.0, -3.0)

    diag = only(lint(figure), "OVERLAP")

    assert reported_area(diag) == pytest.approx(13.30, abs=0.01)
    assert box_overlap(figure, curve, label) == pytest.approx(25.40, abs=0.01)


# -- 9. CROWDING ----------------------------------------------------------


def test_neighbours_under_a_millimetre_apart_are_crowded():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(10.4, 0.0)

    diag = only(lint(group([a, b])), "CROWDING")

    assert diag.severity == "info"
    assert diag.targets == tuple(sorted((a.id, b.children[0].id)))
    assert "only 0.40mm apart" in diag.message
    assert "add 0.60mm" in diag.hint


def test_three_millimetre_neighbours_are_fine():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(13.0, 0.0)
    assert lint(group([a, b])) == []


def test_crowding_clearance_is_configurable():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(12.0, 0.0)
    assert only(lint(group([a, b]), min_clearance_mm=3.0), "CROWDING")


# -- 9a. CROWDING: a link's own endpoints ---------------------------------
#
# `route()` clips a connector to the real boundary of the shapes it joins, so
# an arrowhead resting on its target is the feature, not a defect. It is
# exempt; the same head near a shape the link never touched is not.


def connected(content: list[Diagram], source: Diagram, target: Diagram,
              **kwargs) -> Diagram:
    """Content plus its routed link, composed the way `Figure.build` does."""
    laid_out = group(content)
    routed = route(make_link(source, target, **kwargs), resolve(laid_out))
    return Diagram(children=(laid_out, routed), kind="content")


def heads_in(figure: Diagram) -> list[Diagram]:
    return [node for node in figure.walk() if node.kind == HEAD_KIND]


def test_an_arrowhead_touching_its_own_target_is_not_crowding():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(20.0, 0.0)

    figure = connected([a, b], a, b.children[0])

    assert lint(figure) == []


def test_route_records_the_nodes_a_link_was_clipped_to():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(20.0, 0.0)
    content = group([a, b])

    routed = route(make_link(a, b.children[0]), resolve(content))

    assert routed.attached_to == (a.id, b.children[0].id)


def test_an_arrowhead_near_a_box_it_is_not_attached_to_still_fires():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(20.0, 0.0)
    # The head runs from (13, 0) to (15, 0); this sits 0.30mm above it and
    # a clear 2mm short of b, so only the head-to-bystander pair is close.
    bystander = box(2.0, 2.0, name="bystander").translated(12.0, 2.0)

    figure = connected([a, b, bystander], a, b.children[0])
    diag = only(lint(figure), "CROWDING")

    head = only_one(heads_in(figure))
    assert diag.targets == tuple(sorted((head.id, bystander.children[0].id)))
    assert "0.30mm apart" in diag.message


def test_a_link_is_not_crowded_by_its_own_label():
    """A label on an arrow rests on the arrow. That is the arrow working.

    `examples/hello_figure.py` is the acceptance test whose docstring promises
    zero diagnostics, and it reported four of these -- an arrowhead against the
    plate behind its own label, twice per link.
    """
    # hello_figure's own proportions: a 6mm gap, so the label sits on the
    # short shaft with the head right beside it.
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 16.0)

    figure = connected([a, b], a, b.children[0], label=text("dF/F", 5.0))

    assert lint(figure) == []


# -- 9b. CROWDING: deliberate arrangements --------------------------------


def lattice(rows: int, cols: int, side: float = 4.0, gap: float = 0.5) -> Diagram:
    """A grid of evenly spaced cells under one named container."""
    pitch = side + gap
    cells = [box(side, side, name=f"c{r}{c}").translated(c * pitch, r * pitch)
             for r in range(rows) for c in range(cols)]
    return Diagram(children=tuple(cells), kind="grid").named("matrix")


def test_a_grid_reports_one_finding_per_gap_not_one_per_pair():
    matrix = lattice(3, 3)

    crowding = [d for d in lint(matrix) if d.code == "CROWDING"]

    # 36 pairs in all; 12 orthogonal neighbours at 0.50mm and 8 diagonal ones
    # at 0.71mm are under the clearance, and they collapse to two findings.
    assert len(crowding) == 2
    messages = sorted(d.message for d in crowding)
    assert messages[0] == ("12 pairs of cells inside matrix are 0.50mm apart, "
                           "under the 1.00mm clearance")
    assert messages[1] == ("8 pairs of cells inside matrix are 0.71mm apart, "
                           "under the 1.00mm clearance")


def test_an_aggregated_finding_still_names_every_node_involved():
    matrix = lattice(3, 3)
    cells = [node for node in matrix.walk() if node.kind == "box"]

    tight = only([d for d in lint(matrix) if "0.50mm" in d.message], "CROWDING")

    assert tight.severity == "info"
    assert tight.targets == tuple(sorted(node.id for node in cells))
    assert "add 0.50mm of separation inside matrix" in tight.hint


def test_a_pair_or_two_is_still_reported_pair_by_pair():
    """Aggregation is for floods. Two findings read better named than counted."""
    row = lattice(1, 3)

    crowding = [d for d in lint(row) if d.code == "CROWDING"]

    assert len(crowding) == 2
    assert all("only 0.50mm apart" in d.message for d in crowding)


def test_pairs_are_only_pooled_within_a_shared_container():
    left = lattice(1, 3)
    right = lattice(1, 3).translated(40.0, 0.0)

    crowding = [d for d in lint(group([left, right])) if d.code == "CROWDING"]

    # Four pairs at the same 0.50mm gap, but two containers: pooling them
    # would name a grid that holds none of them.
    assert len(crowding) == 4



# -- 9c. CROWDING: lines of type ------------------------------------------
#
# The clearance floor is a distance between objects. Leading is a multiple of
# the type size, and at small sizes it is far under a millimetre -- so a
# well-set paragraph tripped this rule once per pair of lines, and the only fix
# available to a blind author was to open the leading until the linter stopped
# talking.


def lines(*contents: str, gap: float = 0.4, size_pt: float = 8.0,
          width: float = 20.0) -> Diagram:
    """Text lines stacked the way `vstack` stacks them."""
    height = text_height(size_pt)
    stacked = [text(content, width, size_pt, name=f"line{i}")
               .translated(0.0, i * (height + gap))
               for i, content in enumerate(contents)]
    return Diagram(children=tuple(stacked), kind="stack").named("para")


def test_leading_between_stacked_lines_is_not_crowding():
    assert lint(lines("Received allocated", "intervention (n = 391)")) == []


def test_leading_stays_quiet_when_the_clearance_is_swept_up():
    """A sweep raises the bar for objects. Type is still not two objects."""
    para = lines("Received allocated", "intervention (n = 391)")

    assert lint(para, min_clearance_mm=2.0) == []


def test_a_gap_wider_than_the_type_is_two_blocks_again():
    # 8pt type is 2.82mm; 2.9mm between the lines is past any leading.
    para = lines("one", "two", gap=2.9)

    assert codes(lint(para, min_clearance_mm=4.0)) == ["CROWDING"]


def test_words_jammed_together_sideways_still_report():
    """Leading is vertical. Two words 0.4mm apart on a line is not leading."""
    height = text_height()
    row = Diagram(children=(text("word", 8.0, name="a"),
                            text("jam", 8.0, name="b").translated(8.4, 0.0)),
                  kind="stack").named("row")

    assert codes(lint(row)) == ["CROWDING"]
    assert height > 0.0


def test_two_boxes_in_a_stack_are_still_crowded():
    """The exemption is about type, not about stacks."""
    column = Diagram(children=(box(10.0, 4.0, name="a"),
                               box(10.0, 4.0, name="b").translated(0.0, 4.4)),
                     kind="stack").named("column")

    assert codes(lint(column)) == ["CROWDING"]


def test_text_that_no_stack_put_together_is_still_crowded():
    """Two labels that merely land near each other are worth a word."""
    height = text_height()
    loose = group([text("alpha", 10.0, name="alpha"),
                   text("beta", 10.0, name="beta").translated(0.0, height + 0.4)])

    assert codes(lint(loose)) == ["CROWDING"]


# -- 9d. CROWDING: a gap the author asked for -----------------------------
#
# `hstack(..., gap=th.gap("2xs"))` is a number the author wrote, and it applies
# to every pair the stack makes. Reporting it is a complaint about the theme's
# smallest token wearing a figure's name, and the only fix is to stop using the
# token. The declaration travels in `Diagram.notes` (core M17); the tests below
# write it by hand so they hold whether or not `inklet.layout` has been taught to.


def column(gap: float, declared: float | None) -> Diagram:
    """Two boxes one under the other, and what the stack says it asked for."""
    node = Diagram(children=(box(10.0, 4.0, name="a"),
                             box(10.0, 4.0, name="b").translated(0.0, 4.0 + gap)),
                   kind="stack").named("column")
    return node if declared is None else node.note("gap", declared)


def test_the_gap_a_stack_declared_is_not_crowding():
    assert codes(lint(column(0.4, 0.4))) == []


def test_a_declared_gap_does_not_excuse_a_different_one():
    """The exemption is the measurement matching, not the stack existing: a
    child whose ink reaches past its neighbour's closes a gap nobody asked
    for, and that is the finding worth keeping."""
    assert codes(lint(column(0.4, 0.5))) == ["CROWDING"]


def test_an_undeclared_stack_behaves_as_it_always_did():
    assert codes(lint(column(0.4, None))) == ["CROWDING"]


def test_a_declaration_does_not_reach_inside_one_child():
    """A stack separates neighbours. Two things pushed together inside one of
    them got there some other way, however wide the stack's own gap is."""
    pair = box(24.0, 4.0, box(10.0, 4.0, name="a").translated(-5.2, 0.0),
               box(10.0, 4.0, name="b").translated(5.2, 0.0))
    stack = Diagram(children=(pair, box(24.0, 4.0, name="c").translated(0.0, 4.4)),
                    kind="stack").named("column").note("gap", 0.4)

    assert codes(lint(stack)) == ["CROWDING"]


def test_the_stack_helper_is_honoured_end_to_end():
    """`inklet.layout` stamps the gap itself, so a real stack needs no help."""
    from inklet.layout import hstack, vstack

    rows = vstack([hstack([box(6.0, 3.0, name=f"s{n}"),
                           text(f"{n} %", 6.0, name=f"t{n}")], gap=0.5)
                   for n in range(3)], gap=4.0)

    assert [d for d in lint(rows) if d.code == "CROWDING"] == []


# -- 10. LINK_CROSSES -----------------------------------------------------
#
# The bbox rules cannot see this one at all: a vertical shaft's bounding box is
# zero-width, and `_pairable` drops unfilled paths for exactly that reason. So
# every case here is about segment geometry against a real outline.


def link_in(figure: Diagram) -> Diagram:
    """The routed link group -- the node that recorded what it was clipped to."""
    return only_one([node for node in figure.walk() if node.attached_to])


def bystander(*children: Diagram, width: float = 20.0,
              declared: bool = False) -> Diagram:
    """`a` above, `b` below, and a wide box sitting squarely between them.

    `declared=True` tells the link it crosses that box on purpose.
    """
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 40.0)
    mid = box(width, 8.0, *children, name="mid").translated(0.0, 20.0)
    through = (mid.children[0],) if declared else ()
    return (connected([a, b, mid], a, b.children[0], through=through),
            mid.children[0])


def dogleg(**kwargs) -> Diagram:
    """A small box parked on the diagonal between two corners.

    A straight shaft runs through it. An orthogonal route leaves east, jogs
    across at the midpoint and arrives west, which clears it.
    """
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(30.0, 30.0)
    mid = box(5.0, 5.0, name="mid").translated(20.0, 20.0)
    return connected([a, b, mid], a, b.children[0], **kwargs)


def test_a_shaft_through_a_bystander_is_reported():
    figure, mid = bystander()

    diag = only(lint(figure), "LINK_CROSSES")

    assert diag.severity == "warning"
    assert diag.targets == (link_in(figure).id, mid.id)
    assert "runs through mid for 8.00mm" in diag.message
    assert "move mid off the line between a -> b" in diag.hint


def test_a_crossed_label_is_an_error_and_is_folded_into_its_box():
    caption = text("INNOCENT BYSTANDER", 18.0, name="bystander")
    figure, mid = bystander(caption, width=22.0)

    diag = only(lint(figure), "LINK_CROSSES")

    assert diag.severity == "error"
    assert diag.targets == (link_in(figure).id, mid.id, caption.id)
    assert "cutting through bystander 'INNOCENT BYSTANDER'" in diag.message


def test_a_link_only_touching_its_own_endpoints_is_silent():
    caption = text("Encoder", 14.0, name="cap")
    a = box(20.0, 10.0, name="a")
    b = box(20.0, 10.0, caption, name="b").translated(0.0, 30.0)

    assert lint(connected([a, b], a, b.children[0])) == []


def test_a_straight_shaft_crosses_where_an_elbow_does_not():
    assert only(lint(dogleg()), "LINK_CROSSES")
    assert lint(dogleg(route="orthogonal")) == []


def test_a_shaft_passing_near_without_touching_is_silent():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 40.0)
    # The shaft runs down x = 0; this starts 6mm east of it.
    near = box(6.0, 6.0, name="near").translated(9.0, 20.0)

    assert lint(connected([a, b, near], a, b.children[0])) == []


def test_a_shaft_running_along_a_box_edge_is_not_a_crossing():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 40.0)
    # Its left edge is exactly x = 0, which is where the shaft runs. Counting
    # boundary hits alone would call the whole 10mm edge a crossing.
    graze = box(10.0, 10.0, name="graze").translated(5.0, 20.0)

    assert lint(connected([a, b, graze], a, b.children[0])) == []


def test_an_ellipse_is_judged_by_its_outline_not_its_bounding_box():
    a = box(6.0, 2.0, name="a").translated(1.0, -11.0)
    b = box(6.0, 2.0, name="b").translated(15.0, 3.0)
    # The shaft clips the corner of the ellipse's bounding box between
    # (8, -4) and (10, -2), and stays outside the curve the whole way.
    ellipse = Diagram(prim=EllipsePrim(10.0, 4.0), kind="ellipse").named("ell")

    assert lint(connected([a, b, ellipse], a.children[0], b.children[0])) == []


def test_an_arrow_leaving_the_container_it_started_in_is_silent():
    inner = box(8.0, 8.0, name="inner")
    panel = box(20.0, 20.0, inner, name="panel")
    outside = box(8.0, 8.0, name="outside").translated(40.0, 0.0)

    assert lint(connected([panel, outside], inner, outside)) == []


def test_connectors_crossing_each_other_are_link_crosses_links_business():
    """`LINK_CROSSES` is about a route over a *shape*. Two routes over each
    other are `LINK_CROSSES_LINK` -- see `test_diagnostics_links.py`."""
    p = box(8.0, 8.0, name="p")
    q = box(8.0, 8.0, name="q").translated(30.0, 0.0)
    r = box(8.0, 8.0, name="r").translated(0.0, 30.0)
    s = box(8.0, 8.0, name="s").translated(30.0, 30.0)
    laid_out = group([p, q, r, s])
    placements = resolve(laid_out)
    diagonals = (route(make_link(p, s.children[0]), placements),
                 route(make_link(r.children[0], q.children[0]), placements))

    assert codes(lint(Diagram(children=(laid_out,) + diagonals,
                              kind="content"))) == ["LINK_CROSSES_LINK"]


def test_a_hand_drawn_path_records_no_endpoints_and_link_crosses_leaves_it_alone():
    """`LINK_CROSSES` reads a routed link's `attached_to`, and a hand-drawn
    path has none, so this one belongs to `PATH_CROSSES` -- which does report
    it. See `test_diagnostics_paths.py`."""
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(40.0, 0.0)
    victim = box(8.0, 8.0, name="victim").translated(20.0, 30.0)
    stray = Diagram(prim=PathPrim.polyline([Vec2(20.0, 20.0), Vec2(20.0, 40.0)]),
                    kind="path").named("stray")

    found = lint(connected([a, b, victim, stray], a, b.children[0]))

    assert [d.code for d in found] == ["PATH_CROSSES"]


def test_one_finding_per_crossed_shape():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 60.0)
    first = box(20.0, 8.0, name="m1").translated(0.0, 20.0)
    second = box(20.0, 8.0, name="m2").translated(0.0, 40.0)

    diags = [d for d in lint(connected([a, b, first, second], a, b.children[0]))
             if d.code == "LINK_CROSSES"]

    assert [d.targets[1] for d in diags] == [first.children[0].id,
                                             second.children[0].id]


def test_parts_of_one_object_are_one_finding():
    """A shaft through a mesh cuts a dozen facets, and the author moves the
    mirror rather than its eleventh triangle."""
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 60.0)
    slabs = [box(20.0, 4.0).translated(0.0, y) for y in (20.0, 28.0, 36.0)]
    mirror = Diagram(children=tuple(slabs), kind="group").named("mirror")

    diag = only(lint(connected([a, b, mirror], a, b.children[0])), "LINK_CROSSES")

    assert "runs through mirror across 3 of its parts" in diag.message
    # The deepest run, not the sum: parts of one solid overlap in projection.
    assert "up to 4.00mm through one" in diag.message
    assert "move mirror off the line" in diag.hint
    assert len(diag.targets) == 4          # the link and all three slabs


def test_one_part_of_an_object_is_reported_as_the_object():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 60.0)
    slab = box(20.0, 4.0).translated(0.0, 30.0)
    mirror = Diagram(children=(slab,), kind="group").named("mirror")

    diag = only(lint(connected([a, b, mirror], a, b.children[0])), "LINK_CROSSES")

    assert "runs through mirror for 4.00mm" in diag.message


def test_a_crossed_label_inside_an_object_still_quotes_its_words():
    """Rolling a label up into its group would trade the one thing that
    identifies it -- what it says -- for the name of a container."""
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 60.0)
    caption = text("SIGNAL", 18.0)
    legend = Diagram(children=(caption,), kind="group").named("legend")

    diags = lint(connected([a, b, legend.translated(0.0, 30.0)], a, b.children[0]))

    assert "'SIGNAL'" in only(diags, "LINK_CROSSES").message


def test_a_declared_pass_through_is_not_a_crossing():
    """A beam that stops at the dichroic it transmits through is a lie about
    the instrument, so a figure has to be able to say which one it is."""
    reported, _ = bystander()
    declared, _ = bystander(declared=True)

    assert "LINK_CROSSES" in codes(lint(reported))
    assert "LINK_CROSSES" not in codes(lint(declared))


def test_a_pass_through_is_not_an_end_of_the_arrow():
    """`a -> b -> mid` would be a lie of a different kind, and an elbow has no
    corner to put between an endpoint and something the line runs over."""
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(0.0, 60.0)
    mid = box(20.0, 8.0, name="mid").translated(0.0, 20.0)
    victim = box(20.0, 8.0, name="victim").translated(0.0, 40.0)
    figure = connected([a, b, mid, victim], a, b.children[0],
                       through=(mid.children[0],))

    diag = only(lint(figure), "LINK_CROSSES")

    assert "(a -> b)" in diag.message
    assert "runs through victim" in diag.message


def test_link_crosses_is_deterministic():
    figure, _ = bystander(text("INNOCENT BYSTANDER", 18.0, name="cap"), width=22.0)
    first, second = lint(figure), lint(figure)

    assert first == second
    assert format_report(first) == format_report(second)


# -- 10a. LINK_COLLAPSED --------------------------------------------------
#
# The router already knows when a connector came out as a point: it flags the
# link and draws something harmless. What it could not do until now was say so,
# and an arrow that is missing from a panel of thirty is not something anyone
# finds by looking.


def test_a_link_between_overlapping_shapes_is_reported_as_collapsed():
    a = box(10.0, 10.0, name="a")
    # Four millimetres apart on a ten-millimetre box: the clip points cross
    # over, and `route` draws a point rather than an arrow pointing backwards.
    b = box(10.0, 10.0, name="b").translated(4.0, 0.0)

    figure = connected([a, b], a, b.children[0])
    diag = only(lint(figure), "LINK_COLLAPSED")

    # An error, not a warning: a point is not a shorter arrow. The stub case
    # below still draws a line going the right way, and stays a warning.
    assert diag.severity == "error"
    assert "a -> b" in diag.message
    assert "drawn as a point" in diag.message


def test_a_link_with_room_to_draw_says_nothing():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(30.0, 0.0)

    assert lint(connected([a, b], a, b.children[0])) == []


def test_a_collapsed_link_is_named_as_its_author_named_it():
    # Routing appends its flags to the link's name because a Diagram has
    # nowhere else to keep them. That is an internal channel, and a report
    # about `beam!zero-length` is a report about the wrong thing.
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(4.0, 0.0)

    figure = connected([a, b], a, b.children[0], name="beam")
    diag = only(lint(figure), "LINK_COLLAPSED")

    assert diag.message.startswith("beam (a -> b)")
    assert "!" not in diag.message


def test_a_link_shorter_than_its_own_arrowhead_is_reported():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(11.6, 0.0)

    figure = connected([a, b], a, b.children[0], arrow_size=4.0)
    diag = only(lint(figure), "LINK_COLLAPSED")

    assert diag.severity == "warning"
    assert "shorter than its own arrowhead" in diag.message
    assert "arrow_size" in diag.hint


# -- 10b. LINK_UNCLIPPED --------------------------------------------------
#
# Clipping is the promise the whole library opens with. When the router cannot
# keep it, it aims at the centre instead -- the head buries itself in the fill,
# or drives through an outline into the middle of it. Nothing overlaps and
# nothing overflows, so this is the one class of defect a blind author has no
# other way at all to find.


def ring(name: str) -> Diagram:
    """A C opening west, whose bbox centre sits in the opening rather than in
    the shape. Clipping fires a ray from that centre back towards the source;
    through the opening it crosses no boundary at all."""
    return polygon([(5.0, -5.0), (-5.0, -5.0), (-5.0, -3.0), (3.0, -3.0),
                    (3.0, 3.0), (-5.0, 3.0), (-5.0, 5.0), (5.0, 5.0)],
                   fill="#cccccc").named(name)


def hairline_c(name: str) -> Diagram:
    """`ring` drawn a tenth of a millimetre thick: the same failed clip, but
    now there is nothing on the page to aim at either."""
    t = 0.1
    return polygon([(5.0, -5.0), (-5.0, -5.0), (-5.0, -5.0 + t), (5.0 - t, -5.0 + t),
                    (5.0 - t, 5.0 - t), (-5.0, 5.0 - t), (-5.0, 5.0), (5.0, 5.0)],
                   fill="#cccccc").named(name)


def test_a_link_to_something_that_draws_nothing_is_reported():
    a = box(10.0, 10.0, name="a")
    ghost = Diagram(prim=PhantomPrim(Rect(-1.0, -1.0, 1.0, 1.0)), kind="spacer").named("ghost")
    figure = connected([a, ghost.translated(30.0, 0.0)], a, ghost)

    diag = only(lint(figure), "LINK_UNCLIPPED")

    assert diag.severity == "warning"
    assert "the target end is not clipped" in diag.message
    assert "ran to its centre" in diag.message
    assert ".at(" in diag.hint


def test_the_side_that_failed_is_the_side_reported():
    ghost = Diagram(prim=PhantomPrim(Rect(-1.0, -1.0, 1.0, 1.0)), kind="spacer").named("ghost")
    b = box(10.0, 10.0, name="b").translated(30.0, 0.0)
    figure = connected([ghost, b], ghost, b.children[0])

    diag = only(lint(figure), "LINK_UNCLIPPED")

    assert "the source end is not clipped" in diag.message
    assert diag.targets[1] == ghost.id


def test_a_shape_whose_centre_is_outside_it_is_reported():
    a = box(10.0, 10.0, name="a")
    c = ring("c").translated(30.0, 0.0)

    figure = connected([a, c], a, c)
    diag = only(lint(figure), "LINK_UNCLIPPED")

    assert "centre outside its own outline" in diag.message


def test_a_sliver_is_told_it_is_invisible_rather_than_offered_an_anchor():
    """The `{111}`-plane case: a part with no projected area to speak of.

    A crystal plane within two degrees of a three-quarter camera projects to a
    hairline whose bbox centre falls outside it, so the ray misses and the
    normal wording offers `.at(...)`. That is true and useless: no anchor
    makes an invisible part visible, and the author needs to be told to turn
    the camera.
    """
    a = box(10.0, 10.0, name="a")
    hairline = hairline_c("c").translated(30.0, 0.0)

    diag = only(lint(connected([a, hairline], a, hairline)), "LINK_UNCLIPPED")

    assert "of projected area over a" in diag.message
    assert "effectively invisible from this camera" in diag.message
    assert "centre outside" not in diag.message
    assert ".at(" not in diag.hint
    assert "turn the scene" in diag.hint


def test_a_ring_with_real_width_keeps_the_anchor_wording():
    """The near miss. `ring()` is 2mm thick: its centre is outside it, the
    clip really does fail, and `.at(...)` really is the fix."""
    a = box(10.0, 10.0, name="a")
    c = ring("c").translated(30.0, 0.0)

    diag = only(lint(connected([a, c], a, c)), "LINK_UNCLIPPED")

    assert "centre outside its own outline" in diag.message
    assert ".at(" in diag.hint


def test_a_target_that_draws_nothing_is_not_called_a_sliver():
    """A phantom has no ink and no box, so there is no projected area to
    measure and the reason it was flagged for stands."""
    a = box(10.0, 10.0, name="a")
    ghost = Diagram(prim=PhantomPrim(Rect(-1.0, -1.0, 1.0, 1.0)),
                    kind="spacer").named("ghost")

    diag = only(lint(connected([a, ghost.translated(30.0, 0.0)], a, ghost)),
                "LINK_UNCLIPPED")

    assert "projected area" not in diag.message


def test_an_anchored_endpoint_is_placed_rather_than_clipped():
    """The fix the hint offers has to actually work, or the rule is a trap."""
    a = box(10.0, 10.0, name="a")
    ghost = (Diagram(prim=PhantomPrim(Rect(-1.0, -1.0, 1.0, 1.0)), kind="spacer")
             .named("ghost").translated(30.0, 0.0))

    assert lint(connected([a, ghost], a, ghost.at("center"))) == []


def test_a_link_that_lands_properly_says_nothing():
    a = box(10.0, 10.0, name="a")
    b = box(10.0, 10.0, name="b").translated(30.0, 0.0)

    assert lint(connected([a, b], a, b.children[0])) == []


# -- 11. EMPTY_DIAGRAM ----------------------------------------------------


def test_a_node_with_no_prim_and_no_children_is_reported():
    hollow = Diagram(kind="g").named("hollow")
    figure = group([box(10.0, 10.0, name="real"), hollow])

    diag = only(lint(figure), "EMPTY_DIAGRAM")

    assert diag.severity == "warning"
    assert diag.targets == (hollow.id,)
    assert "draws nothing" in diag.message


def test_a_figure_with_nothing_drawable_is_an_error():
    figure = group([Diagram(prim=PhantomPrim(Rect(0.0, 0.0, 10.0, 10.0)), kind="pad")])

    diags = lint(figure)
    errors = [d for d in diags if d.severity == "error"]
    assert [d.code for d in errors] == ["EMPTY_DIAGRAM"]
    assert "0 visible primitives" in errors[0].message


def test_a_spacer_claiming_space_is_not_empty():
    from inklet.core import Envelope

    spacer = Diagram(envelope_override=Envelope.from_rect(Rect(0.0, 0.0, 5.0, 5.0)),
                     kind="pad").named("gutter")
    figure = group([box(10.0, 10.0, name="real").translated(20.0, 0.0), spacer])
    assert [d for d in lint(figure) if d.code == "EMPTY_DIAGRAM"] == []


def test_claimed_space_does_not_count_as_ink():
    # `envelope_override` inflates what the node reserves, not what it draws,
    # so the geometry rules keep measuring the primitive itself.
    from inklet.core import Envelope

    padded = Diagram(prim=RectPrim(4.0, 4.0),
                     envelope_override=Envelope.from_rect(Rect(-20.0, -20.0, 20.0, 20.0)),
                     kind="box").named("padded")
    label = text("label", 6.0, name="label").translated(10.0, 0.0)
    assert lint(group([padded, label])) == []


def test_a_populated_figure_is_not_empty():
    assert [d for d in lint(box(10.0, 10.0)) if d.code == "EMPTY_DIAGRAM"] == []


# -- 12. FONT_SUBSTITUTED -------------------------------------------------


def shaped_in(family: str, requested: str | None, name: str) -> Diagram:
    size = pt(8.0)
    return Diagram(
        prim=TextPrim(lines=(TextLine("Encoder", 18.0, 0.0),), font_family=family,
                      font_size=size, ascent=size * 0.8, descent=size * 0.2,
                      requested_family=requested),
        kind="text",
    ).named(name)


def test_a_substituted_font_is_reported_once_per_pair():
    labels = [shaped_in("Noto Sans", "Helvetica", f"l{i}").translated(0.0, i * 6.0)
              for i in range(4)]

    diag = only(lint(group(labels)), "FONT_SUBSTITUTED")

    assert diag.severity == "warning"
    assert len(diag.targets) == 4
    assert "4 text prim(s) asked for 'Helvetica' but were shaped with 'Noto Sans'" \
        in diag.message
    assert "+1 more" in diag.message


def test_the_font_that_was_asked_for_is_silent():
    label = shaped_in("Noto Sans", "Noto Sans", "l0")
    assert lint(group([label])) == []


def test_family_comparison_ignores_case_and_spacing():
    label = shaped_in("noto  sans", "Noto Sans", "l0")
    assert [d for d in lint(group([label])) if d.code == "FONT_SUBSTITUTED"] == []


def test_text_with_no_recorded_request_is_silent():
    label = shaped_in("Noto Sans", None, "l0")
    assert lint(group([label])) == []


def test_a_honoured_css_fallback_chain_is_not_a_substitution():
    """A chain ending in a generic says "or whatever you have", so honouring it
    is not an unmet request -- and the shipped theme asks exactly that way, so
    the rule fired on every correctly-written figure."""
    from inklet.typeset import shape as shape_text

    asked = "Helvetica Neue, Helvetica, Arial, sans-serif"
    prim = shape_text("Encoder", font=asked)
    assert prim.requested_family is None
    node = Diagram(prim=prim, kind="text").named("l0")
    assert [d for d in lint(group([node])) if d.code == "FONT_SUBSTITUTED"] == []


def test_a_chain_of_real_families_that_all_missed_is_still_reported():
    """Without a generic tail the author named the families they will accept,
    and getting none of them is worth saying."""
    from inklet.typeset import shape as shape_text

    prim = shape_text("Encoder", font="Helvetica Neue, Arial Narrow")
    if prim.requested_family is None:
        pytest.skip("this machine actually has one of those families")
    assert prim.requested_family == "Helvetica Neue"


# -- 13. MISSING_GLYPHS ---------------------------------------------------


def undrawable(name: str, missing: str = "\u4e00\u4e8c") -> Diagram:
    return Diagram(
        prim=TextPrim(lines=(TextLine("Encoder", 18.0, 0.0),), font_family="Noto Sans",
                      font_size=6.0, ascent=4.8, descent=1.2, missing=missing),
        kind="text",
    ).named(name)


def test_text_no_font_can_draw_is_an_error():
    diag = only(lint(group([undrawable("l0")])), "MISSING_GLYPHS")
    assert diag.severity == "error"
    assert "U+4E00 U+4E8C" in diag.message
    assert "l0" in diag.message


def test_undrawable_text_is_grouped_by_the_characters_that_are_missing():
    """One absent script ruins every string in a language; naming it once is
    the actionable form."""
    nodes = [undrawable(f"l{i}").translated(0.0, i * 8.0) for i in range(4)]
    nodes.append(undrawable("other", "\u13000").translated(40.0, 0.0))

    found = [d for d in lint(group(nodes)) if d.code == "MISSING_GLYPHS"]
    assert len(found) == 2
    counts = sorted(len(d.targets) for d in found)
    assert counts == [1, 4]
    assert "+1 more" in max(found, key=lambda d: len(d.targets)).message


def test_text_that_shaped_completely_is_silent():
    node = Diagram(
        prim=TextPrim(lines=(TextLine("Encoder", 18.0, 0.0),), font_family="Noto Sans",
                      font_size=6.0, ascent=4.8, descent=1.2),
        kind="text",
    ).named("l0")
    assert [d for d in lint(group([node])) if d.code == "MISSING_GLYPHS"] == []


# -- the whole-figure guarantees ------------------------------------------


def clean_figure() -> Diagram:
    """A well-formed two-box figure that every rule must stay silent about."""
    def labelled(caption: str, tag: str) -> Diagram:
        return box(30.0, 16.0, text(caption, 20.0, size_pt=9.0, name=f"{tag}-label",
                                    text_fill="#111111"),
                   name=tag, fill="#ffffff", stroke="#1a1a1a", stroke_width=0.25)

    left = labelled("Encoder", "enc").translated(25.0, 25.0)
    right = labelled("Decoder", "dec").translated(64.0, 25.0)
    connector = Diagram(
        prim=PathPrim.polyline([Vec2(40.0, 25.0), Vec2(49.0, 25.0)]), kind="path",
    ).named("edge").styled(stroke="#1a1a1a", stroke_width=0.25)
    return group([left, right, connector]).named("figure")


def test_a_clean_figure_produces_no_diagnostics():
    assert lint(clean_figure(), page=PAGE) == []


def test_format_report_of_a_clean_figure():
    assert format_report(lint(clean_figure(), page=PAGE)) == "inklet lint: clean, 0 diagnostics"


def messy_figure() -> Diagram:
    """One figure that trips several rules at once, for ordering tests."""
    overflowing = box(20.0, 10.0, text("Encoder (ViT-B/16)", 26.0, name="wide"),
                      name="enc", stroke="#000000", stroke_width=0.04)
    faint = text("subtitle", 30.0, size_pt=4.0, name="sub",
                 text_fill="#999999").translated(0.0, 14.0)
    stray = Diagram(prim=ImagePrim("logo.png", 30.0, 10.0, (100, 40)),
                    kind="img").named("logo").translated(120.0, 0.0)
    return group([overflowing, faint, stray]).named("messy").translated(30.0, 25.0)


def test_results_are_sorted_by_severity_then_code_then_targets():
    diags = lint(messy_figure(), page=PAGE)
    keys = [d.sort_key for d in diags]
    assert keys == sorted(keys)
    severities = [d.severity for d in diags]
    assert severities == sorted(severities, key=("error", "warning", "info").index)


def test_linting_is_deterministic_across_runs():
    figure = messy_figure()
    first = lint(figure, page=PAGE)
    second = lint(figure, page=PAGE)
    assert first == second
    assert [d.message for d in first] == [d.message for d in second]
    assert format_report(first) == format_report(second)


def test_an_identical_figure_built_twice_lints_identically():
    # Node ids differ between builds, so compare the shape of the findings.
    a = [(d.code, d.severity) for d in lint(messy_figure(), page=PAGE)]
    b = [(d.code, d.severity) for d in lint(messy_figure(), page=PAGE)]
    assert a == b


def test_messy_figure_trips_the_expected_rules():
    found = set(codes(lint(messy_figure(), page=PAGE)))
    assert {"TEXT_OVERFLOW", "TINY_TEXT", "HAIRLINE", "LOW_CONTRAST",
            "LOW_DPI", "OFF_CANVAS"} <= found


# -- API surface ----------------------------------------------------------


def test_rules_can_be_selected_by_code():
    diags = lint(messy_figure(), page=PAGE, rules=["TINY_TEXT"])
    assert set(codes(diags)) == {"TINY_TEXT"}


def test_an_unknown_rule_code_is_rejected():
    with pytest.raises(ValueError, match="unknown lint rule"):
        lint(clean_figure(), rules=["NOPE"])


def test_every_rule_is_independently_callable():
    for code in RULES:
        assert set(codes(lint(messy_figure(), page=PAGE, rules=[code]))) <= {code}


def test_a_raising_rule_does_not_kill_the_run():
    def broken(ctx):
        raise RuntimeError("boom")

    diags = lint(messy_figure(), page=PAGE,
                 rules={"BROKEN": broken, "TINY_TEXT": RULES["TINY_TEXT"]})
    failure = only(diags, "LINT_RULE_FAILED")
    assert failure.severity == "info"
    assert "rule BROKEN failed: RuntimeError: boom" in failure.message
    assert "TINY_TEXT" in codes(diags)


def test_lint_accepts_precomputed_placements():
    figure = messy_figure()
    placements = resolve(figure)
    assert lint(figure, page=PAGE, placements=placements) == lint(figure, page=PAGE)


def test_page_fill_switches_the_contrast_backdrop():
    label = text("dark on dark", 20.0, name="label", text_fill="#333333")
    figure = group([label])
    assert [d for d in lint(figure) if d.code == "LOW_CONTRAST"] == []
    assert only(lint(figure, page_fill="#000000"), "LOW_CONTRAST")


# -- report formatting ----------------------------------------------------


def test_format_report_groups_by_severity_with_a_summary():
    report = format_report(lint(messy_figure(), page=PAGE))
    lines = report.splitlines()

    assert lines[0].startswith("inklet lint: ")
    assert "error" in lines[0] and "warning" in lines[0]
    assert "ERROR" in lines and "WARNING" in lines
    assert all(line.startswith("  ") for line in lines
               if line and not line[0].isalpha() and line.strip())
    body = [line for line in lines if line.startswith("  ")]
    assert len(body) == len(lint(messy_figure(), page=PAGE))
    assert any("->" in line for line in body)


def test_format_report_can_colourise():
    diags = lint(messy_figure(), page=PAGE)
    assert "\x1b[31m" in format_report(diags, color=True)
    assert "\x1b[" not in format_report(diags, color=False)


# -- scale ----------------------------------------------------------------


def test_spatial_buckets_find_the_same_pairs_as_the_naive_sweep():
    boxes = [Rect(x, y, x + 4.0, y + 3.0)
             for x in range(0, 200, 5) for y in range(0, 60, 6)]
    assert len(boxes) > 200

    naive = {(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes))}
    bucketed = set(_candidate_pairs(boxes))

    overlapping = {(i, j) for (i, j) in naive
                   if boxes[i].overlap(boxes[j]) is not None}
    assert overlapping <= bucketed          # no real pair is missed
    assert len(bucketed) < len(naive) / 4   # and the sweep really did shrink


def test_keying_pairs_apart_drops_exactly_what_the_caller_would_have():
    """`apart=` is the caller's own filter moved earlier, not a tolerance.

    Both grid paths are exercised: 40 boxes takes the naive branch under
    `_NAIVE_LIMIT`, 480 takes the bucketed one.
    """
    for stride in (20, 5):
        boxes = [Rect(x, y, x + 4.0, y + 3.0)
                 for x in range(0, 200, stride) for y in range(0, 60, 6)]
        # Three blocks and a handful of unkeyed items, the shape a shaded
        # model makes: one huge block, two small ones, some loose furniture.
        keys = [None if i % 17 == 0 else f"block{i % 3}"
                for i in range(len(boxes))]
        kept = set(_candidate_pairs(boxes, apart=keys))
        expected = {(i, j) for (i, j) in _candidate_pairs(boxes)
                    if keys[i] is None or keys[i] != keys[j]}
        assert kept == expected
        assert kept                       # and it did not drop everything


def test_one_shaded_model_does_not_cost_a_quadratic_lint():
    """The kinase in `figures/drug_discovery.py`, in miniature.

    `inklet.model` merges each tone into one path spanning most of the object, so
    every candidate box overlaps every other and the grid gives nothing back.
    Before `apart=`, 3,575 such candidates meant 5.08 million pairs and 30
    seconds of ancestor walking to report two findings. The count is the test:
    a facet of one model paired against a facet of the same model is work no
    outcome depends on.
    """
    boxes = [Rect(0.0, 0.0, 60.0, 60.0)] * 600
    facets = ["kinase"] * 598 + [None, "pocket"]
    pairs = _candidate_pairs(boxes, apart=facets)
    assert len(pairs) == 598 + 598 + 1     # loose x mesh, pocket x mesh, and the two
    assert len(_candidate_pairs(boxes)) == 600 * 599 // 2


def test_a_large_figure_still_lints():
    labels = [text(f"n{i}", 6.0, name=f"n{i}").translated((i % 20) * 8.0,
                                                          (i // 20) * 8.0)
              for i in range(400)]
    diags = lint(group(labels))
    assert [d for d in diags if d.code == "OVERLAP"] == []
    assert [d for d in diags if d.code == "CROWDING"] == []


def test_a_large_well_formed_grid_stays_silent():
    cells = [box(6.0, 4.0, text(f"n{i}", 5.0, size_pt=6.0, name=f"t{i}"),
                 name=f"c{i}", fill="#ffffff", stroke="#000000", stroke_width=0.2)
             .translated(4.0 + (i % 20) * 9.0, 3.0 + (i // 20) * 7.0)
             for i in range(400)]
    assert lint(group(cells), page=Rect(0.0, 0.0, 200.0, 160.0)) == []


def test_a_themed_figure_does_not_report_its_own_arrowheads():
    """`apply_theme` rebuilds every node; the endpoint record has to survive it,
    or the whole report fills up with arrows touching what they point at."""
    import inklet

    a, b = inklet.box("one"), inklet.box("two")
    fig = inklet.figure(width="60mm")
    fig.add(inklet.vstack([a, b], gap=8))
    fig.link(a, b)

    assert [d for d in fig.lint() if d.code == "CROWDING"] == []


# -- inklet.theme integration ------------------------------------------------


def test_theme_contrast_is_used_when_available(monkeypatch):
    from inklet.diagnostics import color

    monkeypatch.setattr(color, "_theme_contrast_ratio", lambda a, b: 21.0)
    assert color.contrast_ratio("#808080", "#ffffff") == 21.0


@pytest.mark.parametrize("broken", [
    lambda a, b: 1 / 0,                 # raises
    lambda a, b: "not a number",        # wrong type
    lambda a, b: -5.0,                  # out of range
    lambda a, b: float("nan"),          # not finite
])
def test_a_broken_theme_falls_back_to_the_local_parser(monkeypatch, broken):
    from inklet.diagnostics import color

    monkeypatch.setattr(color, "_theme_contrast_ratio", broken)
    assert color.contrast_ratio("#808080", "#ffffff") == pytest.approx(3.95, abs=0.05)


def test_the_local_colour_parser_covers_the_usual_notations():
    from inklet.diagnostics.color import parse_color

    assert parse_color("#fff") == (1.0, 1.0, 1.0)
    assert parse_color("#FFFFFF") == (1.0, 1.0, 1.0)
    assert parse_color("white") == (1.0, 1.0, 1.0)
    assert parse_color("rgb(255, 255, 255)") == (1.0, 1.0, 1.0)
    assert parse_color("#ffffffff") == (1.0, 1.0, 1.0)
    assert parse_color("#ffffff80") is None       # translucent: unknowable
    assert parse_color("rgba(0,0,0,0.5)") is None
    assert parse_color("none") is None
    assert parse_color("var(--brand)") is None
    assert parse_color(None) is None


def test_ellipse_frames_are_treated_as_containers():
    label = text("wide", 30.0, name="label")
    frame = Diagram(prim=EllipsePrim(10.0, 6.0), children=(label,),
                    kind="ellipse").named("bubble")
    diag = only(lint(frame), "TEXT_OVERFLOW")
    assert diag.targets == (label.id, frame.id)


# -- CROWDING: data marks -------------------------------------------------

def mark(size: float = 1.0, name: str | None = None) -> Diagram:
    """A scatter point. `inklet.plot` gives these kind "mark"."""
    node = Diagram(prim=EllipsePrim(size / 2, size / 2), kind="mark")
    return node.named(name) if name else node


def plot_of(*marks_at: tuple[Diagram, float, float]) -> Diagram:
    """Marks positioned inside one panel, the way `Panel.marks` builds them:
    each wrapped in its own `place`, so no two marks are ever siblings."""
    return Diagram(
        children=tuple(m.translated(x, y) for m, x, y in marks_at),
        kind="plot-area",
    )


def test_two_marks_in_one_plot_closer_than_the_clearance_are_not_crowding():
    # 0.30mm apart, well under the 1.00mm default -- but that gap is what the
    # measurement says, not a layout slip.
    figure = plot_of((mark(), 0.0, 0.0), (mark(), 1.3, 0.0))

    assert lint(figure) == []


def test_marks_in_different_plots_still_crowd():
    left = plot_of((mark(), 0.0, 0.0))
    right = plot_of((mark(), 0.0, 0.0)).translated(1.3, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert "0.30mm" in diag.message


def facet(name: str | None = None) -> Diagram:
    """One triangle of a rendered solid. `inklet.three` gives these "model-facet"."""
    node = Diagram(prim=RectPrim(1.0, 1.0), kind="model-facet")
    return node.named(name) if name else node


def solid_of(*facets_at: tuple[Diagram, float, float]) -> Diagram:
    """Facets under one `model-facets` group, the way the 3D backend builds
    them: a mesh's triangles share edges, so their gaps are all near zero."""
    return Diagram(
        children=tuple(f.translated(x, y) for f, x, y in facets_at),
        kind="model-facets",
    )


def test_facets_of_one_solid_do_not_crowd_each_other():
    # A mesh's triangles touch by construction. 94 of the 132 infos on the
    # first sheet of stress/mega_figure were pairs of these.
    figure = solid_of((facet(), 0.0, 0.0), (facet(), 1.3, 0.0))

    assert lint(figure) == []


def test_facets_of_two_different_solids_still_crowd():
    left = solid_of((facet(), 0.0, 0.0))
    right = solid_of((facet(), 0.0, 0.0)).translated(1.3, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert "0.30mm" in diag.message


def test_two_near_solids_are_one_finding_naming_the_objects():
    """An author moves the mirror, not the mirror's eleventh triangle."""
    left = solid_of(*((facet(), 0.0, i * 3.0) for i in range(5))).named("mirror")
    right = solid_of(
        *((facet(), 0.0, i * 3.0) for i in range(5))
    ).named("dichroic").translated(1.3, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert "mirror and dichroic come within 0.30mm at 5 points" in diag.message
    assert "model-facet" not in diag.message
    assert len(diag.targets) == 10
    assert "move mirror or dichroic" in diag.hint


def test_two_near_solids_stay_one_finding_however_deeply_nested():
    """`inklet.three.scene` does not put a part's facets in one group.

    It splits them into a group per depth-sorted run, so one part of a protein
    had 445 of them. The collapse below keyed on that inner group rather than
    on the object the author named, so two touching parts produced a finding
    per *pair of runs* -- 7,798 infos on a cartoon protein whose parts touch
    because a protein is one chain. The finding is about the two objects, and
    there are two objects, so there is one finding.
    """
    def runs(offset: float) -> Diagram:
        return Diagram(
            children=tuple(
                solid_of(*((facet(), 0.0, row * 3.0) for row in range(2)))
                for _ in range(4)),
            kind="model-ink",
        ).translated(offset, 0.0)

    left = Diagram(children=(runs(0.0),), kind="model").named("hinge")
    right = Diagram(children=(runs(1.3),), kind="model").named("helix-d")

    diag = only(lint(group([left, right])), "CROWDING")

    assert "hinge and helix-d come within 0.30mm" in diag.message


def test_two_part_groups_of_one_solid_do_not_crowd_each_other():
    """A shaded solid is drawn as faces *and* creases: two groups over the same
    triangles, whose gaps are near zero because they are the same triangles.
    Reported, it reads `scan_lens and scan_lens come within 0.31mm`, which
    names nothing anybody can move."""
    faces = solid_of((facet(), 0.0, 0.0))
    creases = solid_of((facet(), 1.3, 0.0))
    lens = Diagram(children=(faces, creases), kind="model").named("scan_lens")

    assert lint(lens) == []


def test_a_single_touching_part_pair_does_not_claim_a_count():
    left = solid_of((facet(), 0.0, 0.0)).named("mirror")
    right = solid_of((facet(), 0.0, 0.0)).named("lens").translated(1.3, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert "come within 0.30mm, under" in diag.message


def test_a_label_grazing_a_facet_still_fires():
    """The exemption is about the mesh's own geometry. A label placed against
    it is furniture, and `objective 16x / 0.8 NA` 0.06mm from a facet is the
    finding this figure most needed to keep."""
    figure = group([
        solid_of((facet(), 0.0, 0.0)),
        text("objective", 8.0, name="objective").translated(4.9, 0.0),
    ])

    diag = only(lint(figure), "CROWDING")

    assert "objective" in diag.message


def test_the_page_is_never_the_object_a_finding_names():
    """`Figure.build` names the page, and `_object_of` walks up until it finds
    a name. A callout with nothing named above it therefore came back as
    `backbone and page2974 come within 0.00mm`, which names a thing no author
    can move. Above every object is the page; it is not one of them."""
    facets = solid_of(*((facet(), 0.0, row * 3.0) for row in range(3)))
    mesh = Diagram(children=(facets,), kind="model").named("backbone")
    ring = Diagram(prim=RectPrim(1.0, 1.0), kind="mark").translated(1.7, 3.0)
    page = Diagram(children=(mesh, ring), kind="page").named("page1")

    diag = only(lint(page), "CROWDING")

    assert "page1" not in diag.message
    assert "backbone" in diag.message


def test_a_label_near_one_named_solid_is_one_finding():
    """A leader that grazes a protein does not graze it forty-one times.

    Bounding boxes make this worse than it looks: a single cartoon beta strand
    is one 20x27mm triangle, so a callout nowhere near the *ink* still lands
    inside the box. Forty-one sentences about facets nobody named is noise
    around one thing an author can move, and they push the finding that matters
    off the end of the report.
    """
    facets = solid_of(*((facet(), 0.0, row * 3.0) for row in range(6)))
    mesh = Diagram(children=(facets,), kind="model").named("beta sheet")
    figure = group([mesh, text("P-loop", 8.0, name="P-loop").translated(4.9, 6.0)])

    diag = only(lint(figure), "CROWDING")

    assert "P-loop" in diag.message and "beta sheet" in diag.message
    assert "model-facet" not in diag.message
    assert "move" in diag.hint


def test_a_label_near_one_named_solid_keeps_the_computed_side_hint():
    facets = solid_of((facet(), 0.0, 0.0), (facet(), 0.0, 3.0))
    mesh = Diagram(children=(facets,), kind="model").named("lens")
    figure = group([mesh, text("f = 50", 8.0, name="f").translated(4.9, 1.5)])

    diag = only(lint(figure), "CROWDING")

    assert "was positioned by data" in diag.hint
    assert "rather than the mark" in diag.hint


def test_a_mark_crowding_a_label_still_fires():
    figure = group([
        plot_of((mark(), 0.0, 0.0)),
        text("caption", 8.0, name="caption").translated(4.9, 0.0),
    ])

    diag = only(lint(figure), "CROWDING")

    assert "caption" in diag.message


def test_a_thousand_marks_in_one_plot_still_resolve():
    """Envelope and Trace fold over every sibling. Chaining that fold as nested
    closures cost one stack frame per mark and raised RecursionError before the
    figure could be drawn -- at a mark count a spike raster reaches easily."""
    figure = plot_of(*((mark(), float(i) * 3.0, 0.0) for i in range(1000)))

    assert figure.bbox.width == pytest.approx(1000 * 3.0 - 3.0 + 1.0)
    assert lint(figure) == []


# -- CROWDING: a colour key's own bands ------------------------------------


def colorband(name: str | None = None) -> Diagram:
    """One slice of a colour key. `inklet.plot.key` gives these kind "colorband"."""
    node = Diagram(prim=RectPrim(2.6, 1.0), kind="colorband")
    return node.named(name) if name else node


def bar_of(*bands_at: tuple[Diagram, float, float]) -> Diagram:
    """Slices under one `colorbar` group, the way `_bands` builds them."""
    return Diagram(
        children=tuple(b.translated(x, y) for b, x, y in bands_at),
        kind="colorbar",
    )


def test_the_bands_of_one_colour_key_do_not_crowd_each_other():
    # `_bands` overlaps each slice into the next so the antialiased seam falls
    # inside solid colour. Slices exactly two apart therefore abut, and a
    # zero-area intersection arrives at CROWDING as a 0.00mm gap.
    figure = bar_of((colorband(), 0.0, 0.0), (colorband(), 0.0, 1.0))

    assert lint(figure) == []


def test_bands_of_two_different_colour_keys_still_crowd():
    left = bar_of((colorband(), 0.0, 0.0))
    right = bar_of((colorband(), 0.0, 0.0)).translated(2.9, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert "0.30mm" in diag.message


def test_a_band_near_something_unrelated_still_crowds():
    """The exemption is between bands, not a blanket pass for the key."""
    bar = bar_of((colorband(), 0.0, 0.0))
    neighbour = box(2.0, 2.0).translated(0.0, 1.8)      # 0.30mm below the band

    diag = only(lint(group([bar, neighbour])), "CROWDING")

    assert "0.30mm" in diag.message


@pytest.mark.parametrize("steps", [256, 128, 64, 32, 16, 8])
def test_a_real_colour_key_lints_clean_at_every_step_count(steps):
    """The regression this was written for: the library's own key generator
    could not lint clean at any step count, putting noise in the one feedback
    channel a blind author has."""
    import inklet

    inklet.use_theme("nature")
    bar = inklet.colorbar(inklet.ramp("tol-ylorbr"), domain=(0.0, 1.0),
                       length=32.0, thickness=2.6, steps=steps)
    figure = inklet.figure(width=60, theme="nature")
    figure.add(bar)

    assert figure.lint() == []


# -- CROWDING: the hint when only one side is data -------------------------


def near_a_mark(other: Diagram) -> list[Diagnostic]:
    """One data mark with something drawn 0.30mm to its right, in one panel.

    Siblings under one structural container, each in its own `place` -- which
    is how `Panel` builds a mark and an `over` item alike, and what makes the
    two share a source home when both are declared.
    """
    figure = Diagram(
        children=(mark().translated(0.0, 0.0), other.translated(1.3, 0.0)),
        kind="plot-area",
    )
    return [d for d in lint(figure) if d.code == "CROWDING"]


def test_a_mark_beside_a_drawn_shape_is_told_to_declare_it():
    """Moving the mark would falsify the plot, so the hint must not ask for it.

    This is blind-02's violin: jittered cells sitting just inside the KDE
    outline they belong to, and 36 infos telling the author to separate them.
    """
    shape = Diagram(prim=RectPrim(1.0, 1.0), kind="path").styled(fill="#ddd")

    diag = only_one(near_a_mark(shape))

    assert 'kind="mark"' in diag.hint
    assert "positioned by data" in diag.hint


def test_a_mark_beside_furniture_is_told_to_move_the_furniture():
    """Declaring a tick label as data would silence a finding that is real."""
    label = Diagram(prim=RectPrim(1.0, 1.0), kind="tick-label").styled(fill="#000")

    diag = only_one(near_a_mark(label))

    assert 'kind="mark"' not in diag.hint
    assert "move" in diag.hint


def test_declaring_the_drawn_shape_as_data_silences_the_pair():
    """The hint has to be true: doing what it says has to work."""
    declared = Diagram(prim=RectPrim(1.0, 1.0), kind="mark").styled(fill="#ddd")

    assert near_a_mark(declared) == []


def test_a_pair_with_neither_side_computed_keeps_the_plain_hint():
    left = box(4.0, 4.0)
    right = box(4.0, 4.0).translated(4.3, 0.0)

    diag = only(lint(group([left, right])), "CROWDING")

    assert diag.hint == "add 0.70mm of separation or padding"


# -- 10b. LINK_CROSSES, through another link's label ------------------------
#
# A link label rides an opaque plate, which covers the ink beneath it -- but
# only the ink already there. A connector routed afterwards is drawn over the
# plate, and the word it cuts through is as broken as a caption in a box.
# `route_all` re-places a label that a later shaft ran over, so the case the
# linter has to catch is the one where the links were routed separately.


def crossed_label(*, avoid: bool) -> tuple[Diagram, Diagram]:
    """A horizontal labelled link, and a vertical one drawn straight through
    the label. With `avoid=True` the second link is routed knowing about the
    first, the way `Figure.build` does it."""
    left = box(10.0, 10.0, name="left")
    right = box(10.0, 10.0, name="right").translated(60.0, 0.0)
    top = box(10.0, 10.0, name="top").translated(30.0, -30.0)
    bottom = box(10.0, 10.0, name="bottom").translated(30.0, 30.0)
    caption = text("LANE", 6.0, name="lane")
    laid_out = group([left, right, top, bottom])
    placements = resolve(laid_out)
    across = make_link(left, right.children[0], label=caption, label_offset=0.5)
    down = make_link(top, bottom.children[0])
    if avoid:
        routed = route_all([down, across], placements)
    else:
        routed = Diagram(children=(route(across, placements),
                                   route(down, placements)), kind="links")
    return Diagram(children=(laid_out, routed), kind="content"), caption


def test_a_shaft_through_another_links_label_is_an_error():
    figure, caption = crossed_label(avoid=False)

    diag = only(lint(figure), "LINK_CROSSES")

    assert diag.severity == "error"
    assert caption.id in diag.targets
    assert "'LANE'" in diag.message


def test_route_all_keeps_labels_off_every_shaft():
    figure, _ = crossed_label(avoid=True)

    assert not [d for d in lint(figure) if d.code == "LINK_CROSSES"]


def test_a_label_placed_before_a_later_shaft_is_moved_off_it():
    # The order that used to fail: the labelled link first, so its label was
    # placed knowing nothing about the shaft that came next.
    left = box(10.0, 10.0, name="left")
    right = box(10.0, 10.0, name="right").translated(60.0, 0.0)
    top = box(10.0, 10.0, name="top").translated(30.0, -30.0)
    bottom = box(10.0, 10.0, name="bottom").translated(30.0, 30.0)
    caption = text("LANE", 6.0, name="lane")
    laid_out = group([left, right, top, bottom])
    placements = resolve(laid_out)
    across = make_link(left, right.children[0], label=caption, label_offset=0.5)
    down = make_link(top, bottom.children[0])

    routed = route_all([across, down], placements)
    figure = Diagram(children=(laid_out, routed), kind="content")

    assert not [d for d in lint(figure) if d.code == "LINK_CROSSES"]
    label_x = resolve(figure)[caption.id].bbox.center.x
    assert abs(label_x - 30.0) > 3.0, "label still centred on the crossing shaft"
