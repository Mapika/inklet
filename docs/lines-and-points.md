# Lines and points

Use a line when point order matters, a step for discrete changes, and scatter
when the observations should stand independently. Inklet connects line points
in supplied order; sort your data explicitly when necessary.

All values below are illustrative. Each snippet can be run independently with
core Inklet; PNG preview generation additionally uses the `render` extra.
Run a block from the repository root with `.venv/bin/python`; each block writes
an SVG and PDF. Keep x values sorted for a time or numeric trajectory. A line
connects observations in the order supplied and does not fit a model.

## Lines

A continuous response connects the supplied observations in order.

```python
import math
import inklet as i

time = [n / 4 for n in range(49)]
p = i.plot_spec(x=(0, 12), y=(0, 1.15), height=45)
p.grid(x=False, count=4, stroke='#e1e7e4', stroke_width=.15)
for name, rate, colour in [('Control', .24, '#24698c'),
                           ('Treated', .48, '#288675')]:
    response = [(t, 1 - math.exp(-rate * t)) for t in time]
    p.line(response, name=name, stroke=colour, stroke_width=.45)
p.axes(x='Time / s', y='Normalized response')
p.legend(side='bottom')
doc = i.document(width=110)
doc.add('line', p)
doc.save('line.svg', 'line.pdf')
```

![Lines: A continuous response connects the supplied observations in order.](assets/guides/plots-line.png)

*Illustrative first-order responses sampled every 0.25 s. Control and Treated use the same axes and distinct, named colours.*

## Steps

A step holds a value until the next observation.
`where="post"` holds forward, `"pre"` changes at the preceding x, and `"mid"`
changes halfway between samples. These are supplied values, not a fitted model.
Use a step only when the value is held or changes at known transitions; use a
line when interpolation between observations is meaningful.

```python
import inklet as i

commands = [(0, 10), (2, 10), (4, 40), (6, 40), (8, 70),
            (10, 70), (12, 30), (14, 30), (16, 55)]
value, response = 10, []
for n in range(65):
    t = n / 4
    target = commands[min(int(t // 2), 8)][1]
    value += .22 * (target - value)
    response.append((t, value))
p = i.plot_spec(x=(0, 16), y=(0, 85), height=45)
p.grid(x=False, count=4, stroke='#e1e7e4', stroke_width=.15)
p.step(commands, where='post', name='Command',
       stroke='#b86443', stroke_width=.45)
p.line(response, name='Simulated response', stroke='#24698c', stroke_width=.45)
p.axes(x='Time / s', y='Output / %').legend(side='bottom')
doc = i.document(width=115)
doc.add('step', p)
doc.save('step.svg', 'step.pdf')
```

![Steps: A step holds a value until the next observation.](assets/guides/plots-step.png)

*The rust command stays fixed between transitions. The blue simulated response updates every 0.25 s and approaches each new command.*

## Scatter

Scatter shows individual observations without connecting them.
`size` is marker diameter in millimetres, not marker area or a data-coordinate
radius. A sequence supplies one size or colour per point; choose the mapping
explicitly when encoding another measurement.
Avoid encoding a second variable with both size and colour unless a legend makes
the mappings unambiguous; overlapping points can hide observations.

```python
import random
import inklet as i

rng = random.Random(28)
points = [(x := rng.uniform(1, 9), 1.2 + .7 * x + rng.gauss(0, .65))
          for _ in range(60)]
p = i.plot_spec(x=(0, 10), y=(0, 9), height=45)
p.grid(x=False, count=4, stroke='#e1e7e4', stroke_width=.15)
p.scatter(points, size=1.3, color='#24698c', name='Samples', fill_opacity=.65)
reference = i.marker('diamond', 2.6).styled(fill='#b86443', stroke='none')
p.marks(reference, [(2, 2.6), (5, 4.7), (8, 6.8)], name='Reference')
p.axes(x='Input / V', y='Response / mV').legend(side='bottom')
doc = i.document(width=110)
doc.add('scatter', p)
doc.save('scatter.svg', 'scatter.pdf')
```

![Scatter: Scatter shows individual observations without connecting them.](assets/guides/plots-scatter.png)

*Sixty simulated samples and three explicit reference points. Shape and colour distinguish the references without changing marker size to imply another variable.*

## Custom markers

A reusable drawing can mark each observation.
`marks()` positions the same glyph at data coordinates; its dimensions remain
physical. Use the standard `scatter(marker=...)` options for ordinary symbols.

```python
import math
import inklet as i

points = [(x, 5 * (1 - math.exp(-x / 3))) for x in range(1, 11)]
p = i.plot_spec(x=(0, 11), y=(0, 5.5), height=45)
p.grid(x=False, count=4, stroke='#e1e7e4', stroke_width=.15)
p.line(points, stroke='#b9ceca', stroke_width=.3)
glyph = i.marker('diamond', 2.3).styled(fill='#288675', stroke='none')
p.marks(glyph, points, name='Calibration samples')
p.axes(x='Input / V', y='Output / V').legend(side='bottom')
doc = i.document(width=110)
doc.add('markers', p)
doc.save('markers.svg', 'markers.pdf')
```

![Custom markers: A reusable drawing can mark each observation.](assets/guides/plots-markers.png)

*Ten illustrative calibration values use the same diamond glyph. The connecting line follows the supplied values; no model is fitted.*

## Next steps

[Compare plot types](plot-types.md), configure [axes and scales](axes-and-scales.md),
or [arrange several panels](layout.md). For exact options, see the [API](api.md).
