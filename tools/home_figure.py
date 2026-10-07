"""Render the home page's one-call chart to docs/assets/home/growth.svg.

    python tools/home_figure.py

The code is tools/docs_home_chart.py. The home page shows that same file, and
tests/test_docs_site.py runs it and compares the output with the committed SVG,
so the page cannot drift from the figure. The script saves into the working
directory, so it runs in a temporary one here.
"""
from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'tools' / 'docs_home_chart.py'
OUT = ROOT / 'docs' / 'assets' / 'home' / 'growth.svg'


def main():
    source = SOURCE.read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory() as work, contextlib.chdir(work):
        namespace = {'__name__': '__docs__'}
        exec(compile(source, SOURCE.name, 'exec'), namespace)
        serious = [d for d in namespace['chart'].compile().lint()
                   if d.severity in ('error', 'warning')]
        if serious:
            raise SystemExit(f'lint {[(d.severity, d.code) for d in serious]}')
        OUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(work) / 'growth.svg', OUT)
    print(OUT)


if __name__ == '__main__':
    sys.exit(main())
