"""Run the snippets on docs/how-to.md, draw their figures, and keep its method table current.

    python tools/how_to_figures.py          # run every snippet, write its figure to docs/assets/how-to/
                                            # and regenerate the chart-method table on the page
    python tools/how_to_figures.py --check  # run the snippets and fail on a lint error or warning, or a
                                            # stale method table; write nothing

Each ```python block runs on its own, in a scratch directory, the way a reader
would run it. A block that leaves a figure (a name `figure` or `chart`) has that
figure linted; the image line directly after the block names the SVG that is
written for it. The test suite (tests/test_how_to.py) runs the same checks.
"""
from __future__ import annotations

import inspect
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

import inklet as i

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'docs' / 'how-to.md'
OUT = ROOT / 'docs' / 'assets' / 'how-to'

BLOCK = re.compile(r'^```python\n(.*?)^```', re.MULTILINE | re.DOTALL)
IMAGE = re.compile(r'^!\[[^\]]*\]\(assets/how-to/([\w-]+\.svg)\)', re.MULTILINE)
TABLE_START = '<!-- chart-methods:start -->'
TABLE_END = '<!-- chart-methods:end -->'

#: The chart methods the page lists, each with a one-line description. Every
#: one is looked up on `Chart` or, when `Chart` forwards it, on `Panel`; the
#: test calls each and checks that it returns the chart.
METHODS = {
    'labels': 'Axis titles and the chart title. `y2=` titles the right-hand axis.',
    'vline': 'A vertical reference line at x. `label=` names it, clear of the data.',
    'hline': 'A horizontal reference line at y. `label=` names it, clear of the data.',
    'annotate': 'A callout on one data point, with a leader line.',
    'brackets': 'Significance brackets between pairs of groups, from `(a, b, p)` triples.',
    'colorbar': 'The colour bar, or the one already drawn. Takes `title=`, `side=` and so on.',
    'legend': 'The key, or the one already drawn. Takes `side=`, `corner=`, `title=` and so on.',
    'size': 'The width (`single`, `double`, `slide` or millimetres) and the height in millimetres.',
}


class Snippet(NamedTuple):
    index: int           # 1-based, in page order
    code: str
    figure: str | None   # the SVG name the image after the block shows


def snippets(text: str | None = None) -> list[Snippet]:
    """Every python block on the page, with the figure its image line names."""
    text = PAGE.read_text() if text is None else text
    found = list(BLOCK.finditer(text))
    out = []
    for n, block in enumerate(found):
        end = found[n + 1].start() if n + 1 < len(found) else len(text)
        image = IMAGE.search(text, block.end(), end)
        out.append(Snippet(n + 1, block.group(1), image.group(1) if image else None))
    return out


def run(snippet: Snippet):
    """Execute one block in a fresh namespace; return the figure it leaves, or None."""
    namespace = {'__name__': '__main__'}
    theme = i.current_theme()
    try:
        exec(compile(snippet.code, f'how-to.md:block-{snippet.index}', 'exec'), namespace)
    finally:
        i.use_theme(theme)
    return namespace.get('figure', namespace.get('chart'))


def problems(compiled) -> list:
    """The lint diagnostics that are errors or warnings."""
    return [d for d in compiled.lint() if d.severity in ('error', 'warning')]


def shorthand(method) -> str:
    """The call's arguments, as the table shows them: positional names, then `...` for keywords."""
    params = [p for p in inspect.signature(method).parameters.values() if p.name != 'self']
    names = [p.name for p in params if p.kind is p.POSITIONAL_OR_KEYWORD]
    if any(p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD) for p in params):
        names.append('...')
    return ', '.join(names)


def method_table() -> str:
    """The table of chart methods, read from the Chart class and the Panel methods it forwards to."""
    from inklet.quick import Chart
    from inklet.plot.panel import Panel
    rows = ['| Method | Returns | What it does |', '|---|---|---|']
    for name, what in METHODS.items():
        if name in vars(Chart):
            method = getattr(Chart, name)
        else:
            method = getattr(Panel, name)
        rows.append(f'| `chart.{name}({shorthand(method)})` | the chart | {what} |')
    return '\n'.join(rows)


def with_table(text: str) -> str:
    """The page with its method table replaced by the one `method_table` makes."""
    start, end = text.index(TABLE_START), text.index(TABLE_END)
    return text[:start + len(TABLE_START)] + '\n' + method_table() + '\n' + text[end:]


def main(argv):
    check = '--check' in argv
    text = PAGE.read_text()
    failures = []
    for snippet in snippets(text):
        with tempfile.TemporaryDirectory() as scratch:
            here = os.getcwd()
            os.chdir(scratch)
            try:
                figure = run(snippet)
            finally:
                os.chdir(here)
        if snippet.figure is not None and figure is None:
            failures.append(f'block {snippet.index} shows {snippet.figure} but leaves no figure')
            continue
        if figure is None:
            continue
        compiled = figure.compile()
        serious = problems(compiled)
        if serious:
            failures.append(f'block {snippet.index}: ' + ', '.join(f'{d.severity} {d.code}' for d in serious)
                            + '\n' + compiled.report())
            continue
        if snippet.figure is not None and not check:
            OUT.mkdir(parents=True, exist_ok=True)
            compiled.save(OUT / snippet.figure)
            print(OUT / snippet.figure)
    if TABLE_START not in text or TABLE_END not in text:
        failures.append(f'{PAGE.name} has no {TABLE_START} block to hold the method table')
    elif with_table(text) != text:
        if check:
            failures.append(f'the method table on {PAGE.name} is out of date; run python tools/how_to_figures.py')
        else:
            PAGE.write_text(with_table(text))
            print(PAGE)
    if failures:
        raise SystemExit('\n\n'.join(failures))


if __name__ == '__main__':
    main(sys.argv[1:])
