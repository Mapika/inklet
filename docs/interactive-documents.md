# Interactive documents

The **4.0 development preview** adds offline HTML exploration and reproducible
visual editing. Install the [preview version](development-preview.md) explicitly;
`pip install inklet` still selects the stable release.

![A regional report linking a map, time series, distribution and category panels](assets/v4/regional-report.png)

## Choose a workflow

| You want to… | Start here | What stays reproducible |
| --- | --- | --- |
| Inspect, pan and zoom a native figure | [Compiled-scene viewer](compiled-viewer.md) | Native vector export and the compiled snapshot |
| Select and filter observations across plots | [Linked plots](linked-plots.md) | Stable row IDs and a saved selection/view state |
| Build category panels or time series | [Facets](linked-facets.md), [dates and time series](time-series.md) | Category order, missing-value gaps and shared selection |
| Map points and routes alongside regions | [Mixed GeoJSON features](geographic-features.md) | Whole-feature identity, fixed bins and explicit source attribution |
| Join a regional map to values | [Linked maps](linked-maps.md) | Explicit geometry keys, bins and source attribution |
| Display distributions or supplied intervals | [Linked statistics](statistical-views.md) | Stated methods, reference populations and interval meaning |
| Edit plot appearance in the browser | [Visual editing](visual-editing.md) | Versioned overrides, undo/redo and Python reconstruction |
| Replace source data | [Data revisions](data-revisions.md) | Explicit missing-ID policy and a revision report |

## Run a complete report

Start with the [regional report](regional-report.md): a real map with simulated
measurements, linked histories, an ECDF and faceted comparisons. It exercises
selection, filtering, save/reopen, source replacement and exports at two widths.

```bash
python examples/v4/regional_report.py --renderer compiled --editor --output out/regional
```

Open the generated `index.html`. Save the view for selection/filter/zoom and
save overrides for edited styles. Keep both files with the matching source
recipe and data revision. The [visual editing guide](visual-editing.md) shows
how to rebuild the same appearance in Python.

For other data, follow the [engineering report](engineering-report.md),
[calibrated image measurements](scientific-report.md), [mesh fields](mesh-fields.md)
or [contours and streamlines](contours-streamlines.md). Optional
[pandas and Polars adapters](table-inputs.md) preserve explicit row identities.

## Know the boundary

Standalone pages embed their supported operations and assets. They need no
Python server or CDN to use those controls. Arbitrary Python callbacks do not
run inside the exported HTML. Source replacement in the browser switches among
precompiled alternatives; CSV processing and fresh compilation happen in Python.

A native compiled viewer does not automatically infer row relationships for
arbitrary scene objects. Linked figures declare those correspondences explicitly.
The first style editor covers named colours, marker radii and line widths;
label/panel/camera editing remains open. Read the feature guide's limits before
relying on an experimental API or saved-state schema.
