"""Every snippet on docs/how-to.md runs, and every figure it leaves lints clean.

A reader copies these snippets as they are, so each one is run here in a
scratch directory. A figure that lints with an error or a warning is a page
that shows a problem, so that fails. The chart-method table is generated from
the Chart class; the test checks the page has the current table and that each
method listed really returns the chart.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

import inklet as i

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('how_to_figures', ROOT / 'tools' / 'how_to_figures.py')
how_to = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(how_to)

SNIPPETS = how_to.snippets()
FIGURED = [s for s in SNIPPETS if s.figure is not None]


def test_the_page_has_its_twelve_answers_and_each_figure_is_on_disk():
    assert len(FIGURED) >= 12
    names = [s.figure for s in FIGURED]
    assert len(names) == len(set(names)), 'two answers share a figure file'
    for name in names:
        assert (how_to.OUT / name).stat().st_size > 1000, f'{name} is missing or empty'


@pytest.mark.parametrize('snippet', SNIPPETS, ids=lambda s: f'block-{s.index}')
def test_snippet_runs_and_its_figure_lints_clean(snippet, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    figure = how_to.run(snippet)
    if snippet.figure is not None:
        assert figure is not None, f'block {snippet.index} shows {snippet.figure} but leaves no figure'
    if figure is None:
        return
    compiled = figure.compile()
    assert not how_to.problems(compiled), compiled.report()


def test_the_journal_snippet_passes_inklet_check(tmp_path):
    """The page tells a reader to run `inklet check` before submitting; the snippet that says so must pass."""
    snippet = next(s for s in SNIPPETS if s.figure == 'journal.svg')
    script = tmp_path / 'figure1.py'
    script.write_text(snippet.code)
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    done = subprocess.run([sys.executable, '-m', 'inklet', 'check', str(script)],
                          cwd=tmp_path, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_method_table_on_the_page_is_the_generated_one():
    text = how_to.PAGE.read_text()
    assert how_to.with_table(text) == text, 'run python tools/how_to_figures.py to refresh the table'


@pytest.mark.parametrize('name', list(how_to.METHODS))
def test_each_listed_chart_method_exists_and_returns_the_chart(name):
    from inklet.quick import Chart

    def chart_for(name):
        if name == 'brackets':
            return i.boxplot({'g': ['a', 'a', 'b', 'b'], 'v': [1.0, 1.2, 1.4, 1.1]}, x='g', y='v')
        if name == 'colorbar':
            return i.heatmap([[0, 1], [2, 3]], x=['p', 'q'], y=['r', 's'])
        if name == 'legend':
            return i.line(x=[0, 1, 2], y=[1, 2, 3], name='series')
        return i.scatter({'x': [1, 2, 3], 'y': [1, 2, 3]}, x='x', y='y')

    calls = {
        'labels': lambda c: c.labels(title='Title'),
        'vline': lambda c: c.vline(1.5, label='v'),
        'hline': lambda c: c.hline(1.5, label='h'),
        'annotate': lambda c: c.annotate(2, 2, 'note'),
        'brackets': lambda c: c.brackets([('a', 'b', 0.01)]),
        'colorbar': lambda c: c.colorbar(title='r'),
        'legend': lambda c: c.legend(side='bottom'),
        'size': lambda c: c.size(width='single', height=60),
    }
    chart = chart_for(name)
    assert callable(getattr(chart, name))
    assert (name in vars(Chart)) == (name in ('labels', 'colorbar', 'legend', 'size'))
    assert calls[name](chart) is chart
    assert not how_to.problems(chart.compile())
