# Release checks

The [GitHub workflow](../.github/workflows/checks.yml) runs on master pushes,
pull requests and manual dispatch. It does not publish packages.

- Unit and integration tests use the pinned dependencies in
  [`requirements-ci.txt`](../requirements-ci.txt).
- API documentation must match the generated reference. Guide examples are
  executed by the tests, and MkDocs builds with strict navigation/link checks
  using [`requirements-docs.txt`](../requirements-docs.txt).
- Thirteen complete fixtures are compared against reviewed SVG/PDF baselines.
- Complete v2 and v2.5 figures enforce cold-build budgets and cached compilation.
- Wheels are built and installed in isolated environments on Python 3.11,
  3.12 and 3.13. The smoke test verifies both the public API and CLI with only
  core dependencies and rejects accidental imports from the source checkout.
- The twenty-panel stress test checks dense mixed content, live edits,
  provenance, cached compilation and physical resizing.

The figure job uses Ubuntu 24.04, Python 3.12, Chrome, Poppler, DejaVu and Noto
fonts. The visual checker verifies the DejaVu file hashes before comparisons;
font mismatches fail rather than refreshing references. Review artifacts and
test reports are retained for seven days, including on failed runs. The static
documentation site is included in the artifact; it is not deployed publicly.

The workflow uses the official [uv setup action](https://docs.astral.sh/uv/guides/integration/github/).
Action references are pinned to commits. Python test dependencies are locked;
system fonts and renderers come from the runner and Ubuntu packages, so this is
not a fully hermetic rendering environment.

Local equivalents:

```bash
uv venv
uv pip install -r requirements-ci.txt -e .
.venv/bin/python -m pytest -q
.venv/bin/python tools/gen_api.py --check
uv pip install -r requirements-docs.txt
.venv/bin/python -m mkdocs build --strict
.venv/bin/python tools/visual_check.py
.venv/bin/python tools/benchmark_v2.py
.venv/bin/python tools/stress20.py
uv build --wheel --out-dir out/dist
.venv/bin/python tools/check_wheel.py out/dist/inklet-*.whl
```

The wheel check uses uv when available, otherwise Python's venv/pip support.
Neither visual checker updates baselines during normal runs. Changes to the
baseline require explicit visual review and `tools/visual_check.py --update`.
