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
- The preset comparison renders the same plots, workflow, table and native 3D
  object in all ten presets, preserving SVG/PDF files and both previews.
  Preset tests cover inherited styles, explicit overrides, switching, caching,
  data provenance and physical formats.

The figure job uses Ubuntu 24.04, Python 3.12, Chrome, Poppler, DejaVu and Noto
fonts. The visual checker verifies the DejaVu file hashes before comparisons;
font mismatches fail rather than refreshing references. Review artifacts and
test reports are retained for seven days, including on failed runs. The static
documentation site is included in the artifact. Hosting is configured separately
through Read the Docs.

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

## Read the Docs

[`.readthedocs.yaml`](../.readthedocs.yaml) configures a strict MkDocs build on
Ubuntu 24.04 with Python 3.12 and the pinned documentation requirements.
The site includes the existing gallery images and search index; building it
does not require Chrome, Blender or regeneration of the figures.

To activate hosting, sign into the
[Read the Docs dashboard](https://app.readthedocs.org/dashboard/) with GitHub,
choose **Add project**, and select `Mapika/inklet`. Use `inklet` as the project
slug, `master` as the default branch, and `.readthedocs.yaml` as the configuration
file. If the repository is missing, grant the Read the Docs GitHub App access to
`Mapika/inklet`. The GitHub integration enables builds on subsequent pushes.

After the first successful build, the intended documentation address is
`https://inklet.readthedocs.io/en/latest/`. MkDocs uses the canonical URL supplied
by Read the Docs, with that address as the local-build default.

Initially build **latest** from `master`. The existing `v2.5.0` tag predates the
Read the Docs configuration; future release tags will include it and can be
activated as documentation versions without changing the published `v2.5.0` tag.

## Publishing to PyPI

The separate [publishing workflow](../.github/workflows/publish.yml) uploads
the wheel and source archive from an existing, published GitHub release.
It verifies the release's `SHA256SUMS` and runs Twine's strict metadata checks.
It does not rebuild the packages, so GitHub and PyPI receive identical files.
The workflow accepts stable release tags such as `v2.5.0` and runs from `master`.

For the first upload, sign into PyPI and add a GitHub pending publisher under
[account publishing](https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `inklet` |
| GitHub owner | `Mapika` |
| Repository name | `inklet` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

The workflow filename is just `publish.yml`, without `.github/workflows/`.
The matching GitHub environment is named `pypi`. Authentication uses
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/);
no PyPI API token or GitHub repository secret is needed. The first successful
upload creates the PyPI project and activates its publisher for future uploads.

In GitHub Actions, select **Publish to PyPI**, then **Run workflow** on `master`.
Enter the published release tag. Leave **Validate release files without uploading
to PyPI** checked for a dry run; uncheck it to publish after configuring PyPI.
The workflow runs only when manually dispatched. Creating a tag or GitHub release
does not upload to PyPI automatically.

The same operations are available through the GitHub CLI:

```bash
# Validate the existing release without uploading.
gh workflow run publish.yml --ref master -f tag=v2.5.0 -F dry_run=true

# Publish after configuring the pending publisher on PyPI.
gh workflow run publish.yml --ref master -f tag=v2.5.0 -F dry_run=false
```

For subsequent versions, run release checks, create the tag and GitHub release,
and attach the wheel, source archive and `SHA256SUMS` before dispatching the
publishing workflow. PyPI does not permit replacing an uploaded distribution;
package changes require a new version.
