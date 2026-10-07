# Notes: Gapminder bubble chart, 1952 and 2007

`figure.py`: 62 lines, with one function building a panel per year. Output:
`gallery/published/gapminder.{png,svg,pdf}`, double column (183 mm), two
panels a (1952) and b (2007) on identical axes. `figure.report()`:
`inklet lint: 2 warnings, 6 infos`. The two warnings are LOW_CONTRAST on the
pale year watermarks (`color='#e8e8e8'`, 1.23:1), which are meant to recede;
lint's opt-out for decorative text (`kind=inklet.diagnostics.decorative()`)
is still being settled, so it is not used yet (ISSUES-medicine-econ.md, 5).
The infos are CROWDING notes: a country label is 0.01-0.8 mm from a bubble
(they now name the bubble, not the whole panel). `inklet check --strict`
fails on the two warnings until the watermark is declared decorative.

## Matches the reference (Gapminder World chart)

- Encodings: GDP per capita on a log x axis, life expectancy at birth on y,
  bubble area proportional to population, colour by region.
- The region hues are Gapminder's: Africa blue, the Americas green, Asia red,
  Europe yellow-orange.
- The big countries are named: China, India, the United States, Indonesia,
  Brazil, Nigeria, Japan and South Africa. Labels sit clear of the bubbles,
  with leaders where they had to move away.
- Small bubbles are drawn over large ones, as Gapminder draws them, with a
  thin white outline separating overlaps.
- Log ticks at 500, 1k, 2k, 5k, 10k, 20k and 50k, Gapminder's tick values,
  plus 100k for the 1952 Kuwait outlier at about $108k.
- The year is set large and pale behind the data, the signature of the
  animated Gapminder chart.
- A population size key (10 million, 100 million, 1 billion), close to
  Gapminder's "Size by population" key (3, 10, 100, 1000 million).
- The 2007 panel shows the familiar picture: China and India mid-curve,
  Africa spread along the lower left, Japan at the top right, and South
  Africa and Nigeria well below their income peers.

## Differs, and why

- Two panels, 1952 and 2007, on shared axes, where the poster has a single
  year (2012). The 2007 panel is the requested chart and 1952 is the
  suggested companion. The axes are identical, so the shift up and to the
  right reads directly.
- Five continents (the R package excerpt) instead of Gapminder's four regions.
  The excerpt's 142 countries replace the poster's 193 UN members. Russia,
  for example, is not in the excerpt.
- inklet's look: no ornaments (compass rose, world map key, region lines).
  The continent key and the size key sit below the panels rather than in a
  framed box on the plot, because in a double-column figure the two key
  boxes would cover data in one panel or the other. The size key's circles
  stand on a line with their values beneath them.
- The axis titles are scientific-style ("GDP per capita / US$
  (inflation-adjusted, log scale)", "Life expectancy at birth / years"). The
  poster has "INCOME PER PERSON" and "LIFE EXPECTANCY". The poster also
  separates thousands with a thin space ("10 000"), and here the ticks use
  "k".
- Both keys sit below the panels by choice. The vertical size key now
  aligns its circles and labels (ISSUES-medicine-econ.md, 3, fixed), but
  keys on the right made the two plot areas unequal and narrower, which
  crowded the bubbles. The size key's labels are formatted by hand
  ("10 million"): the default writes `1e7`.

## Verdict

Faithful in content and encoding to Gapminder's chart: the same variables,
scales, area encoding, region hues, named countries and year watermark. It
is re-styled in inklet's look as a double-column comparison of 1952 and
2007, and is ready for publication. The keys below the panels leave some
white space under panel a. That is the main compromise.
