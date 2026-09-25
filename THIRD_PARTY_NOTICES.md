# Third-party material

Inklet's original code is covered by [LICENSE](LICENSE). The materials below
retain their own terms. They are example inputs, not dependencies of the core
library. The wheel contains the library and license notices; the source
distribution also includes the examples and their data.

## Colour palette data

Unlike the example material below, these values ship in the library itself,
in `src/inklet/themes/palettes.py` and the generated
`src/inklet/themes/_palette_data.py`. Every `Palette` also carries its source
and licence in its `source` and `license` fields. The dense maps keep an evenly
spaced subset of each published 256-entry table, converted to 8-bit hex; the
subset reproduces the full table within CIEDE2000 1. `tools/gen_palette_data.py`
fetches the pinned sources and checks their SHA-256 hashes.

- **viridis, inferno, plasma, magma**: Nathaniel Smith and Stéfan van der
  Walt, with Eric Firing for viridis. Dedicated to the public domain under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The values
  are taken from matplotlib 3.9.2, `lib/matplotlib/_cm_listed.py`.
- **cividis**: Jamie R. Nuñez, Christopher R. Anderton and Ryan S. Renslow,
  "Optimizing colormaps with consideration for color vision deficiency to
  enable accurate interpretation of scientific data", *PLoS ONE* 13(7):
  e0199239 (2018). The values are taken from the same matplotlib file. The
  map comes from [pnnl/cmaputil](https://github.com/pnnl/cmaputil), under
  this licence:

  ```text
  Copyright (c) 2017, Battelle Memorial Institute

  1.  Battelle Memorial Institute (hereinafter Battelle) hereby grants
  permission to any person or entity lawfully obtaining a copy of this software
  and associated documentation files (hereinafter "the Software") to
  redistribute and use the Software in source and binary forms, with or without
  modification. Such person or entity may use, copy, modify, merge, publish,
  distribute, sublicense, and/or sell copies of the Software, and may permit
  others to do so, subject to the following conditions:

  + Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimers.

  + Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

  + Other than as used herein, neither the name Battelle Memorial Institute or
  Battelle may be used in any form whatsoever without the express written
  consent of Battelle.

  2.  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
  THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
  ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY
  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
  ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
  ```

- **Scientific colour maps** (acton through vik, and the cyclic `…O` maps):
  Fabio Crameri, *Scientific colour maps* version 8.0,
  doi:[10.5281/zenodo.8035877](https://doi.org/10.5281/zenodo.8035877). The
  tables are taken from cmcrameri 1.10. They are used under this licence:

  ```text
  MIT License

  Copyright (c) 2020 Fabio Crameri

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
  ```

- **ColorBrewer** (set1 through ylorrd): Cynthia Brewer, Mark Harrower and
  The Pennsylvania State University, [ColorBrewer 2.0](https://colorbrewer2.org).
  Licensed under the Apache License, Version 2.0; the licence text is in
  [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt). The values are taken
  from `colorbrewer.json` in axismaps/colorbrewer at commit 7d135fc, keeping
  the largest class of each scheme. They were converted from `rgb()` to hex
  and are otherwise unmodified.
- **Paul Tol's schemes** (`tol-*`): Paul Tol, *Colour Schemes*, technical
  note SRON/EPS/TN/09-002, and <https://sronpersonalpages.nl/~pault/>. The
  author states no licence and publishes the values for general use; each is
  cited in `palettes.py`.
- **Okabe-Ito**: Masataka Okabe and Kei Ito, *Color Universal Design*
  (2002, revised 2008). The authors state no licence and publish the values
  as a general recommendation.
- **Machado CVD matrices** (`inklet.themes.color`): Gustavo M. Machado,
  Manuel M. Oliveira and Leandro A. F. Fernandes, "A physiologically-based
  model for simulation of color vision deficiency", *IEEE TVCG* 15(6),
  1291–1298 (2009). The coefficients are transcribed from the authors'
  supplementary page. They were cross-checked against colorspacious, which
  is MIT-licensed.

The `inklet*` palettes are Inklet's own work under its MIT licence. Sources
and terms were checked on 2026-09-25.

## Spot mesh

`stress/meshes/spot.obj` is adapted from Keenan Crane's Spot model, dedicated
under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
The mesh was triangulated, recentered and normalized for rendering tests.

Source and dedication: [Keenan Crane's model repository](https://www.cs.cmu.edu/~kmcrane/Projects/ModelRepository/).
Suggested citation: Crane, K., Pinkall, U. and Schröder, P. (2013),
*Robust fairing via conformal curvature flow*, ACM Transactions on Graphics 32(4).

## Cortical surface mesh

`stress/meshes/brain-lh.obj` is the left cerebral cortical surface from
Neuroscape / Gazzaley Lab, UCSF, hosted at
[NIH 3D, entry 3DPX-000757](https://3d.nih.gov/entries/3DPX-000757).
The entry links to the [CC0 1.0 dedication](https://creativecommons.org/publicdomain/zero/1.0/).
This is a third-party submission with a public-domain dedication, rather than
a claim of US-government authorship. The surface was decimated from 277,894
to 18,000 faces, recentered and normalized into a two-unit cube.

## PDB structure data

`figures/data/1m17-kinase.pdb` is a reduced copy of PDB entry
[1M17](https://www.rcsb.org/structure/1M17), prepared with `tools/strip_pdb.py`.
PDB archive data are available under CC0 1.0 according to the
[RCSB PDB usage policy](https://www.rcsb.org/pages/policies#usage).

Structure authors: Stamos, J., Sliwkowski, M. X. and Eigenbrot, C. (2002),
*Structure of the epidermal growth factor receptor kinase domain alone and in
complex with a 4-anilinoquinazoline inhibitor*, Journal of Biological Chemistry
277, 46265–46272. [Publication DOI](https://doi.org/10.1074/jbc.M207135200).
[Structure DOI](https://doi.org/10.2210/pdb1M17/pdb).

The structure and drug-discovery examples use these coordinates; their
invented compounds and simulated assays are identified in the source and
captions. `gallery/structure.png` is an Inklet render using this structure data.

## Synthetic data and previews

The neural-activity, assay and twenty-panel stress examples generate simulated
observations from fixed seeds. Chemical graphs in `figures/chem_data.py` were
encoded from molecular structural formulas as described in that module.
`stress/assets/mouse.png` is a synthetic test illustration; its sidecar records
provenance. The SEM/TEM-like images under `stress/electro/assets/` are simulated
by `stress/electro/micrograph.py`. They are not experimental micrographs.

Gallery previews and visual-regression baselines are rendered by Inklet from
the retained examples and synthetic fixtures. Original generated artwork is
covered by the project license; underlying third-party data retain the terms
above.

## Fonts and Python dependencies

Font binaries and third-party Python packages are not vendored in this
repository. They are installed separately under their respective licenses.
Inklet can embed font subsets in exports; authors should use fonts whose
licenses permit their intended embedding and redistribution. Regression
previews are raster images, with font identities recorded for reproducibility.

Source terms above were checked on 2026-09-05.

## Showcase furniture (optional download)

The dev2 architectural showcase uses **Modern Arm Chair 01**, by **Vibrant
Nordic**, distributed by Poly Haven under **CC0-1.0**.

- Asset: https://polyhaven.com/a/modern_arm_chair_01
- Licence: https://polyhaven.com/license
- Pinned files and SHA-256 hashes: `examples/showcase/assets.lock.json`

The mesh and textures are downloaded only when requested and stored under
`out/showcase/assets/`; they are not included in the Python package. Generated
architectural gallery images incorporate this asset. The remaining showcase
geometry, scene setup, plots and code are original Inklet work.

## COSEM electron microscopy and organelle segmentations

The real-biology example uses a fixed crop of pyramid level `s4` from
**jrc_hela-3**, provided by the **COSEM Project Team / HHMI Janelia Research
Campus**, under **CC BY 4.0**.

- Data registry and license: https://registry.opendata.aws/janelia-cosem/
- License text: https://creativecommons.org/licenses/by/4.0/
- Publication: Heinrich et al., *Whole-cell organelle segmentation in volume
  electron microscopy*, Nature 599, 141–146 (2021),
  https://doi.org/10.1038/s41586-021-03977-3
- Source objects and checksums: `examples/biology/organelle.lock.json`

`gallery/real-biology.png`, `gallery/oblique-biology.png`, `gallery/slab-biology.png`
and their documented figures are derived
from these data: spatial cropping, intensity windowing, colored mask overlays,
surface extraction, lighting, annotations, oblique resampling, mask-area estimates,
intensity profiles, slab projections, coverage maps, region selections and
quantitative summaries are Inklet example processing.
These derived figures retain **CC BY 4.0**, rather than the
code's MIT license. Attribution appears in the figure and documentation. Raw
volumes, downloaded chunks, generated mesh files and Blender scenes are not
bundled in the repository or wheel; the recipe retrieves the recorded objects.
Accessed 7 September 2026. No endorsement by HHMI or the authors is implied.

## Real fluorescence microscopy example

The `cells3d` two-channel fluorescence data were provided by the **Allen
Institute for Cell Science** and distributed by scikit-image under **CC0**.

- Pinned source and license notice:
  https://gitlab.com/scikit-image/data/-/raw/5c090b56df3988d988ff97928e2ef2d2cbe38e1b/README.md
- CC0 text: https://creativecommons.org/publicdomain/zero/1.0/
- Physical calibration and downsampling:
  https://scikit-image.org/docs/stable/auto_examples/applications/plot_3d_image_processing.html
- TIFF object, SHA-256, axes, channel identities and calibration:
  `examples/biology/cells3d.lock.json`

`gallery/fluorescence-biology.png` is an Inklet-derived figure (MIT, Mark Marosi).
Its processing includes calibrated resampling, explicit channel display windows,
additive RGB compositing, slab projections, Gaussian smoothing, threshold-derived
components, sampled label contours and quantitative summaries. The generated
components are illustrative, without reference annotations or an accuracy claim.
The original data remain CC0; no raw TIFF is bundled in the repository or wheel.
Accessed 7 September 2026. No endorsement by the Allen Institute is implied.

`gallery/label-intensities.png` reuses the same CC0 source. This derived figure
and recipe are MIT, Mark Marosi. They add native, sampled-section and region
intensity tables, population spread and CSV exports using the generated
components above; no additional segmentation validation is implied.

## Natural Earth country maps

`examples/v4/data/world-countries.geojson` and `world-population.csv` are derived
from Natural Earth's Admin 0 countries at 1:110m. Made with Natural Earth. The
map data are [public domain](https://www.naturalearthdata.com/about/terms-of-use/).
The [source manifest](examples/v4/data/world-map-source.json) pins repository
commit `9380cca83db5f9aef52d5e762765100745f84b27`, the input checksum and all
transformations. Antarctica is excluded; retained geometry is not simplified
further. Population estimates and their individual years come from the source
snapshot and are not current estimates. The original example code is MIT.

Source and terms checked on 2026-09-08.

## NIH Visible Human anatomy model

`examples/open_anatomy.py` downloads **Visible Human Heart Vessels and Lungs**,
by **kbrowne**, NIH 3D **3DPX-023212**, version **1.01**.
[Source](https://3d.nih.gov/entries/3DPX-023212?version=1.01) ·
[CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/).
The exact file URL, byte count and SHA-256 are recorded in
[the source manifest](examples/assets/open-anatomy.json).

`docs/assets/scenes/open-anatomy.{png,svg,pdf}` and
`docs/assets/scenes/open-anatomy-highlight.{png,svg,pdf}` are adaptations distributed under
CC BY 4.0. Changes: Blender import, blue-grey material, lighting, cameras and
Inklet vector labels and an explicitly authored upper-region colour selection.
Faces are partitioned without changing their geometry or normals. Source
geometry and proportions are retained; no calibrated
physical dimensions or individual vessel identities are asserted. Original
example Python code is MIT. Source license checked on 2026-09-14.
