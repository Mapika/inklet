"""Backends that turn a resolved Diagram into a file. SVG is the reference one.

SVG is what you keep editing; PDF is what you send. `outline_text` is the
transform that lets the first draw like the second, by turning shaped text into
geometry before either backend sees the tree -- though `to_svg(text="outline")`
is the cheaper spelling of the same picture, because a backend that sees the
glyphs one at a time can define each of them once and place the rest by
reference, and `to_svg(text="embed")` is usually cheaper still and keeps the
text selectable.
"""

from .outline import TEXT_MODES, outline_text, resolve_text_mode
from .pdf import PDF_TEXT_MODES, save_pdf, to_pdf
from .svg import save_svg, to_svg
from .raster import save_png, to_png, rasterize

__all__ = ["to_svg", "save_svg", "to_pdf", "save_pdf", "to_png", "save_png", "rasterize",
           "outline_text", "resolve_text_mode", "TEXT_MODES",
           "PDF_TEXT_MODES"]
