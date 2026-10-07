"""Membrane action potentials from the Hodgkin-Huxley (1952) equations, at 6.3 C.

Hodgkin & Huxley, J. Physiol. 117:500-544 (1952). The conductances, reversal
potentials, rate constants and the 6.3 C temperature are the paper's (SOURCE.md).
Run from anywhere: `python simulate.py` writes data/hh_1952_6p3C.csv.

Sign convention. The paper measures V as displacement from rest, with
depolarisation negative. This script works with depolarisation positive,
v = -V, and writes the column `minus_V_mV` = -V, which is what the paper's
figure 12 panels plot on their "-V (mV)" axis.
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "hh_1952_6p3C.csv"

# Conductances (mS/cm^2), reversal potentials (mV from rest, depolarisation
# positive: E_Na = -V_Na, the paper's -115 mV), membrane capacitance (uF/cm^2).
G_NA, G_K, G_L = 120.0, 36.0, 0.3
E_NA, E_K, E_L = 115.0, -12.0, 10.6
C_M = 1.0

DT = 0.001         # ms, RK4 step (0.01 ms or finer; see NOTES.md)
SAMPLE_EVERY = 10  # store every 10th step, i.e. a 0.01 ms output grid
T_END = 10.0       # ms, the time span of the paper's panel
PULSE_START, PULSE_DUR = 0.0, 0.5   # ms; a square current pulse
STRENGTHS = [6.0, 12.0, 14.0, 25.0] # uA/cm^2; threshold for this pulse is 13.3


def ratio(x, a, b):
    """a * x / (exp(x / b) - 1), with the limit a * b at x = 0."""
    small = np.abs(x) < 1e-7
    safe = np.where(small, 1.0, x)
    return np.where(small, a * b, a * safe / np.expm1(safe / b))


def rates(v):
    """Rate constants (1/ms) at 6.3 C, v = depolarisation (mV).

    These are the 1952 forms written in V = -v, e.g. the paper's
    alpha_m = 0.1 (V + 25) / (exp((V + 25) / 10) - 1).
    """
    alpha_n = ratio(10.0 - v, 0.01, 10.0)
    beta_n = 0.125 * np.exp(-v / 80.0)
    alpha_m = ratio(25.0 - v, 0.1, 10.0)
    beta_m = 4.0 * np.exp(-v / 18.0)
    alpha_h = 0.07 * np.exp(-v / 20.0)
    beta_h = 1.0 / (np.exp((30.0 - v) / 10.0) + 1.0)
    return alpha_n, beta_n, alpha_m, beta_m, alpha_h, beta_h


def derivatives(state, i_stim):
    v, m, h, n = state
    alpha_n, beta_n, alpha_m, beta_m, alpha_h, beta_h = rates(v)
    i_na = G_NA * m**3 * h * (v - E_NA)
    i_k = G_K * n**4 * (v - E_K)
    i_l = G_L * (v - E_L)
    dv = (i_stim - i_na - i_k - i_l) / C_M
    return np.array([dv,
                     alpha_m * (1 - m) - beta_m * m,
                     alpha_h * (1 - h) - beta_h * h,
                     alpha_n * (1 - n) - beta_n * n])


def rest_state():
    """Steady state at rest (v = 0), gating variables at their resting values."""
    alpha_n, beta_n, alpha_m, beta_m, alpha_h, beta_h = rates(0.0)
    return np.array([0.0, alpha_m / (alpha_m + beta_m),
                     alpha_h / (alpha_h + beta_h), alpha_n / (alpha_n + beta_n)])


def stimulus(t, amplitude):
    on = (t >= PULSE_START) & (t < PULSE_START + PULSE_DUR)
    return np.where(on, amplitude, 0.0)


def simulate(amplitude, dt=DT, t_end=T_END):
    """Integrate with classical RK4. Returns time (ms) and depolarisation (mV)."""
    n = int(round(t_end / dt))
    t = np.arange(n + 1) * dt
    v = np.empty(n + 1)
    s = rest_state()
    v[0] = s[0]
    for k in range(n):
        i0 = stimulus(t[k], amplitude)
        i_half = stimulus(t[k] + 0.5 * dt, amplitude)
        i1 = stimulus(t[k] + dt, amplitude)
        k1 = derivatives(s, i0)
        k2 = derivatives(s + 0.5 * dt * k1, i_half)
        k3 = derivatives(s + 0.5 * dt * k2, i_half)
        k4 = derivatives(s + dt * k3, i1)
        s = s + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        v[k + 1] = s[0]
    return t, v


def main():
    columns = {}
    for amplitude in STRENGTHS:
        t, v = simulate(amplitude)
        columns[f"stim_{amplitude:g}uA_cm2"] = v[::SAMPLE_EVERY]   # -V, depolarisation positive
    header = "time_ms," + "minus_V_mV_" + ",minus_V_mV_".join(
        f"{a:g}uA_cm2" for a in STRENGTHS)
    t = t[::SAMPLE_EVERY]
    data = np.column_stack([t] + list(columns.values()))
    np.savetxt(OUT, data, delimiter=",", header=header, comments="",
               fmt=["%.2f"] + ["%.4f"] * len(STRENGTHS))
    print(f"wrote {OUT} ({len(t)} rows)")


if __name__ == "__main__":
    main()
