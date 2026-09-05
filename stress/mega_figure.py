"""The real stress figure: eighteen panels, one page, every modality at once.

`hard_figure` was a normal methods figure -- boxes, arrows, a raster, a
heatmap -- and it only ever asked the engine to do the thing it already did.
This one asks for eighteen things it had no idiom for, on one 183x247mm page,
at journal density: a 3D optical path, a hidden-line brain, a bitmap
composite, filled anatomy with hatching, a Gantt, calcium traces, ten thousand
spikes, a heatmap, a polar tuning plot, violins, a Sankey, a chord diagram, a
dendrogram, a network graph, a state machine, a contour field, and a caption
in six scripts including two the text engine is known to get wrong.

Every panel is built by a function in `stress/panels/` that takes a width and
returns a `Diagram`. None of them knows where on the page it will land, and
none of them is allowed a hardcoded layout coordinate. This file is the only
thing that decides composition -- which is the point: if the panels have to be
nudged into place by hand, the layout engine has failed, and that is a finding
rather than a patch.

    .venv/bin/python stress/mega_figure.py            # build, lint, save
    .venv/bin/python stress/mega_figure.py --measure  # just report the sizes
    .venv/bin/python stress/mega_figure.py --split    # one sheet per page
    .venv/bin/python stress/mega_figure.py --split --pdf   # ...and one PDF
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import inklet
from panels import apparatus, graphs, relations, responses, sections

PAGE_WIDTH = 183.0
PAGE_HEIGHT = 247.0

FULL = 178.0
COLUMN = 84.0
NARROW = 56.0

#: Panel letter, the function that builds it, and the width it is built at.
PANELS = [
    ("a", apparatus.panel_a, FULL),
    ("b", apparatus.panel_b, COLUMN),
    ("c", apparatus.panel_c, COLUMN),
    ("d", sections.panel_d, COLUMN),
    ("e", sections.panel_e, COLUMN),
    ("f", sections.panel_f, COLUMN),
    ("g", responses.panel_g, FULL),
    ("h", responses.panel_h, COLUMN),
    ("i", responses.panel_i, COLUMN),
    ("j", relations.panel_j, COLUMN),
    ("k", responses.panel_k, COLUMN),
    ("l", relations.panel_l, COLUMN),
    ("m", relations.panel_m, COLUMN),
    ("n", relations.panel_n, COLUMN),
    ("o", graphs.panel_o, COLUMN),
    ("p", graphs.panel_p, COLUMN),
    ("q", sections.panel_q, COLUMN),
    ("r", graphs.panel_r, NARROW),
]

#: Panels that span the page. Everything else flows into columns between them.
FULL_WIDTH = {"a", "g"}

GAP = 4.0
ROW_GAP = 5.0

def build_panels(only: set[str] | None = None) -> dict[str, inklet.Diagram]:
    built: dict[str, inklet.Diagram] = {}
    for letter, make, width in PANELS:
        if only and letter not in only:
            continue
        started = time.perf_counter()
        built[letter] = make(width)
        elapsed = time.perf_counter() - started
        box = built[letter].bbox
        print(f"  {letter}  {box.width:6.1f} x {box.height:6.1f} mm   "
              f"{elapsed * 1000:7.0f} ms   {_nodes(built[letter]):6} nodes")
    return built


def _nodes(node: inklet.Diagram) -> int:
    return sum(1 for _ in node.walk())


def lettered(letter: str, panel: inklet.Diagram) -> inklet.Diagram:
    """The panel letter hanging outside its top-left corner.

    `align="top"` rather than a computed offset: the letters line up because
    the columns line up, not because anyone measured them.
    """
    tag = inklet.text(letter, size=inklet.pt(9), font_weight="bold", kind="panel-letter")
    return inklet.hstack([tag, panel], gap=1.2, align="top")


def compose(built: dict[str, inklet.Diagram], columns: int = 2,
            letters: list[str] | None = None) -> inklet.Diagram:
    """Full-width panels break the page into bands; the rest flow inside them.

    `inklet.flow` is the layout this figure asked the library to grow. Row-major
    `grid` costs the height of the tallest panel in every row, which across
    eighteen panels of assorted heights threw away 127mm -- half a page -- on
    white bands under the short ones.
    """
    order = letters if letters is not None else [l for l, _, _ in PANELS]
    bands: list[inklet.Diagram] = []
    run: list[inklet.Diagram] = []
    for letter in order:
        if letter not in built:
            continue
        node = lettered(letter, built[letter].copy())
        if letter in FULL_WIDTH:
            if run:
                bands.append(inklet.flow(run, columns=columns, gap=GAP))
                run = []
            bands.append(node)
        else:
            run.append(node)
    if run:
        bands.append(inklet.flow(run, columns=columns, gap=GAP))
    return inklet.vstack(bands, gap=ROW_GAP, align="left")


def paginate(built: dict[str, inklet.Diagram], columns: int = 2,
             page_height: float = PAGE_HEIGHT) -> list[list[str]]:
    """Cut the panel run into sheets that each fit the page.

    Contiguous and in reading order. Packing across sheets would fit tighter --
    q is short and would happily sit beside b -- but a figure whose panels run
    a, b, f, c is a different figure, and this is the one operation where the
    layout engine is not allowed to be clever.

    Adding a panel can only make a composition taller, so the greedy scan finds
    the fewest sheets for this ordering.
    """
    sheets: list[list[str]] = []
    current: list[str] = []
    for letter, _, _ in PANELS:
        if letter not in built:
            continue
        if current and compose(built, columns, current + [letter]).bbox.height > page_height:
            sheets.append(current)
            current = [letter]
        else:
            current.append(letter)
    if current:
        sheets.append(current)
    return sheets


def save(content: inklet.Diagram, path: str) -> inklet.Figure:
    fig = inklet.figure(width=f"{PAGE_WIDTH}mm")
    fig.add(content)
    fig.save(path)
    return fig


def main() -> int:
    measure = "--measure" in sys.argv
    split = "--split" in sys.argv
    want_pdf = "--pdf" in sys.argv
    print("building panels")
    started = time.perf_counter()
    built = build_panels()
    print(f"  {len(built)} panels in {time.perf_counter() - started:.1f}s")

    content = compose(built)
    box = content.bbox
    print(f"\ncomposed: {box.width:.1f} x {box.height:.1f} mm "
          f"(page is {PAGE_WIDTH} x {PAGE_HEIGHT})")
    over = box.height - PAGE_HEIGHT
    if over > 0:
        need, have = column_budget(built)
        print(f"  OVER by {over:.1f} mm -- the panels want {need:.0f}mm of "
              f"column and one page has {have:.0f}mm, so this is "
              f"{need / have:.2f} pages. Run --split.")
    if measure:
        return 0

    if split:
        sheets = paginate(built)
        figures = []
        for number, letters in enumerate(sheets, start=1):
            sheet = compose(built, letters=letters)
            path = f"stress/mega_figure_{number}.svg"
            fig = save(sheet, path)
            figures.append(fig)
            print(f"\nsheet {number}/{len(sheets)}: {''.join(letters)} -- "
                  f"{sheet.bbox.width:.1f} x {sheet.bbox.height:.1f} mm -> {path}")
            print(fig.report())
        if want_pdf:
            # One file, one page per sheet: `save_pdf` takes a list of roots
            # and shares the images and the alpha states across all of them,
            # which is most of what eighteen panels of raster weigh.
            out = "stress/mega_figure.pdf"
            inklet.save_pdf([fig.build()[0] for fig in figures], out, margin=0.0,
                         background=figures[0].theme.paper)
            print(f"\n{len(figures)} pages -> {out} "
                  f"({Path(out).stat().st_size:,} bytes)")
        return 0

    fig = save(content, "stress/mega_figure.svg")
    print(fig.report())
    return 0


def column_budget(built: dict[str, inklet.Diagram],
                  columns: int = 2) -> tuple[float, float]:
    """(column length these panels need, column length one page has).

    A page offers `columns` runs of `PAGE_HEIGHT`. A full-width panel spends
    its height out of *every* column at once, which is why two of them cost
    more than their 105mm looks like. This is the arithmetic that decides
    whether any packing can fit, before trying one.
    """
    need = sum(built[l].bbox.height * (columns if l in FULL_WIDTH else 1)
               for l in built)
    return need, columns * PAGE_HEIGHT


if __name__ == "__main__":
    raise SystemExit(main())
