import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from data import MM, distributions, outputs

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
df = distributions()
groups = list(df['genotype'].unique())
samples = [df.density[df.genotype == g].to_numpy() for g in groups]
rng = np.random.default_rng(0)

fig, ax = plt.subplots(figsize=(89 * MM, 63.2 * MM))
parts = ax.violinplot(samples, showmedians=True, showextrema=False, widths=0.8)
for body in parts['bodies']:
    body.set_facecolor('0.88')
    body.set_edgecolor('0.3')
    body.set_linewidth(0.5)
    body.set_alpha(1)
parts['cmedians'].set_color('0.1')
parts['cmedians'].set_linewidth(0.8)
for k, values in enumerate(samples, start=1):
    ax.scatter(k + rng.uniform(-0.15, 0.15, len(values)), values, s=3, color=f'C{k - 1}',
               linewidth=0, zorder=3)
ax.set_xticks(range(1, len(groups) + 1), groups)
ax.set_ylabel('Spine density / µm$^{-1}$')
ax.set_ylim(0, 2.5)
for path in outputs('distributions', 'matplotlib'):
    fig.savefig(path)
