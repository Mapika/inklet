# Notes: Hodgkin & Huxley (1952), membrane action potentials at 6.3 C

Output: `gallery/published/hodgkin_huxley_1952.{png,svg,pdf}`, 89 mm wide
(single column). `figure.py` is 54 lines; `simulate.py` 114 lines.
`figure.report()`: `inklet lint: clean, 0 diagnostics`.

## Verdict

**Not verified against Figure 12.** The paper's figure and caption could not be
read from this machine, so this is the 6.3 C model response that the task
describes, with my choice of stimulus duration and strengths. It is a faithful
computation of the paper's model and a plausible recreation of the figure's
content. It is not a verified copy of the figure.

## Matches the model and the paper's conventions

* The equations, conductances (120, 36, 0.3 mS/cm^2), reversal potentials and
  rate constants are the paper's, at 6.3 C with no temperature scaling. They
  agree with the CellML model's constants, except beta_n (see below).
* Sign convention: the figure's y axis is "-V (mV)", as in the paper's panel,
  so depolarisation is up.
* The traces, from the same equations, show the paper's behaviour: a
  sub-threshold response that rises and decays without firing (6 and
  12 uA/cm^2, peaks 2.7 and 5.4 mV); a just-supra-threshold response (14 uA/cm^2)
  that fires late, peaking at 3.9 ms, after a long slow upstroke; a clear action
  potential (25 uA/cm^2) peaking at 1.7 ms at about 105 mV; and the undershoot
  after each spike (about -11 mV at 4.6 to 6.7 ms).
* Threshold for the 0.5 ms pulse is 13.28 uA/cm^2 (bisection).

## Differs, and why

* **Figure 12 not verified.** The stimulus strengths (6, 12, 14, 25 uA/cm^2),
  the 0.5 ms pulse duration and the 0 ms onset are assumptions. The original
  panel shows the response to one unstated stimulus (see the next point).
  Strengths were chosen so that the figure has two sub-threshold and two
  supra-threshold responses, as the task asks.
* **Timescale against the one verified panel.** The Commons panel B (the
  "Spike" image from the same paper) peaks at about 0.8 ms with a trough near
  -10 mV at about 2.7 ms. The 6.3 C model peaks at 1.7 to 3.9 ms, so it is about
  twice as slow. In a quick check (not in the figure), the model at 12 C with a
  40 uA/cm^2 pulse peaks at 0.9 ms and bottoms at 2.66 ms, close to panel B,
  while at 18.5 C it peaks at 0.7 ms. So panel B looks like a warmer run, but
  its temperature is not stated in the image. The figure keeps the task's 6.3 C.
* **beta_n sign in the CellML model.** The Physiome CellML version has
  beta_n = 0.125 exp((V+75)/80) with V absolute. That increases the rate at
  which n closes on depolarisation, which is physically wrong (beta_n must fall
  on depolarisation). The figure uses 0.125 exp(-v/80), the form in the paper's
  convention, as in the textbook (exp(-(V+65)/80) in absolute units). Both
  forms fire, and the CellML sign changes the late trough (-10.0 mV at 6.1 ms
  against -11.2 mV at 4.6 ms for 25 uA/cm^2), so this choice matters for the
  shape. Recorded here so the difference is visible.
* **Labels.** The original has no key. Traces are labelled with their stimulus
  strength in place, with the unit in the title, as the task asked ("direct
  labels"). "6" and "12" sit below their bumps because the bumps are close to
  the baseline. The four strengths are the chosen set, not the paper's labels.
* **Style.** inklet `scientific.modern` (grey axes, light grid, no frame). The
  original panel has a ticked axis with a "B" panel letter, which is omitted.

## Numerics

* RK4, dt = 0.001 ms, 0 to 10 ms, stored every 0.01 ms (1001 rows).
* dt = 0.01 ms was too coarse near threshold: the 14 uA/cm^2 upstroke differed
  by 9.9 mV from dt = 0.0025 ms. At dt = 0.001 ms the largest difference from
  dt = 0.0005 ms is 0.64 mV (14 uA/cm^2) and 0.06 mV (25 uA/cm^2); the peak
  times agree to 0.001 ms.
* A sign error in my first rate constants (depolarisation-negative form applied
  to depolarisation-positive v) stopped the model firing. Fixed before any
  output was written, and the output above is from the corrected rates.
