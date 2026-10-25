"""A house style for a figure set: one suite, one multi-panel journal figure.

`HOUSE` states the style once:
- Helvetica-class type at 6/7 pt, with 8 pt bold panel letters;
- two data line weights (0.6 pt data, 0.75 pt fits) over 0.5 pt axes;
- filled markers without outlines;
- a categorical group palette and two sequential ramps (dose, sample size);
- direct labels instead of keys, and no grey or bold annotation text;
- 89/183 mm widths;
- export as SVG, PDF and PNG with embedded live text.

The figure below is drawn only through it. All data are synthetic.

    PYTHONPATH=src .venv/bin/python examples/house_style.py

writes out/house-style/dose_response.{svg,pdf,png} and prints the lint report
(journal limits and house rules). It then builds the same figure again through
`HOUSE.build`, which skips it because nothing changed. `--gallery` writes
gallery/house-style.png.
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import inklet as i

ROOT = Path(__file__).resolve().parents[1]

# -- the house style, stated once --------------------------------------------------

HOUSE = i.suite(
    "lab",
    base="scientific.nature",
    font="Helvetica, Arial, Nimbus Sans, Liberation Sans, sans-serif",
    allowed_fonts=("Helvetica", "Arial", "Nimbus Sans", "Liberation Sans"),
    ink="#222222",
    type=dict(tick=6, label=7, key=6, note=6, letter=8),
    lines=dict(data=0.6, fit=0.75, axis=0.5),
    markers=dict(size=0.9, outline=False, ring=0.3),
    text=dict(bold="letters", muted=False, muted_colors=("#888888",), keys="outside"),
    palettes={"group": {"control": "#555555", "treated A": "#0072b2", "treated B": "#d55e00",
                        "treated C": "#009e73"},
              "neutral": {"ink": "#222222", "rule": "#cccccc"}},
    ramps={"dose": "tol-ylorbr",
           "size": {"n = 10": "#c6dbef", "n = 30": "#6baed6", "n = 100": "#2171b5", "n = 300": "#08306b"}},
)

DOSES = (0.1, 1.0, 10.0, 100.0)     # concentration, µM


def dose_color(c):
    """Concentration on the dose ramp, log scale from 0.1 (light) to 100 µM (dark)."""
    return HOUSE.ramp("dose")(0.35 + 0.6 * (math.log10(c) + 1) / 3)


# -- panels --------------------------------------------------------------------------


def response(w, h):
    """a: response over time at four concentrations, labelled at the line ends."""
    p = HOUSE.panel(w, h, x=(0, 24), y=(0, 1.0))
    HOUSE.axes(p, x="time (h)", y="response", x_options=dict(ticks=[0, 6, 12, 18, 24]))
    ends = {}
    for c in DOSES:
        half = 16 - 3 * math.log10(c)
        pts = [(t, 0.05 + 0.85 / (1 + math.exp(-(t - half) / 2.2))) for t in range(0, 25)]
        p.line(pts, **HOUSE.line(dose_color(c)))
        p.scatter(pts[::4], **HOUSE.mark(dose_color(c)))
        ends[f"{c:g} µM"] = pts[-1]
    HOUSE.end_labels(p, ends, colors={f"{c:g} µM": dose_color(c) for c in DOSES}, dx=0.8)
    p.hline(0.5, stroke=HOUSE.color("rule"), stroke_width=HOUSE.stroke("data"), dash="dashed")
    return p


def calibration(w, h):
    """b: measured against reference for three instruments, y = x as the fit."""
    rng = random.Random(4)
    p = HOUSE.panel(w, h, x=(0, 10), y=(0, 10))
    HOUSE.axes(p, x="reference value", y="measured value")
    p.line([(0, 0), (10, 10)], **HOUSE.line("ink", "fit"))
    shapes = {"treated A": "circle", "treated B": "square", "treated C": "diamond"}
    for k, (group, shape) in enumerate(shapes.items()):
        pts = [(x, x + rng.gauss(0, 0.35)) for x in (rng.uniform(0.5, 9.5) for _ in range(14))]
        p.scatter(pts, marker=shape, **HOUSE.mark(group))
        p.text(0.4, 9.4 - 0.9 * k, group, anchor="w", size=HOUSE.size("note"),
               text_fill=HOUSE.text_color(group), markup=False)
    return p


def precision(w, h):
    """c: estimate spread against sample size, coloured by the size ramp; open markers are pilot runs."""
    rng = random.Random(7)
    sizes = HOUSE.stops("size")
    p = HOUSE.panel(w, h, x=i.log((5, 500)), y=(0, 1.2))
    HOUSE.axes(p, x="sample size n", y="standard error",
               x_options=dict(ticks=[10, 100], format=lambda v: f"{v:g}"))
    p.line([(n, 3 / math.sqrt(n)) for n in [7 * 1.15 ** k for k in range(31)]], **HOUSE.line("ink", "fit"))
    for name, col in sizes.items():
        n = int(name.split("= ")[1])
        pts = [(n * (1 + rng.uniform(-0.08, 0.08)), 3 / math.sqrt(n) * (1 + rng.gauss(0, 0.08))) for _ in range(5)]
        p.scatter(pts, **HOUSE.mark(col))
        p.scatter([(n * 0.8, 3 / math.sqrt(n) * 1.25)], **HOUSE.mark(col, hollow=True))
    return p


def replicates(w, h):
    """d: mean response per group, bars with replicate marks."""
    rng = random.Random(11)
    groups = ["group 1", "group 2", "group 3"]
    p = HOUSE.panel(w, h, x=(-0.5, 2.5), y=(0, 0.8))
    HOUSE.axes(p, y="response",
               x_options=dict(ticks=[0, 1, 2], format=lambda v: groups[round(v)]))
    for k in range(len(groups)):
        for j, (fill, base) in enumerate(((HOUSE.color("treated A"), 0.05), (HOUSE.color("rule"), 0.4))):
            x0 = k - 0.32 + 0.34 * j
            mean = base * (1 + 0.3 * k)
            p.rect(x0, 0, x0 + 0.3, mean, fill=fill, stroke="none")
            p.scatter([(x0 + 0.15 + rng.uniform(-0.06, 0.06), max(0.005, mean + rng.gauss(0, 0.03)))
                       for _ in range(5)], **HOUSE.mark("ink", size=0.6))
    p.text(-0.4, 0.75, "treated A", anchor="w", size=HOUSE.size("note"),
           text_fill=HOUSE.text_color("treated A"), markup=False)
    p.text(-0.4, 0.69, "control", anchor="w", size=HOUSE.size("note"), text_fill=HOUSE.theme.ink, markup=False)
    return p


def size_key():
    """The one figure-wide key, outside every panel: the sample-size ramp as a bar."""
    items, x = [], 0.0
    for name, col in HOUSE.stops("size").items():
        items.append(i.polygon([(x, 0), (x + 9, 0), (x + 9, 1.4), (x, 1.4)], fill=col, stroke="none"))
        t = HOUSE.label(name, role="key")
        items.append(t.translated(x + 4.5 - (t.bbox.x0 + t.bbox.x1) / 2, 2.0 - t.bbox.y0))
        x += 9
    return i.hstack([HOUSE.label("sample size", role="key"), i.place(items, origin=(0, 0))],
                    gap=1.6, align="start")


def make_figure():
    with HOUSE:
        page = HOUSE.mosaic(["a a b b", "c c d d"],
                            {"a": response, "b": calibration, "c": precision, "d": replicates}, height=112)
        return i.vstack([page, size_key()], gap=1.5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gallery", action="store_true", help="also write gallery/house-style.png")
    args = parser.parse_args(argv)
    out = ROOT / "out" / "house-style"
    result = HOUSE.save(make_figure(), "dose_response", out=out)
    print(result.summary())
    report = HOUSE.build({"dose_response": make_figure}, out=out)   # unchanged: skipped on the next run
    if args.gallery:
        HOUSE.page(make_figure()).save(ROOT / "gallery" / "house-style.png", dpi=200)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
