import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import correlation, outputs

chart = i.heatmap(correlation(), palette='rdbu', center=0, height=80, colorbar='Pearson //r//')
figure = chart.save(*outputs('heatmap', 'inklet'), dpi=200)
print(figure.report())
