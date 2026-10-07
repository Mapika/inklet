# Notes: John Snow's cholera map, Broad Street, 1854

Output: `gallery/published/snow_cholera_1854.{png,svg,pdf}`, a 144 mm square
page (the map is 136 mm square). `figure.py` is 70 lines. `figure.report()`:
`inklet lint: clean, 0 diagnostics`.

## Matches the original

* **Deaths: 578 marks, stacked as in the original.** HistData gives one
  coordinate per death, and its documentation says the points at one address
  are "stacked in a line away from the street ... as they are displayed on
  John Snow's original map". The dark clusters along Broad Street and the
  lines of marks running away from the streets are the same stacks. Each death
  is one small square, so a stack of n deaths shows n squares.
* **Streets: 528 segments** from `Snow.streets`, drawn as the same polylines.
* **Pumps: all 13**, in the original's positions, with the Broad Street pump
  at the centre of the death cluster.
* **Orientation and extent**: the map is in Snow's own coordinates (3 to 20 in
  both directions, 100 m units), and the street grid runs at the same angle as
  the original's (the long street across the top and the diagonal street
  through the cluster both match). The map is not rotated for display.
* **Equal scale**: one data unit is 8 mm on x and on y. The frame measures
  136.3 mm by 136.3 mm in the PNG at 200 dpi.
* **Frame**: the map is enclosed in a rule, like the original's border.

## Differs, and why

* **Streets are lines only.** The original draws the streets as blocks with the
  building outlines, the squares (Golden Square, Soho Square) and the courts.
  HistData's `Snow.streets` holds the 528 street-centre segments, so none of
  the block shapes or building outlines are drawn.
* **Deaths are squares, not bars.** The original's marks are short black bars.
  The squares sit at the same coordinates, but a 0.9 mm square is not a bar.
* **One pump labelled.** The original labels every pump "PUMP". Here only the
  Broad Street pump is labelled, "Broad St pump" (the dataset's label; the
  original says "Broad Street"). A longer label, "Broad Street pump", did not
  fit in the clear space near the pump, so it is shorter and has a leader.
* **Leader and label placement.** The label is in the one clear patch near the
  pump, found by searching the layout in millimetres. A label placed directly
  against the pump covers a death mark in every position tried.
* **A key** is added in the top-left corner (Cholera death, Water pump, Street).
  The original has no key. The key does not cover data (lint is clean).
* **No title, no scale bar, no "MAP 1." heading, no axes or grid.** The
  original has a scale bar ("30 inches to a mile") and the "MAP 1." heading.
  HistData gives 100 m units, so a scale bar could be drawn; it is left out to
  keep the figure to the data.
* **Colours.** Streets are a mid grey (#6b7079) rather than black, so the marks
  stand out. Deaths are the near-black ink; pumps are hollow red rings.
* **Data source.** HistData's digitization (1992, Dodson) is used. Robin Wilson's
  SnowGIS has 489 deaths at 250 locations and 8 pumps (against 578 and 13 here),
  so it was not substituted (SOURCE.md). The difference is not reconciled.

## Verdict

Faithful in the things that carry the argument: the deaths in their stacks, the
pumps, the Broad Street pump at the centre of the cluster, and the streets in
their positions, at equal scale. The main departures are the street blocks,
which are not in the data, and the labelling of the pumps.
