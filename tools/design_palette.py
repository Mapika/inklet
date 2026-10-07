"""Search for a categorical palette by simulated annealing in OKLCH.

    python tools/design_palette.py [--seed N] [--steps N]

Each colour lives in a lightness/chroma box suited to lines and markers on
white (no pale or neon entries). The score is the worst ratio, over the first
3, 4, 6 and all 8 colours, of the smallest pairwise CIEDE2000 distance to its
target -- under normal vision and under deuteranopia, protanopia and
tritanopia (Machado and Viénot, whichever is worse) -- so the colours a short
series uses are the most separable. Prints the palette and its distances.

This is how the `inklet-vivid` palette was chosen; rerun it to check.
"""
from __future__ import annotations

import argparse
import math
import random

from inklet.themes.color import delta_e_2000, from_oklch, in_gamut_oklab, simulate_cvd, to_oklch

#: Lightness and chroma boxes: mid tones that read as a line on paper.
L_RANGE, C_RANGE = (0.46, 0.70), (0.10, 0.165)
#: The lead colour is a calm, deep blue -- a lone series is drawn in it, so it
#: must hold up as a thin line; the others may take any hue.
LEAD_HUE, LEAD_L = (240.0, 262.0), (0.50, 0.60)
#: Distance targets (normal, worst CVD) for each prefix length.
TARGETS = {3: (34.0, 16.0), 4: (30.0, 13.0), 6: (24.0, 9.0), 8: (20.0, 7.0)}
CVD = ('deuteranopia', 'protanopia', 'tritanopia')


#: Yellows and yellow-greens turn olive and muddy when dark or greyish; in
#: this hue range a colour must be light and saturated enough to read as gold.
MUDDY_HUES, GOLD_FLOOR = (70.0, 125.0), (0.62, 0.12)


def _hex(lch):
    if MUDDY_HUES[0] <= lch[2] % 360 <= MUDDY_HUES[1] and (
            lch[0] < GOLD_FLOOR[0] or lch[1] < GOLD_FLOOR[1]):
        return None
    lab = (lch[0], lch[1] * math.cos(math.radians(lch[2])), lch[1] * math.sin(math.radians(lch[2])))
    return from_oklch(lch) if in_gamut_oklab(lab) else None


def _views(colors):
    """Each colour as seen by normal vision and each dichromacy, both methods."""
    views = [list(colors)]
    for kind in CVD:
        for method in ('machado', 'vienot'):
            views.append([simulate_cvd(c, kind, method=method) for c in colors])
    return views


def distances(colors):
    """(smallest normal ΔE00, smallest ΔE00 under any dichromacy) over all pairs."""
    views = _views(colors)
    def smallest(view):
        return min(delta_e_2000(a, b) for k, a in enumerate(view) for b in view[k + 1:])
    return smallest(views[0]), min(smallest(v) for v in views[1:])


def score(colors):
    worst = math.inf
    for count, (normal, cvd) in TARGETS.items():
        n, c = distances(colors[:count])
        worst = min(worst, n / normal, c / cvd)
    return worst


def _random_lch(rng, lead=False):
    hue = rng.uniform(*LEAD_HUE) if lead else rng.uniform(0, 360)
    return [rng.uniform(*(LEAD_L if lead else L_RANGE)), rng.uniform(*C_RANGE), hue]


def _clamp(lch, lead):
    lch[0] = min(max(lch[0], L_RANGE[0]), L_RANGE[1])
    lch[1] = min(max(lch[1], C_RANGE[0]), C_RANGE[1])
    lch[2] %= 360
    if lead:
        lch[0] = min(max(lch[0], LEAD_L[0]), LEAD_L[1])
        lch[2] = min(max(lch[2], LEAD_HUE[0]), LEAD_HUE[1])
    return lch


def search(seed=0, steps=6000):
    rng = random.Random(seed)
    state = []
    while len(state) < 8:
        lch = _random_lch(rng, lead=not state)
        if _hex(lch):
            state.append(lch)
    current = score([_hex(s) for s in state])
    best, best_state = current, [s[:] for s in state]
    for step in range(steps):
        temperature = 0.08 * (1 - step / steps) + 1e-4
        k = rng.randrange(8)
        trial = [s[:] for s in state]
        if rng.random() < 0.15:
            j = rng.randrange(1, 8)
            if k:
                trial[k], trial[j] = trial[j], trial[k]
        else:
            trial[k] = _clamp([trial[k][0] + rng.gauss(0, 0.03), trial[k][1] + rng.gauss(0, 0.015),
                               trial[k][2] + rng.gauss(0, 18)], lead=k == 0)
        colors = [_hex(s) for s in trial]
        if None in colors:
            continue
        value = score(colors)
        if value > current or rng.random() < math.exp((value - current) / temperature):
            state, current = trial, value
            if value > best:
                best, best_state = value, [s[:] for s in trial]
    return [_hex(s) for s in best_state], best


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--steps', type=int, default=6000)
    args = parser.parse_args()
    colors, value = search(args.seed, args.steps)
    print('palette:', ', '.join(colors), f'score {value:.3f}')
    for count in TARGETS:
        n, c = distances(colors[:count])
        print(f'  first {count}: normal {n:.1f}, worst CVD {c:.1f}')
    for color in colors:
        print('  ', color, 'OKLCH', tuple(round(v, 3) for v in to_oklch(color)))


if __name__ == '__main__':
    main()
