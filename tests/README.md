# Test maintenance

Organize tests by enduring behavior, not the release which introduced it.
Keep numerical/geometry oracles, invalid-input contracts and old regression
reproducers even after a new end-to-end workflow covers their happy path.

- **Contracts:** `test_<capability>.py`; a failure names the broken behavior.
- **Acceptance:** complete workflows carry `pytest.mark.acceptance`. Run with
  `python -m pytest -m acceptance`; the full suite includes them automatically.
- **Browser support:** reusable execution and SVG/pixel oracles live in
  `browser_support.py`, never in another test module.
- **Visual fixtures:** `visual/` retains approved baselines and renderer/font
  fingerprints. Historical fixture identifiers stay stable for comparisons.
- **Optional integrations:** explicit skip reasons distinguish missing tools
  from passing coverage. The release runner `tools/acceptance.py` rejects skips as well as failures
  and requires all four reference workflows.

Before deleting a test, identify the replacement assertion and fixture. Matching
function bodies can call different helpers and therefore test different artwork.
Consolidate setup or parameterize equivalent cases while retaining the input
variants and failure oracles. Never retire a regression merely because it came
from an earlier version.

Current complete workflows and their ownership are listed in
[acceptance](../docs/acceptance.md). Older filenames were renamed to feature
names in dev16; Git history retains the original provenance. Do not duplicate
old modules as compatibility wrappers: pytest would collect their tests twice.
