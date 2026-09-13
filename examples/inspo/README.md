# Both figures independently drawn in Inklet

The current outputs are in `out/inspo-native/`. This replaces the earlier
hybrid reconstruction. **None of the reference JPEGs, screenshot crops, or
reference contour caches is loaded.** All 30 panels use independently authored
Inklet plots, arrows, diagrams, text, or projections of real anatomical data.
The fly and wing illustrations are also drawn from primitive shapes.

Files: `chemosensory` and `dimorphism`, each in SVG, PDF and PNG;
`both-figures.pdf`; `inklet-native-figures.zip`; numeric tables in `chart-data/`.
All chart labels are text objects. Anatomy and chart marks are vector paths.
`panel-review.md` contains the panel-by-panel review and source-data limits.
`independent-plot-audit.md` is the pre-repair audit; `audit-resolutions.md` records the independent recheck.

## Reusable Inklet improvements

`inklet.text(bounds="ink")` optionally centers visible glyphs while preserving
editable text. Dimorphism C/D use it for circles and cells; H now uses one
measured legend with verified clearance from its curves.

The library now provides `inklet.connect` for immediately routing between placed
shapes, `inklet.label_column` for measured labels with retained target leaders,
and `Panel.region` for data-aligned selection boxes. It also provides `inklet.tag`, `inklet.arrow`, fitted `View` rendering,
`View.paths`, `View.markers`, `Mesh.from_arrays`, and optional display-only
`Mesh.simplified`. Core lengths accept NumPy real scalars without importing
NumPy. See `docs/scientific-authoring.md` and `examples/scientific_authoring.py`.
`panel-review.md` records every panel's findings and remaining data limitations.

## Real anatomy

MaleCNS v1.0 skeletons and meshes, registered FlyWire v783 female meshes, and
public plotting-space landmarks supply the anatomical drawings. The source
selection contains 860 male neurons. Panel P includes all 255 released members
of cluster 102. `data/manifest.json` records IDs, source URLs, hashes and
subsampling. Full gustatory connection weights select downstream partners.
Anatomical surfaces are projected from real mesh triangles; their silhouettes
are computational contours of those surfaces, never contours of the references.

## Detail pass: panels A, C, F, G, I and J

- A uses a shared anatomical frame split into detailed and schematic hemispheres,
  with distinct smooth arrowed pathways, measured label tags and shaded real surfaces.
  The real `KCab-s` type now matches the alpha/beta label.
- C uses measured receptor-neuron presynaptic sites in the released `AL(L)`
  region for its enlarged view, excluding incoming axon trajectories only there.
  The main overview retains full ORN skeleton connections over shaded anatomy. A single
  oblique camera is derived from the DA1, VA1v and VA1d group centers; no points
  are moved independently. The inset outline is the convex hull of projected
  real ROI vertices, an approximation to its irregular surface.
- F draws a denser sample of actual LH-left presynaptic sites from spatial
  levels 3–5, colored by the postsynaptic neuron's dimorphism annotation.
  All colored sites are retained; every second gray background site is shown
  for legibility. `local-synapses-provenance.json` records counts and filtering.
- G uses rounded native legend geometry, explicit legend rows, reference-read
  marker shapes and fills, and leader lines to named data points. Approximate
  positions and visual encodings are in `chart-data/scatter-g.json`.
- I shows brain neuropils, VNC leg neuropils and nerves from the released ROI
  meshes. Real arbors and schematic arrows occupy different halves. The named examples use
  actual `AN09B017d` and `LgLG1a` skeletons.
- Every J example has its own anatomical locator and dashed region box.

Panel E now uses MaleCNS L and registered FlyWire right MZ_lv2PN neurons,
which occupy the same physical hemisphere; the former opposite-hemisphere
framing made the arbors too small. Whole-brain locators are now separate framed
insets, rather than independently fitted silhouettes behind the arbors. The
unsupported DA1 locator label is omitted. The zero-count female edge is dashed.

Additional ROI meshes come from the MaleCNS `fullbrain-roi-v4`,
`malecns-vnc-neuropil-roi-v0`, and `malecns-vnc-nerve-roi-v2` layers. Fetching and
source mappings are implemented in `refined_data.py` and `detailed_panels.py`.

## Numerical provenance and differences

This is a visual reconstruction, **not an exact rerun of the paper's analysis**.
The layout follows the supplied pages, but some source selections, cameras,
values and computational methods differ. Both pages visibly identify the reconstruction and include panel provenance
notes. Unsupported bootstrap claims, original pagination/branding, and absent
continued-caption pointers have been removed.

| Panels | How drawn / data source |
| --- | --- |
| First A, E, I, J, M; second B, D, P | Real anatomy, authored schematics and labels. Large sensory groups use recorded display subsets; first M uses recomputed top downstream partners. |
| First B | Exact bilateral counts of 53 unique ORN types in the pinned male/female annotation tables, including unknown sides. Keyed records prevent truncated or duplicated category mappings. Not the paper’s original selection. |
| First D, F bars, G, H, K, L | Native approximate reference readings. G’s r and OLS fit are calculated from the displayed approximate points; marker encodings remain approximations. H makes no bootstrap claim. L uses nulls for missing female observations. |
| First C | Actual receptor-neuron presynaptic coordinates within AL ROIs. Left AL oblique inset; no long axons. |
| First F spatial inset | Observed MaleCNS ALPN presynaptic coordinates in left LH, sampled from public spatial levels 3–5; target annotations set the color. |
| Second A, G, H | Released matched type-connection weights: cumulative curves, deterministic stratified scatter sample including zero-weight gutters, and empirical distributions split by type annotation and fru/dsx expression. Release filters differ from the original plotting analysis. A's endpoint and noise-split percentages are computed from the release table; H explicitly combines dimorphic and sex-specific types, uses max(input,output fraction), and its marginal percentages ≥.3 are recomputed from the same conditional populations. |
| Second C–F | Native worked-example diagrams and literal reference values. |
| Second I, J | Native pies and stacked bars from printed rounded percentages. |
| Second K | Actual sampled male presynaptic positions on dimorphic connections. Color is (male weight − female weight)/(male weight + female weight) at those male positions. **This is a male-coordinate proxy, not the original measured male–female density field.** |
| Second L | Authored illustrative nested partitions with actual final community sizes and band-anchored labels. Intermediate partitions are reconstructed, not the original inferred SBM tree; red counts now describe partitions containing enriched leaves. |
| Second M, O | Released weights aggregated by the 311 published communities; M colors use dominant annotated superclass and one normalization for overview/zoom. O draws the top 80 selected directed aggregate edges, with equal-size nodes and a >15% dimorphic-weight-share color threshold. This differs from the original type-resolution adjacency matrix and graph selection/layout. |
| Second N | Exact released community type counts. |
| Second Q | Approximate manually read proportions. |

`chart-data/reference-transcription.json` contains approximate readings;
`chart-data/computed.npz` contains computed arrays; `computed-provenance.json`
records their sources and methods. Additional chart JSON files record ORN counts,
OLS statistics, label anchors, zoom bounds, CDF marginals and visible network tips. No random fake measurement cloud is used.

## Rebuild

From this Inklet checkout:

```sh
uv pip install --python .venv/bin/python -e '.[render,images,three]' -r examples/inspo/requirements.txt
OPENBLAS_NUM_THREADS=2 .venv/bin/python examples/inspo/recreate.py
```

The default anatomy cache is `out/inspo-recreated/data`, reused from the earlier
source acquisition. Outputs go to `out/inspo-native`, with no dependency on
`inspo/` or `trace-cache/`. Use `--data PATH`, `--output PATH`, `--page
chemosensory|dimorphism`, `--width 210` or `--dpi 300` as needed.

The ZIP includes the modified Inklet library source, a standalone example,
compact numerical arrays, selected anatomical data, and rendered figures.
Install the included unreleased library before rebuilding the unpacked bundle:

```sh
python -m pip install -e './library[render,images,three]' -r source/requirements.txt
OPENBLAS_NUM_THREADS=2 python source/recreate.py --data data --output figures
```

For fresh source acquisition, `fly_data.prepare(Path("data"))` retrieves
missing public datasets (~1.3 GB); the renderer can then derive chart arrays.
The bundle omits the large full weight tables because compact derived arrays
are included. `chart_data.py` documents how to regenerate them from releases.

`canvas.py` provides native drawing primitives; `authored_charts.py` draws the
plots and schematics; `anatomical_panels.py` composes real anatomy;
`anatomy.py` projects physical coordinates; `recreate.py` exports the pages.
The example now exercises new Inklet core authoring APIs; see `docs/scientific-authoring.md`.

## Sources and attribution

- [MaleCNS project and downloads](https://male-cns.janelia.org/download/),
  FlyEM / HHMI Janelia, University of Cambridge, MRC Laboratory of Molecular
  Biology, and Google. MaleCNS data: **CC BY 4.0**.
- Berg et al., *Sexual dimorphism in the complete Drosophila male central
  nervous system connectome*, Cell 189, 5504–5526 (2026),
  [doi:10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015).
- [Published community and connectivity data](https://github.com/flyconnectome/2025malecns),
  pinned to commit `67767d2233657983993ff6c2be48e836a935863c`.
- [FlyWire](https://home.flywire.ai/guidelines) public v783 data:
  **CC BY-NC 4.0**. Credit the FlyWire Consortium; Dorkenwald et al.,
  Schlegel et al., and Matsliah et al. (Nature, 2024), and Berg et al. (2026).
- [FlyWire annotations](https://github.com/flyconnectome/flywire_annotations),
  pinned to commit `8587524c1748ce5ef2080822a2fc890fc03bf597`.
- [navis-flybrains](https://github.com/navis-org/navis-flybrains), meshes and
  display-registration landmarks, pinned to commit
  `273333c8d8bf5adeebebd274e554621462e388bd`. Credit Philipp Schlegel and the
  original mesh/registration contributors. The repository is GPL-3.0;
  template metadata records the originating anatomical datasets.
- Reference layout, labels and approximate numerical readings: the two user-supplied Cell pages. Original paper attribution is retained. This reconstruction does not relicense the paper or datasets.
- Public synapse spatial index: [MaleCNS annotation metadata](https://storage.googleapis.com/flyem-male-cns/v1.0/male-cns-v1.0-synapses-precomputed/info). Decoding follows the [Neuroglancer annotation format](https://github.com/google/neuroglancer/blob/master/src/datasource/precomputed/annotations.md).
