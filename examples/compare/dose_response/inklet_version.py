import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import dose_response, outputs

points, curves, ec50 = dose_response()
chart = i.scatter(points, x='conc', y='viability', color='compound', size=1.2, xscale='log',
                  xlabel='Concentration / M', ylabel='Viability / % of control')
chart.line(curves, x='conc', y='fit', color='compound')
figure = chart.save(*outputs('dose_response', 'inklet'), dpi=200)
print(figure.report())
