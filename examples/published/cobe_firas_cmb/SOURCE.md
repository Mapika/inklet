# Source: COBE/FIRAS spectrum of the cosmic microwave background

## Figure being recreated

Intensity of the cosmic microwave background (CMB) against frequency, measured
by the Far-Infrared Absolute Spectrophotometer (FIRAS) on NASA's COBE satellite,
with the 2.725 K blackbody curve. The reference is the widely used FIRAS monopole
plot (Wikimedia Commons, "Cmbr.svg", public domain, by Quantum Doughnut,
drawn in gnuplot from the LAMBDA monopole data): intensity in MJy/sr from 0 to
400 against frequency in cm^-1 from 2 to 22, with data points carrying error
bars and the blackbody curve. The image was viewed only (rendered to PNG) and is
not stored in this repository. The "error bars x400" convention is the one of
the FIRAS papers (Fixsen et al. 1996; Mather et al. 1994).

## References

- Mather, J. C., Cheng, E. S., Cottingham, D. A., Eplee, R. E., Fixsen, D. J.,
  Hewagama, T., Isaacman, R. B., Jensen, K. A., Meyer, S. S., Noerdlinger, P. D.,
  Read, S. M., Rosen, L. P., Shafer, R. A., Wright, E. L., et al. (1994).
  Measurement of the cosmic microwave background spectrum by the COBE FIRAS
  instrument. *The Astrophysical Journal* 420, 439.
  https://doi.org/10.1086/173574
- Fixsen, D. J., Cheng, E. S., Gales, J. M., Mather, J. C., Shafer, R. A. &
  Wright, E. L. (1996). The Cosmic Microwave Background Spectrum from the Full
  COBE FIRAS Data Set. *The Astrophysical Journal* 473, 576-587.
  https://doi.org/10.1086/178173
- Fixsen, D. J. & Mather, J. C. (2002). *The Astrophysical Journal* 581, 817
  (the updated calibration; cited in the data file header).

Both DOIs were checked against the Crossref record on 2026-10-07.

## Data

- File: `data/firas_monopole_spec_v1.txt`, an unmodified copy of
  https://lambda.gsfc.nasa.gov/data/cobe/firas/monopole_spec/firas_monopole_spec_v1.txt
  (NASA LAMBDA, "COBE FIRAS CMB Monopole Spectrum", revision v1, May 2005; the
  product page is https://lambda.gsfc.nasa.gov/product/cobe/firas_monopole_get.cfm).
  Its header names Table 4 of Fixsen et al. (1996) as the source. 61 lines,
  2.4 KB, 40 frequencies from 2.27 to 21.33 cm^-1.
- Columns (from the header): (1) frequency, cm^-1; (2) monopole spectrum,
  MJy/sr, equal to the 2.725 K blackbody plus the residual; (3) residual,
  kJy/sr; (4) 1-sigma uncertainty, kJy/sr; (5) modelled Galaxy spectrum at the
  Galactic poles, kJy/sr (not used).
- Retrieved: 2026-10-07.
- Licence: NASA data; US Government work, no copyright restriction on use
  (NASA LAMBDA data policy). Credit the COBE/FIRAS team and LAMBDA as above.

## Processing (all in `figure.py`)

- Points: column 1 (x) and column 2 (y), unmodified.
- Error bars: 400 x column 4, converted from kJy/sr to MJy/sr (divide by 1000),
  drawn symmetric. The factor is written on the figure ("Error bars x400") and
  the bars are clipped at the axes.
- Blackbody curve: Planck's law in SI, B_nu = 2 h nu^3 / c^2 / (exp(h nu / k T) - 1),
  with h = 6.62607015e-34 J s, c = 299792458 m/s, k = 1.380649e-23 J/K, T = 2.725 K,
  nu = 100 c x (wavenumber in cm^-1), and 1 MJy/sr = 1e-20 W m^-2 Hz^-1 sr^-1.
  Plotted from 2 to 22 cm^-1.
- Check (in the script): column 2 minus the blackbody minus column 3 is under
  0.01 MJy/sr everywhere (the assert allows 0.02). This confirms the units, the
  blackbody and the sign convention. The residual is smooth, not noise, so it
  comes from constant precision in the file's own calculation.
