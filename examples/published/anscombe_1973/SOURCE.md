# Source: Anscombe's quartet

## Publication

F. J. Anscombe (1973). Graphs in Statistical Analysis. *The American
Statistician* 27(1): 17–21. doi:[10.1080/00031305.1973.10478966](https://doi.org/10.1080/00031305.1973.10478966)
(JSTOR stable doi:10.2307/2682899).

The figure recreated is the paper's Figures 1–4 (pp. 19–20): one scatterplot
per data set, each with the common fitted line y = 3 + 0.5x, on identical
axes. The paper's Table (p. 19) prints the four data sets.

## Data

- File: `data/anscombe.csv` (11 rows; columns `rownames, x1..x4, y1..y4`).
- URL: <https://vincentarelbundock.github.io/Rdatasets/csv/datasets/anscombe.csv>
  (Rdatasets mirror of R's `datasets::anscombe`, whose documentation cites
  Anscombe 1973 and Tufte 1989, *The Visual Display of Quantitative
  Information*, pp. 13–14).
- Retrieved: 2026-10-07.
- SHA-256: `02a87e7348a05d2fc235e79e6bd89a9e279110d9398e98e32975d82323eb535c`
- Checked value by value against the Table printed in the paper: identical
  (the paper prints x with one decimal, e.g. `10.0`; R stores the integers).

## Licence

The 44 numbers are a fictitious data set constructed by Anscombe and printed
in the paper; numerical facts of this kind are not subject to copyright and
the set is distributed with base R (the `datasets` package) for unrestricted
use. It is widely treated as public domain. The article itself (text and
original artwork) is © American Statistical Association and is **not**
redistributed here: the original page images were viewed only for comparison
and are not in the repository.

## Processing

None. `figure.py` reads the CSV as published, fits each set by ordinary least
squares (`numpy.polyfit`, giving b0 = 3.00, b1 = 0.500 for every set, as the
paper reports) and draws that line across the full x range 0–20.
