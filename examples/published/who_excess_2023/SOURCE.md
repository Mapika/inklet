# Source: WHO excess mortality, Figures 1, 2 and 5

**Paper.** Msemburi, W. *et al.*, "The WHO estimates of excess mortality
associated with the COVID-19 pandemic", *Nature* **613**, 130–137 (2023).
DOI: [10.1038/s41586-022-05522-2](https://doi.org/10.1038/s41586-022-05522-2).
Article: <https://www.nature.com/articles/s41586-022-05522-2>.

**Figures used.** Figure 1 (global cumulative and monthly death rates), Figure 2
(global and WHO-region P-scores by month) and Figure 5 (the 25 countries with
the highest mean P-scores). Figures 3, 4 and 6 are not recreated.

Captions, as published on the article page:

* Fig. 1: "a, Cumulative global excess death estimates and the cumulative
  reported COVID-19 deaths by month from January 2020 to December 2021. b,
  Global excess death rates per 100,000 population and the reported COVID-19
  death rates per 100,000 population, also by month ... On both plots, the
  central lines of the excess mortality series show the mean estimates and the
  shaded regions indicate the 95% uncertainty intervals."
* Fig. 2: "Monthly estimates of P-scores, expressed as a percentage, aggregated
  globally and for the six WHO regions for the period January 2020 to December
  2021. All plots show the mean estimates and the 95% uncertainty intervals."
* Fig. 5: "The plot shows the 25 countries with the highest mean P-scores for
  years 2020 and 2021 after ranking all WHO member states with populations
  greater than 200,000 by mean P-score from highest to lowest. The mean for each
  country is shown using the central grey dots and the widths of the bars show
  the 95% uncertainty intervals."

**Licence.** The article page states: "Creative Commons Attribution 4.0
International License, which permits use, sharing, adaptation, distribution and
reproduction in any medium or format, as long as you give appropriate credit to
the original author(s) and the source, provide a link to the Creative Commons
licence, and indicate if changes were made." The article is therefore CC BY 4.0.
Attribution: Msemburi, W. *et al.*, Nature 613, 130–137 (2023),
doi:10.1038/s41586-022-05522-2, CC BY 4.0.

**Retrieved.** 2026-10-17.

## Downloaded files

| Downloaded file | URL |
|---|---|
| article page | <https://www.nature.com/articles/s41586-022-05522-2> |
| original Fig. 1 image (used for checking only, not committed) | <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_Fig1_HTML.png> |
| original Fig. 2 image (checking only) | <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_Fig2_HTML.png> |
| original Fig. 5 image (checking only) | <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_Fig5_HTML.png> |
| Source Data, Fig. 1 | <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_MOESM4_ESM.xlsx> |
| Source Data, Fig. 2 | <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_MOESM5_ESM.xlsx> |
| Source Data, Fig. 5 | <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05522-2/MediaObjects/41586_2022_5522_MOESM8_ESM.xlsx> |

The downloads are kept outside the repository. They are not committed.

## Files in `data/`

| File | Origin (workbook, sheet) | Panel(s) it feeds |
|---|---|---|
| `fig1-panelA-cumulative.csv` | MOESM4_ESM.xlsx, sheet "Panel A cumulative" (24 rows, columns `location, year, month, cumul.rep.covid, cumul.excess.mean/low/high`) | Fig. 1a, both faithful and improved |
| `fig1-panelB-rate.csv` | MOESM4_ESM.xlsx, sheet "Panel B rate" (24 rows, columns `location, year, month, rep.covid, excess.mean/low/high`) | Fig. 1b, both versions |
| `fig2-pscore.csv` | MOESM5_ESM.xlsx, the seven sheets "Global", "African Region", "Region of the Americas", "Eastern Mediterranean Region", "European Region", "South-East Asian Region", "Western Pacific Region", stacked in that order (168 rows; columns `region, year, month, pscore_mean, pscore_low, pscore_high`) | Fig. 2, all seven panels, both versions |
| `fig5-top25.csv` | MOESM8_ESM.xlsx, sheet "Countries Top Pscore" (25 rows; columns `Country, iso3, pscore_mean, pscore_low, pscore_high`) | Fig. 5, both versions (22 of its 25 rows are drawn; see NOTES.md) |

## SHA-256 of the original downloads

```
78c9a847ae9630f8264d2f84eac1f4cc7941adf57bc9aba164b71bfc2138425c  MOESM4_ESM.xlsx
00c1d7ae5d3acb7a66a6ae566d7921756b27e6ce2f69d7d9d2f80067af48c475  MOESM5_ESM.xlsx
b010a5baf5c1db8872ae176bd15b6443652fa073287913e842c6907941985145  MOESM8_ESM.xlsx
c447ae39f472e706ecd9a3fb66c425a9c5bad5245466278a97e48d9db13e6cdd  41586_2022_5522_Fig1_HTML.png
fd1f3316e27cdb3a8710bf138bc477771da0f163d8ae57fc46597c4bd4c7062d  41586_2022_5522_Fig2_HTML.png
e7833a76e3a936f765bbeee2acc2c7ffd1254f482a1fea1554d9b7a6037c302f  41586_2022_5522_Fig5_HTML.png
21c3c8eff14ff398d4868f609a2a37a826c7c647419b8c48a86243e8639cf918  article.html
```

## Processing done

1. Each workbook was read with `openpyxl` in normal (not read-only) mode with
   pandas `read_excel`. Values are unchanged. The `year` and `month` columns
   were cast from float to integer and written with `to_csv(index=False)`.
2. `fig2-pscore.csv` stacks the seven Figure 2 sheets in the workbook's order,
   keeping the region name in a column. The values are fractions, as in the
   workbook (0.10 = 10%). The figure scripts multiply by 100 for display.
3. Dates. Each row is one calendar month. The scripts place it at
   `year + (month - 1) / 12`, so January 2020 is 2020.0 and December 2021 is
   2021.917.
4. Units. Fig. 1a cumulative deaths are plotted in millions (divided by 10⁶).
   Fig. 1b rates are plotted as published, per 100,000 population. Fig. 5
   values are multiplied by 100 to give per cent.
5. Nothing is interpolated, smoothed, digitised or added. The only row
   selection is Figure 5's, described in NOTES.md.

## Not available as data

* Figure 1: the workbook gives the mean and the 95% interval for the excess
  series and the reported series. Nothing else is in it. All the panels are
  reproduced.
* Figure 5: the workbook's 25 rows do not match the printed figure. Three rows
  (Andorra, San Marino, Saint Vincent and the Grenadines) are in the workbook
  but not in the figure. Three figure rows (Kuwait, Lebanon, Republic of
  Moldova) are not in the workbook. Their values cannot be recovered without
  digitising the image, which was not done. See NOTES.md.
* Figures 3, 4 and 6 (country and choropleth maps) are not in these workbooks
  and are not recreated.
