"""`inklet.suite`: one house style for a figure set."""
from __future__ import annotations

import json
import os
import sys
import textwrap

import pytest

import inklet as i
from inklet.core import pt

GROUP = {"control": "#0072b2", "treated": "#009e73", "grey": "#90a4ae"}


def _house(**kw):
    return i.suite("test", palettes={"group": GROUP},
                   ramps={"size": ["#deebf7", "#4292c6", "#08306b"], "dose": "tol-ylorbr",
                          "level": {"low": "#deebf7", "mid": "#9ecae1", "high": "#4292c6"}},
                   text={"muted_colors": ("#90a4ae",)}, **kw)


def _figure(house, *, outline=False, grey=False):
    def make(w, h):
        p = house.panel(w, h, x=(0, 1), y=(0, 1))
        house.axes(p, x="time", y="response")
        for k, dy in (("control", 0.0), ("treated", 0.05)):
            pts = [(t / 4, t / 4 * 0.8 + dy) for t in range(5)]
            p.line(pts, **house.line(k))
            kw = house.mark(k)
            if outline:
                kw.update(stroke="#000000", stroke_width=0.2)
            p.scatter(pts, **kw)
        p.line([(0, 0), (1, 0.9)], **house.line("#222222", "fit"))
        house.end_labels(p, {"control": (1, 0.8), "treated": (1, 0.85)})
        if grey:
            p.text(0.2, 0.9, "faint", text_fill="#90a4ae", markup=False)
        return p
    with house:
        return house.mosaic(["a b"], {"a": make, "b": make}, height=50)


def test_sizes_and_weights_are_read_in_mm():
    house = _house(lines={"data": 0.6, "fit": 0.75, "axis": 0.5})
    assert house.stroke("data") == pytest.approx(pt(0.6))
    assert house.stroke("fit") == pytest.approx(pt(0.75))
    assert house.size("letter") == pytest.approx(pt(8))
    assert house.width("single") == 89 and house.width(120) == 120
    with pytest.raises(ValueError, match="tiers are"):
        house.stroke("bold")


def test_customize_merges_nested_fields():
    house = _house().customize(lines={"data": 0.5})
    assert house.lines.data == 0.5 and house.lines.fit == 0.75
    assert _house().lines.data == 0.6


def test_the_theme_carries_font_type_and_data_weight():
    house = _house(font="Nimbus Sans, Arial, sans-serif")
    theme = house.theme
    assert theme.font_family.startswith("Nimbus Sans")
    assert theme.stroke == pytest.approx(pt(0.6))
    assert theme.font_size_small == pytest.approx(pt(6))
    assert house.font_families() == ("Nimbus Sans", "Arial")


def test_with_block_sets_and_restores_the_theme():
    before = i.current_theme()
    house = _house()
    with house:
        assert i.current_suite() is house
        assert i.current_theme() is house.theme
    assert i.current_suite() is None
    assert i.current_theme() is before


def test_palettes_and_ramps():
    house = _house()
    assert house.color("control") == GROUP["control"]
    assert house.color("#123456") == "#123456"
    with pytest.raises(KeyError):
        house.color("placebo")
    size = house.ramp("size")
    assert size(0) == "#deebf7" and size(1) == "#08306b"
    assert house.ramp("dose")(0.5).startswith("#")
    assert house.stops("level")["mid"] == "#9ecae1"


def test_marker_keywords_have_no_outline_and_rings_use_the_series_colour():
    house = _house()
    assert house.mark("control") == dict(size=0.9, color=GROUP["control"], stroke="none")
    ring = house.mark("control", hollow=True)
    assert ring["hollow"] and ring["stroke"] == GROUP["control"] and ring["stroke_width"] == 0.3


def test_text_color_reaches_the_contrast_and_keeps_hue():
    from inklet.themes.color import contrast_ratio, to_oklab
    house = _house()
    pale = "#9ecae1"
    deep = house.text_color(pale)
    assert contrast_ratio(deep, "#ffffff") >= 4.5
    a0, b0 = to_oklab(pale)[1:]
    a1, b1 = to_oklab(deep)[1:]
    assert (a0 * b1 - a1 * b0) == pytest.approx(0, abs=2e-3)       # same hue direction
    assert house.text_color("grey") == house.theme.ink               # a grey series: ink


def test_end_labels_never_overlap():
    house = _house()
    p = house.panel(50, 30, x=(0, 1), y=(0, 1))
    house.end_labels(p, {"one": (1, 0.50), "two": (1, 0.51), "three": (1, 0.52)},
                     colors={k: "#0072b2" for k in ("one", "two", "three")})
    built = p.build()
    boxes = sorted((n.bbox for n in built.walk() if n.prim is not None and hasattr(n.prim, "lines")),
                   key=lambda b: b.y0)
    from inklet.core import resolve
    placed = resolve(built)
    texts = sorted((placed[n.id].bbox for n in built.walk()
                    if n.prim is not None and hasattr(n.prim, "lines")), key=lambda b: b.y0)
    assert len(texts) == 3
    assert all(a.y1 <= b.y0 + 1e-6 for a, b in zip(texts, texts[1:]))


def test_save_writes_every_format_and_a_clean_house_figure_lints_clean(tmp_path):
    house = _house()
    result = house.save(_figure(house), "fig", out=tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fig.pdf", "fig.png", "fig.svg"]
    assert result.written and result.errors == 0
    assert not [d for d in result.diagnostics if d.code in i.diagnostics.HOUSE_CODES]
    svg = (tmp_path / "fig.svg").read_text()
    assert "/usr/" not in svg and "@font-face" in svg


def test_save_reports_house_violations(tmp_path):
    house = _house()
    result = house.save(_figure(house, outline=True, grey=True), "bad", out=tmp_path)
    codes = {d.code for d in result.diagnostics}
    assert {"MARKER_OUTLINE", "MUTED_TEXT"} <= codes


def test_a_second_save_of_the_same_figure_touches_nothing(tmp_path):
    house = _house()
    house.save(_figure(house), "fig", out=tmp_path)
    for p in tmp_path.iterdir():
        os.utime(p, ns=(10**9, 10**9))
    _figure(_house(font="Arial"))          # build something else in between
    result = house.save(_figure(house), "fig", out=tmp_path)
    assert not result.written
    assert all(p.stat().st_mtime_ns == 10**9 for p in tmp_path.iterdir())


def test_build_skips_unchanged_figures_and_isolates_imports(tmp_path):
    """Two figure modules import different helpers named `helper` from their
    own directories; with isolation each sees its own."""
    for name, value in (("one", 1), ("two", 2)):
        d = tmp_path / name
        d.mkdir()
        (d / "helper.py").write_text(f"VALUE = {value}\n")
        (d / f"fig_{name}.py").write_text(textwrap.dedent(f"""
            import sys, pathlib
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from helper import VALUE
            import inklet as i
            def make_figure():
                assert VALUE == {value}, VALUE
                p = i.current_suite().panel(40, 30, x=(0, 1), y=(0, 1))
                p.line([(0, 0), (1, 1)], **i.current_suite().line("control"))
                return p
        """))
        sys.path.insert(0, str(d))
    try:
        house = _house()
        out = tmp_path / "out"
        first = house.build({"one": "fig_one", "two": "fig_two"}, out=out, report=False)
        assert [r.status for r in first.rows] == ["written", "written"], first.table()
        assert first.ok
        second = house.build({"one": "fig_one", "two": "fig_two"}, out=out, report=False)
        assert [r.status for r in second.rows] == ["unchanged", "unchanged"]
        manifest = json.loads((out / ".inklet-build.json").read_text())
        assert set(manifest) == {"one", "two"}
        changed = house.customize(lines={"data": 0.5})
        third = changed.build({"one": "fig_one"}, out=out, report=False, only=["one"])
        assert third.rows[0].status == "written"
    finally:
        for name in ("one", "two"):
            sys.path.remove(str(tmp_path / name))
        for mod in ("fig_one", "fig_two", "helper"):
            sys.modules.pop(mod, None)


def test_build_reports_a_failure_and_continues(tmp_path):
    house = _house()

    def broken():
        raise RuntimeError("no data")

    def good():
        p = house.panel(40, 30, x=(0, 1), y=(0, 1))
        house.axes(p, x="x", y="y")
        return p

    report = house.build({"bad": broken, "good": good},
                         out=tmp_path, report=False)
    assert [r.status for r in report.rows] == ["failed", "written"]
    assert not report.ok and "no data" in report.table()


def test_letters_can_be_upper_case():
    house = _house(letters={"case": "upper"})
    with house:
        def make(w, h):
            p = house.panel(w, h, x=(0, 1), y=(0, 1))
            house.axes(p, x="x", y="y")
            return p
        m = house.mosaic(["a"], {"a": make}, height=30, width=60)
    letters = [n.prim.lines[0].text for n in m.walk() if n.kind == "letter"]
    assert letters == ["A"]


def test_fonts_report_says_what_embeds():
    report = _house(font="sans-serif").fonts()
    assert set(report) == {"regular", "bold", "italic"}
    assert all("embeddable" in v for v in report.values())


def test_build_forgets_project_modules_but_keeps_libraries(tmp_path):
    """Re-importing a library that patches other modules at import time
    (fontTools.subset) would leave two generations of its classes behind."""
    import json as library
    from inklet.suite import _project_module
    (tmp_path / "local_helper.py").write_text("X = 1\n")
    sys.path.insert(0, str(tmp_path))
    try:
        import local_helper
        assert _project_module(local_helper)
        assert not _project_module(library)
        assert not _project_module(i)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("local_helper", None)
