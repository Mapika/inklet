"""The code in the docstrings has to run.

A fresh agent handed this library and a figure brief read about three thousand
lines of source before writing a line of its own, and reported that the one
snippet in `inklet.plot`'s module docstring did not work -- `figure(p.build())` is
not the API. That snippet was the only documentation `inklet.plot` had.

A docstring example is not decoration. It is the first thing anyone copies, and
for a reader who cannot see the figure it is also the only evidence of what a
working call looks like. So the ones that are meant to be complete are executed
here, in a scratch directory, and a failure is a documentation bug.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from pathlib import Path

import pytest

import inklet

SOURCE = Path(inklet.__file__).parent

#: Module docstrings whose example is meant to run start to finish.
COMPLETE = [
    "__init__.py",
    "draw/__init__.py",
    "themes/__init__.py",
    "diagnostics/__init__.py",
    "plot/__init__.py",
]

#: And the ones that are deliberately fragments, with the reason. Listed rather
#: than skipped silently, so that "this cannot run" stays a decision somebody
#: made instead of an oversight nobody noticed.
FRAGMENTS = {
    "assets/__init__.py": "needs an image file, and none ships with the package",
    "three/__init__.py": "needs a mesh on disk and two meshes built by the caller",
    "three/blender/__init__.py": "needs a Blender install",
}


def snippet(relative: str) -> str:
    """The first indented code block out of a module docstring.

    First, and contiguous. Some docstrings indent a prose list further down --
    `inklet.three` describes its pipeline that way -- and running from the first
    indented line to the last would hand the compiler a sentence.
    """
    text = ast.get_docstring(ast.parse((SOURCE / relative).read_text())) or ""
    block: list[str] = []
    for line in text.splitlines():
        indented = line.startswith("    ")
        if indented:
            block.append(line)
        elif not line.strip():
            if block:
                block.append("")
        elif block:
            break
    assert any(line.strip() for line in block), (
        f"{relative} has no indented example")
    while block and not block[-1].strip():
        block.pop()
    return textwrap.dedent("\n".join(block))


@pytest.mark.parametrize("relative", COMPLETE)
def test_the_example_in_the_module_docstring_runs(relative, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = snippet(relative)

    exec(compile(code, f"{relative}:docstring", "exec"), {"__name__": "__doc__"})


@pytest.mark.parametrize("relative", COMPLETE)
def test_a_complete_example_calls_something(relative):
    """Guard against the extractor quietly matching prose instead of code."""
    assert "inklet" in snippet(relative)


@pytest.mark.parametrize("relative", sorted(FRAGMENTS))
def test_a_fragment_is_still_syntactically_python(relative):
    """A fragment may not run, but it must not be nonsense either."""
    ast.parse(snippet(relative))


def test_every_module_docstring_with_an_example_is_accounted_for():
    """New examples land in one list or the other, not in neither."""
    known = set(COMPLETE) | set(FRAGMENTS)
    for path in sorted(SOURCE.rglob("__init__.py")):
        relative = path.relative_to(SOURCE).as_posix()
        text = ast.get_docstring(ast.parse(path.read_text())) or ""
        looks_like_code = any(
            line.startswith("    ") and ("inklet." in line or "import " in line)
            for line in text.splitlines())
        assert not looks_like_code or relative in known, (
            f"{relative} has an example that no test runs; add it to COMPLETE, "
            "or to FRAGMENTS with the reason it cannot run")


# -- the generated reference ----------------------------------------------


def test_the_api_reference_is_up_to_date():
    """`docs/api.md` is generated. A generated file that drifts is worse than
    no file, because it is wrong with a straight face."""
    import subprocess

    root = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, str(root / "tools" / "gen_api.py"), "--check"],
        capture_output=True, text=True, cwd=root)

    assert done.returncode == 0, done.stdout + done.stderr


def test_every_public_name_says_what_it_is():
    """A reference entry that reads "(undocumented)" is a hole in the surface,
    and the reader who finds it has no second place to look."""
    missing = [name for name in inklet.__all__
               if not (inspect.getdoc(getattr(inklet, name, None)) or "").strip()]

    assert missing == []


#: Classes an author is expected to call methods on, as opposed to the core
#: value types (`Vec2`, `Rect`, `Affine`) whose names are their own
#: documentation. `core/` is frozen by CONTRACT.md, so this is also the set
#: whose docstrings can be fixed when the guard fires.
AUTHORED = ("Panel", "Figure", "Scale", "Ramp")


def test_the_classes_an_author_drives_document_their_methods():
    """`docs/api.md` now lists a class's methods, so a hole in one ships.

    blind-02 spent twenty minutes looking for a way to draw a matrix on a
    `Panel` and concluded there was none, because the reference named the
    class and none of its fourteen methods.
    """
    import inspect

    missing = []
    for class_name in AUTHORED:
        cls = getattr(inklet, class_name, None)
        assert cls is not None, f"{class_name} is not exported"
        for name, member in inspect.getmembers(cls, callable):
            if name.startswith("_") or name not in vars(cls):
                continue
            if not (inspect.getdoc(member) or "").strip():
                missing.append(f"{class_name}.{name}")

    assert missing == []
