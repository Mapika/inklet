"""Named colour palettes, transcribed from their published sources.

These are standards, not suggestions: the whole point of a colour-vision-safe
palette is that everyone uses the same eight values, so the hex digits below
are copied from the primary source and must not be "improved". Case is
normalised to lowercase; the numbers are unchanged. The long tables (the
matplotlib and Crameri maps, and ColorBrewer) are generated from pinned
source files by `tools/gen_palette_data.py` into `_palette_data.py`.

Every palette carries its `source` and `license`. The collection, by kind:

- **categorical** -- Okabe-Ito; Paul Tol's bright, vibrant, muted,
  high-contrast, medium-contrast, light, pale and dark; ColorBrewer's eight
  qualitative sets; and Inklet's own designs (`inklet`, `inklet-muted`,
  `inklet-pairs`, `inklet-duo`).
- **sequential** -- viridis, cividis, inferno, plasma and magma; 21 of
  Fabio Crameri's Scientific Colour Maps (batlow, lajolla, oslo, ...); Tol's
  YlOrBr, WhOrBr, iridescent, incandescent and discrete rainbow; and
  ColorBrewer's 18 sequential schemes.
- **diverging** -- Tol's sunset, nightfall, BuRd and PRGn; Crameri's vik,
  roma, berlin and seven more; ColorBrewer's nine.
- **cyclic** -- Crameri's romaO, vikO, brocO, corkO and bamO.

A caveat worth knowing before you reach for one. Categorical CVD-safe palettes
are tuned for *area* -- bars, patches, filled regions -- against a light
background. Several of their lighter members (the yellows and sands) sit well
under WCAG's 3:1 non-text contrast floor on white paper, so they are not safe
for hairlines, arrowheads or text. `Theme.ink_color` exists for that case.

`Palette.report()` measures a palette rather than trusting its reputation:
minimum pairwise CIEDE2000 in normal vision and under simulated protanopia,
deuteranopia and tritanopia (Machado et al. 2009), the lightness each colour
keeps in greyscale, and for ramps whether lightness is monotonic or symmetric.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import combinations

from . import _palette_data as _data
from .color import (
    CVD_KINDS, ColorError, delta_e_2000, interpolate, interpolate_lab,
    interpolate_oklab, parse_color, simulate_cvd, to_hex, to_lab,
)

__all__ = [
    "Palette", "PaletteReport", "PALETTES", "KINDS", "palette", "palette_names",
    "OKABE_ITO", "TOL_BRIGHT", "TOL_MUTED", "TOL_VIBRANT", "TOL_HIGH_CONTRAST",
    "TOL_YLORBR", "TOL_SUNSET", "TOL_BURD", "MAGMA",
    "TOL_MEDIUM_CONTRAST", "TOL_LIGHT", "TOL_PALE", "TOL_DARK",
    "TOL_NIGHTFALL", "TOL_PRGN", "TOL_WHORBR", "TOL_IRIDESCENT",
    "TOL_INCANDESCENT", "TOL_RAINBOW",
    "VIRIDIS", "CIVIDIS", "INFERNO", "PLASMA",
    "INKLET", "INKLET_MUTED", "INKLET_PAIRS", "INKLET_DUO",
]

#: The four kinds of palette. "qualitative" is accepted as another spelling
#: of "categorical" everywhere a kind is taken.
KINDS: tuple[str, ...] = ("categorical", "sequential", "diverging", "cyclic")
_KIND_ALIASES = {"qualitative": "categorical"}

_INTERPOLATORS = {"srgb": interpolate, "lab": interpolate_lab,
                  "oklab": interpolate_oklab}


def _kind(kind: str) -> str:
    key = _KIND_ALIASES.get(kind, kind)
    if key not in KINDS:
        raise ColorError(f"unknown palette kind {kind!r}; expected one of {KINDS}")
    return key


@dataclass(frozen=True)
class Palette:
    """A published set of colours plus the provenance to defend it.

    `kind` is one of `KINDS`. For the ramps -- sequential, diverging,
    cyclic -- the colours are evenly spaced stops of a continuous map, and
    `ramp`, `resampled` and `inklet.ramp` interpolate between them. For
    categorical palettes the order is the published order of use: take the
    first *n* for *n* categories.
    """

    name: str
    colors: tuple[str, ...]
    kind: str = "categorical"     # categorical | sequential | diverging | cyclic
    bad: str | None = None        # what to paint where there is no data
    source: str = ""
    license: str = ""
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.colors:
            raise ColorError(f"palette {self.name!r} has no colours")
        object.__setattr__(self, "colors",
                           tuple(to_hex(parse_color(c)) for c in self.colors))
        object.__setattr__(self, "kind", _kind(self.kind))
        if self.bad is not None:
            object.__setattr__(self, "bad", to_hex(parse_color(self.bad)))

    def __len__(self) -> int:
        return len(self.colors)

    def __iter__(self):
        return iter(self.colors)

    def __getitem__(self, index: int) -> str:
        return self.colors[index]

    @property
    def is_ramp(self) -> bool:
        """True for sequential, diverging and cyclic palettes."""
        return self.kind != "categorical"

    def color(self, index: int) -> str:
        """Cycle. A ninth series reuses the first colour rather than inventing
        a ninth one that nobody checked against a dichromat."""
        return self.colors[index % len(self.colors)]

    def ramp(self, t: float, space: str = "srgb") -> str:
        """Sample the palette as a continuous ramp, t in 0..1.

        `space` is "srgb" (the default, and the historical behaviour), "lab"
        or "oklab". The dense maps are stored with enough stops that all
        three reproduce the published 256-entry table within CIEDE2000 1.
        """
        try:
            sample = _INTERPOLATORS[space]
        except KeyError:
            raise ColorError(
                f"unknown colour space {space!r}; expected one of {tuple(_INTERPOLATORS)}"
            ) from None
        return sample(self.colors, t)

    # -- variants ---------------------------------------------------------

    def reversed(self) -> "Palette":
        """The same colours in the opposite order, named with an `_r` suffix
        (reversing twice gives the original name back)."""
        name = self.name[:-2] if self.name.endswith("_r") else self.name + "_r"
        return replace(self, name=name, colors=tuple(reversed(self.colors)))

    def resampled(self, count: int, space: str = "oklab") -> "Palette":
        """`count` colours from this palette.

        A ramp is sampled evenly, ends included, through `space` (OKLab by
        default); a cyclic ramp is sampled evenly around the loop without
        repeating its start. A categorical palette gives its first `count`
        colours -- the published order is the order of use -- and refuses a
        `count` past its length rather than inventing unchecked colours.
        """
        if count < 1:
            raise ColorError(f"resampled() needs at least one colour, got {count}")
        if not self.is_ramp:
            if count > len(self.colors):
                raise ColorError(
                    f"{self.name} has {len(self.colors)} colours; cannot give {count}. "
                    f"A categorical palette is not interpolated."
                )
            colors = self.colors[:count]
        elif count == 1:
            colors = (self.ramp(0.5, space),)
        elif self.kind == "cyclic":
            colors = tuple(self.ramp(i / count, space) for i in range(count))
        else:
            colors = tuple(self.ramp(i / (count - 1), space) for i in range(count))
        return replace(self, colors=colors)

    def cvd(self, kind: str = "deuteranopia", severity: float = 1.0) -> "Palette":
        """The palette as a reader with colour vision deficiency `kind` sees it,
        simulated with Machado et al. (2009). `severity` below 1 simulates
        the anomalous trichromacies (protanomaly, deuteranomaly, tritanomaly).
        """
        colors = tuple(simulate_cvd(c, kind, method="machado", severity=severity)
                       for c in self.colors)
        return replace(self, name=f"{self.name}+{kind}", colors=colors)

    def greyscale(self) -> "Palette":
        """Each colour as the neutral grey of the same CIE L*: what a
        greyscale printout or photocopy keeps."""
        return replace(self, name=f"{self.name}+grey",
                       colors=tuple(_grey(c) for c in self.colors))

    # -- measurement ------------------------------------------------------

    def lightness(self) -> tuple[float, ...]:
        """CIE L* of each colour, 0 (black) to 100 (white)."""
        return tuple(to_lab(c)[0] for c in self.colors)

    def min_delta_e(self, cvd: str | None = None, severity: float = 1.0) -> float:
        """Smallest CIEDE2000 difference between any two colours, in normal
        vision or under the simulated deficiency `cvd`."""
        return _worst_pair(self._seen(cvd, severity))[0]

    def _seen(self, cvd: str | None, severity: float = 1.0) -> tuple[str, ...]:
        return self.colors if cvd is None else self.cvd(cvd, severity).colors

    def report(self) -> "PaletteReport":
        """Measure the palette: see `PaletteReport`."""
        return _report(self)


@dataclass(frozen=True)
class PaletteReport:
    """What a palette actually does, measured.

    `min_delta_e` is the smallest pairwise CIEDE2000 among all colours (for a
    ramp, among its stops), and `min_delta_e_cvd` the same under each
    simulated dichromacy, with `worst_pairs` naming the pair responsible.
    A difference of about 2 is just noticeable side by side; categorical
    colours a reader must match against a legend want 10 or more.

    `lightness` is each colour's CIE L*, and `min_lightness_gap` the smallest
    step between any two after sorting -- how far apart the colours stay in
    greyscale. `monotonic` (ramps) says whether L* only rises or only falls
    along the stops. For a diverging map, `symmetric` says whether its single
    lightness extreme sits at the centre (within a tenth of its length) with
    lightness running monotonically away from it on both arms, and
    `asymmetry` is the largest L* difference between mirrored stops. Published
    maps are rarely exact mirrors -- ColorBrewer's PRGn ends 11 L* apart --
    so the shape is the test and the mismatch is reported, not judged.
    """

    name: str
    kind: str
    count: int
    min_delta_e: float
    min_delta_e_cvd: dict[str, float]
    worst_pairs: dict[str, tuple[str, str]]
    lightness: tuple[float, ...]
    min_lightness_gap: float
    monotonic: bool | None = None
    symmetric: bool | None = None
    asymmetry: float | None = None

    @property
    def min_delta_e_any(self) -> float:
        """The worst of normal vision and every simulated deficiency."""
        return min(self.min_delta_e, *self.min_delta_e_cvd.values())

    def __str__(self) -> str:
        cvd = "  ".join(f"{k[:4]} {v:5.1f}" for k, v in self.min_delta_e_cvd.items())
        lines = [
            f"{self.name} ({self.kind}, {self.count} colours)",
            f"  min dE00 normal {self.min_delta_e:5.1f}  {cvd}",
            f"  L* {min(self.lightness):.0f}-{max(self.lightness):.0f}, "
            f"min greyscale gap {self.min_lightness_gap:.1f}",
        ]
        if self.monotonic is not None:
            lines.append(f"  lightness monotonic: {self.monotonic}")
        if self.symmetric is not None:
            lines.append(f"  symmetric about the centre: {self.symmetric} "
                         f"(mirrored stops within {self.asymmetry:.1f} L*)")
        return "\n".join(lines)


def _grey(color: str) -> str:
    lightness = to_lab(color)[0]
    # Neutral axis of CIELAB: a* = b* = 0 is R = G = B.
    fy = (lightness + 16) / 116
    y = fy ** 3 if fy > 6 / 29 else 3 * (6 / 29) ** 2 * (fy - 4 / 29)
    encoded = y * 12.92 if y <= 0.0031308 else 1.055 * y ** (1 / 2.4) - 0.055
    return to_hex((encoded * 255.0,) * 3)


def _worst_pair(colors) -> tuple[float, tuple[str, str]]:
    if len(colors) < 2:
        return (float("inf"), (colors[0], colors[0]))
    return min((delta_e_2000(a, b), (a, b)) for a, b in combinations(colors, 2))


def _report(p: Palette) -> PaletteReport:
    normal, pair = _worst_pair(p.colors)
    cvd, pairs = {}, {"normal": pair}
    for kind in CVD_KINDS:
        seen = p.cvd(kind).colors
        value, (a, b) = _worst_pair(seen)
        cvd[kind] = value
        pairs[kind] = (p.colors[seen.index(a)], p.colors[seen.index(b)])
    lightness = p.lightness()
    ordered = sorted(lightness)
    gap = min((b - a for a, b in zip(ordered, ordered[1:])), default=float("inf"))
    monotonic = symmetric = asymmetry = None
    if p.is_ramp and p.kind != "cyclic":
        steps = [b - a for a, b in zip(lightness, lightness[1:])]
        monotonic = all(s > 0 for s in steps) or all(s < 0 for s in steps)
    if p.kind == "diverging":
        symmetric = _symmetric(lightness)
        n = len(lightness)
        asymmetry = max((abs(lightness[i] - lightness[n - 1 - i])
                         for i in range(n // 2)), default=0.0)
    return PaletteReport(p.name, p.kind, len(p), normal, cvd, pairs, lightness,
                         gap, monotonic, symmetric, asymmetry)


def _symmetric(lightness: tuple[float, ...]) -> bool:
    """One lightness extreme near the centre, monotonic arms either side."""
    n = len(lightness)
    centre = (n - 1) / 2
    reach = max(1.0, 0.1 * n)
    for pick in (max, min):
        k = pick(range(n), key=lightness.__getitem__)
        if abs(k - centre) > reach:
            continue
        left = [b - a for a, b in zip(lightness[:k + 1], lightness[1:k + 1])]
        right = [b - a for a, b in zip(lightness[k:], lightness[k + 1:])]
        toward = 1 if pick is max else -1
        if all(d * toward > 0 for d in left) and all(d * toward < 0 for d in right):
            return True
    return False


# --- Okabe-Ito ----------------------------------------------------------------

_NO_LICENSE = ("no licence stated; colour values published by the authors "
               "as a recommendation for general use")


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
    license=_NO_LICENSE,
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
_TOL_LICENSE = ("no licence stated; values published by the author for general "
                "use (his reference implementation tol_colors is BSD-3-Clause)")

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
    license=_TOL_LICENSE,
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
    license=_TOL_LICENSE,
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
    license=_TOL_LICENSE,
)

TOL_HIGH_CONTRAST = Palette(
    name="tol-high-contrast",
    colors=("#004488", "#ddaa33", "#bb5566"),   # blue, yellow, red
    # Designed to be framed by white and black; the note gives it no grey.
    source=_TOL,
    license=_TOL_LICENSE,
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
    license=_TOL_LICENSE,
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
    license=_TOL_LICENSE,
)

TOL_BURD = Palette(
    name="tol-burd",
    colors=(
        "#2166ac", "#4393c3", "#92c5de", "#d1e5f0", "#f7f7f7",
        "#fddbc7", "#f4a582", "#d6604d", "#b2182b",
    ),
    kind="diverging",
    # ColorBrewer RdBu reversed, so that low is blue and high is red. The
    # white centre is the one colour a reader takes to mean "no change".
    bad="#ffee99",
    source=_TOL,
    license=_TOL_LICENSE,
)

# The rest of Tol's schemes. Where the live page (qualitative section dated
# 16 August 2026) and issue 3.2 disagree -- pale and dark were redesigned,
# pale from six colours to seven and dark from six to eleven -- the live page
# is transcribed, because it is the author's current recommendation.
# Medium-contrast, light and the maps are the same in both.
_TOL_WEB = ("Paul Tol, Colour Schemes (web page, qualitative schemes dated "
            "16 August 2026), https://sronpersonalpages.nl/~pault/")

TOL_MEDIUM_CONTRAST = Palette(
    name="tol-medium-contrast",
    colors=(
        "#6699cc",   # light blue
        "#004488",   # dark blue
        "#eecc66",   # light yellow
        "#994455",   # dark red
        "#997700",   # dark yellow
        "#ee99aa",   # light red
    ),
    # Three light/dark pairs that also separate in greyscale.
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_LIGHT = Palette(
    name="tol-light",
    colors=(
        "#77aadd",   # light blue
        "#ee8866",   # orange
        "#eedd88",   # light yellow
        "#ffaabb",   # pink
        "#99ddff",   # light cyan
        "#44bb99",   # mint
        "#bbcc33",   # pear
        "#aaaa00",   # olive
        "#dddddd",   # pale grey -- a member, as in `bright`
    ),
    # For filled cells carrying black labels; too pale for lines on white.
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_PALE = Palette(
    name="tol-pale",
    colors=("#aaccee", "#cceeff", "#bbddbb", "#eeeebb", "#ffbbcc", "#eebbdd",
            "#dddddd"),
    # Backgrounds for black text; "pick pale purple last". Deliberately not
    # distinct from one another -- this is a highlighter, not a key.
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_DARK = Palette(
    name="tol-dark",
    colors=(
        "#4477bb",   # blue
        "#cc4466",   # red
        "#228833",   # green
        "#2255aa",   # sapphire
        "#993366",   # maroon
        "#006644",   # pine
        "#117788",   # teal
        "#882288",   # purple
        "#bb4488",   # magenta
        "#775500",   # brown
        "#444444",   # grey
    ),
    # Text and lines on white: every colour clears 4.5:1 against white, at
    # some cost in distinctness.
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_NIGHTFALL = Palette(
    name="tol-nightfall",
    colors=(
        "#125a56", "#00767b", "#238f9d", "#42a7c6", "#60bce9", "#9dccef",
        "#c6dbed", "#dee6e7", "#eceada", "#f0e6b2", "#f9d576", "#ffb954",
        "#fd9a44", "#f57634", "#e94c1f", "#d11807", "#a01813",
    ),
    kind="diverging",
    # Inspired by ColorBrewer PuBuGn and YlOrRd. Interpolate, or use every
    # second colour when discrete.
    bad="#ffffff",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_PRGN = Palette(
    name="tol-prgn",
    colors=(
        "#762a83", "#9970ab", "#c2a5cf", "#e7d4e8", "#f7f7f7",
        "#d9f0d3", "#acd39e", "#5aae61", "#1b7837",
    ),
    kind="diverging",
    # ColorBrewer PRGn with the green a6dba0 shifted to acd39e for print.
    bad="#ffee99",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_WHORBR = Palette(
    name="tol-whorbr",
    colors=(
        "#ffffff", "#fff7bc", "#fee391", "#fec44f", "#fb9a29",
        "#ec7014", "#cc4c02", "#993404", "#662506",
    ),
    kind="sequential",
    # YlOrBr with the palest yellow set to white, for density histograms.
    bad="#888888",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_IRIDESCENT = Palette(
    name="tol-iridescent",
    colors=(
        "#fefbe9", "#fcf7d5", "#f5f3c1", "#eaf0b5", "#ddecbf", "#d0e7ca",
        "#c2e3d2", "#b5ddd8", "#a8d8dc", "#9bd2e1", "#8dcbe4", "#81c4e7",
        "#7bbce7", "#7eb2e4", "#88a5dd", "#9398d2", "#9b8ac4", "#9d7db2",
        "#9a709e", "#906388", "#805770", "#684957", "#46353a",
    ),
    kind="sequential",
    # Linearly varying luminance: survives monochrome printing.
    bad="#999999",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_INCANDESCENT = Palette(
    name="tol-incandescent",
    colors=(
        "#ceffff", "#c6f7d6", "#a2f49b", "#bbe453", "#d5ce04", "#e7b503",
        "#f19903", "#f6790b", "#f94902", "#e40515", "#a80003",
    ),
    kind="sequential",
    # Linear luminance, bright; Tol notes it is not print-friendly and that
    # the pale cyan is almost white to a protanope.
    bad="#888888",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
)

TOL_RAINBOW = Palette(
    name="tol-rainbow",
    colors=(
        "#d1bbd7", "#ae76a3", "#882e72", "#1965b0", "#5289c7", "#7bafde",
        "#4eb265", "#90c987", "#cae0ab", "#f7f056", "#f6c141", "#f1932d",
        "#e8601c", "#dc050c",
    ),
    kind="sequential",
    # The 14-colour discrete rainbow: colours 3, 6, 9, 10, 12, 14, 15, 16,
    # 17, 18, 20, 22, 24 and 26 of Tol's 29. "The colours have to be used as
    # given: do not interpolate." Ordered by hue, not lightness.
    bad="#777777",
    source=_TOL_WEB,
    license=_TOL_LICENSE,
    notes="discrete: use the colours as given; do not interpolate",
)


# --- matplotlib's perceptually uniform maps ----------------------------------
#
# Stefan van der Walt and Nathaniel Smith's viridis, inferno, plasma and magma
# (with Eric Firing for viridis), designed in CAM02-UCS so lightness changes at
# a steady perceived rate; CC0. Cividis is Nunez, Anderton & Renslow (2018),
# "Optimizing colormaps with consideration for color vision deficiency",
# PLoS ONE 13(7): e0199239, built to look nearly the same to a deuteranope,
# under Battelle's BSD-style licence (see THIRD_PARTY_NOTICES.md). Values are
# matplotlib 3.9.2's `_cm_listed.py` tables; see `_palette_data.py` for the
# subset kept and its reproduction error.
_MPL_URL = "https://github.com/matplotlib/matplotlib/blob/v3.9.2/lib/matplotlib/_cm_listed.py"
_MPL_SOURCE = {
    "viridis": ("Smith, van der Walt & Firing, viridis; " + _MPL_URL, "CC0-1.0"),
    "inferno": ("Smith & van der Walt, inferno; " + _MPL_URL, "CC0-1.0"),
    "plasma": ("Smith & van der Walt, plasma; " + _MPL_URL, "CC0-1.0"),
    "magma": ("Smith & van der Walt, magma; " + _MPL_URL, "CC0-1.0"),
    "cividis": ("Nunez, Anderton & Renslow (2018), PLoS ONE 13(7) e0199239, "
                "doi:10.1371/journal.pone.0199239; " + _MPL_URL,
                "BSD-style (Copyright 2017 Battelle Memorial Institute)"),
}


def _generated(table, name, source, license, bad=None, notes=""):
    kind, colors = table[name]
    return Palette(name=name, colors=colors, kind=kind, bad=bad, source=source,
                   license=license, notes=notes)


VIRIDIS = _generated(_data.MATPLOTLIB, "viridis", *_MPL_SOURCE["viridis"])
CIVIDIS = _generated(_data.MATPLOTLIB, "cividis", *_MPL_SOURCE["cividis"])
INFERNO = _generated(_data.MATPLOTLIB, "inferno", *_MPL_SOURCE["inferno"])
PLASMA = _generated(_data.MATPLOTLIB, "plasma", *_MPL_SOURCE["plasma"])
# The bad-data grey is Inklet's choice, kept from before the dense stops.
MAGMA = _generated(_data.MATPLOTLIB, "magma", *_MPL_SOURCE["magma"], bad="#bfbfbf")


# --- Crameri's Scientific Colour Maps -----------------------------------------
#
# Fabio Crameri, Scientific colour maps, version 8.0 (2023),
# doi:10.5281/zenodo.8035877, MIT licence; see Crameri, Shephard & Heron
# (2020), "The misuse of colour in science communication", Nature
# Communications 11, 5444. Perceptually uniform, readable under colour vision
# deficiency and in greyscale (except the cyclic maps, whose ends meet).
# Values from the 256-entry tables shipped in cmcrameri 1.10, which packages
# version 8.0. Names are lowercased: `batlowK` is "batlowk".
_CRAMERI_SOURCE = ("Fabio Crameri, Scientific colour maps 8.0, "
                   "doi:10.5281/zenodo.8035877")
_CRAMERI_LICENSE = "MIT (Copyright (c) 2020 Fabio Crameri)"

_CRAMERI = tuple(
    _generated(_data.CRAMERI, name, _CRAMERI_SOURCE, _CRAMERI_LICENSE)
    for name in _data.CRAMERI
)


# --- ColorBrewer --------------------------------------------------------------
#
# Cynthia Brewer, Mark Harrower and The Pennsylvania State University,
# ColorBrewer 2.0, https://colorbrewer2.org, Apache License 2.0. The largest
# class of each scheme, from the axismaps/colorbrewer export at commit
# 7d135fc. Names are ColorBrewer's own, lowercased: "set2", "rdbu", "ylgnbu".
# Brewer's sequential and diverging classes are hand-tuned discrete steps
# rather than samples of one smooth curve; interpolating them is common and
# works, but the 9- and 11-step values are the ones that were checked.
_BREWER_SOURCE = ("Brewer, Harrower & The Pennsylvania State University, "
                  "ColorBrewer 2.0, https://colorbrewer2.org")
_BREWER_LICENSE = "Apache-2.0"

_BREWER = tuple(
    _generated(_data.BREWER, name, _BREWER_SOURCE, _BREWER_LICENSE)
    for name in _data.BREWER
)



# --- Inklet's own -------------------------------------------------------------
#
# Designed for this library in OKLCH and measured with `Palette.report()`;
# the thresholds each one is held to are asserted in tests/test_palettes.py.
_INKLET_SOURCE = "Inklet, designed in OKLCH; see docs/palettes.md"
_INKLET_LICENSE = "MIT (Inklet)"

# Eight hues placed by simulated annealing inside hand-chosen OKLCH boxes,
# maximising the smallest CIEDE2000 distance under normal vision and under
# deuteranopia, protanopia and tritanopia (Machado 2009 and Viénot 1999, the
# worse of the two), while keeping every pair at least 5 L* apart in grey.
# Order puts the strongest contrasts first, so the first 2-4 colours of a
# short series are the most separable.
#
#   colour   OKLCH (L, C, h)        L*
#   cobalt   0.461 0.132 256.2      37
#   amber    0.722 0.135  64.1      67
#   teal     0.558 0.081 164.8      50
#   brick    0.429 0.159  30.8      32
#   sky      0.793 0.075 234.4      76
#   plum     0.349 0.091 335.7      23
#   butter   0.920 0.137  99.1      91
#   rose     0.629 0.079 348.2      56
#
# min ΔE00: normal 25.9; deutan 12.4, protan 17.6, tritan 12.4 (worst
# method); greyscale gap 5.5 L*. Okabe-Ito for comparison: 21.7; 11.5,
# 12.3, 0.6 (Viénot tritan); 0.8 L*.
INKLET = Palette(
    name="inklet",
    colors=("#1d57a0", "#df913e", "#418368", "#93190a",
            "#8bc4e5", "#56254c", "#fbe673", "#ad7591"),
    source=_INKLET_SOURCE,
    license=_INKLET_LICENSE,
    notes="Eight colours, separable under all three dichromacies and in greyscale.",
)
# The same recipe at journal chroma (C 0.05-0.10): slate, clay, sage, rust,
# straw, dusty plum, mist.
#   slate 0.501 0.090 255.3 | clay 0.676 0.099 57.8 | sage 0.603 0.049 168.9
#   rust  0.456 0.101  28.1 | straw 0.860 0.088 94.9 | plum 0.379 0.071 318.8
#   mist  0.796 0.063 224.0
# min ΔE00: normal 23.5; deutan 13.4, protan 13.9, tritan 12.9; grey 6.5 L*.
INKLET_MUTED = Palette(
    name="inklet-muted",
    colors=("#3f6596", "#c58757", "#648b7c", "#863e36",
            "#e3d18e", "#52355a", "#90c6db"),
    source=_INKLET_SOURCE,
    license=_INKLET_LICENSE,
    notes="Seven low-chroma colours for print journals.",
)
# Six hues, each as a dark (L 0.44-0.54) and a light (L 0.80-0.88, C <= 0.076)
# member, for grouped data such as control/treated within a condition.
#   blue   0.446 0.111 261.2 / 0.799 0.050 248.5
#   brown  0.518 0.095  51.0 / 0.801 0.055  63.2
#   green  0.543 0.113 158.3 / 0.880 0.057 167.7
#   red    0.439 0.130  22.0 / 0.857 0.076  21.8
#   violet 0.537 0.116 301.3 / 0.869 0.075 305.8
#   olive  0.441 0.091  99.6 / 0.879 0.076 100.3
# min ΔE00: normal 15.1; deutan 6.0, protan 5.6, tritan 5.8. Twelve colours
# in pairs cannot stay far apart under CVD (ColorBrewer's paired: 1.3 protan);
# lean on the pairing, not on hue, to carry meaning.
INKLET_PAIRS = Palette(
    name="inklet-pairs",
    colors=("#2f5291", "#a5c1dd", "#935732", "#d8b79a", "#228356", "#b4e4d0",
            "#8c2c30", "#febdba", "#7a5ca6", "#e0c8fc", "#5f5300", "#e2d99f"),
    source=_INKLET_SOURCE,
    license=_INKLET_LICENSE,
    notes="Six dark/light pairs; colours 2k and 2k+1 share a hue.",
)
# Two conditions (or sexes) and a neutral reference: blue L 0.46, orange
# L 0.74, grey L 0.62 with no chroma. Blue/orange is the one hue pair every
# dichromat keeps apart; the lightness step keeps it apart in greyscale too.
# min ΔE00: normal 27.8; deutan 27.7, protan 24.1, tritan 25.0; grey 12.7 L*.
INKLET_DUO = Palette(
    name="inklet-duo",
    colors=("#24569f", "#ec9247", "#868686"),
    source=_INKLET_SOURCE,
    license=_INKLET_LICENSE,
    notes="Condition A, condition B, reference.",
)


PALETTES: dict[str, Palette] = {
    p.name: p for p in (
        OKABE_ITO, TOL_BRIGHT, TOL_MUTED, TOL_VIBRANT, TOL_HIGH_CONTRAST,
        TOL_MEDIUM_CONTRAST, TOL_LIGHT, TOL_PALE, TOL_DARK,
        TOL_YLORBR, TOL_WHORBR, TOL_IRIDESCENT, TOL_INCANDESCENT, TOL_RAINBOW,
        TOL_SUNSET, TOL_NIGHTFALL, TOL_BURD, TOL_PRGN,
        VIRIDIS, CIVIDIS, INFERNO, PLASMA, MAGMA,
        *_CRAMERI, *_BREWER,
        INKLET, INKLET_MUTED, INKLET_PAIRS, INKLET_DUO,
    )
}


def palette(name: "str | Palette") -> Palette:
    """A palette by name, case- and whitespace-insensitive.

    A trailing `_r` gives the reversed palette, as in matplotlib:
    `palette("viridis_r")` runs yellow to purple. A `Palette` passes through.
    """
    if isinstance(name, Palette):
        return name
    key = name.strip().lower()
    reverse = key.endswith("_r") and key[:-2] in PALETTES
    try:
        found = PALETTES[key[:-2] if reverse else key]
    except KeyError:
        raise KeyError(
            f"unknown palette {name!r}; see palette_names() for the "
            f"{len(PALETTES)} known palettes"
        ) from None
    return found.reversed() if reverse else found


def palette_names(kind: str | None = None) -> tuple[str, ...]:
    """Palette names, sorted so anything that prints or iterates them stays
    deterministic. `kind` keeps one kind: "categorical" (or "qualitative"),
    "sequential", "diverging" or "cyclic"."""
    if kind is None:
        return tuple(sorted(PALETTES))
    wanted = _kind(kind)
    return tuple(sorted(n for n, p in PALETTES.items() if p.kind == wanted))
