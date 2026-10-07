"""Simulated data shared by the inklet and matplotlib versions of each figure.

Every function uses its own fixed seed, so both versions plot identical numbers.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[2] / 'gallery' / 'compare'
MM = 1 / 25.4


def outputs(name, tool):
    """The PNG and PDF paths for one version of one figure."""
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT / f'{name}-{tool}.png', OUT / f'{name}-{tool}.pdf'


def _t95(df):
    """Two-sided 97.5 % quantile of Student's t for small df (table values)."""
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
             8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179}
    return table.get(df, 1.96)


def time_course():
    """Mean reporter signal per condition over 48 h with the 95 % CI half-width."""
    rng = np.random.default_rng(101)
    times = np.arange(0, 49, 4)
    conditions = {'Vehicle': (0.15, 0.0), 'Drug 1 µM': (0.9, 14.0), 'Drug 10 µM': (2.1, 9.0)}
    rows = []
    for name, (amplitude, half_time) in conditions.items():
        rise = amplitude * times ** 2 / (half_time ** 2 + times ** 2) if half_time else amplitude * times / 48
        reps = 1.0 + rise[None, :] + rng.normal(0, 0.12 + 0.08 * rise, (6, times.size))
        mean, sd = reps.mean(0), reps.std(0, ddof=1)
        ci = _t95(5) * sd / np.sqrt(6)
        rows += [{'time': t, 'condition': name, 'mean': m, 'ci': c} for t, m, c in zip(times, mean, ci)]
    return pd.DataFrame(rows)


def mitochondria():
    """Mitochondrial length per cell, four knockdowns x two treatments, n = 6 each."""
    rng = np.random.default_rng(202)
    genotypes = {'Scrambled siRNA': 3.1, 'MFN2 knockdown': 1.6, 'OPA1 knockdown': 1.9,
                 'DRP1 knockdown': 4.6}
    rows = []
    for genotype, base in genotypes.items():
        for treatment, factor in (('Vehicle', 1.0), ('CCCP', 0.55)):
            for value in rng.normal(base * factor, 0.18 * base * factor, 6):
                rows.append({'genotype': genotype, 'treatment': treatment, 'length': value})
    return pd.DataFrame(rows)


def _logistic(conc, bottom, top, log_ec50, hill):
    return bottom + (top - bottom) / (1 + 10 ** ((np.log10(conc) - log_ec50) * hill))


def _fit_logistic(conc, response):
    """Four-parameter logistic fit by Levenberg-Marquardt (no SciPy needed)."""
    order = np.argsort(conc)
    middle = (response.max() + response.min()) / 2
    crossing = np.log10(conc[order][np.argmin(np.abs(response[order] - middle))])
    params = np.array([response.min(), response.max(), crossing, 1.0])

    def sse(q):
        return float(((response - _logistic(conc, *q)) ** 2).sum())

    damping = 1e-2
    for _ in range(500):
        f = _logistic(conc, *params)
        jac = np.empty((conc.size, 4))
        for k in range(4):
            step = np.zeros(4)
            step[k] = 1e-6 * max(1.0, abs(params[k]))
            jac[:, k] = (_logistic(conc, *(params + step)) - f) / step[k]
        normal = jac.T @ jac
        delta = np.linalg.solve(normal + damping * np.diag(np.diag(normal)), jac.T @ (response - f))
        if sse(params + delta) < sse(params):
            params, damping = params + delta, damping / 3
            if np.abs(delta).max() < 1e-9:
                break
        else:
            damping *= 4
    return params


def dose_response():
    """Triplicate viability for two compounds and the fitted four-parameter curves.

    Returns (points, curves, ec50) where ec50 maps compound to EC50 in mol/L.
    """
    rng = np.random.default_rng(303)
    conc = 10.0 ** np.arange(-9, -3.9, 0.5)
    truth = {'Compound A': (4.0, 102.0, -6.8, 1.1), 'Compound B': (18.0, 99.0, -5.6, 1.6)}
    points, curves, ec50 = [], [], {}
    smooth = 10.0 ** np.linspace(-9, -4, 120)
    for name, (bottom, top, log_ec50, hill) in truth.items():
        for c, m in zip(conc, _logistic(conc, bottom, top, log_ec50, hill)):
            for value in rng.normal(m, 4.0, 3):
                points.append({'compound': name, 'conc': c, 'viability': value})
    points = pd.DataFrame(points)
    for name in truth:
        sub = points[points.compound == name]
        params = _fit_logistic(sub.conc.to_numpy(), sub.viability.to_numpy())
        ec50[name] = 10 ** params[2]
        curves += [{'compound': name, 'conc': c, 'fit': f}
                   for c, f in zip(smooth, _logistic(smooth, *params))]
    return points, pd.DataFrame(curves), ec50


def distributions():
    """Spine density in four genotypes, n = 40 neurons each; one group bimodal."""
    rng = np.random.default_rng(404)
    groups = {
        'Wild type': rng.normal(1.45, 0.22, 40),
        'Shank3 +/−': rng.normal(1.20, 0.25, 40),
        'Shank3 −/−': np.concatenate([rng.normal(0.72, 0.12, 22), rng.normal(1.18, 0.14, 18)]),
        'Rescue': rng.normal(1.35, 0.30, 40),
    }
    return pd.DataFrame([{'genotype': g, 'density': v} for g, values in groups.items() for v in values])


def volcano():
    """Differential expression for 3,000 genes: log2 fold change and p-value."""
    rng = np.random.default_rng(505)
    n = 3000
    fold = rng.normal(0, 0.35, n)
    hits = rng.choice(n, 120, replace=False)
    fold[hits] += rng.choice([-1, 1], 120) * rng.gamma(3.0, 0.45, 120)
    z = np.abs(fold) / rng.uniform(0.3, 0.7, n)
    p = np.array([math.erfc(v / math.sqrt(2)) for v in z])
    syllables = ['KR', 'TP', 'MY', 'CD', 'SL', 'GA', 'NF', 'HO', 'RB', 'ZN', 'PL', 'AT']
    genes = [f'{syllables[k % 12]}{syllables[(k // 12) % 12]}{k // 144 + 1}' for k in range(n)]
    return pd.DataFrame({'gene': genes, 'log2fc': fold, 'p': p})


def survival():
    """Overall survival in three arms, n = 80 each, administrative censoring at 60 months."""
    rng = np.random.default_rng(606)
    arms = {'Standard care': 22.0, 'Drug A': 34.0, 'Drug A + B': 55.0}
    rows = []
    for arm, scale in arms.items():
        event_time = rng.weibull(1.3, 80) * scale
        dropout = rng.uniform(6, 120, 80)
        time = np.minimum.reduce([event_time, dropout, np.full(80, 60.0)])
        event = (event_time <= time).astype(int)
        rows += [{'arm': arm, 'months': t, 'event': e} for t, e in zip(time, event)]
    return pd.DataFrame(rows)


def correlation():
    """Pairwise Pearson correlations between ten clinical measurements, n = 250."""
    rng = np.random.default_rng(707)
    names = ['Age', 'Body mass index', 'Systolic pressure', 'Diastolic pressure', 'LDL cholesterol',
             'HDL cholesterol', 'Fasting glucose', 'HbA1c', 'C-reactive protein', 'eGFR']
    latent = rng.normal(size=(250, 3))
    loadings = np.array([
        [0.6, 0.1, 0.0], [0.2, 0.7, 0.1], [0.6, 0.4, 0.0], [0.4, 0.5, 0.0], [0.3, 0.4, -0.2],
        [-0.1, -0.5, 0.3], [0.2, 0.6, 0.5], [0.2, 0.5, 0.6], [0.1, 0.5, 0.1], [-0.7, 0.0, -0.1]])
    values = latent @ loadings.T + rng.normal(0, 0.6, (250, 10))
    return pd.DataFrame(np.corrcoef(values.T), index=names, columns=names)
