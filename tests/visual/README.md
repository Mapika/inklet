# Complete-figure visual checks

Run `.venv/bin/python tools/visual_check.py`. It renders thirteen complete fixtures
through Chrome/Chromium (SVG) and Poppler (PDF), compares each against its
reviewed PNG, and writes `tmp/visual-check/index.html` with baseline/current/diff
images. It exits nonzero when a page changes size or more than 0.1% of pixels
change by at least 25 intensity levels. Antialiasing noise below that level is
ignored. Geometry tests remain responsible for exact coordinates.

Requires Pillow, Chrome/Chromium, Poppler and DejaVu Sans. The font checksums in
`baseline/fonts.json` prevent accidental font substitution from becoming a
misleading rendering regression. `baseline/renderers.json` also checks the
browser and Poppler versions before rendering; engine changes can alter
antialiasing even when the SVG is identical. CI extracts Chrome Stable
145.0.7632.45 from a fixed, SHA-256-verified package and uses Poppler 24.02.0
from Ubuntu 24.04. These pins apply to the baseline checks, not to Inklet users.

For local Linux checks, download the same browser using the commands in
`.github/workflows/checks.yml` (the “Install the reviewed visual browser” step),
using a local scratch directory in place of `$RUNNER_TEMP`. Prepend its `bin`
directory to `PATH` when running the checker. This leaves the system browser
unchanged. Chrome/Chromium with the same version is also accepted. When
intentionally upgrading a renderer, review every difference and update its
recorded version together with the baselines and CI pin.

Use `--update` only after inspecting intended changes. This explicitly replaces
the baselines; normal runs never update them. The fixtures cover embedded
fonts, bold/italic and scientific text, rounded corners, transparency, negative
spacing, dense raster data under vector annotations, all seven markers in
both modes, clipping, an external inset declared before its axes, scientific
diagram components and category subsets with group labels. The six v2 figures
add live revisions, shared scales, twin axes, spanning cells and compiled paint.

Use `--suite v1` or `--suite v2` to select a subset; the default runs all suites.
Performance checks run with `.venv/bin/python tools/benchmark_v2.py`. They record
compilation and export times, cached compilation, node counts and file sizes,
and enforce the budgets in `v2-budgets.json`.
