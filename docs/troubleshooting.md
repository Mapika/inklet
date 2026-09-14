# Troubleshooting

Start with the exact exception or diagnostic code. For environment problems,
run `inklet doctor`. For drawing problems, call `compiled.report()` and inspect
the SVG or [review page](export-review.md).

## Installation and export

| Symptom | Check and resolution |
|---|---|
| `No module named inklet` or command not found | Activate the installation environment; use `python -m inklet` to select that interpreter |
| No font found or missing glyphs | Install an appropriate font, verify Fontconfig, or choose an explicit font family/file |
| PNG preview renderer unavailable | Install `inklet[render]`; the explicit `--png-backend chromium` path requires Chrome/Chromium |
| Blender scene renderer unavailable | Choose a [tested Blender version](compatibility.md), set `INKLET_BLENDER` to its executable and run `inklet doctor`; legacy Grease Pencil recipes have separate version constraints |
| PDF preview renderer unavailable | Install Poppler's `pdftoppm`, or pass `--no-pdf-preview` / `compare_pdf=False` |
| Only vectors are needed | Use `save('figure.svg', 'figure.pdf')` or CLI `--vectors-only` |
| Preview exceeds pixel limit | Lower preview DPI or page dimensions; SVG/PDF retain their vector resolution |
| Unsupported mesh format | Use a native OBJ/STL/PLY mesh or install the optional `three` extra |

Preview generation limits the page to 40 million pixels. Raster scatter limits
its layer to 16 million pixels. A larger page at a fixed DPI can reach these
limits even when the vector drawing is small.

## Layout failures

`LayoutError` usually reports a required size and an available size. Increase
the appropriate cell/page dimension, reduce the number of columns, wrap labels,
or move legends/insets. A fixed `Diagram` does not resize merely because its
cell is narrower. Use a `PlotSpec` or a responsive component when it should
adapt to available dimensions.

Plot margin sharing is opt-in: set `share_plot_margins=True` on the document or
subfigure that owns the grid. Independently nested grids need their own
alignment settings. Explicit compositions should use
measured anchors and dimensions instead of guessed text widths.

## Unexpected data or edits

| Symptom | Likely cause |
|---|---|
| Mutating a list does not change the plot | Literals were snapshotted; use a dataset reference or replace the instruction |
| Export still shows the old data | A compiled figure is a snapshot; call `doc.compile()` again after editing its inputs |
| Assigning to compiled placements raises `TypeError` | The placement mapping is read-only; edit named document cells or composition constraints and recompile |
| Labels or curves appear twice | Drawing methods append; assign a `key` and use `replace()` |
| A category moves or changes colour after filtering | Share a `CategoryEncoding` between the data marks and scale |
| Horizontal category order is reversed | First y category is at the bottom; reverse the list or use an encoding's `scale(reverse=True)` |
| Shared scale rejects columns | Units differ, values are non-finite, or log values are nonpositive |
| Data extend outside the axes | Set `clip=True` if clipping is intended, or widen the domain |
| Annotation stays at its old value | Its coordinate was literal; update it with the data or derive it explicitly |
| Factory cache ignores a change | The input is hidden in a closure/global; pass a tracked dependency explicitly |
| Watch misses a data edit | Add the file or directory with `--watch` |

Dataset updates must retain equal-length columns. Changes across multiple
datasets are separate operations; complete the related edits before compiling.

## Common diagnostics

| Code | Meaning and response |
|---|---|
| `OFF_CANVAS` | Visible artwork extends beyond the page; revise placement or page size |
| `OVERLAP` / `CROWDING` | Items collide or fall below the requested clearance; inspect their highlighted bounds |
| `LOW_CONTRAST` | Text/background contrast falls below the threshold; change the text or fill colour |
| `TINY_TEXT` | Final transformed text is below the minimum; increase physical type size or avoid scaling it down |
| `LOW_DPI` | A raster lacks pixels at its final size; use a higher-resolution source or a smaller placement |
| `KEY_MISMATCH` | A legend or colourbar disagrees with the plotted marks or scale; derive it from the same panel and mapping |
| `LINK_CROSSES` | A route passes through another object; adjust positions, waypoints or routing |
| `LINK_CROSSES_LINK` | Routes cross; inspect whether the crossing is legible and intentional |
| `RULE_FAILED` | A diagnostic rule failed internally; retain a minimal reproducer and report the error |

The [generated diagnostic reference](api.md#diagnostic-codes) is the complete
list. Diagnostic severity is separate from Python warnings and exceptions.
Keep intentional findings visible in review; a blanket suppression can hide
unrelated layout problems.

## Reproducibility and performance

Compare source data, font hashes and environment versions when output changes
between machines. Embedded text includes the selected font in the export;
it does not make two different font substitutions measure identically.
SVG and PDF rasterizations can differ in antialiasing and image interpolation.

Inspect `compiled.stats` for layout, paint and diagnostic time, recipe builds
and cache hits. These describe the compilation that produced the snapshot;
calling `compile()` again without edits can return that same snapshot and its
existing statistics. Time the call separately when measuring cache reuse.

For large plots, start with the [dense-data guide](dense-data.md): packed vector
markers, matrix batching, raster layers and optional line simplification address
different costs. Measure construction, compilation and export separately. The
[stress report](stress20.md) records a fixed workload; its timings are not a
prediction for every figure or machine.

When reporting a bug, include the smallest author script, environment versions,
`doctor` output, diagnostics and expected versus actual behavior. Use simulated
data if the original data cannot be shared. See [contributing](../CONTRIBUTING.md).
