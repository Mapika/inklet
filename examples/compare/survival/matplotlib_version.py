import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from data import MM, outputs, survival


def kaplan_meier(time, event, z=1.96):
    """Survival steps with a log-log Greenwood confidence band."""
    times = np.unique(time[event == 1])
    at_risk = np.array([(time >= t).sum() for t in times])
    deaths = np.array([((time == t) & (event == 1)).sum() for t in times])
    s = np.cumprod(1 - deaths / at_risk)
    with np.errstate(divide='ignore', invalid='ignore'):
        var = np.cumsum(deaths / (at_risk * (at_risk - deaths))) / np.log(s) ** 2
        lo, hi = (s ** np.exp(sign * z * np.sqrt(var)) for sign in (1, -1))
    pad = lambda v: np.r_[1.0, v, v[-1]]
    steps = np.r_[0, times, time.max()]
    return steps, pad(s), pad(np.nan_to_num(lo)), pad(np.nan_to_num(hi, nan=1.0))


plt.style.use(Path(__file__).resolve().parents[1] / 'journal.mplstyle')
df = survival()
ticks = np.arange(0, 61, 10)

fig, (ax, risk) = plt.subplots(2, 1, figsize=(89 * MM, 80 * MM), sharex=True,
                               height_ratios=[4, 1])
arms = []
for k, (arm, group) in enumerate(df.groupby('arm', sort=False)):
    time, event = group['months'].to_numpy(), group['event'].to_numpy()
    t, s, lo, hi = kaplan_meier(time, event)
    ax.step(t, s, where='post', color=f'C{k}', label=arm)
    ax.fill_between(t, lo, hi, step='post', color=f'C{k}', alpha=0.2, linewidth=0)
    censored = np.sort(time[event == 0])
    ax.plot(censored, s[np.searchsorted(t, censored, side='right') - 1], '|', color=f'C{k}',
            markersize=3, markeredgewidth=0.6)
    for tick in ticks:
        risk.text(tick, k, (time >= tick).sum(), ha='center', va='center', color=f'C{k}', fontsize=6)
    arms.append(arm)
ax.set_xlim(0, 60)
ax.set_ylim(0, 1.02)
ax.set_xticks(ticks)
ax.tick_params(labelbottom=True)
ax.set_xlabel('Time / months')
ax.set_ylabel('Overall survival')
ax.legend(loc='upper right')
risk.set_ylim(len(arms) - 0.5, -0.5)
risk.set_yticks(range(len(arms)), arms)
for label, k in zip(risk.get_yticklabels(), range(len(arms))):
    label.set_color(f'C{k}')
risk.tick_params(length=0, pad=10, labelbottom=False)
risk.spines[:].set_visible(False)
risk.set_title('Number at risk', loc='left', fontsize=6)
for path in outputs('survival', 'matplotlib'):
    fig.savefig(path)
