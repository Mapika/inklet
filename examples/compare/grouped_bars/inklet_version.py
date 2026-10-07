import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import mitochondria, outputs

df = mitochondria()
genotypes = list(df['genotype'].unique())
samples = [[df.length[(df.genotype == g) & (df.treatment == t)].tolist() for g in genotypes]
           for t in ('Vehicle', 'CCCP')]

chart = i.chart(ylabel='Mitochondrial length / µm')
chart.barplot(genotypes, samples, name=['Vehicle', 'CCCP 10 µM'])
figure = chart.save(*outputs('grouped_bars', 'inklet'), dpi=200)
print(figure.report())
