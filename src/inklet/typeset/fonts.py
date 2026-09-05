"""Resolving a family name to a font file, and reading its vertical metrics.

`fc-match` is the primary route because fontconfig already encodes this
machine's real font policy: generic aliases, per-family substitutions, and
which weights are actually installed. It is worth knowing that fontconfig
never fails — it substitutes — so a misspelt family silently resolves to
something else. `FontFace.family` is therefore the family you got, which is
not always the family you asked for.

The filename scan behind it is for machines with no fontconfig at all
(minimal containers, Windows). It matches on filenames rather than opening a
thousand fonts to read their name tables.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")

_FC_TIMEOUT_S = 5.0

# Nothing downstream should see a zero-height line, so a font with unusable
# vertical metrics gets the conventional 80/20 split of the em.
_FALLBACK_ASCENT_RATIO = 0.8


class FontNotFoundError(LookupError):
    """No font file could be resolved for a request."""


@dataclass(frozen=True, slots=True)
class FontFace:
    """A font file plus the vertical metrics needed to lay a line out.

    All metrics are in the font's own units; multiply by `scale(size)` to get
    millimetres. `ascent` and `descent` are both positive, measured from the
    baseline upward and downward respectively.
    """

    path: str
    family: str
    units_per_em: int
    ascent: float
    descent: float
    line_gap: float
    weight: int = 400          # OS/2 usWeightClass, as read from the file
    italic: bool = False
    index: int = 0             # face within a .ttc/.otc collection
    # Height of a capital, in font units. Not a line metric -- it is where the
    # *ink* of ordinary text stops, which is what `typeset.onpath` pivots each
    # letter about when it sets a run round a curve. Faces that omit
    # `OS/2.sCapHeight` (version 1 and earlier tables) get the conventional
    # 0.7em, which is what `render.fontembed` already falls back to.
    cap_height: float = 0.0

    def scale(self, size: float) -> float:
        """Factor converting font units to mm at the given type size (mm)."""
        return size / self.units_per_em

    def metrics(self, size: float) -> tuple[float, float, float]:
        """(ascent, descent, line_gap) in mm at the given type size (mm)."""
        k = self.scale(size)
        return self.ascent * k, self.descent * k, self.line_gap * k


@lru_cache(maxsize=128)
def find_font(family: str, weight: str = "regular", italic: bool = False) -> FontFace:
    """Resolve a family name to a usable font file.

    `family` is a generic name (`sans`, `serif`, `mono`), an installed family
    name, or a path to a font file. `weight` is a CSS-ish name (`regular`,
    `medium`, `semibold`, `bold`, ...) or a number as a string.

    Raises FontNotFoundError when the machine has nothing to offer, and
    ValueError for an unknown weight name. With fontconfig present a family
    name that does not exist resolves to a substitute rather than raising, so
    check `FontFace.family` when the exact face matters.
    """
    number = weight_number(weight)
    if _looks_like_path(family):
        return load_face(str(Path(family).expanduser()))

    located = _fc_match(family, number, italic) or _scan_match(family, number, italic)
    if located is None:
        searched = ", ".join(str(d) for d in _font_dirs()) or "no font directories exist"
        raise FontNotFoundError(
            f"no font found for family {family!r} (weight {weight!r}, "
            f"italic={italic}). fc-match is unavailable or found nothing, and "
            f"the fallback scan searched: {searched}. Install a font, or pass "
            f"an explicit path to find_font()."
        )
    return load_face(*located)


@lru_cache(maxsize=256)
def find_fallback(chars: str, weight: str = "regular",
                  italic: bool = False) -> FontFace | None:
    """A face that can draw these characters, for text the chosen font cannot.

    Fontconfig indexes every installed font by the characters it covers, which
    is the only way to answer "who has a glyph for U+8996" without opening a
    thousand files and reading their cmaps.

    `chars` is matched as a set, so pass the distinct characters that need
    covering rather than a whole paragraph. Returns None when there is no
    fontconfig and nothing to ask; note that when fontconfig *is* present it
    substitutes rather than failing, so the caller must still check that what
    came back covers what it asked for.

    The choice is deterministic *on one machine*: the characters are sorted
    before the query, so it does not depend on the order they were written in,
    and fontconfig's answer to a given pattern is fixed by the installed fonts
    and the fontconfig configuration. It is not portable -- a machine with a
    different font set will borrow a different face, and the borrowed face's
    advances differ, so the line breaks can differ with it. A figure that must
    come out identically everywhere should either name a font that covers its
    characters or ship with its text outlined (`to_svg(text="outline")`, or
    PDF, which always outlines).
    """
    wanted = "".join(sorted(set(chars)))
    if not wanted:
        return None
    located = _fc_charset_match(wanted, weight_number(weight), italic)
    return None if located is None else load_face(*located)


def _fc_charset_match(chars: str, weight: int,
                      italic: bool) -> tuple[str, int] | None:
    """Ask fontconfig for a font covering `chars`, by codepoint."""
    nearest = min(_CSS_TO_FC_WEIGHT, key=lambda css: abs(css - weight))
    charset = " ".join(f"{ord(c):x}" for c in chars)
    pattern = (f":charset={charset}:weight={_CSS_TO_FC_WEIGHT[nearest]}"
               f":slant={100 if italic else 0}")
    return _fc_query(pattern)


@lru_cache(maxsize=64)
def load_face(path: str, index: int = 0) -> FontFace:
    """Read metrics from a font file. Cached, since a figure asks repeatedly."""
    from fontTools.ttLib import TTFont, TTLibError

    try:
        font = TTFont(path, lazy=True, fontNumber=index)
    except (OSError, TTLibError) as exc:
        raise FontNotFoundError(f"cannot read font file {path!r}: {exc}") from exc

    try:
        units_per_em = font["head"].unitsPerEm
        ascent, descent, line_gap = _vertical_metrics(font, units_per_em)
        os2 = font["OS/2"] if "OS/2" in font else None
        return FontFace(
            path=str(path),
            family=font["name"].getBestFamilyName() or Path(path).stem,
            units_per_em=units_per_em,
            ascent=ascent,
            descent=descent,
            line_gap=line_gap,
            weight=os2.usWeightClass if os2 is not None else 400,
            italic=bool(font["head"].macStyle & 0b10),
            index=index,
            cap_height=(getattr(os2, "sCapHeight", 0) or 0) or 0.7 * units_per_em,
        )
    except KeyError as exc:
        raise FontNotFoundError(
            f"font file {path!r} is missing the {exc} table and cannot be measured"
        ) from exc
    finally:
        font.close()


def _vertical_metrics(font, units_per_em: int) -> tuple[float, float, float]:
    """Typo metrics when the font supplies them, hhea otherwise.

    Typo metrics are the ones the designer chose for multi-line setting; hhea
    is what Windows clips to and tends to be inflated by accent overshoot.
    Some fonts ship a zeroed OS/2, hence the check rather than blind trust.
    """
    if "OS/2" in font:
        os2 = font["OS/2"]
        if os2.sTypoAscender > 0:
            # sTypoDescender should be negative; a few fonts get the sign wrong.
            return (float(os2.sTypoAscender), float(abs(os2.sTypoDescender)),
                    float(os2.sTypoLineGap))
    if "hhea" in font:
        hhea = font["hhea"]
        if hhea.ascent > 0:
            return float(hhea.ascent), float(abs(hhea.descent)), float(hhea.lineGap)
    ascent = _FALLBACK_ASCENT_RATIO * units_per_em
    return ascent, units_per_em - ascent, 0.0


# CSS numeric weights, which is what callers think in and what OS/2 stores.
_WEIGHT_NUMBERS = {
    "thin": 100, "hairline": 100,
    "extralight": 200, "ultralight": 200,
    "light": 300,
    "regular": 400, "normal": 400, "book": 400,
    "medium": 500,
    "semibold": 600, "demibold": 600,
    "bold": 700,
    "extrabold": 800, "ultrabold": 800,
    "black": 900, "heavy": 900,
}

# Fontconfig uses its own weight scale, not the CSS one.
_CSS_TO_FC_WEIGHT = {100: 0, 200: 40, 300: 50, 400: 80, 500: 100,
                     600: 180, 700: 200, 800: 205, 900: 210}

# Longest first, so "semibold" is not read as "bold" and "ultralight" not as "light".
_WEIGHT_TOKENS = tuple(sorted(_WEIGHT_NUMBERS.items(), key=lambda kv: (-len(kv[0]), kv[0])))

_GENERIC_FAMILIES = {
    "sans": "sans-serif", "sans-serif": "sans-serif", "sansserif": "sans-serif",
    "serif": "serif",
    "mono": "monospace", "monospace": "monospace",
}

# Preference order for the no-fontconfig path, best first.
_GENERIC_FALLBACKS = {
    "sans-serif": ("dejavusans", "notosans", "liberationsans", "freesans",
                   "arial", "helvetica", "segoeui"),
    "serif": ("dejavuserif", "notoserif", "liberationserif", "freeserif",
              "timesnewroman", "georgia"),
    "monospace": ("dejavusansmono", "notosansmono", "liberationmono", "freemono",
                  "couriernew", "consolas"),
}


def weight_number(weight: str | int) -> int:
    """CSS weight number for a weight name or numeric string."""
    if isinstance(weight, int):
        return weight
    key = re.sub(r"[\s_-]+", "", weight.strip().lower())
    if key.isdigit():
        return int(key)
    try:
        return _WEIGHT_NUMBERS[key]
    except KeyError:
        known = ", ".join(sorted(_WEIGHT_NUMBERS))
        raise ValueError(
            f"unknown font weight {weight!r}; expected a number or one of: {known}"
        ) from None


def _looks_like_path(family: str) -> bool:
    return family.lower().endswith(FONT_SUFFIXES) or os.sep in family


def _fc_match(family: str, weight: int, italic: bool) -> tuple[str, int] | None:
    """Ask fontconfig. None if fc-match is missing, broken, or points nowhere."""
    nearest = min(_CSS_TO_FC_WEIGHT, key=lambda css: abs(css - weight))
    name = _GENERIC_FAMILIES.get(family.strip().lower(), family.strip())
    # ':' separates properties and '-' introduces a point size in fc syntax.
    escaped = re.sub(r"([-:,\\])", r"\\\1", name)
    pattern = f"{escaped}:weight={_CSS_TO_FC_WEIGHT[nearest]}:slant={100 if italic else 0}"

    return _fc_query(pattern)


def _fc_query(pattern: str) -> tuple[str, int] | None:
    """Run one fc-match. None if fc-match is missing, broken, or points nowhere."""
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\\t%{index}", pattern],
            capture_output=True, text=True, timeout=_FC_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    path, _, index = result.stdout.strip().partition("\t")
    if not path or not Path(path).is_file():
        return None
    return path, int(index) if index.isdigit() else 0


def _scan_match(family: str, weight: int, italic: bool) -> tuple[str, int] | None:
    """Filename-matched fallback for machines without fontconfig."""
    generic = _GENERIC_FAMILIES.get(family.strip().lower())
    wanted = _GENERIC_FALLBACKS[generic] if generic else (_normalize(family),)

    best: tuple[float, str] | None = None
    for path in _installed_fonts():
        score = _match_score(path.stem, wanted, weight, italic)
        if score is not None and (best is None or score > best[0]):
            best = (score, str(path))
    return (best[1], 0) if best else None


# A tail the style vocabulary cannot explain usually means a different family
# ("NotoSansArabic" answering a request for "NotoSans"), which is a worse
# answer than any wrong weight or slant of the right family.
_UNEXPLAINED_TAIL_PENALTY = 100.0
_SLANT_PENALTY = 50.0
_WEIGHT_PENALTY_PER_STEP = 10.0    # per 100 CSS weight units of distance

_STYLE_WORDS = tuple(sorted(
    set(_WEIGHT_NUMBERS) | {"italic", "oblique", "roman", "upright"},
    key=lambda word: (-len(word), word),
))


def _match_score(stem: str, wanted: tuple[str, ...],
                 weight: int, italic: bool) -> float | None:
    """How well a font filename answers the request; None means no match at all.

    Family agreement dominates, then slant, then closeness of weight, so a
    regular-weight file of the right family always beats a bold of the wrong one.
    """
    normalized = _normalize(stem)
    for rank, candidate in enumerate(wanted):
        if normalized.startswith(candidate):
            tail, family_score = normalized[len(candidate):], 300.0
        elif candidate in normalized:
            tail, family_score = _normalize(stem.partition("-")[2]), 100.0
        else:
            continue
        residue = _style_residue(tail)
        file_weight, file_italic = _style_of(tail)
        return (
            family_score
            - rank                                    # earlier fallbacks preferred
            - (_UNEXPLAINED_TAIL_PENALTY + len(residue) if residue else 0.0)
            - (0.0 if file_italic == italic else _SLANT_PENALTY)
            - _WEIGHT_PENALTY_PER_STEP * abs(file_weight - weight) / 100.0
        )
    return None


def _style_of(tail: str) -> tuple[int, bool]:
    """Read weight and slant out of the style part of a font filename."""
    italic = "italic" in tail or "oblique" in tail
    for token, number in _WEIGHT_TOKENS:
        if token in tail:
            return number, italic
    return 400, italic


def _style_residue(tail: str) -> str:
    """What is left of a filename tail once every style word is struck out."""
    for word in _STYLE_WORDS:
        tail = tail.replace(word, "")
    return tail


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _font_dirs() -> tuple[Path, ...]:
    """Conventional font directories that exist, user-installed ones first."""
    home = Path.home()
    candidates = (
        home / ".local" / "share" / "fonts",
        home / ".fonts",
        home / "Library" / "Fonts",
        Path("/usr/local/share/fonts"),
        Path("/usr/share/fonts"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    )
    return tuple(d for d in candidates if d.is_dir())


@lru_cache(maxsize=1)
def _installed_fonts() -> tuple[Path, ...]:
    """Every font file in those directories, in a fixed order.

    Sorted per directory rather than globally so that a user override in
    ~/.local/share/fonts keeps winning ties against /usr/share/fonts.
    """
    found: list[Path] = []
    for root in _font_dirs():
        found.extend(sorted(p for p in root.rglob("*") if p.suffix.lower() in FONT_SUFFIXES))
    return tuple(found)
