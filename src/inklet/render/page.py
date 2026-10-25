"""Page export settings shared by authored figures and compiled snapshots."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
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


def _keyword_only(func) -> frozenset[str]:
    return frozenset(p.name for p in inspect.signature(func).parameters.values()
                     if p.kind is inspect.Parameter.KEYWORD_ONLY)


_SVG_OPTIONS = _keyword_only(to_svg)

#: The export keywords each file format takes, read from the writers. PNG is
#: drawn through the SVG writer, so it takes SVG's keywords and its own `dpi`.
_EXPORT_OPTIONS = {".svg": _SVG_OPTIONS, ".pdf": _keyword_only(to_pdf),
                   ".png": _SVG_OPTIONS | {"dpi"}}


def check_export_options(suffixes, options, where: str = "save()") -> None:
    """Refuse an export keyword that the requested formats do not take.

    Runs before anything is rendered, so a misspelt keyword costs no file and
    no layout. `save()` writes several formats at once, so `dpi=` is accepted
    there whatever they are: the vector formats ignore a raster resolution.
    `ids=` (SVG element ids) is accepted when an SVG is among the files, and
    `write=` always; neither changes a PDF.
    """
    formats = [s for s in suffixes if s in _EXPORT_OPTIONS]
    if not formats or not options:
        return
    saving = where == "save()"
    accepted = frozenset().union(*(_EXPORT_OPTIONS[s] for s in formats))
    if saving:
        accepted |= {"dpi", "write", "ids"}
    for key in options:
        if key not in accepted:
            raise TypeError(
                f"{where} got an unexpected keyword {key!r}; it accepts "
                f"{', '.join(f'{k}=' for k in sorted(accepted))}")
        if saving and key in ("dpi", "write") or (saving and key == "ids" and ".svg" in formats):
            continue
        for suffix in formats:
            if key not in _EXPORT_OPTIONS[suffix]:
                takes = ', '.join(f'{k}=' for k in sorted(_EXPORT_OPTIONS[suffix]))
                raise TypeError(
                    f"{where} got {key}=, which {suffix} output does not take; "
                    f"{suffix} takes {takes}")


#: What `save(write=...)` accepts.
WRITE_MODES = ("always", "changed")


def save_outputs(figure, *paths: str | Path, write: str = "always",
                 **kwargs) -> dict[str, bool]:
    """Dispatch formats through the caller, retaining its export overrides.

    Every file is rendered first and then written, each through a temporary
    file in the same directory and an atomic rename, so a reader never sees a
    half-written PDF and a failure in one format leaves the others as they
    were. All files written by one call get the same modification time, so a
    build that picks "the newest of pdf, svg and png" sees one export rather
    than whichever format happened to finish in a later second (the PNG,
    usually, since it is drawn last).

    `write="changed"` leaves a file whose bytes would not change untouched,
    timestamp included -- inklet's output is byte-deterministic, so a rebuild
    of an unchanged figure changes nothing on disk and nothing downstream
    rebuilds. If any of the files does change, all of them are written, so the
    set keeps one timestamp. Returns `{path: written}`.
    """
    import os
    import tempfile
    if write not in WRITE_MODES:
        raise ValueError(f"unknown write mode {write!r}; expected one of {', '.join(WRITE_MODES)}")
    mode = kwargs.get("text")
    if mode is not None and mode not in TEXT_MODES:
        raise ValueError(
            f"unknown text mode {mode!r}; expected one of "
            f"{', '.join(TEXT_MODES)}"
        )
    check_export_options([Path(p).suffix.lower() for p in paths], kwargs)
    # A raster resolution means nothing to the vector formats saved alongside.
    vector = {k: v for k, v in kwargs.items() if k != "dpi"}
    rendered: list[tuple[Path, bytes]] = []
    for path in paths:
        target = Path(path)
        suffix = target.suffix.lower()
        if suffix not in (".svg", ".pdf", ".png"):
            raise NotImplementedError(
                f"{target.suffix} output is not supported; write .svg, .pdf or .png"
            )
        if suffix == '.png':
            data = figure.to_png(**kwargs)
        elif suffix == ".pdf":
            # `ids` names SVG elements; a PDF has none to name.
            options = {k: v for k, v in vector.items() if k not in ("text", "ids")}
            if mode in PDF_TEXT_MODES:
                options["text"] = mode
            data = figure.to_pdf(**options)
        else:
            data = figure.to_svg(**vector).encode("utf-8")
        rendered.append((target, data))
    if write == "changed" and all(_same_bytes(t, d) for t, d in rendered):
        return {str(t): False for t, _ in rendered}
    stamp = None
    for target, data in rendered:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        try:
            os.chmod(target, 0o666 & ~_umask())
        except OSError:
            pass
        if stamp is None:
            stamp = target.stat().st_mtime_ns
        os.utime(target, ns=(stamp, stamp))
    return {str(t): True for t, _ in rendered}


def _umask() -> int:
    import os
    mask = os.umask(0)
    os.umask(mask)
    return mask


def _same_bytes(target: Path, data: bytes) -> bool:
    try:
        return target.stat().st_size == len(data) and target.read_bytes() == data
    except OSError:
        return False


@dataclass(frozen=True)
class RenderedPage:
    """A resolved page and the paper colour used by its exporters."""

    root: Diagram | RenderScene
    paper: str

    def to_svg(self, *, text: str = "names", **kwargs) -> str:
        """Return the page as SVG text."""
        check_export_options([".svg"], kwargs, "to_svg()")
        options = dict(
            margin=0.0,
            background=self.paper,
            text=resolve_text_mode(text),
        )
        options.update(kwargs)
        return to_svg(self.root, **options)

    def to_pdf(self, *, text: str = "outline", **kwargs) -> bytes:
        """Return the page as PDF bytes."""
        check_export_options([".pdf"], kwargs, "to_pdf()")
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
        check_export_options([".png"], kwargs, "to_png()")
        return to_png(self.root, dpi=dpi, **(dict(background=self.paper) | kwargs))

    def save(self, *paths: str | Path, **kwargs) -> dict[str, bool]:
        """Write the page to SVG, PDF or PNG files by suffix; see `Figure.save`."""
        return save_outputs(self, *paths, **kwargs)
