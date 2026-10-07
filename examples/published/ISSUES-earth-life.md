# inklet issues found while recreating keeling_curve and palmer_penguins

Found with the working tree at commit efd6144 plus local changes, 2026-10-07.
Status re-checked later on 2026-10-07 against the current tree: 1, 2 and 4
are FIXED and their workarounds are gone from the figures; 3 is still OPEN.

## 1. Negative tick labels use a hyphen-minus, not a minus sign (typography)

**FIXED.** Negative tick labels are typeset with U+2212 automatically; the
`format=` lambda is gone from `keeling_curve` (and from `ligo_gw150914` and
`rnaseq_volcano`).

```python
import inklet as i, re
i.line(x=[0, 1, 2], y=[-2, 0, 2]).save("minus.svg")
print(re.findall(r">(-?\S*2)</text>", open("minus.svg").read()))
# actual:   ['-2', '2']        (U+002D hyphen-minus)
# expected: ['−2', '2']   (U+2212 minus, as the waterfall and
#           correlogram code and the Bland-Altman labels already use)
```

Journals (Nature, Science) ask for a true minus in figures. Workaround in
`keeling_curve/figure.py`: `format=lambda v: f"{v:g}".replace("-", "−")`
on the inset y axis.

## 2. `Panel.text(..., fill=...)` / `color=` is ignored: text renders in the ink colour

**FIXED.** `Panel.text(..., color=)` / `fill=` now colour the `<text>` itself;
`keeling_curve` uses `color="#5b6470"` instead of per-line markup.

```python
import inklet as i, re
c = i.line(x=[0, 10], y=[0, 10])
c.text(8, 2, "one line", fill="#c1121f")      # same with color="#c1121f"
c.save("fill.svg")
print(re.findall(r'<text[^>]*fill="([^"]+)"[^>]*>one', open("fill.svg").read()))
# actual:   ['#1a1a1a']  -- the colour is set on the wrapping <g>, but the
#           <text> element carries its own fill="#1a1a1a", which wins
# expected: ['#c1121f']
```

Single-line and multi-line text both fail; `size=` is honoured. Workaround in
`keeling_curve/figure.py`: colour through markup, `"{#5b6470|...}"` per line
(the tspan fill wins over the text fill).

## 3. Explicit ticks dropped by thinning are not reported by `figure.report()`

**OPEN.** The repro below still gives only the Python `UserWarning` and a
clean report. `keeling_curve` keeps ticks that fit (`[1, 4, 7, 10]`).

```python
import inklet as i
M = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
sub = i.plot_spec(27, 17, x=(0.5, 12.5), y=(0, 1))
sub.line([(1, 0), (12, 1)])
sub.axes(x_options=dict(ticks=[2, 4, 6, 8, 10, 12], format=lambda m: M[int(m) - 1]))
p = i.plot_spec(89, 74, x=(0, 10), y=(0, 10)); p.line([(0, 0), (10, 10)]).axes()
p.inset(sub, corner="nw", width=None)
d = i.preset("scientific.modern", format="single-column").document(); d.add("a", p)
print(d.compile().report())
# actual:   a Python UserWarning on stderr ("axis omitted 3 of 6 explicitly
#           supplied ticks ...") and then "inklet lint: clean, 0 diagnostics"
# expected: the dropped explicit ticks also listed in report() (at least as
#           a warning), since the guide tells agents to rely on report()
```

Workaround: chose ticks that fit (`[1, 4, 7, 10]`).

## 4. Grouped histogram outlines run along the baseline over every empty bin (cosmetic)

**FIXED.** Each group's outline now closes only under its own bins; the
x-axis baseline in `palmer_penguins` panel b is plain grey. No script change
was needed.

```python
import inklet as i
p = i.plot_spec(60, 40, x=(0, 20), y=(0, 5))
p.hist({"a": [1, 2, 2, 3], "b": [15, 16, 16, 17]}, bins=list(range(0, 21)))
p.axes()
d = i.preset("scientific.modern").document(); d.add("a", p)
d.compile().save("hist.png", dpi=300)
# actual:   each group's coloured outline is drawn along y = 0 from the first
#           to the last shared edge (0..20), over the x-axis spine, so the
#           spine reads as a mix of group colours far from any data
# expected: the outline closed only under each group's own non-empty run of
#           bins (or the baseline segment left unstroked), so empty bins draw
#           nothing
```

Visible in `palmer_penguins` panel b (Gentoo teal and Chinstrap purple lines
along the baseline under the Adelie range). Not worked around: it is minor and
the mapping form of `hist` is the only one that draws shared-bin overlays.
