"""HarfBuzz shaping: the one place in inklet where glyph advances come from.

Runs are shaped at the font's own em size and scaled to mm only at the end.
That buys three things at once: the shaped-run cache is size-independent, an
advance is exactly linear in the type size, and the numbers stay integers
until a single final multiply — so shaping the same label twice gives
bit-identical floats, which is what the deterministic-output promise rests on.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, fields, replace
from functools import lru_cache
from typing import Mapping

import uharfbuzz as hb

from ..core.geom import Rect
from ..core.prims import TextLine, TextPrim, TextRun
from ..core.units import mm, pt
from .fonts import FontFace, find_fallback, find_font, load_face, weight_number
from .markup import EMPTY, Mark, Styled, flat, has_markup, parse

# HarfBuzz otherwise takes the language from the process locale, which would
# make output depend on the environment it was rendered in.
DEFAULT_LANGUAGE = "en"

# Slack when testing a candidate line against a wrap width, in mm. Advances are
# integer font units times one float, so the error to absorb is tiny.
_FIT_EPSILON = 1e-9

_ALIGN_ALIASES = {"left": "start", "start": "start", "center": "center",
                  "centre": "center", "right": "end", "end": "end",
                  "justify": "justify", "justified": "justify"}

_ITALIC_WORDS = ("italic", "oblique")


def shape(
    text: str,
    *,
    font: str | FontFace = "sans",
    size: float | str = pt(7),
    weight: str = "regular",
    align: str = "center",
    line_height: float = 1.25,
    width: float | str | None = None,
    features: dict[str, bool | int] | None = None,
    markup: bool = True,
    colors: Mapping[str, str] | None = None,
) -> TextPrim:
    """Measure a string into a fully-shaped TextPrim.

    `size` and `width` are millimetres — pass `units.pt(7)` for a 7pt label, or
    a string like `"7pt"`. `font` is a family name, a path, or a FontFace;
    `weight` may carry a slant, e.g. `"bold italic"`, and is ignored when a
    FontFace is passed directly. `line_height` is a multiple of `size`. `\\n` always breaks a line; `width` additionally
    greedy-wraps on whitespace, which collapses runs of spaces. A single word
    wider than `width` overflows rather than being broken mid-word.

    `align="justify"` requires `width` and stretches the spaces of every line
    but a paragraph's last so it fills the column exactly.

    Inline markup, all of it escapable with `\\` and all of it composable:

    * `**bold**`, `//italic//` -- set in the bold, italic or bold-italic face
      of the same family, resolved the way the block's own face was.
    * `{#c1121f|text}` -- a fill for those characters; a name in `colors` is
      looked up there first, so a theme can offer `{accent|text}`.
    * `_{...}` and `^{...}` -- sub- and superscripts, `H_{2}O`, `x^{2}`, at
      `SCRIPT_SCALE` of the size and shifted off the baseline.

    The braces and the doubled delimiters are the markup, so `file_name`,
    `m^-1`, `*CO` and `https://a.b` are typed as they are; see
    `inklet.typeset.markup` for the whole grammar. `markup=False` turns the lot
    off, for a string that must reach the page exactly as given.

    `features` are OpenType feature tags, e.g. `{"kern": False, "liga": True}`.

    Raises FontNotFoundError if the family resolves to nothing, and ValueError
    for a non-positive size or width or an unrecognised alignment.
    """
    size_mm = mm(size)
    if size_mm <= 0:
        raise ValueError(f"font size must be positive, got {size!r}")
    limit = None if width is None else mm(width)
    if limit is not None and limit <= 0:
        raise ValueError(f"wrap width must be positive, got {width!r}")
    alignment = _resolve_align(align)

    slant = _split_slant(weight)
    face = font if isinstance(font, FontFace) else find_font(font, *slant)
    faces = _Faces(face, None if isinstance(font, FontFace) else str(font), *slant)
    otf = feature_key(features)
    step = line_height * size_mm

    if alignment == "justify" and limit is None:
        raise ValueError("align='justify' needs a width to justify to")

    styled = _styled(text, markup, colors)
    ascent, descent, _ = face.metrics(size_mm)
    lines = []
    borrowed: set[str] = set()
    for paragraph in _break_lines(
            styled, faces, otf, limit, size_mm, alignment == "justify"):
        # The last line of a paragraph keeps its natural width. Stretching it
        # too is the classic justification bug: a two-word closing line spread
        # across the column reads as damage, not as type.
        last = len(paragraph) - 1
        for offset, line in enumerate(paragraph):
            runs = _runs(line, faces, otf, size_mm)
            advance = sum(run.advance for run in runs)
            spacing = 0.0
            if alignment == "justify" and offset < last:
                spacing = _word_spacing(line, advance, limit)
                if spacing > 0.0:
                    advance = limit
            # A single run in the face the block already names is the ordinary
            # case, and saying so twice would only invite the two to disagree.
            mixed = () if _is_plain(runs, face) else runs
            borrowed.update((run.font_path, run.font_index)
                            for run in mixed if run.font_path)
            lines.append(TextLine(line.text, advance, len(lines) * step,
                                  spacing, mixed))
    lines = tuple(lines)
    # A borrowed face is rarely the same height as the one asked for -- CJK
    # faces in particular sit taller and deeper -- so the block takes the
    # extreme of every face drawing it. Sizing it to the Latin metrics alone
    # would crop the very glyphs the fallback was found for.
    for path, index in sorted(borrowed):
        other_ascent, other_descent, _ = load_face(path, index).metrics(size_mm)
        ascent = max(ascent, other_ascent)
        descent = max(descent, other_descent)
    # A superscript reaches above the ascender and a subscript below the
    # descender, by a little; the block has to hold them or the box around a
    # formula clips the "2" in H2O.
    for line in lines:
        for run in line.runs:
            if run.size is None:
                continue
            top, bottom, _ = face.metrics(run.size)
            ascent = max(ascent, top - run.shift)
            descent = max(descent, bottom + run.shift)
    return TextPrim(
        lines=lines,
        font_family=face.family,
        font_size=size_mm,
        ascent=ascent,
        descent=descent,
        align=alignment,
        font_path=face.path,
        requested_family=_requested_family(font, face),
        missing=_missing(lines, face),
        # `otf` is already core's canonical form -- sorted `(tag, value)` pairs,
        # what `core.prims.text_features` builds -- because it is what the
        # shaper was handed. Anything reshaping this block afterwards reads it
        # off the prim instead of being told again and told wrong.
        **({"features": otf} if _PRIM_TAKES_FEATURES else {}),
    )


def _styled(text: str, markup: bool, colors: Mapping[str, str] | None) -> Styled:
    """The text with its marks, or one flat mark per character when there is
    no markup to read -- which is the case for every axis tick in a figure."""
    if markup and has_markup(text):
        return parse(text, colors=colors)
    return flat(text)


@dataclass(frozen=True, slots=True)
class _Faces:
    """The faces one block can be set in: the one asked for, and the heavier
    or sloped variants its inline markup calls for.

    `request` is the family string the caller gave -- a CSS-style chain, most
    often -- and asking for the bold with the *same* string is what keeps the
    substitution policy the same for every run on the line. A caller who
    passed a `FontFace` directly gets `None` here and is re-asked by resolved
    family name, which is the only thing left to ask with.
    """

    base: FontFace
    request: str | None
    weight: str
    italic: bool

    def for_mark(self, mark: Mark) -> FontFace:
        if not (mark.bold or mark.italic):
            return self.base
        return _variant(self.base, self.request, *self.demand(mark))

    def demand(self, mark: Mark) -> tuple[int, bool]:
        """The weight and slant this mark asks for, as `find_font` wants them.

        `**` inside an already-bold block is a no-op rather than an escalation:
        it means "the bold face", and a block set in Black has no heavier one.
        """
        weight = weight_number(self.weight)
        return (max(weight, _BOLD) if mark.bold else weight,
                self.italic or mark.italic)

    def slant(self, mark: Mark) -> tuple[str, bool]:
        """What to ask `find_fallback` for, so a borrowed face matches the run
        it is standing in for."""
        weight, italic = self.demand(mark)
        return str(weight), italic


_BOLD = 700


@lru_cache(maxsize=64)
def _variant(base: FontFace, request: str | None, weight: int,
             italic: bool) -> FontFace:
    """The bold/italic face of the family `base` came from.

    Falls back to `base` rather than to a stranger: a family with no italic
    installed answers with something from a different typeface often enough
    that setting one word of a caption in it would read as a mistake, and a
    regular where an italic was asked for reads as a machine without the font.
    That is also what happens when the family simply has no such face --
    nothing here synthesises a slant or smears a stem to fake one.
    """
    for asked in (request, base.family):
        if asked is None:
            continue
        found = find_font(asked, str(weight), italic)
        if found.family == base.family:
            return found
    return base


def _missing(lines: tuple[TextLine, ...], face: FontFace) -> str:
    """Characters that survived fallback with still no font to draw them.

    `_face_for` hands a character back to the original face when nothing
    installed covers it, which is the honest outcome -- an empty box the reader
    can see -- but it has to be reported, because the advance that came back
    was the width of that box and not of the character.
    """
    absent = []
    for line in lines:
        for text, used in (((run.text, load_face(run.font_path, run.font_index))
                            for run in line.runs)
                           if line.runs else ((line.text, face),)):
            absent.append(_uncovered(text, used))
    return "".join(dict.fromkeys("".join(absent)))


def _is_plain(runs: tuple[TextRun, ...], face: FontFace) -> bool:
    """Whether the whole line is set in the face the prim already names, at
    its size, on its baseline and in the block's colour -- so a backend can
    draw it as one string."""
    return all(run.font_path == face.path and run.font_index == face.index
               and run.size is None and run.shift == 0.0
               and getattr(run, "fill", None) is None
               for run in runs)


#: CSS generic families. A request ending in one of these is a request to
#: substitute, so honouring it is not a substitution worth reporting.
_GENERIC_REQUESTS = frozenset({
    "sans", "sans-serif", "serif", "mono", "monospace",
    "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif",
    "ui-monospace", "ui-rounded", "math", "emoji", "fangsong",
})


def _requested_family(font, face: FontFace) -> str | None:
    """Record the asked-for family only when it is not what came back.

    fc-match always answers, so asking for a font nobody has installed yields a
    substitute rather than an error. Downstream cannot warn about that unless
    the original request survives.

    A CSS-style chain is read the way CSS reads it. `"Helvetica, Arial"` names
    two acceptable families and getting neither is worth saying; the same chain
    ending in `sans-serif` says "or whatever you have", and reporting that as
    an unmet request would fire on every correctly-written theme.
    """
    if isinstance(font, FontFace):
        return None
    names = [name.strip().strip("'\"") for name in str(font).split(",")]
    names = [name for name in names if name]
    if not names:
        return None
    if any(name.lower() == face.family.lower() for name in names):
        return None
    if names[-1].lower() in _GENERIC_REQUESTS:
        return None
    return names[0]


def measure(text: str, **options) -> Rect:
    """The block's local bounding box, centred on the origin like the prim itself."""
    box = shape(text, **options).envelope().bbox()
    return box if box is not None else Rect(0.0, 0.0, 0.0, 0.0)


def _break_lines(
    text: Styled,
    faces: _Faces,
    features: tuple[tuple[str, int], ...],
    limit: float | None,
    size: float,
    justify: bool = False,
) -> list[list[Styled]]:
    """Grouped by paragraph, because justification has to know which line is a
    paragraph's last one and a flat list has thrown that away."""
    paragraphs = text.paragraphs()
    if limit is None:
        return [[para] for para in paragraphs]
    wrap = _wrap_even if justify else _wrap
    return [wrap(para, faces, features, limit, size) for para in paragraphs]


def _word_spacing(line: Styled, advance: float, limit: float) -> float:
    """Millimetres to add to each space so the line reaches the column edge.

    Only spaces are stretched. Spreading the slack over every glyph gap instead
    -- which is what SVG's `lengthAdjust="spacing"` would do -- letter-spaces
    the words, and at the slack a narrow column produces that is visibly wrong.
    A line with no space, or one already over the limit, is left alone.
    """
    spaces = line.count(" ")
    slack = limit - advance
    if spaces == 0 or slack <= 0.0:
        return 0.0
    return slack / spaces


#: Characters that may not start a line: the closing punctuation and small
#: kana that Japanese typesetting forbids at a line head (kinsoku shori).
_NO_BREAK_BEFORE = frozenset(
    "、。，．！？：；・ー々〆゛゜ゝゞヽヾ"
    "）〕］｝〉》」』】〙〗〞"
    ")]}>,.!?:;"
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ"
)

#: Characters that may not end a line, for the same reason at the other edge.
_NO_BREAK_AFTER = frozenset("（〔［｛〈《「『【〘〖〝([{<")


def _wide(char: str) -> bool:
    """Whether this character is written on the ideographic square."""
    return unicodedata.east_asian_width(char) in ("W", "F")


def _breakable(before: str, after: str) -> bool:
    """Whether a line may break between these two characters.

    Scripts that do not write spaces -- Chinese, Japanese, Korean -- break
    between characters instead. Without this a Japanese sentence is a single
    `str.split()` word, cannot wrap at all, and overflows its column entire.

    This is the small, uncontroversial core of the rule: a break is allowed
    where an ideograph or kana meets its neighbour, and forbidden where it
    would strand closing punctuation at the head of a line or an opening
    bracket at the foot of one. It is not the full UAX #14 algorithm and does
    not pretend to be -- there is no Thai dictionary here, and no hyphenation.
    """
    if before in _NO_BREAK_AFTER or after in _NO_BREAK_BEFORE:
        return False
    if unicodedata.category(after) in ("Mn", "Mc", "Me"):
        return False           # never cut a mark from what it attaches to
    return _wide(before) or _wide(after)


@dataclass(frozen=True, slots=True)
class _Pieces:
    """A paragraph, normalised, and every index a line may break at.

    The pieces are held as offsets into one normalised string rather than as a
    list of fragments, because the even breaker asks for O(words^2) candidate
    lines and each one is then a pair of slices instead of a join over a slice
    of a list. That took the caption of `stress/electro_figure.py` from
    7.1 ms to 4.6 ms.
    """

    whole: Styled            # the paragraph with runs of whitespace collapsed
    edge: tuple[int, ...]    # where each piece starts, plus the end

    def __len__(self) -> int:
        return len(self.edge) - 1

    def line(self, start: int, stop: int) -> Styled:
        """Pieces `start:stop` as a line, without the separator in front."""
        at = self.edge[start]
        text = self.whole.text
        if at < len(text) and text[at] == " ":
            at += 1
        return self.whole[at:self.edge[stop]]


def _pieces(paragraph: Styled) -> _Pieces:
    """The paragraph cut at every place a line may break.

    Each piece carries the separator in front of it, so joining a slice
    reconstructs the line exactly: a piece following a space begins with one, a
    piece following a Japanese character begins with nothing. Runs of
    whitespace collapse to a single space, as they did when this was
    `str.split()`, and for text with no ideographs the result is precisely that
    -- which is why no Latin line break in any existing figure moves.
    """
    parts: list[Styled] = []
    for lead, word in paragraph.words():
        start = 0
        for at in range(1, len(word)):
            if _breakable(word.text[at - 1], word.text[at]):
                parts.append(lead + word[start:at])
                lead, start = EMPTY, at
        parts.append(lead + word[start:])
    if not parts:
        return _Pieces(EMPTY, (0,))
    edge, at = [0], 0
    for part in parts:
        at += len(part)
        edge.append(at)
    whole = Styled("".join(part.text for part in parts),
                   b"".join(part.codes for part in parts),
                   paragraph.styles)
    return _Pieces(whole, tuple(edge))


def _join(pieces: _Pieces, start: int, stop: int) -> Styled:
    """One line, without the separator that put the break in front of it."""
    return pieces.line(start, stop)


def _wrap(
    paragraph: Styled,
    faces: _Faces,
    features: tuple[tuple[str, int], ...],
    limit: float,
    size: float,
) -> list[Styled]:
    """Greedy wrap, measuring each candidate line as a whole.

    Measuring the joined candidate rather than summing word widths is the point:
    kerning and ligatures cross the space, so a sum would drift from the advance
    the line actually gets, and a box sized from that sum would be wrong.
    """
    pieces = _pieces(paragraph)
    n = len(pieces)
    if not n:
        return [EMPTY]

    lines: list[Styled] = []
    start = 0
    for at in range(2, n + 1):
        if _advance_mm(pieces.line(start, at), faces, features,
                       size) > limit + _FIT_EPSILON:
            lines.append(pieces.line(start, at - 1))
            start = at - 1
    lines.append(pieces.line(start, n))
    return lines


# What one forced overfull line costs. Bigger than any slack cube a real column
# can produce, so the breaker never chooses to overflow, but finite, so a
# paragraph containing an unbreakable long word still gets laid out.
_OVERFULL_PENALTY = 1e12


def _wrap_even(
    paragraph: Styled,
    faces: _Faces,
    features: tuple[tuple[str, int], ...],
    limit: float,
    size: float,
) -> list[Styled]:
    """Break so the *worst* line is as full as possible, not so the first is.

    Greedy wrapping and justification are a bad pair: greedy takes everything
    it can on each line, so the leftovers pile up and one line ends up stretched
    to four times the natural space width -- the rivers that make justified text
    look broken. Minimising the *worst stretch per space* instead spreads the
    shortfall across the paragraph, which is the classical Knuth badness without
    the hyphenation. Cubed rather than squared because one very loose line is
    worse than several slightly loose ones, and that has to outweigh the
    arithmetic of adding them up.

    Left- and centre-aligned text keeps the greedy breaker: slack there is a
    ragged edge rather than a stretched space, and changing it would move every
    line break in every figure already written.
    """
    pieces = _pieces(paragraph)
    n = len(pieces)
    if not n:
        return [EMPTY]

    # best[i]: (line count, total badness) for words[i:], compared in that
    # order. Badness alone would happily spend an extra line to relax the
    # spaces, which makes the paragraph taller -- and a caption that grows a
    # line to look better has traded the wrong thing. Line count first makes
    # the breaker choose only among the shortest layouts, which is what greedy
    # already guarantees is achievable.
    infinite = (float("inf"), float("inf"))
    best = [infinite] * n + [(0, 0.0)]
    nxt = list(range(1, n + 2))
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            line = _join(pieces, i, j)
            advance = _advance_mm(line, faces, features, size)
            over = advance > limit + _FIT_EPSILON
            if over and j > i + 1:
                break            # every longer candidate is wider still
            slack = limit - advance
            # Badness is the stretch *per space*, not the total shortfall: a
            # line with eight spaces absorbs 8mm invisibly where a line with one
            # is torn in half by it. Dividing by the space count is what makes
            # this Knuth's measure rather than plain min-raggedness.
            spaces = line.count(" ")
            stretch = slack / spaces if spaces else slack
            # A paragraph's last line is free: it ends where the text ends.
            penalty = (_OVERFULL_PENALTY if over
                       else 0.0 if j == n else stretch ** 3)
            lines_after, badness = best[j]
            total = (lines_after + 1, badness + penalty)
            if total < best[i]:
                best[i], nxt[i] = total, j

    lines: list[Styled] = []
    at = 0
    while at < n:
        lines.append(_join(pieces, at, nxt[at]))
        at = nxt[at]
    return lines


@lru_cache(maxsize=8192)
def _advance_units(text: str, face: FontFace, features: tuple[tuple[str, int], ...]) -> int:
    """Shaped advance of one line, in font units."""
    if not text:
        return 0
    return sum(pos.x_advance for pos in shape_buffer(text, face, features).glyph_positions)


@lru_cache(maxsize=8192)
def _advance_mm(text: Styled, faces: _Faces, features: tuple[tuple[str, int], ...],
                size: float) -> float:
    """Width of one line in mm, measured in the fonts that can actually draw it.

    This, not `_advance_units`, is what wrapping and layout must ask. A face
    with no glyph for a character still returns an advance -- the .notdef box
    -- so measuring Japanese in a Latin font yields a plausible number that is
    simply wrong, and every envelope built on it is wrong too. The same goes
    for a bold phrase: it is wider than the regular the block names, and a
    column wrapped against the regular would overrun.

    Cached on top of `_runs`, which is already cached, because the even breaker
    asks for the same candidate line from several starting points and the sum
    is a Python loop over every run of it.
    """
    return sum(run.advance for run in _runs(text, faces, features, size))


#: The script's size as a fraction of the text's, and where its baseline sits
#: as a fraction of the text size: subscripts drop, superscripts rise. The
#: numbers are the OpenType defaults most faces ship with, rounded.
SCRIPT_SCALE = 0.65
SUBSCRIPT_SHIFT = 0.15
SUPERSCRIPT_SHIFT = -0.40

#: Whether this build of core can carry a per-run colour (contract M7). Read
#: rather than assumed, so the typesetter works either way and a figure using
#: `{fill|...}` on an older core loses the colour instead of failing to build.
_RUN_TAKES_FILL = any(field.name == "fill" for field in fields(TextRun))

#: Whether a `TextPrim` can carry the features it was shaped with. Same reading
#: as above: without it, outlining has to be told the features a second time.
_PRIM_TAKES_FEATURES = any(field.name == "features" for field in fields(TextPrim))


@lru_cache(maxsize=8192)
def _runs(text: Styled, faces: _Faces, features: tuple[tuple[str, int], ...],
          size: float) -> tuple[TextRun, ...]:
    """One line as runs: each span of one mark shaped in the face that mark
    calls for, then split further wherever that face runs out of glyphs.

    The common case -- one mark for the whole line, in the block's own face --
    comes straight back out of `_plain_runs` untouched, which is what keeps a
    plain label costing exactly what it used to.
    """
    out: list[TextRun] = []
    for span, mark in text.spans():
        face = faces.for_mark(mark)
        small = size if mark.level == 0 else size * SCRIPT_SCALE
        shift = 0.0 if mark.level == 0 else size * (
            SUBSCRIPT_SHIFT if mark.level > 0 else SUPERSCRIPT_SHIFT)
        for run in _plain_runs(span, face, features, small, faces.slant(mark)):
            out.append(_marked(run, mark, small, shift))
    return tuple(out)


def _marked(run: TextRun, mark: Mark, size: float, shift: float) -> TextRun:
    """A shaped run wearing the rest of what its mark asked for.

    Weight and slant are already in the run -- they are a different face, and
    the face is what it was shaped in. What is left is the size and baseline of
    a script and the fill of a colour span, neither of which changes a glyph.
    """
    if mark.level != 0:
        run = replace(run, size=size, shift=shift)
    if mark.fill is not None and _RUN_TAKES_FILL:
        run = replace(run, fill=mark.fill)
    return run


@lru_cache(maxsize=8192)
def _plain_runs(text: str, face: FontFace, features: tuple[tuple[str, int], ...],
                size: float, slant: tuple[str, bool]) -> tuple[TextRun, ...]:
    """One line split into spans that a single font can draw, in order.

    Three cases, cheapest first. Usually the chosen face covers everything and
    there is one run. Failing that, if the chosen face is the wrong face for
    this text altogether, one *other* face often covers the whole line -- a CJK
    font has Latin in it, so a Japanese sentence quoting "Fig. 1c" still shapes
    as one buffer, which keeps kerning and, for right-to-left text, keeps
    HarfBuzz's own ordering. Otherwise the line is cut into spans, and that
    last case cannot express a right-to-left line containing a left-to-right
    phrase: doing so needs the bidi algorithm, which inklet does not implement.
    """
    if not text:
        return ()
    if _uncovered(text, face) == "":
        return (_run(text, face, features, size),)

    if _mostly_absent(text, face):
        whole = find_fallback(text, *slant)
        if whole is not None and _uncovered(text, whole) == "":
            return (_run(text, whole, features, size),)

    spans: list[tuple[str, FontFace]] = []
    current = face
    start = 0
    for index, char in enumerate(text):
        chosen = _face_for(char, face, current, slant)
        if chosen is not current:
            if index > start:
                spans.append((text[start:index], current))
            start, current = index, chosen
    spans.append((text[start:], current))
    return tuple(_run(span, using, features, size) for span, using in spans)


#: How much of a line the chosen face has to be missing before the whole line
#: is handed to another one. The shortcut is for text in a script the face was
#: never meant for; a Latin caption with one arrow in it is not that, and
#: resetting all thirty of its characters in DejaVu because Noto Sans lacks
#: U+2192 changes the typeface of a whole line to fix one glyph.
_WHOLE_LINE_FALLBACK = 0.5


def _mostly_absent(text: str, face: FontFace) -> bool:
    """Whether this face is the wrong face for this text, rather than merely
    short of a symbol or two."""
    letters = [char for char in text if not char.isspace()]
    covered = sum(1 for char in letters if _covers(face, char))
    return covered < _WHOLE_LINE_FALLBACK * len(letters)


def _face_for(char: str, primary: FontFace, current: FontFace,
              slant: tuple[str, bool]) -> FontFace:
    """Which face should draw this character, preferring continuity.

    Whitespace stays with whatever is drawing the words around it, so that a
    phrase in one script does not fragment at every space. Anything the
    original face can draw goes back to it, so a Latin word inside a Japanese
    sentence is set in the Latin font it was asked for rather than in the CJK
    font's Latin, which is a different design at a different weight. Keeping
    `current` in preference to a fresh search is what makes a run of borrowed
    characters -- "≥ 10" or a Japanese clause -- one span rather than one per
    character, and it is per character that fontconfig would be asked.
    """
    if char.isspace():
        return current
    if _covers(primary, char):
        return primary
    if _covers(current, char):
        return current
    found = find_fallback(char, *slant)
    return found if found is not None and _covers(found, char) else primary


def _run(text: str, face: FontFace, features: tuple[tuple[str, int], ...],
         size: float) -> TextRun:
    return TextRun(text, face.family,
                   _advance_units(text, face, features) * face.scale(size),
                   face.path, face.index)


def _uncovered(text: str, face: FontFace) -> str:
    """The distinct characters of `text` this face has no glyph for, in order."""
    covered = _coverage(face)
    missing = {char for char in text if ord(char) not in covered}
    return "".join(char for char in dict.fromkeys(text) if char in missing)


def _covers(face: FontFace, char: str) -> bool:
    return ord(char) in _coverage(face)


@lru_cache(maxsize=32)
def _coverage(face: FontFace) -> frozenset[int]:
    """Every codepoint this face has a glyph for, read once from its cmap."""
    return frozenset(_hb_font(face).face.unicodes)


def shape_buffer(text: str, face: FontFace,
                 features: tuple[tuple[str, int], ...]) -> hb.Buffer:
    """Shape one line and hand back the buffer, for callers that need glyphs.

    `text` must be non-empty: HarfBuzz leaves the position array unset for an
    empty buffer. `features` is the sorted-tuple form from `feature_key`.
    """
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = DEFAULT_LANGUAGE
    hb.shape(_hb_font(face), buffer, dict(features))
    return buffer


def feature_key(features: dict[str, bool | int] | None) -> tuple[tuple[str, int], ...]:
    """Hashable, order-independent form of a feature dict."""
    if not features:
        return ()
    return tuple(sorted((tag, int(value)) for tag, value in features.items()))


@lru_cache(maxsize=32)
def _hb_font(face: FontFace) -> hb.Font:
    """A HarfBuzz font scaled to font units, so advances come back unscaled.

    Cached per face; HarfBuzz fonts are not safe to shape with concurrently, so
    this module is single-threaded by construction.
    """
    hb_face = hb.Face(hb.Blob.from_file_path(face.path), face.index)
    font = hb.Font(hb_face)
    font.scale = (face.units_per_em, face.units_per_em)
    return font


def _split_slant(weight: str) -> tuple[str, bool]:
    """Pull an italic/oblique token out of a weight string like "bold italic"."""
    tokens = weight.replace("-", " ").replace("_", " ").split()
    upright = [t for t in tokens if t.lower() not in _ITALIC_WORDS]
    return " ".join(upright) or "regular", len(upright) != len(tokens)


def _resolve_align(align: str) -> str:
    try:
        return _ALIGN_ALIASES[align.strip().lower()]
    except KeyError:
        raise ValueError(
            f"unknown alignment {align!r}; expected start/center/end "
            f"(left/right also accepted)"
        ) from None
