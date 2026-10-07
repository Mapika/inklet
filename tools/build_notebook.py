"""Build and execute examples/notebooks/quickstart.ipynb.

The notebook is written from the cells below with nbformat, then run with
nbclient so its outputs are stored and it opens on GitHub with the charts
already drawn. The kernel imports this checkout's `src/` (through PYTHONPATH),
and files it saves go to a temporary directory, not the repository.

Regenerate it with the venv that has nbformat, nbclient and ipykernel:

    /path/to/.venv/bin/python tools/build_notebook.py
"""
from pathlib import Path
import os
import shutil
import tempfile

import nbclient
import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'examples' / 'notebooks' / 'quickstart.ipynb'
SRC = ROOT / 'src'

CELLS = [
    ('md', """# Quickstart: charts from a table

Inklet draws publication-sized charts from a table in one call, measures the
text so labels do not collide, and saves SVG, PDF or PNG. This notebook runs
top to bottom; every chart appears where its cell runs.

Install it from [PyPI](https://pypi.org/project/inklet/):

```sh
pip install inklet
```
"""),
    ('code', """import numpy as np
import pandas as pd
import inklet as i

rng = np.random.default_rng(2024)   # a fixed seed: the same simulated data on every run

# A simulated time course: 2 cell lines x 3 treatments x 3 replicates, sampled hourly.
df = pd.MultiIndex.from_product(
    [['HeLa', 'U2OS'], ['control', 'drug A', 'drug B'], [1, 2, 3], np.arange(9)],
    names=['cell_line', 'treatment', 'replicate', 'hour']).to_frame(index=False)
gain = df['treatment'].map({'control': 0.0, 'drug A': 0.4, 'drug B': 0.8})
base = df['cell_line'].map({'HeLa': 1.0, 'U2OS': 1.4})
df['signal'] = (base + gain * np.log1p(df['hour']) + rng.normal(0, 0.12, len(df))).round(2)

# Hourly means and standard errors, one row per group and hour.
summary = (df.groupby(['cell_line', 'treatment', 'hour'])['signal']
             .agg(mean='mean', sem='sem').reset_index())
hela = summary[summary['cell_line'] == 'HeLa']
endpoint = df[df['hour'] == 8]   # the last hour, one row per replicate

df.head(8)
"""),
    ('md', """## Lines with groups

`color=` draws one line per group, and `error_y=` adds a band. Axis titles come
from the column names unless you give them.
"""),
    ('code', """i.line(hela, x='hour', y='mean', color='treatment', error_y='sem',
       xlabel='Time / h', ylabel='Signal / a.u.', title='HeLa response')
"""),
    ('md', """## Scatter with text labels

`text=` labels each point, placed clear of the marks and of each other.
These compounds are simulated.
"""),
    ('code', """compounds = pd.DataFrame({
    'compound': ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta'],
    'logP': [0.4, 1.1, 1.6, 2.2, 2.5, 3.1, 3.6, 4.2],
    'pIC50': [5.1, 5.9, 6.4, 6.2, 7.0, 7.3, 7.1, 7.9],
})
i.scatter(compounds, x='logP', y='pIC50', text='compound',
          xlabel='Lipophilicity, logP', ylabel='Potency, pIC50')
"""),
    ('md', """## Bars with means, error bars and points

`agg='mean'` averages the rows in each category instead of summing them.
`error_y='sem'` draws the standard error, and `points=True` shows every replicate.
"""),
    ('code', """i.bar(endpoint, x='treatment', y='signal', color='cell_line', agg='mean',
      error_y='sem', points=True, xlabel='Treatment', ylabel='Signal at 8 h / a.u.')
"""),
    ('md', """## Box plots with points

`points=True` overlays the individual samples on each box.
"""),
    ('code', """i.boxplot(endpoint, x='treatment', y='signal', points=True,
          xlabel='Treatment', ylabel='Signal at 8 h / a.u.')
"""),
    ('md', """## Small multiples

`facet_col=` makes one panel per value. The panels share their axes, and each
treatment keeps its colour in every panel.
"""),
    ('code', """i.line(summary, x='hour', y='mean', color='treatment', error_y='sem',
       facet_col='cell_line', xlabel='Time / h', ylabel='Signal / a.u.')
"""),
    ('md', """## Direct labels

`legend='direct'` names each line at its end, so no key is needed.
"""),
    ('code', """i.line(hela, x='hour', y='mean', color='treatment', legend='direct',
       xlabel='Time / h', ylabel='Signal / a.u.')
"""),
    ('md', """## Multi-panel figures

`|` places charts side by side and `/` stacks them. Each panel gets a letter.
"""),
    ('code', """figure = (i.line(hela, x='hour', y='mean', color='treatment', error_y='sem',
                  xlabel='Time / h', ylabel='Signal / a.u.')
          | i.boxplot(endpoint, x='treatment', y='signal', points=True,
                      xlabel='Treatment', ylabel='Signal at 8 h / a.u.'))
figure
"""),
    ('md', """## Save and check

`save()` writes each file by its extension and returns the compiled figure.
`figure.report()` lists overlapping or clipped text, small type, and data
outside the axes, each with a suggested fix. An empty report means no problems.
"""),
    ('code', """figure.save('quickstart.svg', 'quickstart.pdf')
print(figure.report())
"""),
    ('md', """## Existing matplotlib figures

`i.from_matplotlib(fig)` redraws the data of a matplotlib figure as Inklet
charts, so the plotting code can stay as it is. Here the figure is closed before
the cell ends, so only the Inklet version is displayed.
"""),
    ('code', """import matplotlib.pyplot as plt

fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 2.6))
for treatment, group in hela.groupby('treatment'):
    left.plot(group['hour'], group['mean'], label=treatment)
means = endpoint.groupby('treatment')['signal'].agg(['mean', 'sem'])
right.bar(means.index, means['mean'], yerr=means['sem'], capsize=3)
left.set_xlabel('Time / h')
left.set_ylabel('Signal / a.u.')
right.set_ylabel('Signal at 8 h / a.u.')
left.legend()

converted = i.from_matplotlib(fig)
plt.close(fig)
converted
"""),
    ('md', """## Where next

- [Charts in one call](https://inklet.readthedocs.io/en/latest/quick-charts/):
  every chart type and option.
- [Using Inklet with coding agents](https://inklet.readthedocs.io/en/latest/coding-agents/):
  the guide an agent reads, and how to check its figures.
- [Published figures](https://inklet.readthedocs.io/en/latest/published-figures/):
  eight figures recreated from their data.
"""),
]


def build():
    nb = new_notebook()
    nb.metadata['kernelspec'] = {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'}
    nb.metadata['language_info'] = {'name': 'python'}
    for kind, source in CELLS:
        cell = new_markdown_cell(source) if kind == 'md' else new_code_cell(source)
        nb.cells.append(cell)
    return nb


def execute(nb):
    # The kernel is a child process and inherits the environment, so this must
    # be set before the client starts it.
    os.environ['PYTHONPATH'] = os.pathsep.join(filter(None, [str(SRC), os.environ.get('PYTHONPATH')]))
    workdir = Path(tempfile.mkdtemp(prefix='inklet-quickstart-'))
    try:
        client = nbclient.NotebookClient(nb, kernel_name='python3', timeout=120,
                                         resources={'metadata': {'path': str(workdir)}})
        client.execute()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return nb


def main():
    nb = execute(build())
    nbformat.validate(nb)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, OUTPUT)
    print(f'wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KiB)')


if __name__ == '__main__':
    main()
