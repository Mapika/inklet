"""The 4.4 deprecations: every old spelling still works, gives the same result,
and warns exactly once; every canonical spelling is silent.

The suite runs with `InkletDeprecationWarning` as an error (pyproject.toml), so
any test elsewhere that reaches an old spelling fails. This file is where the
old spellings are exercised on purpose.
"""
from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
import random
import re
import sys
import warnings

import pytest

import inklet
from inklet import use_theme
from inklet._compat import InkletDeprecationWarning

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve()


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def caught(call):
    """`call()`'s result and every warning it raised, whatever the filters say."""
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        result = call()
    return result, seen


def one_deprecation(seen, *, mentions=()):
    """Exactly one warning: ours, naming the caller's line in this file."""
    assert [w.category for w in seen] == [InkletDeprecationWarning], [str(w.message) for w in seen]
    message = str(seen[0].message)
    assert "Inklet 5.0" in message
    for word in mentions:
        assert word in message, message
    assert Path(seen[0].filename).resolve() == HERE, seen[0].filename
    return message


# -- import paths -------------------------------------------------------------

MOVED = [
    ("inklet.experimental.volume", "inklet.volume", "Volume"),
    ("inklet.experimental.sections", "inklet.volume", "Plane"),
    ("inklet.experimental.slabs", "inklet.volume", "Slab"),
    ("inklet.experimental.regions", "inklet.volume", "BoxRegion"),
    ("inklet.experimental.channels", "inklet.volume", "Channel"),
    ("inklet.experimental.contours", "inklet.volume", "LabelContour"),
    ("inklet.experimental.measurements", "inklet.volume", "measure_labels"),
    ("inklet.experimental.tiff", "inklet.volume", "read_tiff"),
    ("inklet.experimental.selection", "inklet.selection", "KeyedTable"),
    ("inklet.experimental.temporal", "inklet.selection._temporal", "time_value"),
    ("inklet.experimental._table_adapters", "inklet.selection._table_adapters", "pandas_columns"),
    ("inklet.experimental.layout_editor", "inklet.editor", "LayoutEditor"),
    ("inklet.experimental.scene_viewer", "inklet.render._viewer", "to_html"),
    ("inklet.experimental.project", "inklet.project", "FigureProject"),
    ("inklet.experimental.project.assets", "inklet.project.assets", "AssetManifest"),
    ("inklet.experimental.project.identity", "inklet.project.identity", "EntityMap"),
]
HINTS = {
    "inklet.experimental.temporal": "private to inklet.selection",
    "inklet.experimental._table_adapters": "KeyedTable.from_pandas()",
    "inklet.experimental.scene_viewer": "RenderScene.to_html()",
}


def fresh_import(old):
    """Import `old` anew so its module-level warning runs again."""
    for name in [m for m in sys.modules if m == old or m.startswith(old + ".")]:
        sys.modules.pop(name)
    parent = old.rpartition(".")[0]
    if parent.startswith("inklet.experimental."):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InkletDeprecationWarning)
            importlib.import_module(parent)
    return caught(lambda: importlib.import_module(old))


@pytest.mark.parametrize("old,new,name", MOVED)
def test_moved_modules_warn_once_and_return_the_same_objects(old, new, name):
    module, seen = fresh_import(old)
    message = str(seen[0].message) if seen else ""
    assert [w.category for w in seen] == [InkletDeprecationWarning], message
    assert message.startswith(old + " is deprecated and will be removed in Inklet 5.0")
    assert HINTS.get(old, f"import from {new} instead") in message
    assert getattr(module, name) is getattr(importlib.import_module(new), name)


def test_a_moved_module_warning_names_the_importing_line():
    sys.modules.pop("inklet.experimental.tiff", None)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        from inklet.experimental.tiff import read_tiff  # noqa: F401
    assert len(seen) == 1 and Path(seen[0].filename).resolve() == HERE


def test_project_submodules_reached_as_attributes_warn_once_each():
    for name in [m for m in sys.modules if m.startswith("inklet.experimental.project")]:
        sys.modules.pop(name)
    project, seen = caught(lambda: importlib.import_module("inklet.experimental.project"))
    assert len(seen) == 1
    assets, seen = caught(lambda: project.assets)
    one_deprecation(seen, mentions=("inklet.project.assets",))
    assert assets.AssetManifest is inklet.project.assets.AssetManifest


def test_engineering_is_marked_for_removal_without_a_replacement():
    module, seen = fresh_import("inklet.experimental.engineering")
    assert [w.category for w in seen] == [InkletDeprecationWarning]
    assert "no replacement" in str(seen[0].message)
    assert module.BoxAssembly and module.BoxComponent


def test_the_moved_shims_no_longer_reexport_the_standard_library():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InkletDeprecationWarning)
        selection = importlib.import_module("inklet.experimental.selection")
        editor = importlib.import_module("inklet.experimental.layout_editor")
    assert not hasattr(selection, "json") and not hasattr(selection, "dataclass")
    assert not hasattr(editor, "threading") and editor.LayoutEditor is inklet.editor.LayoutEditor


@pytest.mark.parametrize("new", ["inklet.volume", "inklet.selection", "inklet.project",
                                 "inklet.project.assets", "inklet.project.identity",
                                 "inklet.editor", "inklet.render._viewer", "inklet.plot",
                                 "inklet.assets", "inklet.diagnostics.image"])
def test_canonical_modules_import_silently(new):
    import subprocess
    code = ("import warnings; warnings.simplefilter('error'); "
            f"import {new}; import inklet.experimental.browser, inklet.experimental.figure_planner")
    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT,
                   env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""})


# -- keywords -----------------------------------------------------------------

def svg(p):
    """The drawing, with the automatic ids that count every node ever built blanked."""
    return anonymous(inklet.to_svg(p.build()))


def anonymous(text):
    return re.sub(r'((?:id|href)="#?|url\(#)[A-Za-z_-]*\d+', r"\1n", text)


def cloud():
    rng = random.Random(3)
    points, names = [], []
    for name, (cx, cy) in {"A": (-3, 0), "B": (3, 1)}.items():
        for _ in range(40):
            points.append((cx + rng.gauss(0, 0.6), cy + rng.gauss(0, 0.5)))
            names.append(name)
    return points, names


GROUPS = {"a": [1, 2, 2, 3, 3, 3, 4, 4, 5, 7], "b": [2, 3, 4, 4, 5, 5, 5, 6, 6, 8]}
TWO = ["#aa3377", "#4477aa"]
FOLD = [2.0, -2.1, 0.1, 0.4, -0.3, 1.9, -1.5, 0.0]
PVAL = [1e-4, 1e-5, 0.5, 0.2, 0.7, 1e-3, 1e-3, 0.9]
LINK = [[1, 3, 0.5, 2], [0, 5, 1.0, 3], [2, 4, 1.5, 2], [6, 7, 3.0, 5]]
SURVIVAL = {"x": ([6, 6, 7, 10, 13, 16, 22], [1, 1, 0, 1, 1, 0, 1]),
            "y": ([1, 2, 2, 3, 4, 5, 8], None)}

# (method, x, y, positional args, old keywords, the new spelling of those keywords)
PANEL_KEYWORDS = [
    ("bars", ("a", "b"), (0, 5), (["a", "b"], [[1, 2], [3, 2]]),
     dict(colors=TWO, names=["one", "two"]), dict(color=TWO, name=["one", "two"])),
    ("hist", (0, 8), (0, 6), ([1, 2, 2, 3, 3, 3, 5, 6], 4), dict(colors="#aa3377"), dict(color="#aa3377")),
    ("stackarea", (0, 2), (0, 5), ([0, 1, 2], [[1, 2, 1], [2, 1, 2]]),
     dict(colors=TWO, names=["p", "q"]), dict(color=TWO, name=["p", "q"])),
    ("boxplot", ("a", "b"), (0, 9), (GROUPS,), dict(colors=TWO), dict(color=TWO)),
    ("violin", ("a", "b"), (0, 9), (GROUPS,), dict(colors=TWO), dict(color=TWO)),
    ("swarm", ("a", "b"), (0, 9), (GROUPS,), dict(colors=TWO), dict(color=TWO)),
    ("ridgeline", (0, 9), ("a", "b"), (GROUPS,), dict(colors=TWO), dict(color=TWO)),
    ("raincloud", (0, 9), ("a", "b"), (GROUPS,), dict(colors=TWO), dict(color=TWO)),
    ("dendrogram", None, None, (LINK,), dict(colors=TWO, threshold=2.0), dict(color=TWO, threshold=2.0)),
    ("kaplan_meier", (0, 25), (0, 1), (SURVIVAL,), dict(colors=TWO), dict(color=TWO)),
    ("dumbbell", ("a", "b"), (0, 5), (["a", "b"], [[1, 2], [3, 4]]),
     dict(colors=TWO, names=["pre", "post"]), dict(color=TWO, name=["pre", "post"])),
    ("volcano", (-3, 3), (0, 6), (FOLD, PVAL),
     dict(colors={"up": "#aa0000"}, names=("Down", None, "Up")),
     dict(color={"up": "#aa0000"}, name=("Down", None, "Up"))),
    ("split_violin", ("a", "b"), (0, 9), (GROUPS, {"a": [2, 3, 3, 4, 5], "b": [4, 5, 5, 6, 7]}),
     dict(colors=TWO, names=["c", "t"]), dict(color=TWO, name=["c", "t"])),
    ("embedding", (-6, 6), (-3, 4), cloud(),
     dict(colors={"A": "#aa3377", "B": "#4477aa"}, centre="mean"),
     dict(color={"A": "#aa3377", "B": "#4477aa"}, center="mean")),
]


def panel_for(x, y):
    options = {}
    if x is not None:
        options["x"] = inklet.band(list(x)) if isinstance(x[0], str) else x
    if y is not None:
        options["y"] = inklet.band(list(y)) if isinstance(y[0], str) else y
    return inklet.plot.panel(50, 40, **options)


@pytest.mark.parametrize("method,x,y,args,old,new", PANEL_KEYWORDS, ids=[c[0] for c in PANEL_KEYWORDS])
def test_panel_keyword_aliases_draw_the_same_and_warn_once(method, x, y, args, old, new):
    fresh, seen = caught(lambda: getattr(panel_for(x, y), method)(*args, **new))
    assert seen == []
    legacy, seen = caught(lambda: getattr(panel_for(x, y), method)(*args, **old))
    renamed = [k for k in old if k not in new]
    assert len(seen) == len(renamed)
    for warning, name in zip(seen, renamed):
        one_deprecation([warning], mentions=(f"Panel.{method}({name}=)", f"use {new_name(name)}="))
    assert svg(legacy) == svg(fresh)


def new_name(old):
    return {"colors": "color", "names": "name", "centre": "center", "sizes": "size"}[old]


def test_old_and_new_keyword_together_is_an_error():
    p = panel_for(("a", "b"), (0, 5))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InkletDeprecationWarning)
        with pytest.raises(TypeError, match="both color= and its deprecated spelling colors="):
            p.bars(["a", "b"], [1, 2], color="#000000", colors=["#111111"])


def test_name_takes_one_string_for_a_single_series():
    one = panel_for(("a", "b"), (0, 5)).bars(["a", "b"], [1, 2], name="only")
    listed = panel_for(("a", "b"), (0, 5)).bars(["a", "b"], [1, 2], name=["only"])
    assert svg(one) == svg(listed)


def test_dotplot_takes_size_and_color_beside_its_positional_slots():
    sizes = [[0.25, 1.0, 0.0], [0.5, 0.2, 0.81]]
    colors = [[0.1, 0.9, 0.4], [0.3, 0.7, 0.5]]
    options = dict(x=inklet.band(["a", "b", "c"]), y=inklet.band(["g1", "g2"]))
    positional, seen = caught(lambda: inklet.plot.panel(40, 30, **options).dotplot(sizes, colors))
    assert seen == []
    canonical, seen = caught(lambda: inklet.plot.panel(40, 30, **options).dotplot(size=sizes, color=colors))
    assert seen == []
    legacy, seen = caught(lambda: inklet.plot.panel(40, 30, **options).dotplot(sizes=sizes, colors=colors))
    assert len(seen) == 2 and all(w.category is InkletDeprecationWarning for w in seen)
    assert svg(positional) == svg(canonical) == svg(legacy)
    paint, seen = caught(lambda: inklet.plot.panel(40, 30, **options).dotplot(size=sizes, color="#aa3377"))
    assert seen == [] and "#aa3377" in svg(paint)


def test_polar_pie_and_breakout_keyword_aliases():
    from inklet.plot import polar
    fresh, seen = caught(lambda: polar(20).pie([3, 2, 1], name=["a", "b", "c"], color=TWO + ["#999999"]))
    assert seen == []
    legacy, seen = caught(lambda: polar(20).pie([3, 2, 1], names=["a", "b", "c"], colors=TWO + ["#999999"]))
    assert len(seen) == 2
    one_deprecation(seen[:1], mentions=("PolarPanel.pie(",))
    assert svg(legacy) == svg(fresh)
    def wheel():
        p = polar(20)
        p.pie([30, 45, 25])
        return p
    fresh, seen = caught(lambda: wheel().breakout(0, [60, 25, 15], name=["w", "x", "y"]))
    assert seen == []
    legacy, seen = caught(lambda: wheel().breakout(0, [60, 25, 15], names=["w", "x", "y"]))
    one_deprecation(seen, mentions=("PolarPanel.breakout(names=)",))
    assert svg(legacy) == svg(fresh)


def test_plot_spec_warns_where_the_call_is_recorded():
    def build(**keywords):
        spec = inklet.plot_spec(x=inklet.band(["a", "b"]), y=(0, 5))
        return spec.bars(["a", "b"], [[1, 2], [2, 1]], **keywords).axes().legend()
    fresh, seen = caught(lambda: build(name=["p", "q"]))
    assert seen == []
    legacy, seen = caught(lambda: build(names=["p", "q"]))
    one_deprecation(seen, mentions=("Panel.bars(names=)",))
    def page(spec):
        doc = inklet.document(width=80)
        doc.add("plot", spec)
        return anonymous(doc.compile().to_svg())
    rendered, seen = caught(lambda: (page(legacy), page(fresh)))
    assert seen == [] and rendered[0] == rendered[1]


def test_centre_keywords_of_arcs_and_text():
    from inklet.core import Vec2
    from inklet.draw.shapes import arc_cubics
    from inklet.plot.raster import uniform_pitch
    from inklet.typeset.onpath import baseline_arc
    cases = [
        (lambda: arc_cubics(center=Vec2(1, 2), radius=3, start=0, end=90),
         lambda: arc_cubics(centre=Vec2(1, 2), radius=3, start=0, end=90), "arc_cubics(centre=)"),
        (lambda: baseline_arc(5, 0, 90, center=(1, 1)),
         lambda: baseline_arc(5, 0, 90, centre=(1, 1)), "baseline_arc(centre=)"),
        (lambda: uniform_pitch(centers=[0.0, 1.0, 2.0]),
         lambda: uniform_pitch(centres=[0.0, 1.0, 2.0]), "uniform_pitch(centres=)"),
        (lambda: anonymous(inklet.to_svg(inklet.text_on_arc("Arc", 10, 45, center=(2, 2)))),
         lambda: anonymous(inklet.to_svg(inklet.text_on_arc("Arc", 10, 45, centre=(2, 2)))), "text_on_arc(centre=)"),
    ]
    for canonical, legacy, mention in cases:
        expected, seen = caught(canonical)
        assert seen == [], mention
        got, seen = caught(legacy)
        one_deprecation(seen, mentions=(mention,))
        assert repr(got) == repr(expected)


def test_baseline_arc_keeps_its_positional_centre_slot_silently():
    from inklet.typeset.onpath import baseline_arc
    positional, seen = caught(lambda: baseline_arc(5, 0, 90, (1, 1)))
    assert seen == [] and repr(positional) == repr(baseline_arc(5, 0, 90, center=(1, 1)))
    with pytest.raises(TypeError, match="both"):
        baseline_arc(5, 0, 90, (1, 1), center=(1, 1))


def test_old_keywords_stay_visible_to_signature_binding():
    import inspect
    signature = inspect.signature(inklet.plot.Panel.bars)
    assert repr(signature.parameters["colors"].default) == "<deprecated: use color=>"
    signature.bind(None, ["a"], [1], colors=["#000"], names=["x"])


# -- functions, properties and names ------------------------------------------

def test_renamed_functions_and_names():
    from inklet.assets import harmonise as harmonise_module
    from inklet.diagnostics import image
    from inklet.plot import embedding, matrix
    points, names = cloud()
    cases = [
        (lambda: inklet.plot.cluster_centers(points, names),
         lambda: inklet.plot.cluster_centres(points, names), "cluster_centres()"),
        (lambda: matrix.default_coloring([[1.0, -1.0]], None, None, None),
         lambda: matrix.default_colouring([[1.0, -1.0]], None, None, None), "default_colouring()"),
        (lambda: harmonise_module.as_harmonize(0.5),
         lambda: harmonise_module.as_harmonise(0.5), "as_harmonise()"),
    ]
    for canonical, legacy, mention in cases:
        expected, seen = caught(canonical)
        assert seen == []
        got, seen = caught(legacy)
        one_deprecation(seen, mentions=(mention,))
        assert got == expected
    assert image.average_colour.__name__ == "average_colour"
    assert "average_color" in image.__all__ and "average_colour" in image.__all__
    value, seen = caught(lambda: embedding.CENTRE_METHODS)
    one_deprecation(seen, mentions=("CENTER_METHODS",))
    assert value is embedding.CENTER_METHODS


def test_matrix_centres_alias():
    from inklet.plot import matrix
    import inspect
    parameters = inspect.signature(matrix.matrix_centers).parameters
    assert list(parameters) == list(inspect.signature(matrix.matrix_centres).parameters)


def test_average_colour_alias(tmp_path):
    from inklet.core import Affine, ImagePrim, Rect
    from inklet.diagnostics import image
    pytest.importorskip("PIL")
    from PIL import Image
    path = tmp_path / "flat.png"
    Image.new("RGB", (40, 20), (200, 40, 40)).save(path)
    prim = ImagePrim(source=str(path), width=100.0, height=50.0, pixel_size=(40, 20))
    box = Rect(-40.0, -20.0, 40.0, 20.0)
    expected, seen = caught(lambda: image.average_color(prim, Affine(), box))
    assert seen == [] and expected is not None
    got, seen = caught(lambda: image.average_colour(prim, Affine(), box))
    one_deprecation(seen, mentions=("average_colour()", "average_color()"))
    assert got == expected


def test_harmonise_class_alias_is_the_same_class():
    import inklet.assets
    value, seen = caught(lambda: inklet.assets.Harmonise)
    one_deprecation(seen, mentions=("inklet.assets.Harmonize",))
    assert value is inklet.assets.Harmonize
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        from inklet.assets import Harmonise  # noqa: F401
    assert len(seen) == 1  # the import machinery's probe does not count twice
    assert "Harmonize" in inklet.assets.__all__ and "Harmonise" not in inklet.assets.__all__


def test_polar_centre_property():
    from inklet.plot import polar
    p = polar(20)
    value, seen = caught(lambda: p.centre)
    one_deprecation(seen, mentions=("PolarPanel.centre", "use .center"))
    assert value == p.center


# -- saved files and experimental classes -------------------------------------

def layout_source():
    recipe = inklet.composition(100, 50)
    recipe.add("left", inklet.module("A"), x=10, y=15)
    return recipe


@pytest.mark.parametrize("version", ["0.1", "0.2", "0.3", "0.4"])
def test_old_layout_schemas_load_and_ask_to_be_resaved(version):
    base = layout_source()
    saved = {"schema": f"inklet.composition-layout/{version}",
             "targets": {"/left": {"placement": {"x": 14}}}}
    (restored, report), seen = caught(lambda: base.with_layout_overrides(saved))
    message = one_deprecation(seen, mentions=(f"schema {version}", "re-save"))
    assert "inklet.composition-layout/0.5" in message
    assert restored.layout_overrides(base)["targets"]["/left"]["placement"]["x"] == 14
    resaved = restored.layout_overrides(base)
    assert resaved["schema"] == "inklet.composition-layout/0.5"
    _, seen = caught(lambda: base.with_layout_overrides(json.loads(json.dumps(resaved))))
    assert seen == []


def test_an_invalid_old_layout_file_fails_without_a_deprecation():
    base = layout_source()
    saved = {"schema": "inklet.composition-layout/0.1", "targets": {"/left": {"placement": {"x": math.nan}}}}
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        with pytest.raises(ValueError):
            base.with_layout_overrides(saved)
    assert seen == []


def test_browser_scatter_points_to_browser_figure():
    from inklet.experimental.browser import BrowserFigure, BrowserScatter, ScatterView
    from inklet.selection import KeyedTable
    table = KeyedTable("t", dict(id=["a", "b"], x=[0, 1], y=[1, 0]))
    views = [ScatterView("p", "x", "y", (0, 1), (0, 1))]
    legacy, seen = caught(lambda: BrowserScatter(table, views))
    one_deprecation(seen, mentions=("BrowserFigure(table, views, columns=len(views))",))
    figure, seen = caught(lambda: BrowserFigure(table, views, columns=len(views)))
    assert seen == []
    assert isinstance(legacy, BrowserFigure)


# -- release gate --------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["api-3.1.json", "api-4.2.json"])
def test_the_compatibility_checker_passes_with_every_alias_in_place(fixture):
    spec = importlib.util.spec_from_file_location("compatibility_checker_44", ROOT / "tools/check_compatibility.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    baseline = json.loads((ROOT / "tests/fixtures/compatibility" / fixture).read_text())
    assert checker.check(baseline)[1] == []
