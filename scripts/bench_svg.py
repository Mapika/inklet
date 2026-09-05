#!/usr/bin/env python3
"""Measure what an SVG costs: bytes on disk, DOM nodes, and time to paint.

The renderer's job is not finished when the picture is right -- a figure that
is correct and takes four seconds to open is a figure nobody scrolls past.
This walks the regression corpus, builds each figure once, and records the
numbers a rendering change has to move (or at least not spoil):

    bytes / gzip  what the reader downloads,
    DOM elements  what the viewer has to build a tree from,
    d-length      how much of the file is path data,
    styles        distinct presentation-attribute strings, the dedup headroom,
    build ms      time in `inklet` before a single character is written,
    render ms     time inside `inklet.render.svg`,
    parse ms      `xml.etree` over the result, a renderer-independent proxy,
    paint ms      headless Chrome to first screenshot, the honest one.

Each figure is built in its own subprocess: the corpus modules run at import,
set global themes and are not written to be imported twice.

    scripts/bench_svg.py                       # everything, table to stdout
    scripts/bench_svg.py --only hard,dense     # a subset
    scripts/bench_svg.py --text names,outline,embed --only panels
    scripts/bench_svg.py --json out.json --svg-dir tmp/agents/perf/after
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

#: name -> (module path relative to the repo, argv tail, note).
CORPUS: dict[str, tuple[str, list[str], str]] = {
    "hello":       ("examples/hello_figure.py", [], "import"),
    "panels":      ("examples/panels.py", [], "import"),
    "smoke":       ("examples/render_smoke.py", [], "main"),
    "hard":        ("stress/hard_figure.py", [], "import"),
    "dense":       ("stress/dense_graph.py", [], "import"),
    "three":       ("stress/three_figure.py", [], "import"),
    "electro":     ("stress/electro_figure.py", [], "main"),
    "mega":        ("stress/mega_figure.py", [], "main"),
    "drug":        ("figures/drug_discovery.py", [], "main"),
}

_TAG = re.compile(r"<([a-zA-Z][-\w:]*)")
_D_ATTR = re.compile(r'\bd="([^"]*)"')
_STYLE_KEYS = ("fill", "stroke", "stroke-width", "stroke-dasharray",
               "stroke-linecap", "stroke-linejoin", "opacity", "font-family",
               "font-size", "font-weight")
_ATTR = re.compile(r'\s([-\w:]+)="([^"]*)"')
_ELEMENT = re.compile(r"<([a-zA-Z][-\w:]*)((?:\s[^<>]*)?)/?>")


# -- child: build one figure ----------------------------------------------


def _capture(name: str, text: str = "names") -> list[tuple[str, object]]:
    """Import the corpus module with `save` disarmed, returning renderers.

    The scripts write to fixed paths and print a lint report; both are noise
    here, and the report costs more than everything else measured.
    """
    import inklet
    import inklet.render
    from inklet.figure import Figure

    captured: list[tuple[str, object]] = []

    def fake_save(self, *paths, **kwargs):
        label = Path(str(paths[0])).stem if paths else "figure"
        kwargs.setdefault("text", text)
        captured.append((label, lambda: self.to_svg(**kwargs)))

    def fake_save_svg(root, path, **kwargs):
        from inklet.render.svg import to_svg
        kwargs.setdefault("text", text)
        captured.append((Path(str(path)).stem, lambda: to_svg(root, **kwargs)))

    Figure.save = fake_save                      # type: ignore[method-assign]
    Figure.report = lambda self, **kw: ""        # type: ignore[method-assign]
    inklet.render.save_svg = fake_save_svg
    if hasattr(inklet, "save_svg"):
        inklet.save_svg = fake_save_svg

    path, argv, _ = CORPUS[name]
    module_path = ROOT / path
    sys.argv = [str(module_path), *argv]
    os.chdir(ROOT)

    # The corpus scripts are scripts: some save at import, some behind a
    # `__main__` guard. `runpy` under that name covers both, and the
    # `SystemExit` the guarded ones end on is a normal finish, not a failure.
    import runpy
    try:
        runpy.run_path(str(module_path), run_name="__main__")
    except SystemExit:
        pass
    return captured


def measure_text(text: str) -> dict:
    data = text.encode("utf-8")
    tags: dict[str, int] = {}
    for tag in _TAG.findall(text):
        if tag in ("?xml", "!--"):
            continue
        tags[tag] = tags.get(tag, 0) + 1
    styles: set[str] = set()
    for _tag, attrs in _ELEMENT.findall(text):
        bag = [f"{k}:{v}" for k, v in _ATTR.findall(attrs) if k in _STYLE_KEYS]
        if bag:
            styles.add("|".join(bag))
    return {
        "bytes": len(data),
        "gzip": len(gzip.compress(data, 9, mtime=0)),
        "elements": sum(tags.values()),
        "tags": dict(sorted(tags.items(), key=lambda kv: -kv[1])),
        "d_chars": sum(len(d) for d in _D_ATTR.findall(text)),
        "styles": len(styles),
    }


def parse_ms(text: str, repeats: int = 3) -> float:
    import xml.etree.ElementTree as ET
    best = float("inf")
    for _ in range(repeats):
        started = time.perf_counter()
        ET.fromstring(text)
        best = min(best, (time.perf_counter() - started) * 1e3)
    return best


def run_child(name: str, repeats: int, svg_dir: Path | None,
              text: str = "names") -> list[dict]:
    started = time.perf_counter()
    captured = _capture(name, text)
    build_ms = (time.perf_counter() - started) * 1e3

    rows = []
    for index, (label, render) in enumerate(captured):
        best = float("inf")
        document = ""
        for _ in range(repeats):
            t0 = time.perf_counter()
            document = render()
            best = min(best, (time.perf_counter() - t0) * 1e3)
        again = render()
        row = {
            "figure": name if len(captured) == 1 else f"{name}:{label}",
            "text": text,
            "build_ms": round(build_ms, 1) if index == 0 else 0.0,
            "render_ms": round(best, 1),
            "stable": document == again,
            "parse_ms": round(parse_ms(document), 1),
        }
        row.update(measure_text(document))
        if svg_dir is not None:
            svg_dir.mkdir(parents=True, exist_ok=True)
            suffix = "" if text == "names" else f".{text}"
            (svg_dir / f"{row['figure'].replace(':', '_')}{suffix}.svg").write_text(
                document, encoding="utf-8")
        rows.append(row)
    return rows


# -- parent: paint timing and the table -----------------------------------


def chrome_ms(svg: Path, repeats: int = 3) -> float:
    """Wall time for headless Chrome to load the file and hand back a PNG.

    Browser start-up is in there and dwarfs a small figure, so the blank-page
    row is measured too and the interesting number is the difference. Min of
    `repeats`, because everything that varies here only ever adds.
    """
    text = svg.read_text(encoding="utf-8", errors="replace")[:4000]
    def mm(key: str) -> float:
        try:
            return float(text.split(f'{key}="')[1].split('mm"')[0])
        except (IndexError, ValueError):
            return 200.0
    w = min(int(mm("width") * 96 / 25.4) + 200, 16000)
    h = min(int(mm("height") * 96 / 25.4) + 200, 16000)
    out = svg.with_suffix(".paint.png")
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        subprocess.run(
            ["google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--default-background-color=FFFFFFFF",
             f"--screenshot={out}", f"--window-size={w},{h}",
             f"file://{svg.resolve()}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        best = min(best, (time.perf_counter() - t0) * 1e3)
    out.unlink(missing_ok=True)
    return round(best, 1)


def table(rows: list[dict]) -> str:
    # The `text` column only earns its width when more than one mode was run:
    # a plain benchmark is all `names` and the reader knows it.
    modes = {r.get("text", "names") for r in rows}
    head = ("figure", *(("text",) if len(modes) > 1 else ()),
            "bytes", "gzip", "elems", "styles", "d chars",
            "build ms", "render ms", "parse ms", "paint ms")
    body = [[r["figure"], *((r.get("text", "names"),) if len(modes) > 1 else ()),
             f"{r['bytes']:,}", f"{r['gzip']:,}",
             f"{r['elements']:,}", f"{r['styles']:,}", f"{r['d_chars']:,}",
             f"{r['build_ms']:.0f}", f"{r['render_ms']:.1f}",
             f"{r['parse_ms']:.1f}",
             f"{r.get('paint_ms', 0):.0f}" if r.get("paint_ms") else "-"]
            for r in rows]
    if not body:
        return "(no rows)"
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(head)]
    def line(cells: list[str]) -> str:
        return "| " + " | ".join(
            c.ljust(w) if i == 0 else c.rjust(w)
            for i, (c, w) in enumerate(zip(cells, widths))) + " |"
    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return "\n".join([line(head), rule, *(line(b) for b in body)])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="", help="comma-separated corpus names")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--json", default="")
    ap.add_argument("--svg-dir", default="")
    ap.add_argument("--no-paint", action="store_true")
    ap.add_argument("--text", default="names",
                    help="comma-separated text modes: names, outline, embed")
    ap.add_argument("--child", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    svg_dir = Path(args.svg_dir).resolve() if args.svg_dir else None
    modes = [m.strip() for m in args.text.split(",") if m.strip()] or ["names"]

    if args.child:
        rows = run_child(args.child, args.repeats, svg_dir, modes[0])
        print("@@JSON@@" + json.dumps(rows))
        return 0

    names = [n.strip() for n in args.only.split(",") if n.strip()] or list(CORPUS)
    rows: list[dict] = []
    for name in names:
        for mode in modes:
            started = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, __file__, "--child", name,
                 "--repeats", str(args.repeats), "--text", mode,
                 *(["--svg-dir", str(svg_dir)] if svg_dir else [])],
                capture_output=True, text=True, cwd=ROOT)
            marker = [out for out in proc.stdout.splitlines()
                      if out.startswith("@@JSON@@")]
            if not marker:
                print(f"{name}/{mode}: FAILED\n{proc.stdout[-2000:]}\n"
                      f"{proc.stderr[-2000:]}", file=sys.stderr)
                continue
            got = json.loads(marker[0][len("@@JSON@@"):])
            for row in got:
                row["total_s"] = round(time.perf_counter() - started, 1)
            rows += got
            print(f"  {name}/{mode}: {got[0]['bytes']:,} bytes", file=sys.stderr)

    if svg_dir and not args.no_paint:
        for row in rows:
            mode = row.get("text", "names")
            suffix = "" if mode == "names" else f".{mode}"
            svg = svg_dir / f"{row['figure'].replace(':', '_')}{suffix}.svg"
            if svg.exists():
                row["paint_ms"] = chrome_ms(svg)

    print(table(rows))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
