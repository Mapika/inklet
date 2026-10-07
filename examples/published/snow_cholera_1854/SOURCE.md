# Source: John Snow's cholera map, Broad Street, 1854

**Original.** John Snow, *On the Mode of Communication of Cholera*, 2nd ed.
(London: John Churchill, 1855), with the folding map of cholera deaths around
the Broad Street pump, headed "MAP 1" in the reproduction consulted. The map
records the deaths of the 1854 outbreak by address, drawn as stacks of black
marks, with the pumps marked "PUMP". No DOI exists for the 1855 book.
Reproduction consulted (for comparison only, not redistributed):
<https://commons.wikimedia.org/wiki/File:Snow-cholera-map-1.jpg>
(public domain; Wikimedia Commons).

**Data (used).** The R package **HistData** (Michael Friendly et al.), version
1.1.1, datasets `Snow.deaths`, `Snow.pumps` and `Snow.streets`:
<https://github.com/friendly/HistData> (files `data/Snow.deaths.RData`,
`data/Snow.pumps.RData`, `data/Snow.streets.RData`), documented at
<https://friendly.github.io/HistData/reference/Snow.html>. Provenance as stated
in the package documentation: the data were first digitized in 1992 by Rusty
Dodson of the NCGIA, Santa Barbara, from the map in the 1936 Oxford University
Press reprint of Snow's book; see Tobler, W. (1994), "Snow's Cholera Map",
<http://www.ncgia.ucsb.edu/pubs/snow/snow.html>.

- `Snow.deaths`: 578 deaths, one row per death, `case`, `x`, `y`. The package
  documents that deaths at one address are "stacked in a line away from the
  street ... This is how they are displayed on John Snow's original map", so
  the stacks are in the coordinates.
- `Snow.pumps`: 13 pumps with labels.
- `Snow.streets`: 528 street segments (1241 vertices); `n` is the vertex count
  of each segment.
- Coordinates are in units of 100 m with an arbitrary origin (package
  documentation). Scale of the source map approx. 1:2000.

**Licence.** HistData's `DESCRIPTION` states `License: GPL` (version not
specified). The Dodson digitization's own terms are not stated in the package.
Snow's map and text are public domain (author died 1858).

**Cross-check (not used for plotting).** Robin Wilson's digitization, SnowGIS
(<https://johnsnow.rtwilson.com/download.html>, CSV zip
<https://johnsnow.rtwilson.com/data/SnowGIS_CSV.zip>, retrieved 2026-10-07).
Its README says the data were compiled by Robin Wilson (2011, updated 2026),
with the street layer omitted from the CSV download and the Ordnance Survey
raster layers under "contains Ordnance Survey data (c) Crown copyright and
database right 2013". This figure uses no OS layer. Its `Cholera_Deaths.csv`
has 250 locations summing to 489 deaths, and `Pumps.csv` has 8 pumps. These
disagree with HistData (578 deaths, 13 pumps), so the two digitizations are not
interchangeable. The figure follows HistData because it has the street lines
and the 13 pumps on the original map.

**Retrieved.** 2026-10-07.

SHA-256 of the files as downloaded from HistData (the `.RData` files, retrieved
the same day):

```
183af9d159d14eb125744e054eff7c8066fa11c309fba20bc0e65c33c1fb6358  Snow.deaths.RData
ce07da18f282b90e4f19755a2000e171ba6f4a398179915f894db9f6ada08415  Snow.pumps.RData
cd42dbd30956f7a7af58aa1e351037f7b883bbff34d0f4e34a1c19857ea18328  Snow.streets.RData
```

## Files in `data/`

Converted from the `.RData` objects to CSV with `pyreadr` (Python, read-only
conversion). Values are kept as stored; floats are written to six decimals.
The only check was that each street's rows are contiguous and that `n` equals
the number of rows for that street.

| File | Source object | Columns |
|---|---|---|
| `snow_deaths.csv` | `Snow.deaths` (578 rows) | `case`, `x`, `y` |
| `snow_pumps.csv` | `Snow.pumps` (13 rows) | `pump`, `label`, `x`, `y` |
| `snow_streets.csv` | `Snow.streets` (1241 rows, 528 segments) | `street`, `n`, `x`, `y` |

SHA-256 of the CSV files:

```
1358afec09fe76ad600cc7bc9e086d7e125c0f6497f850724a0fe9983db4630d  snow_deaths.csv
59e465cdbbb387014c6da97a6a9be630ae4e13a75116970be347db0d609f4df9  snow_pumps.csv
0e1eee4de90a96ddba583175ec9c1fa9659e0d70ec4bc54213e76621dd977d3f  snow_streets.csv
```

## Processing done in `figure.py`

* One data unit is 8 mm on both axes. The map is the square 3 to 20 on x and
  y, so the plot is 136 mm by 136 mm, on a 144 mm square page.
* Streets: each `street` is one line through its vertices, 0.15 mm wide.
* Deaths: one square per row, 0.9 mm. Nothing is moved or counted.
* Pumps: 2.6 mm rings in red. Pump 7, "Broad St", is labelled "Broad St pump"
  with a short leader. The label is placed in the one clear patch near the pump
  that does not cover a death mark (found by searching the mm layout).
* No axes, as on the original. The frame is the map's outline.
