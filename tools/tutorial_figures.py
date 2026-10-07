"""Draw the figures of the one-call tutorial, from the page's own code.

    python tools/tutorial_figures.py     # write docs/assets/tutorial/*.svg

`docs/quick-charts.md` runs as one script. Its python blocks execute in order
in one namespace, so a later block can reuse a name from an earlier one. A
figure is declared by an HTML comment on the line before its image:

    <!-- figure: chart -->
    ![Caption](assets/tutorial/one-call.svg)

The variable named in the comment is drawn straight after the block that came
before the image, so the picture is the code on the page. The data file under
docs/assets/data is copied beside the code, as a reader would have it. The
test in tests/test_quick_tutorial.py runs the same blocks and checks each chart
lints clean.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'docs' / 'quick-charts.md'
DATA = ROOT / 'docs' / 'assets' / 'data'
OUT = ROOT / 'docs' / 'assets' / 'tutorial'

BLOCK = re.compile(r'^```python\n(.*?)^```', re.MULTILINE | re.DOTALL)
FIGURE = re.compile(r'<!-- figure: (\w+) -->\n!\[[^\]]*\]\(assets/tutorial/([\w-]+)\.svg\)')


def blocks(text: str) -> list[tuple[str, tuple[str, str] | None]]:
    """Each python block in order, as (code, figure). A figure is (variable, file stem) or None."""
    found = list(BLOCK.finditer(text))
    out = []
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        picture = FIGURE.search(text, match.end(), end)
        figure = (picture.group(1), picture.group(2)) if picture else None
        out.append((match.group(1), figure))
    return out


def run(text: str):
    """Execute the blocks in order in one namespace, yielding after each one.

    Yields (index, code, figure, namespace). The data files are copied into the
    current directory first, so the snippets can name them.
    """
    for path in DATA.glob('*.csv'):
        shutil.copy(path, Path.cwd() / path.name)
    namespace = {'__name__': '__main__'}
    for index, (code, figure) in enumerate(blocks(text)):
        exec(compile(code, f'quick-charts.md:block-{index + 1}', 'exec'), namespace)
        yield index, code, figure, namespace


def draw(out: Path = OUT) -> list[Path]:
    """Write every declared figure to `out` as SVG; returns the paths written."""
    written = []
    out.mkdir(parents=True, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix='tutorial-')
    before = os.getcwd()
    os.chdir(scratch)
    try:
        for _, _, figure, namespace in run(PAGE.read_text()):
            if figure is None:
                continue
            variable, stem = figure
            path = out / f'{stem}.svg'
            namespace[variable].save(path)
            written.append(path)
    finally:
        os.chdir(before)
        shutil.rmtree(scratch, ignore_errors=True)
    return written


def main() -> None:
    for path in draw():
        print(path)


if __name__ == '__main__':
    main()
