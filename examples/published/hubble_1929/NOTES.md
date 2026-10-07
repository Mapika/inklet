# Notes: Hubble (1929), Figure 1

Output: `gallery/published/hubble_1929.{png,svg,pdf}`, 89 × 78 mm (single
column). `figure.py` is 80 lines. `figure.report()`: `inklet lint: clean`.

## Matches the original

* **All 24 black discs** (Table 1 nebulae) at their solar-motion-corrected
  velocities, computed from the table and Hubble's own solution for the
  nebulae individually (X = −65, Y = +226, Z = −195 km/s). Overlaid on the
  scanned original, every computed point falls on its printed disc (SOURCE.md
  gives the checks).
* **9 open circles** (group means): 4 computed from identifiable groups, 5
  digitized from the scan, since the paper does not list group membership.
  The N.G.C. 6822 circle sits under its own disc, as it does in the original.
* **Two lines through the origin**: v = 465 r (individual nebulae) and
  v = 513 r (groups), ending where the original's do (r ≈ 2.22 and 2.14).
* **Cross** at 745 km/s, 1.4 × 10⁶ parsecs: the mean of the 22 Table 2
  nebulae.
* Axis ranges as printed: distance −⅓ to 2⅓ × 10⁶ pc, velocity −333 to
  +1333 km/s, with grid lines only at 0, 1, 2 × 10⁶ pc and 0, 500, 1000 km/s,
  the same tick positions as in the original.

## Differs, and why

* **Line styles follow the caption, not the drawing.** The caption pairs the
  black discs with the **full** line (individual solution, K = 465) and the
  circles with the **broken** line (group solution, K = 513). Measured on the
  scan, the printed full line has slope ≈ 513 and the broken line ≈ 463, so
  the drafted styles are swapped relative to the caption. The recreation
  keeps the caption's pairing, which also matches the K values in the text,
  and colour-codes each line with its markers (ink: nebulae and their fit;
  ochre: groups and their fit). The line lengths follow the drawing.
* **A key** replaces the caption's verbal description, with K values in it.
  The original has no key. It is the automatic key (`legend(names=[...])`
  for the row order); the hollow group-mean marker gets a correct ring
  swatch from `scatter(..., hollow=True)`. The marker rows' labels sit about
  2 mm left of the line rows' labels, because inklet does not give a key's
  swatches a common width (ISSUES-physics.md, 6).
* The red cross is drawn with `stroke=` as well as `color=`: a `plus`
  marker ignores `color=` in the plot, though its key swatch takes it
  (ISSUES-physics.md, 5).
* The broken line uses inklet's `dash="dashed"` (1.6 mm on, 0.8 mm off).
* Axis titles are "Distance (10⁶ parsecs)" and "Velocity (km s⁻¹)"; the
  original writes "DISTANCE", "VELOCITY", "10⁶ PARSECS", "+1000 KM" on the
  axes. The original's velocity unit is printed as "KM"; it is km/s.
* The cross is red to separate it from the circle under it; the original is
  black. Style is inklet `scientific.modern`, with no box frame.
* Group means: 5 of 9 are digitized (±0.01 Mpc, ±10 km/s), not computed.

## Verdict

Very faithful: the data points are recomputed from the paper's table and its
own solar-motion solution, not traced, and they reproduce the printed figure.
The one deliberate departure is the solid/dashed assignment, documented above.
