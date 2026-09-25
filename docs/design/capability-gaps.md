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
| 13 | Dot-plot matrix with a size key | `scatter` per row plus a hand-drawn key | Done: `Panel.dotplot`, `Panel.size_key` |
| 14 | Kaplan-Meier curves with a number-at-risk table | Estimate by hand, `step`, `band` and `text` per cell | Done: `Panel.kaplan_meier`, `Panel.at_risk` |
| 15 | Forest plots with text columns | `errorbars` plus `Panel.text` per row and column | Done: `inklet.forest` |
| 16 | Embedding scatter named by cluster | `scatter` per cluster and hand-placed names | Done: `Panel.embedding` |
| 17 | Split violins for two conditions | Two `violin` calls with hand-clipped halves | Done: `Panel.split_violin` |
| 18 | Many significance brackets, stacked | `bracket` per pair with hand-set heights | Done: `Panel.brackets`, `inklet.plot.format_p` |

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
margin, otherwise outside the rim on the slice's middle angle. A label that
meets another label or its leader searches nearby spots, a third of the type
size apart, outward and round the rim, nearest first. Labels are placed in
slice order; when one cannot clear, the reverse and middle-out orders are
tried too, and the order that clears most labels, then moves them least, is
kept. A label that ends up away from its own slice gets a
hairline leader from the rim at its slice to the nearest point of its box,
never crossing another label, leader or connector; the indices are listed
under `leaders` in the `pie_labels` note. Radar ring values
(`radar_grid(values=True)`) are placed when the panel is built: on the
bisector of the spoke gap where the most values stay a quarter of the type
size clear of every series' edges and vertices, with a paper halo. Values
that cannot keep clear are left out; the `radar_rings` note records the gap,
the values and the clearance. They stay off by default: on a busy chart only
a few values fit.

**Pie breakout bar.** `breakout` reads the slice angles and values that
`pie` records in its `pie_labels` note, so it must follow a `pie` call on the
same panel. The chosen slices must be adjacent. The bar is placed at a fixed
offset from the rim in panel millimetres; connectors run from the rim at the
two outer slice edges to the bar's near corners, upper to top. Part labels
sit beside the bar at the segment centres and are moved down, then lifted
back from the bottom, only as far as needed to clear each other. Default part
colours are shades of the slice colour. When `inklet.polar` was not given
`zero` or `winding`, `breakout` chooses them: the winding runs the chosen
slices down the side that faces the bar (clockwise on the right,
counter-clockwise on the left) and `zero` puts their middle on the bar's axis.
The pie is then drawn again in place. On a busy panel the panel keeps a
journal of its drawing calls and makes them all again under the turned angles,
so grids, axes and text drawn before or after the pie turn with it. Content
passed to `draw`, `under` or `over` in panel coordinates cannot be redrawn,
and an earlier `breakout` is not repeated; either keeps the pie as it is. Outside
pie labels that meet a connector or the bar try spots turned within their
slice and up to two type sizes further out, and take the smallest change
that clears; the ones that cannot are listed under `crossing` in the
`pie_labels` note. The breakout title is kept clear the same way.

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
a round tick, with at most as many ticks as fit without thinning. The
narrow set-size axis ends at the largest set instead when the round tick
would be more than 1.25 times that set. With value
labels, the default column pitch widens to fit the widest label.

**Dot plot.** Circle area is proportional to the size value: the diameter is
`diameter * sqrt(v / top)`, with `top` the largest size and `diameter` 0.9 of
the smaller band step by default. Colours use the `matrix` default ramps
(sequential, or diverging when the values straddle `center`). A missing size
or colour draws nothing; a size of 0 draws nothing and is listed as `empty`
in the `dotplot` note. `size_key` reads the panel's last `dotplot`, or an
`AreaScale` from `inklet.plot.area_scale` for a sized `scatter`; its default
values are round ticks up to `top`. The key is placed like `colorbar`, beyond
the ink already drawn.

**Kaplan-Meier.** The product-limit estimate with Greenwood's variance; the
default band is log-log (`S ** exp(±z se / log S)`), `band="linear"` clips
`S ± z sd` to [0, 1]. A subject censored at an event time is at risk at that
time. Where the estimate reaches 0 the variance and band are undefined and
the band stops. The estimator matches R `survfit` and `scipy.stats.ecdf`.
There is no log-rank test: `pvalue=` only formats and places a supplied
value. `at_risk` counts subjects with duration at or after each x tick and
draws one row per curve below everything drawn so far, with names in the
curve colours; call it after `axes`.

## Layout limits found by the dense figure

`examples/dense_figure.py` worked around these library limits.

| Limit | Workaround | Status |
| --- | --- | --- |
| `share_plot_margins=True` reserved the largest left and right furniture on every plot, which squeezed grids with mixed spans | Sharing turned off | Done: left and right margins are shared along vertical grid lines; `'all'` keeps the whole-grid rule |
| Sharing also gave every plot the tallest data height, overriding the heights chosen per row | Sharing turned off | Done (4.2): data heights are shared along rows only; `'all'` keeps the tallest height; the dense figure shares margins |
| A top or bottom legend, including an inside legend moved above the plot, could only be as wide as the data area | Panel B widened | Done: the key uses the whole panel width when that saves rows |
| A label on a link a few millimetres long floated a label height or more above the boxes, or sat on the arrowhead | The circuit panel has no link labels | Done: nearest clear spot, flagged and reported by `LABEL_OFF_LINK` |

**Grid-line sharing.** A plot's left edge is grid line `column` and its
right edge is grid line `column + colspan`. The left margin of a plot is the
largest measured left margin among plots on its left line, and the right
margin the largest among plots on its right line. With an automatic page
height, the data height is the tallest among plots in the same row and row
span, so each row keeps its authored heights; `'all'` gives every plot the
tallest data height in the grid. The dense figure shares margins.

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

**Forest plots.** `forest` builds one panel with a row per study; the text
columns are drawn outside the plot area on the same row positions, so they
line up with the intervals. Square areas are proportional to the weights,
between 0.7 and 2.4 mm a side. An interval end beyond `limits` stops at the
limit with an arrowhead and is listed under `clipped` in the `forest`
note. It returns a `Diagram`, like `upset`.

**Embedding scatters.** A cluster's name sits at the member point nearest
the coordinate-wise median (distances scaled by the median absolute
deviation), so it stays on the data for curved clusters. A name that would
overlap one already placed moves to the nearest free candidate position.
They also keep clear of other clusters' points, found on a grid of dot
cells, and of other clusters' outlines; a name may sit over its own
cluster and cross its own outline line. With `outline="fill"` it does not
lap its own tint's edge either, which the linter reports as an overlap. A name
that cannot clear another cluster's points takes the position that covers
the fewest, and is listed under `covering` in the `embedding` note.
`outline=` draws each cluster's core: the region whose smoothed density
reaches the level that the `outline_core` share of its points reach. Points
beyond five robust spreads are left out, and an island holding under a tenth
of the points is dropped, so strays neither enlarge the outline nor add
islands.

**Theta labels beside a breakout.** A `theta_axis` label that comes within
half the small gap of a breakout connector, the bar or the title is nudged
along the rim or outward, the smallest move first and at most the type
size, and never onto another label. A label no nudge clears is dropped, as
is a curved label that touches one. The choice is listed in the axis's
`theta_axis` note and in `axis_labels` of the `pie_breakout` note.

**Split violins.** Each half is the `violin` density of its group; with
`scale="shared"` the wider peak of the two halves sets the width, so the
halves compare as densities. A half with fewer than two values is skipped
and listed under `empty` in the note.

**Stacked brackets.** Comparisons are drawn shortest page span first. Each
bracket clears the data between its ends by `gap("xs")` and earlier
brackets by that plus the tick length, so ticks at a shared end do not touch
the bracket below. `format_p` uses strict bounds: p = 0.001 is `**`.

## Deferred work

- Done (4.2): leaders for pie labels placed outside the rim, drawn only
  for labels moved away from their slice.
- Done (4.2): a pie drawn with other content on its panel is turned by
  `breakout`; the other content is drawn again with it.
- Done (4.2): radar ring values are placed at build time in the spoke gap
  with the most room, clear of every series and on a paper halo. They stay
  off by default, since a busy chart leaves room for only a few.
- Done (4.2): `label_points` is placed when the panel is built, so it avoids
  marks drawn after the call. Several calls are placed in call order.
- Done (4.3): per-cluster outlines for `Panel.embedding`, as density
  contours round each cluster's core.
- Done (4.3): cluster names avoid the points of other clusters.
- Done (4.3): theta-axis labels on a pie turned by `breakout` keep off the
  connectors, nudged or dropped.
