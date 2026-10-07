# Source: the Gutenberg-Richter magnitude-frequency law

## Figure being recreated

The Gutenberg-Richter law: the number of earthquakes N at or above magnitude M
falls off as log10 N = a - bM, with b near 1. The founding paper's figure
is not a plot: Gutenberg & Richter (1944) report the counts and a least-squares
fit to them in tables and equations (pages 185-187). The paper has no figure
(all four pages were checked). The plotted form, log N against M with a fitted line, is
the standard presentation. A modern version of it (Wikimedia Commons,
"Gutenberg-Richter law in the 2016 Central Italy earthquake (magnitude).png",
CC BY-SA 4.0): log number of events against magnitude, points, and a red fit
line labelled with a and b. That image was viewed only and is not stored here.

## References

- Gutenberg, B. & Richter, C. F. (1944). Frequency of earthquakes in California.
  *Bulletin of the Seismological Society of America* 34(4), 185-188.
  https://doi.org/10.1785/BSSA0340040185
  (The paper is on the Caltech authors repository; the fit values quoted in
  NOTES.md are from its pages 186-187.)

The DOI was checked against the Crossref record on 2026-10-07.

## Data

- File: `data/usgs_m4.5_2016_2025.csv`, derived from the USGS earthquake
  catalogue (ComCat) through its FDSN event web service:
  https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=YYYY-01-01&endtime=YYYY-12-31T23:59:59&minmagnitude=4.5
  for each year 2016 to 2025, since one query over the full decade returns
  "74424 matching events exceeds search limit of 20000".
- Retrieved: 2026-10-07. 74,436 events with magnitude 4.5 or more, of which
  74,359 are earthquakes; the other 77 are volcanic eruptions (71), nuclear
  explosions (3), landslides (2) and a mine collapse (1), dropped by
  `type == "earthquake"`. The file has two columns: `date` (UTC date, YYYY-MM-DD,
  from `time`) and `mag` (the catalogue's preferred magnitude, unmodified). The
  full time stamp and the other columns are dropped to keep the file under 2 MB
  (1.18 MB here). Magnitude types are mixed (mb, Mww, ml, ... ); `magType` was
  not kept.
- Licence: USGS data and products are in the public domain (USGS copyright
  policy). Credit: U.S. Geological Survey, Earthquake Hazards Program,
  https://earthquake.usgs.gov/earthquakes/search/.

## Processing (all in `figure.py`)

- N(>=M) is the count of events with mag >= M, on the 0.1 magnitude grid from
  4.5 to 8.8, divided by 10 years (2016-01-01 to 2025-12-31) to give events per
  year. Points with N = 0 are dropped (none occur in this range).
- Fit: least squares of log10 N on M over 5.0 <= M <= 7.5 (26 grid points,
  unweighted, as asked). Result: a = 8.30, b = 1.025 +/- 0.007 (standard error from
  the residuals), R^2 = 0.9987. The printed b is 1.02 to two decimals.
- The choice of range: the local slope of the cumulative counts is 1.23 between
  M 4.5 and 5.0 (steeper than b = 1, the bend the fit should not include), 1.02 between
  5.0 and 7.5, and 1.84 between 7.5 and 8.5 (a few events, so noisy). The fit is
  therefore restricted to 5.0-7.5. The cause of the low-magnitude bend is not
  tested here (the catalogue mixes magnitude types, and small events are less
  completely reported). The fit over 4.5-8.5 gives b = 1.14, which is why the
  range matters.
- Aki's maximum-likelihood b for M >= 5.0 (a check, not plotted) is 1.15.
