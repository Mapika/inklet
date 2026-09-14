"""Page export settings shared by authored figures and compiled snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core import Diagram
from .outline import TEXT_MODES, resolve_text_mode
from .pdf import PDF_TEXT_MODES, to_pdf
from .raster import to_png
from .scene import RenderScene
from .svg import to_svg


def validate_pdf_text(text: str) -> None:
    if text not in PDF_TEXT_MODES:
        raise ValueError(
            f"unknown text mode {text!r} for PDF; expected one of "
            f"{', '.join(PDF_TEXT_MODES)}"
            + ("; PDF has no font-name mode, so a searchable PDF is "
               "text='embed'" if text == "names" else ""))


def save_outputs(figure, *paths: str | Path, **kwargs) -> None:
    """Dispatch formats through the caller, retaining its export overrides."""
    mode = kwargs.get("text")
    if mode is not None and mode not in TEXT_MODES:
        raise ValueError(
            f"unknown text mode {mode!r}; expected one of "
            f"{', '.join(TEXT_MODES)}"
        )
    for path in paths:
        target = Path(path)
        suffix = target.suffix.lower()
        if suffix not in (".svg", ".pdf", ".png"):
            raise NotImplementedError(
                f"{target.suffix} output is not supported; write .svg, .pdf or .png"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if suffix == '.png':
            target.write_bytes(figure.to_png(**kwargs))
        elif suffix == ".pdf":
            options = {k: v for k, v in kwargs.items() if k != "text"}
            if mode in PDF_TEXT_MODES:
                options["text"] = mode
            target.write_bytes(figure.to_pdf(**options))
        else:
            target.write_text(figure.to_svg(**kwargs), encoding="utf-8")


@dataclass(frozen=True)
class RenderedPage:
    """A resolved page and the paper colour used by its exporters."""

    root: Diagram | RenderScene
    paper: str

    def to_svg(self, *, text: str = "names", **kwargs) -> str:
        """Return the page as SVG text."""
        options = dict(
            margin=0.0,
            background=self.paper,
            text=resolve_text_mode(text),
        )
        options.update(kwargs)
        return to_svg(self.root, **options)

    def to_pdf(self, *, text: str = "outline", **kwargs) -> bytes:
        """Return the page as PDF bytes."""
        validate_pdf_text(text)
        options = dict(
            margin=0.0,
            background=self.paper,
            text=text,
        )
        options.update(kwargs)
        return to_pdf(self.root, **options)

    def to_png(self, *, dpi=150, **kwargs) -> bytes:
        """Return the page as PNG bytes at physical DPI."""
        return to_png(self.root, dpi=dpi, **(dict(background=self.paper) | kwargs))

    def save(self, *paths: str | Path, **kwargs) -> None:
        """Write the page to SVG, PDF or PNG files by suffix."""
        save_outputs(self, *paths, **kwargs)
