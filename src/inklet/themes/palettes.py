"""Named colour palettes, transcribed from their published sources.

These are standards, not suggestions: the whole point of a colour-vision-safe
palette is that everyone uses the same eight values, so the hex digits below
are copied from the primary source and must not be "improved". Case is
normalised to lowercase; the numbers are unchanged.

A caveat worth knowing before you reach for one. Qualitative CVD-safe palettes
are tuned for *area* -- bars, patches, filled regions -- against a light
background. Several of their lighter members (the yellows and sands) sit well
under WCAG's 3:1 non-text contrast floor on white paper, so they are not safe
for hairlines, arrowheads or text. `Theme.ink_color` exists for that case.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import interpolate

__all__ = [
    "Palette", "PALETTES", "palette", "palette_names",
    "OKABE_ITO", "TOL_BRIGHT", "TOL_MUTED", "TOL_VIBRANT", "TOL_HIGH_CONTRAST",
    "TOL_YLORBR", "TOL_SUNSET",
]


@dataclass(frozen=True)
class Palette:
    """A published set of colours plus the provenance to defend it."""

    name: str
    colors: tuple[str, ...]
    kind: str = "qualitative"     # qualitative | sequential | diverging
    bad: str | None = None        # what to paint where there is no data
    source: str = ""

    def __len__(self) -> int:
        return len(self.colors)

    def __iter__(self):
        return iter(self.colors)

    def __getitem__(self, index: int) -> str:
        return self.colors[index]

    def color(self, index: int) -> str:
        """Cycle. A ninth series reuses the first colour rather than inventing
        a ninth one that nobody checked against a dichromat."""
        return self.colors[index % len(self.colors)]

    def ramp(self, t: float) -> str:
        """Sample the palette as a continuous ramp, t in 0..1."""
        return interpolate(self.colors, t)


# Masataka Okabe & Kei Ito, "Color Universal Design (CUD): How to make figures
# and presentations that are friendly to colorblind people", 20 Nov 2002,
# revised 24 Sep 2008. https://jfly.uni-koeln.de/color/ -- figure 16, which
# prints the 0-255 RGB triples this table was transcribed from. ("Vermillion"
# with two Ls is the source's own spelling.)
#
# R >= 4.0 ships the same eight, in this order, as
# palette.colors(palette = "Okabe-Ito") -- but appends a ninth, gray #999999,
# which is R's addition and not part of the checked set. Only the eight below
# have been through the CUD validation.
OKABE_ITO = Palette(
    name="okabe-ito",
    colors=(
        "#000000",   # black
        "#e69f00",   # orange
        "#56b4e9",   # sky blue
        "#009e73",   # bluish green
        "#f0e442",   # yellow
        "#0072b2",   # blue
        "#d55e00",   # vermillion
        "#cc79a7",   # reddish purple
    ),
    source="Okabe & Ito, Color Universal Design, https://jfly.uni-koeln.de/color/",
)

# Paul Tol, "Colour Schemes", SRON technical note SRON/EPS/TN/09-002, issue
# 3.2, 18 August 2021.
# https://sronpersonalpages.nl/~pault/data/colourschemes.pdf
# (The old personal.sron.nl host was retired on 31 March 2025 and no longer
# serves a valid certificate; the live HTML page has since moved past issue
# 3.2, but every value below is byte-identical in both.)
#
# The note's *figures* order each scheme by hue, but section 2 gives a separate
# recommended sequence -- take the first N colours for N categories. That
# sequence, not the hue order, is what is transcribed here.
_TOL = ("Paul Tol, Colour Schemes, SRON/EPS/TN/09-002 issue 3.2, "
        "https://sronpersonalpages.nl/~pault/data/colourschemes.pdf")

TOL_BRIGHT = Palette(
    name="tol-bright",
    colors=(
        "#4477aa",   # blue
        "#ee6677",   # red
        "#228833",   # green
        "#ccbb44",   # yellow
        "#66ccee",   # cyan
        "#aa3377",   # purple
        "#bbbbbb",   # grey -- an ordinary 7th member here, not a bad-data colour
    ),
    source=_TOL,
)

TOL_MUTED = Palette(
    name="tol-muted",
    colors=(
        "#cc6677",   # rose
        "#332288",   # indigo
        "#ddcc77",   # sand
        "#117733",   # green
        "#88ccee",   # cyan
        "#882255",   # wine
        "#44aa99",   # teal
        "#999933",   # olive
        "#aa4499",   # purple
    ),
    # The only qualitative scheme Tol gives an explicit bad-data colour for:
    # "pale grey is meant for bad data in maps".
    bad="#dddddd",
    source=_TOL,
)

TOL_VIBRANT = Palette(
    name="tol-vibrant",
    colors=(
        "#ee7733",   # orange
        "#0077bb",   # blue
        "#33bbee",   # cyan
        "#ee3377",   # magenta
        "#cc3311",   # red
        "#009988",   # teal
        "#bbbbbb",   # grey -- an ordinary 7th member, as in `bright`
    ),
    source=_TOL,
)

TOL_HIGH_CONTRAST = Palette(
    name="tol-high-contrast",
    colors=("#004488", "#ddaa33", "#bb5566"),   # blue, yellow, red
    # Designed to be framed by white and black; the note gives it no grey.
    source=_TOL,
)

TOL_YLORBR = Palette(
    name="tol-ylorbr",
    colors=(
        "#ffffe5", "#fff7bc", "#fee391", "#fec44f", "#fb9a29",
        "#ec7014", "#cc4c02", "#993404", "#662506",
    ),
    kind="sequential",
    # ColorBrewer YlOrBr with the orange shifted #fe9929 -> #fb9a29 for print.
    bad="#888888",
    source=_TOL,
)

TOL_SUNSET = Palette(
    name="tol-sunset",
    colors=(
        "#364b9a", "#4a7bb7", "#6ea6cd", "#98cae1", "#c2e4ef", "#eaeccc",
        "#feda8b", "#fdb366", "#f67e4b", "#dd3d2d", "#a50026",
    ),
    kind="diverging",
    # Related to ColorBrewer RdYlBu, darkened in the centre and made symmetric.
    bad="#ffffff",
    source=_TOL,
)

PALETTES: dict[str, Palette] = {
    p.name: p for p in (
        OKABE_ITO, TOL_BRIGHT, TOL_MUTED, TOL_VIBRANT, TOL_HIGH_CONTRAST,
        TOL_YLORBR, TOL_SUNSET,
    )
}


def palette(name: str) -> Palette:
    try:
        return PALETTES[name.strip().lower()]
    except KeyError:
        raise KeyError(
            f"unknown palette {name!r}; known palettes are {palette_names()}"
        ) from None


def palette_names() -> tuple[str, ...]:
    """Sorted, so anything that prints or iterates these stays deterministic."""
    return tuple(sorted(PALETTES))
