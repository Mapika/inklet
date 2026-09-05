"""The inline markup grammar: bold, italic, colour, sub- and superscript.

A caption in this family of journals sets its panel letters bold -- "**(a)**
Exploded view..." -- and its species names italic, in the middle of a
justified paragraph. That cannot be a separate diagram per phrase, because a
diagram cannot be justified into the paragraph around it, so the weight has to
travel inside the string.

The delimiters were chosen against the corpus rather than against Markdown,
because a caption is not prose:

* ``**bold**`` -- doubled, because a lone ``*`` is the adsorbed-species prefix
  of every electrochemistry caption ever written (``*CO``, ``*OH``), and
  Markdown's ``*italic*`` would silently italicise everything between two of
  them.
* ``//italic//`` -- doubled for the same reason, and a ``//`` directly after a
  colon is a URL's scheme separator, never a delimiter, so a caption may cite
  two DOIs without turning the text between them over.
* ``{fill|text}`` -- colour. The fill is anything a renderer accepts
  (``{#c1121f|red}``) or a theme token when the caller supplies a palette
  (``{accent|this curve}``).
* ``_{sub}`` and ``^{super}`` -- unchanged, and the reason the braces are
  required: ``file_name`` and ``m^-1`` must survive being typed literally.
* ``\\`` escapes any of ``* / { } | _ ^ \\`` and nothing else, so a Windows
  path keeps its backslashes.

Two rules make the grammar deterministic, and both are worth stating because
they are what a reader will test it against. **Each opener takes the nearest
matching closer**, so ``**a //b** c//`` is bold "a //b" followed by literal
" c//" -- delimiters do not cross. **A delimiter with no partner is ordinary
text**, so half-typed markup shows up as itself instead of eating the rest of
the paragraph.

The parser hands back a `Styled`: the plain text with one `Mark` per
character. Per character rather than per span because wrapping slices lines
out of the middle of the string, and a bold phrase has to be able to break
across a line -- which it can only do if the style survives the slice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Mapping, NamedTuple, Sequence

__all__ = ["Mark", "Styled", "escape_markup", "flat", "parse", "strip_markup",
           "theme_colors"]

#: The characters `\` makes literal. Anything else after a backslash keeps the
#: backslash, so `C:\Users` is typed as it is.
ESCAPABLE = "*/{}|_^\\"

#: `{fill|` -- an opener only with a fill that could be one: no braces, no
#: pipes, no whitespace at the ends. A bare `{` stays a brace.
_COLOUR_OPEN = re.compile(r"\{([^\s{}|\\](?:[^{}|\\]*[^\s{}|\\])?)\|")


class Mark(NamedTuple):
    """Everything the markup can say about one character.

    `level` is 0 for ordinary text, +1 for a subscript and -1 for a
    superscript, matching the sign of the baseline shift each one takes.

    A tuple rather than a dataclass because there is one of these per
    character and wrapping hashes a candidate line for every break it
    considers: `tuple.__hash__` is the C one, and on a justified caption that
    is the difference between a fifth of the shaping time and a twentieth.
    """

    bold: bool = False
    italic: bool = False
    fill: str | None = None
    level: int = 0


PLAIN = Mark()


#: A text block may use this many distinct inline styles. The limit exists
#: because the codes are bytes; 255 combinations of weight, slant, script level
#: and fill is far past what a caption can be, and the alternative costs the
#: wrapper five times its running time (see `Styled`).
MAX_STYLES = 255


@dataclass(frozen=True, slots=True, eq=False)
class Styled:
    """Plain text plus one `Mark` per character.

    Immutable and hashable, so it can key the shaped-run caches the way a bare
    string used to. Slicing keeps the marks aligned, which is the whole point:
    a line the wrapper cuts out of the middle of a bold phrase is still bold.

    The marks are held as one byte per character indexing a small table rather
    than as a tuple of `Mark`. Justifying a paragraph asks the breaker to
    measure every candidate line, each measurement hashes the candidate, and
    hashing a fifty-tuple of tuples is fifty trips through the interpreter
    where hashing fifty bytes is one memory scan. Swapping the representation
    took the caption of `stress/electro_figure.py` from 10.5 ms to 7.1 ms.
    """

    text: str
    codes: bytes                # one index per character into `styles`
    styles: tuple[Mark, ...]    # distinct marks, in first-appearance order

    def __post_init__(self) -> None:
        if len(self.text) != len(self.codes):
            raise ValueError(
                f"a Styled needs one mark per character, got {len(self.codes)} "
                f"for {len(self.text)}"
            )

    def __len__(self) -> int:
        return len(self.text)

    def __bool__(self) -> bool:
        return bool(self.text)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Styled):
            return NotImplemented
        return (self.text == other.text and self.codes == other.codes
                and self.styles == other.styles)

    def __hash__(self) -> int:
        # The style table is deliberately left out. CPython caches the hash of
        # a `str` and of a `bytes`, so this is two loads and a combine, where
        # folding in a tuple of `Mark` would re-hash every field of every
        # distinct style on every lookup -- and the wrapper hashes a candidate
        # line for each of the O(words^2) breaks it considers. Two blocks that
        # agree on text and codes but not on styles collide, which is what
        # `__eq__` is for.
        return hash((self.text, self.codes))

    def __getitem__(self, index: slice) -> Styled:
        return Styled(self.text[index], self.codes[index], self.styles)

    def __add__(self, other: Styled) -> Styled:
        if not other.text:
            return self
        if not self.text:
            return other
        if self.styles is other.styles or self.styles == other.styles:
            return Styled(self.text + other.text, self.codes + other.codes,
                          self.styles)
        return of_marks(self.text + other.text, self.marks + other.marks)

    @property
    def marks(self) -> tuple[Mark, ...]:
        """One `Mark` per character, unpacked. For callers that want them all;
        `spans()` is what the typesetter uses."""
        table = self.styles
        return tuple(table[code] for code in self.codes)

    def count(self, sub: str) -> int:
        return self.text.count(sub)

    def removeprefix(self, prefix: str) -> Styled:
        cut = len(prefix) if self.text.startswith(prefix) else 0
        return self[cut:]

    def spans(self) -> Iterator[tuple[str, Mark]]:
        """The text as maximal runs of one mark, in order."""
        codes, table = self.codes, self.styles
        start = 0
        for at in range(1, len(codes) + 1):
            if at == len(codes) or codes[at] != codes[start]:
                yield self.text[start:at], table[codes[start]]
                start = at

    def paragraphs(self) -> list[Styled]:
        """Split on `\\n`, like `str.split("\\n")`."""
        out, start = [], 0
        for at, char in enumerate(self.text):
            if char == "\n":
                out.append(self[start:at])
                start = at + 1
        out.append(self[start:])
        return out

    def words(self) -> list[tuple[Styled, Styled]]:
        """`(gap, word)` per word, like `str.split()` with the gaps kept.

        The gap is the whitespace *before* the word, collapsed to one space and
        keeping the mark it was typed with -- so the space in `**two words**`
        stays bold and the two words shape as one run, while the space in
        `plain **word**` does not and the bold starts where it was written.
        """
        out: list[tuple[Styled, Styled]] = []
        for match in re.finditer(r"(\s*)(\S+)", self.text):
            at = match.start(1)
            gap = (Styled(" ", self.codes[at:at + 1], self.styles)
                   if match.group(1) else EMPTY)
            out.append((gap, self[match.start(2):match.end(2)]))
        return out


EMPTY = Styled("", b"", ())


def flat(text: str, mark: Mark = PLAIN) -> Styled:
    """`text` with one mark throughout -- what every unmarked label is."""
    if not text:
        return EMPTY
    return Styled(text, bytes(len(text)), (mark,))


def of_marks(text: str, marks: Sequence[Mark]) -> Styled:
    """A `Styled` from one mark per character, packing the table itself."""
    table: dict[Mark, int] = {}
    codes = bytearray(len(text))
    for at, mark in enumerate(marks):
        code = table.get(mark)
        if code is None:
            if len(table) >= MAX_STYLES:
                raise ValueError(
                    f"a text block may use at most {MAX_STYLES} distinct inline "
                    f"styles; this one asks for more. Split it into several "
                    f"text nodes."
                )
            code = table[mark] = len(table)
        codes[at] = code
    return Styled(text, bytes(codes), tuple(table))


def parse(text: str, *, colors: Mapping[str, str] | None = None) -> Styled:
    """Read the markup out of `text`, leaving the plain characters and marks.

    `colors` maps a `{token|...}` name to what the renderer should fill with;
    a token that is not in it is passed through as written, so `{#c1121f|x}`
    needs no palette and `{accent|x}` does.
    """
    out_text: list[str] = []
    out_marks: list[Mark] = []
    _scan(text, PLAIN, colors or {}, out_text, out_marks)
    return of_marks("".join(out_text), out_marks)


def strip_markup(text: str) -> str:
    """`text` with its markup removed -- what the reader will actually see."""
    return parse(text).text


def escape_markup(text: str) -> str:
    """`text` with every markup character made literal.

    For interpolating data into a caption: a sample named `**` or a path with
    a brace in it should read as itself, not open a span.
    """
    return "".join("\\" + char if char in ESCAPABLE else char for char in text)


def theme_colors(theme) -> dict[str, str]:
    """The `{token|text}` names a theme offers: its roles and its series.

    `{accent|this curve}` in a caption is the point of the exercise -- a word
    coloured to match the line it names, without the author copying a hex
    string out of the palette and it going stale when the theme changes.
    `series0` upward are `theme.color(i)`, numbered the way the plots are.

    Duck-typed rather than importing `inklet.themes`, which imports this.
    """
    tokens = {"ink": theme.ink, "muted": theme.muted, "accent": theme.accent,
              "paper": theme.paper, "grid": theme.grid}
    tokens.update((f"series{index}", color)
                  for index, color in enumerate(theme.palette))
    return tokens


def has_markup(text: str) -> bool:
    """Whether the string contains anything the parser would act on.

    A fast reject for the overwhelmingly common case of a plain label, so an
    axis tick does not pay for a scan it cannot need.
    """
    return any(char in text for char in "*/{\\")


# -- the scanner ----------------------------------------------------------


def _scan(text: str, mark: Mark, colors: Mapping[str, str],
          out_text: list[str], out_marks: list[Mark]) -> None:
    """Append `text` to the output, parsed under `mark`.

    Recursive: a delimiter that finds its partner re-enters with the enclosed
    substring and a modified mark, which is what makes `**//both//**` compose.
    """
    at = 0
    while at < len(text):
        char = text[at]
        if char == "\\" and at + 1 < len(text) and text[at + 1] in ESCAPABLE:
            out_text.append(text[at + 1])
            out_marks.append(mark)
            at += 2
            continue

        span = _delimited(text, at, mark, colors)
        if span is not None:
            inner, inner_mark, after = span
            _scan(inner, inner_mark, colors, out_text, out_marks)
            at = after
            continue

        out_text.append(char)
        out_marks.append(mark)
        at += 1


def _delimited(text: str, at: int, mark: Mark,
               colors: Mapping[str, str]) -> tuple[str, Mark, int] | None:
    """The span opening at `at`: its contents, its mark, and where it ends.

    None when nothing opens here, or when what opens here never closes -- in
    which case the caller emits the character as itself.
    """
    if text.startswith("**", at) and not _star_run(text, at):
        close = _find(text, "**", at + 2, skip_runs=True)
        if close is not None:
            return text[at + 2:close], mark._replace(bold=True), close + 2
        return None
    if text.startswith("//", at) and not _url_slashes(text, at):
        close = _find(text, "//", at + 2, skip_urls=True)
        if close is not None:
            return text[at + 2:close], mark._replace(italic=True), close + 2
        return None
    if text[at] in "_^" and text.startswith("{", at + 1):
        close = _matching_brace(text, at + 1)
        if close is not None:
            level = 1 if text[at] == "_" else -1
            return text[at + 2:close], mark._replace(level=level), close + 1
        return None
    if text[at] == "{":
        opener = _COLOUR_OPEN.match(text, at)
        if opener is not None:
            close = _matching_brace(text, at)
            if close is not None:
                fill = opener.group(1)
                return (text[opener.end():close],
                        mark._replace(fill=colors.get(fill, fill)),
                        close + 1)
    return None


def _find(text: str, token: str, start: int, *, skip_urls: bool = False,
          skip_runs: bool = False) -> int | None:
    """The next unescaped `token` at or after `start`."""
    at = start
    while True:
        found = text.find(token, at)
        if found < 0:
            return None
        if (_escaped(text, found) or (skip_urls and _url_slashes(text, found))
                or (skip_runs and _star_run(text, found))):
            at = found + 1
            continue
        return found


def _matching_brace(text: str, start: int) -> int | None:
    """The `}` closing the `{` at `start`, counting nested unescaped braces."""
    depth = 0
    at = start
    while at < len(text):
        if text[at] == "\\" and at + 1 < len(text) and text[at + 1] in ESCAPABLE:
            at += 2
            continue
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return at
        at += 1
    return None


def _escaped(text: str, at: int) -> bool:
    """Whether the character at `at` was made literal by a backslash.

    Counts the run of backslashes before it, so `\\\\**` is a literal
    backslash followed by a live delimiter.
    """
    back = 0
    while at - back - 1 >= 0 and text[at - back - 1] == "\\":
        back += 1
    return back % 2 == 1


def _url_slashes(text: str, at: int) -> bool:
    """Whether the `//` at `at` is a URL's scheme separator rather than markup."""
    return at > 0 and text[at - 1] == ":"


def _star_run(text: str, at: int) -> bool:
    """Whether the `*` at `at` belongs to a run of three or more.

    `***` is how a figure legend names a p threshold, and it is the one string
    a caption in this family of journals is guaranteed to contain. Read as
    markup it is a bold opener followed by a stray star, so it reaches across
    the caption and takes the next `**` -- the panel letter of `**(b)**` -- as
    its partner, emboldening a paragraph and printing a `**`.

    A run of three or more can be given back as text with nothing lost, because
    this grammar has no reading for it: bold is exactly `**`, italic is `//`,
    and Markdown's `***bold italic***` was never spelt that way here. So the
    convention wins the run and the escape (`\\*\\*\\*`, or
    `escape_markup`) is still there for a string that needs one asterisk of a
    run to be a delimiter after all.

    Counted over the *whole* run, not forward from `at`, so the second star of
    `***` is refused as well -- otherwise the scanner emits one star and then
    opens on the two behind it.
    """
    start = at
    while start > 0 and text[start - 1] == "*" and not _escaped(text, start - 1):
        start -= 1
    end = at
    while end < len(text) and text[end] == "*":
        end += 1
    return end - start >= 3
