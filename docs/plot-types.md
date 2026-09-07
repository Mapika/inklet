# Choose a plot type

Start with the relationship you want readers to see. These methods work in a
live `plot_spec()` and in the direct `Panel` API. Use a [document](layout.md) to
arrange several plots; add an explanatory caption in your manuscript.

| What you want to show | Use | Complete example |
| --- | --- | --- |
| A response over time or another ordered variable | `line`, `step` | [Training curves](general-plots.md) |
| Relationships between individual observations | `scatter` | [Dense observations](rendering-engine.md) |
| Values and uncertainty | `line(err=...)`, `band`, `errorbars`, `series` | [Engineering responses](general-plots.md) |
| Values across named categories | `bars`, with `bar_colors` per category | [Business comparisons](general-plots.md) |
| Distribution of observations | `hist`, `boxplot`, `violin` | [Mixed statistical panels](stress20.md) |
| A matrix or sampled field | `matrix` and `colorbar` | [Coordinated heatmaps](biology-panels.md) |
| Additive contributions over x | `stackarea` | [Direct drawing recipes](cookbook.md) |
| Angular or radial measurements | `polar` | [Polar recipe](../examples/polar.py) |
| Nodes and relationships | `graph`, `composition` | [Measured architecture](diagram-engine.md) |
| A three-dimensional scene alongside measurements | `solid`, `scene` | [3D and image guide](three-images.md) |

## A small categorical plot

```python
import inklet as i

p = i.plot_spec(x=['Control', 'Treatment'], y=(0, 10), height=42)
p.bars(['Control', 'Treatment'], [5, 8],
       bar_colors=['#527da8', '#b96932'])
p.axes(y='Response / a.u.')
doc = i.document(width=95)
doc.add('comparison', p)
doc.save('comparison.svg', 'comparison.pdf')
```

`bar_colors` maps colours to categories. For grouped bars, `colors` maps colours
to series. Define [shared categories](data.md) when subsets must retain their
labels and colours. The numbers above are illustrative, not experimental data.

## Add meaning and arrange the page

- [Axes and scales](axes-and-scales.md): numeric, logarithmic, categorical and date coordinates; tick labels and typography.
- [Plotting guide](plotting.md): uncertainty, legends, insets and live edits.
- [Dense data](dense-data.md): choose vector geometry or raster layers without changing the source data.
- [Whole-figure layout](layout.md): align panels, share scales and reserve space for labels.
- [Presets](presets.md): publication, teaching and presentation styles.

For exact signatures, use the [Python API](api.md). For a complete figure you can
edit, browse the [gallery](examples.md).
