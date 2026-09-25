"""Render the palette swatch sheets used by docs/palettes.md.

    .venv/bin/python tools/palette_sheet.py              # docs/assets/palettes/*.svg + .png
    .venv/bin/python tools/palette_sheet.py --out DIR    # somewhere else

Each sheet is drawn by Inklet itself. Categorical palettes get one square per
colour, followed by the same squares as a deuteranope, protanope and
tritanope see them (Machado et al. 2009, full severity) and in greyscale.
Ramps get a continuous strip interpolated in OKLab, with the same four
previews as thinner strips. The PNGs need the `render` extra.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import inklet as i  # noqa: E402
from inklet.core import Diagram, PhantomPrim, Rect, RectPrim, Style  # noqa: E402
from inklet.themes import Palette, palette, palette_names  # noqa: E402

LABEL = 30.0        # label column, mm
SQUARE = 5.0        # categorical swatch, mm
STRIP = 96.0        # ramp strip length, mm
SLICES = 48        # gradient stops per strip
VIEWS = (("deuteranopia", "deutan"), ("protanopia", "protan"),
         ("tritanopia", "tritan"), ("grey", "grey"))


def _rect(w: float, h: float, fill: str) -> Diagram:
    return Diagram(prim=RectPrim(w, h), style=Style(fill=fill, stroke="none"))


def _label(text: str, size: float, muted: bool = False) -> Diagram:
    """Text left-aligned in a fixed-width column, so every row's swatches
    start at the same x."""
    words = i.text(text, size=size, markup=False,
                   **({"text_fill": "#6b7280"} if muted else {}))
    column = Diagram(prim=PhantomPrim(Rect(0, 0, LABEL, words.height)))
    return i.overlay([column, words], align="w")


def _squares(colors, size: float) -> Diagram:
    return i.hstack([_rect(size, size, c) for c in colors], gap=size * 0.12)


def _strip(p: Palette, height: float, length: float = STRIP) -> Diagram:
    """The ramp as one rectangle painted with a vector gradient. Its stops
    are the ramp sampled in OKLab, dense enough that the renderer's sRGB
    blend between neighbours is indistinguishable from the ramp itself."""
    stops = [(k / (SLICES - 1), p.ramp(k / (SLICES - 1), "oklab"))
             for k in range(SLICES)]
    return i.paint(_rect(length, height, stops[0][1]), i.LinearGradient(stops))


def _view(p: Palette, view: str) -> Palette:
    return p.greyscale() if view == "grey" else p.cvd(view)


def row(p: Palette, previews: bool = True) -> Diagram:
    title = _label(p.name, 2.6)
    if p.notes.startswith("discrete"):
        # Tol's rainbow: ordered, but not to be interpolated. Abutting
        # swatches spanning the strip show it as the steps it is.
        width = STRIP / len(p)
        main = i.hstack([_rect(width, 5.0, c) for c in p.colors], gap=0)
        extra = [i.hstack([_rect((STRIP - 3 * 2.4) / 4 / len(p), 1.6, c)
                           for c in _view(p, v).colors], gap=0) for v, _ in VIEWS]
    elif p.is_ramp:
        main = _strip(p, 5.0)
        extra = [_strip(_view(p, v), 1.6, (STRIP - 3 * 2.4) / 4) for v, _ in VIEWS]
    else:
        main = _squares(p.colors, SQUARE)
        extra = [_squares(_view(p, v).colors, SQUARE * 0.45) for v, _ in VIEWS]
    body = [i.hstack([title, main], gap=2.0, align="center")]
    if previews:
        tags = _label("  ·  ".join(t for _, t in VIEWS), 1.8, True)
        body.append(i.hstack([tags, i.hstack(extra, gap=2.4, align="center")],
                             gap=2.0, align="center"))
    return i.vstack(body, gap=0.8, align="left")


def sheet(palettes, previews: bool = True) -> Diagram:
    rows = [row(p if isinstance(p, Palette) else palette(p), previews) for p in palettes]
    return i.vstack(rows, gap=3.2, align="left")


SHEETS = {
    "inklet": ("inklet", "inklet-muted", "inklet-pairs", "inklet-duo",
               "okabe-ito", "tol-bright", "tol-muted"),
    "categorical": tuple(n for n in palette_names("categorical")
                         if not n.startswith("inklet")),
    "sequential": palette_names("sequential"),
    "diverging": palette_names("diverging"),
    "cyclic": palette_names("cyclic"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "assets" / "palettes")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, members in SHEETS.items():
        if args.only and name not in args.only:
            continue
        drawing = sheet(members, previews=name in ("inklet", "categorical", "cyclic")
                        or len(members) < 30)
        svg = args.out / f"{name}.svg"
        i.save_svg(drawing, str(svg), margin=3.0, background="#ffffff",
                   title=f"Inklet palettes: {name}")
        i.save_png(drawing, args.out / f"{name}.png", dpi=args.dpi, margin=3.0,
                   background="#ffffff")
        print(f"wrote {svg} and .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
