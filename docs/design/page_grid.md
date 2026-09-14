---
archived: true
current: ../layout.md
---

# The page-grid combinator: measured, and declined

> Historical design study from before v2. For the implemented document grid,
> see [page layout](../layout.md) and [the compilation contract](v2.md).

*Round 5, 2026-08-24.* The backlog proposed a page-grid combinator to reduce
large, uneven vertical whitespace in multi-panel figures. It identified rows
containing panels that differed in height by 20 mm or more.

Measurements of the named figures showed unequal panel heights within rows,
while the gaps between rows matched their requested values. The proposed grid
did not resolve this mismatch. The measurements and resulting changes follow.

## What is actually uneven

The measurements distinguish gaps between rows from unused space within a row.

**Gaps between rows match the requested values**, to the hundredth of a
millimetre:

| figure | combinator | rows | whitespace between rows |
|---|---|---|---|
| `stress/draw_probe.py` | `vstack(gap=10)` | 19.88 / 62.51 / 62.54 mm tall | 10.00, 10.00 mm |
| `stress/hard_figure.py` | `grid(cols=2, row_gap=9)` | 96.03 / 27.89 mm tall | 9.00 mm |
| `figures/drug_discovery.py` | `vstack(gap=6)` | five bands, 3.84–92.46 mm | 6.00 × 4 mm |

Row heights differ by 42.65 mm in `draw_probe` and 68.14 mm in `hard_figure`.
Changing the gap between rows does not change their heights.

**Unused space within a row comes from unequal panel heights.**
`hard_figure`'s top row is 96.03 mm tall and its two cells differ by 15.47 mm.
The shorter panel (a), the beam path, leaves unused space below it. Reducing the
track height would crop panel (b). Increasing panel (a)'s content height requires
an authoring change, for example with `inklet.fit`.

## What a rhythm would cost

`examples/gallery.py` has sixteen panels using
`facets(cols=2, gap=5, row_gap=4)`. Every panel declares a plot area of
**21.50 × 15.50 mm**. The following measurements reproduce and vary
`facets._place`'s track calculations using those cells:

| rhythm | gap between data regions | spread | page height |
|---|---|---|---|
| today | −5.88 … 11.55 mm | 17.43 mm | 285.08 mm |
| A: one fixed pitch, the tallest track (48.21 mm) | 11.55 … 21.46 mm | 9.91 mm | **381.66 mm** |
| B: quantise each track up to a 2 mm baseline | −4.33 … 13.34 mm | 17.67 mm | 294.21 mm |
| B: … 4 mm baseline | −2.33 … 15.34 mm | 17.67 mm | 304.21 mm |
| B: … 6 mm baseline | −4.33 … 17.34 mm | 21.67 mm | 308.21 mm |

Neither candidate improves both gap uniformity and page height.

**A, a fixed pitch**, reduces the gap spread but adds **96.58 mm** to page
height, an increase of about one third. The pitch must accommodate the tallest
track. Rows 4 and 7 contain 44.21 mm panels beside 24–29 mm panels; using that
pitch throughout adds unused space to shorter rows.

**B, a typographic baseline grid**, increases the gap spread at every tested
unit. Rounding each track up independently adds different amounts to tracks
of different heights. The measured tracks are 28.45, 30.93, 33.05, 33.10,
34.09 and 48.21 mm, so they do not share a repeated height like lines of text.

Both approaches redistribute the space caused by unequal panel sizes and
increase total page height without resolving the underlying size differences.

## So: declined

The proposed `page_grid` combinator was declined. On the tested figure, a fixed
pitch increased page height by about one third, while a baseline grid increased
the gap spread.

For `hard_figure`, `inklet.fit(panel_a, height=track)` could fill the unused
space by rebuilding panel (a) at the track height. The author must decide which
content can change size.

## What the corpus does want, and it is smaller

The measurements produced three findings, recorded in the backlog at the time.

**1. `inklet.facets(panels, axes=False)` already supported panel alignment.**
`examples/gallery.py` used it for sixteen different panels. The missing item
was documentation showing that use, rather than another combinator.

**2. `facets` used bounding-box dimensions for lettered panels.**
`_Cell.area` read `item.width/height` for a `Panel` and bounding-box dimensions
for other objects, including the `Diagram`s returned by `inklet.letters()`.
The grid therefore aligned plot areas but allocated regions using boxes that
differed by 12–15 mm per cell. The fix made `facets._area_size` read the declared
`plot_area` first and preserved that metadata through `letters` and `translated`
wrappers (core M19).

**3. Rows of unequal panels needed an alignment option.**
This round added `row(align="top")` and `column(align="left")`. Centring unequal
panels displaced the panel letters in `figures/mouse_brain.py`'s bottom row by
5.05 mm. Top alignment removed that displacement without changing row spacing.

## Reproducing the numbers

`tmp/agents/r5-align/scratch/`: `rhythm.py` and `rhythm3.py` walk a built
figure for vertical stacks and grid tracks; `rhythm2.py` resolves every
declared plot area to the page and bands them; `rhythm_sim.py` is the table in
"What a rhythm would cost", reproducing `facets._place` and varying it. All
take a corpus script as their argument without modifying it. These paths refer
to the original study workspace; the recorded results above are historical.
