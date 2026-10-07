"""Inline display in Jupyter, VS Code and other IPython front ends.

Figures are shown as an `<img>` holding the SVG, not as inline SVG: two
inline figures would share one DOM, and their embedded font subsets and clip
ids would collide. The raw SVG is offered as well for front ends without HTML.
"""
from __future__ import annotations

from base64 import b64encode
from html import escape

#: On-screen scale for physical sizes. Figures are millimetre-exact; at 1:1 a
#: single-column figure is a 336-pixel thumbnail on most screens.
SCALE = 1.5

_PX_PER_MM = 96 / 25.4


def mimebundle(compiled) -> dict:
    """A display bundle for a `CompiledFigure` or anything with `to_svg()`."""
    svg = compiled.to_svg()
    width = _width(compiled)
    style = 'max-width:100%;height:auto;background:white'
    size = f' width="{width * _PX_PER_MM * SCALE:.0f}"' if width else ''
    data = b64encode(svg.encode('utf-8')).decode('ascii')
    report = _summary(compiled)
    html = f'<img src="data:image/svg+xml;base64,{data}"{size} style="{style}" alt="inklet figure">'
    if report:
        html += f'<pre style="font-size:11px;margin:4px 0 0">{escape(report)}</pre>'
    plain = f'<inklet figure, {width:.0f} mm wide>' if width else '<inklet figure>'
    if report:
        plain += '\n' + report
    return {'text/html': html, 'image/svg+xml': svg, 'text/plain': plain}


def _width(compiled):
    try:
        root = compiled.root if hasattr(compiled, 'root') else compiled.build()[0]
        return root.bbox.width
    except Exception:
        return None


def _summary(compiled) -> str:
    """Warnings worth seeing next to the figure; silent when it is clean."""
    try:
        diagnostics = compiled.lint()
    except Exception:
        return ''
    serious = [d for d in diagnostics if getattr(d, 'severity', '') in ('error', 'warning')]
    if not serious:
        return ''
    from .diagnostics import format_report
    return format_report(serious)
