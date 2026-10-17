# inklet issues found while recreating marek_bwas_2022 (Figure 1)

Found with the working tree at inklet 4.8.1 (commit 51ada61 plus this worktree), 2026-10-17.
Repros were run in a minimal script unless noted.

## 1. `Document.letters()` assigns letters by cell index, so a letter cannot be skipped or matched to a named cell

**OPEN.** The original Figure 1 letters are a, b, e, f, g, h (c and d are the brain maps and are left out). Top-level cells in order `a, b, e, f, g, h` get letters `a, b, c, d, e, f`.

```python
import inklet as i
doc = i.preset("scientific.nature", format="double-column").document(columns=2)
for name, row, col in [("a", 0, 0), ("b", 0, 1), ("e", 1, 0), ("f", 1, 1)]:
    doc.add(name, i.plot_spec(30, 20, x=(0, 1), y=(0, 1)), row=row, column=col)
doc.letters(start="a")
doc.compile().save("letters.png", dpi=100)
# actual:   the cell 'e' is lettered 'c' and 'f' is lettered 'd'
#           (layout.py _decorator: chr(ord(start) + index of the cell in insertion order))
# expected: letters by cell name, or a way to skip letters
```

Workaround in `marek_bwas_2022/fig1.py`: one `i.subfigure` per row, each with `.letters(start=...)` for its own two cells, then placed in the top document with `letters` off. Note the letters apply to each cell of a subfigure, so the pair of plots for one letter is a nested subfigure without letters.

## 2. `Document.add` on a subfigure without `row=` starts a new row, so cells go diagonal

**OPEN.** Repro:

```python
import inklet as i
sub = i.subfigure(columns=2, gap=3)
for k in range(2):
    sub.add(f"c{k}", i.plot_spec(30, 20, x=(0, 1), y=(0, 1)), column=k)   # no row=
print({c.name: (c.row, c.column) for c in sub._cells})
# actual:   {'c0': (0, 0), 'c1': (1, 1)}   (the second cell is one row lower)
# expected: the same row when that cell is free, or an error saying row= is needed
```

The cell is pushed down a row because `row` defaults to "below existing cells". In a real figure the result was a 434 mm page (`PAGE_TOO_TALL`) with no hint that cells were misplaced. Workaround: pass `row=0` explicitly.

## 3. `plot_spec(..., clip=True)` hides data outside the y range and lint reports nothing

**OPEN.**

```python
import inklet as i
p = i.plot_spec(40, 30, x=(0, 1), y=(0, 5), clip=True)
p.line([(0, 1), (0.5, 9), (1, 1)], name="spike")
doc = i.document(width=80); doc.add("a", p)
print(doc.compile().report().splitlines()[0])
# actual:   "inklet lint: clean, 0 diagnostics"; the spike to y = 9 is not drawn
# expected: a diagnostic (e.g. DATA_CLIPPED) with the count and the range that would show it,
#           as DATA_OUTSIDE does without clip=True
```

This bit us in the histograms: the first version clipped the tallest bars at a fixed y range and lint stayed silent. Workaround: compute the y range from the data.

## 4. `legend(names=)` raised "repeats a name" in a real figure but accepted duplicates in a minimal repro

**OPEN (cause unknown).** In `marek_bwas_2022/fig1.py` the g/h keys listed `n = 25` twice (two subsamples) and raised:

```
inklet.core.diagram.DiagramError: legend(names=) repeats a name: ['n = 25', 'r = +0.50', 'n = 25', 'r = -0.64', 'r = -0.08']
```

A minimal script with two scatter series and two line series named the same way was accepted, and so was a list of two identically named line series. I did not find what differed in the real figure. Expected: either the same answer in both cases, or a `label=` option so that the display text need not equal the series identity.

Workaround: give the light subsample a trailing zero-width space in its name (`"n = 25​"`), which makes it unique and invisible.

## 5. `legend(side="top")` in a narrow cell fails with a layout error that blames the data area

**OPEN.** In a four-across grid (cells about 41 mm wide), `legend(side="top", columns=2)` on a 30 mm plot gave (this was the first version of `fig1_improved.py`):

```
LayoutError: cell 'c0' leaves only -0.90 × 28.00 mm for data after labels: ... the furniture takes 22.99 mm left, 19.42 mm right ...
```

The message does not say the key is the cause, and the numbers do not show the key's width. Expected: name the key as the cause and give its width, or let the key wrap into more rows. Workaround: narrower plots (26 mm) and `columns=1`, with the key above the plot.

## 6. `vline` and `vspan` reject `name=`; `line`, `band`, `scatter` accept it

**OPEN.** Repro:

```python
import inklet as i
p = i.plot_spec(40, 30, x=(0, 1), y=(0, 1))
p.vline(0.5, name="top 1%")
# TypeError: vline() got unknown keyword name=; its paint keywords are Style fields such as ...
```

Same for `vspan`. Expected: accept `name=` on reference marks too (a legend entry for a reference line is sometimes wanted), or say in the docs that they are never keyed.

## 7. `SERIES_FLATTENED` cannot be acknowledged when the flat series is the point

**OPEN.** A mean line that stays at the same value across sample size (about −0.11 across 16 bins, under a band 48% of the plot height) triggers `SERIES_FLATTENED` four times. The flatness is the finding in Figure 1 (the mean does not move; the intervals do), and a log axis or a second axis would hide it. There is no option to mark a flat series as intentional. Expected: a `flat_ok=True` (or `reason=`) on the mark, so that the warning is kept for accidental cases and the reason is printed.

Workaround: the warning is explained in `marek_bwas_2022/NOTES.md` and left in place.

## 8. `FONT_SUBSTITUTED` repeats on every text primitive

**OPEN (noise).** With the `scientific.nature` profile and Arial not installed, lint reports one warning per text primitive (137 to 139 in these figures), listing the first few cell paths. The real problems are then hard to see. Expected: one warning with a count, and a per-document way to accept a metric-compatible substitute (the message suggests `expected_fonts=None` for "Liberation Sans"; I did not verify that option).

Workaround: none in the scripts. Liberation Sans is used and the warning is recorded in both NOTES.md files.
