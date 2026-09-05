"""Images that behave like diagrams.

A scientist has a JPEG of a mouse and wants it in figure 1. Pasted into
Illustrator it is a rectangle with a white background: arrows stop at the
picture frame, the stack spaces itself around empty margin, and its colours
belong to whoever took the photograph. `inklet.asset()` returns a `Diagram`
instead -- one that knows its own silhouette, sizes itself to the subject
rather than to the canvas, carries named points, and remembers where it came
from.

    mouse = inklet.asset("mouse.png", width=18)
    fig.add(inklet.hstack([mouse, inklet.box("V1")], gap=6))
    fig.link(mouse.at("nose"), stimulus)      # anchors from mouse.inklet.json
    print(credit_lines(fig.build()[0]))       # what to put under the figure

Nothing here is imported until it is called, so `import inklet` still works with
no image libraries installed at all. The default path needs only Pillow and
NumPy (`pip install "inklet[images]"`); `rembg` and `potrace` are optional and
each says in its own docstring what it is good for.
"""

from __future__ import annotations

from .asset import ASSET_KIND, DEFAULT_WIDTH, SILHOUETTE_KIND, asset
from .cache import PIPELINE_VERSION, cache_root, content_hash
from .cutout import Cutout, cutout_backends, register_cutout
from .deps import AssetError, MissingDependency
from .harmonise import Harmonise
from .lineart import LineArt, potrace_available
from .provenance import Provenance, credit_lines, credits, provenance_of
from .sidecar import Sidecar, load_sidecar, sidecar_path
from .silhouette import Silhouette

__all__ = [
    "asset", "DEFAULT_WIDTH", "ASSET_KIND", "SILHOUETTE_KIND",
    "Cutout", "LineArt", "Harmonise", "Silhouette",
    "register_cutout", "cutout_backends", "potrace_available",
    "Provenance", "credits", "credit_lines", "provenance_of",
    "Sidecar", "load_sidecar", "sidecar_path",
    "AssetError", "MissingDependency",
    "cache_root", "content_hash", "PIPELINE_VERSION",
]
