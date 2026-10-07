# Keeling curve: notes on fidelity

`figure.py`: 68 lines (about 43 of figure code). Output: single column,
89 x 81 mm, `gallery/published/keeling_curve.{png,svg,pdf}`. `figure.report()`:
`inklet lint: clean, 0 diagnostics`.

## Matches the original

- Content of the NOAA GML / Scripps full-record figure: the monthly mean
  (red, showing the seasonal cycle) and NOAA's deseasonalized series (black),
  March 1958 to August 2026, from the same file NOAA plots.
- Axes: year on x with ticks every 10 years from 1960 to 2030; "CO2 mole
  fraction (ppm)" on y with 20 ppm ticks from 320 to 440.
- Title "Atmospheric CO2 at Mauna Loa Observatory" with subscript 2, and the
  two-line institutional credit (Scripps Institution of Oceanography / NOAA
  Global Monitoring Laboratory) as on the NOAA figure.
- Inset of the average seasonal cycle in the upper left, as in the widely
  reproduced version of the figure: monthly departures from the deseasonalized
  value as points joined by a smooth curve, with a zero line. Peak +3.1 ppm in
  May, trough -3.2 ppm in September/October, matching the reference.

## Differs, and why

- The current NOAA image has no inset (the brief asked for one); the inset
  follows the Wikimedia/Scripps-style figure built from the same data. Its
  values are computed here from NOAA's own deseasonalized column rather than
  from a separate harmonic fit, so they can differ from other published
  insets by about 0.1 ppm.
- inklet look: open axes (no box, no inward ticks), lighter grey furniture,
  a legend in the lower right naming the two series (NOAA's figure explains
  them only in the page text), "Seasonally adjusted" for the black line.
- The NOAA logos and the date stamp are left out; the data range (1958-2026)
  is in the title instead.
- The inset month axis shows Jan/Apr/Jul/Oct. Every second month (as in the
  reference) does not fit at this size: inklet thins the explicit ticks and
  only says so in a Python warning (see ISSUES-earth-life.md #3).
- Negative inset ticks get a true minus sign (U+2212) and the credit text its
  grey through `text(..., color=)` with no extra code; both needed
  workarounds before (ISSUES-earth-life.md #1, #2, now fixed).
