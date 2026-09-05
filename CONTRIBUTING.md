# Contributing to Inklet

Use a focused change with a runnable example or minimal reproducer. Describe
the resulting behavior and how it was checked. Keep numerical inputs and
expected results explicit; use simulated data when source data cannot be shared.

## Development environment

From a checkout with Python 3.12 and `uv` installed:

```sh
uv venv --python 3.12
uv pip install -r requirements-ci.txt -e .
.venv/bin/python -m inklet doctor
```

The lock file is the tested scientific environment. Vector-only development
needs fewer packages, but the full suite also exercises optional image and 3D
features. CI installs fonts, Chrome and Poppler as described in
[release checks](docs/release-checks.md).

## Test a change

Run the tests relevant to the modified behavior first:

```sh
.venv/bin/python -m pytest -q tests/test_document.py tests/test_document_v25.py
```

For a release or a broad rendering change:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tools/gen_api.py --check
.venv/bin/python tools/visual_check.py --output out/visual
.venv/bin/python tools/benchmark_v2.py --output out/benchmarks
.venv/bin/python tools/stress20.py --output out/stress20
```

Visual checks need the preview tools. Inspect differences before changing a
baseline; see [visual test instructions](tests/visual/README.md). Performance
results are machine-dependent, so include workload and environment details.

## Documentation

User guides live in `docs/`, with navigation in `mkdocs.yml`. Markdown should
remain readable in both GitHub and the local site. Link to repository files
relatively; the site hook includes gallery images and converts other
out-of-docs links to repository URLs. This avoids duplicate copies of examples
and preview assets.

```sh
uv pip install -r requirements-docs.txt
.venv/bin/python -m pytest -q tests/test_docs.py tests/test_cookbook.py tests/test_guides.py tests/test_docs_site.py
.venv/bin/python tools/gen_api.py --check
.venv/bin/python -m mkdocs build --strict
.venv/bin/python -m mkdocs serve
```

The static site is written to `out/docs-site/`; local serving uses port 8000.
The [MkDocs configuration reference](https://www.mkdocs.org/user-guide/configuration/)
describes navigation and strict validation. CI builds the site and uploads it
as an artifact. There is no automatic public deployment.

New introductory guides should use complete Python examples or clearly state
what preceding blocks they depend on. `tests/test_guides.py` executes registered
pages in a temporary directory, sharing a namespace only within each page.
Prefix a Python fence with `<!-- Requires preview renderers. -->` followed by
a blank line for examples needing preview tools; those examples are exercised
when the tools are available. File-dependent fragments
should state which user files are needed.

`docs/api.md` is generated from public signatures and docstrings. Change the
source docstrings or `tools/gen_api.py`, then regenerate it; do not edit the
generated file by hand. Keep instructions literal and document limitations
alongside the corresponding feature.

## Repository structure

| Path | Purpose |
|---|---|
| `src/inklet/document/` | Live definitions, data, measurement and compilation |
| `src/inklet/plot/`, `draw/`, `layout/`, `links/` | Charts, geometry composition and routing |
| `src/inklet/three/`, `assets/` | Meshes, vector 3D and image processing |
| `src/inklet/typeset/`, `themes/` | Shaped text and physical styling |
| `src/inklet/render/`, `diagnostics/` | Export backends, review and drawing checks |
| `tests/` | Unit, integration and visual regression checks |
| `examples/`, `figures/`, `stress/` | Runnable figures and larger workloads |
| `tools/` | Documentation generation, wheel checks and benchmarks |

Read [the core contract](CONTRACT.md) before changing fundamental geometry,
and [the compilation contract](docs/design/v2.md) before changing dependency,
measurement or caching semantics. Update [the changelog](CHANGELOG.md) for
user-visible changes.
