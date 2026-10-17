# Notes: WHO excess mortality (Msemburi et al. 2023), Figures 1, 2 and 5

## Outputs and lint

Each script writes `.svg`, `.pdf` and `.png` (200 dpi) to `gallery/published/`,
with the prefix `who_excess_2023_`. Sizes are from the SVG headers.

| Script | Output | Size (mm) | `figure.report()` |
|---|---|---|---|
| `fig1.py` | `who_excess_2023_fig1.*` | 89 × 110.8 (single column) | `inklet lint: clean, 0 diagnostics` |
| `fig1_improved.py` | `who_excess_2023_fig1_improved.*` | 89 × 86.2 (single column) | `inklet lint: clean, 0 diagnostics` |
| `fig2.py` | `who_excess_2023_fig2.*` | 183 × 139.7 (double column) | `inklet lint: clean, 0 diagnostics` |
| `fig2_improved.py` | `who_excess_2023_fig2_improved.*` | 183 × 135.1 (double column) | `inklet lint: clean, 0 diagnostics` |
| `fig5.py` | `who_excess_2023_fig5.*` | 183 × 137.3 (double column) | `inklet lint: clean, 0 diagnostics` |
| `fig5_improved.py` | `who_excess_2023_fig5_improved.*` | 183 × 115.3 (double column) | `inklet lint: clean, 0 diagnostics` |

Every script sets `expected_fonts=("Arial", "Helvetica", "Liberation Sans")` in the
Nature preset, because Arial is not installed here. See ISSUES-who_excess_2023.md, item 1.

Figure 1 is 89 mm wide, which matches the original's text scale. Figures 2 and 5 are
183 mm wide, which matches their label scale. Heights follow the original aspect
ratios (1243/1047 for Fig. 1, 1082/1394 for Fig. 2, 1039/1421 for Fig. 5) to within
about 3%.

### Key numbers, checked against the paper

* Fig. 1a, December 2021: cumulative reported deaths 5,420,534 (5.42 M). Cumulative
  excess 14,834,866 (14.83 M), 95% interval 13,231,107 to 16,580,230 (13.23 to 16.58 M).
  The Results text reads "14.83 million excess deaths with an uncertainty interval (UI)
  of 13.23 million to 16.58 million ... 5.42 million COVID-19" reported. Match.
* Fig. 1b: the excess rate peaks at 22.2 per 100,000 in May 2021 (the original's peak
  is about 22). It is negative from about February to June 2020, with a minimum of −2.9
  in April 2020. The reported rate peaks at 5.5 in January 2021.
* Fig. 2: the Global P-score peaks at 37.9% in May 2021. South-East Asia peaks at 121.4%
  in May 2021 (95% interval 100.6% to 146.2%). The original shows the same peak, about
  122% by eye.
* Fig. 5: Peru 97.1% (94.4 to 99.5), Ecuador 50.6%, Bolivia 48.8%. The Results text
  gives "97%", "51%" and "49%". Match.

## Figure 1

### Matches the original

* Two stacked panels: a (cumulative deaths in millions, ticks 0 to 15) and b (death
  rate per 100,000, ticks 0, 10 and 20). Panel letters a and b.
* Time from January 2020 to January 2022, with the original tick labels ("January
  2020", "July 2020", "January 2021", "July 2021", "January 2022").
* Series and colours: reported in red, excess in purple, 95% bands shaded. Key below
  each panel, in the original's order (reported first).
* Data are the workbook values. The only transformation is dividing deaths by 10⁶ for
  panel a.

### Differs, and why

* Font is Liberation Sans, not Arial (metrically compatible). See the note above.
* Axis ranges are read from the original's axis positions: panel a is −1.3 to 17.0 and
  panel b is −5.9 to 27.2. The ticks match.

## Figure 2

### Matches the original

* Seven panels in the same order and layout: four across the top (Global, African,
  Region of the Americas, Eastern Mediterranean), three below (European, South-East
  Asian, Western Pacific), with the empty eighth cell.
* Titles as in the original. The original's ggplot-style colours are used (#F8766D,
  #C49A00, #53B400, #00C094, #00B6EB, #A58AFF, #FB61D7). The 0% line is dashed. Ticks
  are two-line labels: "January / 2020", "October / 2020", "July / 2021". Values are in
  per cent.
* A shared y range of −44 to 158 (the original's spines) and the same x range.
* A mean line with a 95% band in each panel, in that panel's colour.

### Differs, and why

* The original has one "Month Year" under the bottom row and one "P-score (%)" at the
  left. The faithful version repeats the x-title under each bottom-row panel and the
  y-title under each left-column panel, because inklet has no single label under a
  grid. ISSUES item 4.
* Band opacity is the library default, not the original's.

### Shared or free y scale (decision)

**Shared.** All seven panels use the same y range. The faithful version uses −44 to
158 and the improved version −40 to 160. Reasons:

1. The Global line appears in every regional panel as a reference. A grey line means
   the same thing only if the scale is the same.
2. The figure's message is comparative: which region had the largest excess relative
   to expected, and when. South-East Asia's peak (121%) is about three times the Global
   peak (38%). On a free scale it would look as large as the others.
3. The cost is real. Western Pacific (range about −11 to 15%) is compressed to about 7 mm
   of a 52 mm panel, and the African region (about −12 to 27%) to about 10 mm. The
   improved version compensates with taller panels (52 mm), a solid 0% line and more
   visible bands. Its South-East Asian peak is labelled "121%", since that value sets
   the top of the range.

A free scale was rejected because it would break the Global reference and make regions
look equal in size.

## Figure 5

### Matches the original

* Ordered from the highest to the lowest mean P-score. Country names on the left. Mean
  as a grey dot with a black outline, and the 95% interval as a black whisker with end
  caps. The P-score axis has ticks at 25, 50, 75 and 100%, and runs from about 13% to
  104%, measured from the original image.

### Differs, and why

* **22 of the 25 rows are drawn, and the rows differ from the figure.** The workbook
  and the printed figure do not contain the same countries. The workbook has Andorra
  (29.3%), San Marino (28.1%) and Saint Vincent and the Grenadines (26.2%), which the
  figure does not show. All three are well under 200,000 in population, which the
  caption excludes. The figure has Kuwait, Lebanon and the Republic of Moldova (each
  about 23%), which the workbook does not contain. Only the 22 countries common to both
  are drawn, in the figure's order. The three figure-only countries cannot be drawn
  without digitising the image, which was not done. Values for the 22 agree with the
  figure to the precision of the image (for example Georgia 23.6%, 18.8 to 29.3; Brazil
  24.2%).
* The original's x-axis starts at about 13%, not the 20% in the brief. Measured from the
  PNG, the left spine is about 12 points left of the 25% tick, and the faithful version
  keeps that start.
* Font as in Figures 1 and 2.

## Improved versions

### Figure 1 (`fig1_improved.py`)

1. **"Month Year" axis title removed.** The year ticks say what the axis is.
2. **Bulky date labels replaced.** The original's "January 2020" labels are now "2020",
   "2021" and "2022", at each January, with faint year gridlines through both panels.
3. **Key below each panel replaced by direct labels.** The original's key sat under each
   panel, far from the lines. Each series now carries its December 2021 value at its
   end ("Excess 14.8 M", "Reported 5.4 M" in a; "Excess 7.4", "Reported 2.8" in b).
4. **Panels on a common time axis.** `share_plot_margins=True` aligns the data edges.
   Both panels share the x range and gridlines, so a month can be read down the page.
5. **Colour-blind-safe pair.** Red and purple are hard to tell apart with deuteranopia.
   The new pair is Okabe-Ito blue (#0072B2) for excess and vermilion (#D55E00) for
   reported. The vermilion text uses a darker shade (#a64200) to meet the 4.5:1 contrast
   rule.
6. **Zero reference in panel b.** The excess rate is negative in 2020, and a grey zero
   line makes that readable.
7. **Band explained in place.** "Shaded: 95% uncertainty interval" sits in panel a where
   the key's band swatch was.
8. **Plainer y titles.** "Deaths (millions)" replaces "Deaths (×10^{6})", and "Death rate
   per 100,000" replaces "Death rate per 100,000 population".

Kept: both panels, both series, all 95% intervals, the panel order, and the same data.

### Figure 2 (`fig2_improved.py`)

1. **One colour for the regions.** The original gave each panel its own rainbow hue,
   which carries no meaning, and the title already names the region. The regional
   series is now Okabe-Ito blue throughout.
2. **Global as a faint reference in every regional panel.** The original had no
   baseline, so readers compared panels from memory. Global is now a light grey line with
   a faint band in each regional panel. The Global panel itself is blue.
3. **Clear 0% line.** The original's dashed line was faint against the bands. It is now
   a solid dark line.
4. **Visible uncertainty bands.** The band opacity is set to 0.35 (the default is a
   lighter tint). The original's bands were hard to see at print size.
5. **Year ticks.** The two-line "January / 2020", "October / 2020" and "July / 2021" labels
   are replaced by "2020", "2021" and "2022", with minor ticks. The "Month Year" title is
   dropped.
6. **Shared scale kept, and justified.** See "Shared or free y scale" above.
7. **One key in the empty cell.** Where the original left a blank cell, the improved
   version puts four lines of encoding: blue region, blue band, grey Global, black 0%
   line. The lines are left-aligned.
8. **Peak labelled.** South-East Asia's peak is labelled 121%, the value that sets the top
   of the range.
9. **Taller panels** (52 mm, from 50 mm in the faithful version) for a little more
   resolution on the shared scale.

Kept: all seven panels, every interval, the shared scale and the same data.

### Figure 5 (`fig5_improved.py`)

1. **Axis starts at 0%.** The original starts at about 13%, which exaggerates the
   differences between countries near the bottom. Zero is a meaningful P-score
   (no excess).
2. **More ticks.** 0, 20, 40, 60, 80 and 100%, with minor ticks every 10%. The original
   had only 25, 50, 75 and 100%.
3. **Values written beside each interval.** Each mean is printed after its upper whisker
   ("97%", "51%"), so the reader does not have to estimate it from the axis. The values
   match the Results text.
4. **One colour.** The grey dots and black whiskers become blue, as in Figure 2, and
   light vertical gridlines help the eye across the 20% steps.
5. **The same 22 rows** as the faithful version, for the reason given under "Differs".

## Not verified

* Original colours were read by eye from the PNG, not sampled.
* Original positions in Figure 5 were read by eye, not measured. The 13% start of the
  x-axis is an estimate from the spine and tick positions, good to about a point.
* The paper's text was checked only for the numbers listed above.
