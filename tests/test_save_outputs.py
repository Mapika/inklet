"""`save()` writes a set of exports atomically, with one timestamp, and can
leave an unchanged figure's files alone."""
from __future__ import annotations

import os

import pytest

import inklet


def _figure(words="Saved once"):
    fig = inklet.figure(width=40, height=20)
    fig.add(inklet.text(words))
    return fig


def test_every_file_of_one_save_shares_one_mtime(tmp_path):
    paths = [tmp_path / f"f.{ext}" for ext in ("pdf", "svg", "png")]
    written = _figure().save(*paths, dpi=72)
    assert all(written.values())
    stamps = {p.stat().st_mtime_ns for p in paths}
    assert len(stamps) == 1


def test_changed_mode_leaves_identical_files_untouched(tmp_path):
    paths = [tmp_path / "f.svg", tmp_path / "f.pdf"]
    _figure().save(*paths, ids="document")
    for p in paths:
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
    written = _figure().save(*paths, write="changed", ids="document")
    assert written == {str(p): False for p in paths}
    assert all(p.stat().st_mtime_ns == 1_000_000_000 for p in paths)


def test_changed_mode_rewrites_the_whole_set_when_any_file_changes(tmp_path):
    paths = [tmp_path / "f.svg", tmp_path / "f.pdf"]
    _figure().save(*paths)
    for p in paths:
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
    written = _figure("Saved twice").save(*paths, write="changed")
    assert all(written.values())
    assert len({p.stat().st_mtime_ns for p in paths}) == 1
    assert paths[0].stat().st_mtime_ns != 1_000_000_000


def test_no_temporary_files_are_left_behind(tmp_path):
    _figure().save(tmp_path / "f.svg", tmp_path / "f.pdf")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.pdf", "f.svg"]


def test_unknown_write_mode_raises():
    with pytest.raises(ValueError, match="write mode"):
        _figure().save("f.svg", write="sometimes")


def test_document_ids_make_the_svg_independent_of_earlier_builds():
    """Node ids come from one counter per process; `ids="document"` numbers
    them per file, so the second build of a figure is byte-identical."""
    first = _figure().to_svg(ids="document")
    _figure("something else built in between").to_svg()
    assert _figure().to_svg(ids="document") == first
    assert _figure().to_svg() != _figure().to_svg()   # the default keeps node ids
