"""Gapminder: life expectancy against income, 1952 and 2007 (Rosling's bubble chart).

Each bubble is a country: GDP per capita (log scale) on x, life expectancy at
birth on y, bubble area proportional to population, colour by continent.
Data: the `gapminder` R package excerpt (Jennifer Bryan), from Gapminder.
"""
from pathlib import Path

import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'gallery' / 'published'

style = i.preset('scientific.modern', format='double-column')
blue, red, _, gold, purple, _, green, _ = style.theme.palette
# Gapminder's own region hues: Africa blue, the Americas green, Asia red,
# Europe yellow-orange; Oceania (Australia, New Zealand) gets its own.
CONTINENTS = {'Africa': blue, 'Americas': green, 'Asia': red, 'Europe': gold, 'Oceania': purple}
LABELLED = ['China', 'India', 'United States', 'Indonesia', 'Brazil', 'Nigeria', 'Japan',
            'South Africa']
TICKS = [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]

data = pd.read_csv(HERE / 'data' / 'gapminder.csv')
sizes = i.plot.area_scale(1.5e9, 15)          # 1.5 billion people = 15 mm across


def bubbles(year, *, first):
    rows = data[data['year'] == year].sort_values('pop', ascending=False)  # big under small
    p = i.plot_spec(height=74, x=i.log((200, 130000)), y=(25, 87))
    # The year in large pale type behind the bubbles, as in Gapminder's animated chart.
    p.text(30000, 33, f'**{year}**', size=i.pt(40), color='#e8e8e8', front=False, decorative=True)
    p.scatter(list(zip(rows['gdpPercap'], rows['lifeExp'])),
              size=[sizes(v) for v in rows['pop']],
              color=[CONTINENTS[c] for c in rows['continent']],
              fill_opacity=0.85, stroke='#ffffff', stroke_width=style.theme.hairline)
    named = rows[rows['country'].isin(LABELLED)]
    p.label_points(list(zip(named['gdpPercap'], named['lifeExp'])), list(named['country']))
    p.axes(x='GDP per capita / US$ (inflation-adjusted, log scale)',
           y='Life expectancy at birth / years' if first else None,
           x_options={'ticks': TICKS,
                      'format': lambda v: f'{v / 1000:g}k' if v >= 1000 else f'{v:g}'})
    if first:
        p.legend(side='bottom', title='Continent', entries=list(CONTINENTS.items()))
    else:
        p.size_key(sizes, side='bottom', values=[1e7, 1e8, 1e9], title='Population',
                   format=lambda v: f'{v / 1e6:g} million' if v < 1e9 else '1 billion')
    return p


doc = style.document(columns=2, share_plot_margins=True).letters()
doc.add('y1952', bubbles(1952, first=True), row=0, column=0)
doc.add('y2007', bubbles(2007, first=False), row=0, column=1)

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    figure = doc.compile()
    figure.save(OUT / 'gapminder.svg', OUT / 'gapminder.pdf')
    (OUT / 'gapminder.png').write_bytes(figure.to_png(dpi=200))
    print(figure.report())
