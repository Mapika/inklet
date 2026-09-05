"""The electrolyser poster: twelve panels, one sheet, every modality at once.

A single experiment told twelve ways -- a 3D exploded assembly, a crystal
structure, two micrographs, six data panels, a carbon balance, a process loop
and an operando waterfall -- composed onto one sheet with the caption set in
the last column. Nothing here places a panel by coordinate: each module
returns a diagram of an exact width and this file decides only which column it
starts in and how many it spans.

What it is for. `mega_figure` asked whether the library could draw eighteen
unrelated things; this one asks whether it can draw one thing consistently.
Every panel's numbers come from `electro/data.py`, so the Faradaic efficiency
in (e) is the carbon flux in (i) is the plateau in (k), and a species is the
same colour wherever it appears. A figure that cannot hold that together is a
collage with a shared font.

Why a poster and not a journal page. Twelve panels of this weight need about
0.14 m^2; a 183 x 247mm page holds a third of that. Rather than shrink each
panel until its axis labels collide, the sheet is the size the content asks
for -- four columns of 87mm, which is the width every panel was designed at.

    .venv/bin/python stress/electro_figure.py            # build, lint, save
    .venv/bin/python stress/electro_figure.py --measure  # sizes only
    scripts/rasterise.sh stress/electro_figure.svg stress/electro_figure.png 2
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import inklet
from electro import cell, common, imaging, kinetics, system

# -- the grid -------------------------------------------------------------
#
# Four columns at the width the panels were drawn for, each preceded by a lane
# wide enough for its letter. A panel spanning n columns swallows the lanes and
# gaps between them, which is what keeps every column edge on the same x
# whether the row above it holds one panel or four.

COLUMN = common.COLUMN          # 87mm: the width every panel builder defaults to
COLUMNS = 4
GAP = 6.0                       # between columns
ROW_GAP = 7.0                   # between bands
LETTER_BOX = 3.2                # the lane the panel letter sits in
LETTER_GAP = 1.4                # lane to panel
LANE = LETTER_BOX + LETTER_GAP
MARGIN = 6.0


def span(columns: int) -> float:
    """The width of a panel that covers `columns` of them."""
    return columns * COLUMN + (columns - 1) * (LANE + GAP)


CONTENT_WIDTH = COLUMNS * (LANE + COLUMN) + (COLUMNS - 1) * GAP
PAGE_WIDTH = CONTENT_WIDTH + 2 * MARGIN

TITLE = ("A CO_{2}-to-C_{2}H_{4} gas-diffusion electrolyser: "
         "catalyst structure, operando transformation, and a 500-hour pilot run")

#: Letter, builder, and how many columns it spans -- in reading order, which is
#: also the order the story is told in. The module a panel comes from is an
#: implementation detail; its letter is what the caption and the page agree on.
PANELS = [
    ("a", cell.panel_a, 2),         # exploded flow cell, 3D line art
    ("b", cell.panel_b, 1),         # Cu2O cuprite unit cell
    ("c", imaging.panel_c, 1),      # SEM field with HR-TEM inset
    ("d", imaging.panel_d, 1),      # particle size distribution
    ("e", kinetics.panel_e, 1),     # Faradaic efficiency vs potential
    ("f", kinetics.panel_f, 1),     # Tafel plot
    ("g", kinetics.panel_h, 1),     # operando FTIR
    ("h", kinetics.panel_g, 2),     # operando XRD waterfall
    ("i", system.panel_i, 1),       # carbon balance
    ("j", system.panel_l, 1),       # cyclic voltammograms vs loading
    ("k", system.panel_j, 2),       # 500 h stability run
    ("l", system.panel_k, 1),       # the pilot loop
]

#: Which letters share a band. Every band spans exactly `COLUMNS` columns; the
#: caption is a cell like any other and takes the slot the loop leaves open.
BANDS = [
    ("a", "b", "c"),
    ("d", "e", "f", "g"),
    ("h", "i", "j"),
    ("k", "l", "caption"),
]

#: The caption. Subscripts throughout, and the acknowledgement is set in five
#: scripts -- Latin, Greek, Cyrillic, Japanese and Arabic -- because a caption
#: is where a figure's typesetting is most likely to be asked for a font it
#: does not have, and the fallback path should be exercised on the page rather
#: than only in a unit test.
#:
#: The panel letters are bold and `operando` is italic, both inline: `**...**`
#: and `//...//` are measured in the real bold and italic faces of the family,
#: so the justified column is wrapped against the type it will actually draw.
#: A lone `*` is left alone, which is why the adsorbed `*CO` below needs no
#: escape.
CAPTION = (
    "**Figure 1.** **(a)** Exploded view of the flow cell: gas-diffusion "
    "electrode, catholyte channel, anion-exchange membrane and anode. "
    "**(b)** Cu_{2}O nanocube catalyst in the cuprite structure, a = 0.427 nm. "
    "**(c)** Secondary-electron image of the as-deposited layer, with a lattice "
    "image of one particle inset; the ring marks the particle the inset "
    "zooms into. **(d)** Edge lengths measured over the field in (c), with a "
    "lognormal fit. **(e)** Faradaic efficiency against applied potential. "
    "**(f)** The same currents as a Tafel plot, with the mass-transport limit "
    "shaded. **(g)** //Operando// FTIR over the same sweep; the *CO band grows "
    "in before C_{2}H_{4} appears. **(h)** //Operando// XRD through the first "
    "150 min of electrolysis: Cu_{2}O reduces to metallic Cu. **(i)** Carbon "
    "balance at −1.08 V. **(j)** Cyclic voltammograms against catalyst "
    "loading. **(k)** A 500 h run at 200 mA cm^{−2}, with two electrolyte "
    "flushes marked. **(l)** The pilot loop the run was made in. "
    "Simulated data throughout: the cell, the catalyst and the run are "
    "inventions, generated by stress/electro/data.py to exercise the drawing "
    "library."
)

ACKNOWLEDGEMENT = "Typeset by inklet — δοκιμή · проверка · 組版試験 · اختبار"


def build_panels(only: set[str] | None = None) -> dict[str, inklet.Diagram]:
    built: dict[str, inklet.Diagram] = {}
    for letter, make, columns in PANELS:
        if only and letter not in only:
            continue
        started = time.perf_counter()
        want = span(columns)
        built[letter] = make(want)
        box = built[letter].bbox
        flag = "" if abs(box.width - want) < 0.05 else f"  !! asked for {want:.1f}"
        print(f"  {letter}  {box.width:6.1f} x {box.height:6.1f} mm   "
              f"{(time.perf_counter() - started) * 1000:7.0f} ms   "
              f"{sum(1 for _ in built[letter].walk()):6} nodes{flag}")
    return built


def lettered(letter: str, panel: inklet.Diagram) -> inklet.Diagram:
    """The panel letter in its own lane, left of the panel's top-left corner.

    The lane is padded to a fixed width rather than shrink-wrapped, so that
    'l' and 'm' start their panels at the same x and the columns line up.
    """
    tag = inklet.text(letter, size=inklet.pt(9), font_weight="bold", kind="panel-letter")
    lane = inklet.hstack([tag, inklet.spacer(width=max(0.0, LETTER_BOX - tag.bbox.width))],
                      align="top")
    return inklet.hstack([lane, panel], gap=LETTER_GAP, align="top")


def caption_cell(theme) -> inklet.Diagram:
    """The caption, set to one column, to be placed like a panel."""
    return inklet.vstack([
        inklet.text(CAPTION, size=theme.font_size_small, width=COLUMN,
                 align="justify", kind="caption"),
        inklet.label(ACKNOWLEDGEMENT, align="left"),
    ], gap=theme.gap("m"), align="left")


def compose(built: dict[str, inklet.Diagram]) -> inklet.Diagram:
    """Bands of cells, each band exactly `CONTENT_WIDTH` across."""
    theme = inklet.current_theme()
    rows: list[inklet.Diagram] = [
        inklet.text(TITLE, size=theme.font_size_large, font_weight="bold",
                 width=CONTENT_WIDTH, align="center", kind="figure-title"),
    ]
    for band in BANDS:
        cells: list[inklet.Diagram] = []
        for letter in band:
            if letter == "caption":
                cells.append(inklet.hstack(
                    [inklet.spacer(width=LETTER_BOX), caption_cell(theme)],
                    gap=LETTER_GAP, align="top"))
            elif letter in built:
                cells.append(lettered(letter, built[letter]))
        if cells:
            rows.append(inklet.hstack(cells, gap=GAP, align="top"))
    return inklet.vstack(rows, gap=ROW_GAP, align="left")


def main() -> int:
    inklet.use_theme("nature")
    print("building panels")
    started = time.perf_counter()
    built = build_panels()
    print(f"  {len(built)} panels in {time.perf_counter() - started:.1f}s")

    content = compose(built)
    box = content.bbox
    print(f"\ncomposed: {box.width:.1f} x {box.height:.1f} mm "
          f"(content width should be {CONTENT_WIDTH:.1f})")
    if "--measure" in sys.argv:
        return 0

    fig = inklet.figure(width=f"{PAGE_WIDTH}mm", margin=MARGIN)
    fig.add(content)
    fig.save("stress/electro_figure.svg")
    page = fig.page_rect(box)
    print(f"page: {page.width:.1f} x {page.height:.1f} mm")
    print(fig.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
