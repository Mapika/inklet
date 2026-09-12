<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Mapika/inklet/adbbc4082920173a9e7b95d27af11622cfc545fa/docs/assets/brand/inklet-logo-dark.svg">
    <img src="https://raw.githubusercontent.com/Mapika/inklet/adbbc4082920173a9e7b95d27af11622cfc545fa/docs/assets/brand/inklet-logo.svg" alt="Inklet" width="280" height="69">
  </picture>
</h1>

**Scientific figures from Python, with measured layout and editable SVG/PDF output.**

Combine plots, diagrams, images and native 3D artwork on a page sized in
millimetres. Keep data and labels live, compile the figure, and inspect its
layout and print diagnostics before exporting.

[Get started](https://inklet.readthedocs.io/en/stable/quickstart/) · [Documentation](https://inklet.readthedocs.io/en/stable/) ·
[Examples](https://inklet.readthedocs.io/en/stable/examples/) · [API reference](https://inklet.readthedocs.io/en/stable/api/)

![Twenty-panel Inklet figure with 3D surfaces, architecture diagrams, dense scatter, statistical charts, polar plots and Sankey flows](https://raw.githubusercontent.com/Mapika/inklet/v2.6.0/gallery/stress20.png)

This [twenty-panel stress test](https://inklet.readthedocs.io/en/stable/stress20/) includes 30,000 scatter points,
5,580 mesh triangles and 7,200 vector events. Its data are simulated. Only the
dense scatter and scalar field are rasterized; the other artwork remains vector.

Inklet 3.1 adds [everyday plots from CSV](https://inklet.readthedocs.io/en/stable/general-plots/),
[faster rendering and nested layouts](https://inklet.readthedocs.io/en/stable/rendering-engine/),
[measured diagram improvements](https://inklet.readthedocs.io/en/stable/diagram-engine/)
and [dense vector lines with axis font controls](https://inklet.readthedocs.io/en/stable/plotting-engine/).
The illustrated docs start with [choosing a plot type](https://inklet.readthedocs.io/en/stable/plot-types/),
then cover axes, dense data, page layout and exports. Figure planning and microscopy
ship under `inklet.experimental` as a [research preview](https://inklet.readthedocs.io/en/stable/research-preview/):
their signatures and report schemas may change.

## 4.0 development preview

**4.0.0.dev4** fixes closed polar curves and shaded bands, and adds a visual
plot gallery with 22 runnable examples. It retains shared compiled rendering,
offline viewing, linked reports, and reproducible plot editing with undo/redo.
```sh
python -m pip install "inklet==4.0.0.dev4"
```

[Preview guide and examples](https://inklet.readthedocs.io/en/latest/development-preview/) ·
[4.0 roadmap](https://inklet.readthedocs.io/en/latest/roadmap/) ·
[Release notes](https://github.com/Mapika/inklet/releases/tag/v4.0.0.dev4)

This is an opt-in development release. Experimental APIs and saved-state schemas
may change; 3.1.0 remains the stable release. General browser editing,
depth-aware 3D selection and the remaining 4.0 release gates are still open.
Animation and presentation authoring remain in the 5.0 direction.

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

## Your first figure

Save this as `first_figure.py` and run `python first_figure.py`:

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

## What you can build

| Task | Main tools | Guide |
|---|---|---|
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
Inklet 2.6 adds [scientific, educational and marketing presets](https://inklet.readthedocs.io/en/stable/presets/).
The [latest documentation](https://inklet.readthedocs.io/en/latest/) follows the
development branch. The source Markdown is also readable on GitHub, and
contributors can serve the site from a checkout:

```sh
python -m pip install -e '.[docs]'
python -m mkdocs serve
```

See [contributing](https://github.com/Mapika/inklet/blob/v2.6.0/CONTRIBUTING.md) for tests, documentation checks and visual
regressions. Existing users can consult [migration](https://inklet.readthedocs.io/en/stable/migration/),
[the v2.5 changes](https://inklet.readthedocs.io/en/stable/v2.5/) and [the changelog](https://github.com/Mapika/inklet/blob/v2.6.0/CHANGELOG.md).

## License

Inklet code is available under the [MIT license](https://github.com/Mapika/inklet/blob/v2.6.0/LICENSE). Included third-party
meshes and structural data retain their own terms; see
[third-party notices](https://github.com/Mapika/inklet/blob/v2.6.0/THIRD_PARTY_NOTICES.md).
