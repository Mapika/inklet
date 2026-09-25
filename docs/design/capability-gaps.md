# Plotting capability gaps

This note lists the plot types and annotations that dense journal figures use
and that Inklet did not provide as a single call. The reference pages were
two Cell figure pages (stacked cell-type bars with counts, dumbbells,
diverging bars, radar charts, pies with a breakout bar, a labelled scatter,
cumulative curves and several colorbars on one page).

For each gap, "before" is what an author had to write. The ranking puts
first the gaps that appear most often in published figures and that took the
most hand-written geometry.

## Audit: already provided

These were checked and are not gaps:

| Need | Existing API |
| --- | --- |
| Significance brackets | `Panel.bracket` |
| Zoom insets | `Panel.inset(zoom=)` |
| Colorbars | `Panel.colorbar`, `inklet.plot.colorbar` |
| Swarm, box, violin, histogram | `Panel.swarm`, `boxplot`, `violin`, `hist` |
| Sankey and alluvial bands | `Panel.ribbon`, `inklet.sankey` |
| Network graphs | `inklet.graph` |
| One annotation with a leader | `Panel.annotate`, `Panel.guide` |
| Label columns beside lines | `label_column`, `place_labels` |
| Polar lines, bands, roses | `PolarPanel.line`, `band`, `rose` |
| Diverging bars | `bars(stacked=True)` with negative values and `format=lambda v: f"{abs(v):g}"` on the axis |
| Heatmaps | `Panel.matrix` |

## Ranked gaps

| Rank | Gap | Before | Status |
| --- | --- | --- | --- |
| 1 | Value labels on bars and stacked segments | `Panel.text` per bar, with the segment arithmetic copied from `marks.py` | Done: `Panel.bars(labels=)` |
| 2 | Dumbbell and lollipop plots | `line` plus two `scatter` calls per category | Done: `Panel.dumbbell`, `Panel.lollipop` |
| 3 | Labels for many points, clear of each other | `Panel.text` or `annotate` per point with hand-set offsets | Done: `Panel.label_points` |
| 4 | Empirical cumulative distributions | Sort, count ties and call `step` | Done: `Panel.ecdf`, `inklet.plot.ecdf` |
| 5 | Radar charts | `PolarPanel.line(interpolate=False)` plus a hand-drawn polygon grid and labels | Done: `PolarPanel.radar`, `PolarPanel.radar_grid` |
| 6 | Pie and donut charts with labels | `draw.sector` per slice and hand-placed labels | Done: `PolarPanel.pie` |
| 7 | Pie breakout bar (a slice expanded into a stacked bar) | Compose by hand | Done: `PolarPanel.breakout` |
| 8 | Ridgeline (stacked density curves) | `fill` per group with offsets | Done: `Panel.ridgeline` |
| 9 | Raincloud (half violin, box and points) | `violin` plus `swarm` with offsets | Done: `Panel.raincloud` |
| 10 | Dendrogram beside a heatmap | Hand-drawn elbows | Done: `Panel.dendrogram` |
| 11 | UpSet plots | Matrix of dots plus bars, by hand | Done: `inklet.upset` |
| 12 | Volcano plot helper | `scatter`, `hline`, `vline` and now `label_points` | Done: `Panel.volcano` |

## Implemented behaviour

**Bar value labels.** Labels use the same slot and span arithmetic as the
rectangles. A label goes inside when it fits (the text width plus a quarter
of the type size on each side along the bar, and the full font box across
it), otherwise past the bar end. A stacked segment that does not fit is
omitted and listed in the `bar_labels` note. Inside labels use the theme ink
or paper, whichever has more contrast with the fill. Labels are never
shrunk.

**Dumbbell and lollipop.** Positions come from the band scale, like `bars`.
Missing values (`None`, NaN) draw no dot; a dumbbell category with one value
draws no connector.

**Point labels.** Deterministic candidate search round each point (8
directions on the first ring, then 16 per ring out to `reach`, plus boxes
above, below and beside the point slid so one end lines up with it).
Candidates are scored by overlap with marks, labelled points and placed
labels, and by crossings of stroked lines, leaders and labelled points, plus
distance and a fixed cost for needing a leader. After the first pass, a
repair pass lifts each label on a leader together with its neighbours,
places it first, and keeps the result when it scores better. Dense scatters
stored as marker batches are expanded into per-marker boxes and indexed on a
grid. Leaders are drawn only for labels off the first ring. Unresolved
labels are listed in the `point_labels` note. A wide label on a point near
the plot edge, with a dense cloud round it, can still need a long leader:
the search does not place labels outside the plot area.

**ECDF.** Ties share a step; missing values are excluded from the
denominator. `complementary=True` gives the share strictly above each value.
On a log axis, points that cannot be mapped are dropped.

**Radar and pie.** Both require a whole-turn polar panel and follow its
`zero` and `winding`. Radar rings are polygons by default. Pie labels go
inside a slice when the label box fits within the annular sector with a
margin, otherwise outside the rim, moved outward to avoid other outside
labels.

**Pie breakout bar.** `breakout` reads the slice angles and values that
`pie` records in its `pie_labels` note, so it must follow a `pie` call on the
same panel. The chosen slices must be adjacent. The bar is placed at a fixed
offset from the rim in panel millimetres; connectors run from the rim at the
two outer slice edges to the bar's near corners, upper to top. Part labels
sit beside the bar at the segment centres and are moved down, then lifted
back from the bottom, only as far as needed to clear each other. Default part
colours are shades of the slice colour. When `inklet.polar` was not given
`zero` or `winding` and the pie is the only content on the panel, `breakout`
chooses them: the winding runs the chosen slices down the side that faces the
bar (clockwise on the right, counter-clockwise on the left) and `zero` puts
their middle on the bar's axis. The pie is then drawn again in place. Outside
pie labels that meet a connector or the bar try spots turned within their
slice and up to two type sizes further out, and take the smallest change
that clears; the ones that cannot are listed under `crossing` in the
`pie_labels` note.

**Ridgeline.** Needs a band y scale and a continuous x scale. Each ridge's
baseline is the lower edge of its category's step, and the density is
evaluated over the whole x domain with the `violin` bandwidth rule. Ridges
are drawn top-down with opaque fills. `fit=True` scales all ridges by one
factor so the top ones stay in the plot area; when the top row holds the
tallest peak this can reduce the overlap to about one row.

**Raincloud.** Uses the `violin` groups, bandwidth rule and `cut`, and the
`boxplot` statistics. Each slot is split into lanes by fixed fractions of its
half-width: the half violin from the centre line to 0.95, the box centred at
-0.2 and the points across -0.32 to -0.92. The box has no caps and no
outlier points. Jitter is uniform within the points lane from a generator
seeded by `seed`; `points="swarm"` packs the points with the `swarm` fit,
which shrinks the dots of a crowded group. The half violin's fill is the
group colour blended at least 35% towards paper, and further for dark
colours until its contrast with paper is at most 3:1.

**Volcano.** A point is significant when p is strictly below `p_threshold`
and its absolute fold change is at least `fold_threshold`. Points are drawn
with `scatter` in the order ns, down, up, and threshold rules with `hline`
and `vline`, so they sit under the points. Labels go to the `top`
significant points inside the plot area, ranked by p and then by absolute
fold change. A p-value of 0 is drawn at the smallest positive p-value;
missing values are skipped. The default up and down colours are from the Tol
sunset palette, and the ns colour is the theme's muted colour blended
towards paper. In a dense cloud `label_points` can leave a label closer than
the 1 mm lint clearance to an unlabelled point.

**Dendrogram.** The leaf order is SciPy's default: the first cluster of each
merge row on the left. Leaves sit at positions 0 to n-1 and each merge
midway between its outer children. A nested tree's merges are one unit
above their tallest child, and a node may have more than two children. On a
band leaf axis the categories must equal the leaf order, or `dendrogram`
raises an error naming the order to use; it does not reorder the band or
the matrix. `threshold=` colours the subtrees whose merges are all below it,
one colour each from left to right, skipping palette colours too close to
the ink.

**UpSet.** Intersections are exclusive: an element of a mapping is counted
once, in the intersection of exactly the sets that contain it. Set sizes
count all the data, including intersections removed by `min_size` or
`max_intersections`. `upset` builds three `Panel`s (intersection bars,
matrix, set bars) on the same band scales and lays them out with `row` and
`column`, which line up plot areas; it returns one `Diagram`, not a panel,
so further drawing into the three panels is not possible. Size axes end on
a round tick for the intersection bars and at the largest set for the set
bars, with at most as many ticks as fit without thinning. With value
labels, the default column pitch widens to fit the widest label.

## Layout limits found by the dense figure

`examples/dense_figure.py` worked around these library limits.

| Limit | Workaround | Status |
| --- | --- | --- |
| `share_plot_margins=True` reserved the largest left and right furniture on every plot, which squeezed grids with mixed spans | Sharing turned off | Done: left and right margins are shared along vertical grid lines; `'all'` keeps the whole-grid rule |
| A top or bottom legend, including an inside legend moved above the plot, could only be as wide as the data area | Panel B widened | Done: the key uses the whole panel width when that saves rows |
| A label on a link a few millimetres long floated a label height or more above the boxes, or sat on the arrowhead | The circuit panel has no link labels | Done: nearest clear spot, flagged and reported by `LABEL_OFF_LINK` |

**Grid-line sharing.** A plot's left edge is grid line `column` and its
right edge is grid line `column + colspan`. The left margin of a plot is the
largest measured left margin among plots on its left line, and the right
margin the largest among plots on its right line. The dense figure still
leaves sharing off: sharing also gives every plot the tallest data height,
which would override the heights chosen per row.

**Panel-wide keys.** The key is fitted to the data width first. If the
panel, including the tick labels and axis name left of the data, is wider,
the key is refitted to that width and kept when it has fewer rows. It is then
centred on the data if it fits within the data width, and otherwise starts at
the panel's left edge, next to the panel letter.

**Short link labels.** When no candidate spot beside the line is clear, the
label is moved out along the normal from eleven points on the line, in
0.25 mm steps up to two label sizes. It must be 0.25 mm clear of nodes, other
label plates and the arrowheads, and about the label offset from other
shafts. The smallest step wins, and ties go to the point nearest the middle
of the line.

## Deferred work

- Leaders for pie labels placed outside the rim.
- A pie drawn after other content on its panel is not turned by `breakout`.
- Ring values on radar charts sit inside the data region and collide with
  most polygons; `radar_grid(values=True)` draws them, and they are off by
  default.
- `label_points` avoids only what is drawn before it is called.
