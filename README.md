<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Mapika/inklet/adbbc4082920173a9e7b95d27af11622cfc545fa/docs/assets/brand/inklet-logo-dark.svg">
    <img src="https://raw.githubusercontent.com/Mapika/inklet/adbbc4082920173a9e7b95d27af11622cfc545fa/docs/assets/brand/inklet-logo.svg" alt="Inklet" width="280" height="69">
  </picture>
</h1>

**Scientific figures from Python, with measured layout and editable SVG/PDF output.**

```python
import inklet as i

data = {'time': [0, 1, 2, 3], 'signal': [1, 3, 2, 4]}   # or a pandas/Polars DataFrame
i.line(data, x='time', y='signal').save('signal.pdf', 'signal.svg')
```

One call gives you a chart sized for a journal column, with measured labels and
vector output. Combine charts into lettered multi-panel figures with `|` and `/`,
bring existing matplotlib figures across with `i.from_matplotlib(fig)`, and add
diagrams, images and native 3D artwork on the same millimetre-sized page.

[Get started](https://inklet.readthedocs.io/en/stable/quickstart/) · [Documentation](https://inklet.readthedocs.io/en/stable/) ·
[Examples](https://inklet.readthedocs.io/en/stable/examples/) · [API reference](https://inklet.readthedocs.io/en/stable/api/)

![Twenty-panel Inklet figure with 3D surfaces, architecture diagrams, dense scatter, statistical charts, polar plots and Sankey flows](https://raw.githubusercontent.com/Mapika/inklet/v2.6.0/gallery/stress20.png)

This [twenty-panel stress test](https://inklet.readthedocs.io/en/stable/stress20/) includes 30,000 scatter points,
5,580 mesh triangles and 7,200 vector events. Its data are simulated. Only the
dense scatter and scalar field are rasterized; the other artwork remains vector.

Start with [plots from CSV](https://inklet.readthedocs.io/en/stable/general-plots/),
then combine them with measured diagrams, images and 3D in one figure. Shared
scales keep panels comparable; physical dimensions keep type and strokes
consistent when you change the page size. The
[plot guide](https://inklet.readthedocs.io/en/stable/plot-types/) helps choose a
representation, while [layout](https://inklet.readthedocs.io/en/stable/layout/)
and [export review](https://inklet.readthedocs.io/en/stable/export-review/)
cover the finished page.

## Inklet 4.0

**4.6.0 is stable**. It adds charts in one call (`i.line(df, x=, y=,
color=)` and about twenty more), a matplotlib bridge (`i.from_matplotlib`),
inline notebook display, and tooling for coding agents (`inklet guide`,
`inklet check`, `inklet skill`). 4.5 let a page choose among layout
alternatives and pack panels without a grid. The 4.4 series added about
60 plot types, 98 curated palettes with the new default `inklet` palette, and a
label placement engine for direct labels and legends. 4.x is the deprecation
series before 5.0: old spellings
and `inklet.experimental` import paths still work and now warn, naming the
replacement.

```sh
python -m pip install --upgrade inklet
```

[4.0 guide](https://inklet.readthedocs.io/en/latest/development-preview/) ·
[Figure project tutorial](https://inklet.readthedocs.io/en/latest/project-workflows/) ·
[4.0 roadmap](https://inklet.readthedocs.io/en/latest/roadmap/) ·
[Release notes](https://github.com/Mapika/inklet/blob/master/CHANGELOG.md)

From 4.3, microscopy volumes (`inklet.volume`), keyed selections
(`inklet.selection`), figure projects (`inklet.project`) and the layout editor
(`inklet.editor`) are stable; the rest of `inklet.experimental` stays opt-in. The supported controls,
saved-file policy and deferred features are listed in the
[compatibility guide](https://inklet.readthedocs.io/en/latest/compatibility/).
Inklet 5.0 focuses on dense journal figures; animation and presentation authoring move to the 5.x direction.

## Install

Python **3.11 or later** is required. Install from [PyPI](https://pypi.org/project/inklet/):

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install inklet
```

SVG/PDF output and the built-in 3D renderer need no browser or external rendering
engine. Text needs an installed font. For PNG output and visual review, install
`python -m pip install 'inklet[render]'`. Poppler adds independent PDF previews;
use `compare_pdf=False` or `--no-pdf-preview` for a review without it.
See [installation](https://inklet.readthedocs.io/en/stable/installation/) for system packages, Windows activation,
optional dependencies and environment checks.

## Your first chart

```python
import inklet as i

data = {'time': [0, 1, 2, 3] * 2, 'signal': [1, 3, 2, 4, 2, 4, 3, 5],
        'condition': ['control'] * 4 + ['treated'] * 4}

chart = i.line(data, x='time', y='signal', color='condition')
figure = chart.save('response.svg', 'response.pdf')
print(figure.report())
```

`data` can also be a pandas or Polars DataFrame. Axes fit the data, axis titles
come from the column names, and the legend appears because there are two groups.
`line`, `scatter`, `bar`, `hist`, `kde`, `ecdf`, `boxplot`, `violin`, `strip`,
`area`, `regression` and `heatmap` share these keywords. Put charts side by side
with `|` and stack them with `/`:

```python
figure = (i.line(data, x='time', y='signal', color='condition')
          | i.boxplot(data, x='condition', y='signal', points=True))
figure.save('figure1.pdf')
```

Fourteen [published figures recreated from their data](https://inklet.readthedocs.io/en/latest/published-figures/)
-- LIGO's first detection, Hubble 1929, the Keeling curve, the CMB spectrum, Snow's cholera map and more -- show
what the finished output looks like. See [charts in one call](https://inklet.readthedocs.io/en/latest/quick-charts/) for every
chart type and option, and [bringing matplotlib figures](https://inklet.readthedocs.io/en/latest/matplotlib/)
for converting existing plotting code.

Try it in a notebook: [examples/notebooks/quickstart.ipynb](https://github.com/Mapika/inklet/blob/master/examples/notebooks/quickstart.ipynb).

### The document model

Charts are a front end to live documents, which also hold diagrams, images and
3D scenes. Save this as `first_figure.py` and run `python first_figure.py`:

```python
import inklet as i


def make_document():
    data = i.dataset(
        {'time': [0, 1, 2, 3], 'signal': [1, 3, 2, 4]},
        name='response',
        source=i.Source('Quickstart demonstration', method='simulated'),
    )
    plot = i.plot_spec(x=(0, 3), y=(0, 5))
    plot.line(data.points('time', 'signal'), name='Signal', stroke='#176b9b')
    plot.axes(x='Time / s', y='Signal / mV').legend(side='bottom')

    doc = i.publication('single-column').document()
    doc.add('response', plot, min_height=55)
    return doc


if __name__ == '__main__':
    figure = make_document().compile()
    figure.save('response.svg', 'response.pdf')
    print(figure.report())
```

The document measures axis labels and the legend, fits the plot to an 89 mm
page, and saves SVG and PDF with embedded text. It does not shrink the font to
make the plot fit. The [quickstart](https://inklet.readthedocs.io/en/stable/quickstart/) continues with live data
edits, multiple panels and review exports.

## Build, inspect, revise

With the [preview dependencies](https://inklet.readthedocs.io/en/stable/installation/#visual-review) installed:

```sh
inklet doctor
inklet build first_figure.py --output out/review
inklet watch first_figure.py --output out/review
```

`build` writes the vector files, PNG previews, diagnostics, a provenance manifest
and a local HTML review page. `watch` serves a preview at
`http://127.0.0.1:8765/` and rebuilds when the authoring code changes. Review pages
support diagnostic filters, SVG highlights and comparisons with a saved revision.

For an environment without preview tools, use
`inklet build first_figure.py --output out/review --vectors-only`.

## With a coding agent

```sh
inklet guide                            # usage guide for agents, matching this version
inklet skill                            # install it as .claude/skills/inklet/SKILL.md
inklet check figure.py --png preview.png  # build, list layout problems, exit 1 on errors
```

The chart API follows the plotly express convention that agents already know.
Every figure reports overlapping, clipped or undersized text in plain language
with the fix, and `save()` raises a `LayoutWarning` when something needs
attention. Nothing opens a window, and output is byte-for-byte deterministic. See
[using Inklet with coding agents](https://inklet.readthedocs.io/en/latest/coding-agents/).

## What you can build

| Task | Main tools | Guide |
|---|---|---|
| Charts from a table in one call | `line`, `scatter`, `bar`, `boxplot`, `heatmap`, `\|` and `/` layouts | [Charts in one call](https://inklet.readthedocs.io/en/latest/quick-charts/) |
| Existing matplotlib figures | `from_matplotlib` | [Bring matplotlib figures](https://inklet.readthedocs.io/en/latest/matplotlib/) |
| Scientific, educational and branded styles | `preset`, independent formats, live switching | [Presets](https://inklet.readthedocs.io/en/stable/presets/) |
| Multi-panel figures | `document`, `subfigure`, weighted columns, spans, panel letters | [Layout](https://inklet.readthedocs.io/en/stable/layout/) |
| Scientific plots | `plot_spec`, axes, bands, distributions, heatmaps, insets, polar plots | [Plotting](https://inklet.readthedocs.io/en/stable/plotting/) |
| Data-driven revisions | `Dataset`, `Series`, shared scales, categories, `derive`, source records | [Live data](https://inklet.readthedocs.io/en/stable/data/) |
| Architecture and flow diagrams | `composition`, `module`, named ports, measured connections, `graph` | [Diagrams](https://inklet.readthedocs.io/en/stable/diagrams/) |
| 3D and image panels | `solid`, `model`, `scene`, `asset`, explicit file dependencies | [3D and images](https://inklet.readthedocs.io/en/stable/three-images/) |
| Publication exports | Physical presets, embedded or outlined text, SVG/PDF, review bundles | [Export and review](https://inklet.readthedocs.io/en/stable/export-review/) |

## How Inklet works

A `Document` holds live definitions. `compile()` measures their contents, places
them, routes connections and produces a snapshot used by both export backends.
Updating a dataset or named instruction invalidates dependent components;
unchanged definitions can reuse their cached geometry. Earlier snapshots remain
unchanged.

Numeric lengths, including low-level text sizes, are **millimetres**. Use
`i.pt(8)` for an 8-point text size; publication profile options such as
`font_pt=8` take points explicitly. Plot coordinates follow their data scales.

The direct `Figure`, `Panel` and `Diagram` APIs remain supported for fixed
drawings. See [the authoring model](https://inklet.readthedocs.io/en/stable/concepts/) for when to use each layer.

## Scope and limits

- Layout respects physical constraints. Impossible fits raise `LayoutError`;
  changing page width does not automatically rearrange the number of columns.
- Diagnostics help find collisions, small type and other print issues. Review
  the rendered figure as well; a clean report does not establish scientific accuracy.
- Rasterization keeps dense exports compact, but dense-scatter rebuilds can
  still be expensive. The [stress report](https://inklet.readthedocs.io/en/stable/stress20/) records the workload,
  timings and remaining limitations.
- Reproducible appearance requires consistent inputs, fonts and dependencies.
  The export manifest records dataset and font hashes for comparison.

## Scene rendering

Inklet combines complete Blender scenes with vector plots, labels and
measurements. Cycles uses an available GPU and falls back to CPU when none is
found. Render queues provide progress, cancellation and bounded concurrency.
Saved camera projection and numeric passes support depth-tested paths, object
masks and world-space dimensions without rerendering an annotation change.

Three editable templates cover laboratory apparatus, product presentation and
architecture. The [annotated laboratory](https://inklet.readthedocs.io/en/stable/complex-scene/)
combines 265 objects, twelve callouts, a measured footprint, two detail views and
an analytic response plot.

![An annotated laboratory cutaway with detail views and a response plot](https://raw.githubusercontent.com/Mapika/inklet/v3.0.0/gallery/v3-complex-scene.png)

PNG export uses resvg and needs no browser. Gradients, hatching and group
blending remain vector in SVG/PDF. Masks and explicit rasterization create image
layers; keep editable text outside them. Blender is installed separately and
remains optional for ordinary plots and native vector 3D.

[Rendering guide](https://inklet.readthedocs.io/en/stable/v3/) ·
[Scene templates](https://inklet.readthedocs.io/en/stable/scene-templates/) ·
[Showcase library](https://inklet.readthedocs.io/en/stable/showcase/) ·
[Upgrade from 2.6](https://inklet.readthedocs.io/en/stable/migration/#from-26-to-30) ·
[Compatibility](https://inklet.readthedocs.io/en/stable/compatibility/)

## Documentation and development

Read the [documentation on Read the Docs](https://inklet.readthedocs.io/en/stable/).
The [latest documentation](https://inklet.readthedocs.io/en/latest/) follows the
development branch. The source Markdown is also readable on GitHub, and
contributors can serve the site from a checkout:

```sh
python -m pip install -e '.[docs]'
python -m mkdocs serve
```

See [contributing](https://github.com/Mapika/inklet/blob/master/CONTRIBUTING.md) for tests, documentation checks and visual
regressions. Existing users can consult [migration](https://inklet.readthedocs.io/en/stable/migration/),
[historical guides](https://inklet.readthedocs.io/en/latest/history/) and [the changelog](https://github.com/Mapika/inklet/blob/master/CHANGELOG.md).

## License

Inklet code is available under the [MIT license](https://github.com/Mapika/inklet/blob/master/LICENSE). Included third-party
meshes and structural data retain their own terms; see
[third-party notices](https://github.com/Mapika/inklet/blob/master/THIRD_PARTY_NOTICES.md).
