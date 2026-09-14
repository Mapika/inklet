# Everyday plots from CSV tables

This example combines six common plots from machine learning,
engineering and business: training curves, benchmark points, a sensor response,
residuals, grouped revenue bars and a composition heatmap. All inputs are original
**simulated data**, supplied as small typed CSV files. SVG/PDF authoring uses only
Inklet's core dependencies; PNG export adds the render extra.

[Full-size figure](../gallery/general-plots.png) ·
[Editable SVG](assets/examples/general-plots.svg) · [PDF](assets/examples/general-plots.pdf) ·
[Executable recipe](../examples/general_plots.py) ·
[Data and source hashes](assets/research-preview/general-plots.json) ·
[LaTeX caption](assets/research-preview/general-plots-caption.tex)

![Six plots covering simulated training loss, model accuracy and latency, a sensor response, residual distribution, quarterly revenue and product revenue shares.](../gallery/general-plots.png)

## Reproduce it

For a smaller step-by-step example, use [From CSV to a figure](csv-figure.md).
Run these commands from a checkout of this documentation revision, which
includes the updated [source recipe](../examples/general_plots.py):

```bash
python -m pip install -e '.[render]'
python examples/general_plots.py
```

Outputs in `out/general-plots/` include SVG/PDF/PNG, an HTML review, `data.json`,
`caption.txt` and `caption.tex`. The input files are in
`examples/data/general-plots/`; nothing is downloaded. In a LaTeX figure
environment, place the PDF and then use `\input{caption.tex}`. Figure titles,
panel descriptions and methods stay in the external caption.

The example reads explicit numeric types with `inklet.read_csv`, shares model
colors between a and b, and uses live dataset references for plots. Revenue
shares are derived from the same columns used for the grouped bars. Updating
those columns updates both panels when the document is compiled again.
The [data guide](data.md#typed-csv-input) explains source hashes and parsing rules.

## Plot appearance changes

Each row pairs related views: loss with model comparison, response with
residuals, and revenue with its composition. Blue, teal and rust consistently
identify series. The benchmark labels name the points directly, while the
response separates light sample markers from the darker model line. A reference
line marks zero residual, and histogram separators make bin boundaries visible.

Axes use the theme's hairline weight, with light grey horizontal guides. Legends wrap
to the available width without shrinking text. Plot margins are shared so data
areas align across the grid. Use [axes and text](axes-and-scales.md)
for font and stroke controls, and [plot layout](publication-plots.md) for legends
and insets. These guides describe the current behavior.

## Compare the previous styling

The [earlier styling comparison](../gallery/general-plots-before.png) preserves
the original six-panel layout with heavier axes and one-column legends. To
compare those two styling choices in the **current** layout, run:

```bash
python examples/general_plots.py --legacy-look --output out/general-plots/before
```

This uses the current renderer and arrangement; it does not reproduce the archived
image pixel for pixel. The main figure is 200 mm wide; rebuild at the required physical size
instead of shrinking the finished image.

## Read the plots

- **a–b:** Simulated loss curves and benchmark points share model names and colors.
  No actual model training, held-out evaluation or inference timing was performed.
- **c–d:** A simulated first-order response has Gaussian noise with standard
  deviation 0.03 and seed 2026. Residuals are supplied in the CSV and histogram
  bins are fixed at width 0.02. Inklet does not fit the response model.
- **e–f:** Simulated revenue in thousands of euros, and each product's percentage
  of the total for that quarter. The color scale spans 0–100%; the table provides
  the unnormalized inputs.

All data, processing, figure artwork and captions are MIT, Mark Marosi.
