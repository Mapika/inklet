# Source: Hubble (1929), Figure 1

**Paper.** Edwin Hubble, "A relation between distance and radial velocity
among extra-galactic nebulae", *Proceedings of the National Academy of
Sciences* **15**(3), 168–173 (1929).
DOI: [10.1073/pnas.15.3.168](https://doi.org/10.1073/pnas.15.3.168);
PMC: [PMC522427](https://pmc.ncbi.nlm.nih.gov/articles/PMC522427/).
Figure 1 ("Velocity-Distance Relation among Extra-Galactic Nebulae"), p. 172.

**Licence.** The article was published in the United States in 1929; its
copyright term has expired and it is in the public domain in the US. The
tabulated values are facts transcribed from it. Positions come from SIMBAD
(CDS, Strasbourg; Wenger et al. 2000, A&AS 143, 9), which asks to be
acknowledged when used.

**Retrieved.** 2026-10-07.

**Copies consulted.**
* A scan of the printed article (pages 168–173), CCITT images in
  <https://www.hep.shef.ac.uk/roszkowski/phy306/papers/hubble1929.pdf>,
  decoded and read page by page (PNAS and PMC PDF links were behind a
  bot challenge from this machine).
* A retyped transcription in
  <https://www.astro.rug.nl/~weygaert/tim1publication/cosmo2007/literature/hubble.1929.pdf>
  (from the NASA "Scale of the Universe" 1996 debate pages).

## Files in `data/`

### `table1.csv`: Table 1, transcribed

The 24 nebulae of Table 1 ("Nebulae whose distances have been estimated from
stars involved or from mean luminosities in a cluster"): `ms` photographic
magnitude of the brightest stars, `r_mpc` distance in 10⁶ parsecs, `v_kms`
measured velocity in km/s, `mt` total visual magnitude, `Mt` total visual
absolute magnitude.

Every `r` and `v` was read from the scan and checked against the retyped
transcription; all 24 pairs agree. Spot checks: N.G.C. 6822 r 0.214,
v −130; N.G.C. 1068 r 1.0, v +920; N.G.C. 4649 r 2.0, v +1090. The printed
table shows the minus sign only on the first `Mt` (−16.0) and on the mean
(−15.5); the column is absolute magnitudes, so the sign is restored on every
row here (the retyped copy drops it everywhere). `ms` is blank (".." in the
paper) where no value is given. `Mt` and `ms` are not used by the figure.

### `coordinates.csv`: positions for the solar-motion correction

J2000 right ascension and declination (degrees) from SIMBAD's `basic` table
for each nebula (S. Mag. = SMC, L. Mag. = LMC), fetched with a TAP query on
2026-10-07. `figure.py` precesses them to B1900 (IAU 1976 precession).

### `group_means.csv`: the 9 group points (open circles)

The paper says the 24 nebulae were combined "into 9 groups according to
proximity in direction and in distance" but does not list the groups.
* 4 groups are identified unambiguously and are **computed** with the group
  solution (solar motion X = +3, Y = +230, Z = −133 km/s): the Magellanic
  Clouds; M31 + M32 + M33; N.G.C. 6822 alone (its circle is hidden under its
  own disc in the original, which is why that disc looks larger); N.G.C. 5236
  alone. Each agrees with the circle in the scanned figure to within 6 km/s.
* The other 5 are **digitized** from the scanned Figure 1: axis calibration
  from the printed grid lines (0, 10⁶, 2×10⁶ parsecs; 0, 500, 1000 km), ring
  centres found by a ring-template search in the 1-bit scan. Estimated
  uncertainty ±0.01 Mpc and ±10 km/s (the circle at 1.4 Mpc lies under the
  cross, so it is less certain). A search for partitions of the remaining 17
  nebulae that reproduce these 5 means found several, none unique, so the
  digitized positions are used.

## Processing done in `figure.py`

The figure plots "radial velocities, corrected for solar motion". The paper's
equation of condition is rK + X cos α cos δ + Y sin α cos δ + Z sin δ = v, and
the correction subtracts the solar-motion term from v, using the solution
for the 24 nebulae individually (X = −65, Y = +226, Z = −195 km/s).

Validation:
* Applied to Table 2 with Hubble's adopted round-number solution (apex
  A = 277°, D = +36°, V₀ = 280 km/s), the same code reproduces his tabulated
  solar-motion terms `vs` for 21 of the 22 nebulae within 13 km/s (mean
  |difference| 4.8 km/s, N.G.C. 3115 is the exception at 51 km/s).
* A least-squares refit of Table 1 with these positions gives K = 465,
  X = −66, Y = +237, Z = −199, against the published 465, −65, 226, −195.
* Overlaid on the scanned figure, all 24 corrected points fall on the
  printed black discs.

Lines: v = 465 r (individual solution) and v = 513 r (group solution), drawn
from the origin to r = 2.22 and 2.14, where the lines of those slopes end in
the original (measured on the scan). Note that in the printed figure the
**full** line has slope 513 and the **broken** line slope 465 (measured at
r = 1.25, 1.5, 1.8 and 2.1 on the scan), the reverse of the caption, which
pairs the full line with the individual solution (K = 465). The recreation
follows the caption and the K values in the text; see NOTES.md.
Cross: 745 km/s at 1.4 × 10⁶ parsecs (paper, p. 172).
