# The page-grid combinator: measured, and declined

> Historical design study from before v2. For the implemented document grid,
> see [page layout](../layout.md) and [the compilation contract](v2.md).

*Round 5, 2026-08-24. BACKLOG's item reads: "Vertical whitespace between panel
rows is large and uneven in almost every multi-panel corpus figure (gallery,
hard_figure, draw_probe, mega). Rows are stacked with one gap while the panels
in them differ in height by 20mm or more, so the figure reads as four blocks
floating rather than as a page. Not a bug in any one file -- it is the absence
of a 'page grid' combinator that gives rows a common rhythm. Worth a design
note before anyone builds it."*

This is that note. The short version: **the diagnosis is right, the proposed
cure is not, and the corpus wants something smaller.** The measurements are
below, all taken on the built trees of the figures the item names.

## What is actually uneven

Two different things get called "uneven whitespace", and only one of them is
real.

**The gap between rows is not uneven.** Where a figure stacks rows, it gets
exactly the gap it asked for, to the hundredth of a millimetre:

| figure | combinator | rows | whitespace between rows |
|---|---|---|---|
| `stress/draw_probe.py` | `vstack(gap=10)` | 19.88 / 62.51 / 62.54 mm tall | 10.00, 10.00 mm |
| `stress/hard_figure.py` | `grid(cols=2, row_gap=9)` | 96.03 / 27.89 mm tall | 9.00 mm |
| `figures/drug_discovery.py` | `vstack(gap=6)` | five bands, 3.84–92.46 mm | 6.00 × 4 mm |

A combinator that gives rows "a common rhythm" has nothing to fix here. The
rhythm is already common; it is the *rows* that differ, by 42.65 mm in
`draw_probe` and 68.14 mm in `hard_figure`.

**The whitespace inside a row is uneven, and no rhythm removes it.**
`hard_figure`'s top row is 96.03 mm tall and its two cells differ by 15.47 mm,
so the shorter one — panel (a), the beam path — floats in its track with a
band of nothing under it. Look at the render and that void is what reads as
"blocks floating": roughly a fifth of the page height, under panel (a), above
panel (c). It is not spacing. It is a 96 mm track holding an 80 mm panel, and
the only things that close it are shrinking the track (which crops (b)) or
growing the content (which is an authoring decision, `inklet.fit`'s job, not a
combinator's).

## What a rhythm would cost

`examples/gallery.py` is the worst case in the corpus and the fairest test:
sixteen panels, `facets(cols=2, gap=5, row_gap=4)`, every one of them
declaring a plot area of exactly **21.50 × 15.50 mm**. If any figure should
fall onto a rhythm for free, it is this one. Measured on its own cells, with
`facets._place`'s track arithmetic reproduced and varied:

| rhythm | gap between data regions | spread | page height |
|---|---|---|---|
| today | −5.88 … 11.55 mm | 17.43 mm | 285.08 mm |
| A: one fixed pitch, the tallest track (48.21 mm) | 11.55 … 21.46 mm | 9.91 mm | **381.66 mm** |
| B: quantise each track up to a 2 mm baseline | −4.33 … 13.34 mm | 17.67 mm | 294.21 mm |
| B: … 4 mm baseline | −2.33 … 15.34 mm | 17.67 mm | 304.21 mm |
| B: … 6 mm baseline | −4.33 … 17.34 mm | 21.67 mm | 308.21 mm |

Both candidate designs fail, and they fail for the same reason.

**A, a fixed pitch**, halves the spread and costs **96.58 mm of page** — a
third again as long, on a figure that is already two and a half pages. It
cannot do better: the pitch has to clear the tallest track, and gallery's rows
4 and 7 hold panels 44.21 mm tall against their neighbours' 24–29 mm, so every
other row inherits 19 mm of void it did not need.

**B, a typographic baseline grid**, is the design that sounded most promising
— it is what a page layout program does — and it makes the spread *worse* at
every unit tried, because rounding each track up independently adds a
different amount to each. A baseline grid works on a page of running text
because the thing being quantised is one repeated unit, the line. A page of
panels has no such unit: the tracks are 28.45, 30.93, 33.05, 33.10, 34.09,
48.21 mm, and there is no number that divides them tidily.

The common cause is the one the first section named. Gallery's rows are not
ragged because the spacing is arbitrary; they are ragged because the *panels
are different sizes*, and a rhythm redistributes that difference without
removing any of it. Every millimetre a rhythm takes out of the gaps it puts
back into the tracks, and then charges page height for the privilege.

## So: declined

No `page_grid` combinator. It converges — the API is easy to write, `inklet.grid`
already has the track machinery, and either rhythm is twenty lines inside
`facets._place` — and it should not be built, because on the corpus figure it
was proposed for it either costs a third of a page or makes the number it
targets go up.

What would actually close `hard_figure`'s void is `inklet.fit(panel_a,
height=track)`, which already exists, and the decision of *which* panel gives
way is the author's. That is a figure change, not a library change.

## What the corpus does want, and it is smaller

Three findings fell out of the measurement, in ascending order of size. All
three are filed in BACKLOG.

**1. The page grid already exists and is not called that.** It is
`inklet.facets(panels, axes=False)` — the docstring says "leaves the furniture to
you and does the alignment only" — and `examples/gallery.py` is already using
it exactly that way, for sixteen panels that are not a facet grid of one
variable in any sense. Whatever a `page_grid` name would have been for, this
is it. What is missing is discoverability and a line in the cookbook, not a
combinator.

**2. `facets` sized its region off boxes when handed a lettered panel.**
Fixed in this round, and it is the reason the gallery numbers above were worth
taking: `_Cell.area` read `item.width/height` for a `Panel` and the *bounding
box* for anything else, and `inklet.letters()` returns `Diagram`s. So gallery's
grid aligned on the plot areas — `_origin_of` reads the note — and then
blocked out its region on the boxes, which differ by 12–15 mm per cell. It now
reads the declared `plot_area` first (see `facets._area_size`), which is only
possible because a note now survives the wrappers `letters` and `translated`
put round a panel (core M19).

**3. Rows of unequal panels needed an alignment argument, not a rhythm.**
`row(align="top")` and `column(align="left")`, this round. That is the case
the BACKLOG item was reaching for when it said the figure reads as blocks: a
tall member centred among short ones lifts its panel letter clear of its
neighbours', which on `figures/mouse_brain.py`'s bottom row is 5.05 mm and is
the first thing a reader sees. Alignment fixes that for nothing; a rhythm
would not have fixed it at all.

## Reproducing the numbers

`tmp/agents/r5-align/scratch/`: `rhythm.py` and `rhythm3.py` walk a built
figure for vertical stacks and grid tracks; `rhythm2.py` resolves every
declared plot area to the page and bands them; `rhythm_sim.py` is the table in
"What a rhythm would cost", reproducing `facets._place` and varying it. All
take a corpus script as their argument and change nothing.
