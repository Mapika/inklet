"""Content-addressed storage for derived rasters.

Every step in the pipeline -- cutout, crop, line art, harmonisation -- produces
a new PNG that the SVG backend embeds as a data URI. Two things follow from
that. The derived file has to be reproducible, because "same input, same SVG
bytes" is a hard invariant of this library and the raster is most of those
bytes. And it has to be cached, because XDoG over a 12-megapixel photograph is
not something to redo on every `fig.save()`.

Both fall out of naming the file after a hash of everything that went into it:
the source bytes, the parameters, and a version counter for when the pipeline
itself changes. A cache hit is then provably the same file the pipeline would
have written, so the cache can never be stale.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from .deps import AssetError

__all__ = [
    "PIPELINE_VERSION", "content_hash", "derive_key", "cache_root",
    "cache_path", "cached_file", "canonical", "slug",
]

# Bump when a change to this package would produce different pixels from the
# same inputs -- or, as in 2, a materially different file from the same pixels.
# Without it, an old cache entry outlives the code that made it.
#   2: `save_png` picks the smallest PNG mode that is still exact, instead of
#      writing everything as RGBA.
PIPELINE_VERSION = 2

_READ_CHUNK = 1 << 20


def content_hash(path: Path) -> str:
    """SHA-256 of a file's bytes, streamed so a 100 MB TIFF does not have to be
    resident. This is also the provenance hash: it identifies the picture
    independently of what the author happened to call it."""
    if not Path(path).is_file():
        raise AssetError(f"no such image: {str(path)!r}")
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AssetError(f"cannot read image {str(path)!r}: {exc}") from exc
    return digest.hexdigest()


def canonical(value: Any) -> str:
    """Parameters as one stable string.

    `sort_keys` is the load-bearing part: a dict's insertion order must never
    reach the hash, or the same figure built by two different call paths would
    cache to two different files and the SVGs would differ.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def derive_key(source_hash: str, *parts: Any) -> str:
    """Hash of the source plus every parameter that affects the output."""
    digest = hashlib.sha256()
    digest.update(f"inklet.assets/{PIPELINE_VERSION}\n".encode())
    digest.update(source_hash.encode())
    for part in parts:
        digest.update(b"\n")
        digest.update(canonical(part).encode())
    return digest.hexdigest()[:32]


def cache_root(override: str | Path | None = None) -> Path:
    """Where derived rasters live.

    Explicit argument, then `INKLET_CACHE_DIR`, then the XDG cache directory. The
    temp-directory fallback is for read-only homes in CI; nothing about the
    location reaches the SVG, which embeds the bytes rather than the path, so a
    different cache directory still yields identical output.
    """
    if override is not None:
        return Path(override)
    env = os.environ.get("INKLET_CACHE_DIR")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CACHE_HOME")
    home = Path(base) if base else Path.home() / ".cache"
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path(tempfile.gettempdir()) / "inklet-cache" / "assets"
    return home / "inklet" / "assets"


def cached_file(root: Path, stem: str, key: str, suffix: str,
                build: Callable[[Path], None]) -> Path:
    """Return the derived file, building it only if it is not already there.

    The build writes to a sibling temp file and renames, so a crash or a second
    process mid-build can never leave a half-written PNG under a name that
    claims to be a complete one.
    """
    root.mkdir(parents=True, exist_ok=True)
    target = cache_path(root, stem, key, suffix)
    if target.exists():
        return target
    temp = target.with_name(f"{target.name}.{os.getpid()}.part")
    try:
        build(temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    return target


def cache_path(root: Path, stem: str, key: str, suffix: str) -> Path:
    """Where a derived file lands. Exposed so a caller can test for a hit
    without going through `cached_file` and its build callback."""
    return root / f"{slug(stem)}-{key}{suffix}"


def slug(stem: str) -> str:
    """The human-readable half of a cache filename. Restricted to characters
    that survive every filesystem, since the source stem is whatever the author
    named their photograph."""
    kept = [c if (c.isalnum() or c in "-_") else "-" for c in stem]
    return "".join(kept).strip("-")[:48] or "asset"
