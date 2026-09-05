"""What `inklet.typeset` promises the rest of the library: numbers that are right.

Every box in a figure is sized from these advances, so the assertions here are
about measured millimetres, not about how the module is put together.
"""

from __future__ import annotations

import pytest

from inklet.core.geom import Rect
from inklet.core.prims import TextPrim
from inklet.core.units import pt
from inklet.typeset import (
    FontFace,
    FontNotFoundError,
    find_font,
    load_face,
    measure,
    shape,
    text_to_paths,
)
from inklet.typeset.fonts import _scan_match
from inklet.typeset.fonts import find_font
from inklet.typeset.shaping import _advance_units

SAMPLE = "Encoder (ViT-B/16)"

# Latin pairs the major text faces kern, and pairs with straight sides that
# essentially never do.
KERN_PAIRS = ("AV", "AW", "To", "Ta", "Yo", "VA", "AT", "LT", "P.", "F,")
FLAT_PAIRS = ("nn", "HH", "im")

# Advances are integer font units scaled by one float; a micron is generous.
MICRON = 1e-3


def isolated_sum(pair: str, **options) -> float:
    """What a naive per-character width table would have said."""
    return sum(shape(char, **options).width for char in pair)


# --- font resolution ------------------------------------------------------


def test_generic_families_resolve_to_real_files():
    for family in ("sans", "serif", "mono"):
        face = find_font(family)
        assert isinstance(face, FontFace)
        assert face.path.lower().endswith((".ttf", ".otf", ".ttc", ".otc"))
        assert face.units_per_em > 0
        assert face.ascent > 0 and face.descent > 0


def test_bold_resolves_to_a_heavier_face_than_regular():
    regular, bold = find_font("sans"), find_font("sans", "bold")
    assert bold.weight >= regular.weight
    # Either a different file, or a machine with only one weight installed.
    assert bold.path != regular.path or bold.weight == regular.weight


def test_unknown_weight_names_are_rejected():
    with pytest.raises(ValueError, match="unknown font weight"):
        find_font("sans", "chunky")


def test_fallback_scan_distinguishes_weight_and_slant():
    """fontconfig hides this path on a normal machine, so exercise it directly:
    it is what a minimal container falls back to."""
    plain = _scan_match("sans", 400, italic=False)
    bold = _scan_match("sans", 700, italic=False)
    slanted = _scan_match("sans", 400, italic=True)
    if plain is None:
        pytest.skip("no scannable fonts in the conventional directories")

    faces = {style: load_face(found[0]) for style, found in
             (("plain", plain), ("bold", bold), ("slanted", slanted)) if found}
    assert faces["bold"].weight > faces["plain"].weight
    assert faces["slanted"].italic and not faces["plain"].italic


def test_a_family_nothing_can_satisfy_raises_something_actionable(monkeypatch):
    monkeypatch.setattr("inklet.typeset.fonts._fc_match", lambda *args: None)
    find_font.cache_clear()
    try:
        with pytest.raises(FontNotFoundError) as raised:
            find_font("Definitely Not An Installed Family")
        message = str(raised.value)
        assert "Definitely Not An Installed Family" in message
        assert "fc-match" in message and "find_font" in message
    finally:
        find_font.cache_clear()


def test_face_scales_metrics_to_the_type_size():
    face = find_font("sans")
    ascent, descent, _ = face.metrics(pt(7))
    assert ascent == pytest.approx(face.ascent * pt(7) / face.units_per_em)
    assert 0 < ascent < pt(7) * 2
    assert 0 < descent < pt(7)


# --- advances -------------------------------------------------------------


def test_advance_grows_with_string_length():
    widths = [shape("m" * n).width for n in range(1, 12)]
    assert widths == sorted(widths)
    assert all(b > a for a, b in zip(widths, widths[1:]))


def test_advance_grows_with_font_size():
    widths = [shape(SAMPLE, size=pt(size)).width for size in (5, 7, 9, 12)]
    assert all(b > a for a, b in zip(widths, widths[1:]))


def test_advance_is_linear_in_size():
    single = shape(SAMPLE, size=pt(7)).width
    assert shape(SAMPLE, size=pt(14)).width == pytest.approx(2 * single, rel=1e-12)
    assert shape(SAMPLE, size=pt(3.5)).width == pytest.approx(single / 2, rel=1e-12)


def test_sizes_may_be_given_as_strings():
    assert shape(SAMPLE, size="7pt").width == shape(SAMPLE, size=pt(7)).width
    assert shape(SAMPLE, size="2.469444444444444mm").width == pytest.approx(
        shape(SAMPLE, size=pt(7)).width, rel=1e-9
    )


def test_sample_label_lands_at_a_plausible_physical_width():
    """A 7pt, 18-character label is a couple of centimetres wide. This is the
    unit-conversion tripwire: mm/pt confusion shows up as 3mm or 200mm."""
    assert 15.0 < shape(SAMPLE, size=pt(7)).width < 22.0


def test_non_positive_sizes_and_widths_are_rejected():
    with pytest.raises(ValueError, match="size must be positive"):
        shape(SAMPLE, size=0)
    with pytest.raises(ValueError, match="width must be positive"):
        shape(SAMPLE, width=-1)


# --- kerning --------------------------------------------------------------


def test_kerning_is_applied_not_summed_per_character():
    kerned = {pair: shape(pair).width - isolated_sum(pair) for pair in KERN_PAIRS}
    moved = {pair: delta for pair, delta in kerned.items() if abs(delta) > MICRON}
    if not moved:
        face = find_font("sans")
        pytest.skip(f"{face.family} ({face.path}) has no kern data for {KERN_PAIRS}")

    # Flat-sided pairs must be untouched, so the difference above is kerning
    # rather than some artefact of measuring one character at a time.
    for pair in FLAT_PAIRS:
        assert shape(pair).width == pytest.approx(isolated_sum(pair), abs=MICRON)

    # And turning the feature off recovers exactly the naive sum.
    for pair in moved:
        assert shape(pair, features={"kern": False}).width == pytest.approx(
            isolated_sum(pair), abs=MICRON
        )


def test_disabling_a_feature_changes_the_measurement():
    pair = next((p for p in KERN_PAIRS
                 if abs(shape(p).width - shape(p, features={"kern": False}).width) > MICRON), None)
    if pair is None:
        pytest.skip(f"{find_font('sans').family} has no kern data")
    assert shape(pair, features={"kern": True}).width == shape(pair).width


# --- line breaking --------------------------------------------------------


def test_explicit_newlines_make_lines_with_stacked_baselines():
    size, line_height = pt(7), 1.25
    prim = shape("a\nbb\nccc", size=size, line_height=line_height)
    step = line_height * size

    assert [line.text for line in prim.lines] == ["a", "bb", "ccc"]
    assert [line.baseline for line in prim.lines] == pytest.approx([0.0, step, 2 * step])
    advances = [line.advance for line in prim.lines]
    assert all(b > a for a, b in zip(advances, advances[1:]))
    assert prim.height == pytest.approx(prim.ascent + 2 * step + prim.descent)


def test_ascent_and_descent_come_from_the_font_not_the_line_height():
    tight = shape("Hg", line_height=1.0)
    loose = shape("Hg", line_height=3.0)
    assert tight.ascent == loose.ascent
    assert tight.descent == loose.descent
    # One line, so line_height cannot reach the block height either.
    assert tight.height == pytest.approx(loose.height)


def test_a_blank_line_still_occupies_a_line():
    prim = shape("top\n\nbottom", size=pt(7))
    assert [line.text for line in prim.lines] == ["top", "", "bottom"]
    assert prim.lines[1].advance == 0.0


def test_empty_text_measures_to_one_empty_line():
    prim = shape("")
    assert [line.text for line in prim.lines] == [""]
    assert prim.width == 0.0
    assert prim.height == pytest.approx(prim.ascent + prim.descent)


# --- word wrap ------------------------------------------------------------

PARAGRAPH = "the quick brown fox jumps over the lazy dog"


def test_wrapped_lines_fit_the_width():
    limit = 20.0
    prim = shape(PARAGRAPH, size=pt(7), width=limit)
    assert len(prim.lines) > 1
    for line in prim.lines:
        assert line.advance <= limit + MICRON, f"{line.text!r} overflows"
    assert prim.width <= limit + MICRON


def test_wrap_is_greedy_so_no_line_could_hold_the_next_word():
    limit = 20.0
    prim = shape(PARAGRAPH, size=pt(7), width=limit)
    for line, following in zip(prim.lines, prim.lines[1:]):
        next_word = following.text.split()[0]
        overfull = shape(f"{line.text} {next_word}", size=pt(7))
        assert overfull.width > limit


def test_wrap_preserves_every_word():
    prim = shape(PARAGRAPH, size=pt(7), width=15.0)
    assert " ".join(line.text for line in prim.lines) == PARAGRAPH


def test_wrap_respects_explicit_newlines_too():
    prim = shape(f"{PARAGRAPH}\nshort tail", size=pt(7), width=20.0)
    assert prim.lines[-1].text == "short tail"


def test_an_unbreakable_word_overflows_rather_than_crashing():
    long_word = "supercalifragilisticexpialidocious"
    prim = shape(f"tiny {long_word} end", size=pt(7), width=5.0)
    assert [line.text for line in prim.lines] == ["tiny", long_word, "end"]
    assert prim.width > 5.0  # the linter's job to complain, not the shaper's


# --- the prim's geometry --------------------------------------------------


def test_width_is_the_widest_line_and_the_bbox_agrees():
    prim = shape("a\nbb\nccc\nd", size=pt(7))
    assert prim.width == max(line.advance for line in prim.lines)

    box = prim.envelope().bbox()
    assert box.width == pytest.approx(prim.width)
    assert box.height == pytest.approx(prim.height)
    assert box.center.x == pytest.approx(0.0)
    assert box.center.y == pytest.approx(0.0)


def test_measure_returns_the_same_box_as_shaping():
    box = measure(SAMPLE, size=pt(7))
    prim = shape(SAMPLE, size=pt(7))
    assert isinstance(box, Rect)
    assert box == prim.envelope().bbox()


def test_alignment_is_normalised_and_validated():
    assert shape("x", align="left").align == "start"
    assert shape("x", align="right").align == "end"
    assert shape("x", align="centre").align == "center"
    assert shape("x", align="justified", width=20.0).align == "justify"
    with pytest.raises(ValueError, match="unknown alignment"):
        shape("x", align="ragged")


# -- justification --------------------------------------------------------

PARAGRAPH = ("Orientation selectivity across the mouse visual hierarchy. "
             "Two-photon calcium imaging of layer 2/3 pyramidal cells in "
             "twelve cortical areas, imaged through a cranial window.")


def test_justify_needs_a_width():
    with pytest.raises(ValueError, match="needs a width"):
        shape(PARAGRAPH, align="justify")


def test_justified_lines_fill_the_column_exactly():
    prim = shape(PARAGRAPH, size=pt(7), width=52.0, align="justify")

    assert len(prim.lines) > 1
    for line in prim.lines[:-1]:
        assert line.advance == pytest.approx(52.0)
        assert line.word_spacing > 0.0
    assert prim.width == pytest.approx(52.0)


def test_the_last_line_of_a_paragraph_is_not_stretched():
    prim = shape(PARAGRAPH, size=pt(7), width=52.0, align="justify")
    last = prim.lines[-1]
    assert last.word_spacing == 0.0
    assert last.advance < 52.0


def test_every_paragraph_keeps_its_own_short_last_line():
    prim = shape(f"{PARAGRAPH}\n{PARAGRAPH}", size=pt(7), width=52.0,
                 align="justify")
    loose = [i for i, line in enumerate(prim.lines) if line.word_spacing == 0.0]
    # One per paragraph, and each is the line before the next starts.
    assert len(loose) == 2
    assert loose[1] == len(prim.lines) - 1


def test_a_word_wider_than_the_column_is_not_squeezed():
    prim = shape("supercalifragilisticexpialidocious and more", size=pt(7),
                 width=12.0, align="justify")
    assert prim.lines[0].word_spacing == 0.0
    assert prim.lines[0].advance > 12.0


def test_justified_text_is_never_taller_than_ragged_text():
    """Relaxing the spaces must not cost a line: a caption that grows to look
    better has traded away the thing the layout was holding."""
    for width in (34.0, 41.0, 52.0, 63.0, 78.0):
        ragged = shape(PARAGRAPH, size=pt(7), width=width, align="start")
        even = shape(PARAGRAPH, size=pt(7), width=width, align="justify")
        assert len(even.lines) == len(ragged.lines), width


def test_justified_offsets_start_at_the_column_edge():
    prim = shape(PARAGRAPH, size=pt(7), width=52.0, align="justify")
    assert all(prim.line_offset(line) == 0.0 for line in prim.lines)


def test_line_offsets_follow_the_alignment():
    prim = shape("a\nlonger", align="start")
    short = prim.lines[0]
    assert prim.line_offset(short) == 0.0
    assert shape("a\nlonger", align="end").line_offset(short) == pytest.approx(
        prim.width - short.advance
    )


def test_prim_carries_the_font_it_was_measured_with():
    prim = shape(SAMPLE, size=pt(7))
    face = find_font("sans")
    assert isinstance(prim, TextPrim)
    assert prim.font_path == face.path
    assert prim.font_family == face.family
    assert prim.font_size == pt(7)


# --- determinism ----------------------------------------------------------


def test_shaping_twice_gives_identical_floats():
    first = shape(f"{SAMPLE}\nsecond line", size=pt(7), width=15.0)
    second = shape(f"{SAMPLE}\nsecond line", size=pt(7), width=15.0)
    assert first == second
    assert [line.advance.hex() for line in first.lines] == [
        line.advance.hex() for line in second.lines
    ]


def test_results_survive_a_cold_cache():
    """The caches must be an optimisation, not the source of the agreement."""
    warm = shape(SAMPLE, size=pt(7))
    _advance_units.cache_clear()
    find_font.cache_clear()
    cold = shape(SAMPLE, size=pt(7))
    assert cold == warm


def test_feature_dict_order_does_not_change_the_result():
    a = shape(SAMPLE, features={"kern": True, "liga": False})
    b = shape(SAMPLE, features={"liga": False, "kern": True})
    assert a == b


# --- outlining ------------------------------------------------------------


def sole_outline(prim, **options):
    """The one path a block with no colour markup outlines to."""
    entries = text_to_paths(prim, **options)
    assert len(entries) == 1, f"expected one fill group, got {len(entries)}"
    path, fill = entries[0]
    assert fill is None
    return path


def test_outlines_land_inside_the_measured_block():
    prim = shape("Hxg", size=pt(7))
    paths = sole_outline(prim)
    assert paths.filled
    assert len(paths.subpaths) >= 3  # at least one contour per glyph

    glyphs = paths.envelope().bbox()
    block = prim.envelope().bbox()
    assert block.x0 - MICRON <= glyphs.x0 and glyphs.x1 <= block.x1 + MICRON
    assert block.y0 - MICRON <= glyphs.y0 and glyphs.y1 <= block.y1 + MICRON

    # The cap of an "H" sits at cap height above the baseline, which is most of
    # the ascent but never all of it.
    cap = prim.first_baseline - glyphs.y0
    assert 0.5 * prim.ascent < cap < prim.ascent


def test_outlining_whitespace_draws_nothing():
    assert text_to_paths(shape("   ")) == []
    assert text_to_paths(shape("")) == []


#: A face whose proportional and tabular digits are different widths. Not every
#: family has both -- Noto Sans, the default here, is tabular already -- so the
#: drift this guards can only be shown in one that does.
_TNUM_FAMILY = "Cantarell"

needs_tnum_family = pytest.mark.skipif(
    find_font(_TNUM_FAMILY).family != _TNUM_FAMILY,
    reason=f"{_TNUM_FAMILY} is not installed on this machine",
)


@needs_tnum_family
def test_a_block_outlines_under_the_features_it_was_measured_with():
    """The mismatch `TextPrim.features` exists to make impossible: outlining
    re-runs the shaper, and asking it a different question moves the glyphs
    inside a box that was sized by the first answer. Ten digits drift 2.8mm."""
    prim = shape("0123456789", font=_TNUM_FAMILY, size=10, features={"tnum": True})
    assert prim.features == (("tnum", True),)
    assert prim.width == pytest.approx(58.0, abs=0.01)

    ink = sole_outline(prim).envelope().bbox()
    assert ink.width == pytest.approx(57.03, abs=0.01)

    # What the same call outlined to before the prim carried its features: the
    # proportional digits, 2.79mm narrower than the block they were stacked in.
    loose = sole_outline(shape("0123456789", font=_TNUM_FAMILY, size=10))
    assert loose.envelope().bbox().width == pytest.approx(54.24, abs=0.01)


@needs_tnum_family
def test_the_features_a_text_node_asked_for_reach_its_outlines():
    """End to end, through the public spelling and the tree transform, with no
    parameter passed anywhere."""
    import inklet

    node = inklet.text("0123456789", font=_TNUM_FAMILY, size=10,
                    features={"tnum": True})
    ink = inklet.outline_text(node).prim.envelope().bbox()
    assert ink.width == pytest.approx(57.03, abs=0.01)
    assert node.prim.width == pytest.approx(58.0, abs=0.01)


def test_features_are_recorded_in_the_canonical_order():
    """Two callers asking for the same features in the other order build equal
    prims, which is what lets a cache key be the prim."""
    a = shape(SAMPLE, features={"liga": True, "kern": False})
    b = shape(SAMPLE, features={"kern": False, "liga": True})
    assert a.features == b.features == (("kern", False), ("liga", True))
    assert a == b
    assert shape(SAMPLE).features == ()


def test_outlining_needs_a_font_path():
    naked = TextPrim(lines=shape("x").lines, font_family="sans", font_size=pt(7),
                     ascent=1.0, descent=0.3)
    with pytest.raises(ValueError, match="font_path"):
        text_to_paths(naked)


# --- fonts a face cannot draw -------------------------------------------
#
# The whole class of bug these cover: a missing glyph is not an error. It is a
# `.notdef` box with a width, so the wrong measurement propagates silently into
# the envelope, the wrap and the page fit.

JAPANESE = "視覚野の方位選択性は刺激コントラストに依存する。図1cは面積ごとの選択性指数を示す。"
ARABIC = "وانتقائية الاتجاه (V1) القشرة البصرية للفأر"
DEVANAGARI = "दृश्य प्रांतस्था में अभिविन्यास चयनात्मकता का मापन"


def _covered(text: str, prim: TextPrim) -> bool:
    """Whether every character of `text` found a font in this prim."""
    return prim.missing == ""


@pytest.mark.parametrize("sample", [JAPANESE, ARABIC, DEVANAGARI])
def test_text_a_latin_font_cannot_draw_borrows_one_that_can(sample):
    prim = shape(sample, font="Helvetica Neue", size=pt(7))
    if not _covered(sample, prim):
        pytest.skip("this machine has no font covering the sample")
    runs = [run for line in prim.lines for run in line.runs]
    assert runs, "a Latin face cannot draw this, so the line must be run-split"
    assert all(run.font_family != prim.font_family for run in runs)


def test_borrowed_advance_is_the_borrowed_font_s_advance():
    """The measurement is the point: `.notdef` boxes measure to a plausible
    number, and a figure built on that number is wrong everywhere."""
    face = find_font("Helvetica Neue")
    if _advance_units(JAPANESE, face, ()) == 0:
        pytest.skip("no shaping available")
    prim = shape(JAPANESE, font="Helvetica Neue", size=pt(7))
    if not _covered(JAPANESE, prim):
        pytest.skip("this machine has no font covering the sample")
    notdef_width = _advance_units(JAPANESE, face, ()) * face.scale(pt(7))
    assert prim.width > notdef_width * 1.3
    assert prim.width == pytest.approx(
        sum(run.advance for run in prim.lines[0].runs), abs=1e-9)


def test_a_line_the_font_covers_carries_no_runs():
    """The ordinary case stays exactly as it was: one family, no run table."""
    prim = shape(SAMPLE, font="Helvetica Neue", size=pt(7))
    assert all(line.runs == () for line in prim.lines)
    assert prim.missing == ""


def test_latin_inside_another_script_keeps_the_asked_for_font():
    """A borrowed face is borrowed only for what the original cannot draw --
    otherwise a Latin word in a Japanese sentence changes typeface midway."""
    prim = shape("hiero " + chr(0x13000) + " sign", font="Helvetica Neue", size=pt(7))
    runs = [run for line in prim.lines for run in line.runs]
    if len(runs) < 2:
        pytest.skip("this machine resolves the whole line to one face")
    assert runs[0].font_family == prim.font_family
    assert runs[0].text.strip() == "hiero"


def test_undrawable_characters_are_recorded_not_hidden():
    from inklet.typeset.shaping import _uncovered
    face = find_font("Helvetica Neue")
    assert _uncovered("Encoder", face) == ""
    absent = _uncovered("視覚野", face)
    if absent == "":
        pytest.skip("this Latin face covers CJK")
    assert absent == "視覚野"
    # Distinct, and in the order they appear.
    assert _uncovered("視視覚", face) == "視覚"


def test_block_height_covers_every_face_that_draws_it():
    """A borrowed face with a taller ascent must not be cropped by the metrics
    of the face that could not draw it."""
    from inklet.typeset.fonts import load_face
    prim = shape(JAPANESE, font="Helvetica Neue", size=pt(7))
    for run in prim.lines[0].runs:
        face = load_face(run.font_path, run.font_index)
        ascent, descent, _ = face.metrics(pt(7))
        assert prim.ascent >= ascent - MICRON
        assert prim.descent >= descent - MICRON


# --- breaking a script that writes no spaces ----------------------------


def test_japanese_wraps_between_characters():
    """`str.split()` sees one word, so without character breaks the sentence
    cannot wrap at all and overflows its column entire."""
    prim = shape(JAPANESE, font="Helvetica Neue", size=pt(7), width=25.0,
                 align="start")
    assert len(prim.lines) > 1
    assert prim.width <= 25.0 + MICRON
    assert "".join(line.text for line in prim.lines) == JAPANESE


def test_japanese_wrapping_keeps_punctuation_off_the_line_head():
    from inklet.typeset.shaping import _breakable
    assert _breakable("る", "。") is False      # kinsoku: never start with 。
    assert _breakable("（", "図") is False      # nor end with an opening bracket
    assert _breakable("視", "覚") is True
    assert _breakable("t", "h") is False        # Latin still breaks at spaces only


def test_latin_line_breaks_are_untouched_by_character_breaking():
    """The break-opportunity list must reduce to `str.split()` for text with no
    ideographs, or every figure already written re-wraps."""
    from inklet.typeset.markup import parse
    from inklet.typeset.shaping import _join, _pieces
    paragraph = "Responses are reported as the normalised fluorescence change"
    pieces = _pieces(parse(paragraph))
    assert _join(pieces, 0, len(pieces)).text == paragraph
    assert len(pieces) == len(paragraph.split())
    assert _join(pieces, 2, 5).text == "reported as the"


def test_outlining_borrows_the_same_faces_the_shaping_did():
    """Both backends must draw the same figure. Outlining the whole block in
    the named font would put `.notdef` boxes exactly where the SVG backend puts
    readable glyphs."""
    prim = shape(JAPANESE, font="Helvetica Neue", size=pt(7))
    if prim.missing:
        pytest.skip("this machine has no font covering the sample")
    outline = sole_outline(prim)
    xs = [point.x for sub in outline.subpaths for point in sub.points]
    block = prim.envelope().bbox()
    assert block.x0 - MICRON <= min(xs) and max(xs) <= block.x1 + MICRON
    # Real glyphs, not a row of identical rectangles: a `.notdef` box is four
    # points, so 42 characters of boxes could not reach this many subpaths.
    assert len(outline.subpaths) > len(JAPANESE)


# -- sub- and superscripts -------------------------------------------------
#
# `H_{2}O` and `x^{2}`: the braces are the markup, so an underscore or caret
# in a file name or a unit is never touched.


def test_script_markup_becomes_small_shifted_runs():
    prim = shape("H_{2}O", size=pt(8))
    (line,) = prim.lines
    assert [run.text for run in line.runs] == ["H", "2", "O"]
    h, two, o = line.runs
    assert h.size is None and h.shift == 0.0
    assert two.size is not None and two.size < prim.font_size
    assert two.shift > 0.0                          # a subscript drops
    assert o.size is None
    assert shape("x^{2}", size=pt(8)).lines[0].runs[1].shift < 0.0


def test_scripts_measure_narrower_than_full_size_text():
    plain = shape("H2O", size=pt(8)).width
    marked = shape("H_{2}O", size=pt(8)).width
    assert shape("HO", size=pt(8)).width < marked < plain


def test_braceless_underscores_and_carets_are_ordinary_text():
    for text in ("file_name", "m^-1", "a_{", "b}_c", "x^{}"):
        prim = shape(text, size=pt(8))
        assert prim.lines[0].runs == (), text
    # An empty script is markup all the same, and markup does not survive
    # into the line: `TextLine.text` is what the reader sees, not what was typed.
    assert shape("x^{}", size=pt(8)).lines[0].text == "x"


def test_scripts_stay_inside_the_block_and_outline_the_same():
    prim = shape("Ca^{2+} and F_{0}", size=pt(8))
    glyphs = sole_outline(prim).envelope().bbox()
    block = prim.envelope().bbox()
    assert block.x0 - MICRON <= glyphs.x0 and glyphs.x1 <= block.x1 + MICRON
    assert block.y0 - MICRON <= glyphs.y0 and glyphs.y1 <= block.y1 + MICRON
    # The superscript does reach higher than the capital it follows.
    plain = sole_outline(shape("Ca and F", size=pt(8))).envelope().bbox()
    assert glyphs.y0 < plain.y0


def test_scripts_survive_wrapping_and_reach_the_svg():
    import inklet
    node = inklet.text("C_{15}H_{15}ClN_{4}O_{2} is the formula", width=18)
    svg = inklet.to_svg(node)
    assert "_{" not in svg
    assert svg.count("<tspan") >= 8
    assert 'font-size=' in svg
    assert len(node.prim.lines) >= 2


def test_the_glyph_contour_cache_is_public_and_shared():
    """`render.glyphs` places glyphs one at a time so it can keep a fill per
    glyph, while `text_to_paths` builds one path per block. They must walk the
    same pen once, not twice, so the cache they share is public."""
    from inklet.core.geom import Vec2
    from inklet.typeset.outline import glyph_contours, placed_contours
    from inklet.typeset.shaping import shape_buffer

    face = find_font("sans")
    buffer = shape_buffer("A", face, ())
    gid = buffer.glyph_infos[0].codepoint

    glyph_contours.cache_clear()
    contours = glyph_contours(face.path, face.index, gid)
    assert contours and glyph_contours.cache_info().misses == 1

    scale = face.scale(10.0)
    placed = placed_contours(face.path, face.index, gid, Vec2(3.0, 4.0), scale)
    assert glyph_contours.cache_info().misses == 1      # came out of the cache
    assert len(placed) == len(contours)

    # Font space has y up and inklet has y down, and that flip happens here only.
    x, y = contours[0].points[0]
    assert placed[0].points[0].x == pytest.approx(3.0 + x * scale)
    assert placed[0].points[0].y == pytest.approx(4.0 - y * scale)


# --- what `inklet.text` does with the style it is handed ----------------------


def test_a_non_string_is_refused_by_name():
    """`inklet.text(16)` raised `argument of type 'int' is not iterable` from
    three frames inside the markup scanner. An agent reading that cannot tell
    which call it came from, let alone what was wrong with it."""
    import inklet

    for call, what in ((inklet.text, "text"), (inklet.label, "label"),
                       (inklet.title, "title")):
        with pytest.raises(TypeError, match=rf"{what}\(\) takes the words"):
            call(16)
        with pytest.raises(TypeError, match=rf"{what}\(\) takes a string, not list"):
            call(["a"])
    with pytest.raises(TypeError, match="size=1.5"):
        inklet.text(1.5)


def test_a_slanted_weight_is_measured_and_declared():
    """The block is set in the bold italic; the live `<text>` has to ask for
    the same face or a viewer re-shapes it inside a box built for another.
    Weight and slant are separate fields, so both have to be said."""
    import inklet

    node = inklet.text("Nature", weight="bold italic")
    assert node.style.font_weight == "bold"
    assert node.style.font_style == "italic"
    assert load_face(node.prim.font_path).italic
    assert load_face(node.prim.font_path).weight >= 700

    upright = inklet.text("Nature", weight="bold")
    assert upright.style.font_style is None
    assert not load_face(upright.prim.font_path).italic


def test_a_slant_asked_for_as_a_style_field_is_measured_too():
    """`font_style="italic"` and `weight="italic"` are the same request. The
    italic is a different design, not the upright leaned over, so a block
    measured in the upright and painted in the italic is the wrong width."""
    import inklet

    styled = inklet.text("Nature", font_style="italic")
    assert load_face(styled.prim.font_path).italic
    assert styled.prim.width == pytest.approx(
        inklet.text("Nature", weight="italic").prim.width, abs=MICRON)
    if find_font("sans", "regular", True).path != find_font("sans").path:
        assert styled.prim.width != pytest.approx(
            inklet.text("Nature").prim.width, abs=MICRON)


def test_a_halo_claims_the_space_its_ink_takes():
    """A halo is a stroke painted under the glyphs, half of it covered by the
    glyph itself. Layout spaces by the envelope and `inklet.lint` measures gaps
    with it, so a haloed label with no room for its halo is packed touching
    its neighbour and the halo eats into it."""
    import inklet

    plain = inklet.text("over a micrograph")
    haloed = inklet.text("over a micrograph", halo=0.4)
    assert haloed.width == pytest.approx(plain.width + 0.4, abs=MICRON)
    assert haloed.height == pytest.approx(plain.height + 0.4, abs=MICRON)
    assert haloed.style.halo == 0.4
    # Nothing was shaped differently: a halo has no advance.
    assert haloed.prim == plain.prim
    # A unit string is read like every other length.
    assert inklet.label("x", halo="0.6mm").bbox.width == pytest.approx(
        inklet.label("x").bbox.width + 0.6, abs=MICRON)


def test_a_haloed_label_is_spaced_for_its_halo():
    import inklet

    stacked = inklet.vstack([inklet.text("one", halo=0.5), inklet.text("two", halo=0.5)],
                         gap=1.0)
    bare = inklet.vstack([inklet.text("one"), inklet.text("two")], gap=1.0)
    assert stacked.height == pytest.approx(bare.height + 1.0, abs=MICRON)
