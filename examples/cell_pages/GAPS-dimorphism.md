# Gaps: Cell dimorphism page on the 4.4 API

This file backs `dimorphism.py`, which rebuilds the Cell 2026 p. 5518 page
(panels A–Q) on the released 4.4 API. The page uses
`i.preset('scientific.cell').document(columns=12).letters()` and has no hand
placement: no page or panel coordinates, no dx/dy nudges, no `xytext`, no
manual legend positions, and no changes under `src/`. Wherever 4.4 could not
express what the reference shows, the page draws the closest honest
approximation, and the gap is logged below.

The entries are ranked by severity:

- **blocks**: there was no honest route. The page had to change its design, or it would not compile.
- **ugly**: the page compiles but is visibly worse than the reference.
- **minor**: a papercut, an API inconsistency, or a small visual difference.

Unless an entry says otherwise, each repro runs as-is after this setup:

```python
import inklet as i
S = i.preset('scientific.cell')
```

`repros.py` ran each repro against 4.4.1 and recorded the outcome in its
entry. Where no small case reproduced the problem, the entry says so.

---

## Blocks

### 1. Legends and titles above or below a plot are charged to its side margins (F, H, M, N, Q)
- **Reference:** a key with two or three columns sits above or below a narrow plot, and the plot keeps its full data width.
- **4.4:** the width of the key, and of a wide title or axis label, is charged to the plot's left and right margins. In a 2-of-12-column cell, a two-column key with four entries leaves **-2.80 mm** of data width, and the compile fails.
  - Workarounds on the page:
    - F and N: one legend column.
    - H and M: the key moved into its own subfigure row.
    - Q: two columns.
  - The page is taller because of these changes.
- **Category:** legend / layout grid.
- **Repro:**
  ```python
  p = i.plot_spec(height=34, x=(0, 1), y=(0, 1))
  for k, name in enumerate(['dimorphic types', 'isomorphic types', 'all types', 'fru+ or dsx+ only']):
      p.line([(0, k / 4), (1, k / 4)], name=name)
  p.legend(side='top', columns=2)
  doc = S.document(columns=12); doc.add('x', p, colspan=2); doc.compile()   # data width -2.80 mm
  ```
- **Suggested API:**
  - A key on side top or bottom should reserve height and be allowed to overhang the plot margins, up to the cell width.
  - `p.legend(side='top', columns=2, span='cell')`, where `span='data'` gives today's behavior.

### 2. A nested subfigure divides column widths wrongly (I, J)
- **Reference:** a narrow rotated axis label ("% of connections") stands next to a male pie above a female pie.
- **4.4:** a narrow cell in column 0 (`rowspan=2`) of a 15-column subfigure halves the width of the wide cell next to it. The result is `LayoutError: 21.93 < 38`. I and J were rebuilt as a component made of `hstack` and `vstack`.
- **Category:** layout grid.
- **Repro:**
  ```python
  sub = i.subfigure(columns=15, gap=.2)
  sub.add('axis', i.component(i.box, 'y', width=3, height=30), row=0, column=0, rowspan=2)
  sub.add('male', i.component(i.box, 'x', width=38, height=20), row=0, column=1, colspan=14)
  doc = S.document(columns=12); doc.add('i', sub, row=0, column=0, colspan=3); doc.compile()
  ```
- **Suggested API:** this is a bug fix. The subfigure track solver should give the cell `colspan * track + gaps`, the same as the page grid does.

### 3. `i.connect` and `i.bracket(within=...)` misplace endpoints inside nested stacks (C, D)
- **Reference:** circles in a male and a female column are joined by amber links with weights (C). Tables are joined by arrows labeled "scale weights" and "square root" (D).
- **4.4:** when the shapes sit in an `hstack` inside a `vstack`, the link endpoints land at the wrong offsets. The error changes with `align=` (see `nest.py`: left, right and center each fail differently).
  - Workaround: C and D were rebuilt on `i.graph`, with hidden edges to keep the labels in rank.
  - This workaround costs the header alignment in D (♂ and ♀ are not centered over their columns) and gives C's circles rank-based spacing.
- **Category:** bug (diagram).
- **Repro:**
  ```python
  rows, circles = [], []
  for k in range(3):
      a = i.circle(i.text('m'), width=4, height=4); circles.append(a)
      rows.append(i.hstack([i.text('label ' * (k + 1)), a], gap=4, align='center'))
  col = i.vstack(rows, gap=7, align='right')
  i.overlay([col, i.connect(circles[0], circles[1], within=col)])   # endpoints land off the circles
  ```
- **Suggested API:** this is a bug fix. `within=` should resolve positions through every nesting level.

### 4. `share_plot_margins=True` leaks margins between rows (G and M)
- **Reference:** each plot has its own margins.
- **4.4:** on the full page, G (row 1, columns 5–7) received margins from M (row 3, columns 2–7), because both end at the same column. G's data width went negative. The page now uses `share_plot_margins=False`, so plots in the same row no longer share their axes alignment.
- **Category:** layout grid.
- **Repro:** none. The two-row case (`share_margins_rows` in `repros.py`) compiles fine; only the full 17-cell page fails.
- **Suggested API:**
  - Share margins only between cells whose rows overlap.
  - Alternatively, `document(share_plot_margins='row')`, with `'column'` or `True` as today.

---

## Ugly

### 5. Fixed-size diagrams do not reserve their natural width (C, D, E)
- **Reference:** the flow diagrams sit at their natural size.
- **4.4:** track allocation ignores an eager diagram's width, so a fixed-width graph can end up in a narrower cell.
  - `min_width=` does not include the width the panel letter takes.
  - The eager `bbox` is measured under the global theme, not the preset's theme.
- **Workaround:**
  - A `lettered_width()` helper (`i.letters([d])[0].bbox.width`) sets each cell's `min_width`.
  - `i.use_theme(STYLE.theme)` runs before the diagrams are built.
- **Category:** layout grid.
- **Repro:**
  ```python
  g = i.graph({'a': i.box('a long node'), 'b': i.box('b')}, [('a', 'b')]).build()
  doc = S.document(columns=12).letters()
  doc.add('c', g, column=0, colspan=1, min_width=g.bbox.width)
  doc.compile()   # the lettered cell is short by the letter width
  ```
- **Suggested API:**
  - `doc.add(..., min_width='natural')`, the default for eager diagrams, measured under the document theme and including the letter.

### 6. `annotate(side=...)` is overridden, and notes on the two sides of a threshold collide (A)
- **Reference:** a dashed noise threshold, with "noise / 81% of connections" to its left and "signal / 19%" to its right.
- **4.4:**
  - When there is not enough room, a note given `side='w'` is moved to the east, where it overlaps the east note.
  - The page merges both into one note ("noise ← | → signal ...") with `side='n'`.
  - Lint still reports that note OFF_PANEL by 5.86 mm on the right.
- **Category:** placement engine.
- **Repro:**
  ```python
  p = i.plot_spec(height=30, x=i.log((1, 1e3)), y=(0, 1))
  p.line([(1, .2), (1e3, .8)])
  p.vline(10)
  p.annotate(10, .9, 'noise\n81%', side='w', leader=False)
  p.annotate(10, .9, 'signal\n19%', side='e', leader=False)
  ```
- **Suggested API:**
  - An explicit `side=` should be binding, and the engine should shrink or wrap the text instead of moving it.
  - `p.vline(10, name='threshold', left='noise…', right='signal…')`, which puts paired labels on the two sides of a guide.

### 7. A corner legend covers the data, and lint does not notice (A, H)
- **Reference:** the key sits in empty space.
- **4.4:** `legend(corner='se')` puts a plate over the curves. In A, the curves were cut at x=20. Lint reports no problem (`legend_corner` repro: `[]`).
- **Category:** legend (also a lint false negative).
- **Repro:**
  ```python
  p = i.plot_spec(height=30, x=(1, 1000), y=(0, 1))
  p.line([(1, .1), (1000, .15)], stroke='orange', name='dimorphic')
  p.line([(1, .2), (1000, .25)], stroke='blue', name='specific')
  p.legend(corner='se', title='cell types')
  ```
- **Suggested API:**
  - `p.legend(corner='auto')` would choose the emptiest corner.
  - Lint should report DATA_HIDDEN when a legend plate covers marks.

### 8. Adding a key row to a nested subfigure squeezes the plot height (H)
- **Reference:** the key is above the curves, and the curves are full height.
- **4.4:** with a legend row added, the plot row kept only 4.8 mm of height. The page sets `min_height=40` on the plot row as a workaround.
- **Category:** layout grid.
- **Repro:** none. `subfigure_rows` in `repros.py` compiles correctly; the failure needs the full H cell with its neuron column.
- **Suggested API:** this is a bug fix. The subfigure should take the page row's height, and legend rows should size to their content.

### 9. The force-directed network layout does not balance an isolated node (O)
- **Reference:** a 12-node community network, hand-arranged, with the dimorphic hub at the center.
- **4.4:**
  - With `layout='force'`, the isolated node was thrown to the corner and the rest collapsed toward a point.
  - The small repro only shows the isolated node pushed to one side.
  - The page uses `layout='circular'`, and no node can be pinned to the center.
- **Category:** bug / missing option.
- **Repro:**
  ```python
  p = i.plot_spec(height=40, width=40)
  p.network(['a', 'b', 'c', 'lonely'], [('a', 'b', 5), ('b', 'c', 3), ('c', 'a', 2)], layout='force')
  ```
- **Suggested API:**
  - `p.network(..., layout='force', center='hub', pin={'hub': (0, 0)})`, with components packed side by side.

### 10. A raster matrix rejects transparent missing cells, and a matrix cannot take a color per row (M)
- **Reference:** a connectivity matrix with one hue per cell class, shaded by weight.
- **4.4:**
  - `matrix(raster=True, missing='none')` raises `ColorError`.
  - The vector fallback (7 layers of 96k cells) is too slow.
- **Workaround:**
  - One raster with a banded, stepped ramp: `value = 2*class + shade`, with stops that go from white to each class color.
  - Side effect: lint's KEY_MISMATCH fires, because the key's colors are reached only through the ramp (see the lint false positives).
- **Category:** bug + missing option.
- **Repro:**
  ```python
  p = i.plot_spec(height=30, x=[0, 1, 2], y=[0, 1, 2])
  p.matrix([[1, None, 2], [None, 3, None], [4, None, 5]], x=[0, 1, 2], y=[0, 1, 2],
           missing='none', raster=True)   # ColorError
  ```
- **Suggested API:**
  - `p.matrix(values, color=row_classes, colors={'ascending': '#8db878', ...}, shade=i.log(...))`, which gives a hue per row or class, with the value mapped to lightness.

### 11. Graph arrowheads ignore the edge stroke color, and graph circles render as ellipses (C)
- **Reference:** amber links with amber heads, and round nodes.
- **4.4:**
  - The edge extra `{'stroke': AMBER}` colors the shaft, but the arrowhead stays black.
  - `i.circle(..., width=3.4, height=3.4)` comes out as an ellipse once it is placed as a graph node.
- **Category:** bug (diagram).
- **Repro:**
  ```python
  i.graph({'a': i.circle(i.text('a'), width=3.4, height=3.4),
           'b': i.circle(i.text('b'), width=3.4, height=3.4)},
          [('a', 'b', {'stroke': '#e0a526', 'stroke_width': .5})], direction='down').build()
  ```
- **Suggested API:**
  - Heads should inherit `stroke`, with `head_color=` as an override.
  - A circle node should keep its aspect ratio: `i.circle(..., size=3.4)`.

### 12. Graph layout cannot force a same-rank edge, and a note next to a node collides with the link (E)
- **Reference:** "discard" hangs to the right of the threshold box, with the ~80%/~10% note beside it. The yes/no branches run horizontally.
- **4.4:** there is no same-rank constraint. The note stacked under "discard" is crossed by the threshold→iso link (a LINK_CROSSES error, 8.44 mm), and "t-statistics" cannot be an edge annotation in a side margin.
- **Category:** diagram / placement engine.
- **Repro:**
  ```python
  i.graph({'t': i.box('threshold'), 'd': i.box('discard'), 'x': i.box('next')},
          [('t', 'd', 'no'), ('t', 'x', 'yes')], direction='down').build()   # 'd' goes a rank below, not beside
  ```
- **Suggested API:**
  - `i.graph(..., same_rank=[('threshold', 'discard')])`.
  - Node extras such as `{'note': i.text(...), 'note_side': 'e'}` that the router avoids.

### 13. A category axis cannot repeat labels or group them (F)
- **Reference:** bars are labeled ♂ ♀ ♂ ♀, with the group labels "in" and "out" underneath.
- **4.4:** `i.categories` requires distinct labels, so the labels became "in ♂", "in ♀" and so on. They do not fit flat at 2 of 12 columns, so they are rotated 90°.
- **Category:** missing option.
- **Repro:**
  ```python
  i.categories({'in-m': 'k', 'in-f': 'k', 'out-m': 'k', 'out-f': 'k'},
               labels={'in-m': '♂', 'in-f': '♀', 'out-m': '♂', 'out-f': '♀'})   # DiagramError
  ```
- **Suggested API:**
  - `i.categories(keys, labels=..., groups={'in': ['in-m', 'in-f'], 'out': [...]})`, which draws a second tier of group labels.

### 14. A wide axis label eats the data width of a narrow plot (F, H)
- **Reference:** an axis label longer than the plot runs past the plot's frame.
- **4.4:** the label's width sets the margins. At 36 mm, "fraction of dimorphic in- or outputs" leaves 2.84 mm of data.
- **Category:** layout grid.
- **Repro:**
  ```python
  p = i.plot_spec(height=34, x=(0, 1), y=(0, 1)); p.line([(0, 0), (1, 1)])
  p.axes(x='fraction of dimorphic in- or outputs', y='y')
  doc = S.document(width=36, columns=1); doc.add('x', p); doc.compile()   # 2.84 mm of data
  ```
- **Suggested API:**
  - Wrap or overhang the label: `p.axes(x=..., x_options={'label_wrap': True})`, or `label_overhang=True`.

### 15. Anatomy artwork needs the private `inklet.core` (B, D, K, P)
- **Reference:** projected neuron skeletons and neuropil meshes.
- **4.4:** the anatomy views reused from the prior art build on internal primitives. No public API embeds a projected mesh or skeleton as a sized diagram. The views come out correctly, but the example depends on private modules.
- **Category:** artwork embedding.
- **Repro:** `grep -n "inklet.core" examples/inspo/anatomy.py`, which contains `from inklet.core import PathPrim, Subpath, Vec2`. The anatomy module is the reused prior art, and it also uses `inklet.three`.
- **Suggested API:**
  - `i.projection(mesh | paths, view='front', width=..., color=..., name=...)`, which returns a Diagram with lint-visible names.

### 16. The page ends up about 40% taller than the reference
- **Reference:** about 250 mm.
- **4.4:** about 347 mm (4098 px at 300 dpi). The height is the sum of entries 1, 5, 8 and 14:
  - keys moved into rows;
  - plots held at their min_height;
  - diagrams kept at their natural width.
- **Category:** layout grid.
- **Repro:** the full page only.
- **Suggested API:** `document(height=250)`, with the rows shrinking to fit and reporting which cells hit their minima.

---

## Minor

### 17. A connect label must be a Diagram, and a plain string crashes (C, D)
- **4.4:** `i.connect(a, b, within=row, label='x')` raises `AttributeError`.
- **Category:** bug.
- **Repro:**
  ```python
  a, b = i.box('a'), i.box('b'); row = i.hstack([a, b], gap=10)
  i.overlay([row, i.connect(a, b, within=row, label='x')])
  ```
- **Suggested API:** accept a `str` and wrap it in `i.text` using the theme's size.

### 18. `highlight=` on an icicle fails when given a list (L)
- **4.4:** plot_spec replay turns the list into a tuple, and the tuple is read as a single path ("names no node"). A `set` works.
- **Category:** bug.
- **Repro:**
  ```python
  p = i.plot_spec(height=30, x=(0, 1), y=(0, 1))
  p.icicle({'a': {'a1': 1, 'a2': 2}, 'b': {'b1': 3}}, highlight=['a1', 'b1'])
  ```
- **Suggested API:** accept any iterable of names; use an explicit `path=(...)` to name a path.

### 19. Text color is `fill=`, not `color=` (A, C, H, I/J)
- **4.4:**
  - `i.text('x', color=...)` raises `TypeError`.
  - `p.label_points(..., color=...)` raises `TypeError`.
  - Both need `fill=`, which breaks the color=/name=/size= convention the plots use.
- **Category:** missing option (convention).
- **Repro:** `i.text('dimorphic', color='#e0a526')`.
- **Suggested API:** accept `color=` on `text`, `label_points`, `tag` and `annotate`, and keep `fill=` as a deprecated alias.

### 20. Legend entries cannot have colored text (H, I/J, Q)
- **Reference:** entries such as "dimorphic types" are written in their series color, with no swatch.
- **4.4:** only swatch plus ink text is possible.
- **Category:** legend.
- **Suggested API:** `i.legend(entries, style='text')`, or per entry `(name, color, {'swatch': False})`.

### 21. `i.tag` has no `stroke_dash`, and `i.box(pad=...)` takes only a scalar (E)
- **4.4:**
  - `i.tag('discard', stroke_dash=(.5, .5))` raises `TypeError`.
  - `i.box('x', pad=(.5, 1))` raises `UnitError`.
- **Category:** missing option.
- **Suggested API:**
  - `i.tag(..., stroke_dash=)`, the same as `box`.
  - `pad=(x, y)` or `pad=(top, right, bottom, left)`.

### 22. No per-cell opt-out from page letters, and no page divider
- **Reference:** a horizontal rule separates the page's lower block.
- **4.4:**
  - `doc.add(..., letter=False)` raises `TypeError`.
  - Any rule added as a cell would take a letter.
  - The page has no rule.
- **Category:** layout grid.
- **Suggested API:**
  - `doc.add(..., letter=False)`.
  - `doc.rule(row=3)`.

### 23. A responsive factory is handed about 0.14 mm more than the letter leaves (D)
- **4.4:**
  - D's factory, built at zero width, reports its minimum.
  - The cell then passes a width 0.14 mm over the space left after the letter.
  - The page adds 0.5 mm of tolerance.
- **Category:** bug.
- **Suggested API:** this is a bug fix. The factory width should equal the cell width minus the letter gutter exactly.

### 24. "plot furniture did not settle after 24 measurement passes" (layout)
- **4.4:** this happened once, while C's and D's spans were being tuned. It went away after the spans were rebalanced.
- **Category:** layout grid.
- **Repro:** not kept.
- **Suggested API:** the error should name the cell and the furniture that is oscillating.

### 25. A vline label is pushed off the panel, and `place_in_clear_space` fails in height-capped cells (A, P)
- **4.4:**
  - `p.vline(10, label=...)` near the right edge puts the label outside the frame.
  - In P, `place_in_clear_space` found no room for the key once the view was capped at 80 mm. The key is stacked below the view instead.
- **Category:** placement engine.
- **Suggested API:**
  - `vline(label_side='auto')`, clamped to the frame.
  - `place_in_clear_space` should report the largest free box it found.

### 26. The network `size_key` draws circles for square nodes, and white labels sit on light nodes (O)
- **4.4:**
  - The key's glyphs ignore `shape='square'`.
  - A white label on the light grey node gives LOW_CONTRAST.
- **Category:** legend / bug.
- **Suggested API:**
  - The key should inherit the node shape.
  - Label color should default to `'auto'`, meaning contrast-picked.

### 27. Category axes have no gap or separator and no per-tick emphasis (N)
- **Reference:** gaps between cluster groups, and a bold label for the dimorphic cluster.
- **Category:** missing option.
- **Suggested API:** `i.categories(..., gaps_after=['c3'], emphasis={'c7': 'bold'})`.

### 28. No broken axis or zero strip on a log axis (G)
- **Reference:** a log–log scatter with a separate "0" strip for connections that are absent in one sex.
- **4.4:** the page approximates it with `i.symlog(linthresh=1)` and a pale band.
- **Category:** missing option.
- **Suggested API:** `i.log((1, 1e5), zero='strip')`.

### 29. No glyph at the end of a line, and no rotated direct segment labels (A, F)
- **Reference:** A's curves end in a small marker. F labels segments inside the bars.
- **Category:** missing option.
- **Suggested API:**
  - `p.line(..., end_marker='circle')`.
  - `p.bars(..., segment_labels=True, label_rotate=90)`.

### 30. The icicle collapses levels, and its bottom count labels crowd (L)
- **Reference:** a four-level hierarchy with every level visible.
- **4.4:** levels with a single child are merged, and the adjacent "311" labels overlap (a lint OVERLAP error).
- **Category:** missing option.
- **Suggested API:** `p.icicle(..., collapse=False, labels='fit')`.

### 31. The axis tells the user it omitted explicitly supplied ticks (H)
- **4.4:** it raises `UserWarning: axis omitted N of M explicitly supplied ticks` at narrow widths. A warning is fine; an option to keep them all is missing.
- **Category:** text.
- **Suggested API:** `ticks=..., thin=False`, which already exists on `axis` but cannot be set through `axes()` without `x_options`. Document it there.

### 32. Calling `p.axis('bottom', ...)` after `p.axes()` adds a second bottom axis (F)
- **4.4:** `axes()` already creates the bottom axis. A second `axis('bottom', rotate=90)` draws a second set of tick labels over the first, instead of updating the existing axis. Lint catches the result as OVERLAP, and the page uses `axes(x_options={'rotate': 90})`.
- **Category:** bug.
- **Repro:**
  ```python
  p = i.plot_spec(height=30, x=['a', 'b'], y=(0, 1)); p.bars(['a', 'b'], [.3, .6])
  p.axes(y='y'); p.axis('bottom', rotate=90)
  ```
- **Suggested API:** `axis(side)` updates the axis on that side; `axis(side, at=...)` adds another.

### 33. Data-level approximations, which are not API gaps
These are recorded so that they are not mistaken for API gaps:

- **K:** shows a signed male−female synapse contrast per neuropil rather than the reference's density projection.
- **M:** is built at community level.
- **I/J:** the pies are smaller than in the reference, because the 4-column cell cannot give them more room.

---

## Lint false positives

These findings appear in the page's lint report, but the page is correct:

| Code | Where | Why it is wrong |
|---|---|---|
| CROWDING (info) | K, D, P, J (the anatomy views) | Overlapping translucent meshes and skeletons are the artwork. They are not labels. |
| KEY_MISMATCH (warning) | M | The class colors reach the matrix through a stepped ramp (entry 10), so lint does not see them drawn. |
| OVERLAP (error and warning) | D tables | `value_table` cell rects overlap their own text, and the header row's line box overlaps the value row by 0.31 mm. The table reads cleanly. |
| OVERLAP (warning) | G | The scatter markers overlap by design (dense data). |
| (false negative) | A, H | A corner legend plate covering curves reports nothing (entry 7). |
