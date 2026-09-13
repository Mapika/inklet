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
python -m pytest -m acceptance --junitxml=out/acceptance.xml
```

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

## Reviewing a candidate

Retain JUnit results, rendered exports and revision reports. Inspect failures for
changed geometry, asset bytes, stale identities, missing selections, incompatible
saved edits and off-page artwork. Compare clean and cached results and retain
old immutable snapshots throughout revisions. Do not update visual baselines or
weaken assertions simply to make a candidate green.

[Figure projects](project-workflows.md) documents the reproducible bundle API.
[Release checks](release-checks.md) covers the broader installation, visual and
performance gates. [The roadmap](roadmap.md) records remaining RC decisions.
