"""The `<name>.inklet.json` file that travels with an image.

Named points on a picture are data about that picture, not about the figure
using it: whoever decides where a mouse's nose is should have to decide once,
and every figure that places the mouse should get the answer for free. So the
anchors live next to the file, in fractions of the *subject's* bounding box --
fractions, so re-exporting the artwork at a different resolution does not
invalidate them, and of the subject rather than the canvas, so trimming the
white margin does not either.

    mouse.png
    mouse.inklet.json   {"anchors": {"nose": [0.12, 0.44]},
                      "license": "CC BY 4.0", "attribution": "..."}

The licence fields are read and reported verbatim. Nothing in this module
invents, infers or defaults them: an asset with no recorded licence is reported
as having no recorded licence, which is a fact an author can act on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .deps import AssetError

__all__ = ["Sidecar", "sidecar_path", "load_sidecar", "coerce_anchors", "SUFFIX"]

SUFFIX = ".inklet.json"

_LICENCE_FIELDS = ("license", "attribution", "source_url", "notes")


@dataclass(frozen=True)
class Sidecar:
    """What was found beside the image. Empty when there is no sidecar."""

    path: Path | None = None
    anchors: tuple[tuple[str, tuple[float, float]], ...] = ()
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    notes: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.path is None


def sidecar_path(image: str | Path) -> Path:
    """`mouse.png` -> `mouse.inklet.json`, beside it."""
    file = Path(image)
    return file.with_name(file.stem + SUFFIX)


def load_sidecar(image: str | Path) -> Sidecar:
    path = sidecar_path(image)
    if not path.is_file():
        return Sidecar()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # Loud, because a sidecar that is present and unreadable is an
        # authoring mistake; silently ignoring it loses the anchors an author
        # believes they have and the failure surfaces much later.
        raise AssetError(f"cannot read sidecar {str(path)!r}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise AssetError(f"sidecar {str(path)!r} must contain a JSON object")

    fields = {name: _text(data.get(name), name, path) for name in _LICENCE_FIELDS}
    return Sidecar(path=path, anchors=coerce_anchors(data.get("anchors"), path),
                   **fields)


def coerce_anchors(raw: Any, where: Path | str | None = None
                   ) -> tuple[tuple[str, tuple[float, float]], ...]:
    """Validate `{"nose": [u, v]}` into a sorted tuple of pairs.

    Sorted by name so that two runs -- or a JSON file and a Python dict written
    in a different order -- produce the same anchors in the same order, and so
    that the hash of the parameters does not depend on authoring order.
    """
    if raw is None:
        return ()
    if not isinstance(raw, Mapping):
        raise AssetError(f"anchors must be an object of name -> [u, v]{_at(where)}")
    out = []
    for name in sorted(raw):
        value = raw[name]
        try:
            u, v = value
            pair = (float(u), float(v))
        except (TypeError, ValueError) as exc:
            raise AssetError(
                f"anchor {name!r} must be two numbers, got {value!r}{_at(where)}"
            ) from exc
        out.append((str(name), pair))
    return tuple(out)


def _text(value: Any, field: str, where: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AssetError(f"sidecar field {field!r} must be a string{_at(where)}")
    return value


def _at(where: Path | str | None) -> str:
    return f" in {str(where)!r}" if where else ""
