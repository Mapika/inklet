# Layout solver: compact pages from declared flexibility

*Draft, 2026-09-29, for 5.0.* Status: proposal.

## Problem

The 5.0 acceptance rebuilds of two Cell pages come out 30–50 % taller than the
references. On the dimorphism page (347 → 280 mm so far, reference ≈ 213 mm),
every millimetre recovered was an authoring decision the engine could have
made:

- **Key placement.** Keys under or above plots took their own bands. The
  reference puts them in free data space (H), beside the plot (O), or under a
  neighbour's inset (M). `legend(corner='auto'|'best')` exists but the author
  must choose it, and must know which choice keeps the page short.
- **Plot data heights.** Authored at 34 mm on rows whose whole reference
  height is 37 mm. Nothing told the author which rows set the page height.
- **Column widths.** Track weights are author guesses. Fixed artwork's
  natural width is not reserved (the scripts call `lettered_width()` and pass
  `min_width=`), and a panel with side keys (O) was starved while its
  neighbour (P) had spare width.
- **Fixed artwork.** Anatomy renders and diagrams keep their authored size,
  leaving 20–50 mm holes beside tall plots, or forcing rows taller.

The 2026-08 page-grid study declined imposing a rhythm, because only the
author knows what may change size. This proposal keeps that principle: the
author declares *what may flex and within what bounds*; the engine chooses.

## Principles

1. **Text never shrinks.** Type sizes and stroke widths are fixed. Flex acts
   on data regions, artwork scale, key placement and track sizes.
2. **Declared, bounded, deterministic.** Every choice the solver makes comes
   from a range or an option list the author wrote (or a documented default).
   The same inputs give the same page.
3. **Explainable.** The compiled figure reports which cell set each row and
   column, which choices were made, and the unused area per cell.
4. **Opt-in per page.** `document(fit=None)` keeps today's behaviour exactly.

## Vocabulary

| Item | Declaration | Solver chooses |
|---|---|---|
| Plot | `plot_spec(height=(18, 30))` or `aspect=(0.6, 1.2)` (data region) | data height within the range; rows keep one data height per `share_plot_margins` |
| Key | `legend(place='auto')` (the default under `fit`) | among inside-free-space corners, right, bottom, top, with column counts that fit |
| Artwork | `component(f, responsive=True, min_width=, min_height=)`; fixed art: `component(f, scale=(0.7, 1))` | size within bounds; fixed art is rebuilt, never bitmap-scaled |
| Columns | `document(columns='auto')` or weights plus `min_width` | widths: measured natural widths of fixed art (with letters) as floors, flex by weights |
| Page | `document(fit='compact')` or `fit=('height', 220)` | minimise height, or meet a target height; then fill holes |

## Algorithm

Discrete choices (key placements, column counts) and continuous sizes (tracks,
data heights, art scale) are solved in two nested loops. Both reuse the
existing measure-to-fixed-point pass and the build cache, so re-evaluating a
choice rebuilds only the cells that changed.

1. **Start compact.** Each plot at its range minimum, each art item at its
   smallest scale, each key at its first feasible candidate. Lay out once.
2. **Critical path.** For each row track, record the cell that sets it; the
   rows' sum is the page height. For spans, the cell whose span requirement
   is binding.
3. **Local search on the critical cells.** For each binding cell, try its
   alternatives (next key placement, key columns, moving width from a
   non-binding neighbour column). Accept a change if page height drops by more
   than 0.1 mm; stop when a full pass improves nothing, or after a fixed
   number of passes. Candidates are ordered so the search is deterministic.
4. **Fill.** With the page height fixed, grow flexible content into the unused
   area of each track: plots towards their maximum (shared rows grow
   together), artwork towards scale 1. This removes holes rather than adding
   height.
5. **Target height.** `fit=('height', h)`: after step 3, if the compact page
   is shorter than `h`, step 4 distributes the surplus (as the 5.0 fixed-
   height rules already do); if longer, raise a `LayoutError` naming the
   binding cells and their minimum contributions.

## Report

`compiled.layout_report()` lists, per row: height, binding cell, unused area
per cell; per column: width and binding cell; and each choice made
(`h.key → inside nw`, `o.keys → right`, `b.scale → 0.82`).

## Out of scope

- Reordering or re-spanning panels (the author's grid is kept).
- Shrinking text or strokes.
- Global optimality: a deterministic local search over declared options is
  enough when the author's grid is sensible.

## Plan

1. Measured natural widths of fixed artwork as column floors (removes the
   `lettered_width()` workaround). Small, standalone.
2. The layout report (critical path and holes). Useful on its own and needed
   by step 4.
3. Ranged plot heights and `fit='compact'`/fill for plots only.
4. `legend(place='auto')` candidates evaluated by the layout.
5. Artwork scale ranges.
6. Re-run both acceptance pages with `fit='compact'` and compare heights to
   the references.
