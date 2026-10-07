"""NCCTG advanced lung cancer: overall survival by sex (Loprinzi et al. 1994).

Kaplan-Meier curves with log 95% confidence bands (R's default), censor
ticks, a number-at-risk table and the two-sided log-rank p-value.
Data: R survival package `lung` (Rdatasets survival/cancer.csv).
"""
from pathlib import Path

import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'gallery' / 'published'

lung = pd.read_csv(HERE / 'data' / 'lung.csv')
time = lung['time'].to_numpy(float)
event = (lung['status'] == 2).to_numpy()           # 1 = censored, 2 = dead
male = (lung['sex'] == 1).to_numpy()               # 1 = male, 2 = female
arms = {'Male': (time[male], event[male]), 'Female': (time[~male], event[~male])}

TICKS = [0, 250, 500, 750, 1000]
chart = i.chart(width='single', height=62, xlim=(0, 1030), ylim=(0, 1))
chart.kaplan_meier(arms, band='log', pvalue='logrank')
chart.axes(x='Time since enrolment / days', y='Overall survival probability',
           x_options={'ticks': TICKS})
chart.legend(corner='ne', title='Sex')
chart.at_risk(ticks=TICKS)

if __name__ == '__main__':
    test = i.plot.logrank(arms)
    print(f'log-rank chi2 = {test.statistic:.2f} on {test.df} df, p = {test.p:.4f}')
    OUT.mkdir(parents=True, exist_ok=True)
    figure = chart.save(OUT / 'ncctg_lung.png', OUT / 'ncctg_lung.svg',
                        OUT / 'ncctg_lung.pdf', dpi=200)
    print(figure.report())
