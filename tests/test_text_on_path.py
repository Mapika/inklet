"""Type set along a curve, and type set at an angle.

Both features place a run that HarfBuzz already measured, so the assertions
here are about *where the advances went* -- millimetres and directions -- and
about the three contracts a placed run still has to keep: the same bytes
twice, a bbox that is the placed extent rather than the straight block's, and
words that are still words under `text="embed"`.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import pytest

import inklet
from inklet.core.geom import Vec2
from inklet.draw.coords import ORIGIN_ANCHOR
from inklet.render.glyphs import glyph_outline, placed_glyphs
from inklet.typeset import onpath as op

SVG = "{http://www.w3.org/2000/svg}"
WORD = "Hamburgefons"
SIZE = 2.4


def ink(node: inklet.Diagram) -> list[Vec2]:
    """Every outline point of a placed run, in the run's own coordinates."""
    out: list[Vec2] = []
    for child in node.children:
        for glyph in placed_glyphs(child.prim):
            for contour in glyph_outline(glyph, glyph.origin):
                out += [child.transform.apply(p) for p in contour.points]
    return out


def gaps(node: inklet.Diagram) -> list[float]:
    """Closest approach of each neighbouring pair of clusters' real outlines."""
    groups = []
    for child in node.children:
        pts = []
        for glyph in placed_glyphs(child.prim):
            for contour in glyph_outline(glyph, glyph.origin):
                pts += [child.transform.apply(p) for p in contour.points]
        groups.append(pts)
    return [min((p - q).length for p in a for q in b)
            for a, b in zip(groups, groups[1:])]


# -- item 1: an angle, and the sign of it ----------------------------------


def test_a_positive_angle_turns_clockwise_on_the_page():
    """The whole library's convention, pinned where an author will look."""
    east = inklet.text(WORD, size=4.0, angle=0.0)
    down = inklet.text(WORD, size=4.0, angle=90.0)
    assert east.bbox.width > east.bbox.height          # reads across
    assert down.bbox.height > down.bbox.width          # reads down the page
    # +90 sends +x to +y, and y grows downward, so the baseline now runs
    # *down* the page: the left end of the run is at the top.
    corner = down.transform.apply(Vec2(-east.bbox.width / 2, 0.0))
    assert corner.y < 0.0


def test_the_y_axis_label_is_minus_ninety():
    label = inklet.text("intensity", size=3.0, angle=-90)
    assert label.bbox.height > label.bbox.width
    assert label.transform.apply(Vec2(1.0, 0.0)).y < 0.0   # +x reads upward


def test_the_bbox_is_the_rotated_extent():
    straight = inklet.text(WORD, size=SIZE)
    turned = inklet.text(WORD, size=SIZE, angle=-90)
    assert turned.bbox.width == pytest.approx(straight.bbox.height)
    assert turned.bbox.height == pytest.approx(straight.bbox.width)


def test_rotation_turns_the_block_and_not_the_letters():
    """One transform over one shaped block -- not a glyph-by-glyph rebuild."""
    turned = inklet.text(WORD, size=SIZE, angle=30)
    assert turned.prim is None and len(turned.children) == 1
    assert turned.children[0].prim.text == WORD


# -- item 2: the curve ------------------------------------------------------


def test_one_child_per_shaping_cluster():
    """A ligature is one drawing and gets one station; a mark rides its base."""
    run = inklet.text_on_path("waffle fi", op.baseline_arc(20, -140, -40), size=3)
    assert [child.prim.text for child in run.children] == [
        "w", "a", "ffl", "e", " ", "fi"]


def test_an_empty_string_is_an_empty_node():
    """r7-polar generates tick labels in a loop and an empty one is legal."""
    run = inklet.text_on_path("", op.baseline_arc(20, -140, -40), size=3)
    assert run.children == () and run.prim is None


def test_the_envelope_is_the_curved_extent():
    """A run round a quarter circle is nothing like its straight block."""
    straight = inklet.text(WORD, size=SIZE)
    curved = inklet.text_on_path(WORD, op.baseline_arc(8, -180, -90), size=SIZE)
    assert curved.bbox.height > 3 * straight.bbox.height


def test_the_letters_sit_on_the_curve():
    """Every baseline lands on the circle it was set on, to a micron."""
    radius = 14.0
    run = inklet.text_on_path(WORD, op.baseline_arc(radius, -170, -10), size=SIZE)
    for child in run.children:
        seat = child.transform.apply(Vec2(0.0, child.prim.first_baseline))
        assert seat.length == pytest.approx(radius, abs=2e-3)


def test_side_below_hangs_the_run_under_the_curve():
    flat = op.baseline([(-30, 0), (30, 0)])
    above = inklet.text_on_path(WORD, flat, side="above", size=SIZE)
    below = inklet.text_on_path(WORD, flat, side="below", size=SIZE)
    # "above" seats the baseline on the curve, so the body stands off it and
    # the descenders cross; "below" drops the block by its own ascent, so the
    # top of the body is what touches and nothing at all is above the line.
    assert above.bbox.y0 < 0.0
    assert below.bbox.y0 == pytest.approx(0.0, abs=1e-9)
    assert below.bbox.y1 > above.bbox.y1
    # Same way up, not turned over: below is a shift, not a reversal.
    assert [c.prim.text for c in below.children] == \
           [c.prim.text for c in above.children]
    assert all(child.transform.d > 0 for child in below.children)


def test_lift_raises_the_run_clear_of_the_stroke():
    flat = op.baseline([(-30, 0), (30, 0)])
    sitting = inklet.text_on_path(WORD, flat, size=SIZE)
    lifted = inklet.text_on_path(WORD, flat, lift=1.0, size=SIZE)
    assert lifted.bbox.y1 == pytest.approx(sitting.bbox.y1 - 1.0)


def test_flip_keeps_the_lower_half_of_a_ring_the_right_way_up():
    lower = op.baseline_arc(16, 10, 170)
    upright = inklet.text_on_path("lower half", lower, flip=True, size=SIZE)
    inverted = inklet.text_on_path("lower half", lower, flip=False, size=SIZE)
    assert all(child.transform.d > 0 for child in upright.children)
    assert all(child.transform.d < 0 for child in inverted.children)
    # The flip turns the *run*, so the reading order is still the string's.
    xs = [child.transform.e for child in upright.children]
    assert xs == sorted(xs)


def test_align_survives_the_flip():
    """`align="start"` means the author's start of the curve, turned or not."""
    lower = op.baseline_arc(16, 10, 170)
    run = inklet.text_on_path("ab", lower, align="start", flip=True, size=SIZE)
    first = run.children[0].transform.apply(Vec2(0.0, 0.0))
    assert first.x > 0.0                    # bearing 10 deg, east of centre


def test_overflow_extend_runs_off_the_end_tangent():
    short = op.baseline([(-4, 0), (4, 0)])
    run = inklet.text_on_path("far too long for this", short, size=SIZE)
    assert run.bbox.width > 8.0             # it overhangs, visibly
    ys = [child.transform.f for child in run.children]
    assert max(ys) - min(ys) < 1e-9         # straight on, not curling


def test_overflow_raise_says_what_to_do_about_it():
    short = op.baseline([(-4, 0), (4, 0)])
    with pytest.raises(ValueError, match="overhang"):
        inklet.text_on_path("far too long for this", short,
                         overflow="raise", size=SIZE)


def test_a_bad_mode_names_the_modes():
    with pytest.raises(ValueError, match="extend"):
        inklet.text_on_path("x", op.baseline([(0, 0), (9, 0)]), overflow="clip")


# -- the pinch, and the pivot that answers it -------------------------------


def test_the_pivot_is_half_the_cap_height():
    face = inklet.typeset.load_face(inklet.text(WORD, size=SIZE).prim.font_path)
    assert face.cap_height > 0
    prim = inklet.text(WORD, size=SIZE).prim
    assert op._pivot_height(prim, None) == pytest.approx(
        face.cap_height * face.scale(SIZE) / 2)


def test_a_straight_run_is_unaffected_by_the_pivot():
    """The parallel of a straight line has the same length and the same
    stations, so the compensation cannot move straight type by a micron."""
    flat = op.baseline([(-30, 0), (30, 0)])
    turned = inklet.text_on_path(WORD, flat, size=SIZE)
    naive = inklet.text_on_path(WORD, flat, pivot=0.0, size=SIZE)
    for a, b in zip(turned.children, naive.children):
        assert a.transform.e == pytest.approx(b.transform.e, abs=1e-12)
        assert a.transform.f == pytest.approx(b.transform.f, abs=1e-12)


def test_the_pivot_opens_the_pinch_on_the_inside_of_a_tight_curve():
    """Measured, not asserted from theory: "Hamburgefons" at 2.4mm on a 5mm
    circle with the letters facing inward comes within 0.03mm of touching
    pivoted on the baseline and clears by 0.19mm pivoted at mid-cap, against
    0.24mm for the same string set straight."""
    inward = op.baseline_arc(5.0, 90, -270)
    naive = min(gaps(inklet.text_on_path(WORD, inward, flip=False, pivot=0.0,
                                      size=SIZE)))
    pivoted = min(gaps(inklet.text_on_path(WORD, inward, flip=False, size=SIZE)))
    straight = min(gaps(inklet.text_on_path(
        WORD, op.baseline([(-40, 0), (40, 0)]), size=SIZE)))
    assert naive < 0.05                          # ink all but touching
    assert pivoted > 6 * naive
    assert 0.6 < pivoted / straight < 1.4        # within half a stop of flat


def test_a_curve_tighter_than_the_pivot_still_sets():
    """The offset would fold; the run degrades to the naive placement rather
    than refusing the figure."""
    run = inklet.text_on_path("ab", op.baseline_arc(0.4, -180, 0), size=SIZE)
    assert len(run.children) == 2


# -- text_on_arc, the consumer's call ---------------------------------------


def test_text_on_arc_keeps_its_ink_clear_of_the_circle():
    for angle in (-90.0, -20.0, 45.0, 90.0, 175.0):
        run = inklet.text_on_arc("240", 12.0, angle, side="outside", gap=0.8,
                              size=SIZE)
        assert min(p.length for p in ink(run)) > 12.0 + 0.8 - 1e-6, angle


def test_text_on_arc_inside_stays_inside():
    for angle in (-90.0, 30.0, 120.0):
        run = inklet.text_on_arc("240", 12.0, angle, side="inside", gap=0.5,
                              size=SIZE)
        assert max(p.length for p in ink(run)) < 12.0 - 0.5 + 1e-6, angle


def test_text_on_arc_reads_the_right_way_up_all_the_way_round():
    """A cluster is upside-down exactly when its tangent points leftward --
    the local up-vector `(0, -1)` lands on `(tangent.y, -tangent.x)`, so the
    test is `tangent.x >= 0`, which is the transform's `d`.

    Asked of the middle cluster of each label, because the ends of a run
    centred on due east or due west genuinely do tip past the vertical: a
    tangential label there reads bottom-to-top, and its far letters lean over
    the top. That is the curve, not the placement.
    """
    for angle in range(-180, 180, 15):
        run = inklet.text_on_arc("270", 12.0, float(angle), size=SIZE)
        middle = run.children[len(run.children) // 2]
        assert middle.transform.d > -1e-9, angle


def test_text_on_arc_is_centred_on_its_bearing():
    run = inklet.text_on_arc("270", 12.0, -90.0, size=SIZE)
    xs = [child.transform.e for child in run.children]
    assert sum(xs) / len(xs) == pytest.approx(0.0, abs=1e-6)
    assert all(child.transform.f < 0 for child in run.children)  # due north


def test_text_on_arc_rejects_a_circle_it_cannot_set_on():
    with pytest.raises(ValueError):
        inklet.text_on_arc("x", 1.0, 0.0, side="inside", gap=2.0, size=SIZE)


# -- composition ------------------------------------------------------------


def test_the_run_carries_the_curves_own_origin():
    """`inklet.drawn([ring, label])` has to put the type back on the ring, and
    that works because the run copies the node's `origin` anchor."""
    ring = inklet.arc(18, -170, -10)
    label = inklet.text_on_path("excitation", ring, lift=0.8, size=SIZE)
    assert ORIGIN_ANCHOR in label.anchors
    assert op._ORIGIN_ANCHOR == ORIGIN_ANCHOR
    together = inklet.drawn([ring, label])
    assert together.bbox.height > ring.bbox.height     # the type sits outside


def test_a_curved_label_does_not_report_against_itself():
    """Rotating a glyph inflates its axis-aligned box; the letters of one word
    are not a collision. See `diagnostics.rules._one_block`."""
    fig = inklet.figure(width="120mm")
    ring = inklet.arc(20, -180, 179.999, stroke="#999", stroke_width=0.2)
    fig.add(inklet.drawn([ring, inklet.text_on_arc("orientation / deg", 22, -90,
                                             size=3.0)]))
    assert fig.lint() == []


# -- the two output contracts -----------------------------------------------


def test_the_same_figure_twice_is_the_same_bytes(tmp_path):
    fig = inklet.figure(width="90mm")
    fig.add(inklet.drawn([inklet.arc(18, -170, -10),
                       inklet.text_on_arc(WORD, 19.5, -90, gap=0.5, size=SIZE)]))
    first, second = tmp_path / "a.svg", tmp_path / "b.svg"
    fig.save(first)
    fig.save(second)
    assert first.read_bytes() == second.read_bytes()


def test_two_builds_put_every_cluster_in_the_same_place():
    """Bytes twice out of one figure would not catch a station that depended
    on iteration order, because the run is placed once. So the stations are
    compared across two independent constructions, exactly."""
    def stations():
        run = inklet.text_on_arc(WORD, 19.5, -90, gap=0.5, size=SIZE)
        return [(c.transform.a, c.transform.b, c.transform.c,
                 c.transform.d, c.transform.e, c.transform.f)
                for c in run.children]

    assert stations() == stations()


def test_embedded_text_is_still_text():
    """The searchable-text contract: one live `<text>` per cluster, in reading
    order, so a reader copying the label out gets the label."""
    run = inklet.text_on_arc("waffle iron", 20.0, -90.0, size=3.0)
    root = ET.fromstring(inklet.to_svg(run, text="embed"))
    words = [element.text for element in root.findall(f".//{SVG}text")]
    assert "".join(words) == "waffle iron"


def test_the_whole_string_is_written_on_the_group():
    """No single node spells the label, so a diagnostic reads it from here."""
    from inklet.typeset.outline import TEXT_NOTE
    run = inklet.text_on_arc("waffle iron", 20.0, -90.0, size=3.0)
    assert run.notes[TEXT_NOTE] == "waffle iron"


# -- item 4: the face a document embeds is the face it uses ------------------


def test_an_italic_run_embeds_the_italic_face():
    """`fontembed` was declaring `font-style:normal` for every face, including
    the ones cut from an italic file. A conforming reader is entitled to slant
    an already-slanted face on the strength of that."""
    pytest.importorskip("fontTools", reason="embedding needs fontTools.subset")
    block = inklet.text("roman //italic//", size=6.0)
    document = inklet.to_svg(block, text="embed")
    slants = re.findall(r"@font-face\{font-family:([\w-]+);font-style:(\w+)",
                        document)
    assert len(slants) == 2, "one subset per face file"
    assert sorted(style for _, style in slants) == ["italic", "normal"]


def test_the_italic_subset_is_the_italic_design():
    """Not the roman sheared: the file carries the italic's own outlines, and
    says so in the one bit a renderer reads to decide whether to synthesise."""
    fonttools = pytest.importorskip("fontTools", reason="needs fontTools")
    from io import BytesIO
    import base64
    from fontTools.ttLib import TTFont

    block = inklet.text("roman //italic//", size=6.0)
    document = inklet.to_svg(block, text="embed")
    faces = re.findall(
        r"font-family:(inklet[\w-]+);font-style:(\w+);[^;]*;"
        r"src:url\(data:font/\w+;base64,([A-Za-z0-9+/=]+)\)", document)
    assert len(faces) == 2
    for _, declared, payload in faces:
        font = TTFont(BytesIO(base64.b64decode(payload)), lazy=True)
        sloped = bool(font["head"].macStyle & 0b10)
        assert sloped == (declared == "italic")


def test_a_roman_only_document_declares_nothing_slanted():
    pytest.importorskip("fontTools", reason="embedding needs fontTools.subset")
    document = inklet.to_svg(inklet.text("roman only", size=6.0), text="embed")
    assert "font-style:italic" not in document
    assert "font-style:normal" in document


# -- what it refuses --------------------------------------------------------


def test_a_two_line_block_is_refused_rather_than_truncated():
    """A curve has one baseline. Setting `lines[0]` and dropping the rest is
    the failure that looks like a success."""
    with pytest.raises(ValueError, match="one baseline"):
        inklet.text_on_path(inklet.text("two\nlines", size=SIZE),
                         op.baseline_arc(20, -140, -40))


def test_a_shape_is_not_a_string():
    with pytest.raises(TypeError, match="shaped text block"):
        inklet.text_on_path(inklet.circle(width=4, height=4),
                         op.baseline_arc(20, -140, -40))
