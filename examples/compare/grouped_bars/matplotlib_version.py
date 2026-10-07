import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from data import MM, mitochondria, outputs

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
df = mitochondria()
genotypes = list(df['genotype'].unique())
treatments = {'Vehicle': 'Vehicle', 'CCCP': 'CCCP 10 µM'}
stats = df.groupby(['genotype', 'treatment'])['length'].agg(['mean', 'sem'])
rng = np.random.default_rng(0)

fig, ax = plt.subplots(figsize=(89 * MM, 63.2 * MM))
x = np.arange(len(genotypes))
width = 0.38
for k, (treatment, label) in enumerate(treatments.items()):
    color = f'C{k}'
    offset = (k - 0.5) * width
    means = [stats.loc[(g, treatment), 'mean'] for g in genotypes]
    sems = [stats.loc[(g, treatment), 'sem'] for g in genotypes]
    ax.bar(x + offset, means, width * 0.9, color=color, alpha=0.45, edgecolor=color,
           linewidth=0.6, label=label)
    ax.errorbar(x + offset, means, yerr=sems, fmt='none', ecolor='0.1', elinewidth=0.6,
                capsize=2, capthick=0.6)
    for j, g in enumerate(genotypes):
        values = df.length[(df.genotype == g) & (df.treatment == treatment)]
        jitter = rng.uniform(-0.1, 0.1, len(values))
        ax.scatter(x[j] + offset + jitter, values, s=6, color=color, zorder=3, linewidth=0)
ax.set_xticks(x, genotypes)
ax.set_ylabel('Mitochondrial length / µm')
ax.set_ylim(bottom=0)
ax.legend(ncols=2, loc='lower center', bbox_to_anchor=(0.5, 1.0))
for path in outputs('grouped_bars', 'matplotlib'):
    fig.savefig(path)
