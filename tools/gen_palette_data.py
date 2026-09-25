"""Regenerate `src/inklet/themes/_palette_data.py` from the published sources.

The perceptually uniform maps ship as 256-entry tables. Inklet keeps an
evenly spaced subset of the *published entries themselves* -- no resampling,
no rounding beyond the 8-bit hex every renderer uses -- and picks the
smallest subset for which interpolating between the kept stops reproduces
every one of the 256 published entries within CIEDE2000 < 1 in each of the
three spaces `inklet` interpolates in (OKLab, CIELAB and sRGB). Evenly spaced
means the step must divide 255: 17, 15, 5, 3 or 1 entries.

Sources are downloaded from pinned URLs and verified by SHA-256:

    .venv/bin/python tools/gen_palette_data.py            # rewrite the module
    .venv/bin/python tools/gen_palette_data.py --check    # fail if stale

`--cache DIR` keeps the downloads (default `out/palette-sources`).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inklet.themes import color as C  # noqa: E402
from inklet.themes.color import parse_color, to_hex  # noqa: E402

TARGET = ROOT / "src" / "inklet" / "themes" / "_palette_data.py"

SOURCES = {
    "matplotlib": (
        "https://raw.githubusercontent.com/matplotlib/matplotlib/v3.9.2/lib/matplotlib/_cm_listed.py",
        "86980cc7b6e3c49c799e5d4f6d0bda0835011d07fc9e3691accda231a05e64e3",
    ),
    "crameri": (
        "https://files.pythonhosted.org/packages/83/17/24e1d6d7a882a15fed5dcf7528891c9782613fd9a2ebe1bb426f4f1ef581/cmcrameri-1.10-py3-none-any.whl",
        "0ccc9970fe35d74543bb8aeca5a5a97d8a09de71d2237d1bb714c9968cc2018d",
    ),
    "brewer": (
        "https://raw.githubusercontent.com/axismaps/colorbrewer/7d135fc4e19eda73f2eb1bf55fcdf4a04fe4881f/export/colorbrewer.json",
        "729cb527c1edcf3267c4521df29ede5092f3e6171c5a259e2ebdd252335840b9",
    ),
}

MATPLOTLIB = ("viridis", "cividis", "inferno", "plasma", "magma")

# Crameri's own classes (Scientific colour maps 8.0 user guide). The
# multi-sequential topography maps (bukavu, fes, oleron) and the categorical
# *S variants are left out; the first need a split point to be used honestly
# and the second are 100-colour look-up sets rather than figure palettes.
CRAMERI = {
    "sequential": (
        "batlow", "batlowK", "batlowW", "acton", "bamako", "bilbao", "buda",
        "davos", "devon", "glasgow", "grayC", "hawaii", "imola", "lajolla",
        "lapaz", "lipari", "navia", "nuuk", "oslo", "tokyo", "turku",
    ),
    "diverging": (
        "bam", "berlin", "broc", "cork", "lisbon", "managua", "roma",
        "tofino", "vanimo", "vik",
    ),
    "cyclic": ("bamO", "brocO", "corkO", "romaO", "vikO"),
}

BREWER_KINDS = {"qual": "categorical", "seq": "sequential", "div": "diverging"}

STEPS = (17, 15, 5, 3, 1)
TOLERANCE = 1.0


# The comparison runs in floating point on both sides: against the published
# floating-point entry, not its 8-bit rounding, and on the interpolated value
# before it is rounded for output. Rounding either side first measures the
# 8-bit grid instead of the interpolation -- one code value of jitter in a
# near-black grey is already a CIEDE2000 difference of 1-2, which is why a
# comparison against hex entries never converges, however dense the stops.

def _lab(rgb255) -> tuple[float, float, float]:
    linear = [C._linearize(c) for c in rgb255]
    x, y, z = (v / w for v, w in zip(C._apply(C._RGB_TO_XYZ, linear), C._D65))
    fx, fy, fz = C._lab_f(x), C._lab_f(y), C._lab_f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _lab_to_rgb(lab) -> list[float]:
    fy = (lab[0] + 16) / 116
    fx, fz = fy + lab[1] / 500, fy - lab[2] / 200
    xyz = [C._lab_f_inv(f) * w for f, w in zip((fx, fy, fz), C._D65)]
    return [C._encode(c) * 255.0 for c in C._apply(C._XYZ_TO_RGB, xyz)]


def _oklab_to_rgb(lab) -> list[float]:
    return [C._encode(c) * 255.0 for c in C._oklab_to_linear(lab)]


def _lerp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def _sampler(stops: list[str], space: str):
    if space == "oklab":
        points = [C.to_oklab(s) for s in stops]
        back = _oklab_to_rgb
    elif space == "lab":
        points = [C.to_lab(s) for s in stops]
        back = _lab_to_rgb
    else:
        points = [parse_color(s) for s in stops]
        back = list

    def sample(t: float) -> list[float]:
        position = t * (len(points) - 1)
        index = min(int(position), len(points) - 2)
        return back(_lerp(points[index], points[index + 1], position - index))
    return sample


def _error(stops: list[str], rows: list[list[float]]) -> float:
    last = len(rows) - 1
    reference = [_lab([c * 255.0 for c in row]) for row in rows]
    worst = 0.0
    for space in ("oklab", "lab", "srgb"):
        sample = _sampler(stops, space)
        for i, lab in enumerate(reference):
            worst = max(worst, C._ciede2000(_lab(sample(i / last)), lab))
    return worst


def fetch(key: str, cache: Path) -> bytes:
    url, digest = SOURCES[key]
    path = cache / url.rsplit("/", 1)[1]
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    actual = hashlib.sha256(data).hexdigest()
    if actual != digest:
        raise SystemExit(f"{url}: SHA-256 {actual} does not match pinned {digest}")
    return data


def as_hex(rows) -> list[str]:
    return [to_hex([c * 255.0 for c in row]) for row in rows]


def matplotlib_tables(source: bytes) -> dict[str, list[str]]:
    tree = ast.parse(source.decode())
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith("_") and name.endswith("_data"):
                key = name[1:-5]
                if key in MATPLOTLIB:
                    tables[key] = ast.literal_eval(node.value)
    return tables


def crameri_tables(wheel: bytes) -> dict[str, list[str]]:
    tables = {}
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        for names in CRAMERI.values():
            for name in names:
                text = archive.read(f"cmcrameri/cmaps/{name}.txt").decode()
                rows = [[float(v) for v in line.split()] for line in text.splitlines() if line.strip()]
                tables[name] = rows
    return tables


def fit(rows: list[list[float]]) -> tuple[list[str], float]:
    """The sparsest evenly spaced subset of `rows` that reproduces them."""
    table = as_hex(rows)
    last = len(table) - 1
    for step in STEPS:
        if last % step:
            continue
        stops = table[::step]
        worst = _error(stops, rows)
        if worst < TOLERANCE:
            return stops, worst
    raise SystemExit("no subset reproduces the table")


def brewer_schemes(source: bytes) -> list[tuple[str, str, list[str]]]:
    data = json.loads(source)
    out = []
    for name in sorted(data):
        entry = data[name]
        kind = BREWER_KINDS[entry["type"]]
        largest = max(int(k) for k in entry if k.isdigit())
        colors = []
        for text in entry[str(largest)]:
            r, g, b = (int(v) for v in text[4:-1].split(","))
            colors.append(to_hex((r, g, b)))
        out.append((name, kind, colors))
    return out


def render(cache: Path) -> str:
    mpl = matplotlib_tables(fetch("matplotlib", cache))
    cram = crameri_tables(fetch("crameri", cache))
    brewer = brewer_schemes(fetch("brewer", cache))
    lines = [
        '"""Palette stops generated by `tools/gen_palette_data.py`. Do not edit.',
        "",
        "Every value is a published entry, converted to 8-bit hex. The maps keep an",
        "evenly spaced subset of their 256 entries; the comment on each gives the",
        "step and the worst CIEDE2000 error of re-interpolating the full table.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# name -> (kind, stops)",
        "MATPLOTLIB: dict[str, tuple[str, tuple[str, ...]]] = {",
    ]

    def emit(name: str, kind: str, table: list[str]) -> None:
        stops, worst = fit(table)
        step = 255 // (len(stops) - 1)
        lines.append(f"    # every {step}th of {len(table)} entries, max dE00 {worst:.2f}")
        lines.append(f"    {name.lower()!r}: ({kind!r}, (")
        for i in range(0, len(stops), 8):
            chunk = ", ".join(repr(c) for c in stops[i:i + 8])
            lines.append(f"        {chunk},")
        lines.append("    )),")

    for name in MATPLOTLIB:
        emit(name, "sequential", mpl[name])
    lines += ["}", "", "CRAMERI: dict[str, tuple[str, tuple[str, ...]]] = {"]
    for kind, names in CRAMERI.items():
        for name in names:
            emit(name, kind, cram[name])
    lines += ["}", "", "# ColorBrewer, largest class of each scheme.",
              "BREWER: dict[str, tuple[str, tuple[str, ...]]] = {"]
    for name, kind, colors in brewer:
        lines.append(f"    {name.lower()!r}: ({kind!r}, (")
        for i in range(0, len(colors), 8):
            chunk = ", ".join(repr(c) for c in colors[i:i + 8])
            lines.append(f"        {chunk},")
        lines.append("    )),")
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cache", type=Path, default=ROOT / "out" / "palette-sources")
    args = parser.parse_args()
    text = render(args.cache)
    if args.check:
        if TARGET.read_text() != text:
            print(f"{TARGET} is out of date; run tools/gen_palette_data.py")
            return 1
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
