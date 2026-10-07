# Source: snowshoe hare and Canada lynx pelt returns, 1845-1935

## Figure being recreated

The classic predator-prey plot of the Hudson's Bay Company (HBC) fur records:
annual numbers of snowshoe hare (solid) and Canada lynx (dashed) pelts, in
thousands, 1845-1935, as drawn in Odum's *Fundamentals of Ecology* and many
textbooks since. The reference image was viewed only and is not stored in the
repository: `Lynx-Hare_cycle.jpg` (860 x 426 px), published on the Hudson Bay
population cycles page of Memorial University of Newfoundland
(https://mun.ca/biology/scarr/Hudson_Bay_population_cycles.html; page text
(c) 2025 Steven M. Carr). The image caption there reads "Population cycles in
Lynx & its prey (Elton 1925)".

## Primary sources

- MacLulich, D. A. (1937). *Fluctuations in the Numbers of the Varying Hare
  (Lepus americanus)*. University of Toronto Studies, Biological Series No. 43.
  University of Toronto Press. (The HBC pelt series is in this monograph.)
- Elton, C. & Nicholson, M. (1942). The ten-year cycle in numbers of the lynx
  in Canada. *Journal of Animal Ecology* 11(2), 215-244.
  https://doi.org/10.2307/1358
- Odum, E. P. *Fundamentals of Ecology*, Saunders, p. 191 (the page the
  astsa package cites for the series; the edition is not stated there).
- Stenseth, N. C., Falck, W., Bjornstad, O. N. & Krebs, C. J. (1997).
  Population regulation in snowshoe hare and Canadian lynx: asymmetric food
  web configurations between hare and lynx. *PNAS* 94(10), 5147-5152.
  (Background only; not used for any value.)

## Data

- File: `data/LynxHare.txt`, unmodified copy of
  http://people.whitman.edu/~hundledr/courses/M250F03/LynxHare.txt
  (a Whitman College course page, path `M250F03`; plain text, no header;
  91 lines, 1845-1935; columns: year, hare, lynx; both series in
  thousands of pelts; 1,606 bytes; md5 3ebf3cb7b96da8389ea9ba3f63abee8a).
- Retrieved: 2026-10-07.
- Cross-checks (all agree exactly):
  - R package astsa 2.5, objects `Hare` and `Lynx` (CRAN, GPL >= 2): the same
    91 values per series, checked number by number. astsa cites Odum p. 191 and
    describes the series as "the number, in thousands, of snowshoe hare pelts
    purchased by the Hudson's Bay Company".
  - R package tsibbledata 0.4.1, dataset `pelt` (CRAN, GPL-3): the same
    numbers in raw pelt counts (for example 1845: 19,580 hare, 30,090 lynx).
    It is a tsibble of "Hudson Bay Company trading records ... for all areas of
    the company".
- Licence: no licence is stated on the Whitman page. The numbers are
  historical HBC trade records, published in MacLulich (1937) and by Odum, and
  redistributed under GPL in astsa and tsibbledata. The file is kept as an
  unmodified copy for provenance.
- Caveat (from astsa and the Carr page): the series counts pelts traded, an
  indirect index of the animal populations. The trapping effort is not known
  and the pelt returns depend on it.

## Processing (all in `figure.py`)

- Whitespace-separated read with no header; columns named year, hare, lynx.
  Values are used as published (thousands), not scaled or smoothed. Each
  series is joined through its annual points in year order.
