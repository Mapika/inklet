"""Inline bold, italic and colour, and the fallback that catches the rest.

Two things are being asserted here, and they are not the same thing. One is
that the grammar reads the way it is documented -- what is markup, what is
literal, and what happens to half-typed markup. The other is that the
*measurement* is honest: a bold phrase is measured in the bold face, so a
column wrapped around it fits the type that will actually be drawn.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core.prims import PathPrim
from inklet.core.units import pt
from inklet.typeset import escape_markup, shape, text_to_paths
from inklet.typeset.fonts import find_fallback, find_font, load_face
from inklet.typeset.markup import ESCAPABLE, parse, strip_markup
from inklet.typeset.shaping import _advance_units, feature_key

SIZE = pt(7)

# Advances are integer font units scaled by one float; a micron is generous.
MICRON = 1e-3

#: A literal to test `{token|...}` against, so the assertions do not move when
#: a theme's accent does.
ACCENT = "#0072b2"


def faces_of(prim) -> list[tuple[str, int, bool]]:
    """(text, weight, italic) per run of a single-line block."""
    (line,) = prim.lines
    out = []
    for run in line.runs:
        face = load_face(run.font_path, run.font_index)
        out.append((run.text, face.weight, face.italic))
    return out


def plain_text(prim) -> str:
    return "\n".join(line.text for line in prim.lines)


def has_real_bold() -> bool:
    """Whether this machine has a bold of the default family to set."""
    family = inklet.current_theme().font_family
    return find_font(family, "bold").path != find_font(family).path


needs_bold = pytest.mark.skipif(not has_real_bold(),
                                reason="only one weight of the theme family is installed")
needs_italic = pytest.mark.skipif(
    find_font(inklet.current_theme().font_family, "regular", True).path
    == find_font(inklet.current_theme().font_family).path,
    reason="no italic of the theme family is installed")


# --- the grammar ----------------------------------------------------------


def test_markup_never_reaches_the_page():
    """`TextLine.text` is what the reader sees. Anything else and the SVG
    ships the delimiters, or a linter reads a caption that nobody wrote."""
    prim = shape("**(a)** //view// of {accent|the cell}, Ca^{2+}", size=SIZE)
    assert plain_text(prim) == "(a) view of the cell, Ca2+"
    assert "**" not in inklet.to_svg(inklet.text("**(a)** panel"))


@pytest.mark.parametrize("literal", [
    "the *CO band and the *OH band",       # adsorbed species, not italics
    "https://doi.org/10.1/a and https://doi.org/10.1/b",
    "unclosed **bold and //italic",
    "file_name and m^-1 and 50/50",
    "a {brace} with no fill and {|no name|}",
])
def test_text_that_looks_like_markup_but_is_not(literal):
    """The delimiters were chosen so that real captions survive being typed."""
    assert strip_markup(literal) == literal
    assert plain_text(shape(literal, size=SIZE)) == literal


def test_escapes_make_any_delimiter_literal():
    assert strip_markup(r"\*\*not bold\*\*") == "**not bold**"
    assert strip_markup(r"H\_{2}O") == "H_{2}O"
    assert strip_markup(r"a \\ b") == "a \\ b"
    original = "**{weird}** //name// with \\ in it"
    assert strip_markup(escape_markup(original)) == original


@pytest.mark.parametrize("typed,read", [
    (r"\*\*not bold\*\*", "**not bold**"),
    (r"a \/\/b\/\/ c", "a //b// c"),
    (r"\{accent|x}", "{accent|x}"),
    (r"x\^{2} and a\_{1}", "x^{2} and a_{1}"),
    (r"\} and \|", "} and |"),
    (r"\**bold**", "**bold**"),          # the escape kills the whole opener
    (r"**bold\**", "**bold**"),          # and the whole closer
    (r"\\**bold**", "\\bold"),          # an escaped backslash leaves it live
    ("C:\\Users\\new", "C:\\Users\\new"),   # \U and \n are not escapes
])
def test_every_escapable_delimiter_is_made_literal(typed, read):
    """`\\` covers exactly `* / { } | _ ^ \\` and nothing else, so a Windows path
    and a LaTeX-looking string both survive being typed."""
    assert strip_markup(typed) == read
    assert plain_text(shape(typed, size=SIZE)) == read


def test_escaping_and_stripping_are_inverses_on_arbitrary_text():
    """`escape_markup` is what a caller interpolates data through, so it has to
    survive anything -- a sample named `**`, a path, a half-typed brace."""
    import random
    import string

    alphabet = string.printable[:70] + ESCAPABLE
    random.seed(20260823)
    for _ in range(3000):
        raw = "".join(random.choice(alphabet)
                      for _ in range(random.randrange(0, 14)))
        assert strip_markup(escape_markup(raw)) == raw


@pytest.mark.parametrize("typed,marks", [
    ("{accent|**bold**}", [(True, False, ACCENT, 0)]),
    ("**{accent|bold}**", [(True, False, ACCENT, 0)]),
    ("//{accent|slant}//", [(False, True, ACCENT, 0)]),
    ("**//both//**", [(True, True, None, 0)]),
    ("{accent|H_{2}O}", [(False, False, ACCENT, 0), (False, False, ACCENT, 1),
                         (False, False, ACCENT, 0)]),
    ("{accent|{#c1121f|inner}}", [(False, False, "#c1121f", 0)]),
])
def test_marks_nest_and_compose_in_either_order(typed, marks):
    """A nested span modifies the mark it is scanned under rather than
    replacing it, so the inner delimiter never has to restate the outer one."""
    styled = parse(typed, colors={"accent": ACCENT})
    assert [(m.bold, m.italic, m.fill, m.level)
            for _, m in styled.spans()] == marks


def test_an_opener_takes_the_nearest_closer_and_spans_do_not_cross():
    styled = parse("**a //b** c//")
    assert styled.text == "a //b c//"
    assert [(text, mark.bold, mark.italic) for text, mark in styled.spans()] == [
        ("a //b", True, False), (" c//", False, False),
    ]


def test_markup_can_be_turned_off_entirely():
    prim = shape("**(a)** H_{2}O", size=SIZE, markup=False)
    assert plain_text(prim) == "**(a)** H_{2}O"
    assert prim.lines[0].runs == ()


# --- faces ----------------------------------------------------------------


@needs_bold
def test_bold_is_set_in_the_bold_face_not_a_style_attribute():
    prim = shape("plain **heavy** plain", size=SIZE)
    weights = {text: weight for text, weight, _ in faces_of(prim)}
    assert weights["heavy"] >= 700
    assert weights["plain "] < 700


@needs_italic
def test_italic_is_set_in_the_italic_face():
    prim = shape("in //vitro// only", size=SIZE)
    slants = {text: italic for text, _, italic in faces_of(prim)}
    assert slants["vitro"] is True
    assert slants["in "] is False


@needs_bold
@needs_italic
def test_bold_and_italic_compose_into_the_bold_italic_face():
    (_, weight, italic), = [r for r in faces_of(shape("**//x//**", size=SIZE))]
    assert weight >= 700 and italic is True


@needs_bold
def test_a_bold_superscript_is_bold_and_small():
    prim = shape("**Ca^{2+}**", size=SIZE)
    assert all(weight >= 700 for _, weight, _ in faces_of(prim))
    (line,) = prim.lines
    script = next(run for run in line.runs if run.text == "2+")
    assert script.size is not None and script.size < prim.font_size
    assert script.shift < 0.0


@needs_bold
def test_a_run_never_leaves_the_family_it_was_asked_for():
    """A machine with no bold of some family answers with a stranger, and one
    word of a caption in a different typeface reads as a mistake."""
    prim = shape("a **b** c", font="serif", size=SIZE)
    families = {run.font_family for run in prim.lines[0].runs}
    assert families == {prim.font_family}


def test_the_whole_block_can_be_set_bold_and_is_measured_that_way():
    node = inklet.text("Figure 1", weight="bold")
    assert node.prim.font_path == find_font(
        inklet.current_theme().font_family, "bold").path
    # And the live `<text>` asks for the same weight it was measured in.
    assert 'font-weight="bold"' in inklet.to_svg(node)


# --- measurement ----------------------------------------------------------


@needs_bold
def test_a_bold_phrase_measures_as_the_bold_face_measures_it():
    """The point of the exercise: the column is wrapped against the width the
    type will draw at, not against the regular's."""
    marked = shape("**Reversible**", size=SIZE)
    bold = shape("Reversible", size=SIZE, weight="bold")
    assert marked.width == pytest.approx(bold.width, abs=MICRON)
    assert marked.width != pytest.approx(shape("Reversible", size=SIZE).width,
                                         abs=MICRON)


@needs_bold
def test_run_advances_add_up_to_the_line_advance():
    prim = shape("one **two** three //four//", size=SIZE)
    (line,) = prim.lines
    assert sum(run.advance for run in line.runs) == pytest.approx(line.advance,
                                                                  abs=MICRON)


@needs_bold
def test_a_styled_run_may_break_across_a_line():
    """A bold phrase is not an atom: it wraps like any other words, and the
    style survives the break."""
    prim = shape("The **quick brown fox jumps over** the lazy dog",
                 size=SIZE, width=25)
    bold_lines = [index for index, line in enumerate(prim.lines)
                  if any(load_face(run.font_path, run.font_index).weight >= 700
                         for run in line.runs)]
    assert len(prim.lines) >= 3
    assert len(bold_lines) >= 2, "the bold phrase should span a line break"


@needs_bold
def test_justification_still_fills_the_column_exactly_with_runs():
    width = 30.0
    prim = shape("The **quick brown fox** jumps over the very lazy dog and "
                 "then keeps on going for a while",
                 size=SIZE, width=width, align="justify")
    assert len(prim.lines) >= 3
    for line in prim.lines[:-1]:
        assert line.advance == pytest.approx(width, abs=MICRON)
        assert line.word_spacing >= 0.0
    # The renderer advances the pen by run advance plus this line's spacing per
    # space in the run; on a line built of runs that has to land on the column
    # edge too, or the last word of a justified line sits short of it.
    mixed = [line for line in prim.lines[:-1] if line.runs]
    assert mixed, "the bold phrase should put runs on at least one full line"
    for line in mixed:
        pen = sum(run.advance + run.text.count(" ") * line.word_spacing
                  for run in line.runs)
        assert pen == pytest.approx(width, abs=MICRON)


def test_shaping_marked_up_text_twice_gives_identical_floats():
    sample = "**(a)** //Escherichia coli// at {accent|37 °C}, µ = 0.4 h^{-1}"
    first, second = shape(sample, size=SIZE), shape(sample, size=SIZE)
    assert [line.advance for line in first.lines] == [line.advance
                                                      for line in second.lines]
    node = inklet.text(sample)
    assert inklet.to_svg(node) == inklet.to_svg(node)


# --- colour ---------------------------------------------------------------


def test_a_colour_span_carries_its_own_fill():
    prim = shape("plain {#c1121f|red} plain", size=SIZE)
    fills = {run.text: getattr(run, "fill", None) for run in prim.lines[0].runs}
    assert fills["red"] == "#c1121f"
    assert fills["plain "] is None


def test_a_theme_token_resolves_to_the_theme_s_colour():
    theme = inklet.current_theme()
    node = inklet.text("the {accent|accented} word")
    fills = {run.text: getattr(run, "fill", None)
             for run in node.prim.lines[0].runs}
    assert fills["accented"] == theme.accent
    assert inklet.text("{series1|x}").prim.lines[0].runs[0].fill == theme.color(1)


def test_colour_has_no_width():
    """A fill changes no advance, so a coloured caption wraps where the plain
    one did -- worth pinning, because it is the cheap way to be wrong."""
    marked = shape("one {accent|two} three", size=SIZE)
    plain = shape("one two three", size=SIZE)
    assert marked.width == pytest.approx(plain.width, abs=MICRON)


# --- outlining ------------------------------------------------------------


def only_ink(prim):
    """Every glyph of a block, whatever colour it was asked for, in one path.

    Fine for measuring where the ink lands; the colours themselves are what
    `text_to_paths` keeps the groups apart for.
    """
    subpaths = tuple(sub for path, _ in text_to_paths(prim) for sub in path.subpaths)
    return PathPrim(subpaths, filled=True)


@needs_bold
def test_outlines_use_the_face_the_run_was_measured_in():
    """Outlining a bold run in the regular would put lighter glyphs in a box
    sized for heavier ones -- and PDF output is all outlines."""
    marked = only_ink(shape("**Reversible**", size=SIZE))
    bold = only_ink(shape("Reversible", size=SIZE, weight="bold"))
    plain = only_ink(shape("Reversible", size=SIZE))
    assert marked.envelope().bbox().width == pytest.approx(
        bold.envelope().bbox().width, abs=MICRON)
    assert marked.envelope().bbox().width != pytest.approx(
        plain.envelope().bbox().width, abs=MICRON)


@needs_bold
def test_marked_up_glyphs_stay_inside_the_measured_block():
    prim = shape("**(a)** //Exploded// view of {accent|the cell}, Ca^{2+}",
                 size=SIZE)
    glyphs = only_ink(prim).envelope().bbox()
    block = prim.envelope().bbox()
    assert block.x0 - MICRON <= glyphs.x0 and glyphs.x1 <= block.x1 + MICRON
    assert block.y0 - MICRON <= glyphs.y0 and glyphs.y1 <= block.y1 + MICRON


# --- fallback for scientific symbols --------------------------------------

#: The symbols a methods caption actually contains. Every one of them must
#: either be in the family or be borrowed from a face that has it; none may
#: come back as a `.notdef` box with a plausible width.
SYMBOLS = "µ °C ≥ → Å ∆ ± × ≈ Ω λ ‰ ½ − – — “” β α σ ⁻"


@pytest.mark.parametrize("symbol", SYMBOLS.split())
def test_a_scientific_symbol_is_drawn_by_something(symbol):
    prim = shape(symbol, size=SIZE)
    assert prim.missing == "", f"nothing installed can draw {symbol!r}"
    assert prim.width > 0.0


def test_borrowing_one_glyph_does_not_reset_the_whole_line():
    """Noto Sans has no U+2192. Handing the line to DejaVu because of it
    changes the typeface of every word in the caption to fix one arrow."""
    prim = shape("Temperature 25 °C rises → fast", size=SIZE)
    (line,) = prim.lines
    families = [run.font_family for run in line.runs]
    if len(families) == 1:
        pytest.skip("this machine's default family covers the arrow")
    assert families.count(prim.font_family) >= 2
    borrowed = [run.text for run in line.runs
                if run.font_family != prim.font_family]
    assert "".join(borrowed).strip() == "→"


def test_fallback_is_the_same_face_every_time():
    """Two runs of the same script in one figure must not land in two
    different fonts, or the page is set in a typeface nobody chose."""
    first = shape("a → b", size=SIZE).lines[0].runs
    second = shape("c → d", size=SIZE).lines[0].runs
    paths = {run.font_path for run in first if run.text.strip() == "→"}
    assert paths == {run.font_path for run in second if run.text.strip() == "→"}


@needs_bold
def test_a_borrowed_face_for_a_bold_run_is_asked_for_bold():
    """The fallback search inherits the run's weight, not the block's, so a
    bold word in a script the family lacks is set in that script's bold if the
    machine has one -- and in its only weight if it does not."""
    prim = shape("plain **bold 視覚**", size=SIZE)
    borrowed = [run for run in prim.lines[0].runs
                if run.font_family != prim.font_family]
    if not borrowed:
        pytest.skip("the theme family covers the sample")
    wanted = find_fallback("視覚", "700", False)
    assert wanted is not None
    assert {run.font_path for run in borrowed} == {wanted.path}


# --- OpenType features ----------------------------------------------------


def test_kerning_and_ligatures_are_on_by_default():
    face = find_font("sans")
    kerned = _advance_units("AV", face, ())
    unkerned = _advance_units("AV", face, feature_key({"kern": False}))
    assert kerned <= unkerned
    liga = _advance_units("fi", face, feature_key({"liga": True}))
    assert _advance_units("fi", face, ()) == liga


def test_tabular_figures_can_be_asked_for():
    """`tnum` is the real typographic win for an axis: ticks that do not
    shuffle sideways as the digits change."""
    face = find_font("Cantarell")
    if face.family != "Cantarell":
        pytest.skip("Cantarell, whose default figures are proportional, is absent")
    default = {_advance_units(d, face, ()) for d in "0123456789"}
    tabular = {_advance_units(d, face, feature_key({"tnum": True}))
               for d in "0123456789"}
    assert len(default) > 1 and len(tabular) == 1


def test_features_reach_the_shaper_through_inklet_text():
    wide = inklet.text("0123456789", font="Cantarell")
    if wide.prim.font_family != "Cantarell":
        pytest.skip("Cantarell is absent")
    tabular = inklet.text("0123456789", font="Cantarell", features={"tnum": True})
    assert tabular.prim.width != pytest.approx(wide.prim.width, abs=MICRON)


# --- how the marks are stored ---------------------------------------------
#
# `Styled` keeps one byte per character indexing a table of distinct marks
# rather than one `Mark` per character, because the even breaker hashes every
# candidate line it measures and the table costs the wrapper five times its
# running time. That is an optimisation with three sharp edges -- slicing,
# concatenating tables that disagree, and a hash that deliberately leaves the
# table out -- so each one is nailed down here.


def test_a_slice_keeps_the_marks_lined_up_with_the_characters():
    styled = parse("plain **bold** plain")
    assert styled[6:10].text == "bold"
    assert all(mark.bold for mark in styled[6:10].marks)
    assert not any(mark.bold for mark in styled[:6].marks)
    assert [span for span, _ in styled[6:10].spans()] == ["bold"]


def test_two_blocks_that_read_the_same_but_are_set_differently_are_not_equal():
    """The shaped-run cache is keyed on `Styled`. If a bold line compared equal
    to the same words set regular, the second one would come back out of the
    cache in the first one's faces."""
    bold = parse("**word**")
    plain = parse("word")
    assert bold.text == plain.text
    assert bold != plain
    assert shape("**word**", size=SIZE).width != pytest.approx(
        shape("word", size=SIZE).width, abs=MICRON)


def test_the_hash_leaves_the_style_table_out_but_equality_does_not():
    """Deliberate: two blocks may collide in the dict and are then separated by
    `__eq__`. What must never happen is the reverse."""
    bold, plain = parse("**word**"), parse("word")
    assert hash(bold) == hash(plain)
    assert len({bold: 1, plain: 2}) == 2


def test_joining_two_differently_marked_strings_rebuilds_the_table():
    left, right = parse("**a**"), parse("//b//")
    joined = left + right
    assert joined.text == "ab"
    assert [(m.bold, m.italic) for m in joined.marks] == [(True, False), (False, True)]


def test_joining_an_empty_string_keeps_the_other_side_untouched():
    from inklet.typeset.markup import EMPTY

    styled = parse("**a**")
    assert (EMPTY + styled) is styled
    assert (styled + EMPTY) is styled


def test_a_block_with_more_styles_than_the_table_holds_says_so():
    from inklet.typeset.markup import MAX_STYLES

    crowded = "".join(f"{{#{n:06x}|x}}" for n in range(MAX_STYLES + 2))
    with pytest.raises(ValueError, match="distinct inline styles"):
        parse(crowded)


# --- what the reader is told the node is called ---------------------------


def test_a_box_is_named_what_its_label_says():
    """`node.name` is what the linter and `fig.report()` quote back. Quoting
    the delimiters at a reader who never typed them into a diagnostic makes
    the diagnostic harder to read than the figure."""
    assert inklet.box("**(a)** Cell").name == "(a) Cell"
    assert inklet.circle("{accent|hot}").name == "hot"
    assert inklet.box("H_{2}O reservoir").name == "H2O reservoir"
    # Nothing that is not markup is touched: a path keeps its backslashes and
    # an adsorbed species keeps its star.
    assert inklet.box(r"C:\Users\run").name == r"C:\Users\run"
    assert inklet.box("*CO coverage").name == "*CO coverage"


def test_a_diagnostic_quotes_the_label_the_reader_sees():
    """A figure is generated by something that cannot look at it, so the report
    is the only channel. Delimiters in it name a string nobody typed."""
    fig = inklet.figure(width=60)
    fig.add(inklet.overlay([inklet.box("**(a)** Cell", width=30, height=6),
                         inklet.label("a very long label indeed here")]))
    report = fig.report()
    assert "'(a) Cell'" in report
    assert "**" not in report and "_{" not in report


# --- scripts that are not Latin -------------------------------------------
#
# The acknowledgement line of `stress/electro_figure.py`, which is on the page
# precisely so that the fallback path is exercised by a figure and not only
# here. If any of this stops shaping, that page stops being typeset.

ACKNOWLEDGEMENT = "Typeset by inklet — δοκιμή · проверка · 組版試験 · اختبار"


def test_five_scripts_on_one_line_all_find_a_face():
    prim = shape(ACKNOWLEDGEMENT, size=3.0)
    if prim.missing:
        pytest.skip(f"this machine has no font for {prim.missing!r}")
    (line,) = prim.lines
    # Latin/Greek/Cyrillic share a face; CJK and Arabic each borrow their own.
    assert len({(run.font_path, run.font_index) for run in line.runs}) >= 3
    assert sum(run.advance for run in line.runs) == pytest.approx(
        line.advance, abs=MICRON)
    assert all(run.advance > 0 for run in line.runs)


def test_a_right_to_left_run_keeps_its_own_shaping():
    """Arabic is shaped as one buffer in one face, so the letters join. Cut
    into one span per character it would come back in isolated forms."""
    prim = shape("اختبار", size=6.0)
    if prim.missing:
        pytest.skip("this machine has no Arabic face")
    (line,) = prim.lines
    assert len(line.runs) <= 1
    assert line.advance > 0
    # Joined forms are narrower than the isolated letters set side by side.
    isolated = sum(shape(char, size=6.0).width for char in "اختبار")
    assert line.advance < isolated


def test_a_combining_mark_adds_ink_but_no_width():
    """A mark is positioned onto the letter it belongs to, not set beside it.
    Measuring it as a character would widen every accented caption."""
    base = shape("a", size=10.0)
    marked = shape("a\u0301", size=10.0)      # a + combining acute
    assert marked.width == pytest.approx(base.width, abs=MICRON)

    ink = only_ink(marked).envelope().bbox()
    plain = only_ink(base).envelope().bbox()
    assert ink.width == pytest.approx(plain.width, abs=0.05)
    assert ink.y0 < plain.y0 - 1.0            # the accent sits above the letter


def test_a_line_never_breaks_a_mark_off_the_letter_it_belongs_to():
    prim = shape("aaaa a\u0301aaa aaaa", size=6.0, width=14.0)
    assert len(prim.lines) > 1
    for line in prim.lines:
        assert not line.text.startswith("\u0301")
