# inklet issues found while recreating ncctg_lung and gapminder

These were found on 2026-10-07, with the working tree at commit efd6144 plus
local changes. Every repro below was run with `.venv/bin/python`, with warnings
silenced, and the output shown was the actual output at the time.

Status re-checked later on 2026-10-07: 1, 2, 3, 4 and 6 are FIXED; 5 is IN
PROGRESS (the diagnostics change is being made); 7 is OPEN. The figures no
longer carry workarounds for the fixed items.

## 1. `kaplan_meier` censor ticks beyond an explicit `xlim` become empty nodes (EMPTY_DIAGRAM warnings)

**FIXED.** On a clipping panel, censor ticks past the x domain are left out;
the repro reports clean. `ncctg_lung` now uses `xlim=(0, 1000)`.

```python
import inklet as i
c = i.chart(xlim=(0, 10), ylim=(0, 1))
c.kaplan_meier({'A': ([2, 4, 6, 12], [1, 1, 0, 0])})   # subject censored at t=12 > xlim
print(c.document().compile().report())
# actual:   inklet lint: 1 warning
#           EMPTY_DIAGRAM  cell-chart/0/3 has no primitive and no children, ...
# expected: clean. The clipped-away censor tick is dropped, or clipped
#           silently like the step line and the band.
```

This is the usual case: the published axis stops at a round number (1000
days) and follow-up runs a little longer (1022 days). Each censor-tick group
that falls wholly outside gives one warning. A group with ticks still inside
does not warn. `censors=False` or no `xlim` makes the warning go away.
Workaround in `ncctg_lung/figure.py`: `xlim=(0, 1030)` covers the last
follow-up.

## 2. `Panel.text(..., fill=...)` / `color=` does not colour the text, and `TEXT_FILL_IGNORED` stays silent

**FIXED.** `fill=`/`color=` now set the fill on the `<text>` element (the
repro gives `fill="#cccccc"`), so the silent lint case no longer arises.
`gapminder` uses `color='#e8e8e8'` for the year.

This is also issue 2 in `ISSUES-earth-life.md`. The extra finding here is that
lint does not catch it.

```python
import inklet as i, re
p = i.plot_spec(x=(0, 1), y=(0, 1))
p.text(.5, .5, '1952', size=i.pt(40), fill='#cccccc')     # same with color=
d = i.preset('scientific.modern').document(); d.add('a', p)
f = d.compile()
print(re.findall(r'<text[^>]*>', f.to_svg()), f.report())
# actual:   [... fill="#1a1a1a" ...]  inklet lint: clean, 0 diagnostics
# expected: the text in #cccccc. Failing that, the TEXT_FILL_IGNORED warning
#           that rules.py describes for exactly this case.
```

`Panel.text` turns `color=` into `fill=` with `_color_as(style, "fill")`.
`text_at` then sets that fill on the wrapping placement group, where a
`<text>` element with its own `fill="#1a1a1a"` (from the theme's `text_fill`)
overrides it. TEXT_FILL_IGNORED looks only at `fill` on the text node itself,
so it misses the wrapper. Workaround in `gapminder/figure.py`: `text_fill=`.

## 3. Vertical `size_key` misaligns its circles and labels

**FIXED.** `size_key(..., side='right')` now centres each circle in a common
slot and the labels share a left edge. `gapminder` keeps `side='bottom'`
by choice: keys on the right made the two plot areas narrower and unequal.

```python
import inklet as i
s = i.plot.area_scale(1e9, 15)
p = i.plot_spec(x=(0, 1), y=(0, 1))
p.scatter([(0.5, 0.5)], size=2)
p.size_key(s, values=[1e7, 1e8, 1e9], side='right')       # orient defaults to "v"
d = i.preset('scientific.modern').document(); d.add('a', p)
d.compile().save('sizekey.png')
# actual:   the circles are flush left, and the three labels start at three
#           different x positions (each label sits just right of its own
#           circle).
# expected: as _left_aligned_labels' docstring says, "the circle centred in a
#           slot `widest` across, then its label, so the labels share a left
#           edge".
```

The cause, in `src/inklet/plot/dotplot.py` `size_key`, is that
`_left_aligned_labels` builds the centred slots correctly. Then
`vstack(rows, align="left")` re-aligns each row by its own bounding box. A
small circle's row starts at `widest/2 - r`, so every row moves left by a
different amount. Fix: stack with `align` disabled, or give each row a
transparent slot `widest` wide. Workaround in `gapminder/figure.py`:
`side='bottom'`, which gives the horizontal layout.

## 4. A `size_key` set outside the plot trips CROWDING against its own panel

**FIXED.** The repro reports clean, and the remaining `label_points` CROWDING
infos in `gapminder` now name the bubble (a mark), so their hint can be acted
on. Still open, minor: the default size-key format writes `1e7` / `1e8` /
`1e9`.

```python
import inklet as i
s = i.plot.area_scale(1e9, 15)
p = i.plot_spec(x=(0, 1), y=(0, 1))
p.scatter([(0.5, 0.5)], size=2)
p.axes(x='x', y='y')
p.size_key(s, values=[1e7, 1e8, 1e9], side='bottom')
d = i.preset('scientific.modern').document(); d.add('a', p)
print(d.compile().report())
# actual:   inklet lint: 3 infos
#           CROWDING  cell-a/0/3/0/0/1/0 '1e7' and a are only 0.68mm apart, ...
#           -> a was positioned by data, so move ... '1e7' rather than the mark
# expected: clean. The key's labels sit 0.6 x gap('xs') under its own circles
#           by design, so inklet's own layout should not trip its own rule.
```

The other party in each of these infos is named as the whole panel (`a`), not
as a mark, so the hint ("move the label rather than the mark") cannot be acted
on. The same happens with the `label_points` labels in `gapminder` (`'Japan'
and y2007 are only 0.07mm apart`). Two minor points also turned up: the
default size-key format writes `1e7` / `1e8` / `1e9` for these values, and
`10M` or `10,000,000` would read better. Severity is info, so `--strict`
passes.

## 5. No way to mark decorative text for LOW_CONTRAST; translucent text skips the check entirely

**IN PROGRESS.** LOW_CONTRAST now composites translucent text too (both
repro cases give 1 warning), and an opt-out,
`kind=inklet.diagnostics.decorative()`, is being added by the diagnostics
work. Until that settles, `gapminder` draws the year in plain `color='#e8e8e8'`
and its report shows two LOW_CONTRAST warnings for the watermarks; with the
opt-out the report has only CROWDING infos.

```python
import inklet as i
for fill in ('#e6e8eb', '#1a1a1a1a'):
    p = i.plot_spec(x=(0, 1), y=(0, 1))
    p.text(.5, .5, '2007', size=i.pt(40), text_fill=fill, front=False)
    d = i.preset('scientific.modern').document(); d.add('a', p)
    print(fill, d.compile().report().splitlines()[0])
# actual:   #e6e8eb   -> inklet lint: 1 warning (LOW_CONTRAST 1.23:1 ...)
#           #1a1a1a1a -> inklet lint: clean       (renders identically pale)
# expected: a consistent rule. Either the translucent colour is composited
#           over the backdrop and checked too, or the author can declare a
#           watermark decorative (for example `decorative=True` or a kind
#           that LOW_CONTRAST skips) and the opaque grey passes.
```

A pale year behind the data is the signature of Gapminder's chart. Workaround:
`text_fill=ink, opacity=0.1`, which renders the same as the pale grey and is
not checked.

## 6. Feature gaps met in survival analysis (not bugs)

**FIXED.** `kaplan_meier(band='log')` matches R's default, and
`kaplan_meier(pvalue='logrank')` / `inklet.plot.logrank(data)` run the
Mantel-Cox test (10.33 on 1 df, P = 0.0013 for these data). `ncctg_lung`
uses both; its numpy test is gone.

- `kaplan_meier(band=...)` offers `"log-log"`, `"linear"` or None. R's
  `survfit` and survminer default to `conf.type = "log"`, so an exact match
  with an R figure is not possible.
- There is no log-rank test. `pvalue=` takes a value computed elsewhere (as
  documented). `ncctg_lung/figure.py` has a 20-line numpy Mantel-Cox test. A
  `pvalue='logrank'` option would make the common case one call.

## 7. Quick-API facets follow the order of first appearance, not sorted order (minor)

**OPEN.** The repro still gives 'year = 2007' before 'year = 1952'.

```python
import inklet as i, pandas as pd
df = pd.DataFrame({'year': [2007, 1952, 2007, 1952], 'x': [1, 2, 3, 4], 'y': [1, 2, 3, 4]})
i.scatter(df, x='x', y='y', facet_col='year').save('facet.svg')
# actual:   panels 'year = 2007', 'year = 1952' (row order)
# expected: numeric facet values in ascending order (1952, 2007), or a
#           documented `facet_order=` argument
```

This turned up when the gapminder rows were sorted by population, so that
large bubbles are drawn first. The final figure uses the document model and is
not affected.
