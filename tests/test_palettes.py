"""inklet.themes: the palette collection, measured.

Every palette is checked for what its kind promises: categorical sets are
reported under normal vision and each simulated dichromacy, sequential maps
must be monotonic in lightness, diverging maps must be symmetric in shape,
cyclic maps must close. Inklet's own designs are held to the thresholds
their comments in palettes.py state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import inklet as i
from inklet.plot import panel
from inklet.plot.ramp import SEQUENTIAL, as_ramp, ramp
from inklet.themes import (
    CVD_KINDS, KINDS, NATURE, PALETTES, Palette, ThemeError, delta_e_2000,
    delta_e_ok, from_oklab, from_oklch, interpolate_oklab, palette,
    palette_names, parse_color, simulate_cvd, to_oklab, to_oklch,
)
from inklet.themes.color import ColorError, _ciede2000

ROOT = Path(__file__).resolve().parents[1]


def by_kind(kind):
    return [pytest.param(palette(n), id=n) for n in palette_names(kind)]


# --- every palette ------------------------------------------------------------


@pytest.mark.parametrize("name", palette_names())
def test_every_palette_parses_and_cites_source_and_licence(name) -> None:
    p = palette(name)
    assert p.kind in KINDS
    for c in p.colors:
        parse_color(c)
    if p.bad is not None:
        parse_color(p.bad)
    assert p.source.strip(), f"{name} cites no source"
    assert p.license.strip(), f"{name} states no licence position"


def test_the_collection_covers_each_kind() -> None:
    counts = {k: len(palette_names(k)) for k in KINDS}
    assert counts["categorical"] >= 20
    assert counts["sequential"] >= 45
    assert counts["diverging"] >= 20
    assert counts["cyclic"] >= 5
    assert sum(counts.values()) == len(PALETTES)
    for name in ("viridis", "cividis", "inferno", "plasma", "magma", "batlow",
                 "vik", "romao", "set2", "rdbu", "tol-light", "tol-nightfall",
                 "inklet", "inklet-muted", "inklet-pairs", "inklet-duo"):
        assert name in PALETTES


def test_no_gpl_or_proprietary_sets_are_shipped() -> None:
    # ggsci is GPL and Tableau's sets are proprietary: neither may be vendored.
    for name in PALETTES:
        assert not name.startswith(("ggsci", "tableau", "npg", "lancet", "jama"))
    for p in PALETTES.values():
        assert "GPL" not in p.license


# --- categorical ----------------------------------------------------------------


@pytest.mark.parametrize("p", by_kind("categorical"))
def test_categorical_palettes_report_normal_and_every_cvd(p) -> None:
    r = p.report()
    assert r.kind == "categorical" and r.count == len(p)
    assert set(r.min_delta_e_cvd) == set(CVD_KINDS)
    assert r.min_delta_e > 0
    assert all(v >= 0 for v in r.min_delta_e_cvd.values())
    assert r.min_delta_e_any <= r.min_delta_e
    assert str(r).startswith(p.name)


def worst_cvd(p: Palette) -> float:
    """The smallest distance under any dichromacy, by either simulation."""
    worst = float("inf")
    for kind in CVD_KINDS:
        for method in ("machado", "vienot"):
            seen = [simulate_cvd(c, kind, method=method) for c in p.colors]
            worst = min(worst, min(delta_e_2000(a, b) for k, a in enumerate(seen)
                                   for b in seen[k + 1:]))
    return worst


@pytest.mark.parametrize("name, normal, cvd, grey", [
    ("inklet", 25.0, 12.0, 5.0),
    ("inklet-muted", 23.0, 12.5, 6.0),
    ("inklet-pairs", 15.0, 5.5, None),
    ("inklet-duo", 27.0, 24.0, 12.0),
])
def test_inklet_palettes_meet_their_stated_thresholds(name, normal, cvd, grey) -> None:
    p = palette(name)
    r = p.report()
    assert r.min_delta_e >= normal
    assert worst_cvd(p) >= cvd
    if grey is not None:
        assert r.min_lightness_gap >= grey
    assert p.license == "MIT (Inklet)"


def test_inklet_beats_okabe_ito_on_every_measure() -> None:
    ours, theirs = palette("inklet"), palette("okabe-ito")
    assert len(ours) == len(theirs) == 8
    assert ours.report().min_delta_e > theirs.report().min_delta_e
    assert worst_cvd(ours) > worst_cvd(theirs)
    assert ours.report().min_lightness_gap > theirs.report().min_lightness_gap


def test_inklet_pairs_share_a_hue_and_split_in_lightness() -> None:
    p = palette("inklet-pairs")
    for k in range(0, len(p), 2):
        (l1, _, h1), (l2, _, h2) = to_oklch(p[k]), to_oklch(p[k + 1])
        assert l2 - l1 > 0.25
        assert min(abs(h1 - h2), 360 - abs(h1 - h2)) < 15


def test_inklet_duo_reference_is_neutral() -> None:
    assert to_oklch(palette("inklet-duo")[2])[1] < 0.002


# --- ramps --------------------------------------------------------------------

#: Tol's discrete rainbow deliberately runs dark-light-dark-light; it is a
#: sequence of distinct hues for ordered classes, not a lightness ramp.
NOT_MONOTONIC = {"tol-rainbow"}


@pytest.mark.parametrize("p", by_kind("sequential"))
def test_sequential_maps_are_monotonic_in_lightness(p) -> None:
    if p.name in NOT_MONOTONIC:
        assert p.report().monotonic is False
        assert "interpolate" in p.notes
        return
    assert p.report().monotonic, [round(v) for v in p.lightness()]


@pytest.mark.parametrize("p", by_kind("diverging"))
def test_diverging_maps_are_symmetric(p) -> None:
    r = p.report()
    assert r.symmetric, [round(v) for v in r.lightness]
    # Published maps are not exact mirrors; PuOr is the most lopsided.
    assert r.asymmetry < 25


@pytest.mark.parametrize("name", ["tol-burd", "tol-sunset", "tol-nightfall",
                                  "managua", "roma", "rdbu"])
def test_designed_symmetric_maps_mirror_closely(name) -> None:
    assert palette(name).report().asymmetry < 5


@pytest.mark.parametrize("p", by_kind("cyclic"))
def test_cyclic_maps_close_on_themselves(p) -> None:
    assert delta_e_2000(p.colors[0], p.colors[-1]) < 1.0
    four = p.resampled(4)
    assert len(four) == 4 and four[0] == p.ramp(0, "oklab")


DENSE = ["viridis", "cividis", "inferno", "plasma", "magma", "batlow", "vik",
         "romao", "oslo", "berlin", "grayc"]


@pytest.mark.parametrize("name", DENSE)
def test_dense_maps_interpolate_alike_in_every_space(name) -> None:
    """Offline proxy for the reproduction check: with enough stops, OKLab,
    CIELAB and sRGB interpolation must agree between the stops. Each is
    within 1 of the published colour, so two may differ by up to 2 -- and
    8-bit rounding of the result adds a little of its own."""
    p = palette(name)
    n = len(p) - 1
    for k in range(n):
        t = (k + 0.5) / n
        a, b, c = (p.ramp(t, s) for s in ("oklab", "lab", "srgb"))
        assert delta_e_2000(a, b) < 2.0 and delta_e_2000(a, c) < 2.0


def _generator():
    path = ROOT / "tools" / "gen_palette_data.py"
    spec = importlib.util.spec_from_file_location("gen_palette_data", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("gen_palette_data", module)
    spec.loader.exec_module(module)
    return module


def test_dense_maps_reproduce_the_published_tables() -> None:
    """ΔE00 < 1 against the full 256-entry float tables, when the pinned
    sources have been fetched into out/palette-sources."""
    cache = ROOT / "out" / "palette-sources"
    if not cache.is_dir():
        pytest.skip("palette sources not fetched; run tools/gen_palette_data.py")
    gen = _generator()
    try:
        mpl = gen.matplotlib_tables(gen.fetch("matplotlib", cache))
        cram = gen.crameri_tables(gen.fetch("crameri", cache))
    except (OSError, SystemExit) as exc:  # offline and not cached
        pytest.skip(f"palette sources unavailable: {exc}")
    for name, rows in {**mpl, **cram}.items():
        stops = list(palette(name.lower()).colors)
        if name == "magma":
            assert stops[0] == "#000004" and stops[-1] == "#fcfdbf"
        assert gen._error(stops, rows) < 1.0, name


# --- palette API ----------------------------------------------------------------


def test_reversed_and_the_r_suffix() -> None:
    v = palette("viridis")
    r = palette("viridis_r")
    assert r.name == "viridis_r" and r.colors == tuple(reversed(v.colors))
    assert r.reversed() == v
    assert palette(" Viridis_R ") == r
    with pytest.raises(KeyError, match="unknown palette"):
        palette("nonsense_r")


def test_resampled() -> None:
    v = palette("viridis").resampled(5)
    assert len(v) == 5 and v.kind == "sequential"
    assert v[0] == palette("viridis")[0] and v[-1] == palette("viridis")[-1]
    assert palette("inklet").resampled(3).colors == palette("inklet").colors[:3]
    with pytest.raises(ColorError):
        palette("inklet").resampled(9)
    with pytest.raises(ColorError):
        palette("viridis").resampled(0)


def test_cvd_and_greyscale_variants() -> None:
    p = palette("okabe-ito")
    d = p.cvd("deuteranopia")
    assert len(d) == len(p) and d.name == "okabe-ito+deuteranopia"
    assert d.min_delta_e() == p.min_delta_e("deuteranopia")
    g = p.greyscale()
    assert all(c[1:3] == c[3:5] == c[5:7] for c in g.colors)
    with pytest.raises(ColorError):
        p.cvd("monochromacy")


def test_palette_names_by_kind() -> None:
    assert palette_names("qualitative") == palette_names("categorical")
    assert "viridis" in palette_names("sequential")
    assert "viridis" not in palette_names("diverging")
    assert set(palette_names()) == set(PALETTES)
    assert list(palette_names()) == sorted(palette_names())
    with pytest.raises(ValueError):
        palette_names("rainbow")


def test_palette_kind_alias_and_validation() -> None:
    assert Palette("x", ("#000000",), kind="qualitative").kind == "categorical"
    with pytest.raises(ValueError):
        Palette("x", ("#000000",), kind="spiral")


# --- colour science -------------------------------------------------------------


@pytest.mark.parametrize("lab1, lab2, expected", [
    # Sharma, Wu & Dalal (2005), table 1: pairs 1, 7, 17 and 25.
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
])
def test_ciede2000_matches_sharma(lab1, lab2, expected) -> None:
    assert _ciede2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)
    assert _ciede2000(lab2, lab1) == pytest.approx(expected, abs=1e-4)


def test_oklab_matches_ottosson() -> None:
    assert to_oklab("#ffffff") == pytest.approx((1.0, 0.0, 0.0), abs=1e-4)
    assert to_oklab("#ff0000") == pytest.approx((0.62796, 0.22486, 0.12585), abs=1e-4)
    for c in ("#1d57a0", "#df913e", "#000000", "#808080"):
        assert from_oklab(to_oklab(c)) == c
        assert from_oklch(to_oklch(c)) == c
    assert delta_e_ok("#000000", "#ffffff") == pytest.approx(100.0, abs=0.01)
    assert interpolate_oklab(("#000000", "#ffffff"), 0.0) == "#000000"


def test_machado_simulation() -> None:
    for kind in CVD_KINDS:
        # Neutrals are unchanged, and severity 0 is normal vision.
        assert simulate_cvd("#ffffff", kind, method="machado") == "#ffffff"
        assert simulate_cvd("#808080", kind, method="machado") == "#808080"
        assert simulate_cvd("#d55e00", kind, method="machado", severity=0.0) == "#d55e00"
    # Red and green collapse for a deuteranope; blue and yellow do not.
    red_green = delta_e_2000(simulate_cvd("#e41a1c", method="machado"),
                             simulate_cvd("#4daf4a", method="machado"))
    blue_yellow = delta_e_2000(simulate_cvd("#0072b2", method="machado"),
                               simulate_cvd("#f0e442", method="machado"))
    assert red_green < 20 < blue_yellow
    with pytest.raises(ColorError):
        simulate_cvd("#ff0000", method="brettel-ish")
    with pytest.raises(ColorError):
        simulate_cvd("#ff0000", method="machado", severity=1.5)


# --- wiring ---------------------------------------------------------------------


def test_ramp_accepts_names_and_oklab() -> None:
    r = ramp("viridis", space="oklab")
    assert r.space == "oklab" and r(0.0) == palette("viridis")[0]
    assert as_ramp("batlow").stops == palette("batlow").colors
    assert as_ramp(palette("vik")).stops == palette("vik").colors
    assert as_ramp(SEQUENTIAL) is SEQUENTIAL and as_ramp(None) is None
    shade = lambda t: "#000000"  # noqa: E731
    assert as_ramp(shade) is shade


def test_default_sequential_ramp_is_unchanged() -> None:
    assert SEQUENTIAL.stops == ("#fcfdbf", "#fec488", "#fc8961", "#e75263",
                                "#b73779", "#832681", "#51127c", "#1d1147")


def test_matrix_and_scatter_take_a_palette_name() -> None:
    p = panel(20, 10).matrix([[0.0, 0.5], [1.0, 0.25]], ramp="viridis")
    assert p._ramp.stops == palette("viridis").colors
    q = panel(20, 10).scatter([(0, 0), (1, 1)], color=[0.0, 1.0], ramp="batlow")
    assert q._ramp.stops == palette("batlow").colors
    p.colorbar()


def test_themes_pick_palettes_by_name() -> None:
    t = NATURE.with_palette("inklet")
    assert t.palette == palette("inklet").colors
    assert t.color(1) == "#df913e" and NATURE.palette == palette("okabe-ito").colors
    assert NATURE.with_palette(palette("tol-muted")).palette == palette("tol-muted").colors
    assert NATURE.with_palette(["#111111", "#222222"]).palette == ("#111111", "#222222")
    with pytest.raises(ThemeError, match="resampled"):
        NATURE.with_palette("viridis")
    small = NATURE.with_palette(palette("viridis").resampled(4))
    assert len(small.palette) == 4


def test_presets_customize_takes_a_palette_name() -> None:
    chosen = i.preset("scientific.nature").customize(palette="inklet-muted")
    assert chosen.theme.palette == palette("inklet-muted").colors
