# End-to-end acceptance

The acceptance suite verifies complete user workflows. Feature contracts and
historical regressions remain in the normal suite; passing one happy-path
example does not replace them. All tests still run by default.

| Workflow | Entry point | What a pass establishes |
| --- | --- | --- |
| Regional analysis | `tests/test_regional_report.py` | Import/derive CSV, hidden selections, save/reopen, removed rows, resize and browser/static agreement |
| Engineering study | `tests/test_engineering_report.py` | Geometry and units, linked drawings, preserved label decisions, revisions, CLI reopen and vector exports |
| Calibrated measurement | `tests/test_scientific_report.py` | Source-pixel membership, missing intensities, calibration changes, source replacement and browser/static agreement |
| Reusable mixed project | `tests/test_project_acceptance.py` | Verified asset bundle, cross-content selection, editor undo/redo, native-camera choices, reopen, revised inputs, removed targets and two widths |

Run the shared acceptance entry point:

```sh
python tools/acceptance.py --output out/acceptance.xml
```

The release runner collects the four reference modules explicitly, requires a
result from each, and rejects failures, errors and skips. Ordinary development
can still use `python -m pytest -m acceptance`; that command permits optional
skips and is not by itself the release gate.

The browser cases require Chrome/Chromium; independent previews use the render
extra and Poppler. An unavailable optional dependency produces an explicit skip,
which is **not evidence that the corresponding acceptance gate passed**. The
release environment installs the declared dependencies.

## Test ownership

- `test_project_contracts.py` owns asset integrity and identity mapping failures.
- `test_project_acceptance.py` owns the new project lifecycle.
- The three report modules retain their domain-specific numerical and failure
  cases, with complete workflows marked `acceptance`.
- `tests/browser_support.py` owns browser execution and pixel-comparison helpers.
  Tests no longer import those helpers from another test module.
- Regression files use behavior names, such as `test_nested_documents.py` and
  `test_render_contracts.py`, rather than release or showcase-round numbers.

See the [test maintenance policy](../tests/README.md). A similar test title is
not proof of duplication: the chemical and structural figure determinism tests,
for example, exercise different fixtures and both remain valuable.

## Project lifecycle performance

```sh
python tools/benchmark_project.py --output out/project-benchmark.json
```

CI enforces [declared budgets](../tests/performance/project-budgets.json) for
build, edit, undo/redo, selection, save, reopen, source revision, resize and
SVG/PDF export. It runs the two-entity mixed project at 140 and 190 mm, taking
three measurements per width with fresh projects and temporary directories.
The report retains every measurement and limit; missing stage limits fail.

These are elapsed-time regression ceilings for the Linux/Python 3.12 release
environment, not browser frame-rate or large-data guarantees. Font and filesystem
caches may be warm. Input fixture creation and correctness assertions are outside
the timed stages; revision includes recipe reconstruction. Each stage and the
sum of timed stages must pass. Review measurements before changing a limit;
never raise one automatically after a failure.

Browser interaction and larger report performance remain separate RC evidence;
the small project benchmark does not establish their limits.

## Reviewing a candidate

Retain JUnit results, rendered exports and revision reports. Inspect failures for
changed geometry, asset bytes, stale identities, missing selections, incompatible
saved edits and off-page artwork. Compare clean and cached results and retain
old immutable snapshots throughout revisions. Do not update visual baselines or
weaken assertions simply to make a candidate green.

[Figure projects](project-workflows.md) documents the reproducible bundle API.
[Release checks](release-checks.md) covers the broader installation, visual and
performance gates. [The roadmap](roadmap.md) records remaining RC decisions.
