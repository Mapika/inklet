import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from data import MM, correlation, outputs

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
corr = correlation()

fig, ax = plt.subplots(figsize=(89 * MM, 88 * MM))
image = ax.imshow(corr, cmap='RdBu', vmin=-1, vmax=1, aspect='auto')
ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=45, ha='right',
              rotation_mode='anchor')
ax.set_yticks(range(len(corr.index)), corr.index)
ax.spines[:].set_visible(False)
colorbar = fig.colorbar(image, ax=ax, shrink=0.8)
colorbar.set_label('Pearson $r$')
colorbar.outline.set_linewidth(0.5)
for path in outputs('heatmap', 'matplotlib'):
    fig.savefig(path)
