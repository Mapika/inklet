# Label placement and direct labelling

A dense figure has many labels: named points in a scatter, the top hits of a
volcano plot, one name per curve, and callouts on a schematic. inklet places
them with one deterministic search, so you should not need to move labels by
hand. This page covers what the search avoids, the calls that use it, and what
happens when there is not enough room.

## What a label avoids

Every placer scores each candidate position against everything the panel has
drawn, including marks drawn after the call:

- **Other labels.** Labels never overlap, and each one keeps the theme's `xs`
  gap from the others. This is the same clearance that the lint rule
  `CROWDING` measures.
- **Labelled points.** A label never covers a point that someone else's label
  names.
- **Marks.** Markers, bars, error bars, rules and text are covered as little
  as possible. A stroked line through a label counts as a collision.
  Confidence bands and shaded areas are measured by their outline, not by
  their bounding box.
- **Leaders.** A leader never crosses another leader or passes through
  another label. It avoids other labelled points, and it runs through as few
  marks as it can.

The search is joint. It makes a greedy first pass, lets each label move to its
best position given all the others, and then runs an annealing pass with a
seed hashed from the labels' own text and coordinates. A final pass moves
colliding pairs together. The search reads no clock and does not depend on
`hash()`, so the same figure gives the same SVG bytes in every process.

## Named points

```python
p.scatter(cloud, color=TH.muted)
p.scatter(hits, color=TH.color(0))
p.label_points(hits, names)
```

Each label tries eight compass positions next to its point first. If those are
taken, it moves out along sixteen rays, as far as two and a half times `reach`,
and a hairline leader connects it back to its point. Positions past `reach`
cost more for every extra millimetre, so a long leader is used only when no
closer position is free. `volcano(labels=...)` and the embedding scatters use
the same search.

## Curve names instead of a legend

```python
for g in groups:
    p.line(curves[g], name=g)
p.label_lines()                   # names in a column past the curve ends
p.label_lines(where="inside")     # names beside the last stretch of each curve
```

`label_lines()` names each `line`, `step` or `ecdf` that was drawn with
`name=`. Pass `names=[...]` to label only some of them. Each name is set in
its series' colour, darkened only as much as it needs to be readable on the
paper, so a yellow curve gets an ochre name that passes `LOW_CONTRAST`.
Pass `color=False` to set the names in ink.

- `where="end"` puts the names in a column just right of the curve ends, each
  at the height where its curve ends. When names would collide, they are
  pushed apart by the smallest total movement that keeps them in order. A
  name that moves off its curve's end gets a thin leader in the curve's
  colour.
- `where="inside"` puts each name just above or below its own curve, and
  prefers positions near the end of the curve. The names are chosen together,
  so that no name sits on another name, is crossed by a curve, or is closer to
  another curve than to its own.

## Keys in the emptiest spot

```python
p.legend(corner="best")
```

`corner="best"` scores positions across the whole plot area against every
drawn mark and picks the emptiest one. Among equally empty positions, the one
nearest a corner wins. If every position would cover data, the key goes
outside, beside the plot on the right, as it would with `side="right"`. The
older options still work as before: `corner="ne"` and the other fixed
corners, and `corner="auto"`, which uses the first clear position and raises
an error if there is none.

## Callouts on diagrams

```python
art = rig
for part, text in LABELS:
    art = inklet.annotate(rig.find(part), text, within=art)
art = inklet.place_labels(art, method="joint")
```

The default `method="greedy"` is unchanged and still places one label at a
time. `method="joint"` tries more distances (`JOINT_RADII`) and decides every
callout together with the same search as above. Use it when callouts end up
on neighbouring parts, or when their leaders tangle.

## When a label does not fit

The placers never drop or shrink a label. If no clean position exists, the
label is still drawn at the least bad position and named in its call's note:

| Call | Note | Key |
| --- | --- | --- |
| `label_points` | `point_labels` | `unresolved` |
| `label_lines` | `line_labels` | `unresolved` |
| `place_labels` | `place_labels` | `unresolved` |

`inklet.lint` reports each non-empty list as a `LABEL_UNPLACED` warning, with
the labels named. To fix it, give the labels more room: make the panel larger,
use smaller type or fewer labels, or shorten the labels. `point_labels` also
lists labels that sit on a background mark under `covering_marks`. These are
not errors, but they are useful to know about when you are checking a dense
cloud.

## Measuring it

`tools/benchmark_labels.py` builds a fixed set of crowded cases: clustered
scatters with 60 and 200 labels, a volcano plot, ten curves, labels over bars
and areas, and two sets of callouts. For each case it reports label overlaps,
labels on marks, leader crossings, unresolved labels, how far each label sits
from its point, lint findings and runtime:

```
.venv/bin/python tools/benchmark_labels.py --png out/labels
```
