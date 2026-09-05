"""Finding Blender, and saying so plainly when it is not there.

Blender is a *subprocess*, never an import. Its `bpy` module is built against
its own interpreter and its own numpy; importing it into this process would
either fail or, worse, half-work. Everything this package does goes out through
`subprocess.run` and comes back as an SVG file, which also means a crash inside
Blender is a return code rather than a segfault in the caller's Python.

The whole backend is optional. `import inklet` on a machine with no Blender must
work, so nothing here runs at import time; discovery happens on the first bake,
and what a caller gets when it fails is a sentence naming `INKLET_BLENDER` rather
than a `FileNotFoundError` from four frames down.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BlenderError", "BlenderNotFound", "BlenderTooOld", "Blender",
    "find_blender", "blender_available", "clear_discovery_cache",
    "ENV_VAR", "MINIMUM_VERSION", "CONVENTIONAL_PATHS",
]

#: Set this to an absolute path to pin one build. Named in every failure
#: message, because "install Blender" is not actionable when three are already
#: installed and none of them is on PATH.
ENV_VAR = "INKLET_BLENDER"

#: Line Art baking through `object.lineart_bake_strokes` plus the Grease Pencil
#: SVG exporter. Both exist from 3.x, but 4.2 is the first LTS where the pair
#: is stable enough to hash the output of, and it is the version this backend
#: has been measured against.
MINIMUM_VERSION = (4, 2)

#: Looked at in order, after `$INKLET_BLENDER` and after `$PATH`. These are where
#: a Blender that was unpacked rather than installed by a package manager ends
#: up; a tarball download is the normal way to get a specific LTS.
CONVENTIONAL_PATHS = (
    "~/.local/opt/blender/blender",
    "~/.local/bin/blender",
    "~/blender/blender",
    "/opt/blender/blender",
    "/usr/local/bin/blender",
    "/usr/bin/blender",
    "/snap/bin/blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "~/Applications/Blender.app/Contents/MacOS/Blender",
    "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
)

_VERSION_LINE = re.compile(r"^Blender\s+(\d+)\.(\d+)(?:\.(\d+))?")

# `blender --version` costs about 50 ms, and discovery is called from every
# bake, from `blender_available()` and from a test's skipif. Memoised by
# resolved path so the cost is paid once per process.
_probed: dict[str, "Blender | BlenderError"] = {}


class BlenderError(RuntimeError):
    """Anything this backend cannot do: no binary, a version too old, a bake
    that failed or timed out, an export that produced nothing."""


class BlenderNotFound(BlenderError):
    """No Blender executable could be found."""


class BlenderTooOld(BlenderError):
    """A Blender was found, but predates the API this backend uses."""


@dataclass(frozen=True, slots=True)
class Blender:
    """A binary that has been run once and answered."""

    path: Path
    version: tuple[int, int, int]
    banner: str          # the whole first line, e.g. "Blender 4.2.23 LTS"

    @property
    def release(self) -> str:
        return ".".join(str(n) for n in self.version)


def find_blender(executable: str | Path | None = None) -> Blender:
    """Locate a usable Blender, or raise saying exactly what to do about it.

    Order: the explicit argument, then `$INKLET_BLENDER`, then `blender` on
    `$PATH`, then the conventional install locations. The environment variable
    outranks `$PATH` on purpose -- a machine with a distribution Blender 3.6 on
    `$PATH` and a 4.2 unpacked in `~/.local/opt` is the common case, and the
    author should be able to say which one wins without editing `$PATH`.
    """
    for candidate, why in _candidates(executable):
        found = _probe(candidate)
        if isinstance(found, Blender):
            return found
        if why in ("explicit", "env"):
            # A path the author named and that does not work is an error, not
            # a reason to quietly fall through to some other build. The failure
            # is rebuilt rather than re-raised: `_probe` memoises its result,
            # and raising one exception instance twice staples the second
            # traceback onto the first.
            named = f"blender= names {candidate}" if why == "explicit" else (
                f"{ENV_VAR} names {candidate}")
            raise type(found)(f"{found}\n({named}; unset it to search "
                              f"$PATH and the usual install locations)")
    raise BlenderNotFound(
        "no Blender executable found. This backend renders line art by driving "
        f"Blender {MINIMUM_VERSION[0]}.{MINIMUM_VERSION[1]} or newer as a "
        f"subprocess. Install it and put it on PATH, or set {ENV_VAR} to the "
        "binary (not the directory): "
        f"{ENV_VAR}=/path/to/blender. Looked at: "
        + ", ".join(str(p) for p, _ in _candidates(executable))
    )


def blender_available(executable: str | Path | None = None) -> bool:
    """Whether a usable Blender exists. For choosing a backend and for skipping
    tests; never for changing output silently."""
    try:
        find_blender(executable)
    except BlenderError:
        return False
    return True


def clear_discovery_cache() -> None:
    """Forget every probe. Only useful to a test that moves the binary."""
    _probed.clear()


def _candidates(executable: str | Path | None) -> list[tuple[Path, str]]:
    """Every path worth trying, in order, with why it is being tried."""
    out: list[tuple[Path, str]] = []
    if executable is not None:
        out.append((Path(executable).expanduser(), "explicit"))
    env = os.environ.get(ENV_VAR)
    if env:
        out.append((Path(env).expanduser(), "env"))
    on_path = shutil.which("blender")
    if on_path:
        out.append((Path(on_path), "path"))
    out.extend((Path(p).expanduser(), "conventional") for p in CONVENTIONAL_PATHS)
    seen: list[Path] = []
    unique = []
    for path, why in out:
        if path not in seen:
            seen.append(path)
            unique.append((path, why))
    return unique


def _probe(path: Path) -> Blender | BlenderError:
    """Run `--version` and read it. Returns the failure rather than raising it,
    so the search can keep going past a candidate that did not work out."""
    key = str(path)
    if key in _probed:
        return _probed[key]
    result = _run_version(path)
    _probed[key] = result
    return result


def _run_version(path: Path) -> Blender | BlenderError:
    if not path.is_file():
        return BlenderNotFound(f"no such file: {path}")
    try:
        done = subprocess.run(
            [str(path), "--version"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except OSError as exc:
        return BlenderNotFound(f"cannot run {path}: {exc}")
    except subprocess.TimeoutExpired:
        return BlenderError(f"{path} did not answer --version within 60s")

    banner = ""
    version = None
    for line in done.stdout.splitlines():
        match = _VERSION_LINE.match(line.strip())
        if match:
            banner = line.strip()
            version = tuple(int(g) if g else 0 for g in match.groups())
            break
    if version is None:
        return BlenderNotFound(
            f"{path} does not identify itself as Blender "
            f"(`--version` said {done.stdout.strip()[:120]!r})"
        )
    if version[:2] < MINIMUM_VERSION:
        return BlenderTooOld(
            f"{path} is {banner}, which is too old: this backend needs "
            f"Blender {MINIMUM_VERSION[0]}.{MINIMUM_VERSION[1]} or newer for "
            f"Grease Pencil Line Art baking and SVG export. Point {ENV_VAR} at "
            "a newer build."
        )
    return Blender(path=path, version=version, banner=banner)
