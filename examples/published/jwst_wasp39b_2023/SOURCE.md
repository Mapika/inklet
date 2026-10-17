# Source: JWST WASP-39b, Figure 3 (top panel)

**Paper.** JWST Transiting Exoplanet Community Early Release Science Team
(E.-M. Ahrer *et al.*), "Identification of carbon dioxide in an exoplanet
atmosphere", *Nature* **614**, 649–652 (2023).
DOI: [10.1038/s41586-022-05269-w](https://doi.org/10.1038/s41586-022-05269-w).
Article: <https://www.nature.com/articles/s41586-022-05269-w>.
Figure 3, "Interpretation of WASP-39b's transmission spectrum" (top panel only;
see "Not available as data").

**Caption (Fig. 3, from the article page).** "Top: a comparison of the FIREFLy
reduction and its 1 σ uncertainties (labelled 'Data') to the best-fit ScCHIMERA
theoretical model binned to the resolution of the data (blue curve; Methods).
The key parameters of the model are 10-times solar metallicity, a carbon-to-oxygen
ratio of 0.35 and cloud opacity of 7 × 10⁻³ cm² g⁻¹. The impact of the opacity
sources expected from thermochemical equilibrium over the full bandpass are
indicated by removing the opacity contribution from individual gases one at a time.
... Bottom: the molecular absorption cross-sections for each gas in the best-fit
model. The model is well matched to the data (χ²/N_data = 1.3) ..."

**Licence.** The article page states: "This article is licensed under a Creative
Commons Attribution 4.0 International License, which permits use, sharing,
adaptation, distribution and reproduction in any medium or format, as long as you
give appropriate credit to the original author(s) and the source, provide a link to
the Creative Commons licence, and indicate if changes were made." Licence:
<http://creativecommons.org/licenses/by/4.0/>.

Attribution: JWST Transiting Exoplanet Community Early Release Science Team
(Ahrer *et al.*), *Nature* 614, 649–652 (2023), CC BY 4.0. Figure redrawn with
inklet; the data are the article's Supplementary Information (MOESM1).

**Retrieved.** 2026-10-17.

**DOI note.** The task named Zenodo 10.5281/zenodo.6809899 as the data bundle.
The article cites that DOI only as reference 60 (ExoTiC-LD v2.1, Wakeford & Grant),
not for these spectra, and the bundle's README gives no DOI. The bundle used here
is the article's supplementary file MOESM1 (its ZIP contains `ZENODO/`).

## Downloaded files and URLs

All downloads used `curl -sL -c cj -b cj -A "Mozilla/5.0"`.

| Local (scratch) name | URL | Used for |
|---|---|---|
| `article.html` | https://www.nature.com/articles/s41586-022-05269-w | captions, licence (no data) |
| `original-fig1.png` | https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05269-w/MediaObjects/41586_2022_5269_Fig1_HTML.png | reference only |
| `original-fig2.png` | `…/41586_2022_5269_Fig2_HTML.png` (same prefix) | reference only |
| `original-fig3.png` | `…/41586_2022_5269_Fig3_HTML.png` (same prefix) | reference, comparison |
| `moesm1.zip` | https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05269-w/MediaObjects/41586_2022_5269_MOESM1_ESM.zip | all `data/` files |
| `moesm2.csv` | https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05269-w/MediaObjects/41586_2022_5269_MOESM2_ESM.csv | downloaded; Fig 1 light curves, not used by Figure 3 |

SHA-256 of each original download (`sha256sum`):

```
f0e2db1cd0d214e55f692ff6d3c9b173e29e11b2493d6fdf5b49fce4763b215a  article.html
2ffeee9015d48d03f95d9930fb28a801a8dee846b91b4555334ba0dd2409570d  original-fig1.png
d8eaaec8c9c224218e1d075284b34e3035b10e831029986210ce3d4e52435519  original-fig2.png
7c7fd17f39ac11ff88c7ee1fedb837fd5ea919410f23749b8e9092f2db9ef95e  original-fig3.png
a79be00b58e4fb04fc309375e64a9e065bb7ba9d12591b60177e8cbcccdccc1f  moesm1.zip
4659ee6f6a05b577cf80328edc521b4929f222b0d21a9f368b6fe834b0016492  moesm2.csv
```

Member files of `moesm1.zip` read for Figure 3 (`sha256sum` of the extracted
text, as unpacked from the ZIP into `ZENODO/`):

```
83e5e45d5867f1abe6a8776469d4284daf2630f66b7f67736453d912a6bfdd27  ZENODO/TRANSMISSION_SPECTRA_DATA/FIREFLY_REDUCTION.txt
45d014400577a5208f9f699a7811c0cc95aeb2c4f308583db9e90297f35cca1d  ZENODO/MODEL_FITS/ScCHIMERA_MODEL.txt
759c9bf54f5a6dd368411d6d8b54de87c00b77c1d806d51eda2a4f900ea60f04  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noH2O.txt
7185d9a6cdad35fc24a044d9be346f435dba484739dda31d04dcc1ea4333f191  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noCO.txt
7d41ab15efb4350ecce93f7e646d86cf4bd0fdab559f567d8e3dac51374ff004  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noCO2.txt
881b0ed401f714c141ac048bde8875a627239fcf8615c74fc6a9cac1c9ea730f  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noCH4.txt
e384f355bf77b2f3f1935ed37032576d32c7f41e375ab5552ca3c58ca2e57034  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noH2S.txt
f0542e25f98a643f7119b700c8c32dccaaad1fd2422e80f7b0778faa56688b86  ZENODO/MODEL_FITS/ScCHIMERA_MODEL_noCloud.txt
563b0359d82b57f07bed82c278195348ed7dac203aef736d272b4d07e6e2be31  ZENODO/README
```

## Files in `data/`

Values are copied unchanged; the files only change layout (CSV, named columns).
Transit depth is absolute (Rp/Rs)², as the bundle README states.

| File in `data/` | Origin (`moesm1.zip`, member file; columns) | Panel(s) fed |
|---|---|---|
| `fig3_firefly_data.csv` (95 rows) | `ZENODO/TRANSMISSION_SPECTRA_DATA/FIREFLY_REDUCTION.txt`; `wv_center`→`wavelength_um`, `transit_depth`, `wv_wdth`→`bin_width_um`, `tran_unc`→`transit_depth_1sigma` | Fig 3 top: "Data" points and 1σ error bars; improved panel a |
| `fig3_best_fit.csv` (217 rows) | `ZENODO/MODEL_FITS/ScCHIMERA_MODEL.txt`; `wl [um]`→`wavelength_um`, `Depth`→`transit_depth` | Fig 3 top: "All opacity" curve (cropped to the data range); improved panel a "Best fit" |
| `fig3_remove_one_gas.csv` (95 rows) | `ZENODO/MODEL_FITS/ScCHIMERA_MODEL_no{H2O,CO,CO2,CH4,H2S,cloud}.txt`, each `Depth` column: `no_H2O`, `no_CO`, `no_CO2`, `no_CH4`, `no_H2S`, `no_cloud`; `wavelength_um` = the FIREFLY `wv_center` (identical to every variant file) | Fig 3 top: the six "No X" curves; improved panel b (strips) |

The Figure 3 bottom panel and the scale-height axis have no file in the bundle.

## Processing done in the scripts

1. **Conversion (`scripts/make_data.py`, not committed).** The whitespace and
   tab-separated text files were read with exact decimal parsing
   (`float_precision="round_trip"`) and written as CSV with `repr` precision, so
   the stored numbers equal the file's values. Checked: the `no_*` wavelengths
   equal the variant files' wavelengths exactly.
2. **Units.** Values are multiplied by 100 in the scripts only, to plot transit
   depth in per cent as the published axis does (`PCT = 100`).
3. **Faithful figure (`fig3.py`).** Best-fit curve cropped to the observed
   wavelength range (3.014–5.548 µm), as in the published figure, where it spans
   the data only. Nothing is smoothed, binned or interpolated.
4. **Improved figure (`fig3_improved.py`).** The best fit is linearly interpolated
   (`numpy.interp`) onto the 95 data wavelengths, because the remove-one-gas models
   are on that grid and the best fit is not. Each strip is

   `effect_X(λ) = [fit(λ) − noX(λ)] × 10⁶ ppm`,

   the depth a source adds (positive means it deepens the transit). Interpolation
   check: the interpolated best fit against the FIREFLy data gives χ²/N = 1.29
   (N = 95), matching the published 1.3, so the interpolation does not distort the
   fit. Peaks (computed from the model files, not measured): CO₂ 1,240 ppm at 4.36 µm (> 100 ppm from 4.19 to
   4.67 µm); H₂O 753 ppm at 3.01 µm; clouds 425 ppm at 3.89 µm; CO 191 ppm at
   4.77 µm; H₂S 149 ppm at 3.79 µm; CH₄ 72 ppm at 3.01 µm (mean 3.5 ppm).

## Not available as data

* **Bottom panel of Fig. 3** (molecular absorption cross-sections, log₁₀σ for
  H₂O, CO, CO₂, CH₄, H₂S). No cross-section file is in the bundle, and digitising
  the published curves is not allowed, so the panel is left out.
* **Right-hand "Scale heights" axis.** The bundle gives no zero point for it (the
  1-bar reference radius) and the Fig. 2 caption gives only the 800 km per scale
  height assumption, so the axis cannot be placed from the data. Left out.
* Fig. 2 (the four reductions) and Fig. 1 (light curves) are not part of this
  figure. `moesm2.csv` was downloaded but is not used here.
