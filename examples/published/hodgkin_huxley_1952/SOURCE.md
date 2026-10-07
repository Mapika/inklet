# Source: Hodgkin & Huxley (1952), membrane action potentials at 6.3 C

**Paper.** A. L. Hodgkin and A. F. Huxley, "A quantitative description of
membrane current and its application to conduction and excitation in nerve",
*Journal of Physiology* **117**, 500-544 (1952).
DOI: [10.1113/jphysiol.1952.sp004764](https://doi.org/10.1113/jphysiol.1952.sp004764);
PubMed 12991237.

**Figure.** Figure 12 of the paper is the target: calculated membrane action
potentials at 6.3 C for several stimulus strengths. **Not verified.** The
paper's full text and figure list were not reachable from this machine (PubMed
Central and the publisher's pages returned a bot challenge; Europe PMC holds
only the citation). The Figure 12 caption, its stimulus protocol and its
temperature are therefore taken from the task, not from the paper.

**Verified original.** One calculated action potential from the same paper,
panel B, is on Wikimedia Commons as
<https://commons.wikimedia.org/wiki/File:Spike_HH.png> (file from "The
Physiological Society, volume 117, 1952", public domain per the file page). It
shows -V (mV) against time, 0 to 10 ms, with a peak near 90 mV at about 0.8 ms
and a trough near -10 mV at about 2.7 ms. It is used as a shape check only
(NOTES.md), not as data.

**Licence.** The copyright status of the paper was not checked. No image from it
is redistributed here: the traces are computed from the equations, and the
Commons panel is used only for comparison. The CellML model below was
consulted for the constants and rate constants; its licence was not checked.

**Retrieved.** 2026-10-07.

## Model and constants

Standard Hodgkin-Huxley equations, as in the paper (the paper's sign convention
is "V is displacement from rest, depolarisation negative").

* Membrane: C dV/dt = I_stim - I_Na - I_K - I_L, with C = 1 uF/cm^2.
* Conductances: g_Na = 120, g_K = 36, g_L = 0.3 mS/cm^2.
* Reversal potentials (paper convention, displacement from rest):
  E_Na = -115 mV, E_K = +12 mV, E_L = -10.613 mV. In `simulate.py` the
  depolarisation-positive form is used: 115, -12, +10.613 mV.
* Gating: dm/dt, dh/dt, dn/dt with the paper's rate constants at 6.3 C
  (temperature factor 3^((T-6.3)/10) = 1, so no scaling). The rate constants
  in depolarisation-positive form (v = -V):

  alpha_n = 0.01 (10 - v) / (exp((10 - v)/10) - 1), beta_n = 0.125 exp(-v/80)
  alpha_m = 0.1 (25 - v) / (exp((25 - v)/10) - 1),  beta_m = 4 exp(-v/18)
  alpha_h = 0.07 exp(-v/20),                        beta_h = 1 / (exp((30 - v)/10) + 1)

* Resting state: m = 0.0529, h = 0.5961, n = 0.3177.

**Cross-check.** The Physiome Model Repository's CellML version of the model,
"Hodgkin, Huxley, 1952" ("Original Model + Stimulus"),
<https://models.physiomeproject.org/exposure/5d116522c3b43ccaeb87a1ed10139016/hodgkin_huxley_1952.cellml/source_text>
(retrieved 2026-10-07), has the same conductances, reversal potentials and
rate constants for alpha_n, alpha_m, beta_m, alpha_h and beta_h, with V
absolute (rest -75 mV). Its beta_n is written 0.125 exp((V+75)/80), which has
the opposite sign to the form above. The form above is used because beta_n
must fall on depolarisation (it is the rate at which n closes). The
discrepancy is recorded in NOTES.md.

## Stimulus

A square current pulse of 0.5 ms, starting at t = 0, in uA/cm^2. The duration
is an assumption (it is the paper's protocol for Figure 12 that is not
verified). The strengths are 6, 12, 14 and 25 uA/cm^2. The threshold for a
0.5 ms pulse is 13.28 uA/cm^2 (bisection on whether the peak exceeds 50 mV at
dt = 0.001 ms). 6 and 12 are sub-threshold, 14 and 25 supra-threshold.

## Files in `data/`

`hh_1952_6p3C.csv`, written by `simulate.py`. Columns:

| Column | Meaning |
|---|---|
| `time_ms` | time from pulse onset, 0 to 10 ms, every 0.01 ms (1001 rows) |
| `minus_V_mV_<s>uA_cm2` | -V in mV for stimulus strength s: depolarisation positive, as the paper's "-V (mV)" axis |

Integration: classical RK4 with dt = 0.001 ms; every tenth step is written.
Convergence (dt = 0.001 ms against 0.0005 ms): the largest difference is 0.64 mV,
for the 14 uA/cm^2 trace, just above threshold, where the upstroke timing is
most sensitive; for 25 uA/cm^2 it is 0.06 mV (NOTES.md).

SHA-256:

```
d74c76e3ab5b9e6fb80c700da157987b25d542b1cd008aead947eaba1ee69ea3  data/hh_1952_6p3C.csv
a2edac544e6662faa340f99a702bc2e407c1438a0cba16e66ee285af98d92ba7  simulate.py
```

Regenerate with `python simulate.py` (numpy only).
