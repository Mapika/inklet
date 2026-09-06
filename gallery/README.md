# Gallery

The eight `showcase-*.png` figures are rendered at 300 dpi with
`tools/showcase_gallery.py`. See the [showcase library](../docs/showcase.md)
for recipes, Blender scenes, downloads and credits.

The earlier figures below are rasterised at 3x with `scripts/rasterise.sh`
unless specified otherwise.

| file | source | shows |
|---|---|---|
| [`stress20.png`](stress20.png) | [`examples/stress20.py`](../examples/stress20.py) | Twenty-panel v2.5 stress test: native 3D, architecture, network, dense scatter, statistics, polar, Sankey and 7,200 vector events; see [checks and findings](../docs/stress20.md) |
| `plots.png` | `examples/gallery.py` | 16 plot types, one panel each |
| `season.png` | `figures/showcase_season.py` | lines + twin axis, raster heatmap, colorbar, legend, date axis, annotated peak |
| `process.png` | `figures/showcase_process.py` | flow diagram: trunk, self-loop, ports, markup labels |
| `part.png` | `figures/showcase_part.py` | drilled 3D part with dimension lines and a callout |
| `structure.png` | `figures/structure.py` | five-panel EGFR structure figure: lobe-coloured cartoon, pocket close-up with measured H-bonds, interaction schematic, SPR, K_D per variant |
| `polar.png` | `examples/polar.py` | polar plots: orientation-tuning curve with axial mean vector, 180-degree rose histogram |
| `flow.png` | `stress/flow.py` | Sankey: cortical progenitor fate, width-proportional ribbons, crossing-minimised |
| `chem_fingerprints.png` | `figures/chem_fingerprints.py` | eight-panel cheminformatics figure: 38 drugs, circular fingerprints and Tanimoto matrix seriated by optimal leaf ordering, dendrogram, substructure incidence by subgraph isomorphism, nine structural formulas, and two 3-D panels from one hand-written eigensolver -- a distance-geometry conformer as ball-and-stick and the chemical space itself as classical MDS of the Tanimoto distances |

Regenerate any of them from the repo root:

    .venv/bin/python examples/gallery.py
    scripts/rasterise.sh examples/gallery.svg gallery/plots.png 3

The twenty-panel preview is generated at 150 dpi by
`.venv/bin/python tools/stress20.py`; copy `out/stress20/stress20.png` to
`gallery/stress20.png` after reviewing it.

Third-party data and mesh terms are listed in [the notices](../THIRD_PARTY_NOTICES.md).
