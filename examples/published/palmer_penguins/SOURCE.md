# Source: Palmer penguins (genus *Pygoscelis*)

## Study

Gorman, K. B., Williams, T. D. & Fraser, W. R. (2014). Ecological sexual
dimorphism and environmental variability within a community of Antarctic
penguins (genus *Pygoscelis*). *PLoS ONE* 9(3), e90081.
https://doi.org/10.1371/journal.pone.0090081

## Figure being recreated

The bill length vs bill depth figure by species with per-species linear fits
("Penguin bill dimensions", and the "Simpson's paradox" companion with one
pooled fit), and the flipper length histogram by species ("Penguin flipper
lengths"), as published in the palmerpenguins package README and pkgdown site
(https://allisonhorst.github.io/palmerpenguins/articles/examples.html) and in
Horst, Hill & Gorman (2022). The reference images were viewed only; they are
not stored in this repository.

## Data

- File: `data/penguins.csv`, unmodified copy of
  https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv
  (344 penguins, 8 columns; 'NA' marks missing values; 14 KB;
  md5 a06a0210251465a86fb970018292304d).
- Retrieved: 2026-10-07.
- Licence: CC0 1.0 (public domain dedication), per the palmerpenguins
  package and the Palmer Station LTER data policy.
- Package: Horst, A. M., Hill, A. P. & Gorman, K. B. (2020). palmerpenguins:
  Palmer Archipelago (Antarctica) penguin data. R package version 0.1.0.
  https://doi.org/10.5281/zenodo.3960218
- Package paper: Horst, A. M., Hill, A. P. & Gorman, K. B. (2022). Palmer
  Archipelago penguins data in the palmerpenguins R package - an alternative
  to Anderson's irises. *The R Journal* 14(1), 244-254.
  https://doi.org/10.32614/RJ-2022-020
- Original data (Environmental Data Initiative, Palmer Station Antarctica LTER
  and K. Gorman, 2020):
  Adelie https://doi.org/10.6073/pasta/98b16d7d563f265cb52372c8ca99e60f ;
  Gentoo https://doi.org/10.6073/pasta/7fca67fb28d56ee2ffa3d9370ebda689 ;
  Chinstrap https://doi.org/10.6073/pasta/c14dfcfada8ea13a17536e73eb6fbe9e

## Processing (all in `figure.py`)

- Panel a: rows missing bill length or depth dropped (2 rows; n = 342:
  Adelie 151, Chinstrap 68, Gentoo 123). Ordinary least-squares fit of depth on
  length per species with 95% confidence band, and one pooled fit over all
  species (dashed, no band).
- Panel b: rows missing flipper length dropped (n = 342). Counts in 2 mm bins
  from 172 to 232 mm, the same edges for every species, overlaid.
