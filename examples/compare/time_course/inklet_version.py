import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import outputs, time_course

chart = i.line(time_course(), x='time', y='mean', color='condition', error_y='ci',
               xlabel='Time / h', ylabel='Reporter signal / a.u.', xlim=(0, 48))
figure = chart.save(*outputs('time_course', 'inklet'), dpi=200)
print(figure.report())
