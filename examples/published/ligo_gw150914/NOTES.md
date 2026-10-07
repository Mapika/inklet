# Notes: LIGO GW150914, Figure 1

Output: `gallery/published/ligo_gw150914.{png,svg,pdf}`, 183 × 114 mm (double
column). `figure.py` is 78 lines. `figure.report()`: `inklet lint: clean`.

## Matches the original

* Layout: two columns (Hanford H1 left, Livingston L1 right) under the
  original's column titles "Hanford, Washington (H1)" and "Livingston,
  Louisiana (L1)", and three strain rows: observed, numerical relativity, residual.
* Data: the exact GWOSC Figure 1 time series (16384 Hz, 0.25–0.46 s,
  35–350 Hz band-passed), plotted without resampling.
* L1 observed panel overlays H1 observed **shifted by 6.9 ms and inverted**,
  built from the H1 file as the caption describes. L1 is drawn over H1, as
  in the original.
* Axes: time 0.25–0.46 s with ticks 0.30–0.45 shown only under the bottom row;
  one shared "Strain (10⁻²¹)" label on the left; ticks −1.0…1.0 on rows 1–2 and
  −0.5…0.5 on the residual row. One strain unit is the same height (11.5 mm)
  in every row, so the shorter residual row is on the same scale, as in the
  original.
* Keys in the lower-left corner of each panel, below the traces, in the
  original's order (L1 observed first, via `legend(names=[...])`, while L1 is
  still drawn over H1) and with the original's names ("H1 observed", "L1 observed", "H1 observed (shifted,
  inverted)", "Numerical relativity", "Residual"). Red for H1, blue for L1,
  light orange for the shifted H1, as in the original's colour coding.

## Differs, and why

* **No reconstruction bands in row 2.** The original shades 90% credible
  regions for the wavelet (BayesWave) and template reconstructions. They are
  not in the Figure 1 data release, so only the numerical-relativity curve is
  drawn and the key has one entry instead of three.
* **No time-frequency row.** Row 4 (Q-transform maps with a colour bar) is
  published only as PNG images, not as a grid, so it was left out, as allowed.
* Style: inklet `scientific.modern` (grey axes, light grid, sans-serif type,
  no closed frame, no inward ticks) instead of the original's boxed panels
  with ticks on all four sides. Tick labels use a true minus sign (U+2212),
  inklet's default.
* Y ranges: rows 1–2 span −1.55…1.45 and the residual row −1.0…0.6, slightly
  different from the original's, to leave room for the keys below the traces.
  Lint now reports a key plate that hides data (`KEY_COVERS_DATA`), and
  these ranges keep it clean (ISSUES-physics.md, issue 1).

## Verdict

Faithful for the three strain rows: same data, same panels, overlay, units
and scales. The figure has fewer elements than the original because the
reconstruction bands and the spectrograms are not available as data.
