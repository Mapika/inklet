# Inklet: three-paper reproduction audit

**Dev15 follow-up:** the core now provides `vector='seamless'`, explicit
bilinear scalar interpolation for raster fields, `Panel.placed`, `Panel.guide`,
independent legend ordering/gaps, inset colorbars and `FigureReview.save_bundle`.
The recipes use these APIs. Shared axes were already supported by `facets` and
now have a worked guide in `docs/complex-figures.md`.

The new six-map vector export is about 13 MB and takes 16 seconds versus the
47 MB / 28 second baseline below. PDF size grows from 1.1 MB to 5.2 MB.
Foreground cell boundaries now remain exact; no 30% cell overlap is used.
Underpaint suppresses background-colored antialiasing cracks. Smooth scalar
interpolation is separately opt-in and raster-only; this release does not add
SVG/PDF gradient meshes or full TeX typesetting.

Native review bundles include verified source hashes, all 43 data rectangles and
separate diagnostic overlays. A 0.8 mm outer margin protects edge lettering;
the inset colorbar typography was raised above the 5 pt diagnostic minimum.
Reference attribution and the source/publication ambiguities below still apply.

The remainder records the original audit and baseline.

Built and visually compared all three figures, covering 43 axes. The recreations
use released data, editable vector marks and native text. SVG, PDF and PNG exports
are available in the comparison page. These are close reproductions, not
pixel-identical copies. Numerical/source checks do not certify visual identity.

| Figure | What was reproduced | Remaining differences |
| --- | --- | --- |
| Nature viral evolution, Fig. 4 a–k | All 11 country pairs; frequency curves; fitness means and minimum/maximum bands; missing-data gaps; local/global lineage keys; shared calendar | Font metrics, line weights, date-label spacing and some vertical axis limits differ slightly. Limits are derived from the released values, with the published Denmark fitness range supplied explicitly. |
| Nature Chemical Engineering protein engineering, Fig. 4 a–f | All 15 axes; all 1,352 sequence predictions for each agent; highlighted trajectories; unified-model and pairwise correlations; 10 °C sliding uncertainty windows; chosen-sequence percentile traces; all 5,408 final scatter samples | Publication typography and some traces do not match pixel for pixel. Agent 2's third highlighted sequence, 6311, is inferred from the visible trajectory and released predictions; the author's older script lists only two highlights. Percentile traces follow the released workbook and author rank formulas, rather than digitizing the image. |
| Nature Communications quantum response, Fig. 5 a–f | All 240,000 released samples; six nine-decade log–log domains; individual maxima/normalization; diagonal guides and annotations; shared normalized key | Native cells remain discernible at high zoom; the reference uses a smoother continuous appearance. The color map is reconstructed from 65 color-key samples. Serif/math styling and some annotation sizes differ. |

No quantitative marks were traced from screenshots, invented or substituted
with synthetic data. An initially considered neuronal-mapping figure was rejected
because the accessible source workbook omitted the plotted raster and heatmap
arrays. Source completeness is a selection constraint, not an Inklet limitation.

**Confirmed Inklet limitation: dense, seamless vector heatmaps.** The batched
matrix mode preserves exact cell boundaries but can show antialiasing seams.
Six 200 × 200 maps took about 9 seconds and produced a 6.4 MB SVG in that mode.
The final native-cell version uses 30% cell overlap to substantially suppress
those seams; it takes about 28 seconds and produces a 47 MB SVG. Overlap slightly
expands the displayed footprint of samples and is not a scientific interpolation.
The original smooth field is therefore only approximated. Raster heatmaps are
already supported, but sacrifice per-cell editability. A seamless tiled/mesh
export path with bounded memory is the highest-priority improvement exposed here.

**Authoring friction: precise plot-area placement.** My initial helper incorrectly
positioned panels by their complete bounds, shifting data rectangles when axis
furniture differed. Inklet already exposes `plot_area()` and area anchors; using
that API fixed the error. This is not missing alignment support. A concise,
documented “place this data rectangle here” recipe would make such mistakes less
likely when matching an existing plate. The existing figure/mosaic APIs should
remain the default for new figures.

**Authoring friction: shared furniture and scientific text.** Independent
multi-column legend orders, small embedded color keys, rotated line annotations,
mixed serif/sans typography and fixed publication dimensions were achievable.
This reconstruction still required substantial measured placement in the recipes.
Inklet already supports italic faces and native sub/superscript markup; their
presence should not be mistaken for full TeX math layout. Better high-level
recipes for multi-row shared axes, in-panel keys and labels attached to data
guides would reduce the manual work. This audit does not establish that every
existing layout or legend API is insufficient.

**Review improvement: distinguish numerical and graphical fidelity.** The local
review page keeps the original and recreation together at full resolution.
`review.py` checks source hashes, expected axis/sample counts, six response maxima,
SVG image absence and export signatures. Recorded correlations and percentile
values are available in the JSON reports. It does not compare every plotted
coordinate independently or automate collision detection. A reusable figure
review command that combines source provenance, plot-area checks and panel-level
visual comparisons would make future regressions easier to catch.

Prioritize: (1) seamless dense fields with smaller editable exports; (2) simpler
precise placement/shared-furniture recipes; (3) reusable provenance and visual
review reports. These figures exercise dense quantitative plotting particularly
well. They do not newly validate molecular cartoons, microscopy segmentation,
3D anatomy, Sankey diagrams or every other kind of heterogeneous scientific plate.

Paper attribution and source URLs are in `sources.json` and the comparison page.
All three articles identify their content as CC BY 4.0; the reproductions redraw
and retypeset that material. Original figures and author data remain credited to
Raharinirina et al., Rapp et al. and Denton et al., respectively.
