"""Build the one-call chart gallery: its SVGs and the page that shows their code.

    python tools/quick_gallery.py             # write docs/assets/quick-gallery/*.svg and the page
    python tools/quick_gallery.py --markdown  # print the page instead of writing it

Each example's code is a string here. The string is executed to draw the
figure and is also the code block on docs/quick-gallery.md, so the page cannot
drift from what ran. The data are simulated with fixed seeds, so a rerun
reproduces the same files. Every figure must lint without errors or warnings.
"""
from __future__ import annotations

import math
import random
import sys
import textwrap
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
        '`df` has `group` and `latency (ms)`, 50 animals per group. The axis is fixed '
        'with `xlim=`.',
        {'df': latency},
        """
        chart = i.ecdf(df, x='latency (ms)', color='group', xlim=(0, 600))
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
        'facets', 'Panels with facet_col',
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
        'layout', 'Panels with | and /',
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
]

HEAD = """\
<!-- Generated by tools/quick_gallery.py. Edit the script and run it; this page is written from it. -->

# Chart gallery

Every one-call chart type, drawn from simulated data, with the code that drew it.
The examples assume `import inklet as i`. `df` is a table of simulated
measurements, and each figure names its columns. Options such as `width`,
`palette` and `legend` are described in [Charts in one call](quick-charts.md).
"""


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
    """The page: heading, note, image and code for each example, in order."""
    parts = [HEAD]
    for example in EXAMPLES:
        parts.append(f"## {example.title}\n\n{example.note}\n\n"
                     f"![{example.alt}](assets/quick-gallery/{example.name}.svg)\n\n"
                     f"```python\n{code_of(example)}\n```\n")
    return '\n'.join(parts)


def main(argv):
    if '--markdown' in argv:
        sys.stdout.write(markdown())
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for example in EXAMPLES:
        figure = render(example)
        path = OUT / f'{example.name}.svg'
        figure.save(path)
        print(path)
    PAGE.write_text(markdown())
    print(PAGE)


if __name__ == '__main__':
    main(sys.argv[1:])
