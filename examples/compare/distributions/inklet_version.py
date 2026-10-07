import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import distributions, outputs

chart = i.violin(distributions(), x='genotype', y='density', points=True,
                 xlabel='', ylabel='Spine density / µm^{-1}')
figure = chart.save(*outputs('distributions', 'inklet'), dpi=200)
print(figure.report())
