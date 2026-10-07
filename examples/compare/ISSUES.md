# Issues found while building the matplotlib comparison

Status after the fixes of 2026-10-07: all eleven items are fixed. The repros
are kept below as regression cases. The workarounds
listed under the fixed items have been removed from the example scripts.

Found against the working tree of 2026-10-07 (4.5.0 plus the uncommitted quick
API, `src/inklet/quick.py` and `src/inklet/plot/autodomain.py`). Each has a
minimal repro, what was expected, what happened, and the workaround used in
`examples/compare/`. Ordered by how much they affect a finished figure.

## 1. Confidence bands are opaque and hide the curves drawn before them (FIXED)

**Status:** Fixed: `Panel.band` now paints in the under layer, beneath all data marks, and a grouped quick `line(error_y=)` draws translucent bands (fill opacity 0.22) in the series colour. Verified: the repro gives `fill-opacity="0.22"`, and the time-course and survival figures show every curve with no redraw.


Affects `line(error_y=)` and `kaplan_meier()` with more than one group.

```python
import inklet as i
d = dict(x=[0, 1, 2] * 2, y=[1, 2, 3, 1.2, 2.1, 2.9], g=['a'] * 3 + ['b'] * 3, e=[0.5] * 6)
print(i.line(d, x='x', y='y', color='g', error_y='e').to_svg())
# band paths: fill="#c7e0ee" fill-opacity="1", then fill="#f6dcc7" fill-opacity="1"
```

- **Expected:** every series' line stays visible. Either all bands go under all
  lines, or the bands are translucent so overlaps blend.
- **Actual:** each group draws band then line, and the band is an opaque tint
  (`Panel.band` mixes the colour towards paper, `fill-opacity="1"`). Group 2's
  band covers group 1's line where the bands overlap. In the survival figure,
  the Drug A curve vanished under the Drug A + B band from about 5 to 25 months.
  The time course lost the Vehicle line from 0 to 5 h. Censor ticks of earlier
  groups are hidden the same way. The lint report is clean, so nothing warns
  about it.
- **Workaround:** draw the lines again on top. For `line`, a second
  `chart.line(df, x=, y=, color=)` merges into the same legend entries. For
  Kaplan-Meier, a second `kaplan_meier(..., shade=False)` cannot be used,
  because `at_risk()` then lists every group twice (`Panel._survival` is
  appended per call and `at_risk` runs in a later phase). The example redraws
  each curve with `chart.step()` from `i.plot.kaplan_meier(durations, events)`
  and hard-codes the palette colours (4 extra lines).
- **Suggested fix:** draw all bands of one call before its lines and steps, or
  put band fills in an under layer.

## 2. `save(..., dpi=)` fails when the paths include a PDF (FIXED)

**Status:** Fixed: `dpi` now goes only to PNG outputs. Verified with the repro. All scripts now use one `save(png, pdf, dpi=200)` call.


```python
import inklet as i
i.line(x=[1, 2], y=[1, 2]).save('a.png', 'a.pdf', dpi=200)
# TypeError: to_pdf() got an unexpected keyword argument 'dpi'
```

- **Expected:** `dpi` applies to the PNG and is ignored for vector formats. The
  guide shows `save('fig.pdf', 'fig.png')` as the normal call.
- **Actual:** `render/page.py: save_outputs` passes every keyword except `text`
  to `to_pdf`.
- **Workaround:** `figure = chart.save(pdf)` then `figure.save(png, dpi=200)`.

## 3. Auto y-range from the violin probe is wrong: tails are cut and data can fall outside (FIXED)

**Status:** Fixed: the violin, box and strip auto range now includes the group samples before probing. Verified: the repro's y ticks run 0.5 to 3.5, and the gallery violin no longer needs `ylim`.


```python
import inklet as i
d = {'g': ['a'] * 5 + ['b'] * 5, 'v': [1, 1.1, 1.2, 1.3, 3.0, 1, 1.05, 1.1, 1.2, 1.25]}
i.violin(d, x='g', y='v').save('violin.png')    # y ticks 0.8 ... 1.2
i.boxplot(d, x='g', y='v').save('box.png')      # y ticks 1.0 ... 3.0 (correct)
```

- **Expected:** the y domain covers the violins, including the 2-bandwidth
  tails, as it does for `boxplot` and `strip`.
- **Actual:** the domain is about 0.77 to 1.22. Both violins are cut flat at
  the top, and the 1.3 and 3.0 observations are outside the plot. Lint is
  clean. With the gallery data (40 points per group) the upper tail of the
  last violin is cut flat at the axis top. The new `plot/autodomain.py` reads
  the violin extent from a probe panel, and the probe seems to clip or cull at
  its placeholder domain.
- **Workaround:** explicit `ylim=(0, 2.5)`.

## 4. Panel methods called through a chart skip the chart's legend and label logic (FIXED)

**Status:** Fixed: Panel methods called through a chart now count `name=` for the legend and register string categories for auto rotation. Verified: the repro draws a legend, and the gallery bar charts need no explicit `legend()` or `x_options`. See item 10 for a side effect.


```python
import inklet as i
c = i.chart(ylabel='length')
c.barplot(['Scrambled siRNA', 'MFN2 knockdown', 'OPA1 knockdown', 'DRP1 knockdown'],
          [[[1, 2]] * 4, [[2, 3]] * 4], name=['Vehicle', 'CCCP'])
(c | c).save('bars.png')
```

- **Expected:** the same as quick-API marks: a legend appears for named series,
  and crowded category labels turn 45 degrees (`Chart._tick_options`).
- **Actual:** no legend is drawn, and in a half-width panel the category labels
  stay upright and almost touch. With the gallery data, the four-panel figure's
  lint reports `CROWDING 'Scrambled siRNA' and 'MFN2 knockdown' are only
  0.91mm apart`. With the repro data, lint is clean although the gap is about
  the same. `Chart.__getattr__` forwards to
  the spec without updating `_named` or `_x_categories`. The guide recommends
  `i.chart().barplot(...)` for means with points, so this path is common.
- **Workaround:** `.legend(side='top')`, and
  `chart.axes(y='...', x_options={'rotate': 30})` in the four-panel figure.

## 5. Volcano labels can sit off-diagonal from their point with no leader (FIXED)


```python
chart = i.chart()
chart.volcano(df['log2fc'], df['p'], labels=df['gene'], top=10, size=1.0)
# examples/compare/volcano/inklet_version.py, data from examples/compare/data.py
```

- **Expected:** each label is either next to its point or joined to it by a
  leader.
- **Actual:** `ZNKR17` and `CDKR10` are placed about 2 mm diagonally away with
  no leader. `ZNKR17` sits between two blue points, so a reader cannot tell
  which one it names. Lint gives only an info line (`'ZNKR17' and chart are
  only 0.93mm apart`), which is about crowding and not about the missing
  leader. Passing `label_options={'clear': 0.3}` produced 7 CROWDING infos and
  did not add leaders.
- **Workaround:** none used. The default placement is shown as is.

## 6. Lint flags layout that inklet generated itself (FIXED)


```python
chart = i.chart(xlim=(0, 60), ylim=(0, 1))
chart.kaplan_meier({'Standard care': (t0, e0), 'Drug A': (t1, e1), 'Drug A + B': (t2, e2)}).at_risk()
chart.save('km.png').report()
# INFO CROWDING 'Drug A' and 'Drug A + B' are only 0.59mm apart, under the 1.00mm clearance
# INFO CROWDING 'Number at risk' and 'Standard care' are only 0.93mm apart
```

- **Expected:** the default number-at-risk table passes inklet's own lint.
- **Actual:** its default row gap (`theme.gap('xs') * 0.5`) is below the
  1.00 mm CROWDING clearance, so every KM figure with `at_risk()` has
  diagnostics the user cannot fix except through `row_gap=`.
- **Workaround:** none. The infos are left in the report.

## 7. `xlabel=''` still reserves the axis-title row (FIXED)

**Status:** Fixed: `xlabel=''` and `ylabel=''` reserve no title row. Verified in the violin figure (`xlabel=''`).


```python
i.violin(df, x='genotype', y='density', xlabel='')   # blank band under the ticks
```

- **Expected:** an empty string removes the x-axis title and gives its space
  back to the plot, as `ax.set_xlabel('')` does in matplotlib. Leaving `xlabel`
  out falls back to the column name, so `''` is the obvious way to drop it.
- **Actual:** the x axis is at the same height as with a title, and a blank
  band is left under the tick labels.
- **Workaround:** used a real title (`xlabel='Genotype'`).

## 8. Legend markers ignore the scatter `size=` (FIXED)


```python
c = i.scatter(points, x='conc', y='viability', color='compound', size=1.2)
# data markers r=0.6 mm, legend markers r=0.857 mm
```

- **Expected:** legend swatches match the plotted markers.
- **Actual:** legend markers keep the default size, so the key's dots are about
  40 % wider than the data dots. Cosmetic.
- **Workaround:** none.

## 9. Small API frictions (not bugs) (FIXED)

**Status:** Fixed: `i.heatmap(..., colorbar='title')` titles the colour bar, and a list passed as `color=` raises `TypeError`. Verified both.


- `i.heatmap(matrix_df, ...)` has no way to title the colour bar. `z=` names it
  only for long tables. The example uses `colorbar=False` and then
  `chart.colorbar(title='Pearson //r//')`.
- `i.line(x=..., y=..., color=[...])` treats a list `color=` as nothing (no
  grouping, default ink). Only column names group. This is documented, but a
  list fails silently instead of raising.

## 10. Automatic category rotation fires for labels that fit upright (FIXED)

Fixed: labels are now set upright first, and a chart is rebuilt with 45-degree
labels only when the compiled figure's lint finds two of its category labels
colliding. The single-column grouped-bar chart draws them upright again; the
half-width panel in the four-panel figure still turns them.

This appeared after the fix for item 4, which now registers `barplot` categories.

```python
chart = i.chart(ylabel='Mitochondrial length / µm')
chart.barplot(['Scrambled siRNA', 'MFN2 knockdown', 'OPA1 knockdown', 'DRP1 knockdown'],
              samples, name=['Vehicle', 'CCCP 10 µM'])    # 89 mm wide
```

- **Expected:** upright labels when they fit. Before the fix, this exact chart
  drew them upright at 89 mm with lint clean (gaps of at least 1 mm), and
  matplotlib fits them upright at the same size and type size.
- **Actual:** `Chart._tick_options` turns them 45 degrees because the widest
  label is wider than `0.9 * step`, where step is `(width - 14 mm) / n`.
  The rotated labels take roughly 12 mm more height, so the plot area is
  noticeably shorter than in the matplotlib version. In the half-width panel
  of the four-panel figure, rotating is the right call: upright labels were
  0.91 mm apart there.
- **Suggestion:** compare measured label widths against the real band step
  minus the CROWDING clearance, not a 0.9 factor on an estimated data width.
- **Workaround:** none used. The figures show the default behaviour.

## 11. Kaplan-Meier bands are still opaque, so overlapping intervals hide each other (FIXED)

This is what is left of item 1. The curves are visible now, but `kaplan_meier`
bands still go through `Panel.band` with an opaque tint. Only the quick
`line(error_y=)` path got translucency.

```python
c = i.chart(xlim=(0, 60), ylim=(0, 1))
c.kaplan_meier(arms)      # arms: three groups, from examples/compare/data.py survival()
c.to_svg()                # band fills: #c7e0ee, #f6dcc7, #c7eae0, all fill-opacity="1"
```

- **Expected:** where two arms' confidence intervals overlap, both stay
  visible, as with the translucent quick-line bands or matplotlib's `alpha`.
- **Actual:** the band drawn later covers the earlier one. In the gallery
  figure, the Standard care interval is hidden under the Drug A band from
  about 15 to 30 months.
- **Workaround:** none used.
