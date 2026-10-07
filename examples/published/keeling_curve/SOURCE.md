# Source: the Keeling curve (atmospheric CO2 at Mauna Loa Observatory)

## Figure being recreated

NOAA Global Monitoring Laboratory / Scripps Institution of Oceanography,
"Atmospheric CO2 at Mauna Loa Observatory" (full-record monthly mean figure,
https://gml.noaa.gov/ccgg/trends/ , image `co2_data_mlo.png`), together with the
average seasonal-cycle inset of the widely reproduced Keeling-curve figure built
from the same NOAA/Scripps data (Wikimedia Commons, "Mauna Loa CO2 monthly mean
concentration.svg"). The reference images were viewed only; they are not
stored in this repository.

## Data

- File: `data/co2_mm_mlo.txt`, unmodified copy of
  https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt
  (file header: "File Creation: Sat Sep 5 03:55:38 2026"; 822 monthly rows,
  March 1958 to August 2026; 58 KB).
- Retrieved: 2026-10-07.
- Licence: NOAA GML data are US Government work, in the public domain, made
  freely available with a request for citation (see the file header).
- Requested credit (NOAA "How to reference content from this page"):
  Dr. Xin Lan, NOAA/GML (gml.noaa.gov/ccgg/trends/) and Dr. Ralph Keeling,
  Scripps Institution of Oceanography (scrippsco2.ucsd.edu/).
- Data from March 1958 to April 1974 are Scripps (C. D. Keeling) measurements;
  from May 1974 on, NOAA. December 2022 to early July 2023 are from Maunakea
  (Mauna Loa eruption), as noted in the file header.

## References (per NOAA's "Further reading" guidance)

- Keeling, C. D., Bacastow, R. B., Bainbridge, A. E., Ekdahl, C. A.,
  Guenther, P. R., Waterman, L. S. & Chin, J. F. S. (1976). Atmospheric carbon
  dioxide variations at Mauna Loa Observatory, Hawaii. *Tellus* 28(6), 538-551.
  https://doi.org/10.3402/tellusa.v28i6.11322
- Thoning, K. W., Tans, P. P. & Komhyr, W. D. (1989). Atmospheric carbon
  dioxide at Mauna Loa Observatory: 2. Analysis of the NOAA GMCC data,
  1974-1985. *J. Geophys. Res.* 94(D6), 8549-8565.
  https://doi.org/10.1029/JD094iD06p08549

## Processing (all in `figure.py`)

- Columns read: decimal date, monthly average, de-seasonalized. The
  de-seasonalized series is NOAA's own (Thoning et al. 1989 method); it is
  plotted as given, not recomputed.
- Average seasonal cycle (inset): for each calendar month, the mean of
  (monthly average - de-seasonalized) over the record. NOAA-era months that
  NOAA filled by interpolation (negative #days, from May 1974) are excluded
  (one month in this release); all Scripps-era months are kept, since that
  part of the file carries no #days. The 12 means are joined by a smooth
  periodic curve (December wrapped to January) for display only.
