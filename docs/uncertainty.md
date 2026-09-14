# Uncertainty and supplied intervals

Inklet draws the bounds or error magnitudes you supply; it does not infer
a confidence interval from raw observations. State what the interval means
and how another calculation produced it. Distinguish absolute bounds from
distances around a central estimate.

All values below are illustrative. Each snippet can be run independently with
core Inklet; PNG preview generation additionally uses the `render` extra. Run a
block as a script from the repository root, or paste it into a Python session.
Every block creates its own document and writes SVG and PDF.

## Bands

A band joins supplied lower and upper bounds over x.
Both arrays contain absolute y coordinates. Draw the central line afterward.

```python
import inklet as i
x = list(range(13))
mean = [2.0, 2.25, 2.55, 2.7, 2.95, 3.15, 3.35, 3.6, 3.72, 3.95, 4.1, 4.28, 4.5]
low = [1.45, 1.72, 2.05, 2.1, 2.42, 2.55, 2.72, 3.05, 3.0, 3.35, 3.4, 3.68, 3.82]
high = [2.55, 2.82, 3.0, 3.35, 3.5, 3.8, 3.98, 4.15, 4.52, 4.55, 4.82, 4.88, 5.18]
p = i.plot_spec(x=(0, 12), y=(0, 5.6), height=44)
p.band(x, low, high, fill='#b8d6cd', stroke='none')
p.line(list(zip(x, mean)), stroke='#288675', stroke_width=.5)
p.grid(x=False, y=True, count=5, stroke='#e1e7e4', stroke_width=.15)
p.axes(x='Time / s', y='Estimate / a.u.')
doc = i.document(width=110)
doc.add('band', p)
doc.save('band.svg', 'band.pdf')
```

![Bands: A band joins supplied lower and upper bounds over x.](assets/guides/plots-band.png)

*Rendered from the code above. The 13-point centre line and changing bounds are
supplied illustrative values; the band is not a confidence interval.*

## Error bars

Error bars show distances from each estimate.
`yerr` and `xerr` accept symmetric magnitudes or one `(down, up)` pair per
point. Convert absolute interval limits by subtracting the central estimate.
`cap` is the half-width of an end cap in millimetres.

```python
import inklet as i
points = [(1, 2.1), (2, 3.35), (3, 2.85), (4, 4.15), (5, 3.75)]
p = i.plot_spec(x=(0, 6), y=(0, 5.5), height=44)
p.errorbars(points, yerr=[(.25, .4), (.45, .3), (.35, .55), (.5, .38), (.28, .46)],
            xerr=[.08, .12, .1, .14, .09], cap=1, stroke='#24698c')
p.scatter(points, size=1.8, color='#24698c')
p.grid(x=False, y=True, count=5, stroke='#e1e7e4', stroke_width=.15)
p.axes(x='Dose / µM', y='Response / mV')
doc = i.document(width=110)
doc.add('errorbars', p)
doc.save('errorbars.svg', 'errorbars.pdf')
```

![Error bars: Error bars show distances from each estimate.](assets/guides/plots-errorbars.png)

*Rendered from the code above. Five illustrative dose–response estimates have
asymmetric response distances and supplied dose uncertainty.*

## Line with errors

A line can show supplied uncertainty as a band or error bars.
`err` uses error magnitudes, like `errorbars`; `err_style="band"` shades the
spread and `err_style="bars"` draws whiskers. The uncertainty is drawn before the line.

```python
import inklet as i
p = i.plot_spec(x=(0, 12), y=(0, 6), height=44)
p.line([(0, 1.5), (1, 1.95), (2, 2.35), (3, 2.85), (4, 3.1),
       (5, 3.55), (6, 3.85), (7, 4.05), (8, 4.35), (9, 4.55),
       (10, 4.78), (11, 5.0), (12, 5.18)],
       err=[.28, .34, .3, .42, .38, .45, .36, .5, .44, .52, .46, .58, .5],
       err_style='band', stroke='#b86443', name='Supplied estimate')
p.grid(x=False, y=True, count=5, stroke='#e1e7e4', stroke_width=.15)
p.axes(x='Time / s', y='Estimate / a.u.').legend(side='bottom')
doc = i.document(width=110)
doc.add('line-errors', p)
doc.save('line-errors.svg', 'line-errors.pdf')
```

![Line with errors: A line can show supplied uncertainty as a band or error bars.](assets/guides/plots-line-errors.png)

*Rendered from the code above.*

## Reusable series

A Series keeps the name, values, colour and absolute bounds together.
Use `plot_spec().series()` when several panels should share that definition.
The lower and upper arrays are absolute bounds, not error magnitudes.

```python
import inklet as i
times = list(range(7))
control = i.Series('Control', times, [1.3, 1.65, 1.95, 2.2, 2.5, 2.72, 2.95], '#24698c',
                   [1.0, 1.32, 1.6, 1.82, 2.08, 2.3, 2.5],
                   [1.6, 1.98, 2.3, 2.58, 2.9, 3.12, 3.4])
treatment = i.Series('Treatment', times, [1.5, 1.95, 2.3, 2.72, 3.0, 3.32, 3.6], '#288675',
                     [1.15, 1.58, 1.9, 2.3, 2.55, 2.85, 3.08],
                     [1.88, 2.3, 2.7, 3.1, 3.45, 3.78, 4.12])
p = i.plot_spec(x=(0, 6), y=(0, 4.5), height=44)
p.series(control, stroke_width=.45)
p.series(treatment, stroke_width=.45)
for series in (control, treatment):
    p.series(series, uncertainty=False, stroke_width=.45)
p.grid(x=False, y=True, count=5, stroke='#e1e7e4', stroke_width=.15)
p.axes(x='Time / s', y='Estimate / a.u.').legend(side='bottom')
doc = i.document(width=110)
doc.add('series', p)
doc.save('series.svg', 'series.pdf')
```

![Reusable series: A Series keeps the name, values, colour and absolute bounds together.](assets/guides/plots-series.png)

*Rendered from the code above. The reusable definitions compare illustrative
Control and Treatment trajectories with absolute, nonconstant bounds; these
bands do not claim confidence intervals.*

The final line-only pass keeps both trajectories visible above the overlapping
bands. Reusing a series name keeps one combined entry in the legend.

## Next steps

[Compare plot types](plot-types.md), configure [axes and scales](axes-and-scales.md),
or [arrange several panels](layout.md). For exact options, see the [API](api.md).
