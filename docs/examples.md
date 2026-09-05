# Examples

These figures link to executable source in the repository. Commands below run
from a checkout with Inklet installed. Review bundles need the
[preview dependencies](installation.md#visual-review); add `--vectors-only`
where supported to save only SVG/PDF.

## A complete live document

The [v2.5 example](../examples/v25_document.py) combines nested grids, measured
architecture modules, plots, publication defaults and live data.

```sh
inklet build examples/v25_document.py --output out/v25 --name document
```

Start here when adapting Inklet for your own multi-panel figure. The smaller
[v2 example](../examples/v2_document.py) focuses on datasets and shared scales.

## Twenty-panel stress test

![Twenty-panel mixed-media stress figure](../gallery/stress20.png)

Native 3D, a measured architecture, network, dense scatter, statistical charts,
polar response, Sankey flow and vector events share one page. The data are
simulated and the meshes are generated locally.

```sh
python tools/stress20.py
```

[Source](../examples/stress20.py) · [Workload, checks and findings](stress20.md)

This command also exercises edits, cached compilation, provenance, resizing
and independent SVG/PDF rendering. It takes longer than the small examples.

## Direct drawing examples

| Figure | Source | Run |
|---|---|---|
| Plot collection | [gallery.py](../examples/gallery.py) | `python examples/gallery.py` |
| Methods flow | [showcase_process.py](../figures/showcase_process.py) | `python figures/showcase_process.py` |
| Time series and heatmap | [showcase_season.py](../figures/showcase_season.py) | `python figures/showcase_season.py` |
| Labelled 3D part | [showcase_part.py](../figures/showcase_part.py) | `python figures/showcase_part.py` |
| Polar response | [polar.py](../examples/polar.py) | `python examples/polar.py` |

These use the direct API and may save next to their source scripts. Their
output paths are defined in the scripts; they are not all CLI factory modules.
The [repository gallery](../gallery/README.md) lists additional figures and assets.

## Scientific examples

The [neural-activity example](../figures/neural_activity.py) combines learning
curves, a spike raster, a peri-event histogram and endpoint statistics. All
observations are simulated from fixed seeds.

```sh
python figures/neural_activity.py
```

The [structure figure](../figures/structure.py) draws the EGFR kinase from PDB
1M17 beside explicitly simulated assay data. See the
[third-party notices](../THIRD_PARTY_NOTICES.md) for the structure data and meshes.
