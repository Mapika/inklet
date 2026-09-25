"""Dense label-placement benchmark: collisions, displacement and runtime.

Builds a fixed set of crowded labelling cases -- clustered scatters with 60
and 200 labels, a volcano plot, a ten-curve line plot, labels over bars, error
bars and a shaded area, and two sets of diagram callouts -- and measures each
result geometrically, independently of the placer's own scoring:

* ``label_label``: pairs of labels whose boxes overlap.
* ``label_mark``: labels covering a data marker, crossed by a stroked data
  line (curves, error bars, rules) or sitting on a filled bar or area.
* ``label_text``: labels overlapping other text (tick labels, legend, title).
* ``leader_cross``: leader/leader crossings plus leaders passing through a
  label other than their own.
* ``unresolved``: labels the placer itself reported as unresolved.
* ``legend_cover``: markers, stroked segments and filled shapes under the
  key (the key's own swatches excluded).
* ``mean_disp`` / ``max_disp``: distance in mm from each labelled anchor to
  the nearest point of its label box.
* ``lint``: warnings and errors from ``inklet.lint`` (all rules).
* ``seconds``: wall time to build the figure, which is when labels are placed.

Every case is deterministic (fixed seeds, fixed tables), so two runs on the
same source give identical counts. Usage::

    .venv/bin/python tools/benchmark_labels.py                  # table
    .venv/bin/python tools/benchmark_labels.py --png out/labels # and PNGs
    .venv/bin/python tools/benchmark_labels.py --legacy         # old APIs only

``--legacy`` builds every case with the APIs that existed before direct
labelling (curve ends named with ``label_points``, ``legend()`` in a fixed
corner), for a before/after comparison on one source tree.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if "--source" in sys.argv:          # benchmark another checkout's src/
    sys.path.insert(0, sys.argv[sys.argv.index("--source") + 1])
else:
    sys.path.insert(0, str(ROOT / "src"))

import inklet  # noqa: E402
from inklet.core import MarkerBatchPrim, PathPrim, Rect, Vec2, resolve  # noqa: E402
from inklet.draw.coords import as_drawn  # noqa: E402

#: Kinds of the text nodes the placers put down, and of their leaders.
LABEL_KINDS = {"label", "annotation-label", "line-label"}
LABEL_HOLDERS = {"point-labels", "annotation", "line-labels"}
LEADER_KINDS = {"leader", "label-leader"}

GENES = ("Sst Pvalb Vip Lamp5 Sncg Calb1 Calb2 Npy Cck Reln Chat Th Gad1 Gad2 "
         "Slc17a7 Rorb Foxp2 Cux2 Fezf2 Ctip2 Satb2 Tbr1 Pax6 Dlx1 Nkx2-1 Lhx6 "
         "Prox1 Neurod6 Cntnap2 Grin2b Kcnq2 Scn1a Syt1 Snap25 Fos Arc Egr1 "
         "Npas4 Junb Nr4a1 Bdnf Homer1 Egr2 Gfap Aqp4 Olig2 Mbp Plp1 Pdgfra "
         "Cx3cr1 Tmem119 P2ry12 Cldn5 Flt1 Pecam1 Acta2 Myh11 Vtn Kcnj8 Rgs5").split()


def gene(k: int) -> str:
    return GENES[k % len(GENES)] + ("" if k < len(GENES) else str(k // len(GENES)))


# -- cases ----------------------------------------------------------------


def clusters(n_labels: int, width: float, height: float, seed: int):
    rng = random.Random(seed)
    centres = [(rng.uniform(1.5, 8.5), rng.uniform(1.5, 8.5)) for _ in range(6)]
    cloud = []
    for _ in range(6 * n_labels):
        cx, cy = centres[rng.randrange(6)]
        cloud.append((min(9.8, max(0.2, rng.gauss(cx, 0.9))),
                      min(9.8, max(0.2, rng.gauss(cy, 0.9)))))
    hits = cloud[:n_labels]
    p = inklet.plot.panel(width, height, x=(0, 10), y=(0, 10))
    p.scatter(cloud, size=0.7, color="#c4c9cf")
    p.scatter(hits, size=0.9, color="#1f5f99")
    p.axes(x="UMAP 1", y="UMAP 2")
    names = [gene(k) for k in range(n_labels)]
    p.label_points(hits, names)
    return p, dict(zip(names, hits))


def case_scatter_60(legacy):
    return clusters(60, 90, 65, 7)


def case_scatter_200(legacy):
    return clusters(200, 170, 120, 11)


def case_volcano(legacy):
    rng = random.Random(3)
    fold = [rng.gauss(0, 1.3) for _ in range(2500)]
    pvals = [10 ** -(abs(f) * rng.uniform(0.4, 2.2) + abs(rng.gauss(0, 0.6)))
             for f in fold]
    names = [gene(k) for k in range(len(fold))]
    p = inklet.plot.panel(80, 70, x=(-5, 5), y=(0, 12))
    p.volcano(fold, pvals, labels=names, top=30)
    p.axes(x="log2 fold change", y="-log10 p")
    result = {}
    ranked = [i for i in range(len(fold))]
    # The labelled points, recovered from the volcano note.
    for node in [*p._content, *p._over]:
        note = node.notes.get("volcano")
        if note:
            for i in note["labelled"]:
                result[names[i]] = (fold[i], min(12.0, -math.log10(pvals[i])))
    del ranked
    return p, result


def curves():
    out = []
    for k in range(10):
        pts = []
        for s in range(61):
            t = s / 60 * 10
            y = 5 + 3.2 * math.tanh((t - 2 - 0.4 * k) / 1.5) * (0.35 + 0.07 * k) \
                + 0.25 * math.sin(t * (1 + 0.1 * k))
            pts.append((t, y))
        out.append((f"condition {k + 1}", pts))
    return out


def case_curves_10(legacy):
    p = inklet.plot.panel(80, 55, x=(0, 10), y=(0, 10))
    anchors = {}
    for k, (name, pts) in enumerate(curves()):
        p.line(pts, name=name)
        anchors[name] = pts[-1]
    p.axes(x="Time (s)", y="Response")
    if legacy or not hasattr(p, "label_lines"):
        p.label_points(list(anchors.values()), list(anchors))
    else:
        p.label_lines()
    return p, anchors


def case_curves_inside(legacy):
    p = inklet.plot.panel(80, 55, x=(0, 10), y=(0, 10))
    anchors = {}
    for k, (name, pts) in enumerate(curves()):
        if k % 2:
            continue
        p.line(pts, name=name, stroke_width=0.35)
        anchors[name] = pts[-1]
    p.axes(x="Time (s)", y="Response")
    if legacy or not hasattr(p, "label_lines"):
        p.label_points(list(anchors.values()), list(anchors))
    else:
        p.label_lines(where="inside")
    return p, anchors


def case_bars_areas(legacy):
    p = inklet.plot.panel(90, 55, x=(-0.5, 11.5), y=(0, 10))
    rng = random.Random(5)
    heights = [rng.uniform(2.5, 8.5) for _ in range(12)]
    p.fill_between([x * 0.5 - 0.5 for x in range(25)],
                   [1.5 + 0.8 * math.sin(x / 3) for x in range(25)],
                   [4.5 + 1.2 * math.sin(x / 4) for x in range(25)],
                   fill="#dfe8f0")
    p.bars(list(range(12)), heights, width=0.6)
    tops = [(k, h) for k, h in enumerate(heights)]
    p.errorbars(tops, yerr=[0.8] * 12)
    trend = [(k, h + 0.6 * math.sin(k)) for k, h in enumerate(heights)]
    p.line(trend, stroke="#b04a2e")
    p.scatter(trend, size=1.0, color="#b04a2e")
    p.axes(x="Sample", y="Signal")
    p.legend(entries=[("measured", "#1f5f99"), ("model", "#b04a2e")],
             **({} if legacy else {"corner": "best"}))
    names = [f"S{k + 1}{'abc'[k % 3]}" for k in range(12)]
    anchors = dict(zip(names, trend))
    p.label_points(trend, names)
    return p, anchors


STORM = [
    (66.3, 28.9, 'Sst'), (26.4, 24.0, 'Pvalb'), (66.6, 9.1, 'Vip'),
    (71.8, 40.6, 'Lamp5'), (39.4, 32.9, 'Sncg'), (23.1, 41.6, 'Calb1'),
    (41.1, 25.1, 'Calb2'), (36.9, 33.0, 'Npy'), (60.2, 3.3, 'Cck'),
    (82.2, 24.4, 'Reln'), (59.9, 30.3, 'Chat'), (82.5, 51.4, 'Th'),
    (13.2, 21.3, 'Gad1'), (43.2, 26.4, 'Gad2'), (45.8, 45.5, 'Slc17a7'),
    (49.6, 43.4, 'Rorb'), (80.4, 50.5, 'Foxp2'), (11.0, 5.6, 'Cux2'),
    (45.8, 37.1, 'Fezf2'), (73.8, 48.6, 'Ctip2'), (15.9, 16.5, 'Satb2'),
    (47.9, 28.0, 'Tbr1'), (22.2, 11.9, 'Pax6'), (58.4, 47.0, 'Dlx1'),
    (7.1, 52.1, 'Nkx2-1'), (35.2, 40.0, 'Lhx6'), (75.3, 47.9, 'Prox1'),
    (57.0, 23.0, 'Neurod6'), (15.9, 46.1, 'Cntnap2'), (14.3, 24.0, 'Grin2b'),
    (43.7, 31.5, 'Kcnq2'), (51.0, 27.4, 'Scn1a'), (54.2, 36.5, 'Syt1'),
    (80.9, 22.4, 'Snap25'),
]


def place(art, legacy):
    """`place_labels`, jointly where this checkout has the joint search."""
    import inspect
    if not legacy and "method" in inspect.signature(inklet.place_labels).parameters:
        return inklet.place_labels(art, method="joint")
    return inklet.place_labels(art)


def case_callouts_34(legacy):
    th = inklet.current_theme()
    dots = inklet.place([
        ((x, y), inklet.marker("circle", 1.3, fill=th.color(0),
                               stroke="none").named(name))
        for x, y, name in STORM])
    art = dots
    for _, _, name in STORM:
        art = inklet.annotate(dots.find(name), name, within=art, clear=1.2,
                              size=th.font_size_small,
                              leader_style={"stroke": th.ink,
                                            "stroke_width": th.hairline})
    art = place(art, legacy)
    return art, {name: name for _, _, name in STORM}


def case_diagram_callouts(legacy):
    """A rig of boxes and discs with 24 callouts, parts close together."""
    th = inklet.current_theme()
    parts = []
    rng = random.Random(21)
    names = []
    for k in range(24):
        x, y = 10 + (k % 6) * 11 + rng.uniform(-2, 2), 8 + (k // 6) * 9 + rng.uniform(-1.5, 1.5)
        shape = (inklet.box(width=7, height=4, fill="#dfe8f0", stroke="#4a5a68")
                 if k % 3 else inklet.circle(width=4.4, height=4.4, fill="#f2d7c9",
                                   stroke="#8a4b2e"))
        name = f"part {k + 1}"
        names.append((x, y, name))
        parts.append(((x, y), shape.named(name)))
    rig = inklet.place(parts)
    art = rig
    for _, _, name in names:
        art = inklet.annotate(rig.find(name), name, within=art,
                              size=th.font_size_small,
                              leader_style={"stroke": th.ink,
                                            "stroke_width": th.hairline})
    art = place(art, legacy)
    return art, {name: name for _, _, name in names}


CASES = {
    "scatter_60": case_scatter_60,
    "scatter_200": case_scatter_200,
    "volcano_30": case_volcano,
    "curves_inside_5": case_curves_inside,
    "curves_10": case_curves_10,
    "bars_areas_12": case_bars_areas,
    "callouts_34": case_callouts_34,
    "diagram_24": case_diagram_callouts,
}


# -- measurement ----------------------------------------------------------


def _walk(node, parents=()):
    yield node, parents
    for child in node.children:
        yield from _walk(child, parents + (node,))


def _segments_of(prim, world):
    out = []
    for sub in prim.subpaths:
        pts = [world.apply(v) for v in sub.points]
        out.extend(zip(pts, pts[1:]))
        if sub.closed and len(pts) > 2:
            out.append((pts[-1], pts[0]))
    return out


def _hits(a, b, box):
    enter, leave = 0.0, 1.0
    for s, e, lo, hi in ((a.x, b.x, box.x0, box.x1), (a.y, b.y, box.y0, box.y1)):
        d = e - s
        if abs(d) < 1e-12:
            if s < lo or s > hi:
                return False
            continue
        t0, t1 = sorted(((lo - s) / d, (hi - s) / d))
        enter, leave = max(enter, t0), min(leave, t1)
        if enter > leave:
            return False
    return True


def _cross(a, b, c, d):
    def side(p, q, r):
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
    return side(c, d, a) * side(c, d, b) < -1e-12 and side(a, b, c) * side(a, b, d) < -1e-12


def _inside(poly, p):
    hit = False
    for (a, b) in zip(poly, poly[1:] + poly[:1]):
        if (a.y > p.y) != (b.y > p.y):
            x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x > p.x:
                hit = not hit
    return hit


def _area(a: Rect, b: Rect) -> float:
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return w * h if w > 0 and h > 0 else 0.0


def _shrink(box: Rect, by: float) -> Rect:
    return Rect(box.x0 + by, box.y0 + by, box.x1 - by, box.y1 - by)


def measure(root, anchors, frame_point):
    places = resolve(root)
    labels, leaders, markers, segments, polys, texts = [], [], [], [], [], []
    legend = None
    for node, parents in _walk(root):
        if node.prim is None or node.id not in places:
            continue
        here = places[node.id]
        kinds = {p.kind for p in parents} | {node.kind}
        is_text = type(node.prim).__name__ == "TextPrim"
        if is_text and (node.kind in LABEL_KINDS) and kinds & LABEL_HOLDERS:
            labels.append((getattr(node.prim, "text", ""), here.bbox))
            continue
        if isinstance(node.prim, PathPrim) and (
                node.kind in LEADER_KINDS
                or (node.kind in ("mark-line", "connector") and kinds & LABEL_HOLDERS)):
            segs = _segments_of(node.prim, here.world)
            if segs:
                leaders.append((segs[0][0], segs[-1][1], segs))
            continue
        if kinds & LABEL_HOLDERS and node.kind in ("label-plate",):
            continue
        if "legend" in kinds:
            if here.bbox is not None:
                legend = here.bbox if legend is None else legend.union(here.bbox)
            if is_text:
                texts.append(here.bbox)
            continue
        if is_text:
            texts.append(here.bbox)
        elif isinstance(node.prim, MarkerBatchPrim):
            w = here.world
            scale = math.sqrt(abs(w.a * w.d - w.b * w.c))
            for x, y, size, _, _ in node.prim.records():
                c = w.apply(Vec2(x, y))
                markers.append((c, size * scale / 2))
        elif isinstance(node.prim, PathPrim):
            filled = node.prim.filled and here.style.fill not in (None, "none")
            stroked = here.style.stroke not in (None, "none")
            if filled:
                for sub in node.prim.subpaths:
                    pts = [here.world.apply(v) for v in sub.points]
                    if len(pts) > 2:
                        polys.append(pts)
            elif stroked:
                segments.extend(_segments_of(node.prim, here.world))
        elif here.bbox is not None and node.kind not in ("background",):
            # Rect/ellipse shapes in diagrams.
            box = here.bbox
            polys.append(list(box.corners))
    boxes = [b for _, b in labels]
    label_label = sum(1 for i, a in enumerate(boxes) for b in boxes[i + 1:]
                      if _area(a, b) > 0.05)
    label_mark = 0
    label_text = 0
    for text, box in labels:
        inner = _shrink(box, 0.15)
        own = anchors.get(text)
        own = frame_point(own) if own is not None else None
        hit = False
        for c, r in markers:
            if own is not None and (c - own).length < 1e-3:
                continue
            nx = min(max(c.x, inner.x0), inner.x1)
            ny = min(max(c.y, inner.y0), inner.y1)
            if math.hypot(c.x - nx, c.y - ny) < r:
                hit = True
                break
        if not hit:
            hit = any(_hits(a, b, inner) for a, b in segments)
        if not hit:
            probe = [Vec2(inner.x0 + (inner.x1 - inner.x0) * i / 4,
                          inner.y0 + (inner.y1 - inner.y0) * j / 2)
                     for i in range(5) for j in range(3)]
            hit = any(any(_inside(poly, q) for q in probe) for poly in polys
                      if Rect.hull(poly).overlap(inner) is not None)
        label_mark += hit
        label_text += any(_area(inner, t) > 0.05 for t in texts)
    leader_cross = 0
    for i, (a0, a1, segs) in enumerate(leaders):
        for b0, b1, other in leaders[i + 1:]:
            leader_cross += any(_cross(p, q, r, s) for p, q in segs for r, s in other)
        # Through a label other than the one it ends on.
        for _, box in labels:
            end_on = _area(_shrink(box, -0.3), Rect(a1.x, a1.y, a1.x, a1.y)) >= 0 and (
                box.x0 - 0.3 <= a1.x <= box.x1 + 0.3 and box.y0 - 0.3 <= a1.y <= box.y1 + 0.3)
            start_on = box.x0 - 0.3 <= a0.x <= box.x1 + 0.3 and box.y0 - 0.3 <= a0.y <= box.y1 + 0.3
            if end_on or start_on:
                continue
            if any(_hits(p, q, _shrink(box, 0.1)) for p, q in segs):
                leader_cross += 1
    disp = []
    for text, box in labels:
        if text not in anchors:
            continue
        a = frame_point(anchors[text])
        nx = min(max(a.x, box.x0), box.x1)
        ny = min(max(a.y, box.y0), box.y1)
        disp.append(math.hypot(a.x - nx, a.y - ny))
    unresolved = 0
    for node in root.walk():
        for key in ("point_labels", "line_labels", "place_labels"):
            note = node.notes.get(key)
            if isinstance(note, dict):
                unresolved += len(note.get("unresolved", ()))
    # Data the key covers: markers, stroked segments and filled shapes.
    legend_cover = 0
    if legend is not None:
        legend_cover += sum(1 for c, r in markers
                            if legend.x0 - r < c.x < legend.x1 + r
                            and legend.y0 - r < c.y < legend.y1 + r)
        legend_cover += sum(1 for a, b in segments if _hits(a, b, legend))
        legend_cover += sum(1 for poly in polys
                            if Rect.hull(poly).overlap(legend) is not None
                            and any(_inside(poly, q) for q in legend.corners))
    return dict(labels=len(labels), label_label=label_label,
                label_mark=label_mark, label_text=label_text,
                leader_cross=leader_cross, leaders=len(leaders),
                unresolved=unresolved, legend_cover=legend_cover,
                mean_disp=round(sum(disp) / len(disp), 2) if disp else 0.0,
                max_disp=round(max(disp), 2) if disp else 0.0)


def run(name, legacy=False, png=None):
    inklet.use_theme("nature")
    start = time.perf_counter()
    made, anchors = CASES[name](legacy)
    if hasattr(made, "build"):
        built = made.build()
        root = as_drawn(built)
        frame_point = lambda xy: made.point(*xy)  # noqa: E731
    else:
        built = root = made
        # Diagram cases name their targets; find each one in the frame.
        places = resolve(root)
        centres = {node.name: places[node.id].bbox.center
                   for node in root.walk()
                   if node.name and node.id in places
                   and places[node.id].bbox is not None}
        frame_point = centres.__getitem__
    seconds = time.perf_counter() - start
    out = measure(root, anchors, frame_point)
    found = inklet.lint(built)
    out["lint"] = len(found)
    codes = {}
    for d in found:
        codes[d.code] = codes.get(d.code, 0) + 1
    out["lint_codes"] = dict(sorted(codes.items()))
    out["seconds"] = round(seconds, 3)
    if png is not None:
        png.mkdir(parents=True, exist_ok=True)
        (png / f"{name}.png").write_bytes(inklet.to_png(built, dpi=200))
        (png / f"{name}.svg").write_text(inklet.to_svg(built))
    return out


COLUMNS = ("labels", "label_label", "label_mark", "label_text", "leader_cross",
           "leaders", "unresolved", "legend_cover", "mean_disp", "max_disp", "lint", "seconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--png", type=Path, help="write each case as PNG and SVG here")
    parser.add_argument("--legacy", action="store_true",
                        help="use only the pre-direct-labelling APIs")
    parser.add_argument("--json", type=Path, help="write the results as JSON")
    parser.add_argument("--source", help="import inklet from this src/ directory")
    parser.add_argument("cases", nargs="*", default=list(CASES))
    args = parser.parse_args()
    results = {}
    print("case".ljust(15) + "".join(c.rjust(13) for c in COLUMNS))
    for name in args.cases:
        r = run(name, args.legacy, args.png)
        results[name] = r
        print(name.ljust(15) + "".join(str(r[c]).rjust(13) for c in COLUMNS)
              + "  " + json.dumps(r["lint_codes"]), flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
