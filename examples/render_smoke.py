"""Renders examples/render_smoke.svg: one single-column figure, core prims only.

Deliberately no TextPrim -- text metrics come from `inklet.typeset`, and hand-faked
advances in an example would be a lie about where the ink lands. Colours are
literals here because `inklet.themes` owns tokens and this file is a caller, not
library code.

    .venv/bin/python examples/render_smoke.py
"""

from __future__ import annotations

import os

from inklet.core import (
    COLUMN_SINGLE, Diagram, EllipsePrim, PathPrim, RectPrim, Subpath, Vec2, pt,
)
from inklet.render import save_svg

MARGIN = 4.5  # 80 mm of content + 2 * 4.5 = one 89 mm column exactly


def card(name: str, cx: float, cy: float, fill: str) -> Diagram:
    prim = RectPrim(34.0, 16.0, radius=2.0)
    return Diagram(prim=prim, kind="card", name=name).styled(fill=fill).translated(cx, cy)


def curve(start: Vec2, end: Vec2, bulge: float) -> Diagram:
    """One cubic, bulging downward, so the file carries a real bezier."""
    c1 = Vec2(start.x, start.y + bulge)
    c2 = Vec2(end.x, end.y - bulge)
    flat = (start, c1, c2, end)  # geometry-only fallback for envelopes
    sub = Subpath(points=flat, curves=((start, c1, c2, end),))
    return Diagram(prim=PathPrim((sub,)), kind="link")


def build() -> Diagram:
    left = card("input", -23.0, -8.0, "#e8eef7")
    right = card("output", 23.0, -8.0, "#e8eef7")
    hub = Diagram(prim=EllipsePrim(11.0, 7.0), kind="hub", name="hub").styled(
        fill="#f6ecdf").translated(0.0, 12.0)

    hop = Diagram(prim=PathPrim.polyline((Vec2(-6.0, -8.0), Vec2(6.0, -8.0))),
                  kind="link").styled(stroke_dash=(1.2, 0.8))
    down_left = curve(Vec2(-23.0, 0.0), Vec2(-6.5, 8.0), 5.0)
    down_right = curve(Vec2(23.0, 0.0), Vec2(6.5, 8.0), 5.0)

    nodes = Diagram(children=(left, right, hub), kind="nodes", name="nodes").styled(
        stroke="#334155", stroke_width=pt(0.75))
    links = Diagram(children=(hop, down_left, down_right), kind="links",
                    name="links").styled(stroke="#94a3b8", stroke_width=pt(1.0),
                                         stroke_linecap="round")
    return Diagram(children=(nodes, links), kind="figure", name="smoke")


if __name__ == "__main__":
    figure = build()
    out = os.path.join(os.path.dirname(__file__), "render_smoke.svg")
    save_svg(figure, out, width=COLUMN_SINGLE, margin=MARGIN,
             background="#ffffff", title="inklet render smoke test")
    print(f"{out}  {os.path.getsize(out)} bytes  bbox {figure.bbox}")
