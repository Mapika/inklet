# Hare and lynx: notes on fidelity

`figure.py`: 45 lines (about 28 of figure code). Output: single column,
89 x 62 mm plot, `gallery/published/hare_lynx.{png,svg,pdf}`.
`figure.report()`: `inklet lint: clean, 0 diagnostics`.

## Matches the original

- Content: the annual HBC pelt returns of snowshoe hare and Canada lynx,
  1845-1935, both series in thousands, 91 points each, from the same numbers
  as the astsa `Hare`/`Lynx` objects (checked: zero difference).
- Layout: time on x with ticks every 10 years from 1845 to 1935; numbers on y
  in thousands, with ticks every 20 from 0 to 160; hare as a solid line and
  lynx dashed; a key in the upper right (the classic figure has its key in the
  same place).
- Shape: the reference peaks are where they should be. Hare about 152 thousand
  in 1863 (data 152.65); lynx about 70 thousand in 1866-67 (data 70.77 and
  72.77); hare near 135 thousand in 1885-86 (data 134.85 and 134.86); lynx
  peak 79.35 in 1886; hare about 100 thousand in 1875 (data 101.25); hare
  about 90 thousand in 1933 (data 89.76). 1845 starts at hare 19.58 and lynx
  30.09.

## Differs, and why

- Colour: the classic is black and grey. The brief asked for distinct colours,
  so hare is Okabe-Ito blue and lynx vermilion; the lynx keeps its dashed
  line, so the two stay apart in greyscale.
- Y axis starts at 0. The reference's lowest tick sits a little above 0. The
  lowest values are 1.80 (hare, 1928) and 3.19 (lynx, 1919), so starting at 0
  shows the troughs honestly.
- Axis titles say what is counted: "Pelts purchased (thousands)" and "Year",
  rather than "Number in thousands" and "Time in years". No title, as in the
  reference.
- The data are the Whitman College copy of the Odum series, which agrees with
  astsa and tsibbledata. The reference is a redrawn version. Its 1935 end
  points were read by eye, roughly: its hare falls to about 20-25 thousand and
  its lynx is about 40-50 thousand at 1935. The data give 15.76 and 35.40. The
  reference is a small redrawn image, so this is probably reading error, but I
  could not check it against MacLulich (1937) itself.
- Lines are drawn through annual points (no smoothing); the reference joins
  them the same way.

## Checked and found no bug

- The `dash="dashed"` lynx line and two-colour legend render without
  overlap, and `figure.report()` is clean. No inklet issue was found in this
  figure.
