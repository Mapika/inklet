# Source: ATLAS Higgs couplings, Figure 5

**Paper.** ATLAS Collaboration, "A detailed map of Higgs boson interactions by the
ATLAS experiment ten years after the discovery", *Nature* **607**, 52–59 (2022).
DOI: [10.1038/s41586-022-04893-w](https://doi.org/10.1038/s41586-022-04893-w).
Article: <https://www.nature.com/articles/s41586-022-04893-w>. Figure 5.

**Data.** HEPData record `ins2104706` (version 1), doi
[10.17182/hepdata.130266](https://doi.org/10.17182/hepdata.130266), tables 5
("Figure 5 without $\kappa_{c}$") and 6 ("Figure 5 with $\kappa_{c}$"). Downloaded
from <https://www.hepdata.net/download/submission/ins2104706/1/yaml>.

**Licence.** The article page states: "This article is licensed under a Creative
Commons Attribution 4.0 International License". The HEPData record is released under
CC BY 4.0. Attribution: ATLAS Collaboration, "A detailed map of Higgs boson
interactions by the ATLAS experiment ten years after the discovery", *Nature* 607,
52–59 (2022), data from HEPData doi:10.17182/hepdata.130266 (CC BY 4.0).

**Retrieved.** 2026-10-17. The archive was fetched by an earlier session step, not by
the session that wrote these scripts; the sha256 below was checked against the file
in the scratch directory.

## Downloaded files

| File | URL | Retrieved | sha256 |
|---|---|---|---|
| `HEPData-ins2104706-v1-yaml.tar.gz` | <https://www.hepdata.net/download/submission/ins2104706/1/yaml> | 2026-10-17 | `b98306b08f1462c1418cae438bc1b7a812ea92940f1dcbd7a88bb0747ef6806e` |

The two data files were extracted from that archive (`HEPData-ins2104706-v1-yaml/`)
and copied unchanged. Their SHA-256 values are:

```
62ff4109de0f5def02945797354ea74741fc26c46484900142248cb2cb2511eb  figure_5_without_kc.yaml
229ab1414b7e4da21f8b6ebff82d2e12580d76378783eccd4283f555ef6a92db  figure_5_with_kc.yaml
```

The `submission.yaml` mapping was checked by hand. Each `data_file:` line is in the same
YAML document as its `name:` line, so "Figure 5 without $\kappa_{c}$" is
`figure_5_without_kc.yaml` and "Figure 5 with $\kappa_{c}$" is `figure_5_with_kc.yaml`.

## Files in `data/`

| File | HEPData table | Origin | Panels fed |
|---|---|---|---|
| `figure_5_without_kc.yaml` | t5, "Figure 5 without $\kappa_{c}$" (`data_file` of that document) | HEPData ins2104706 v1, table 5 | Fig 5 top (filled circles, κ_c = κ_t) and bottom (κ_c = κ_t) |
| `figure_5_with_kc.yaml` | t6, "Figure 5 with $\kappa_{c}$" (`data_file` of that document) | HEPData ins2104706 v1, table 6 | Fig 5 top and bottom (grey crosses, κ_c free; κ_c also in both panels) |

Each file has, per particle: the particle mass (GeV), the value
κ_F m_F/vev or √κ_V m_V/vev, the coupling modifier κ, and the asymmetric
uncertainties of both (`asymerror` minus/plus). The independent-variable labels
give the particle. Both tables are used; no other table from this record is plotted.

## Processing

* Values, errors and masses are read exactly as published. No value is recomputed.
  The error bar lower and upper distances are `-minus` and `plus`.
* The SM line is y = m/vev, with **vev = 246.0 GeV**. The caption gives "vev = 246
  GeV", and the table values reproduce it: κ·m/vev with the tabulated κ returns 246.00
  GeV for the fermions (for example τ: 0.92166 × 1.777 / 0.0066577 = 246.00). The earlier
  note's 246.22 GeV does not match the data.
* Labels in the key-table inset are typeset from the paper's Figure 5 (the
  particle names, which are figure text, not data).
* The κ_c best fit (0.031, interval 0 to 3.06) is drawn as an arrow, not as a point, in
  the bottom panel. In the top panel its lower bound of 0 is not representable on a log
  axis; the whisker is drawn down to the bottom of the panel, and the scripts say so.
* The improved version shifts scenario markers horizontally by ±5% of mass (see
  NOTES.md). The values are not moved.

## Not available as data

* The p-values, 56% (κ_c = κ_t) and 65% (κ_c free), are stated in the HEPData
  description only. They are not plotted, and no figure element depends on them.
* The SM curve is a function (m/vev), not a table entry.
* The lepton/quark particle table (the tiles in the faithful version) is a figure
  legend. It is redrawn from the original image, not from data.
* The stacked-fraction axis label in the original is typeset as text.
