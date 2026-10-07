import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from data import MM, outputs, volcano

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
df = volcano()
df['y'] = -np.log10(df['p'])
significant = (df['p'] < 0.05) & (df['log2fc'].abs() >= 1)
classes = {'ns': (~significant, '0.75'),
           'down': (significant & (df['log2fc'] < 0), '#4a7bb7'),
           'up': (significant & (df['log2fc'] > 0), '#dd3d2d')}

fig, ax = plt.subplots(figsize=(89 * MM, 63.2 * MM))
for mask, color in classes.values():
    ax.scatter(df.log2fc[mask], df.y[mask], s=4, color=color, linewidth=0)
for x in (-1, 1):
    ax.axvline(x, color='0.4', linewidth=0.4, linestyle='--', zorder=0)
ax.axhline(-np.log10(0.05), color='0.4', linewidth=0.4, linestyle='--', zorder=0)
nudge = {'ZNKR17': (-14, -6), 'CDKR10': (-16, 4), 'MYPL9': (4, -4), 'ATHO1': (4, 0),
         'MYAT19': (4, 0), 'MYCD5': (-4, 0)}
for _, row in df[significant].nsmallest(10, 'p').iterrows():
    default = (4, 0) if row.log2fc > 0 else (-4, 0)
    offset = nudge.get(row.gene, default)
    ax.annotate(row.gene, (row.log2fc, row.y), xytext=offset, textcoords='offset points',
                ha='left' if offset[0] > 0 else 'right', va='center', fontsize=6,
                arrowprops=dict(arrowstyle='-', linewidth=0.3, shrinkA=0, shrinkB=1))
ax.set_xlabel('log$_2$ fold change')
ax.set_ylabel('$-$log$_{10}$ $P$')
for path in outputs('volcano', 'matplotlib'):
    fig.savefig(path)
