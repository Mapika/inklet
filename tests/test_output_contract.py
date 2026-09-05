"""What leaves the library: `Figure.save`, the id an SVG is committed with,
the notes an annotation rides on, and the grid gap a rule is allowed to forgive.

Each test here is a promise about the *output* side of `inklet` -- the file a
paper actually ships, or the committed corpus file a diff is read against --
rather than about the geometry that goes into it.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

import inklet
from inklet.core import Diagram, RectPrim
from inklet.render import PDF_TEXT_MODES, TEXT_MODES

ROOT = Path(__file__).resolve().parent.parent


def figure_with_text(words: str = "Searchable text") -> inklet.Figure:
    fig = inklet.figure(width="80mm")
    fig.add(inklet.text(words))
    return fig


# -- text= reaches the PDF ------------------------------------------------


def test_save_carries_the_text_mode_into_the_pdf(tmp_path) -> None:
    """`fig.save("f.svg", "f.pdf", text="embed")` embeds in *both* files.

    The one call a paper wants: the PDF to submit and the SVG to keep editing,
    both searchable, from one build. `save` used to strip `text=` before
    reaching `to_pdf`, which was right while PDF had one text mode and became
    a keyword that was accepted and silently dropped.
    """
    fig = figure_with_text()
    fig.save(tmp_path / "f.svg", tmp_path / "f.pdf", text="embed")

    assert b"FontFile" in (tmp_path / "f.pdf").read_bytes()
    assert "@font-face" in (tmp_path / "f.svg").read_text()


def test_a_pdf_outlines_unless_it_is_told_otherwise(tmp_path) -> None:
    fig = figure_with_text()
    fig.save(tmp_path / "plain.pdf")

    assert b"FontFile" not in (tmp_path / "plain.pdf").read_bytes()


def test_names_is_an_svg_answer_and_leaves_the_pdf_outlined(tmp_path) -> None:
    """`"names"` is a question PDF does not ask, so the PDF takes the safe
    reading of "I did not think about the PDF" and outlines, while the SVG
    gets the live `<text>` it asked for. The alternative -- raising -- would
    make the default SVG mode unusable in a two-target save."""
    fig = figure_with_text()
    fig.save(tmp_path / "n.svg", tmp_path / "n.pdf", text="names")

    assert b"FontFile" not in (tmp_path / "n.pdf").read_bytes()
    assert "<text" in (tmp_path / "n.svg").read_text()


def test_an_unknown_text_mode_is_refused_before_any_file_is_written(tmp_path):
    """...rather than at whichever target happens to come first in the list."""
    fig = figure_with_text()
    with pytest.raises(ValueError, match="unknown text mode"):
        fig.save(tmp_path / "a.svg", tmp_path / "b.pdf", text="Embed")

    assert not (tmp_path / "a.svg").exists()


def test_to_pdf_takes_the_two_modes_pdf_has_and_refuses_the_third() -> None:
    """The mode is spelled out on `Figure.to_pdf` rather than passed through
    `**kwargs`, so the reference lists it beside `to_svg`'s three and a typo
    is refused with the figure's own name on the traceback."""
    fig = figure_with_text()
    for mode in PDF_TEXT_MODES:
        assert fig.to_pdf(text=mode).startswith(b"%PDF")
    with pytest.raises(ValueError, match="no font-name mode"):
        fig.to_pdf(text="names")


def test_the_two_mode_tuples_say_what_the_docstrings_say() -> None:
    assert TEXT_MODES == ("names", "outline", "embed")
    assert PDF_TEXT_MODES == ("outline", "embed")
    assert set(PDF_TEXT_MODES) < set(TEXT_MODES)


# -- the docstrings a reference is generated from -------------------------


#: Every output entry point whose docstring is the reference for `text=`.
_OUTPUT_DOCS = [
    inklet.to_svg, inklet.save_svg, inklet.to_pdf, inklet.save_pdf,
    inklet.Figure.to_svg, inklet.Figure.to_pdf, inklet.Figure.save,
]


@pytest.mark.parametrize("func", _OUTPUT_DOCS, ids=lambda f: f.__qualname__)
def test_no_output_docstring_advertises_a_features_argument(func) -> None:
    """`features=` was removed from the backends and lingered in their prose.

    A block is shaped under the features it was *measured* with and carries
    them itself, so the place to pass them is `inklet.text`. A docstring that
    names `features` as an argument of the backend sends a reader looking for
    a keyword that raises `TypeError`.
    """
    doc = func.__doc__ or ""
    assert not re.search(r"`features`\s*argument", doc)
    assert "features=" not in doc


@pytest.mark.parametrize("func", _OUTPUT_DOCS, ids=lambda f: f.__qualname__)
def test_no_output_docstring_says_pdf_always_outlines(func) -> None:
    """PDF has had a live-text mode since round 3; three docstrings still said
    it did not, which is worse than saying nothing."""
    doc = " ".join((func.__doc__ or "").split())
    for lie in ("Text is outlined, so", "PDF always outlines",
                "ignores the keyword"):
        assert lie not in doc


def test_the_save_docstring_states_what_text_means_for_each_format() -> None:
    doc = " ".join((inklet.Figure.save.__doc__ or "").split())
    assert "embed" in doc and "outline" in doc and "names" in doc
    assert "no font-name mode" in doc


# -- one writer per committed SVG -----------------------------------------


def _save_targets() -> dict[str, list[str]]:
    """{committed svg path: the scripts that write it}, read out of the source.

    Static rather than executed: the point is to catch a *second* writer being
    added, and running the corpus to find that out takes four minutes.
    """
    targets: dict[str, list[str]] = defaultdict(list)
    scripts = sorted(
        set(ROOT.glob("examples/*.py")) | set(ROOT.glob("stress/*.py"))
        | set(ROOT.glob("stress/electro/*.py")) | set(ROOT.glob("figures/*.py"))
    )
    for script in scripts:
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None)
            if name not in ("save", "save_svg"):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value.endswith(".svg"):
                        targets[arg.value].append(
                            str(script.relative_to(ROOT)))
    return targets


def test_no_committed_svg_is_written_by_two_scripts() -> None:
    """Node ids are sequential per process, so an SVG's ids depend on how many
    `Diagram`s were built before it was saved -- which is deterministic per
    entry point and nothing else.

    `stress/electro/cell.svg` was the case that taught this: a file saved from
    two scripts churns its ids on every full-corpus render and gets committed
    back and forth. The counter cannot be reset at `Figure.save`, because by
    then every id has been handed out; one writer per file is the property
    that actually holds.
    """
    duplicated = {path: writers
                  for path, writers in _save_targets().items()
                  if len(writers) > 1}
    assert duplicated == {}


def test_the_electro_panels_are_saved_by_their_own_modules() -> None:
    """The poster composes the panels; it does not re-save their sheets."""
    targets = _save_targets()
    assert targets["stress/electro/kinetics.svg"] == ["stress/electro/kinetics.py"]
    assert targets["stress/electro_figure.svg"] == ["stress/electro_figure.py"]


# -- an annotation rides on notes, not on an attribute --------------------


def test_a_declared_domain_survives_a_restyle_without_being_named() -> None:
    """`scale_domain` is a note, so `replace` carries it and `apply_theme` has
    no line about it. It used to be an instance attribute as well, and that
    attribute was the only reason `apply_theme` had a by-name hand-copy."""
    from inklet.plot import colorbar, ramp as make_ramp
    from inklet.plot.scale import linear

    bar = colorbar(make_ramp(("#ffffff", "#000000")), scale=linear((0.0, 100.0)))
    assert bar.notes["scale_domain"] == (0.0, 100.0)
    assert not hasattr(bar, "scale_domain")

    restyled = inklet.figure(width="80mm")
    restyled.add(bar)
    built, _ = restyled.build()
    carried = [n for n in built.walk()
               if getattr(n, "notes", {}).get("scale_domain") is not None]
    assert carried, "the note did not survive apply_theme"


def test_the_plot_layer_stamps_no_attributes_on_a_diagram() -> None:
    """Whatever `inklet.plot` records about a node goes in `notes`. An attribute
    on a frozen dataclass does not survive `replace`, which is every rebuild.
    """
    from inklet.plot import panel, ramp as make_ramp
    from inklet.plot.scale import linear

    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 5.0, 10.0]], ramp=make_ramp(("#ffffff", "#000000")),
             scale=linear((0.0, 10.0)))
    for node in p.build().walk():
        stray = set(vars(node)) - {f for f in vars(Diagram(kind="probe"))}
        assert stray == set(), f"{node.kind} carries {stray}"


# -- a grid's two gaps ----------------------------------------------------


def grid_cells(count: int = 4, **kwargs) -> inklet.Diagram:
    cells = [Diagram(prim=RectPrim(8.0, 5.0), kind="box")
             .styled(fill="#cccccc").named(f"c{i}") for i in range(count)]
    return inklet.grid(cells, **kwargs)


def crowded_pairs(node: inklet.Diagram) -> list[str]:
    fig = inklet.figure(width=60)
    fig.add(node)
    return sorted(d.message.split(" are only")[0]
                  for d in fig.lint() if d.code == "CROWDING")


def test_a_grid_forgives_its_own_two_gaps_and_nothing_else() -> None:
    """Both declared gaps are under the 1mm clearance, so all four
    grid-adjacent pairs would be findings if the grid had not asked for them.

    The two diagonals are not the grid's doing: nothing declares the distance
    across a corner, so they stay findings. `c1`/`c2` is the pair that makes
    the point -- one apart in the child list, and on opposite corners of the
    grid because the row wrapped between them. A one-dimensional adjacency
    test forgives it; this one must not.
    """
    grid = grid_cells(4, cols=2, col_gap=0.5, row_gap=0.6)

    assert grid.notes["grid_cells"] == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert (grid.notes["col_gap"], grid.notes["row_gap"]) == (0.5, 0.6)
    assert crowded_pairs(grid) == ["c0 and c3", "c1 and c2"]


def test_the_column_gap_is_not_checked_against_the_row_gap() -> None:
    """The older `gap` note is `min` of the two, and reading it for a
    horizontal pair reports the row spacing as the column's intent. Here the
    columns are 0.9mm apart and the rows 0.3mm; a rule reading `gap` would
    forgive neither pair, because neither distance is 0.3mm across.
    """
    grid = grid_cells(4, cols=2, col_gap=0.9, row_gap=0.3)

    assert grid.notes["gap"] == 0.3
    assert crowded_pairs(grid) == ["c0 and c3", "c1 and c2"]


def test_a_grid_that_records_no_cells_reports_every_close_pair() -> None:
    """The no-op the rule has to degrade to. A tree built before
    `layout/flow.py` wrote these notes -- or by hand, or by an older version
    -- carries no `grid_cells`, and the rule then forgives nothing rather than
    guessing an adjacency it cannot see.
    """
    grid = grid_cells(4, cols=2, col_gap=0.5, row_gap=0.6)
    for key in ("grid_cells", "grid_shape", "col_gap", "row_gap"):
        grid.notes.pop(key, None)

    assert crowded_pairs(grid) == [
        "c0 and c1", "c0 and c2", "c0 and c3", "c1 and c2",
        "c1 and c3", "c2 and c3",
    ]


def test_a_grid_declaration_does_not_reach_inside_one_cell() -> None:
    """The grid separates cells; it says nothing about two things in one.

    `col_gap` is the distance between neighbouring cells and is not a licence
    for whatever is crowded inside either of them. Same shape as the stack
    rule's `test_a_declaration_does_not_reach_inside_one_child`, and the
    reason `_slots_under` compares the two items' *cells* rather than just
    finding the grid overhead.
    """
    def box(name: str) -> inklet.Diagram:
        return (Diagram(prim=RectPrim(3.0, 5.0), kind="box")
                .styled(fill="#cccccc").named(name))

    crowded_cell = Diagram(kind="g", children=(
        box("left"), box("right").translated(3.3, 0.0)))
    rest = [Diagram(prim=RectPrim(8.0, 5.0), kind="box")
            .styled(fill="#cccccc").named(f"c{i}") for i in range(1, 4)]
    grid = inklet.grid([crowded_cell, *rest], cols=2, col_gap=2.0, row_gap=2.0)

    assert crowded_pairs(grid) == ["left and right"]
