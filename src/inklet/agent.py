"""The usage guide for coding agents, and its installation as a skill.

`inklet guide` prints the guide shipped with this version, so an agent reads
instructions that match the code it is about to call. `--api` adds every plot
method with its signature, read from the installed `Panel` rather than written
down, so it cannot fall behind.
"""
from __future__ import annotations

import inspect
from importlib.resources import files
from pathlib import Path

SKILL_DESCRIPTION = (
    'Make publication-quality plots and multi-panel figures with the inklet Python '
    'library (line, scatter, bar, histogram, box, violin, heatmap, regression and 100+ '
    'scientific plot types; SVG/PDF/PNG). Use when asked to plot, chart or visualize '
    'data, or to make a figure for a paper, report or slide.'
)

#: Panel methods that are plumbing rather than marks.
_INTERNAL = {'build', 'draw', 'over', 'under', 'place', 'placed', 'point', 'coord', 'marks'}


def guide(*, api: bool = False) -> str:
    """The agent guide as Markdown; `api=True` appends the plot method index."""
    text = files('inklet').joinpath('guide.md').read_text(encoding='utf-8')
    if api:
        text = text.rstrip() + '\n\n' + api_index()
    return text


def api_index() -> str:
    """Every `Panel` method (usable on `plot_spec()` and on charts) with its signature."""
    from .plot.panel import Panel
    lines = ['## Plot methods', '',
             'Call these on a chart (`chart.volcano(...)`) or on `i.plot_spec()`.',
             'Positional `points` are (x, y) rows; `groups` map a category to its samples.', '']
    for name, method in sorted(inspect.getmembers(Panel, inspect.isfunction)):
        if name.startswith('_') or name in _INTERNAL:
            continue
        signature = _signature(method)
        doc = (inspect.getdoc(method) or '').split('\n\n')[0].replace('\n', ' ')
        lines.append(f'- `{name}{signature}`' + (f': {doc}' if doc else ''))
    return '\n'.join(lines) + '\n'


def _signature(method) -> str:
    """Parameter names and defaults, without annotations or deprecated keywords."""
    parts, starred = [], False
    for param in list(inspect.signature(method).parameters.values())[1:]:
        if param.kind is param.VAR_POSITIONAL:
            parts.append('*' + param.name)
            starred = True
        elif param.kind is param.VAR_KEYWORD:
            parts.append('**' + param.name)
        else:
            if param.kind is param.KEYWORD_ONLY and not starred:
                parts.append('*')
                starred = True
            if param.default is param.empty:
                parts.append(param.name)
            elif '<deprecated' not in repr(param.default):
                parts.append(f'{param.name}={param.default!r}')
    return '(' + ', '.join(parts) + ')'


def install_skill(directory: str | Path = '.claude/skills') -> Path:
    """Write `<directory>/inklet/SKILL.md`; returns the file written.

    The skill is the guide with the front matter agent harnesses read to
    decide when to load it. Rerun after upgrading inklet to refresh it.
    """
    target = Path(directory) / 'inklet' / 'SKILL.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    body = guide()
    from .cli import _version
    # The version says which inklet the instructions describe; rerun
    # `inklet skill` after upgrading when it no longer matches.
    target.write_text(f'---\nname: inklet\ndescription: {SKILL_DESCRIPTION}\n---\n\n'
                      f'<!-- written for inklet {_version()} -->\n\n{body}', encoding='utf-8')
    return target
