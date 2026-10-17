# Source: Marek, Tervo-Clemmens et al. (2022), Figure 1

**Paper.** Scott Marek, Brenden Tervo-Clemmens, Finnegan J. Calabro, *et al.*,
"Reproducible brain-wide association studies require thousands of
individuals", *Nature* **603**, 654–660 (2022). Published 16 March 2022.
DOI: [10.1038/s41586-022-04492-9](https://doi.org/10.1038/s41586-022-04492-9).
Article: <https://www.nature.com/articles/s41586-022-04492-9>. Figure 1.

**Licence.** The article page states: "This article is licensed under a
Creative Commons Attribution 4.0 International License, which permits use,
sharing, adaptation, distribution and reproduction in any medium or format, as
long as you give appropriate credit to the original author(s) and the source,
provide a link to the Creative Commons licence, and indicate if changes were
made." Attribution: Marek *et al.*, *Nature* 603, 654–660 (2022),
https://doi.org/10.1038/s41586-022-04492-9, CC BY 4.0.

**Retrieved.** 2026-10-17.

## Downloads

| File (in scratchpad, not committed) | URL | SHA-256 |
|---|---|---|
| article page (licence, caption, text) | <https://www.nature.com/articles/s41586-022-04492-9> | not hashed (HTML page) |
| `original-fig1.png` (1404 × 1211 px) | <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-04492-9/MediaObjects/41586_2022_4492_Fig1_HTML.png> | `dafd10743ab422260bfa15ecf1cf42db88b6d0dfc873d7e5a092a51ecfe1da7a` |
| `source.xlsx` (Source Data Fig. 1, 3.9 MB) | <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-04492-9/MediaObjects/41586_2022_4492_MOESM4_ESM.xlsx> | `cc797e96d815377f52d341dd9e796104e82972c69a1ee9b6993a4a14ebc247cd` |

The article's own "Source Data Fig. 1" link points to `MOESM4_ESM.xlsx`.

## Files in `data/`

Written by a one-off conversion of `source.xlsx` (see Processing). Values are
unchanged; blank cells stay blank. Sizes total about 1.8 MB.

| File | Origin (workbook sheet) | Panel(s) it feeds |
|---|---|---|
| `fig1a_thickness_r.csv.gz` | sheet `A`: 59,412 × 6; columns Vertex/ROI/Network for cognition and psychopathology (ROI 333 values, network 13 values; other cells blank) | a |
| `fig1b_rsfc_r.csv.gz` | sheet `B`: 77,421 × 6; columns Edge/Component/Network for cognition and psychopathology (Component 100, Network 105 values) | b |
| `fig1e_thickness_cognition.csv` | sheet `E_left`: 1,000 resamples × 16 sample-size bins | e, left (cognition) |
| `fig1e_thickness_psychopathology.csv` | sheet `E_right`: 1,000 × 16 | e, right (psychopathology) |
| `fig1f_rsfc_cognition.csv` | sheet `F_left`: 1,000 × 16 | f, left |
| `fig1f_rsfc_psychopathology.csv` | sheet `F_right`: 1,000 × 16 | f, right |
| `fig1g_thickness_cognition.csv` | sheet `G_left`: 3,604 rows; `DMN_25_1, Cog_25_1` and `DMN_25_2, Cog_25_2` (25 values each), `DMN_fullsamp, Cog_fullsamp` (3,604) | g, left |
| `fig1g_thickness_psychopathology.csv` | sheet `G_right`: as above with `Psy_*` | g, right |
| `fig1h_rsfc_cognition.csv` | sheet `H_left`: 3,928 rows; `DMN_25_*`, `Cog_25_*` (25 each), `DMN_fullsamp`, `Cog_fullsamp` (3,928) | h, left |
| *(none)* | sheet `H_right`: **header row only** (see below) | h, right: not drawn |
| *(none)* | sheets `C`, `D`: per-ROI/network mean \|r\| for the brain maps | c, d: not drawn |

`_data.py` loads these files; the figure scripts read nothing else.

## Sheet H_right is empty

Loaded in normal (non-read-only) mode with openpyxl, `H_right` has
`max_row = 1`: only the header `DMN_25_1, Psy_25_1, DMN_25_2, Psy_25_2,
DMN_fullsamp, Psy_fullsamp`. The raw XML (`xl/worksheets/sheet12.xml`) confirms
it: `<dimension ref="A1:F1"/>` and a single `<row r="1">`. So the scout's
"1 row" is correct and it is the header, not data. Panel h (right,
RSFC and psychopathology) therefore cannot be drawn from this file and is left out.

## Processing

1. Opened `source.xlsx` with `openpyxl.load_workbook` in normal mode (not
   read-only). Read each sheet's values row by row.
2. Written to CSV with Python's `csv` module, each float as its shortest
   round-trip `repr` (no rounding). Blank cells are written empty.
3. Sheets `A` and `B` have a header row; kept as is. Gzipped with
   `gzip` level 9, mtime 0, because each text file exceeds 1 MB.
4. Sheets `E_*` and `F_*` have **no header row**: row 1 is data (1,000 rows in
   total). A header of sample-size labels was added: `n=25, n=33, n=50, n=70,
   n=100, n=135, n=200, n=265, n=375, n=525, n=725, n=1000, n=1430, n=2000,
   n=2800`, then the 16th bin: `n=3604` for thickness, `n=3928` for RSFC. The
   bin list is the caption's (16 values). The workbook's annotation cells in
   columns R and S ("rows = resamples", "columns = sample size bins") were
   dropped.
5. The 16th bin label is a judgement. The caption says "3,604 (3,928 for
   cortical thickness)", but the data say the reverse: `G` (thickness) has
   3,604 full-sample rows and `H` (RSFC) has 3,928, and the legends of panels
   g and h print n = 3,604 and n = 3,928 for those panels. So thickness uses
   3,604 and RSFC 3,928. The check: the column SD of each sheet falls as
   1/√n (25 → 0.20, 2,800 → 0.019), and the last column is within noise of
   either value, so the workbook cannot settle it.
6. `G_*` and `H_left` keep their original headers and blank cells. Each sheet
   holds the two n = 25 subsamples (25 values per column pair) and the
   full sample (3,604 or 3,928 rows).
7. Sheets `C` and `D` are not converted: they feed the brain maps, which are
   not drawn.

## Not available as data

* **Panels c and d** (brain surfaces of mean |r| by ROI and network): need the
  atlas and the per-ROI geometry, which the source data do not contain. Left out.
* **Panel h, right** (RSFC vs psychopathology scatter): sheet `H_right` is empty.
* **Full-sample points** in g and h: the workbook has them (3,604 and 3,928 values),
  but the original does not plot them; only the full-sample fit is drawn.
* **Sample-size labels** for the 16 resample columns and the `E/F` headers:
  not in the workbook; taken from the caption (see Processing 4–5).
* **Confidence-interval method** for the dashed lines in e and f: not stated in
  the caption or methods excerpt; see NOTES.md.
* **Values quoted in the text that are not in these sheets**: the 11 million
  associations behind "median |r| = 0.01" and "top 1% > 0.06"; the out-of-sample
  |r| = 0.16; the split-half n = 1,964 figure; all Supplementary Figures.
