# Roadmap to Inklet 4.0

Status: proposed development plan, September 2026. Inklet 3.1 is the released
baseline. The capabilities below are targets, not available APIs or dated
release promises. Implementation decisions become commitments after the
prototype and acceptance checks described here.

[4.0.0.dev1](development-preview.md) is the first installable development
snapshot. It collects the implemented experimental workflows described below;
3.1.0 remains the stable release. Publishing a preview does not close the
remaining roadmap or stabilization gates.

Phase A has started: [the foundations report](v4-foundations.md) records the
first fixtures, engine corrections, baseline timings and offline selection
prototype. A bounded scatter backend comparison, linked maps, explicit data
revisions, category panels and optional table adapters are implemented; broader
backend/performance coverage remains an upcoming gate.

## Product direction

Inklet 4.0 should let people build connected visual documents from Python:
ordinary charts, maps, diagrams, images and 3D scenes that support exploration,
visual editing and reproducible static export. Scientific publishing remains
an important use, alongside analysis, engineering, education and product work.

A project should retain its data relationships, author choices and physical
layout when its inputs change. A user should be able to explore a result in
HTML, save the selected state, and export that state to SVG, PDF or PNG.

Animation, timelines, video/GIF generation and presentation authoring belong
to the **5.0 direction**. Interactive controls and camera manipulation belong
to 4.0; sequencing them over time does not. Existing presentation styling
presets remain supported.

## Next implementation priorities

The next increments should strengthen the general framework, rather than expand
one domain. Geography, microscopy and engineering are adapters and acceptance
examples; none should determine the shared document architecture.

1. **Reusable compositions:** explicit inputs, named content slots and attachment
   points for plots, diagrams, images and 3D, with source/asset manifests.
2. **Shared object identity:** stable named objects and explicit relationships
   beyond table rows, so selections and authored decisions survive replacement.
3. **Reproducible authoring:** extend saved overrides to labels and panel layout,
   then camera settings, with clear limits, undo/redo and revision reconciliation.
4. **Cross-content acceptance:** exercise the same composition and editing
   contracts in a plot, a diagram and an image/3D view; verify resizing, reopening
   and static/browser export agreement.

The bounded point/route adapter is implemented; defer further geographic
expansion. [Reusable plot recipes](plot-recipes.md) now begin the shared-engine
work with copied/composed instructions, independent styling and improved
automatic layout. General composition templates and browser layout editing
remain open. The next development release should advance shared
composition or editing capabilities and use domain examples to test those
capabilities, rather than make another map report its central deliverable.

## Who this should serve

| User | Complete 4.0 workflow | What establishes success |
| --- | --- | --- |
| Analyst or business team | Combine a regional map, time series and categorical comparisons in an interactive report | Filtering preserves category colours, units and row identity; the selected state exports consistently |
| Engineer or architect | Combine a model, dimensions, a system diagram and supplied simulation results | Measurements remain attached to geometry and charts; sections and static exports use explicit units |
| Researcher | Connect observations, an image region or 3D object, and statistical panels | Selections and derived values have explicit correspondence and provenance; publication exports retain readable vector labels |
| Educator | Build an explorable function, field or geometric construction with linked controls | A learner can use the documented controls without Python installed; the author can export a chosen state |
| Product or design team | Annotate an object and compare its measurements using a shared visual theme | Components and styles can be reused across reports without manual reconstruction |

These are visualization workflows. Importing a building or a simulation result
does not imply that Inklet becomes a CAD modeller, simulation solver or
statistical inference package.

## Feature scope

The minimum deliverables below define the proposed 4.0 scope. The expansion
column records further directions that must earn their place through examples
and implementation evidence; it is not an additional release checklist.

| Direction | Minimum 4.0 deliverable | Expansion candidates |
| --- | --- | --- |
| Everyday plotting | Consistent table-to-plot authoring; pandas and Polars adapters as optional integrations; facets and small multiples; robust date, category and missing-value behavior; measured legends and direct labels | Additional statistical summaries, financial chart recipes, richer distribution and uncertainty views |
| Geographic visualization | GeoJSON points, lines and regions; a documented projection subset; choropleths joined by stable keys; offline map figures and linked selections | Additional projections and formats, raster backgrounds and optional map services |
| Interactive documents | Standalone HTML with hover, zoom/pan, selection, linked panels and controls over supported data operations; save and restore state | Larger server-backed datasets, richer notebook integration and incremental external data updates |
| Technical illustration | Reusable named symbols and ports; stronger graph and connector layout; equations and dimensions; authored section and exploded views for a documented geometry subset | Domain-specific symbol libraries, assembly metadata and additional engineering interchange formats |
| Scientific visualization | Coordinated image/volume and plot views; scalar/vector-field views including contours and streamlines; imported meshes with attached values; explicit uncertainty and units | Molecular structure adapters, larger out-of-core volumes, specialized simulation formats |
| Visual editing and reuse | Local browser inspector for selection, labels, panel dimensions, styles and camera settings; undo/redo; saved overrides; reusable compositions and asset manifests | Richer direct manipulation, project templates and additional editor tools |

Existing dates, distribution plots, datasets, presets, native 3D and microscopy
tools are foundations to improve and connect. The [plot guide](plot-types.md),
[data guide](data.md), [3D guide](three-images.md) and
[research preview](research-preview.md) describe their current scope.

### Everyday quality is part of the release

Common plots need the same attention as complex scenes. Establish explicit,
consistent behavior for empty inputs, missing and nonfinite values, constant
domains, reversed scales, category ordering, date/time zones, uncertainty
intervals, clipping, legends and facets. Statistical summaries must identify
their method and input population; filtering must not silently change the
meaning of a displayed interval.

Provide complete examples for time series, survey comparisons, distributions,
regression results supplied by another package, and regional data. Every new
plotting guide should show an actual generated result beside runnable code.

### Interaction must have an explicit execution model

A standalone document can carry data, a supported set of declarative operations
and precomputed alternatives. It must work without a Python server or remote
assets for its advertised controls. Arbitrary Python callbacks require a local
Python session and must be identified as such before export.

Selections use stable data/object identities. A filtered-out selection, a
deleted object or an ambiguous join receives a defined result and a diagnostic
where needed. Hover cannot be the only way to access a value: keyboard
navigation, readable descriptions and a data-table alternative are part of
the interactive workflow.

### Editing must remain reproducible

Python continues to define the project. The editor records versioned structured
overrides keyed by stable identities; it does not rewrite arbitrary Python.
Reopening and rebuilding must preserve those edits. When a source edit removes
an edited object, the editor must report the orphaned override and offer a
reviewable resolution.

Imported geometry and asset bundles must carry units, source and attribution
where available. Reusable compositions should have explicit inputs and named
attachment points. General extension hooks can be stabilized after at least
two independent integrations exercise them.

## Engine work that supports the features

The detailed [4.0 engine plan](design/v4.md) connects implementation stages,
contracts and measurements. Its main work areas are:

| Engine work | User benefit | Required evidence |
| --- | --- | --- |
| Stable identity and explicit dependency revisions | Data edits and saved visual edits reach every related view | Cached output agrees with a clean build after supported edits; old snapshots remain unchanged |
| Shared coordinate and geometry contracts | Marks, labels, dimensions and hit testing agree across 2D, images, maps and 3D | Numerical checks through nested transforms, projection, clipping and export |
| Incremental measurement, layout and rendering | Editing a label or filtering a table avoids rebuilding unrelated content | Stage timings and invalidation traces on complete projects |
| Common resolved output and backend capability reports | Interactive and static views preserve the same authored meaning | Cross-backend geometry/paint checks and explicit fallback reports |
| Constraints and preserved author decisions | Resizing a document preserves alignments, label locks and minimum readable sizes | Feasible results satisfy constraints; failures explain the conflicting requirements |
| Bounded geometry, raster and GPU work | Dense data and complex scenes remain usable | Recorded latency, memory, output size and approximation error on fixed workloads |

GPU rendering should prefer a supported available device, with CPU fallback
when discovery finds none. Failed renders must follow an explicit fallback
policy and report the backend actually used. A GPU must not become a requirement
for ordinary plots or static vector export.

## Delivery phases

Phases express dependency order. They do not assign dates or assume that every
phase needs a separate public version.

| Phase | Deliverables | Exit condition |
| --- | --- | --- |
| A: foundations during 3.x | Broader regression corpus; stage-level benchmarks; identity, coordinate and backend design prototypes; ordinary plot corrections | Baselines are reproducible and prototype results identify the architecture choices |
| B: 4.0 development preview | Connected data/object model, table adapters, facets, first map layer and a minimal HTML interaction runtime | Analyst workflow works from import through saved selection and static export |
| C: mixed-content preview | Geometry/field adapters, technical diagram improvements, authored sections, connected measurements and layout constraints | Engineering and scientific workflows pass revision and export checks |
| D: authoring beta | Local editor, structured overrides, undo/redo, reusable compositions, accessibility and documentation | All three workflows survive editing, reopening, input replacement and page resizing |
| E: release candidate | Migration path, supported-format matrix, installation checks and complete visual/performance review | All release gates below pass on the declared environments |

Ordinary plotting, documentation and safe engine fixes can ship in 3.x when
they preserve its contracts. New 4.0 models should remain experimental until
their semantics settle. Each development increment should deliver an executable
user workflow as well as its engine change.

### First implementation increment

The [browser comparison and direct interaction prototype](browser-rendering.md)
now cover the fifth step for fixed-axis scatter. The measured
[backend decision](design/browser-backends.md) retains SVG by default with an
explicit hybrid option for dense points. [Mixed linked plots](linked-plots.md)
now extend that runtime to source-ordered lines and signed bars, including
static reconstruction and directly restored HTML. [Linked region maps](linked-maps.md)
now add a bounded GeoJSON polygon join, holes, fixed color bins and a first
regional analysis figure. [Data revisions](data-revisions.md) now preserve valid
selections through Python replacement and browser switching. [Category panels](linked-facets.md)
add explicit facets with shared physical scales and empty-category retention.
[pandas and Polars inputs](table-inputs.md) now add immutable scalar snapshots
with explicit keys and equivalent cross-library exports. [Linked time series](time-series.md)
add calendar/UTC axes, temporal table imports and explicit elapsed-time gaps.
[Linked statistical views](statistical-views.md) add fixed-reference ECDFs and
supplied intervals with explicit populations and methods. The
[complete regional report](regional-report.md) now combines a real map, entity
series, distributions and group comparisons, with saved-state reconstruction,
CSV replacement and exports at two physical widths. This completes the bounded
Phase B analyst reference workflow. Multi-table relationships, the engineering
and scientific workflows, recomputed grouped summaries and broader distribution
types remain outstanding; the other Phase B and release gates are still open.
The [mixed geographic feature workflow](geographic-features.md) extends the map
subset to GeoJSON points, lines and multi-geometries, with whole-feature picking,
explicit provenance and geometry revisions. Projection remains flat longitude/latitude;
reprojection and geometric measurements are not implemented.
An opt-in [compiled-renderer bridge](regional-report.md#shared-compiled-renderer)
now runs that report through shared packed-marker execution while retaining
linked selection, filtering, saved states and revision policies. A first
[plot-style inspector](visual-editing.md) adds versioned overrides and undo/redo,
including revision reconciliation. General native scene identity mappings,
label/panel/camera editing and the other release gates remain open.
The [linked engineering report](engineering-report.md) starts Phase C with
native drawing/table correspondence, explicit box sections and measurements,
geometry replacement, retained label offsets and two-width exports. This bounded
box workflow does not close the mesh, camera, editing or constraint gates.
The [calibrated image measurement report](scientific-report.md) now adds labeled
pixel correspondence, source measurements, missing intensities, calibration
revisions and reproducible scientific exports. The [linked mesh-field report](mesh-fields.md)
adds supplied scalar/vector face fields, exact triangle picking in XY plans,
calibrated arrows, geometry revisions and a fixed-camera native 3D reference.
The [contour and streamline report](contours-streamlines.md) adds nodal grid
interpolation, linear contours, normalized-vector RK4 tracing, masks, termination
reports and linked cell selections. Depth-aware 3D selection, volume interaction, external
microscopy adapters for this browser model and general editing constraints
remain open. [Shared plotting quality](plot-quality.md) also improves numeric
ticks across static plots and browser frames.


Start phase A with a small, reviewable sequence:

1. Add the three reference-project briefs and small licensed/simulated fixtures;
   record which steps work in 3.1 and which are missing.
2. Extend the adversarial corpus for everyday plots and record stage-level
   cold-build, edit, resize and export baselines. Set workload budgets.
3. Prototype persistent row/object IDs and a versioned selection state using
   two linked plots. Verify replacement, removal and save/reopen behavior.
4. Export that prototype as offline HTML with selection and filtering, then
   reproduce its saved state in a Python static export.
5. Compare browser backend options on that example plus text, clipping and a
   dense layer; write the architecture decision before expanding the runtime.

This increment should establish the dependency and interaction contracts while
continuing to ship useful plotting corrections in 3.x.

## Three reference projects

1. **Regional analysis report.** Use a redistributable or simulated table and
   region geometry. Link a map, time series, distribution and faceted category
   plot. Filter a group, select a region, save/reopen the state, replace the
   table, and export the same chosen state at two physical widths.
2. **Engineering study.** Use an original or redistributable assembly/building
   model with explicit units and supplied analysis data. Combine a section,
   dimensions, a system diagram and response plots. Select a component across
   views, revise geometry, preserve label decisions, and export a report.
3. **Scientific measurement figure.** Connect a calibrated image/volume,
   region measurements, uncertainty plots and a field or mesh view. Replace
   inputs, test missing correspondences, revise panel sizes, and verify both
   the HTML selection state and publication output.

Each project includes source, small input fixtures, attribution, expected
measurements, saved states, failure cases and a documented command to rebuild.
Add an educational control example and a branded product composition to check
reuse beyond those three acceptance projects.

## Release gates

- All reference projects complete their documented import, interaction, edit,
  reopen, revision and export paths. A showcase screenshot alone is insufficient.
- Cache-enabled and clean builds agree after supported mutations. Earlier
  snapshots remain unchanged. Repeated deterministic builds retain the current
  SVG contract under a fixed environment.
- Layout, clipping, text, paint and scene visibility pass numerical,
  adversarial and complete-figure visual checks. Independent PDF previews remain
  part of export validation. Approximate operations disclose their tolerance.
- Interactive HTML works offline for the supported operation set. Keyboard
  interaction and textual/data alternatives are tested. Unsupported Python
  callbacks and backend features are reported before an incomplete export.
- Performance reports cover cold builds, unchanged builds, data edits, label
  edits, resizing, interaction and export. Phase A sets numerical budgets on
  named hardware before implementation; later phases may not silently relax them.
- Linux, macOS and Windows installation paths, optional dependencies, supported
  browsers and CPU/GPU paths have a published test matrix. Core static use
  remains available without a browser, GPU or scientific-data extras.
- Every public feature has a runnable example, an illustrated guide, stated
  limitations and migration notes. Asset provenance and licenses are recorded.

The [existing release checks](release-checks.md) continue to apply. The 3.1
adversarial regressions become part of the permanent engine acceptance corpus.

## Decisions to resolve before stabilizing APIs

Prototype the browser rendering strategy, serialized specification, stable
identity rules, data adapter boundaries and layout solver changes. Select
technologies using the reference projects, backend fidelity and deployment
cost. Benchmark existing behavior before replacing an engine subsystem.

Browser support for expensive 3D interactions, the first projection/field
format subsets, and dependency packaging need explicit prototype decisions.
Advanced import formats or specialist algorithms can move to later 4.x releases
without weakening the core reference workflows. A cut to a minimum deliverable
requires an explicit roadmap revision.

## Direction after 4.0: 5.0

Build animation and presentation authoring on stable identities, saved states
and reusable documents: timelines, keyframes, transitions, camera paths,
progressive annotations, slide sequencing and video/GIF export. Timing,
interpolation and temporal reproducibility need their own design and acceptance
tests. The 4.0 engine should permit that extension without requiring its
implementation for the 4.0 release.
