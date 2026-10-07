# Published figures, recreated

Eight well-known figures from eight fields, rebuilt in Inklet from the data
behind them. Each lives in
[`examples/published/`](../examples/published/) with its data, a `SOURCE.md`
(full citation, data URL, licence, retrieval date and any processing) and a
`NOTES.md` that says what matches the original and what differs. Each script
runs in under a second and its lint report is clean.

Original figure images are not reproduced here; follow the citations to see
them. The recreations are restyled in Inklet's default look, not copied
pixel for pixel. Where a published figure needed data that is not public, the
notes say what was left out.

## Physics: the first gravitational-wave detection

![LIGO GW150914: Hanford and Livingston strain, numerical-relativity waveforms and residuals](../gallery/published/ligo_gw150914.png)

Abbott et al. (LIGO and Virgo Collaborations), "Observation of Gravitational
Waves from a Binary Black Hole Merger", *Phys. Rev. Lett.* 116, 061102 (2016),
[doi:10.1103/PhysRevLett.116.061102](https://doi.org/10.1103/PhysRevLett.116.061102), Figure 1.
Data: the GWOSC Figure 1 release (CC BY 4.0), unmodified. The three strain
rows are recreated; the spectrogram row and the 90% waveform bands are not
published as data. [Script](../examples/published/ligo_gw150914/figure.py) ·
[notes](../examples/published/ligo_gw150914/NOTES.md)

## Astronomy: Hubble's velocity–distance relation

![Hubble 1929: velocity against distance for 24 nebulae with both fitted lines](../gallery/published/hubble_1929.png)

E. Hubble, "A relation between distance and radial velocity among
extra-galactic nebulae", *PNAS* 15, 168–173 (1929),
[doi:10.1073/pnas.15.3.168](https://doi.org/10.1073/pnas.15.3.168), Figure 1.
Data: Table 1 of the paper (public domain), with velocities corrected for solar
motion using Hubble's own solution; the refit reproduces his K = 465 km/s/Mpc.
Five of the nine group means are read from the printed figure.
[Script](../examples/published/hubble_1929/figure.py) ·
[notes](../examples/published/hubble_1929/NOTES.md)

## Climate: the Keeling curve

![Monthly mean CO2 at Mauna Loa, 1958–2026, with the average seasonal cycle inset](../gallery/published/keeling_curve.png)

C. D. Keeling et al., "Atmospheric carbon dioxide variations at Mauna Loa
Observatory, Hawaii", *Tellus* 28, 538–551 (1976), and the NOAA GML / Scripps
record as published at gml.noaa.gov. Data: NOAA GML monthly means (public
domain), March 1958 to August 2026.
[Script](../examples/published/keeling_curve/figure.py) ·
[notes](../examples/published/keeling_curve/NOTES.md)

## Ecology: Palmer penguins

![Bill depth against bill length by species with per-species and pooled fits, and flipper length histograms](../gallery/published/palmer_penguins.png)

K. B. Gorman, T. D. Williams & W. R. Fraser, "Ecological sexual dimorphism and
environmental variability within a community of Antarctic penguins (genus
*Pygoscelis*)", *PLoS ONE* 9, e90081 (2014),
[doi:10.1371/journal.pone.0090081](https://doi.org/10.1371/journal.pone.0090081),
as packaged and plotted by Horst, Hill & Gorman (palmerpenguins, CC0). Panel a
shows Simpson's paradox: the pooled slope is negative, every species' slope
positive. [Script](../examples/published/palmer_penguins/figure.py) ·
[notes](../examples/published/palmer_penguins/NOTES.md)

## Medicine: survival in advanced lung cancer

![Kaplan–Meier overall survival by sex with confidence bands, censor marks, log-rank P and number at risk](../gallery/published/ncctg_lung.png)

Loprinzi et al., "Prospective evaluation of prognostic variables from
patient-completed questionnaires", *J. Clin. Oncol.* 12, 601–607 (1994),
[doi:10.1200/JCO.1994.12.3.601](https://doi.org/10.1200/JCO.1994.12.3.601).
The trial's data are R's `survival::lung`; this Kaplan–Meier plot by sex is
their standard published presentation (R `survival` and survminer
documentation), not a figure printed in the paper. Medians, at-risk counts and
the log-rank P = 0.0013 match R.
[Script](../examples/published/ncctg_lung/figure.py) ·
[notes](../examples/published/ncctg_lung/NOTES.md)

## Genomics: glucocorticoid response in airway smooth muscle

![Volcano plot of dexamethasone versus untreated expression with 316 significant genes and labelled glucocorticoid-responsive genes](../gallery/published/rnaseq_volcano.png)

Himes et al., "RNA-Seq transcriptome profiling identifies CRISPLD2 as a
glucocorticoid responsive gene that modulates cytokine function in airway
smooth muscle cells", *PLoS ONE* 9, e99625 (2014),
[doi:10.1371/journal.pone.0099625](https://doi.org/10.1371/journal.pone.0099625), Figure 1A.
Data: the authors' Cuffdiff results deposited with the paper (GEO GSE52778);
316 genes at q < 0.05, as in the caption. Gene labels are added.
[Script](../examples/published/rnaseq_volcano/figure.py) ·
[notes](../examples/published/rnaseq_volcano/NOTES.md)

## Development: health and wealth of nations

![Gapminder bubble charts of life expectancy against GDP per capita in 1952 and 2007](../gallery/published/gapminder.png)

Hans Rosling's Gapminder chart (Gapminder Foundation; Rosling, Rosling &
Rosling Rönnlund, *Factfulness*, 2018), with the `gapminder` data excerpt
(CC0; Gapminder data CC BY 4.0). Bubble area is population; 1952 and 2007
share their axes. [Script](../examples/published/gapminder/figure.py) ·
[notes](../examples/published/gapminder/NOTES.md)

## Statistics: Anscombe's quartet

![Anscombe's four data sets, each with the same fitted line y = 3 + 0.5x](../gallery/published/anscombe_1973.png)

F. J. Anscombe, "Graphs in Statistical Analysis", *The American Statistician*
27, 17–21 (1973),
[doi:10.1080/00031305.1973.10478966](https://doi.org/10.1080/00031305.1973.10478966),
Figures 1–4. Data: the paper's table, checked value by value.
[Script](../examples/published/anscombe_1973/figure.py) ·
[notes](../examples/published/anscombe_1973/NOTES.md)

## Rebuild them

```sh
for script in examples/published/*/figure.py; do python "$script"; done
```

The scripts write to `gallery/published/`. They need pandas and NumPy for
reading the data files.
