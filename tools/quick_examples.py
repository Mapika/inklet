"""Render the figures on the one-call chart and matplotlib bridge pages.

    python tools/quick_examples.py

Writes docs/assets/examples/quick-*.svg and mpl-bridge-*.{png,svg}. The
data are simulated with fixed seeds, so reruns produce the same files.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import inklet as i

OUT = Path(__file__).resolve().parent.parent / 'docs' / 'assets' / 'examples'


def response_table():
    rng = random.Random(4)
    rows = []
    for condition, gain in (('control', 1.0), ('treated', 1.6)):
        for t in range(0, 25):
            rows.append({'time': t / 2, 'condition': condition,
                         'signal': gain * (1 - math.exp(-t / 8)) + rng.gauss(0, 0.04)})
    return rows


def outcome_table():
    rng = random.Random(7)
    return [{'group': group, 'response': rng.gauss(mean, 0.35)}
            for group, mean in (('control', 1.0), ('low dose', 1.4), ('high dose', 2.1))
            for _ in range(24)]


def quick_line():
    return i.line(response_table(), x='time', y='signal', color='condition',
                  xlabel='Time / h', ylabel='Signal / a.u.')


def quick_layout():
    rows = response_table()
    outcomes = outcome_table()
    trace = i.line(rows, x='time', y='signal', color='condition', xlabel='Time / h',
                   ylabel='Signal / a.u.')
    spread = i.boxplot(outcomes, x='group', y='response', points=True, xlabel='',
                       ylabel='Response')
    histogram = i.hist(outcomes, x='response', color='group', bins=14, xlabel='Response',
                       legend='right')
    return (trace | spread) / histogram


def matplotlib_source():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = response_table()
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for condition in ('control', 'treated'):
        picked = [r for r in rows if r['condition'] == condition]
        times = [r['time'] for r in picked]
        signal = [r['signal'] for r in picked]
        left.plot(times, signal, label=condition)
        left.fill_between(times, [s - 0.08 for s in signal], [s + 0.08 for s in signal], alpha=0.25)
    left.set_xlabel('Time / h')
    left.set_ylabel('Signal / a.u.')
    left.legend()
    means = {'control': 1.0, 'low dose': 1.4, 'high dose': 2.1}
    right.bar(list(means), list(means.values()), yerr=[0.1, 0.12, 0.15], capsize=3)
    right.set_ylabel('Response')
    fig.tight_layout()
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    quick_line().save(OUT / 'quick-line.svg')
    quick_layout().save(OUT / 'quick-layout.svg')
    fig = matplotlib_source()
    fig.savefig(OUT / 'mpl-bridge-before.png', dpi=110)
    i.from_matplotlib(fig).save(OUT / 'mpl-bridge-after.svg')
    for name in ('quick-line.svg', 'quick-layout.svg', 'mpl-bridge-before.png', 'mpl-bridge-after.svg'):
        print(OUT / name)


if __name__ == '__main__':
    main()
