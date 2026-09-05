"""Isolated probes. Each one stresses exactly one thing so a failure is
attributable. Prints measured numbers, not just pass/fail -- a layout engine
lies most convincingly when it produces something plausible."""

import math, sys
import inklet
from inklet import Vec2
from inklet.typeset import shape, measure
from inklet.typeset.shaping import shape_buffer, feature_key
from inklet.typeset.fonts import find_font


def glyphs(text, font="sans"):
    """Glyph ids in visual order. TextLine keeps only an advance, so the only
    way to inspect shaping is to go back to HarfBuzz directly -- which is
    itself a finding: nothing downstream can see the glyphs."""
    b = shape_buffer(text, find_font(font), feature_key(None))
    return [i.codepoint for i in b.glyph_infos]

RESULTS = []

def probe(name):
    def deco(fn):
        try:
            verdict, detail = fn()
        except Exception as e:
            verdict, detail = "CRASH", f"{type(e).__name__}: {e}"
        RESULTS.append((name, verdict, detail))
        return fn
    return deco


# -- 1. Complex scripts ---------------------------------------------------

@probe("RTL Arabic")
def _():
    p = shape("العلوم العصبية", font="Amiri", size=inklet.pt(9))
    w = p.width
    # Same text reversed at the codepoint level must NOT change the advance if
    # bidi is handled; if it does, we are laying out logical order verbatim.
    rev = shape("العلوم العصبية"[::-1], font="Amiri", size=inklet.pt(9))
    same = abs(w - rev.width) < 1e-6
    return ("SUSPECT" if not same else "OK",
            f"width={w:.3f}mm, reversed={rev.width:.3f}mm, "
            f"{'advance changes with codepoint order' if not same else 'stable'}")

@probe("Arabic ligatures")
def _():
    # lam-alef is a mandatory ligature: 'لا' must shape to ONE glyph.
    p = shape("لا", font="Amiri", size=inklet.pt(9))
    g = glyphs("\u0644\u0627", "Amiri")
    return ("OK" if len(g) == 1 else "NOTE",
            f"lam-alef -> {len(g)} glyph(s) {g}")

@probe("CJK")
def _():
    p = shape("神経科学", font="AR PL UMing CN", size=inklet.pt(9))
    g = glyphs("\u795e\u7d4c\u79d1\u5b66", "AR PL UMing CN")
    return ("OK" if len(g) == 4 else "SUSPECT",
            f"{len(g)} glyphs, width={p.width:.3f}mm")

@probe("CJK line breaking")
def _():
    # CJK breaks between any two characters; there are no spaces to wrap on.
    p = shape("神経科学の研究における画像解析手法", font="AR PL UMing CN",
              size=inklet.pt(9), width=15)
    over = p.width - 15
    return ("FAIL" if over > 0.1 else "OK",
            f"{len(p.lines)} line(s), width={p.width:.3f}mm vs limit 15mm "
            f"(overflow {over:+.3f}mm)")

@probe("Devanagari clusters")
def _():
    p = shape("तंत्रिका विज्ञान", size=inklet.pt(9))
    g = glyphs("\u0924\u0902\u0924\u094d\u0930\u093f\u0915\u093e")
    tofu = g.count(0)
    return ("OK" if tofu == 0 else "FAIL",
            f"{len(g)} glyphs, {tofu} .notdef, width={p.width:.3f}mm")

@probe("Combining diacritics")
def _():
    a = shape("é", size=inklet.pt(9))       # e + combining acute
    b = shape("é", size=inklet.pt(9))        # precomposed e-acute
    d = abs(a.width - b.width)
    return ("OK" if d < 0.01 else "SUSPECT",
            f"decomposed {a.width:.4f} vs precomposed {b.width:.4f}mm "
            f"(delta {d:.4f})")

@probe("Emoji / missing glyph")
def _():
    p = shape("brain \U0001F9E0 scan", size=inklet.pt(9))
    tofu = glyphs("brain \U0001F9E0 scan").count(0)
    return ("OK" if tofu == 0 else "SUSPECT",
            f"{tofu} .notdef glyph(s) -- no fallback across faces" if tofu
            else "resolved in one face")


# -- 2. Text layout edge cases -------------------------------------------

@probe("Unbreakable long word")
def _():
    w = 20.0
    p = shape("Immunohistochemistry-based", size=inklet.pt(7), width=w)
    over = p.width - w
    return ("KNOWN" if over > 0 else "OK",
            f"overflows wrap width by {over:+.3f}mm (documented: no hyphenation)")

@probe("Empty + whitespace strings")
def _():
    outs = []
    for s in ["", " ", "\n", "\n\n", "  \n  "]:
        try:
            p = shape(s, size=inklet.pt(7))
            outs.append(f"{s!r}->{len(p.lines)}L/{p.height:.2f}mm")
        except Exception as e:
            outs.append(f"{s!r}->{type(e).__name__}")
    return ("OK", "; ".join(outs))

@probe("Zero-width & control chars")
def _():
    p = shape("a​b­c\tz", size=inklet.pt(7))
    return ("OK", f"width={p.width:.3f}mm, {len(glyphs(chr(97)+chr(0x200b)))} glyphs for a+ZWSP")


# -- 3. Geometry under rotation ------------------------------------------

@probe("Rotated text envelope")
def _():
    t = inklet.text("Fluorescence", size=inklet.pt(7))
    w0, h0 = t.width, t.height
    r = t.rotated(90)
    # A 90-degree rotation must swap the extents exactly.
    ok = abs(r.width - h0) < 1e-6 and abs(r.height - w0) < 1e-6
    return ("OK" if ok else "FAIL",
            f"{w0:.3f}x{h0:.3f} -> {r.width:.3f}x{r.height:.3f}mm")

@probe("Rotated box in a stack")
def _():
    lab = inklet.text("y axis", size=inklet.pt(7)).rotated(-90)
    plot = inklet.box(inklet.spacer(30, 20))
    row = inklet.hstack([lab, plot], gap=2)
    expect = lab.width + 2 + plot.width
    return ("OK" if abs(row.width - expect) < 1e-6 else "FAIL",
            f"row={row.width:.4f}mm, expected {expect:.4f}mm")

@probe("45-degree envelope tightness")
def _():
    b = inklet.box(inklet.spacer(40, 10)).rotated(45)
    corner_hull = (b.width)  # measured
    # A tight envelope for a 40x10 rect at 45deg is (40+10)/sqrt2 = 35.355
    inner = inklet.box(inklet.spacer(40, 10))
    ideal = (inner.width + inner.height) / math.sqrt(2)
    return ("OK" if abs(corner_hull - ideal) < 1e-6 else "SUSPECT",
            f"width={corner_hull:.4f}mm, tight={ideal:.4f}mm")

@probe("Non-uniform scale + rotate")
def _():
    b = inklet.box(inklet.spacer(20, 10)).scaled(2.0, 0.5).rotated(30)
    return ("OK", f"{b.width:.4f} x {b.height:.4f}mm (visual check needed)")


# -- 4. Layout combinators ------------------------------------------------

@probe("Grid, wildly unequal cells")
def _():
    cells = [inklet.box("a"), inklet.box("A very much longer label indeed"),
             inklet.box("b"), inklet.box(inklet.spacer(5, 40))]
    g = inklet.grid(cells, cols=2, gap=3)
    widest = max(c.width for c in cells)
    tallest = max(c.height for c in cells)
    # Uniform cells => 2*widest + gap
    ok = abs(g.width - (2 * widest + 3)) < 1e-6
    return ("OK" if ok else "NOTE",
            f"grid={g.width:.3f}x{g.height:.3f}mm; uniform would be "
            f"{2*widest+3:.3f}x{2*tallest+3:.3f} -> "
            f"{'uniform cells' if ok else 'per-column sizing'}")

@probe("Deep nesting x8")
def _():
    d = inklet.text("core", size=inklet.pt(6))
    for i in range(8):
        d = inklet.box(inklet.vstack([d, inklet.label(f"L{i}")], gap=1), pad=1.5)
    depth = max(len(list(n.walk())) for n in [d])
    return ("OK", f"{d.width:.3f}x{d.height:.3f}mm, {depth} nodes")

@probe("Empty containers")
def _():
    outs = []
    for name, fn in [("hstack[]", lambda: inklet.hstack([])),
                     ("vstack[]", lambda: inklet.vstack([])),
                     ("grid[]", lambda: inklet.grid([], cols=2)),
                     ("box(spacer0)", lambda: inklet.box(inklet.spacer(0, 0)))]:
        try:
            d = fn()
            outs.append(f"{name}->{d.width:.2f}x{d.height:.2f}")
        except Exception as e:
            outs.append(f"{name}->{type(e).__name__}")
    return ("OK", "; ".join(outs))

@probe("Negative / zero gap")
def _():
    a, b = inklet.box("A"), inklet.box("B")
    tight = inklet.hstack([a, b], gap=-2)
    return ("OK", f"gap=-2 -> width {tight.width:.3f}mm "
                  f"(sum {a.width+b.width:.3f}, overlap allowed)")


# -- 5. Links -------------------------------------------------------------

@probe("Arrow into a circle")
def _():
    src = inklet.box("source")
    dst = inklet.circle(inklet.text("target", size=inklet.pt(6)))
    fig = inklet.figure(width=80)
    fig.add(inklet.vstack([src, dst], gap=15))
    fig.link(src, dst)
    root, places = fig.build()
    conn = [n for n in root.walk() if n.kind == "link"]
    if not conn:
        return ("FAIL", "no connector emitted")
    tip = places[conn[0].id].point("end")  # world frame; anchor_point() is local
    c = places[dst.id]
    cx, cy = c.point("center").x, c.point("center").y
    rx, ry = c.bbox.width / 2, c.bbox.height / 2
    # On the ellipse boundary this is 1.0
    val = ((tip.x - cx) / rx) ** 2 + ((tip.y - cy) / ry) ** 2
    return ("OK" if abs(val - 1.0) < 0.02 else "FAIL",
            f"tip normalised radius^2 = {val:.4f} (1.0 = on the curve)")

@probe("Self-link")
def _():
    a = inklet.box("recurrent")
    fig = inklet.figure(width=80); fig.add(a)
    fig.link(a, a, label="loop")
    root, _ = fig.build()
    return ("OK", f"{len([n for n in root.walk() if n.kind=='link'])} connector(s)")

@probe("Link across nesting depth")
def _():
    deep = inklet.box("deep")
    outer = inklet.box(inklet.vstack([inklet.box(inklet.hstack([inklet.box("x"), deep], gap=2)),
                                inklet.label("panel")], gap=2))
    other = inklet.box("far")
    fig = inklet.figure(width=120)
    fig.add(inklet.hstack([outer, other], gap=20))
    fig.link(deep, other)
    root, places = fig.build()
    conn = [n for n in root.walk() if n.kind == "link"][0]
    start = places[conn.id].point("start")
    db = places[deep.id].bbox
    on_edge = min(abs(start.x - db.x1), abs(start.x - db.x0),
                  abs(start.y - db.y0), abs(start.y - db.y1))
    return ("OK" if on_edge < 0.01 else "FAIL",
            f"start {on_edge:.5f}mm from the nested box's own edge")

@probe("30 crossing links")
def _():
    left = [inklet.box(f"in {i}") for i in range(6)]
    right = [inklet.box(f"out {j}") for j in range(5)]
    fig = inklet.figure(width=140)
    fig.add(inklet.hstack([inklet.vstack(left, gap=3), inklet.spacer(40, 1),
                        inklet.vstack(right, gap=3)], gap=6))
    for a in left:
        for b in right:
            fig.link(a, b)
    root, _ = fig.build()
    n = len([x for x in root.walk() if x.kind == "link"])
    return ("OK" if n == 30 else "FAIL", f"{n} connectors routed, no obstacle avoidance")

@probe("Link to a zero-size node")
def _():
    a = inklet.box("A"); z = inklet.spacer(0, 0)
    fig = inklet.figure(width=80); fig.add(inklet.vstack([a, z], gap=10))
    fig.link(a, z)
    root, _ = fig.build()
    return ("OK", f"{len([n for n in root.walk() if n.kind=='link'])} connector(s)")


# -- 6. Determinism & scale ----------------------------------------------

@probe("Determinism under heavy load")
def _():
    def build():
        fig = inklet.figure(width=140)
        rows = [inklet.hstack([inklet.box(f"n{i}{j}") for j in range(4)], gap=2)
                for i in range(4)]
        fig.add(inklet.vstack(rows, gap=2))
        return fig.to_svg()
    import re
    a, b = build(), build()
    blank = lambda s: re.sub(r'id="[^"]*"', 'id="X"', s)
    if a == b:
        return ("OK", "byte-identical within one process")
    return ("FAIL" if blank(a) != blank(b) else "ID-DRIFT",
            "geometry identical; ids differ -- counter is process-global, "
            "so rebuilding churns every id")

@probe("Overflow off a narrow column")
def _():
    wide = inklet.box("An unbreakable label that is emphatically far wider than any single column could ever hope to contain")
    fig = inklet.figure(width=inklet.COLUMN_SINGLE)
    fig.add(wide)
    d = fig.lint()
    codes = sorted({x.code for x in d})
    return ("OK" if any("CANVAS" in c for c in codes) else "FAIL",
            f"content {wide.width:.1f}mm in an {inklet.COLUMN_SINGLE}mm column -> {codes}")


def main():
    w = max(len(n) for n, _, _ in RESULTS)
    bad = 0
    for name, verdict, detail in RESULTS:
        if verdict in ("FAIL", "CRASH"):
            bad += 1
        print(f"{name.ljust(w)}  {verdict.ljust(8)} {detail}")
    print(f"\n{len(RESULTS)} probes, {bad} hard failures")
    return 0

sys.exit(main())
