"""Live text in a PDF: one Type0/CIDFontType2 per face, `/Identity-H` encoded.

The PDF backend outlines by default and should keep doing so -- geometry draws
identically anywhere and depends on nothing installed. What outlining cannot do
is be *read*: a reader's find box, a copy-paste into a caption, a text-mining
crawler and a screen reader all see a page of filled paths. This module is the
other trade, and it is a real trade rather than a strict improvement, so it is
opt-in behind `to_pdf(text="embed")`.

`/Identity-H` is what makes it fit the rest of `inklet`. The two-byte code in the
content stream *is* the glyph id, so the glyphs HarfBuzz already chose go
straight into the file and no shaping happens on the other side: the reader
paints the same glyphs at the same places as the outlined file, and the ink
does not depend on the viewer agreeing about ligatures. `render.fontembed`
cuts the face down to those ids and leaves them numbered where they were, and
a `/ToUnicode` CMap built from the shaping clusters puts the characters back
for anyone reading rather than painting.

Positioning is exact and not approximately exact. A viewer advances the pen by
the `/W` entry -- an integer thousandth of the em -- while the layout was
measured in the font's own units, so the two disagree by up to half a
thousandth per glyph and a forty-character label would end a visible fraction
of a millimetre from where the outlined one ends. Every glyph therefore
carries the `TJ` adjustment that lands the *next* one exactly where
`placed_glyphs` put it, which costs a few bytes a glyph and makes the two text
modes the same picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .fontembed import SfntSubset, embeddable, sfnt_widths, subset_sfnt
from .glyphs import PlacedGlyph

__all__ = ["FontShelf", "FontUse", "text_runs", "TextRunGroup"]

#: Codes per `beginbfchar` block. The spec's limit is 100.
_BFCHAR_BLOCK = 100

#: A glyph whose adjustment rounds below this many thousandths of the em is
#: left alone: at 7pt one thousandth is 2.5 micrometres, and the number costs
#: three bytes on every letter of the page.
_ADJUST_EPS = 0.5


@dataclass
class FontUse:
    """One face as this document uses it: a resource name and its glyphs."""

    name: str
    path: str
    index: int
    gids: set[int] = field(default_factory=set)
    #: gid -> the characters it spells, first spelling wins. A glyph reached
    #: from two different strings (rare, and always a shaping oddity) is
    #: extracted as the first, because `/ToUnicode` maps a code once.
    unicode: dict[int, str] = field(default_factory=dict)

    def note(self, glyph: PlacedGlyph) -> None:
        self.gids.add(glyph.gid)
        if glyph.chars and glyph.gid not in self.unicode:
            self.unicode[glyph.gid] = glyph.chars

    def subset(self) -> SfntSubset:
        return subset_sfnt(self.path, self.index, frozenset(self.gids))


class FontShelf:
    """The faces a document sets, in the order it first sets them.

    Shared across pages the way rasters are: three sheets in one family embed
    one subset. `use` returns None for a face that cannot be a `/FontFile2` --
    a CFF/OpenType one -- and the caller outlines that block instead, which is
    the same picture and the only part of the page that is not selectable.
    """

    def __init__(self) -> None:
        self.faces: dict[tuple[str, int], FontUse] = {}

    def use(self, path: str, index: int) -> FontUse | None:
        key = (path, index)
        got = self.faces.get(key)
        if got is None:
            if not embeddable(path, index):
                return None
            got = self.faces[key] = FontUse(f"F{len(self.faces)}", path, index)
        return got


@dataclass(frozen=True, slots=True)
class TextRunGroup:
    """Consecutive glyphs a single `BT`/`ET` can draw.

    One text object can hold any number of glyphs at one size in one face on
    one baseline in one colour; each of those changing starts another, because
    each of them lives in the text state rather than in the string.
    """

    glyphs: tuple[PlacedGlyph, ...]
    #: None when the face cannot be embedded, and these glyphs must be drawn
    #: as outlines like the rest of the file.
    font: FontUse | None

    @property
    def fill(self) -> str | None:
        return self.glyphs[0].fill


def text_runs(glyphs: list[PlacedGlyph], shelf: FontShelf) -> list[TextRunGroup]:
    """Split a block's glyphs into the text objects that will draw it."""
    groups: list[TextRunGroup] = []
    current: list[PlacedGlyph] = []
    key = None
    font: FontUse | None = None
    for glyph in glyphs:
        mine = (glyph.font_path, glyph.font_index, glyph.size, glyph.fill,
                glyph.origin.y)
        if key != mine:
            if current:
                groups.append(TextRunGroup(tuple(current), font))
            current, key = [], mine
            font = shelf.use(glyph.font_path, glyph.font_index)
        current.append(glyph)
        if font is not None:
            font.note(glyph)
    if current:
        groups.append(TextRunGroup(tuple(current), font))
    return groups


def show_text(group: TextRunGroup, n) -> list[str]:
    """The operators that draw one group, `BT` to `ET`.

    `n` formats a millimetre the way the rest of the stream does. The text
    matrix carries the y flip rather than the font size, so `Tf` states the
    size in millimetres and a `TJ` number is a thousandth of it -- the same
    arithmetic a reader does, which is the point of doing it here.
    """
    first = group.glyphs[0]
    size = first.size
    widths = sfnt_widths(first.font_path, first.font_index)
    ops = ["BT", f"/{group.font.name} {n(size)} Tf",
           f"1 0 0 -1 {n(first.origin.x)} {n(first.origin.y)} Tm"]

    parts: list[str] = []
    pending = ""
    for index, glyph in enumerate(group.glyphs):
        pending += f"{glyph.gid:04X}"
        if index + 1 == len(group.glyphs):
            break
        # Where the reader's pen will be after this glyph, against where the
        # next glyph has to start. See the module docstring.
        advance = widths[glyph.gid] if glyph.gid < len(widths) else 0
        wanted = (group.glyphs[index + 1].origin.x - glyph.origin.x) / size * 1000.0
        adjust = advance - wanted
        if abs(adjust) >= _ADJUST_EPS:
            parts.append(f"<{pending}>")
            parts.append(_number(adjust))
            pending = ""
    parts.append(f"<{pending}>")
    ops.append("[" + "".join(parts) + "] TJ")
    ops.append("ET")
    return ops


def _number(value: float) -> str:
    """A `TJ` adjustment: whole thousandths, because a reader rounds the pen to
    them anyway and the fraction is bytes nobody spends."""
    return str(int(round(value)))


def to_unicode_cmap(use: FontUse) -> bytes:
    """The `/ToUnicode` stream mapping this face's codes back to characters.

    Without it a reader has a page of glyph ids: the text is selectable and
    copies out as mojibake, which is worse than outlining, where at least
    nothing pretends to be text.
    """
    entries = [(gid, use.unicode[gid]) for gid in sorted(use.unicode)]
    blocks = []
    for start in range(0, len(entries), _BFCHAR_BLOCK):
        chunk = entries[start:start + _BFCHAR_BLOCK]
        rows = "\n".join(f"<{gid:04X}> <{text.encode('utf-16-be').hex().upper()}>"
                         for gid, text in chunk)
        blocks.append(f"{len(chunk)} beginbfchar\n{rows}\nendbfchar")
    body = "\n".join(blocks)
    return (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        f"{body}\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode("ascii")


def widths_array(subset: SfntSubset) -> str:
    """The `/W` array, runs of consecutive ids collapsed into one entry.

    `[3 [260] 40 [556 519 728]]` rather than one bracket per glyph: a figure's
    glyphs come out of the same alphabet, so the ids arrive in long runs and
    the collapsed form is roughly half the bytes.
    """
    runs: list[tuple[int, list[int]]] = []
    for gid, width in subset.widths:
        if runs and gid == runs[-1][0] + len(runs[-1][1]):
            runs[-1][1].append(width)
        else:
            runs.append((gid, [width]))
    return "[" + " ".join(f"{gid} [{' '.join(str(w) for w in ws)}]"
                          for gid, ws in runs) + "]"
