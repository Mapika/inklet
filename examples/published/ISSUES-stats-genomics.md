# inklet issues found while recreating anscombe_1973 and rnaseq_volcano

Found with the working tree at commit efd6144 plus local changes, 2026-10-07.
Status re-checked later on 2026-10-07: 2, 3 and 4 are FIXED; 5 is PARTLY
FIXED (tick positions, not minor ticks); 1 is OPEN.

## 1. `label_points` ignores text markup by default (inconsistent with `text`, `legend`, titles)

**OPEN.** `label_points` still defaults to `markup=False`, and so do
`volcano(labels=...)` labels. `rnaseq_volcano` now sets the gene names in
italics with `label_options={"font_style": "italic"}` instead of markup.

```python
import inklet as i
p = i.plot_spec(x=(0, 4), y=(0, 4))
p.scatter([(1, 1), (2, 2)])
p.label_points([(1, 1), (2, 2)], ["//FKBP5//", "**bold**"])
p.text(3, 3, "//italic//")
p.axes(x="x", y="y")
doc = i.preset("scientific.modern", format="single-column").document()
doc.add("a", p, min_height=50)
doc.compile().save("markup.png")
# actual:   the point labels read "//FKBP5//" and "**bold**" literally;
#           the text() call renders "italic" in italics
# expected: point labels parse markup like every other text entry point
#           (gene symbols are conventionally italic, so volcano labels need it)
```

`plot/point_labels.py` declares `markup: bool = False`, while `Panel.text`,
`legend` and `annotate` default to `True`, and the guide documents
`//italic//` as general text markup. `volcano(labels=...)` inherits the same
default. Workaround in `rnaseq_volcano/figure.py`:
`label_points(..., markup=True)`.

## 2. `volcano` cannot label a chosen list of genes, or class by q while plotting p

**FIXED.** `volcano(..., q=padj, labels=genes, highlight=[...])` classes by q
while plotting raw p and names the chosen genes. `rnaseq_volcano` uses it;
the p-threshold trick, its assertion and the hand-placed labels are gone
(an assertion on the 316-gene count stays). The rings around the named genes
take their positions from `inklet.plot.volcano_points`, so the p = 0
placement is no longer re-implemented.

```python
p.volcano(fold, pvalues, labels=genes, top=6)   # only "the 6 smallest p"
```

Papers name the genes they discuss (here CRISPLD2, DUSP1, FKBP5, KLF15,
PER1, TSC22D3), not the top N by p, and they colour by the adjusted p (q)
while plotting the raw p on y. `volcano` supports neither:

- expected: e.g. `volcano(..., highlight=["CRISPLD2", "DUSP1"])` or
  `labels=` accepting a mask/subset, and `significant=` (a boolean mask or a
  `q=` sequence) for the classes;
- actual: labels are always the `top` most significant points; classes use
  `p < p_threshold` on the same p as y.

Workarounds: classes reproduced by passing `p_threshold` just above the
largest raw p of the q < 0.05 genes (exact here, asserted in `figure.py`, but
not true in general, e.g. when untested genes have small p); labels added
with a separate `label_points` call, which means re-implementing volcano's
p = 0 placement (`-log10(min positive p)`) to find the labelled points'
y positions.

## 3. Volcano legend order follows paint order, so "not significant" heads the key

**FIXED.** The key lists up, down, n.s.; `legend(names=[...])` can reorder or
filter. `rnaseq_volcano` uses a plain `legend()` with `name=` on the classes.

```python
p = i.plot_spec()
p.volcano([-3, 0.1, 3], [1e-6, 0.5, 1e-6],
          name={"down": "down", "ns": "n.s.", "up": "up"})
p.legend()
# actual:   key rows "n.s.", "down", "up" (ns is drawn first so it sits beneath)
# expected: the significant classes first, or an order= option
```

Workaround: `legend(entries=[(name, i.marker("circle", size=1.4, fill=c)), ...])`.

## 4. Quick API: panel letter sits below the chart title

**FIXED.** Quick layouts set the letter beside the chart title, on its line.
`anscombe_1973` still passes `letters=False`, now by choice: the data-set
numbers in the titles are the identifiers.

```python
import inklet as i
a = i.scatter(x=[1, 2, 3], y=[1, 4, 9], title="Data set 1")
b = i.scatter(x=[1, 2, 3], y=[9, 4, 1], title="Data set 2")
(a | b).save("letters.png")
# actual:   "a"/"b" are set at the top-left of the plot area, one line BELOW
#           the left-aligned title "Data set 1", so the title is the topmost
#           element and the letter reads as belonging to the axis
# expected: the letter at the top-left corner of the cell, on (or above) the
#           title's line, as journals place panel labels
```

Workaround in `anscombe_1973/figure.py`: `i.Layout("grid", charts,
columns=2, width="double", letters=False)` and the data-set number in the
title.

## 5. Quick API has no public option for tick positions or minor ticks

**PARTLY FIXED.** Quick charts accept `xticks=` / `yticks=`. There is still
no `minor=` (or axis-options passthrough), so `anscombe_1973` keeps its
`chart.axes(...)` call for the unit minor ticks, with the axis titles
repeated there.

`i.scatter(...)`/`i.line(...)` accept `xlim`/`ylim` but not `xticks=`,
`yticks=` or `minor=`. Reproducing a paper's furniture (Anscombe: labels every
5, a minor tick at every unit) needs `chart.axes(x=..., y=..., x_options={"ticks":
[...], "minor": 5}, ...)`, which replaces the chart's own axes call, so the
axis titles must be repeated there and `xlabel=`/`ylabel=` are silently
ignored. Expected: `xticks=`, `yticks=`, `minor=` chart options (or an
`axis_options=` passthrough) that compose with the automatic axes.
