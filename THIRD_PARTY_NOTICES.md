# Third-party material

Inklet's original code is covered by [LICENSE](LICENSE). The materials below
retain their own terms. They are example inputs, not dependencies of the core
library. The wheel contains the library and license notices; the source
distribution also includes the examples and their data.

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
