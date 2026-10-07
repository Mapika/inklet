import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import distributions, dose_response, mitochondria, outputs, time_course

course = i.line(time_course(), x='time', y='mean', color='condition', error_y='ci',
                xlabel='Time / h', ylabel='Reporter signal / a.u.', xlim=(0, 48))

cells = mitochondria()
genotypes = list(cells['genotype'].unique())
samples = [[cells.length[(cells.genotype == g) & (cells.treatment == t)].tolist() for g in genotypes]
           for t in ('Vehicle', 'CCCP')]
bars = i.chart(ylabel='Mitochondrial length / µm')
bars.barplot(genotypes, samples, name=['Vehicle', 'CCCP 10 µM'])

points, curves, ec50 = dose_response()
dose = i.scatter(points, x='conc', y='viability', color='compound', size=1.2, xscale='log',
                 xlabel='Concentration / M', ylabel='Viability / % of control')
dose.line(curves, x='conc', y='fit', color='compound')

spread = i.violin(distributions(), x='genotype', y='density', points=True,
                  xlabel='', ylabel='Spine density / µm^{-1}')

figure = ((course | bars) / (dose | spread)).save(*outputs('multi_panel', 'inklet'), dpi=200)
print(figure.report())
