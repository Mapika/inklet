# Browser backend decision: scatter preview

The later [mixed-plot increment](../linked-plots.md) adds line and rectangle
geometry to this runtime. The timings below describe the scatter implementation
at commit `bbd4d55`; they have not been rerun for mixed plots.

**Status:** bounded experimental decision for 4.0 phase A. Retain SVG as the
Python API default and expose hybrid rendering explicitly for dense scatter.
Continue to compile layout and text in Python. This does not choose the backend
for every future plot, map, image or 3D view.

The [runnable guide](../browser-rendering.md) provides the supported workflow.
Unlike the earlier [selection experiment](../v4-foundations.md), the browser
draws point geometry and arbitrary visible/selected subsets rather than choosing
from precompiled figure states.

## Shared geometry and text

Python measures the document, axis labels and tick labels using the existing
compiler. It exports an outlined SVG frame, measured plot rectangles and
physical point coordinates linked to explicit row IDs. Coordinates and clip
rectangles are quantized to six decimal places in millimetres. Missing
coordinate pairs are omitted independently in each view.

All three browser modes consume that same scene. Canvas draws circles through
Canvas 2D and rasterizes the supplied frame; it is not a second text-layout
engine. Hybrid retains the SVG frame and vector selection rings over canvas
points. Each live renderer namespaces its SVG IDs and references, avoiding
collisions with page controls or other renderer instances.

Pointer positions use the inverse of the SVG
[screen transformation matrix](https://developer.mozilla.org/en-US/docs/Web/API/SVGGraphicsElement/getScreenCTM).
Canvas buffers follow
[device pixel ratio](https://developer.mozilla.org/en-US/docs/Web/API/Window/devicePixelRatio),
using actual rounded buffer dimensions when mapping physical coordinates.
A fixed-size spatial hash indexes centers in page space; clipping and visibility
are checked when querying. Selected vector overlays look up rows directly.

## Measurements

[Raw timing records](../assets/v4/browser-study.json) ·
[Benchmark script](../../tools/browser_study.js) ·
[Raster comparison observations](../assets/v4/browser-quality.json)

Environment: Linux, HeadlessChrome 150, 1440 × 1100 viewport, device pixel ratio
1, approximately 1112 × 456.5 CSS pixels for the plot stage. Data is original,
deterministic simulated input. Each row contributes a circle to two panels,
except one missing signal coordinate. No external HTTP resources were loaded.

Seven warm repetitions measure synchronous redraw and one-row selection
submission. Each operation also waits for two animation-frame callbacks;
those elapsed times are recorded separately and are not isolated GPU timings.
Picking timings exclude DOM event handling and table refreshes.

| Rows | Backend | Redraw submission median, ms | Selection submission median, ms | Pick p95, ms |
| ---: | --- | ---: | ---: | ---: |
| 100 | SVG | 1.7 | 0.3 | 0.1 |
| 100 | Canvas | 2.7 | 0.9 | 0.1 |
| 100 | Hybrid | 1.9 | 0.3 | 0.1 |
| 3,000 | SVG | 22.0 | 0.3 | 0.1 |
| 3,000 | Canvas | 9.1 | 1.0 | 0.1 |
| 3,000 | Hybrid | 8.2 | 0.3 | 0.1 |
| 20,000 | SVG | 156.1 | 0.2 | 0.2 |
| 20,000 | Canvas | 49.0 | 1.0 | 0.1 |
| 20,000 | Hybrid | 47.9 | 0.3 | 0.1 |

Each of the nine cases compares 200 indexed picks with an independent exhaustive
nearest-center query: **zero mismatches in 1,800 queries**. A zoomed coordinate
round trip differed by approximately 1e-14 mm. Invalid viewport loading retained
the previous state. These results cover circular scatter marks and fixed axes.

The report counts SVG nodes and the two allocated canvas backing buffers. It
does not measure whole-process memory, GPU execution, browser startup, file
parsing, export cost or full UI latency. The 20,000-row hybrid redraw still
exceeds a 60 Hz frame budget. Results are local observations, not CI performance
ceilings or a promise for all devices. There is no automatic backend threshold.

To reproduce with the agent-browser CLI installed:

```sh
python examples/v4/browser_scatter.py --count 20000 --output out/v4-browser
agent-browser --session study set viewport 1440 1100
agent-browser --session study open file://$PWD/out/v4-browser/index.html
agent-browser --session study eval --stdin < tools/browser_study.js
```

The final command returns a JSON string containing the timing report. Browser
versions and host load affect results; keep the environment fields with it.

## Fidelity review

Screenshots of the same 100 visible rows with two selections were compared
within the measured plot area. Relative to SVG, pixels whose maximum RGB
channel difference exceeded 25 occupied about 0.74% of the canvas crop and
0.13% of the hybrid crop. Mean maximum-channel differences were about 0.49 and
0.11 on the 0–255 scale. These are observations with no acceptance threshold;
they do not justify a claim of identical backend output.

Canvas frame text is rasterized at a fixed intrinsic resolution and softens
when enlarged. Hybrid keeps that text in vector form, though point edge
antialiasing still differs. All modes export a fresh vector SVG using the
original measured frame and clipped circles. Independent rendering of browser
and Python SVG exports gave identical pixels at 150 dpi for the checked
fit-page and zoomed/panned saved views. This is rendered agreement for those
states, not byte-identical XML or a proof for all states.

Headless regression checks exercise device pixel ratios 1 and 2, missing and
outside-domain points, reversed domains, hidden selections, invalid states and
multiple instances. The repository's reviewed CI Chrome version is separate
from the locally measured browser. Browser interaction also checks real pointer
selection, keyboard pan/zoom and opening a downloaded state.

## Boundaries and next work

- Keep the existing static compiler authoritative for measured layout and vector
  export. The browser scene is a snapshot, not a replacement document model.
- Line and bar identity/picking now have explicit boundary rules and independent
  query checks in the [mixed-plot preview](../linked-plots.md). Region geometry
  and arbitrary linked figures still need their own semantics and tests.
- Introduce explicit scene/update validation and table adapters before accepting
  browser-side data replacement. Saved views currently require matching data
  and scene revisions.
- Measure UI latency, cold loading, large selections and other browsers before
  choosing automatic rendering thresholds or a general runtime architecture.
- Add map/facet workflows and the engineering/scientific reference recipes to
  test broader use. Do not infer mesh or image performance from circles.

This implementation uses Canvas 2D, not a WebGL renderer. GPU execution is not
selected or verified. A future GPU backend needs its own resource, fallback
and fidelity study, following the platform's
[WebGL guidance](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices).
Animation and presentation authoring remain outside the 4.0 scope.
