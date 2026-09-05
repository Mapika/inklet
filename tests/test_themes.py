"""Tests for the token layer.

Two of these are not really unit tests but standing measurements: the contrast
table and the CVD separation table record what the shipped palettes actually
do. They are written to fail if a number moves, in either direction -- a colour
that quietly starts passing is as much a change as one that starts failing.
"""

from __future__ import annotations

import pytest

from inklet.core.style import Style
from inklet.core.units import to_pt
from inklet.themes import (
    GAP_NAMES, HAIRLINE_FLOOR, OKABE_ITO, PALETTES, ROLES, THEMES, TOL_BRIGHT,
    TOL_MUTED, TOL_SUNSET, TOL_VIBRANT, TOL_YLORBR, ColorError, Theme, ThemeError,
    contrast_ratio, darken, delta_e, interpolate, lighten, mix, palette,
    palette_names, parse_color, readable, relative_luminance, simulate_cvd,
    theme, theme_names, to_hex, to_lab,
)

import math


def hue_of(color: str) -> float | None:
    """The LCh hue angle in degrees, or None for something with no hue."""
    _, a, b = to_lab(color)
    if math.hypot(a, b) < 1e-6:
        return None
    return math.degrees(math.atan2(b, a))


def chroma_of(color: str) -> float:
    _, a, b = to_lab(color)
    return math.hypot(a, b)

ALL_THEMES = [THEMES[name] for name in theme_names()]

# The roles the module documents as its minimum contract. `ROLES` may be a
# superset; these eight are what `inklet.figure.apply_theme` dispatches on and so
# must never disappear.
DOCUMENTED_ROLES = (
    "box", "text", "label", "link", "frame", "panel-title", "emphasis", "muted",
)


# --- roles -------------------------------------------------------------------

@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
@pytest.mark.parametrize("role", ROLES)
def test_every_theme_covers_every_role(theme_obj: Theme, role: str) -> None:
    style = theme_obj.style_for(role)
    assert isinstance(style, Style)
    assert not style.is_empty, f"{theme_obj.name}/{role} set nothing"


@pytest.mark.parametrize("role", DOCUMENTED_ROLES)
def test_documented_roles_are_shipped(role: str) -> None:
    assert role in ROLES


def test_unknown_role_raises() -> None:
    with pytest.raises(ThemeError, match="unknown role"):
        theme().style_for("nonesuch")


def test_roles_leave_unrelated_fields_none_so_inheritance_works() -> None:
    """`emphasis` must be droppable on any subtree without resizing it."""
    emphasis = theme().style_for("emphasis")
    assert emphasis.font_size is None
    assert emphasis.fill is None
    assert emphasis.corner_radius is None

    body = theme().style_for("text")
    combined = emphasis.over(body)
    assert combined.font_size == body.font_size      # inherited
    assert combined.text_fill == theme().accent      # overridden
    assert combined.font_weight == "bold"


def test_unfilled_roles_say_none_rather_than_inheriting_a_fill() -> None:
    """A link routed over a filled box must not pick that fill up."""
    for role in ("link", "frame", "grid", "root"):
        assert theme().style_for(role).fill == "none"


def test_shape_roles_carry_no_type_and_type_roles_carry_no_stroke() -> None:
    box = theme().style_for("box")
    assert box.font_family is None and box.font_size is None
    for role in ("text", "label", "panel-title", "code"):
        style = theme().style_for(role)
        assert style.stroke is None and style.stroke_width is None


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_role_colours_all_parse(theme_obj: Theme) -> None:
    for role in ROLES:
        style = theme_obj.style_for(role)
        for value in (style.fill, style.stroke, style.text_fill):
            if value is not None and value != "none":
                parse_color(value)


# --- contrast ----------------------------------------------------------------

@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_ink_on_paper_clears_wcag_aaa(theme_obj: Theme) -> None:
    assert contrast_ratio(theme_obj.ink, theme_obj.paper) >= 7.0


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_muted_stays_readable_as_body_text(theme_obj: Theme) -> None:
    """Muted is secondary text, not decoration; WCAG AA is the floor."""
    assert contrast_ratio(theme_obj.muted, theme_obj.paper) >= 4.5


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_accent_clears_the_non_text_floor(theme_obj: Theme) -> None:
    assert contrast_ratio(theme_obj.accent, theme_obj.paper) >= 3.0


# FINDING, not a workaround. Every shipped palette is a published CVD-safe set
# designed for *area* fills; several of their lighter members fall under WCAG's
# 3:1 non-text floor on white paper and must not be used for strokes or text.
# The palettes are shipped byte-exact anyway -- editing a standard to make a
# test pass would be the actual bug -- and `Theme.ink_color` is the supported
# way to get a line-safe version. Measured ratios, to 2dp:
KNOWN_LOW_CONTRAST_ON_PAPER = {
    "nature": {"#e69f00": 2.25, "#56b4e9": 2.31, "#f0e442": 1.32},
    "slides": {"#ccbb44": 1.95, "#66ccee": 1.84, "#bbbbbb": 1.92},
    "notebook": {"#ddcc77": 1.58, "#88ccee": 1.72, "#44aa99": 2.74, "#999933": 2.94},
}


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_palette_contrast_on_paper(theme_obj: Theme) -> None:
    expected = KNOWN_LOW_CONTRAST_ON_PAPER[theme_obj.name]
    failing = {
        color: round(contrast_ratio(color, theme_obj.paper), 2)
        for color in theme_obj.palette
        if contrast_ratio(color, theme_obj.paper) < 3.0
    }
    assert failing == expected, (
        f"{theme_obj.name}: the set of palette colours below 3:1 on paper "
        f"changed. Expected {expected}, measured {failing}."
    )


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_ink_color_lifts_every_palette_entry_over_the_floor(theme_obj: Theme) -> None:
    for index in range(len(theme_obj.palette)):
        lifted = theme_obj.ink_color(index)
        assert contrast_ratio(lifted, theme_obj.paper) >= 3.0, (
            f"{theme_obj.name} series {index} -> {lifted}"
        )


def test_ink_color_leaves_already_safe_colours_untouched() -> None:
    nature = theme("nature")
    assert nature.ink_color(5) == nature.color(5) == "#0072b2"


def test_ink_color_honours_a_stricter_ratio() -> None:
    nature = theme("nature")
    assert contrast_ratio(nature.ink_color(1, min_ratio=7.0), nature.paper) >= 7.0


# --- text_color: the darkest same-hue colour that can carry type -------------


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_text_color_clears_the_type_floor_for_every_series(theme_obj: Theme) -> None:
    for index in range(len(theme_obj.palette)):
        readable_ = theme_obj.text_color(index)
        assert contrast_ratio(readable_, theme_obj.paper) >= 4.5, (
            f"{theme_obj.name} series {index} -> {readable_}"
        )


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_text_color_holds_the_hue_it_was_given(theme_obj: Theme) -> None:
    """The point of it. `ink_color` blends towards ink and every series drifts
    towards the same grey; this walks L* with a* and b* in proportion, so the
    hue angle survives -- a reader still matches the word to the line."""
    for index in range(len(theme_obj.palette)):
        before = hue_of(theme_obj.color(index))
        after = hue_of(theme_obj.text_color(index))
        if before is None or after is None:      # a grey has no hue to keep
            continue
        drift = abs((after - before + 180.0) % 360.0 - 180.0)
        assert drift <= 5.0, (
            f"{theme_obj.name} series {index}: hue moved {drift:.1f} degrees"
        )


def test_text_color_is_darker_and_never_lighter_on_a_light_paper() -> None:
    nature = theme("nature")
    for index in range(len(nature.palette)):
        assert (relative_luminance(nature.text_color(index))
                <= relative_luminance(nature.color(index)) + 1e-9)


def test_text_color_leaves_a_colour_that_already_passes_exactly_alone() -> None:
    nature = theme("nature")
    assert nature.text_color(5) == nature.color(5) == "#0072b2"


def test_text_color_beats_ink_color_at_keeping_the_hue() -> None:
    """The measurement that says why both exist. Okabe-Ito's yellow at 4.5:1."""
    nature = theme("nature")
    yellow = nature.color(4)
    blended = nature.ink_color(4, min_ratio=4.5)
    held = nature.text_color(4)
    assert contrast_ratio(blended, nature.paper) >= 4.5
    assert contrast_ratio(held, nature.paper) >= 4.5
    assert chroma_of(held) > chroma_of(blended)


def test_text_color_honours_a_stricter_ratio() -> None:
    nature = theme("nature")
    assert contrast_ratio(nature.text_color(1, min_ratio=7.0),
                          nature.paper) >= 7.0


def test_text_color_is_deterministic() -> None:
    nature = theme("nature")
    assert [nature.text_color(i) for i in range(8)] == [
        nature.text_color(i) for i in range(8)]


def test_readable_lightens_when_the_background_is_dark() -> None:
    """The same search, run the other way: on a dark ground the answer is
    lighter than what it was handed, not darker."""
    lifted = readable("#0072b2", "#101010")
    assert contrast_ratio(lifted, "#101010") >= 4.5
    assert relative_luminance(lifted) > relative_luminance("#0072b2")


def test_readable_falls_back_to_black_or_white_when_the_hue_cannot_get_there() -> None:
    """21:1 is only black on white; there is no hue that reaches it."""
    assert readable("#0072b2", "#ffffff", min_ratio=21.0) == "#000000"
    assert readable("#0072b2", "#000000", min_ratio=21.0) == "#ffffff"


def test_readable_takes_any_colour_not_just_a_palette_entry() -> None:
    assert contrast_ratio(readable("#f0e442", "#ffffff"), "#ffffff") >= 4.5


def test_contrast_ratio_endpoints() -> None:
    assert contrast_ratio("#000000", "#ffffff") == 21.0
    assert contrast_ratio("#ffffff", "#000000") == 21.0
    assert contrast_ratio("#0072b2", "#0072b2") == 1.0
    assert contrast_ratio("#f0e442", "#f0e442") == 1.0


def test_relative_luminance_endpoints() -> None:
    assert relative_luminance("#000000") == 0.0
    assert relative_luminance("#ffffff") == pytest.approx(1.0)
    assert relative_luminance("#808080") == pytest.approx(0.2158605, abs=1e-6)


# --- colour vision deficiency ------------------------------------------------
#
# Simulation is Vienot, Brettel & Mollon (1999), "Digital video colourmaps for
# checking the legibility of displays by dichromats", Color Research and
# Application 24(4), 243-252.
#
# Threshold: CIE76 dE*ab >= 10. The just-noticeable difference for dE*ab is
# ~2.3, so 10 is roughly four JNDs -- comfortably "these are different colours"
# rather than "a trained eye could tell them apart", with enough slack to
# survive the rendering, printing and clipping differences between the number
# measured here and what a reader actually sees. The measured minima are far
# above it, which is the point: Okabe-Ito was built for exactly this.
CVD_DELTA_E_FLOOR = 10.0

# Red-green deficiencies, ~8% of men. These are what Okabe-Ito targets.
RED_GREEN = ("deuteranopia", "protanopia")


@pytest.mark.parametrize("kind", RED_GREEN)
def test_adjacent_okabe_ito_colours_stay_apart_under_cvd(kind: str) -> None:
    colors = OKABE_ITO.colors
    for first, second in zip(colors, colors[1:]):
        distance = delta_e(simulate_cvd(first, kind), simulate_cvd(second, kind))
        assert distance >= CVD_DELTA_E_FLOOR, (
            f"{kind}: {first} and {second} collapse to dE={distance:.1f}"
        )


@pytest.mark.parametrize("kind", RED_GREEN)
def test_no_okabe_ito_pair_at_all_collapses_under_cvd(kind: str) -> None:
    """Stronger than the adjacency check: a reader picking any two series out
    of a legend must be able to tell them apart, not just neighbours."""
    colors = OKABE_ITO.colors
    worst = min(
        (delta_e(simulate_cvd(a, kind), simulate_cvd(b, kind)), a, b)
        for i, a in enumerate(colors)
        for b in colors[i + 1:]
    )
    distance, first, second = worst
    assert distance >= CVD_DELTA_E_FLOOR, f"{kind}: {first}/{second} dE={distance:.1f}"


def test_okabe_ito_is_not_tritanopia_safe() -> None:
    """FINDING, recorded rather than hidden. Okabe-Ito is designed for the
    red-green deficiencies; under tritanopia (~0.01% prevalence, and not a
    design goal of the palette) vermillion and reddish purple collapse to
    dE ~ 1, i.e. the same colour. Do not claim the palette is safe for it."""
    distance = delta_e(simulate_cvd("#d55e00", "tritanopia"),
                       simulate_cvd("#cc79a7", "tritanopia"))
    assert distance < 2.0


@pytest.mark.parametrize("kind", ("deuteranopia", "protanopia", "tritanopia"))
def test_simulation_leaves_the_neutral_axis_alone(kind: str) -> None:
    """A dichromat sees greys as greys; if the matrices were transcribed wrong
    this is where it shows up first."""
    for grey in ("#000000", "#404040", "#808080", "#c0c0c0", "#ffffff"):
        assert delta_e(simulate_cvd(grey, kind), grey) < 1.0


def test_simulation_is_a_projection() -> None:
    """Simulating an already-simulated colour must not move it again."""
    once = simulate_cvd("#e69f00", "deuteranopia")
    assert delta_e(simulate_cvd(once, "deuteranopia"), once) < 1.0


def test_unknown_cvd_kind_raises() -> None:
    with pytest.raises(ColorError, match="unknown CVD kind"):
        simulate_cvd("#000000", "monochromacy")


# --- spacing -----------------------------------------------------------------

def test_gap_name_and_index_agree() -> None:
    for theme_obj in ALL_THEMES:
        assert theme_obj.gap("m") == theme_obj.gap(3)


@pytest.mark.parametrize("name,index", sorted(GAP_NAMES.items()))
def test_every_gap_name_resolves_to_its_index(name: str, index: int) -> None:
    for theme_obj in ALL_THEMES:
        assert theme_obj.gap(name) == theme_obj.space[index]


def test_gap_scale_is_monotonic() -> None:
    for theme_obj in ALL_THEMES:
        steps = theme_obj.space
        assert list(steps) == sorted(steps)
        assert steps[0] > 0


def test_unknown_gap_raises() -> None:
    with pytest.raises(ThemeError, match="unknown spacing step"):
        theme().gap("enormous")
    with pytest.raises(ThemeError, match="outside"):
        theme().gap(99)


# --- scaling -----------------------------------------------------------------

LENGTH_FIELDS = (
    "font_size", "font_size_small", "font_size_large",
    "stroke", "thick", "radius", "arrow_size",
)
COLOR_FIELDS = ("ink", "paper", "muted", "accent", "grid")


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_scaled_doubles_lengths(theme_obj: Theme) -> None:
    big = theme_obj.scaled(2)
    for field in LENGTH_FIELDS:
        assert getattr(big, field) == pytest.approx(getattr(theme_obj, field) * 2)
    assert big.space == tuple(s * 2 for s in theme_obj.space)
    assert big.hairline == pytest.approx(theme_obj.hairline * 2)


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_scaled_leaves_colours_and_ratios_alone(theme_obj: Theme) -> None:
    big = theme_obj.scaled(2)
    for field in COLOR_FIELDS:
        assert getattr(big, field) == getattr(theme_obj, field)
    assert big.palette == theme_obj.palette
    assert big.line_height == theme_obj.line_height   # a ratio has no size
    assert big.font_family == theme_obj.font_family
    assert big.name == theme_obj.name


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_scaled_clamps_hairline_to_the_print_floor(theme_obj: Theme) -> None:
    tiny = theme_obj.scaled(0.01)
    assert tiny.hairline == HAIRLINE_FLOOR
    assert theme_obj.hairline * 0.01 < HAIRLINE_FLOOR   # the clamp really bit


def test_hairline_floor_is_a_quarter_point() -> None:
    assert to_pt(HAIRLINE_FLOOR) == pytest.approx(0.25, abs=0.001)


def test_every_theme_ships_above_the_print_floor() -> None:
    for theme_obj in ALL_THEMES:
        assert theme_obj.hairline >= HAIRLINE_FLOOR
        assert theme_obj.hairline < theme_obj.stroke < theme_obj.thick


def test_scaled_round_trips() -> None:
    nature = theme("nature")
    assert nature.scaled(4).scaled(0.25).font_size == pytest.approx(nature.font_size)


def test_scaled_rejects_non_positive_factors() -> None:
    for factor in (0, -1, -0.5):
        with pytest.raises(ThemeError, match="positive"):
            theme().scaled(factor)


def test_themes_are_frozen() -> None:
    with pytest.raises(Exception):
        theme().ink = "#ff0000"


# --- type --------------------------------------------------------------------

def test_font_sizes_are_stored_in_millimetres() -> None:
    """Contract: mm everywhere. A stored 7.0 would mean someone kept points."""
    nature = theme("nature")
    assert to_pt(nature.font_size) == pytest.approx(7.0)
    assert to_pt(nature.font_size_small) == pytest.approx(6.0)
    assert to_pt(nature.font_size_large) == pytest.approx(8.0)
    assert to_pt(theme("slides").font_size) == pytest.approx(14.0)


@pytest.mark.parametrize("theme_obj", ALL_THEMES, ids=theme_names())
def test_type_scale_is_ordered(theme_obj: Theme) -> None:
    assert theme_obj.font_size_small < theme_obj.font_size < theme_obj.font_size_large
    assert 1.0 <= theme_obj.line_height <= 2.0


def test_nature_fits_a_single_column() -> None:
    """7pt body on an 89mm column is the spec this theme exists to hit."""
    nature = theme("nature")
    assert to_pt(nature.font_size_small) >= 5.0    # journal minimum legible size
    assert nature.stroke == 0.25
    assert nature.radius == 1.0


# --- palettes ----------------------------------------------------------------

def test_okabe_ito_values_are_exact() -> None:
    """Pinned on purpose. This is a published standard: if a contrast test ever
    tempts someone to nudge a value, this fails first and asks them not to."""
    assert OKABE_ITO.colors == (
        "#000000", "#e69f00", "#56b4e9", "#009e73",
        "#f0e442", "#0072b2", "#d55e00", "#cc79a7",
    )


def test_tol_values_are_exact() -> None:
    assert TOL_BRIGHT.colors == (
        "#4477aa", "#ee6677", "#228833", "#ccbb44", "#66ccee", "#aa3377",
        "#bbbbbb",
    )
    assert TOL_MUTED.colors == (
        "#cc6677", "#332288", "#ddcc77", "#117733", "#88ccee",
        "#882255", "#44aa99", "#999933", "#aa4499",
    )


def test_only_muted_declares_a_bad_data_colour() -> None:
    """Tol documents a bad-data colour for `muted` only. The greys in `bright`
    and `vibrant` are ordinary 7th scheme members, and mislabelling one as
    bad-data would silently drop a usable series colour."""
    assert TOL_MUTED.bad == "#dddddd"
    assert TOL_BRIGHT.bad is None
    assert TOL_BRIGHT.colors[-1] == "#bbbbbb"
    assert TOL_YLORBR.bad == "#888888"
    assert TOL_SUNSET.bad == "#ffffff"


def test_vibrant_matches_bright_in_shape() -> None:
    assert TOL_VIBRANT.colors == (
        "#ee7733", "#0077bb", "#33bbee", "#ee3377", "#cc3311", "#009988",
        "#bbbbbb",
    )


def test_every_palette_is_lowercase_hex_and_unique() -> None:
    for name in palette_names():
        colors = palette(name).colors
        assert all(c == c.lower() and len(c) == 7 and c[0] == "#" for c in colors)
        assert len(set(colors)) == len(colors), f"{name} has a duplicate"


def test_every_palette_cites_a_source() -> None:
    for name in palette_names():
        assert palette(name).source


def test_palette_cycles() -> None:
    p = OKABE_ITO
    assert p.color(0) == p.color(len(p)) == "#000000"
    assert p.color(len(p) + 1) == p.colors[1]


def test_theme_color_shades_past_the_palette_rather_than_repeating() -> None:
    """`Palette.color` cycles (see above); `Theme.color` deliberately does not.

    A wrap made series 7 byte-identical to series 0, so an eight-series legend
    named two different things with one swatch. Past the end the colour is the
    palette again with its lightness moved -- same hue, visibly not the same
    swatch. Inside the palette nothing changed, which is what keeps the corpus
    where it was.
    """
    nature = theme("nature")
    size = len(nature.palette)
    assert [nature.color(i) for i in range(size)] == list(nature.palette)
    assert nature.color(size + 2) != nature.palette[2]
    assert nature.color(-1) == nature.palette[-1]
    assert len({nature.color(i) for i in range(2 * size)}) == 2 * size


def test_sequential_ramp_darkens_monotonically() -> None:
    luminances = [relative_luminance(c) for c in TOL_YLORBR.colors]
    assert luminances == sorted(luminances, reverse=True)


def test_diverging_ramp_is_lightest_in_the_middle() -> None:
    luminances = [relative_luminance(c) for c in TOL_SUNSET.colors]
    assert luminances.index(max(luminances)) == len(luminances) // 2


def test_ramp_endpoints_and_interpolation() -> None:
    assert TOL_YLORBR.ramp(0.0) == TOL_YLORBR.colors[0]
    assert TOL_YLORBR.ramp(1.0) == TOL_YLORBR.colors[-1]
    assert TOL_SUNSET.ramp(0.5) == TOL_SUNSET.colors[5]
    midpoint = interpolate(("#000000", "#ffffff"), 0.5)
    assert midpoint == "#808080"


def test_ramp_clamps_out_of_range() -> None:
    assert TOL_YLORBR.ramp(-5) == TOL_YLORBR.colors[0]
    assert TOL_YLORBR.ramp(5) == TOL_YLORBR.colors[-1]


def test_unknown_palette_raises() -> None:
    with pytest.raises(KeyError, match="unknown palette"):
        palette("viridis")


# --- colour utilities --------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("#abc", (170, 187, 204)),
    ("#AABBCC", (170, 187, 204)),
    ("#0072b2", (0, 114, 178)),
    ("rgb(0, 114, 178)", (0, 114, 178)),
    ("rgb(0 114 178)", (0, 114, 178)),
    ("rgb(0%, 100%, 50%)", (0, 255, 128)),
    ("navy", (0, 0, 128)),
    ("  White  ", (255, 255, 255)),
])
def test_parse_color_forms(text: str, expected: tuple[int, int, int]) -> None:
    assert parse_color(text) == expected


def test_parse_color_accepts_a_triple() -> None:
    assert parse_color((0, 114, 178)) == (0, 114, 178)
    assert parse_color((-5, 300, 12.6)) == (0, 255, 13)   # clamped and rounded


@pytest.mark.parametrize("bad", [
    "#12345", "#gggggg", "rgb(1,2)", "rgb(1,2,3,4)", "rgba(1,2,3,0.5)",
    "rgb(0 0 0 / 50%)", "chartreuse", "", "0072b2",
])
def test_parse_color_rejects_junk(bad: str) -> None:
    with pytest.raises(ColorError):
        parse_color(bad)


def test_to_hex_normalises() -> None:
    assert to_hex((0, 114, 178)) == "#0072b2"
    assert to_hex((0.4, 113.6, 177.5)) == "#0072b2"


def test_mix_endpoints_and_symmetry() -> None:
    assert mix("#0072b2", "#ffffff", 0.0) == "#0072b2"
    assert mix("#0072b2", "#ffffff", 1.0) == "#ffffff"
    assert mix("#000000", "#ffffff", 0.5) == mix("#ffffff", "#000000", 0.5)


def test_mix_rejects_out_of_range_amounts() -> None:
    for amount in (-0.1, 1.1):
        with pytest.raises(ColorError, match="0..1"):
            mix("#000000", "#ffffff", amount)


def test_lighten_and_darken_move_the_right_way() -> None:
    base = "#0072b2"
    assert relative_luminance(lighten(base, 0.3)) > relative_luminance(base)
    assert relative_luminance(darken(base, 0.3)) < relative_luminance(base)
    assert lighten(base, 1.0) == "#ffffff"
    assert darken(base, 1.0) == "#000000"
    assert lighten(base, 0.0) == darken(base, 0.0) == base


# --- determinism and lookup --------------------------------------------------

def test_lookup_is_case_and_whitespace_insensitive() -> None:
    assert theme("  NATURE ") is theme("nature")
    assert palette("Okabe-Ito") is OKABE_ITO


def test_default_theme_is_nature() -> None:
    assert theme().name == "nature"


def test_unknown_theme_raises() -> None:
    with pytest.raises(ThemeError, match="unknown theme"):
        theme("dracula")


def test_names_are_sorted_not_insertion_ordered() -> None:
    """Anything that enumerates these can end up in output; sorting is what
    keeps two runs byte-identical."""
    assert theme_names() == tuple(sorted(THEMES))
    assert palette_names() == tuple(sorted(PALETTES))
    assert list(theme_names()) == sorted(theme_names())


def test_style_for_is_deterministic() -> None:
    for theme_obj in ALL_THEMES:
        for role in ROLES:
            assert theme_obj.style_for(role) == theme_obj.style_for(role)


def test_derived_colours_are_deterministic() -> None:
    nature = theme("nature")
    once = [nature.ink_color(i) for i in range(8)]
    assert once == [nature.ink_color(i) for i in range(8)]
    assert mix("#e69f00", "#1a1a1a", 0.35) == mix("#e69f00", "#1a1a1a", 0.35)


def test_the_three_documented_themes_ship() -> None:
    assert theme_names() == ("nature", "notebook", "slides")
