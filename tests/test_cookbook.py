"""Every recipe in `docs/cookbook.md` is executed here.

The cookbook exists because a fresh agent, given this library and a figure
brief, could not find how to do any of it and invented its own answers -- a
flow with a side branch, sibling boxes at one size, a hole in a grid, a shaded
span on a plot. Documentation that has never been run is how those answers get
invented anyway, one release later, when the API has moved.

So the blocks are extracted and executed in order, sharing one namespace, in a
scratch directory. Their own `assert` lines are the assertions: a recipe that
claims a clean lint has to produce one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

COOKBOOK = Path(__file__).resolve().parent.parent / "docs" / "cookbook.md"

BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)


def blocks() -> list[str]:
    return BLOCK.findall(COOKBOOK.read_text())


def test_the_cookbook_still_has_recipes_in_it():
    """Guard the extractor: a regex that silently matches nothing would make
    every test below pass by doing nothing at all."""
    assert len(blocks()) >= 10


def test_every_recipe_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {"__name__": "cookbook"}

    for index, code in enumerate(blocks()):
        try:
            exec(compile(code, f"cookbook.md:block{index + 1}", "exec"), namespace)
        except Exception as exc:  # noqa: BLE001 -- the point is to report which
            pytest.fail(f"cookbook block {index + 1} failed: {exc!r}\n\n{code}")


def test_each_recipe_asserts_something():
    """A block with no assertion is a claim nobody is checking."""
    unchecked = [i + 1 for i, code in enumerate(blocks())
                 if "assert" not in code and "import inklet" not in code]

    assert unchecked == []
