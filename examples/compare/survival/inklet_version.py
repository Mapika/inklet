import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import outputs, survival

df = survival()
arms = {arm: (group['months'], group['event']) for arm, group in df.groupby('arm', sort=False)}
chart = i.chart(xlabel='Time / months', ylabel='Overall survival', xlim=(0, 60), ylim=(0, 1),
                height=72)
chart.kaplan_meier(arms).legend(corner='ne').at_risk()
figure = chart.save(*outputs('survival', 'inklet'), dpi=200)
print(figure.report())
