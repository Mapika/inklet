"""Build the one-call chart gallery: its figures and the page that shows them.

    python tools/quick_gallery.py             # write docs/assets/quick-gallery/ and the page
    python tools/quick_gallery.py --markdown  # print the page instead of writing it

Each example's code is a string here. The string is executed to draw the
figure and is also the code block on docs/quick-gallery.md, so the page cannot
drift from what ran. For each example this writes a full-size SVG (shown in
its section) and a PNG (the card thumbnail in the grid at the top of the
page). After a run, `python tools/docs_thumbnails.py` writes the WebP
previews the cards use. The data are simulated with fixed seeds, so a rerun
reproduces the same files. Every figure must lint without errors or warnings.
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
import textwrap
import unicodedata
from pathlib import Path
from typing import NamedTuple

import inklet as i

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'assets' / 'quick-gallery'
PAGE = ROOT / 'docs' / 'quick-gallery.md'


# -- simulated tables: plain dicts of lists, so the code can name them ------


def growth():
    """Signal over 24 h for three conditions, with a standard error per point."""
    rng = random.Random(4)
    table = {'condition': [], 'time (h)': [], 'signal (a.u.)': [], 'se (a.u.)': []}
    for condition, gain in (('control', 1.0), ('low dose', 1.4), ('high dose', 1.9)):
        for t in range(25):
            mean = gain * (1 - math.exp(-t / 7))
            table['condition'].append(condition)
            table['time (h)'].append(t)
            table['signal (a.u.)'].append(round(mean + rng.gauss(0, 0.05), 3))
            table['se (a.u.)'].append(round(0.05 + 0.02 * mean, 3))
    return table


def outcomes():
    """A response measured on 24 animals in each of three groups."""
    rng = random.Random(11)
    table = {'group': [], 'response (a.u.)': []}
    for group, mean in (('control', 1.0), ('low dose', 1.4), ('high dose', 2.1)):
        for _ in range(24):
            table['group'].append(group)
            table['response (a.u.)'].append(round(rng.gauss(mean, 0.35), 3))
    return table


def dose_response():
    """Percent response to four replicates at each dose, for two strains."""
    rng = random.Random(5)
    table = {'strain': [], 'dose (mg/kg)': [], 'response (%)': []}
    for strain, ec50 in (('wild type', 4.0), ('mutant', 12.0)):
        for dose in (0.5, 1, 2, 4, 8, 16, 32):
            for _ in range(4):
                table['strain'].append(strain)
                table['dose (mg/kg)'].append(dose)
                table['response (%)'].append(round(100 - 80 * dose / (dose + ec50) + rng.gauss(0, 3), 1))
    return table


def lake():
    """Eighty water samples: temperature, dissolved oxygen and chlorophyll."""
    rng = random.Random(8)
    table = {'temperature (°C)': [], 'oxygen (mg/L)': [], 'chlorophyll (µg/L)': []}
    for _ in range(80):
        temperature = rng.uniform(4, 24)
        table['temperature (°C)'].append(round(temperature, 1))
        table['oxygen (mg/L)'].append(round(12.5 - 0.25 * temperature + rng.gauss(0, 0.6), 2))
        table['chlorophyll (µg/L)'].append(round(rng.uniform(0.5, 25), 2))
    return table


def specimens():
    """Specimens collected, one row each, labelled by species."""
    rng = random.Random(21)
    return {'species': rng.choices(['Daphnia', 'Bosmina', 'Cyclops', 'Keratella'],
                                   weights=[5, 3, 2, 1], k=120)}


def plots():
    """Total biomass of each site in each season: one row per pair."""
    rng = random.Random(13)
    table = {'site': [], 'season': [], 'biomass (g/m2)': []}
    for site, base in (('Ridge', 120), ('Meadow', 180), ('Marsh', 240), ('Forest', 95)):
        for season, factor in (('spring', 0.8), ('summer', 1.3), ('autumn', 1.0)):
            table['site'].append(site)
            table['season'].append(season)
            table['biomass (g/m2)'].append(round(base * factor + rng.gauss(0, 8), 1))
    return table


def morphology():
    """Body length of 200 specimens, split by sex."""
    rng = random.Random(17)
    table = {'sex': [], 'length (mm)': []}
    for sex, mean in (('female', 41.0), ('male', 46.0)):
        for _ in range(100):
            table['sex'].append(sex)
            table['length (mm)'].append(round(rng.gauss(mean, 4.5), 1))
    return table


def expression():
    """Expression of one gene in 80 wild-type and 80 knockout samples."""
    rng = random.Random(23)
    table = {'genotype': [], 'expression (log2)': []}
    for genotype, mean in (('wild type', 8.0), ('knockout', 6.2)):
        for _ in range(80):
            table['genotype'].append(genotype)
            table['expression (log2)'].append(round(rng.gauss(mean, 1.1), 2))
    return table


def latency():
    """Response latency of 50 sham and 50 treated animals, right-skewed."""
    rng = random.Random(31)
    table = {'group': [], 'latency (ms)': []}
    for group, median in (('sham', 180.0), ('treated', 120.0)):
        for _ in range(50):
            table['group'].append(group)
            table['latency (ms)'].append(round(rng.lognormvariate(math.log(median), 0.35), 1))
    return table


def yields():
    """Crop yield in 15 plots for each of three treatments."""
    rng = random.Random(37)
    table = {'treatment': [], 'yield (t/ha)': []}
    for treatment, mean in (('no fertiliser', 4.1), ('fertiliser A', 5.0), ('fertiliser B', 4.7)):
        for _ in range(15):
            table['treatment'].append(treatment)
            table['yield (t/ha)'].append(round(rng.gauss(mean, 0.5), 2))
    return table


def grip():
    """Peak grip force of 40 people in each of three age cohorts."""
    rng = random.Random(41)
    table = {'cohort': [], 'grip force (N)': []}
    for cohort, mean in (('18-35', 42.0), ('36-55', 36.0), ('56-75', 29.0)):
        for _ in range(40):
            table['cohort'].append(cohort)
            table['grip force (N)'].append(round(rng.gauss(mean, 6.0), 1))
    return table


def soil():
    """Soil pH from 20 samples at each of three sites."""
    rng = random.Random(43)
    table = {'site': [], 'soil pH': []}
    for site, mean in (('Upland', 6.1), ('Riparian', 5.4), ('Estuary', 7.2)):
        for _ in range(20):
            table['site'].append(site)
            table['soil pH'].append(round(rng.gauss(mean, 0.35), 2))
    return table


def generation():
    """Electricity generated from four sources, 2010 to 2024."""
    table = {'year': [], 'source': [], 'generation (TWh)': []}
    trends = {
        'gas': lambda t: 6.0 - 0.10 * t,
        'hydro': lambda t: 4.0 + 0.03 * math.sin(t),
        'wind': lambda t: 0.8 + 0.35 * t,
        'solar': lambda t: 0.15 + 0.12 * t * (1 + 0.05 * t),
    }
    for t, year in enumerate(range(2010, 2025)):
        for source, trend in trends.items():
            table['year'].append(year)
            table['source'].append(source)
            table['generation (TWh)'].append(round(trend(t), 2))
    return table


def calibration():
    """Absorbance of 11 standards, each measured twice."""
    rng = random.Random(47)
    table = {'concentration (µM)': [], 'absorbance (AU)': []}
    for concentration in range(0, 51, 5):
        for _ in range(2):
            table['concentration (µM)'].append(concentration)
            table['absorbance (AU)'].append(round(0.021 * concentration + 0.03 + rng.gauss(0, 0.02), 3))
    return table


def cytokines():
    """Log2 fold change of six genes under four conditions, long format."""
    rng = random.Random(53)
    conditions = ['LPS 1 h', 'LPS 4 h', 'LPS 24 h', 'IFN-g 4 h']
    profile = {
        'Tnf': [2.6, 3.1, 0.4, 0.2],
        'Il6': [3.4, 4.2, 1.1, 0.3],
        'Cxcl10': [0.5, 2.8, 3.0, 4.6],
        'Nos2': [0.2, 1.8, 2.9, 3.5],
        'Ifit1': [0.3, 1.2, 1.9, 5.1],
        'Actb': [0.0, 0.1, -0.1, 0.0],
    }
    table = {'gene': [], 'condition': [], 'log2 fold change': []}
    for gene, values in profile.items():
        for condition, value in zip(conditions, values):
            table['gene'].append(gene)
            table['condition'].append(condition)
            table['log2 fold change'].append(round(value + rng.gauss(0, 0.15), 2))
    return table


def cell_types():
    """Cells counted in one tissue sample, by type: one row per type."""
    return {'cell type': ['Neurons', 'Glia', 'Vascular', 'Immune', 'Other'],
            'cells (n)': [54, 28, 12, 4, 2]}


def pathway_scores():
    """Enrichment score of five pathways from one differential-expression run."""
    return {'pathway': ['Interferon', 'Apoptosis', 'Cell cycle', 'Hypoxia', 'Lipid'],
            'score': [2.4, -1.1, 0.6, -2.3, 1.2]}


def sites():
    """Mean soil moisture at four sites, before and after a dry season."""
    return {'site': ['Ridge', 'Meadow', 'Marsh', 'Forest'],
            'before (%)': [41, 52, 32, 61],
            'after (%)': [56, 48, 44, 70]}


def budget():
    """Changes that take a budget from its opening to its closing balance, one row per step."""
    return {'step': ['Opening', 'Sales', 'Costs', 'Tax', 'Grants', 'Closing'],
            'change (k$)': [120, 45, -30, -12, 8, None]}


def support():
    """Support for a policy in four countries, measured in 2015 and in 2025."""
    rng = random.Random(61)
    table = {'year': [], 'country': [], 'support (%)': []}
    for country, start, change in (('Denmark', 42, 19), ('Spain', 30, -2),
                                   ('Italy', 25, 15), ('Chile', 36, 4)):
        for year, share in ((2015, start), (2025, start + change)):
            table['year'].append(year)
            table['country'].append(country)
            table['support (%)'].append(round(share + rng.gauss(0, 1.0)))
    return table


def viability():
    """Viability over 24 h of two cell lines treated with vehicle or a drug."""
    rng = random.Random(59)
    table = {'cell line': [], 'drug': [], 'time (h)': [], 'viability (%)': []}
    for line in ('HeLa', 'MCF-7'):
        for drug, effect in (('vehicle', 0.0), ('drug A', 0.35), ('drug B', 0.6)):
            for t in range(0, 25, 3):
                table['cell line'].append(line)
                table['drug'].append(drug)
                table['time (h)'].append(t)
                table['viability (%)'].append(round(100 - effect * 60 * (t / 24) + rng.gauss(0, 2), 1))
    return table


def outcomes_by_sex():
    """Response of 12 females and 12 males in each of three groups; males respond more."""
    rng = random.Random(29)
    table = {'group': [], 'sex': [], 'response (a.u.)': []}
    for group, mean in (('control', 1.0), ('low dose', 1.4), ('high dose', 2.1)):
        for sex, shift in (('female', 0.0), ('male', 0.3)):
            for _ in range(12):
                table['group'].append(group)
                table['sex'].append(sex)
                table['response (a.u.)'].append(round(rng.gauss(mean + shift, 0.35), 3))
    return table


def survival_arms():
    """Follow-up of 40 patients on placebo and 40 on drug; follow-up ends are censored."""
    rng = random.Random(67)
    table = {'arm': [], 'months': [], 'died': []}
    for arm, scale in (('placebo', 14.0), ('drug', 24.0)):
        for _ in range(40):
            death = rng.expovariate(1 / scale)
            end = rng.uniform(4, 36)
            table['arm'].append(arm)
            table['months'].append(round(max(0.1, min(death, end)), 1))
            table['died'].append(int(death <= end))
    return table


def genes():
    """Fold change and p-value of 200 genes; 12 are truly changed, and q adjusts for 200 tests."""
    rng = random.Random(71)
    named = ['Il6', 'Tnf', 'Cxcl10', 'Nos2', 'Ifit1', 'Irf7', 'Mx1', 'Isg15', 'Oas1a', 'Stat1',
             'Socs3', 'Ccl5']
    rows = []
    for k in range(200):
        truth = (1 if k % 2 == 0 else -1) * rng.uniform(1.0, 3.0) if k < 12 else 0.0
        fold = truth + rng.gauss(0, 0.15)
        p = math.erfc(abs(fold) / 0.2 / math.sqrt(2))
        rows.append((named[k] if k < 12 else f'Gene {k:03d}', fold, p))
    # Benjamini-Hochberg: each q is the smallest false discovery rate at which its gene is called.
    count = len(rows)
    order = sorted(range(count), key=lambda k: rows[k][2])
    q = [1.0] * count
    running = 1.0
    for rank in range(count - 1, -1, -1):
        k = order[rank]
        running = min(running, rows[k][2] * count / (rank + 1))
        q[k] = running
    return {'gene': [row[0] for row in rows],
            'log2 fold change': [round(row[1], 3) for row in rows],
            'p-value': [row[2] for row in rows],
            'fdr': [round(value, 6) for value in q]}


def studies():
    """Odds ratios from four studies, each with its 95 per cent interval, and the pooled estimate."""
    return {'study': ['Ahmed 2019', 'Berg 2020', 'Chen 2021', 'Dubois 2022', 'Evans 2023', 'Pooled'],
            'odds ratio': [0.72, 0.91, 0.64, 0.58, 1.12, 0.79],
            'lower': [0.55, 0.62, 0.38, 0.41, 0.70, 0.66],
            'upper': [0.94, 1.33, 1.08, 0.82, 1.79, 0.95],
            'participants': [812, 355, 210, 640, 150, 2167],
            'pooled': [False, False, False, False, False, True]}


# -- the examples -----------------------------------------------------------


class Example(NamedTuple):
    name: str     # file stem: docs/assets/quick-gallery/<name>.svg
    title: str    # the page heading
    alt: str      # the image's alt text
    note: str     # what the simulated tables hold
    data: dict    # variable name in the code -> table builder
    code: str     # the chart code: executed, then shown on the page


EXAMPLES = [
    Example(
        'line', 'Lines with an error band',
        'Three signal curves rising from zero over 24 hours and levelling off, '
        'the high-dose curve highest, each with a shaded standard-error band',
        '`df` has `condition`, `time (h)`, `signal (a.u.)` and `se (a.u.)`. The band '
        'spans one `se (a.u.)` either side of each point.',
        {'df': growth},
        """
        chart = i.line(df, x='time (h)', y='signal (a.u.)', color='condition',
                       error_y='se (a.u.)', markers=True)
        """),
    Example(
        'scatter-groups', 'Scatter with groups',
        'Percent response falling as dose rises, for wild-type and mutant strains; '
        'the mutant points sit higher at each dose',
        '`df` has `strain`, `dose (mg/kg)` and `response (%)`.',
        {'df': dose_response},
        """
        chart = i.scatter(df, x='dose (mg/kg)', y='response (%)', color='strain')
        """),
    Example(
        'scatter-colour', 'Scatter coloured by a number',
        'Dissolved oxygen against temperature for 80 water samples, each point '
        'coloured by chlorophyll on a colour ramp with a colour bar',
        '`df` has `temperature (°C)`, `oxygen (mg/L)` and `chlorophyll (µg/L)`. A numeric '
        '`color` column with many values is drawn as a ramp.',
        {'df': lake},
        """
        chart = i.scatter(df, x='temperature (°C)', y='oxygen (mg/L)',
                          color='chlorophyll (µg/L)')
        """),
    Example(
        'bar-count', 'Bars counting rows',
        'Bars of the number of specimens in each of four species, from the most '
        'common to the least',
        '`df` has one row per specimen in a `species` column. Without `y`, a bar '
        'counts its rows.',
        {'df': specimens},
        """
        chart = i.bar(df, x='species')
        """),
    Example(
        'bar-grouped', 'Grouped bars',
        'Total biomass at four sites, with side-by-side bars for spring, summer and autumn',
        '`df` has `site`, `season` and `biomass (g/m2)`, one row per site and season.',
        {'df': plots},
        """
        chart = i.bar(df, x='site', y='biomass (g/m2)', color='season')
        """),
    Example(
        'bar-mean', 'Mean bars with error bars and points',
        'Mean response of control, low-dose and high-dose groups as bars, with '
        'standard-error whiskers and a dot for each of the 24 animals in each group',
        '`df` has `group` and `response (a.u.)`, one row per animal. `agg=` takes the '
        'mean of each group, and `error_y=` takes its standard error.',
        {'df': outcomes},
        """
        chart = i.bar(df, x='group', y='response (a.u.)', agg='mean',
                      error_y='sem', points=True)
        """),
    Example(
        'hist', 'Overlaid histograms',
        'Histograms of body length for female and male specimens, the male '
        'distribution shifted to the right',
        '`df` has `sex` and `length (mm)`, one row per specimen.',
        {'df': morphology},
        """
        chart = i.hist(df, x='length (mm)', color='sex', bins=20)
        """),
    Example(
        'kde', 'Filled density curves',
        'Smoothed density curves of gene expression for wild-type and knockout samples, '
        'the knockout curve centred lower',
        '`df` has `genotype` and `expression (log2)`, 80 samples per genotype.',
        {'df': expression},
        """
        chart = i.kde(df, x='expression (log2)', color='genotype', fill=True)
        """),
    Example(
        'ecdf', 'Cumulative distributions',
        'Cumulative proportion against latency for sham and treated animals; the '
        'treated curve rises earlier',
        '`df` has `group` and `latency (ms)`, 50 animals per group.',
        {'df': latency},
        """
        chart = i.ecdf(df, x='latency (ms)', color='group')
        """),
    Example(
        'boxplot', 'Box plots with points',
        'Crop yield in three treatments as box plots, with each plot drawn as a dot over its box',
        '`df` has `treatment` and `yield (t/ha)`, 15 plots per treatment.',
        {'df': yields},
        """
        chart = i.boxplot(df, x='treatment', y='yield (t/ha)', points=True)
        """),
    Example(
        'violin', 'Violins',
        'Violins of grip force for three age cohorts, each shape showing the spread of '
        '40 people; the force falls with age',
        '`df` has `cohort` and `grip force (N)`, 40 people per cohort.',
        {'df': grip},
        """
        chart = i.violin(df, x='cohort', y='grip force (N)')
        """),
    Example(
        'strip', 'Strip plot',
        'Soil pH of 20 samples at each of three sites, as jittered dots',
        '`df` has `site` and `soil pH`.',
        {'df': soil},
        """
        chart = i.strip(df, x='site', y='soil pH')
        """),
    Example(
        'area', 'Stacked areas',
        'Electricity generation from four sources from 2010 to 2024, stacked; wind '
        'and solar grow while gas shrinks',
        '`df` has `year`, `source` and `generation (TWh)`. Areas stack unless '
        '`stacked=False`.',
        {'df': generation},
        """
        chart = i.area(df, x='year', y='generation (TWh)', color='source')
        """),
    Example(
        'regression', 'Regression with a confidence band',
        'Absorbance against concentration for a calibration series, with a fitted line '
        'and a shaded 95 per cent confidence band',
        '`df` has `concentration (µM)` and `absorbance (AU)`, two readings per standard.',
        {'df': calibration},
        """
        chart = i.regression(df, x='concentration (µM)', y='absorbance (AU)')
        """),
    Example(
        'heatmap', 'Heatmap with a diverging colour bar',
        'Log2 fold change of six genes under four conditions as coloured cells, '
        'centred on zero',
        '`df` is a long table with `gene`, `condition` and `log2 fold change`. A '
        'diverging `palette=` with `center=0` puts zero at the middle of the colour bar.',
        {'df': cytokines},
        """
        chart = i.heatmap(df, x='condition', y='gene', z='log2 fold change',
                          palette='rdbu', center=0)
        """),
    Example(
        'facets', 'Facet panels',
        'Viability over 24 hours in two panels, one per cell line, with vehicle and two '
        'drugs; the panels share axes and one key',
        '`df` has `cell line`, `drug`, `time (h)` and `viability (%)`. `facet_col=` '
        'makes one panel per value of a column.',
        {'df': viability},
        """
        chart = i.line(df, x='time (h)', y='viability (%)', color='drug',
                       facet_col='cell line')
        """),
    Example(
        'layout', 'Combined panels',
        'A line plot and a box plot side by side, with a histogram below them, the '
        'panels lettered a to c',
        '`df` is the growth table, and `outcomes` is the response table. `|` places '
        'panels side by side and `/` stacks them.',
        {'df': growth, 'outcomes': outcomes},
        """
        trace = i.line(df, x='time (h)', y='signal (a.u.)', color='condition',
                       error_y='se (a.u.)')
        spread = i.boxplot(outcomes, x='group', y='response (a.u.)', points=True)
        chart = (trace | spread) / i.hist(outcomes, x='response (a.u.)', color='group', bins=14)
        """),
    Example(
        'direct-legend', 'Names at the line ends',
        'Three signal curves with their names written at the line ends in place of a key',
        '`df` is the growth table from the first example.',
        {'df': growth},
        """
        chart = i.line(df, x='time (h)', y='signal (a.u.)', color='condition',
                       legend='direct')
        """),
    Example(
        'pie', 'Pie chart',
        'Cell types in one tissue sample as a pie: neurons take just over half of the '
        'disc, and the two smallest slices are labelled outside the rim',
        '`df` has `cell type` and `cells (n)`, one row per type. The slices are sized by '
        '`values=`, labelled with their shares, and keyed by `names=`.',
        {'df': cell_types},
        """
        chart = i.pie(df, names='cell type', values='cells (n)')
        """),
    Example(
        'donut', 'Donut chart',
        'The same cell types as a donut, with the key at the bottom',
        '`df` is the cell-type table from the pie chart. `hole=0.5` leaves a hole half '
        'the radius of the disc.',
        {'df': cell_types},
        """
        chart = i.pie(df, names='cell type', values='cells (n)', hole=0.5, legend='bottom')
        """),
    Example(
        'lollipop', 'Lollipop chart',
        'Enrichment score of five pathways as dots on stems from zero, one row per '
        'pathway, with the rows read from the top',
        '`df` has `pathway` and `score`, one row per pathway. `orient=\'h\'` lays the '
        'stems across the page.',
        {'df': pathway_scores},
        """
        chart = i.lollipop(df, x='pathway', y='score', orient='h')
        """),
    Example(
        'dumbbell', 'Dumbbell chart',
        'Soil moisture at four sites before and after a dry season: each site is a line '
        'between its two dots, and the legend says which dot is which',
        '`df` has `site`, `before (%)` and `after (%)`, one row per site. `x=` names the '
        'two value columns.',
        {'df': sites},
        """
        chart = i.dumbbell(df, y='site', x=['before (%)', 'after (%)'])
        """),
    Example(
        'waterfall', 'Waterfall chart',
        'A budget from its opening balance to its closing one: sales add, costs and tax '
        'take away, and the closing bar is the running total',
        '`df` has `step` and `change (k$)`. The two `totals=` steps stand from zero; a '
        'missing change on a total shows the running total.',
        {'df': budget},
        """
        chart = i.waterfall(df, x='step', y='change (k$)', totals=['Opening', 'Closing'])
        """),
    Example(
        'slope', 'Slope chart',
        'Support for a policy in four countries in 2015 and in 2025, each country a line '
        'with its name and value written at both ends',
        '`df` has `year`, `country` and `support (%)`: two time points per country. '
        '`format=` writes the values as percentages.',
        {'df': support},
        """
        chart = i.slope(df, x='year', y='support (%)', group='country', format='{:.0f}%')
        """),
    Example(
        'line-secondary', 'Lines on a right-hand axis',
        'Gas, hydro and wind generation on the left axis and solar generation on a '
        'right-hand axis, from 2010 to 2024',
        '`df` is the generation table from the stacked-area example. `secondary_y=` puts '
        'the named series on a right-hand axis with its own scale.',
        {'df': generation},
        """
        chart = i.line(df, x='year', y='generation (TWh)', color='source',
                       secondary_y=['solar'], markers=True)
        """),
    Example(
        'regression-equation', 'Regression with its equation',
        'Absorbance against concentration for a calibration series, with the fitted line, '
        'its confidence band and its equation written on the plot',
        '`df` is the calibration table from the regression example. `equation=True` writes '
        'the fitted line on the plot.',
        {'df': calibration},
        """
        chart = i.regression(df, x='concentration (µM)', y='absorbance (AU)', equation=True)
        """),
    Example(
        'bar-grouped-mean', 'Grouped mean bars with error bars and points',
        'Mean response of control, low-dose and high-dose groups, with a bar for each sex, '
        'standard-error whiskers and a dot for each animal',
        '`df` has `group`, `sex` and `response (a.u.)`, one row per animal. `color=` puts '
        'the bars side by side, and `agg=`, `error_y=` and `points=` work as they do for a '
        'single series.',
        {'df': outcomes_by_sex},
        """
        chart = i.bar(df, x='group', y='response (a.u.)', color='sex', agg='mean',
                      error_y='sem', points=True)
        """),
    Example(
        'survival', 'Survival curves',
        'Kaplan-Meier survival curves for placebo and drug, the drug curve staying higher, '
        'with censor ticks, a confidence band and a number-at-risk table',
        '`df` has `arm`, `months` and `died`. `died` is 1 where the patient died and 0 where '
        'follow-up ended first, which is a censored observation.',
        {'df': survival_arms},
        """
        chart = i.survival(df, time='months', event='died', color='arm')
        """),
    Example(
        'volcano', 'Volcano plot',
        'Log2 fold change against p-value for 200 genes, the changed genes coloured up or '
        'down and two of them named',
        '`df` has one row per gene: `log2 fold change`, a raw `p-value` and an adjusted '
        '`fdr`. `q=` classes each point by its adjusted p-value, and `highlight=` names the '
        'genes to label.',
        {'df': genes},
        """
        chart = i.volcano(df, x='log2 fold change', y='p-value', label='gene', q='fdr',
                          highlight=['Il6', 'Cxcl10'])
        """),
    Example(
        'forest', 'Forest plot',
        'Odds ratios from four studies and their pooled estimate, each study a square on a '
        'log axis with its interval, the pooled estimate a diamond',
        '`df` has `study`, `odds ratio`, `lower` and `upper`, one row per study. `summary=` '
        'draws a flagged row as a diamond, and `right=` lists the text beside the plot: here '
        'the estimate with its interval.',
        {'df': studies},
        """
        chart = i.quick.forest(df, label='study', estimate='odds ratio', lower='lower',
                               upper='upper', summary='pooled', log=True, measure='OR',
                               right=['ci'])
        """),
]

# The page's card grid: each family, its one-line text, and each example's
# card text. A card links to the example's section further down the page.
FAMILIES = [
    ('Lines and trends', 'Series followed along an axis, with their bands and right-hand scales.', [
        ('line', 'Three curves with standard-error bands, one per condition.'),
        ('direct-legend', 'The same curves, named where each line ends.'),
        ('line-secondary', 'Solar on a right-hand axis beside three sources on the left.'),
        ('area', 'Four sources stacked over fifteen years.'),
        ('slope', 'Each country\'s support in two years, joined by a line.'),
    ]),
    ('Relationships', 'Points against points, with fitted lines.', [
        ('scatter-groups', 'Percent response against dose for two strains.'),
        ('scatter-colour', 'Points coloured by a numeric column, with a colour bar.'),
        ('regression', 'A fitted line with its 95 per cent confidence band.'),
        ('regression-equation', 'The same fit, with its equation written on the plot.'),
    ]),
    ('Distributions', 'The spread of values, as histograms, curves and dots.', [
        ('hist', 'Overlaid histograms of body length by sex.'),
        ('kde', 'Smoothed density curves of expression for two genotypes.'),
        ('ecdf', 'Cumulative proportion of latency for two groups.'),
        ('boxplot', 'Box plots of crop yield, with each plot as a dot.'),
        ('violin', 'Violins of grip force across three age cohorts.'),
        ('strip', 'Jittered dots of soil pH at three sites.'),
    ]),
    ('Categories and shares', 'Bars, dots and wedges for counts and totals.', [
        ('bar-count', 'Bars counting specimens in each species.'),
        ('bar-grouped', 'Biomass at four sites, with bars side by side by season.'),
        ('bar-mean', 'Mean response with error bars and a dot for each animal.'),
        ('bar-grouped-mean', 'Mean response by group, one bar per sex, with error bars and dots.'),
        ('lollipop', 'Pathway scores as dots on stems from zero.'),
        ('dumbbell', 'Soil moisture before and after a dry season, at four sites.'),
        ('waterfall', 'A budget from its opening balance to its closing balance.'),
        ('pie', 'Cell types in one tissue sample as a pie.'),
        ('donut', 'The same cell types as a donut.'),
    ]),
    ('Matrices', 'Values in a grid of coloured cells.', [
        ('heatmap', 'Log2 fold change of six genes, centred on zero.'),
    ]),
    ('Studies and survival', 'Statistics from experiments, trials and cohorts.', [
        ('volcano', 'Fold change against p-value for 200 genes, with two named.'),
        ('forest', 'Odds ratios from four studies and their pooled estimate.'),
        ('survival', 'Kaplan-Meier curves for two arms, with a number-at-risk table.'),
    ]),
    ('Panels', 'Several charts in one figure, with shared axes or lettered panels.', [
        ('facets', 'Viability in one panel per cell line, sharing axes.'),
        ('layout', 'Lettered panels placed side by side and stacked.'),
    ]),
]

HEAD = """\
<!-- Generated by tools/quick_gallery.py. Edit the script and run it; this page is written from it. -->

# Chart gallery

Every one-call chart type, drawn from simulated data. Each card shows a chart;
selecting it opens the section below with the code that drew it and the
full-size figure. The examples assume `import inklet as i`. `df` is a table of
simulated measurements, and each figure names its columns. Options such as
`width`, `palette` and `legend` are described in [Charts in one call](quick-charts.md).
"""


def anchor(title):
    """The id mkdocs gives a heading with this text (its toc slug), so a card can link to it."""
    text = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)


def code_of(example):
    """The chart code, dedented and without its surrounding blank lines."""
    return textwrap.dedent(example.code).strip('\n')


def render(example):
    """Draw one example; returns its compiled figure after checking the lint."""
    namespace = {'i': i, **{name: build() for name, build in example.data.items()}}
    exec(compile(code_of(example), f'quick_gallery:{example.name}', 'exec'), namespace)
    chart = namespace['chart']
    figure = chart.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    if serious:
        raise SystemExit(f'{example.name}: lint {[(d.severity, d.code) for d in serious]}\n'
                         + figure.report())
    return figure


def markdown():
    """The page: a section layout whose card grid links to the examples below it.

    The front matter names the card groups for tools/docs_theme/section.html,
    which shows the text above `<!-- cards -->`, then the grid, then the rest:
    one section per example with its note, full-size SVG and code.
    """
    by_name = {example.name: example for example in EXAMPLES}
    groups = []
    for family, text, cards in FAMILIES:
        groups.append({'title': family, 'text': text, 'cards': [
            {'title': by_name[name].title, 'text': summary,
             'image': f'assets/quick-gallery/{name}.png',
             'page': f'quick-gallery.md#{anchor(by_name[name].title)}'}
            for name, summary in cards]})
    front = json.dumps({'layout': 'section', 'title': 'Chart gallery', 'groups': groups},
                       indent=2, ensure_ascii=False)
    sections = []
    for family, text, cards in FAMILIES:
        sections.append(f"## {family}\n\n{text}\n")
        for name, _ in cards:
            example = by_name[name]
            sections.append(f"### {example.title}\n\n{example.note}\n\n"
                            f"![{example.alt}](assets/quick-gallery/{example.name}.svg)\n\n"
                            f"```python\n{code_of(example)}\n```\n")
    return '\n'.join([f'---\n{front}\n---\n', HEAD, '<!-- cards -->\n', *sections])


def main(argv):
    if '--markdown' in argv:
        sys.stdout.write(markdown())
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for example in EXAMPLES:
        figure = render(example)
        path = OUT / f'{example.name}.svg'
        figure.save(path)
        # The card thumbnail: the same figure as a PNG, which docs_thumbnails.py can resize.
        (OUT / f'{example.name}.png').write_bytes(figure.to_png())
        print(path)
    PAGE.write_text(markdown())
    print(PAGE)


if __name__ == '__main__':
    main(sys.argv[1:])
