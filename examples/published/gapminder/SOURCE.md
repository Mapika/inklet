# Source: Gapminder life expectancy vs income bubble chart (1952 and 2007)

## Figure being recreated

Hans Rosling's Gapminder bubble chart, "Health and Wealth of Nations", plots
income per person on a log scale against life expectancy. Each circle is a
country, its area proportional to population, and its colour gives the world
region. The chart was published by the Gapminder Foundation (gapminder.org,
the Gapminder World posters and the animated Trendalyzer chart) and is used
throughout:

- Rosling, H., Rosling, O. & Rosling Rönnlund, A. (2018). *Factfulness: Ten
  Reasons We're Wrong About the World - and Why Things Are Better Than You
  Think*. Flatiron Books (US) / Sceptre (UK). ISBN 978-1-250-10781-7.

The visual reference was the Gapminder Foundation's "Gapminder World 2012"
poster (CC BY 3.0, Wikimedia Commons, `File:Gapminder-World-2012.pdf`). It was
viewed only and is not stored in this repository. The 2007 cross-section with
log GDP per capita, life expectancy, bubble area for population and continent
colours is the standard reproduction built from the `gapminder` R package.
The package's own example is `plot(lifeExp ~ gdpPercap, gapminder,
subset = year == 2007, log = "x")`.

## Data

- File: `data/gapminder.csv`, an unmodified copy of
  https://vincentarelbundock.github.io/Rdatasets/csv/gapminder/gapminder.csv:
  1704 rows (142 countries x 12 years, 1952-2007 every 5 years). Columns:
  `rownames, country, continent, year, lifeExp, pop, gdpPercap`. 89 KB.
  sha256 `787a909f89c853d2b6ea02106c4e0d8f3f7f0f992ba36149af41c6b31817e425`.
- Excerpt by Jennifer Bryan: Bryan, J. *gapminder: Data from Gapminder*.
  R package version 1.0.1. https://doi.org/10.32614/CRAN.package.gapminder,
  https://github.com/jennybc/gapminder. Package licence: CC0. Its source is
  https://www.gapminder.org/data/.
- Underlying data: Gapminder Foundation, free material under CC BY 4.0
  ("Free data from www.gapminder.org"). `gdpPercap` is GDP per capita in US$,
  inflation-adjusted (the package documentation's wording), `lifeExp` is life expectancy at birth in years, and `pop` is
  population.
- Retrieved: 2026-10-07.

## Processing (all in `figure.py`)

- Rows for 1952 and for 2007 (142 countries each). No values are missing.
- Bubble diameter = 15 mm x sqrt(pop / 1.5e9), using
  `inklet.plot.area_scale(1.5e9, 15)`, so bubble area is proportional to
  population. China in 2007 (1.32 billion) is the largest, at 14.1 mm.
- Bubbles are drawn largest first, so small countries stay visible on top of
  large ones, as on gapminder.org.
- Continent colours follow Gapminder's region hues: Africa blue, the Americas
  green, Asia red, Europe yellow-orange. Oceania (Australia and New Zealand,
  a separate continent in this excerpt) is purple. The colours are taken from
  the inklet `scientific.modern` palette.
- Labelled countries: China, India, the United States, Indonesia, Brazil,
  Nigeria, Japan and South Africa.
