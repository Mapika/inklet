import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from data import MM, dose_response, outputs

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
points, curves, ec50 = dose_response()

fig, ax = plt.subplots(figsize=(89 * MM, 63.2 * MM))
for k, (compound, group) in enumerate(points.groupby('compound')):
    fit = curves[curves.compound == compound]
    ax.scatter(group['conc'], group['viability'], s=8, color=f'C{k}', linewidth=0)
    ax.plot(fit['conc'], fit['fit'], color=f'C{k}', label=compound)
ax.set_xscale('log')
ax.set_xlabel('Concentration / M')
ax.set_ylabel('Viability / % of control')
ax.legend()
for path in outputs('dose_response', 'matplotlib'):
    fig.savefig(path)
