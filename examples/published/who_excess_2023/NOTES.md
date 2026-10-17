# Notes: WHO excess mortality (Msemburi et al. 2023), Figures 1, 2 and 5

## Outputs and lint

Each script writes `.svg`, `.pdf` and `.png` (200 dpi) to `gallery/published/`,
with the prefix `who_excess_2023_`. Sizes are from the SVG headers.

| Script | Output | Size (mm) | `figure.report()` |
|---|---|---|---|
| `fig1.py` | `who_excess_2023_fig1.*` | 89 × 104.8 (single column) | 1 info (font) |
| `fig1_improved.py` | `who_excess_2023_fig1_improved.*` | 89 × 86.2 (single column) | 1 info (font) |
| `fig2.py` | `who_excess_2023_fig2.*` | 183 × 140.7 (double column) | 1 info (font) |
| `fig2_improved.py` | `who_excess_2023_fig2_improved.*` | 183 × 135.1 (double column) | 1 info (font) |
| `fig5.py` | `who_excess_2023_fig5.*` | 136 × 107.6 | 1 info (font) |
| `fig5_improved.py` | `who_excess_2023_fig5_improved.*` | 136 × 107.6 | 1 info (font) |

The one info line in every report is `FONT_SUBSTITUTED`: text is set in Liberation
Sans, which has the same metrics as Arial, because Arial is not installed here. The
scripts no longer pass `expected_fonts`, so this is reported as information rather
than suppressed. See ISSUES-who_excess_2023.md, item 1.

Heights follow the original aspect ratios: 1243/1047 for Fig. 1 (105.6 mm at 89 mm
wide), 1082/1394 for Fig. 2 (142.0 mm at 183 mm) and 1039/1421 for Fig. 5 (99.4 mm at
136 mm). The faithful versions are within 1% of these.

## Print width (pass 2)

Measured in the original PNGs. The cap height is the height of a flat-topped tick
digit ("1"), counting partial-pixel edges. At 7 pt Arial the cap is 0.716 × 7 pt =
1.77 mm, so the print width is W_px × 1.77 / cap_px.

| Figure | Original W × H, px | Digit used | Cap, px | Width at 7 pt, mm | Print width |
|---|---|---|---|---|---|
| 1 | 1047 × 1243 | "1" in "15" | 17.75 | 104.4 | **89 mm** |
| 2 | 1394 × 1082 | "1" in "150" | 14.75 | 167.3 | **183 mm** |
| 5 | 1421 × 1039 | "1" in "100%" | 17.75 | 141.7 | **136 mm** |

Figure 1 sits on the boundary at 7 pt: 104.4 mm is 15.4 mm from 89 and 15.6 mm from
120. It is 89 mm for two reasons. The rule of nearest width picks 89 by 0.2 mm. And
the original's panel letters are 8 pt bold, as Nature sets them (the preset encodes
this). The letter "b" in Fig. 1 has a 24 px ascender, which gives 33.5 px per em and
88 mm. At 89 mm the tick labels then come out at 6 pt, which matches the 17.75 px cap
(6 pt × 0.716 = 1.52 mm). Under the 7 pt assumption the figure would be 120 mm, but
the panel letters contradict that, so 89 mm is taken.

Figure 5 at 141.7 mm is nearest 136, and figure 2 at 167 mm is nearest 183.

## What changed in pass 2, and why

Shared across the figures:

* Print sizes set to the measured widths above (Fig. 1 unchanged at 89; Fig. 2 unchanged
  at 183; Fig. 5 from 183 to 136), with heights set to the original aspect ratio.
* `expected_fonts` removed from every script. The font note is now `FONT_SUBSTITUTED`
  as information, not a suppressed workaround.
* Frame: all six keep `axes="open"`, because the originals have open left and bottom
  axes. The Nature preset draws the axis ink in #1a1a1a, the journal's black, so the
  axes are black without an override.
* Italics: none of the originals sets a variable in italic. "Deaths", "P-score" and
  "P-Score" are upright in the originals, so they stay upright here. Units and labels
  are upright too.

### Figure 1 (faithful, `fig1.py`)

* Width 89 mm (unchanged). Height 110.8 to 104.8 mm: each plot 34 to 31 mm tall, so
  the figure matches the original's aspect ratio.
* Keys: the script has one `legend()` call per panel, not two calls on one panel. Both
  keys show every entry, below the x title, as in the original. Panel a's key is one
  row. Panel b's key sits on two rows at this width; the original has one. I tried
  `columns=2` (layout error: the legend cannot fit the data) and `columns="auto",
  max_width=82` (the 81 mm key overhangs the plot and the layout fails). The
  two-row key is kept as the nearest layout that is clean. See the remaining
  differences below.

### Figure 2 (faithful, `fig2.py`)

* Width 183 mm (unchanged). Height 139.7 to 140.7 mm.
* Axis names set once for the grid: `doc.label(x="Month Year", y="P-score (%)")`.
  The cells keep their own ticks, as in the original, and no panel repeats a title.
* The 0% reference line is #1a1a1a, the journal black, not #222222.

### Figure 5 (faithful, `fig5.py`)

* Width 183 to 136 mm. The plot is 98 × 92 mm, down from 108 × 122 mm. Its height goes
  from 137.3 to 107.6 mm, near the original's aspect ratio (1039/1421); the plot is
  92 mm rather than 84 mm tall so that 22 country names fit at Nature's 7 pt.
* The 108 mm plot was drawn about 98 mm wide at 136 mm, with no lint diagnostic (the
  right furniture takes the space). The width is now set explicitly. See ISSUES item
  9.
* Errorbars are black (#000000) and the means are grey dots with black outlines, as in
  the original. Unchanged.

### Figure 1 (improved, `fig1_improved.py`)

* "Shaded: 95% uncertainty interval" removed from inside the figure. It is in the
  suggested caption below.
* Panel a's y range top lowered from 20.0 to 17.0 (the band's top is 16.6). The headroom
  was there for the note. The end labels stay: "Excess 14.8 M" and "Reported 5.4 M" in
  a, "Excess 7.4" and "Reported 2.8" in b.
* Width 89 mm and height 86.2 mm, unchanged.
* The journal frame: the field is epidemiology, and the original is open, so the
  improved version stays `axes="open"`.

### Figure 2 (improved, `fig2_improved.py`)

* Key in the empty eighth cell: `Panel.key_diagram()` on a drawn panel that carries
  every named series. The four rows are named series: "Region, monthly P-score" (line),
  "95% uncertainty interval" (band), "Global (repeated in every panel)" (grey line and
  band) and "0% line". The hand-drawn swatches and text are gone, so the key is
  generated from the marks it explains. `draw_series()` draws the same marks into the
  panels and into the key's source panel, so they cannot drift.
* The y name "P-score (%)" is set once with `doc.label(y=)`, not on each left-column
  panel. There is no x name: the year ticks carry it, as before.
* The "121%" peak label is kept.
* Height 135.1 mm (unchanged in design).
* No panel letters. `doc.letters()` on this 4-column grid at 183 mm shrinks each 36 mm
  plot to 28.9 mm (the letter adds furniture; `PLOT_WIDTH_OVERRIDDEN` on all seven
  cells), so the improved version carries no letters. The caption names the panels
  instead. See ISSUES item 10.

### Figure 5 (improved, `fig5_improved.py`)

* Width 136 mm and plot 98 × 92 mm, from a 100 × 100 mm plot at 183 mm. The same print
  size as the faithful version, so the pair matches. The value labels beside each
  interval and the 0 to 100% scale are unchanged.

## Figure 1

### Matches the original

* Two stacked panels: a (cumulative deaths in millions, ticks 0 to 15) and b (death
  rate per 100,000, ticks 0, 10 and 20). Panel letters a and b.
* Time from January 2020 to January 2022, with the original tick labels ("January
  2020", "July 2020", "January 2021", "July 2021", "January 2022").
* Series and colours: reported in red, excess in purple, 95% bands shaded. A key below
  each panel, in the original's order (reported first), with the band swatch.
* Open axes, black, with the original's labels "Deaths (×10^{6})" and "Death rate per
  100,000 population".
* Data are the workbook values. The only transformation is dividing deaths by 10⁶ for
  panel a.

### Differs, and why

* Font is Liberation Sans, not Arial (metrically compatible). See the note above.
* Axis ranges are read from the original's axis positions: panel a is −1.3 to 17.0 and
  panel b is −5.9 to 27.2. The ticks match.
* Plot width is 62 mm. The original's plot is about 75 mm wide. At 89 mm the tick labels
  and the "January 2022" end label need the room, so a wider plot would not fit.
* Panel b's key is two rows, not one. See "Figure 1 (faithful)" above.

## Figure 2

### Matches the original

* Seven panels in the same order and layout: four across the top (Global, African,
  Region of the Americas, Eastern Mediterranean), three below (European, South-East
  Asian, Western Pacific), with the empty eighth cell.
* Titles as in the original. The original's ggplot-style colours are used (#F8766D,
  #C49A00, #53B400, #00C094, #00B6EB, #A58AFF, #FB61D7). The 0% line is dashed and
  black. Ticks are two-line labels: "January / 2020", "October / 2020", "July / 2021".
  Values are in per cent.
* One "P-score (%)" beside the grid and one "Month Year" under it (`doc.label`), as in
  the original.
* A shared y range of −44 to 158 (the original's spines) and the same x range.
* A mean line with a 95% band in each panel, in that panel's colour.

### Differs, and why

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
   "2021" and "2022", at each January. Grid lines fall only at those year boundaries,
   in both panels.
3. **Key below each panel replaced by direct labels.** The original's key sat under each
   panel, far from the lines. Each series now carries its December 2021 value just to
   the right of the plot area, unclipped ("Excess 14.8 M", "Reported 5.4 M" in a;
   "Excess 7.4", "Reported 2.8" in b).
4. **Panels on a common time axis.** `share_plot_margins=True` aligns the data edges.
   Both panels share the x range (2019.9 to January 2022, the end of the data), so a
   month reads down the page. The x range no longer runs on to 2022.9 to make room for
   the labels; the labels sit outside the axes instead.
5. **Colour-blind-safe pair.** Red and purple are hard to tell apart with deuteranopia.
   The new pair is Okabe-Ito blue (#0072B2) for excess and vermilion (#D55E00) for
   reported. The vermilion text uses a darker shade (#a64200) to meet the 4.5:1 contrast
   rule.
6. **Zero reference in panel b.** The excess rate is negative in 2020, and a grey zero
   line makes that readable.
7. **Explanation moved to the caption.** The "Shaded: 95% uncertainty interval" note
   sat inside panel a. It is removed, and the caption below gives the band's meaning.
   Panel a's top is lowered to 17.0 to match, since the headroom was for the note.
8. **Plainer y titles.** "Deaths (millions)" replaces "Deaths (×10^{6})", and "Death rate
   per 100,000" replaces "Death rate per 100,000 population".

Kept: both panels, both series, all 95% intervals, the panel order, the end labels and
the same data.

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
7. **A real key in the empty cell, built from the drawn marks.** The key is
   `key_diagram()` on a panel that drew every named series. Its rows are "Region,
   monthly P-score", "95% uncertainty interval", "Global (repeated in every panel)" and
   "0% line", and its swatches are the marks' own colour, tint and stroke. It covers no
   data (the cell holds no data). The earlier hand-drawn key is removed.
8. **Peak labelled.** South-East Asia's peak is labelled 121%, the value that sets the top
   of the range.
9. **Taller panels** (52 mm, from 50 mm in the faithful version) for a little more
   resolution on the shared scale.
10. **One y name for the grid.** "P-score (%)" is set once with `doc.label(y=)`, not on
    each left-column panel.

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
6. **Print size.** 136 mm wide with a 98 × 92 mm plot, the same as the faithful version.

## Suggested caption

Written as Nature legends. The improved figures carry no explanation inside them, so
each caption states what the marks mean.

**Figure 1.** **a**, Cumulative excess deaths (blue) and cumulative reported
COVID-19 deaths (vermilion), January 2020 to December 2021, in millions. The shaded
band is the 95% uncertainty interval for the excess. **b**, Monthly excess (blue) and
reported COVID-19 (vermilion) death rates per 100,000 population over the same period,
with the 95% uncertainty interval for the excess shaded. Excess rates below zero mean
fewer deaths than expected.

**Figure 2.** Monthly P-scores, the percentage by which deaths exceed expected deaths,
globally (top left, blue) and for the six WHO regions, January 2020 to December 2021.
Lines are means and shaded bands are 95% uncertainty intervals. In each regional panel
the global mean is repeated in grey. All panels share one scale, and the solid line at
0% marks no excess. The South-East Asian peak, 121% in May 2021, is labelled.

**Figure 5.** Mean P-score (%) with 95% uncertainty intervals for 22 countries, ranked
from highest to lowest; the mean is written beside each interval. P-score is the
percentage by which deaths exceed expected deaths. The scale starts at zero.

## Key numbers, checked against the paper

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

## Not verified

* Original colours were read by eye from the PNG, not sampled.
* Original positions in Figure 5 were read by eye, not measured. The 13% start of the
  x-axis is an estimate from the spine and tick positions, good to about a point.
* The paper's text was checked only for the numbers listed above.
* The caption wording is ours. It has not been checked against the paper's own legends.
