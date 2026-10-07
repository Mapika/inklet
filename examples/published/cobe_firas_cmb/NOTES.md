# COBE/FIRAS CMB spectrum: notes on fidelity

`figure.py`: 71 lines (about 45 of figure code). Output: single column,
89 x 66 mm, `gallery/published/cobe_firas_cmb.{png,svg,pdf}`. `figure.report()`:
`inklet lint: clean, 0 diagnostics`.

## Matches the original

- The data: the 40 FIRAS monopole points from NASA LAMBDA
  (`firas_monopole_spec_v1.txt`, Table 4 of Fixsen et al. 1996), from 2.27 to
  21.33 cm^-1, plotted as the file gives them.
- The blackbody: a 2.725 K Planck curve computed from the SI constants, from
  2 to 22 cm^-1. It sits on the data within 0.01 MJy/sr, and the script asserts
  that the file's monopole equals blackbody plus residual.
- Axes as in the reference (gnuplot "Cosmic microwave background spectrum"
  plot from Wikimedia Commons, Cmbr.svg): intensity in MJy/sr from 0 to 400
  against frequency in cm^-1 from 2 to 22, ticks every 50 MJy/sr and every
  2 cm^-1.
- Data points as red crosses, the blackbody as a blue line, and a key naming
  both.
- Error bars drawn at 400 x 1 sigma, the convention that makes the small errors
  visible. The note "Error bars x400" is on the figure.

## Differs, and why

- Error bars at the high-frequency end are not like the reference. The table's
  1-sigma values grow from about 5 kJy/sr at 2 cm^-1 to 282 kJy/sr at 21.33 cm^-1.
  At x400 that is about 113 MJy/sr, so the bars run past the bottom of the axis
  from about 17 cm^-1 and are clipped there (`clip=True`). The reference draws
  much shorter bars at the same frequencies. I could not reconcile this with
  column 4 without the Fixsen et al. (1996) table, which I did not read, so the
  file's values are used as given. Treat the high-frequency bars as the
  tabulated uncertainty x400, not as a checked match of the reference.
- Style: inklet's `scientific.modern` look (grey axes, no box), colour-led
  marks, and a title on the figure. The reference is gnuplot's default.
- Legend: the key sits in the top right (inside the empty part of the plot),
  naming the blackbody "Black body, T = 2.725 K" and the points "COBE/FIRAS
  data". The reference's key reads "COBE data" and "Black body spectrum".
- Axis labels "Intensity / (MJy sr^{-1})" and "Frequency / cm^{-1}"; the
  reference's are "Intensity [MJy/sr]" and "Frequency [1/cm]".
- The FIRAS 1996 paper's own figures were not checked; the comparison is with
  the Wikimedia plot only.

## Verdict

Faithful in content (data, blackbody, units, error-bar convention). The
high-frequency error bars are the one place it departs visibly from the
reference, and the cause is the uncertainty column (see above), not the
rendering.
