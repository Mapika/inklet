import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from data import MM, outputs, time_course

plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
df = time_course()

fig, ax = plt.subplots(figsize=(89 * MM, 63.2 * MM))
for condition, group in df.groupby('condition', sort=False):
    line, = ax.plot(group['time'], group['mean'], label=condition)
    ax.fill_between(group['time'], group['mean'] - group['ci'], group['mean'] + group['ci'],
                    color=line.get_color(), alpha=0.2, linewidth=0)
ax.set_xlim(0, 48)
ax.set_xlabel('Time / h')
ax.set_ylabel('Reporter signal / a.u.')
ax.legend()
for path in outputs('time_course', 'matplotlib'):
    fig.savefig(path)
