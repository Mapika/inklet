import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inklet as i

from data import outputs, volcano

df = volcano()
chart = i.chart(xlabel='log_{2} fold change', ylabel='−log_{10} //P//')
chart.volcano(df['log2fc'], df['p'], labels=df['gene'], top=10, size=1.0)
figure = chart.save(*outputs('volcano', 'inklet'), dpi=200)
print(figure.report())
