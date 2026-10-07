# Notes: NCCTG lung cancer survival by sex

`figure.py`: 37 lines, of which the figure itself takes 7. The log-rank test
is inklet's own (`kaplan_meier(..., pvalue='logrank')`, and
`inklet.plot.logrank` for the printed statistic). Output:
`gallery/published/ncctg_lung.{png,svg,pdf}`, single column (89 mm), 62 mm
plot height plus the at-risk table.
`figure.report()`: `inklet lint: clean, 0 diagnostics`.

## Matches the reference (survminer / survival-package presentation)

- The data: the same 228 patients and the same step curves, censor marks at
  the same times, male median 270 days and female median 426 days.
- Pointwise 95% confidence bands on the log scale (`band='log'`), R
  `survfit`'s and survminer's default `conf.type = "log"`, shaded in each
  curve's colour.
- Log-rank p-value 0.0013 (chi-square 10.33 on 1 df), from inklet's built-in
  Mantel-Cox test. It agrees with survminer's "p = 0.0013" and with
  `survdiff`.
- Number-at-risk table at 0, 250, 500, 750 and 1000 days: Male 138, 62, 20, 7,
  2 and Female 90, 53, 21, 3, 0. These are the reference's numbers, and the
  columns sit under the x ticks.
- Days on the x axis, with ticks every 250 days as in the reference.

## Differs, and why

- Style: inklet's `scientific.modern` look (grey axes, no panel box or grid),
  with the theme's blue and red in place of survminer's yellow and blue. The
  key sits inside the top-right corner of the plot, titled "Sex", where the
  reference has a "Strata" key above the plot. The table takes the curve
  colours for its row names and numbers, as the reference does.
- The x axis stops at 1000 days, the last at-risk column. The reference's
  axis runs on to the last follow-up (1022 days), so the final 22 days of the
  male curve and its last censor tick (at 1022 days) are not drawn here.
  `xlim=(0, 1030)` would show them.
- The p-value reads "Log-rank *P* = 0.0013" (journal style, test named) in
  the lower-left corner, where the reference has "p = 0.0013" at mid-left.
- The x-axis title says "Time since enrolment / days" where the reference has
  "Time". The y-axis title is "Overall survival probability".

## Verdict

Faithful: the content and structure are the reference's, and every number
checks out against R. It is re-styled to inklet's single-column look and
ready for publication.
