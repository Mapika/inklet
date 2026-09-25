"""Regression lines with confidence bands, LOWESS, and residuals.

`linear_fit` is ordinary least squares of y on x with the textbook
confidence band for the mean response,

    y(x) +/- t(1 - a/2, n - 2) * s * sqrt(1/n + (x - mean(x))**2 / Sxx),

and the prediction interval for a new observation, which adds 1 under the
square root. `lowess` is Cleveland's locally weighted regression as R's
`lowess()` computes it (tricube weights over the nearest `frac` of the
points, a local line, and `iterations` robustness passes with bisquare
weights), so its output can be checked against R. Both draw nothing;
`Panel.regression` and `Panel.residuals` draw with them.

Student's t quantile is computed here from the regularized incomplete beta
function (a continued fraction), so the core needs no SciPy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import DiagramError

__all__ = ["LinearFit", "linear_fit", "lowess", "t_cdf", "t_quantile"]


# -- Student's t -------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """The regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """The cumulative distribution function of Student's t with `df`
    degrees of freedom."""
    if df <= 0:
        raise DiagramError(f"degrees of freedom must be positive, got {df!r}")
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t > 0 else tail


def t_quantile(p: float, df: float) -> float:
    """The `p` quantile of Student's t with `df` degrees of freedom."""
    if not 0.0 < p < 1.0:
        raise DiagramError(f"a quantile probability is between 0 and 1, got {p!r}")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_quantile(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-14 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


# -- least squares -------------------------------------------------------------


@dataclass(frozen=True)
class LinearFit:
    """An ordinary least-squares line `y = intercept + slope * x`.

    `r2` is the coefficient of determination, `sigma` the residual standard
    error on `n - 2` degrees of freedom, `slope_se` and `intercept_se` the
    standard errors, and `p` the two-sided p-value of the slope against 0.
    """

    slope: float
    intercept: float
    r2: float
    sigma: float
    slope_se: float
    intercept_se: float
    p: float
    n: int
    x_mean: float
    sxx: float

    def predict(self, x: float) -> float:
        """The fitted value at `x`."""
        return self.intercept + self.slope * x

    def band(self, x: float, confidence: float = 0.95, *,
             prediction: bool = False) -> tuple[float, float]:
        """`(low, high)` of the confidence band for the mean response at `x`,
        or of the prediction interval for one new observation."""
        if not 0.0 < confidence < 1.0:
            raise DiagramError(f"confidence is between 0 and 1, got {confidence!r}")
        if self.n < 3:
            raise DiagramError("a confidence band needs at least three points")
        t = t_quantile(0.5 + confidence / 2.0, self.n - 2)
        extra = 1.0 if prediction else 0.0
        half = t * self.sigma * math.sqrt(
            extra + 1.0 / self.n + (x - self.x_mean) ** 2 / self.sxx)
        y = self.predict(x)
        return y - half, y + half

    def residuals(self, points: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
        """`(x, y - fitted)` for each point."""
        return [(float(p[0]), float(p[1]) - self.predict(float(p[0])))
                for p in points]


def _pairs(points) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for p in points:
        if p[0] is None or p[1] is None:
            continue
        x, y = float(p[0]), float(p[1])
        if math.isfinite(x) and math.isfinite(y):
            xs.append(x)
            ys.append(y)
    return xs, ys


def linear_fit(points: Sequence[Sequence[float]]) -> LinearFit:
    """Least squares of y on x over `(x, y)` points; missing values skipped."""
    xs, ys = _pairs(points)
    n = len(xs)
    if n < 2:
        raise DiagramError("a linear fit needs at least two points")
    mx, my = math.fsum(xs) / n, math.fsum(ys) / n
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        raise DiagramError("a linear fit needs at least two distinct x values")
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = math.fsum((y - my) ** 2 for y in ys)
    slope = sxy / sxx
    intercept = my - slope * mx
    sse = math.fsum((y - intercept - slope * x) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - sse / syy if syy > 0 else 1.0
    if n > 2:
        sigma = math.sqrt(sse / (n - 2))
        slope_se = sigma / math.sqrt(sxx)
        intercept_se = sigma * math.sqrt(1.0 / n + mx * mx / sxx)
        if slope_se > 0:
            t = slope / slope_se
            # Both tails directly, not 1 - cdf, which cancels for small p.
            p = _betainc((n - 2) / 2.0, 0.5, (n - 2) / (n - 2 + t * t))
        else:
            p = 0.0
    else:
        sigma = slope_se = intercept_se = math.nan
        p = math.nan
    return LinearFit(slope=slope, intercept=intercept, r2=r2, sigma=sigma,
                     slope_se=slope_se, intercept_se=intercept_se, p=p, n=n,
                     x_mean=mx, sxx=sxx)


# -- LOWESS ----------------------------------------------------------------------


def lowess(points: Sequence[Sequence[float]], *, frac: float = 2.0 / 3.0,
           iterations: int = 3, delta: float | None = None
           ) -> list[tuple[float, float]]:
    """Cleveland's LOWESS smoother, computed as R's `lowess()` does.

    Returns `(x, smoothed y)` for every point, sorted by x (ties keep input
    order). `frac` is the share of the points in each local fit,
    `iterations` the number of robustness passes, and `delta` the distance
    within which points are interpolated instead of fitted (default: 1% of
    the x range, as in R).
    """
    xs, ys = _pairs(points)
    n = len(xs)
    if n < 2:
        raise DiagramError("lowess needs at least two points")
    if not 0.0 < frac <= 1.0:
        raise DiagramError(f"lowess frac is in (0, 1], got {frac!r}")
    if iterations < 0:
        raise DiagramError(f"lowess iterations cannot be negative, got {iterations!r}")
    order = sorted(range(n), key=lambda k: (xs[k], k))
    x = [xs[k] for k in order]
    y = [ys[k] for k in order]
    if delta is None:
        delta = 0.01 * (x[-1] - x[0])
    fitted = _clowess(x, y, frac, iterations, delta)
    return list(zip(x, fitted))


def _lowest(x, y, n, xs, nleft, nright, w, userw, rw):
    """One local fit at `xs` over the window; `None` when it has no weight."""
    rng = x[n - 1] - x[0]
    h = max(xs - x[nleft], x[nright] - xs)
    h9, h1 = 0.999 * h, 0.001 * h
    a = 0.0
    j = nleft
    while j < n:
        w[j] = 0.0
        r = abs(x[j] - xs)
        if r <= h9:
            if r <= h1:
                w[j] = 1.0
            else:
                w[j] = (1.0 - (r / h) ** 3) ** 3
            if userw:
                w[j] *= rw[j]
            a += w[j]
        elif x[j] > xs:
            break
        j += 1
    nrt = j - 1
    if a <= 0.0:
        return None
    for j in range(nleft, nrt + 1):
        w[j] /= a
    if h > 0.0:
        a = sum(w[j] * x[j] for j in range(nleft, nrt + 1))
        b = xs - a
        c = sum(w[j] * (x[j] - a) ** 2 for j in range(nleft, nrt + 1))
        if math.sqrt(c) > 0.001 * rng:
            b /= c
            for j in range(nleft, nrt + 1):
                w[j] *= b * (x[j] - a) + 1.0
    return sum(w[j] * y[j] for j in range(nleft, nrt + 1))


def _clowess(x, y, f, nsteps, delta):
    n = len(x)
    ys = [0.0] * n
    if n < 2:
        return list(y)
    ns = max(2, min(n, int(f * n + 1e-7)))
    rw = [1.0] * n
    w = [0.0] * n
    res = [0.0] * n
    for iteration in range(1, nsteps + 2):
        nleft, nright, last, i = 0, ns - 1, -1, 0
        while True:
            if nright < n - 1:
                d1 = x[i] - x[nleft]
                d2 = x[nright + 1] - x[i]
                if d1 > d2:
                    nleft += 1
                    nright += 1
                    continue
            fit = _lowest(x, y, n, x[i], nleft, nright, w, iteration > 1, rw)
            ys[i] = y[i] if fit is None else fit
            if last < i - 1:
                denom = x[i] - x[last]
                for j in range(last + 1, i):
                    alpha = (x[j] - x[last]) / denom
                    ys[j] = alpha * ys[i] + (1.0 - alpha) * ys[last]
            last = i
            cut = x[last] + delta
            i = last + 1
            while i < n:
                if x[i] > cut:
                    break
                if x[i] == x[last]:
                    ys[i] = ys[last]
                    last = i
                i += 1
            i = max(last + 1, i - 1)
            if last >= n - 1:
                break
        for k in range(n):
            res[k] = y[k] - ys[k]
        sc = sum(abs(r) for r in res) / n
        if iteration > nsteps:
            break
        ordered = sorted(abs(r) for r in res)
        m1 = n // 2
        if n % 2 == 0:
            m2 = n - m1 - 1
            cmad = 3.0 * (ordered[m1] + ordered[m2])
        else:
            cmad = 6.0 * ordered[m1]
        if cmad < 1e-7 * sc:
            break
        c9, c1 = 0.999 * cmad, 0.001 * cmad
        for k in range(n):
            r = abs(res[k])
            if r <= c1:
                rw[k] = 1.0
            elif r <= c9:
                rw[k] = (1.0 - (r / cmad) ** 2) ** 2
            else:
                rw[k] = 0.0
    return ys


# -- what Panel.regression draws ---------------------------------------------------

#: Accepted values of `Panel.regression(method=)`.
REGRESSION_METHODS = ("linear", "lowess")


def regression_curve(points, *, method: str = "linear", confidence: float | None = 0.95,
                     prediction: bool = False, samples: int = 100,
                     span: tuple[float, float] | None = None,
                     frac: float = 2.0 / 3.0, iterations: int = 3,
                     log_x: bool = False) -> dict:
    """The line and band `Panel.regression` draws, without drawing them.

    Returns a dict with `line` (points), `band` (`(x, low, high)` or None),
    `fit` (a `LinearFit`, or None for LOWESS) and `method`.

    With `log_x=True` the fit is of y on ``log10(x)``, points with x <= 0
    are dropped, and the curve is returned in data units -- so it is
    straight on a log axis, and the slope is the change in y per decade.
    """
    if method not in REGRESSION_METHODS:
        raise DiagramError(f'regression method is "linear" or "lowess", not {method!r}')
    xs, ys = _pairs(points)
    if log_x:
        kept = [(math.log10(x), y) for x, y in zip(xs, ys) if x > 0]
        xs, ys = [k[0] for k in kept], [k[1] for k in kept]
    if len(xs) < 2:
        raise DiagramError("a regression needs at least two points")
    back = (lambda u: 10.0 ** u) if log_x else (lambda u: u)
    if method == "lowess":
        smooth = lowess(list(zip(xs, ys)), frac=frac, iterations=iterations)
        line, seen = [], set()
        for x, y in smooth:
            if x not in seen:
                seen.add(x)
                line.append((back(x), y))
        return {"line": line, "band": None, "fit": None, "method": method}
    fit = linear_fit(list(zip(xs, ys)))
    if span is None:
        lo, hi = min(xs), max(xs)
    else:
        lo, hi = float(span[0]), float(span[1])
        if log_x:
            if not (lo > 0 and hi > 0):
                raise DiagramError("a regression span on a log axis must be positive")
            lo, hi = math.log10(lo), math.log10(hi)
    if samples < 2:
        raise DiagramError(f"a regression line needs at least 2 samples, got {samples}")
    grid = [lo + (hi - lo) * k / (samples - 1) for k in range(samples)]
    line = [(back(x), fit.predict(x)) for x in grid]
    band = None
    if confidence is not None and fit.n >= 3:
        bounds = [fit.band(x, confidence, prediction=prediction) for x in grid]
        band = ([back(x) for x in grid], [b[0] for b in bounds], [b[1] for b in bounds])
    return {"line": line, "band": band, "fit": fit, "method": method}
