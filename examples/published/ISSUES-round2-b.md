# inklet issues found while recreating hare_lynx and ebbinghaus_1885

Found with the working tree on 2026-10-07. No inklet bug was found: both
figures build with `figure.report()` clean (`inklet lint: clean, 0
diagnostics`). The items below are friction, not defects.

## 1. Log scale for the full model is not in the guide (documentation)

`i.guide` documents `xscale='log'` only for the quick API (`i.line(...,
xscale='log')`). The full model (`i.plot_spec(...)`) takes a log axis through
`i.log((low, high))` (the same object as `inklet.plot.scale.log`), which the
guide never mentions. Found by reading `quick._domain`.

```python
import inklet as i
p = i.plot_spec(89, 62, x=i.log((0.01, 100)), y=(0, 70))   # works
p = i.plot_spec(89, 62, x=(0.01, 100), y=(0, 70))          # linear, not what is meant
```

Used in `ebbinghaus_1885/figure.py`. Expected: a line in the guide's
"full model" section.

## 2. Default log-axis tick labels use powers of ten (style)

With `x=i.log((0.01, 100))` and explicit ticks `[0.01, 0.1, 1, 10, 100]`, the
default labels are typeset as `10^{-2}`, `10^{-1}`, `10^{0}`, ... . The
figure wants the plain numbers, as in the reference. Workaround in
`ebbinghaus_1885/figure.py`:

```python
x_options=dict(ticks=[0.01, 0.1, 1, 10, 100], format=lambda v: f"{v:g}")
```

Not a crash, and the override works; recorded as a default to review.

## 3. Concurrent edit of `src/inklet/quick.py` during a run (process)

While `ebbinghaus_1885/figure.py` was being run for the first time,
`src/inklet/quick.py` contained git conflict markers (`<<<<<<< HEAD` at about
line 350), so `import inklet` raised `SyntaxError`. About a minute later the
markers were gone (file mtime 21:20) and the same script ran. Nothing in this
round touched `src/`. Reported only so that anyone editing the tree knows that
a broken import can appear mid-run.
