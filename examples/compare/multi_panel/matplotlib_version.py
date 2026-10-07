import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import ScaledTranslation

from data import MM, distributions, dose_response, mitochondria, outputs, time_course

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
rng = np.random.default_rng(0)
fig, axes = plt.subplots(2, 2, figsize=(183 * MM, 123.8 * MM))
(ax_a, ax_b), (ax_c, ax_d) = axes

course = time_course()
for condition, group in course.groupby('condition', sort=False):
    line, = ax_a.plot(group['time'], group['mean'], label=condition)
    ax_a.fill_between(group['time'], group['mean'] - group['ci'], group['mean'] + group['ci'],
                      color=line.get_color(), alpha=0.2, linewidth=0)
ax_a.set(xlim=(0, 48), xlabel='Time / h', ylabel='Reporter signal / a.u.')
ax_a.legend()

cells = mitochondria()
genotypes = list(cells['genotype'].unique())
stats = cells.groupby(['genotype', 'treatment'])['length'].agg(['mean', 'sem'])
x = np.arange(len(genotypes))
for k, (treatment, label) in enumerate({'Vehicle': 'Vehicle', 'CCCP': 'CCCP 10 µM'}.items()):
    offset = (k - 0.5) * 0.38
    means = [stats.loc[(g, treatment), 'mean'] for g in genotypes]
    sems = [stats.loc[(g, treatment), 'sem'] for g in genotypes]
    ax_b.bar(x + offset, means, 0.34, color=f'C{k}', alpha=0.45, edgecolor=f'C{k}',
             linewidth=0.6, label=label)
    ax_b.errorbar(x + offset, means, yerr=sems, fmt='none', ecolor='0.1', elinewidth=0.6,
                  capsize=2, capthick=0.6)
    for j, g in enumerate(genotypes):
        values = cells.length[(cells.genotype == g) & (cells.treatment == treatment)]
        ax_b.scatter(x[j] + offset + rng.uniform(-0.1, 0.1, len(values)), values, s=6,
                     color=f'C{k}', zorder=3, linewidth=0)
ax_b.set_xticks(x, genotypes)
ax_b.set(ylabel='Mitochondrial length / µm', ylim=(0, None))
ax_b.legend(ncols=2, loc='lower center', bbox_to_anchor=(0.5, 1.0))

points, curves, ec50 = dose_response()
for k, (compound, group) in enumerate(points.groupby('compound')):
    fit = curves[curves.compound == compound]
    ax_c.scatter(group['conc'], group['viability'], s=8, color=f'C{k}', linewidth=0)
    ax_c.plot(fit['conc'], fit['fit'], color=f'C{k}', label=compound)
ax_c.set(xscale='log', xlabel='Concentration / M', ylabel='Viability / % of control')
ax_c.legend()

spread = distributions()
groups = list(spread['genotype'].unique())
samples = [spread.density[spread.genotype == g].to_numpy() for g in groups]
parts = ax_d.violinplot(samples, showmedians=True, showextrema=False, widths=0.8)
for body in parts['bodies']:
    body.set(facecolor='0.88', edgecolor='0.3', linewidth=0.5, alpha=1)
parts['cmedians'].set(color='0.1', linewidth=0.8)
for k, values in enumerate(samples, start=1):
    ax_d.scatter(k + rng.uniform(-0.15, 0.15, len(values)), values, s=3, color=f'C{k - 1}',
                 linewidth=0, zorder=3)
ax_d.set_xticks(range(1, len(groups) + 1), groups)
ax_d.set(ylabel='Spine density / µm$^{-1}$', ylim=(0, 2.5))

for ax, letter in zip(axes.flat, 'abcd'):
    ax.text(0, 1, letter, transform=ax.transAxes + ScaledTranslation(-28 / 72, 6 / 72, fig.dpi_scale_trans),
            fontsize=9, fontweight='bold', va='bottom')
fig.align_labels()
for path in outputs('multi_panel', 'matplotlib'):
    fig.savefig(path)
