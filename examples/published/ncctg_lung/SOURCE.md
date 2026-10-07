# Source: NCCTG advanced lung cancer, overall survival by sex

## Study

Loprinzi, C. L., Laurie, J. A., Wieand, H. S., Krook, J. E., Novotny, P. J.,
Kugler, J. W., Bartel, J., Law, M., Bateman, M., Klatt, N. E., et al. (1994).
Prospective evaluation of prognostic variables from patient-completed
questionnaires. North Central Cancer Treatment Group.
*Journal of Clinical Oncology* 12(3), 601-607.
https://doi.org/10.1200/JCO.1994.12.3.601

## Figure being recreated

The Kaplan-Meier plot of overall survival by sex is the standard presentation
of these trial data. It is in the R `survival` package documentation and is
best known from the `survminer` README (`ggsurvplot(fit, conf.int = TRUE,
pval = TRUE, risk.table = TRUE, ...)`, image
`tools/README-ggplot2-customized-survival-plot-1.png` in
https://github.com/kassambara/survminer). That plot has two curves with censor
marks, confidence bands, "p = 0.0013" and a number-at-risk table at 0, 250, 500,
750 and 1000 days. The JCO paper itself reports Cox models of the
questionnaire variables rather than this plot. The reference image was viewed
only and is not stored in this repository.

## Data

- File: `data/lung.csv`, an unmodified copy of
  https://vincentarelbundock.github.io/Rdatasets/csv/survival/cancer.csv
  (the `lung`/`cancer` data set of the R `survival` package, "NCCTG Lung
  Cancer Data"). 228 patients and 11 columns: `rownames, inst, time, status,
  age, sex, ph.ecog, ph.karno, pat.karno, meal.cal, wt.loss`. 7 KB.
  sha256 `4045e3fee76936bb8bd9312243d7b81b36ed224a12800fcef12e8a361883cfb6`.
  (Rdatasets' `survival/lung.csv` URL is a different, unrelated table.)
- Documentation: https://vincentarelbundock.github.io/Rdatasets/doc/survival/lung.html
  (source: Terry Therneau).
- Retrieved: 2026-10-07.
- Licence: the data ship with the R package `survival` (Therneau T. M.,
  version 3.8-12, https://doi.org/10.32614/CRAN.package.survival), licensed
  LGPL (>= 2) according to its CRAN DESCRIPTION. Rdatasets redistributes
  package data sets as CSV.
- Package reference: Therneau, T. M. & Grambsch, P. M. (2000). *Modeling
  Survival Data: Extending the Cox Model*. Springer.
  https://doi.org/10.1007/978-1-4757-3294-8

## Processing (all in `figure.py`)

- `time`: survival time in days. `status`: 1 = censored, 2 = dead, so an event
  is `status == 2`. `sex`: 1 = male (n = 138, 112 deaths), 2 = female
  (n = 90, 53 deaths). No rows are dropped. The variables used have no missing
  values.
- Kaplan-Meier estimate and pointwise 95% confidence band from inklet's
  `kaplan_meier` (Greenwood variance, log transform as R's `survfit`
  default). Median survival: male 270 days, female 426 days, the same as R's
  `survfit`.
- Log-rank (Mantel-Cox) test from inklet (`pvalue='logrank'` on the plot,
  `inklet.plot.logrank` for the printed values). Result: chi-square 10.33 on
  1 df, p = 0.0013, the same as R's `survdiff(Surv(time, status) ~ sex,
  data = lung)` (chi-square 10.3, p = 0.001).
