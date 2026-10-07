"""Run the Python examples in `src/inklet/guide.md`, the page coding agents read.

The examples are fragments that refer to a table or two the reader already has,
so the namespace supplies them (`df`, `fit`, `other_plot`). Each block runs in
order in one namespace, as an agent would read them, in a scratch directory.
"""
import re
from pathlib import Path

import pandas as pd
import pytest

import inklet as i

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / 'src' / 'inklet' / 'guide.md'
BLOCK = re.compile(r'^```python\n(.*?)^```', re.MULTILINE | re.DOTALL)
BLOCKS = [code for code in BLOCK.findall(GUIDE.read_text(encoding='utf-8'))]


def _namespace():
    """The tables and objects the guide's fragments assume the reader has."""
    rows = 24
    df = pd.DataFrame({
        'time': [t % 12 for t in range(rows)],
        'signal': [0.5 + 0.1 * (t % 7) for t in range(rows)],
        'condition': ['control', 'treated'] * (rows // 2),
        'drug': ['A', 'B', 'C'] * (rows // 3),
        'cell_line': ['HeLa', 'MCF7'] * (rows // 2),
        'replicate': [1, 2, 3, 1] * (rows // 4),
        'strain': ['wt', 'ko', 'wt', 'ko'] * (rows // 4),
        'dose': [1, 2, 4, 8] * (rows // 4),
        'response': [1.0, 2.2, 3.1, 4.8] * (rows // 4),
        't': [t % 12 for t in range(rows)],
        'y': [1.0 + 0.2 * (t % 5) for t in range(rows)],
        'group': ['control', 'treated'] * (rows // 2),
    })
    fit = pd.DataFrame({'dose': [1, 2, 4, 8], 'predicted': [1.1, 2.0, 3.2, 4.7]})
    other_plot = i.plot_spec()
    other_plot.line([(0, 1), (1, 3), (2, 2)], name='Other')
    return {'df': df, 'fit': fit, 'other_plot': other_plot}


def test_every_guide_python_block_runs(tmp_path, monkeypatch):
    assert len(BLOCKS) >= 5
    original_theme = i.current_theme()
    monkeypatch.chdir(tmp_path)
    namespace = {'__name__': '__main__', **_namespace()}
    try:
        for index, code in enumerate(BLOCKS):
            exec(compile(code, f'guide.md:block-{index + 1}', 'exec'), namespace)
    finally:
        i.use_theme(original_theme)


def test_the_chart_method_table_names_methods_a_chart_has():
    """Every method in the guide's 'Chart methods' table is callable on a chart."""
    text = GUIDE.read_text(encoding='utf-8')
    section = text.split('| Method | Use |', 1)[1].split('\n\n', 1)[0]
    names = sorted(set(re.findall(r'`(\w+)\(', section)))
    chart = i.line(x=[1, 2], y=[1, 2])
    missing = [name for name in names if not callable(getattr(chart, name, None))]

    assert names
    assert missing == []
