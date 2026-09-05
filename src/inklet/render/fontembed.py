"""Font subsets small enough to live inside the SVG that uses them.

Outlining makes a figure independent of the machine that opens it by throwing
the font away and keeping the ink. Embedding does it the other way round: keep
the font, but only the letters this figure actually sets, compressed and
base64'd into an `@font-face` rule in the document's own `<style>`. The text
stays text -- selectable, searchable, copyable, and shaped by the very face it
was measured against -- and a caption costs a few kilobytes once instead of
several bytes per letter forever.

The subset is by *character*, not by glyph id, on purpose. The shaper that
laid the figure out ran here; the shaper that draws it runs in the reader's
viewer, and it will look the characters up in the subset's `cmap` and apply
the subset's `GSUB` to them. `fontTools.subset` closes over layout for us --
ask for `f` and `i` and the `fi` ligature comes too -- so what arrives is the
set of glyphs the viewer can reach, which is the set it needs.

WOFF2 is the smaller wrapper and needs `brotli`; without it this emits WOFF,
whose zlib is universally available and roughly 20% larger. `WOFF2` says
which one you got.

PDF wants the same idea and none of the same details, so `subset_sfnt` is the
second half of this module: a bare TrueType file rather than a web wrapper,
cut by *glyph id* rather than by character, with the ids left where they were.
Both differences follow from `/Identity-H`, where the two-byte code in the
content stream is the glyph id itself -- there is no shaper on the other side
to look a character up, so what has to survive is the numbering the shaping
that already happened produced.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

__all__ = ["WOFF2", "FontSubset", "SfntSubset", "UnembeddableFont",
           "subset_face", "subset_sfnt", "sfnt_widths", "embeddable",
           "face_rule", "readable"]


def _have_brotli() -> bool:
    try:
        import brotli  # noqa: F401
    except ImportError:
        try:
            import brotlicffi  # noqa: F401
        except ImportError:
            return False
    return True


#: True when `fontTools` can write WOFF2 here. See the module docstring.
WOFF2 = _have_brotli()


@dataclass(frozen=True, slots=True)
class FontSubset:
    """One face cut down to the characters a figure uses."""

    data: bytes
    #: `"woff2"` or `"woff"`, whichever this machine could write.
    flavor: str
    #: Glyphs that survived, including `.notdef`. Reported, not used.
    glyphs: int
    #: Whether the face this was cut from is a sloped design (`head.macStyle`
    #: bit 1, the same bit `typeset.load_face` reads). It is the descriptor
    #: `face_rule` has to write, and it is read here because this is the one
    #: place that already has the file open.
    italic: bool = False

    @property
    def data_uri(self) -> str:
        payload = base64.b64encode(self.data).decode("ascii")
        return f"data:font/{self.flavor};base64,{payload}"


@lru_cache(maxsize=64)
def readable(path: str, index: int) -> bool:
    """Whether `fontTools` can open this face at all.

    Asked before a backend commits to embedding, because the alternative --
    naming a family whose `@font-face` rule then fails to be written -- is a
    figure with no text in it. A face that fails here falls back to being
    named the ordinary way.
    """
    from fontTools.ttLib import TTFont

    try:
        TTFont(path, lazy=True, fontNumber=index).close()
    except Exception:                                     # noqa: BLE001
        return False
    return True


def subset_face(path: str, index: int, codepoints: frozenset[int]) -> FontSubset:
    """Cut `path` down to `codepoints` and wrap it as WOFF2 (or WOFF).

    Deterministic: the subsetter's options are fixed, the codepoints are sorted
    before they reach it, and the `head` timestamps -- the one field in a font
    file that would otherwise record when this ran -- are zeroed. The same
    figure embeds the same bytes on every run and on every machine with the
    same font file.

    Raises whatever `fontTools` raises for a file it cannot read or subset;
    callers that have a fallback should catch `Exception` around it, because
    a font too broken to subset is not a reason to fail a whole render.
    """
    return _subset_face(path, index, codepoints)


@lru_cache(maxsize=32)
def _subset_face(path: str, index: int, codepoints: frozenset[int]) -> FontSubset:
    """Cached: three sheets of one figure set in one face subset it once."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.recalc_timestamp = False    # never stamp the run into the output
    options.hinting = False             # a screen-and-print webfont needs none
    options.glyph_names = False         # post format 3: names are for editors
    options.legacy_cmap = False
    options.symbol_cmap = True          # some UI faces map only into the PUA
    # DSIG signs bytes we just changed; FFTM is FontForge's build timestamp,
    # which is both useless here and the one thing in the file that is not a
    # function of the input. The subsetter warns about FFTM if left in.
    options.drop_tables += ["DSIG", "FFTM"]
    options.notdef_outline = False

    font = _open(path, index)
    # Read off the whole face before the subsetter touches it: what the
    # `@font-face` has to declare is a property of the *design*, not of the
    # cut, and this is where the file is already open.
    italic = bool(font["head"].macStyle & 0b10)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)

    head = font["head"]
    head.created = head.modified = 0
    font.flavor = "woff2" if WOFF2 else "woff"
    buffer = BytesIO()
    font.save(buffer)
    count = len(font.getGlyphOrder())
    font.close()
    return FontSubset(buffer.getvalue(), font.flavor, count, italic)


def _open(path: str, index: int):
    """The one way this module opens a face, and the reason it is a function.

    `recalcTimestamp=False` is load-bearing rather than tidy. `head.modified`
    is rewritten *at save time* from the clock unless the font says not to, so
    zeroing it after subsetting -- which is what this module did until
    2026-08-23 -- zeroes a field that is then filled in again three lines
    later. The symptom was a `text="embed"` SVG whose bytes changed between
    processes and not within one, because the subset is memoised: three bytes
    of every embedded face were the wall clock and the checksum over it.
    """
    from fontTools.ttLib import TTFont

    return TTFont(path, fontNumber=index, recalcTimestamp=False)


def face_rule(family: str, subset: FontSubset) -> str:
    """The `@font-face` rule that installs `subset` under `family`.

    `font-weight: 100 900` is not a claim that the face is variable: it says
    any requested weight is *served* by this file, which is what stops a
    viewer from synthesising a bold when the tree asks for one and the
    embedded face is already the bold.

    `font-style` is *not* written that way, because the two synthesis rules
    are not the same request. A slant can be faked convincingly and a weight
    cannot, so a viewer will shear an upright face on its own -- and there is
    one case in inklet where that is the right answer: a theme role that sets
    `font_style` after the block was shaped leaves a roman-measured line
    asking for an italic, and a sheared roman is the face those advances were
    measured in. So the descriptor states what the file *is* (`head.macStyle`
    bit 1, the bit `typeset.load_face` reads): a roman subset stays
    `normal` and keeps the shear available, and the italic file inklet embeds
    for `//markup//` or `font_style="italic"` says `italic` and takes the
    licence to shear it a second time away.

    Blink happens not to need telling -- it reads the italic bit off the file
    and refuses to synthesise over a face that already slants, which is why
    the lie cost nothing in Chrome. The descriptor is what a viewer is
    *entitled* to believe, though, and it was describing a face that does not
    exist in the document.
    """
    slant = "italic" if subset.italic else "normal"
    return ("@font-face{font-family:" + family + ";font-style:" + slant + ";"
            "font-weight:100 900;src:url(" + subset.data_uri + ")"
            f" format('{subset.flavor}')" + "}")


# -- the PDF side: a bare sfnt, cut by glyph id ----------------------------


#: Everything a PDF font descriptor asks for that is not a number this module
#: computes, so the caller does not reopen the face to find out.
@dataclass(frozen=True, slots=True)
class SfntSubset:
    """One TrueType face cut down to the glyphs a figure places, ids intact.

    `data` is a whole sfnt file, which is what `/FontFile2` wants; `widths` is
    the advance of each retained glyph in PDF glyph space (1/1000 em, already
    rounded), which is what `/W` wants and what a caller has to position
    against, since the viewer will advance by exactly these numbers and not by
    the fractional ones the shaper used.
    """

    data: bytes
    #: The six uppercase letters PDF puts in front of a subset's name.
    tag: str
    postscript_name: str
    widths: tuple[tuple[int, int], ...]
    #: /FontBBox, /Ascent, /Descent, /CapHeight, /ItalicAngle, in glyph space.
    bbox: tuple[int, int, int, int]
    ascent: int
    descent: int
    cap_height: int
    italic_angle: float
    flags: int

    @property
    def width_map(self) -> dict[int, int]:
        return dict(self.widths)


class UnembeddableFont(ValueError):
    """This face cannot be written as a `/FontFile2`, so outline it instead."""


def subset_sfnt(path: str, index: int, gids: frozenset[int]) -> SfntSubset:
    """Cut `path` down to `gids`, keeping their numbering, as a raw sfnt.

    Cutting by glyph id rather than by character is what `/Identity-H` needs:
    the content stream names glyphs directly, so the set that has to survive is
    the set the shaper actually placed, and `retain_gids` keeps each of them at
    the number it already has. That is also why no layout closure is wanted
    here -- a ligature the shaper chose is already in `gids`, and one it did
    not choose is a glyph nothing can reach.

    Deterministic in the same way `subset_face` is: fixed options, sorted ids,
    zeroed `head` timestamps. Raises `UnembeddableFont` for a CFF face, whose
    outlines are not a `/FontFile2` at all.
    """
    return _subset_sfnt(path, index, gids)


@lru_cache(maxsize=32)
def _subset_sfnt(path: str, index: int, gids: frozenset[int]) -> SfntSubset:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    font = _open(path, index)
    if "glyf" not in font:
        font.close()
        raise UnembeddableFont(
            f"{path!r} has no 'glyf' table (a CFF/OpenType face); PDF would "
            f"need a CIDFontType0 and inklet outlines it instead")

    scale = 1000.0 / font["head"].unitsPerEm
    # The advances come from the *uncut* face, because `retain_gids` pads
    # `hmtx` for the glyphs it dropped and a padded entry is a zero rather
    # than the width the face gives that glyph. Sharing the table with
    # `sfnt_widths` is also what lets a caller position against `/W` before
    # the subset it will end up in exists.
    table = sfnt_widths(path, index)
    widths = tuple(sorted((gid, table[gid]) for gid in gids if gid < len(table)))
    descriptor = _descriptor(font, scale)

    options = subset.Options()
    options.recalc_timestamp = False
    options.hinting = False
    options.glyph_names = False
    options.legacy_cmap = False
    options.symbol_cmap = True
    options.drop_tables += ["DSIG", "FFTM"]
    options.notdef_outline = False
    # The two that make this a PDF subset rather than a web one. Layout tables
    # are dead weight in a file whose glyphs are already chosen, and the ids
    # are the encoding, so they cannot be renumbered.
    options.retain_gids = True
    options.layout_features = []
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(gids=sorted(gids))
    subsetter.subset(font)

    head = font["head"]
    head.created = head.modified = 0
    font.flavor = None
    buffer = BytesIO()
    font.save(buffer)
    font.close()
    data = buffer.getvalue()
    return SfntSubset(data=data, tag=_subset_tag(data), widths=widths,
                      **descriptor)


def _descriptor(font, scale: float) -> dict:
    """The `/FontDescriptor` numbers, read off the face before it is cut."""
    from fontTools.ttLib import TTLibError

    head, post = font["head"], font["post"]
    try:
        name = font["name"].getDebugName(6) or font["name"].getBestFamilyName()
    except (KeyError, TTLibError):                        # noqa: BLE001
        name = None
    os2 = font["OS/2"] if "OS/2" in font else None
    hhea = font["hhea"] if "hhea" in font else None
    ascent = getattr(os2, "sTypoAscender", 0) or (getattr(hhea, "ascent", 0) or 0)
    descent = getattr(os2, "sTypoDescender", 0) or (getattr(hhea, "descent", 0) or 0)
    cap = getattr(os2, "sCapHeight", 0) or int(0.7 * head.unitsPerEm)
    # Symbolic, because `/Identity-H` addresses glyphs and not a named
    # encoding, which is the condition PDF attaches to the nonsymbolic bit.
    flags = 4 | (64 if head.macStyle & 0b10 else 0) | (1 if post.isFixedPitch else 0)
    return {
        "postscript_name": _ascii_name(name or "Font"),
        "bbox": (int(round(head.xMin * scale)), int(round(head.yMin * scale)),
                 int(round(head.xMax * scale)), int(round(head.yMax * scale))),
        "ascent": int(round(ascent * scale)),
        "descent": int(round(descent * scale)),
        "cap_height": int(round(cap * scale)),
        "italic_angle": float(post.italicAngle),
        "flags": flags,
    }


def _ascii_name(name: str) -> str:
    """A PostScript name: printable ASCII with none of PDF's delimiters."""
    out = "".join(c for c in name if "!" <= c <= "~" and c not in "()<>[]{}/%#")
    return out or "Font"


def _subset_tag(data: bytes) -> str:
    """Six uppercase letters distinguishing this subset from another of the
    same face. Derived from the bytes so that it is stable across runs and
    different where the subsets differ, which is the whole job of the tag."""
    import hashlib

    digest = int.from_bytes(hashlib.md5(data).digest()[:8], "big")
    letters = []
    for _ in range(6):
        digest, remainder = divmod(digest, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(letters)


@lru_cache(maxsize=16)
def sfnt_widths(path: str, index: int) -> tuple[int, ...]:
    """Every glyph's advance in PDF glyph space (1/1000 em), by glyph id.

    Rounded here, once, because the rounding is not an approximation a caller
    may repeat differently: a PDF reader advances its pen by exactly the
    integer in `/W`, so this *is* the advance, and anything positioning text
    against it has to agree to the unit.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(path, lazy=True, fontNumber=index)
    try:
        scale = 1000.0 / font["head"].unitsPerEm
        metrics = font["hmtx"].metrics
        return tuple(int(round(metrics[name][0] * scale))
                     for name in font.getGlyphOrder())
    finally:
        font.close()


@lru_cache(maxsize=64)
def embeddable(path: str, index: int) -> bool:
    """Whether this face can be a PDF `/FontFile2`.

    Asked before a backend commits to live text, for the same reason
    `readable` is asked before an `@font-face`: the alternative is discovering
    it while writing the page, when the content stream already names a font
    that will not be there. A CFF face fails here and is outlined instead.
    """
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(path, lazy=True, fontNumber=index)
    except Exception:                                     # noqa: BLE001
        return False
    try:
        return "glyf" in font and "hmtx" in font and "head" in font
    finally:
        font.close()
