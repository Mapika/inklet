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


def test_a_render_failure_leaves_every_existing_file_as_it_was(tmp_path, monkeypatch):
    """Every format renders before any file is touched, so a PDF that fails
    to render leaves the SVG written before it and the old PDF alone."""
    paths = [tmp_path / "f.svg", tmp_path / "f.pdf"]
    _figure().save(*paths)
    before = {p: p.read_bytes() for p in paths}
    fig = _figure("A changed figure")

    def broken(*args, **kwargs):
        raise RuntimeError("cannot render")
    monkeypatch.setattr(type(fig), "to_pdf", broken)
    with pytest.raises(RuntimeError, match="cannot render"):
        fig.save(*paths)
    assert {p: p.read_bytes() for p in paths} == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.pdf", "f.svg"]


def test_a_failed_write_removes_its_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "f.svg"
    _figure().save(target)
    before = target.read_bytes()

    def no_rename(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", no_rename)
    with pytest.raises(OSError, match="disk full"):
        _figure("A changed figure").save(target)
    assert target.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["f.svg"]


def test_ids_reach_the_svg_and_are_dropped_for_the_pdf(tmp_path):
    svg, pdf = tmp_path / "f.svg", tmp_path / "f.pdf"
    _figure().save(svg, pdf, ids="document")
    assert svg.read_text(encoding="utf-8") == _figure().to_svg(ids="document")
    with pytest.raises(TypeError, match="ids="):
        _figure().save(pdf, ids="document")


def test_save_returns_one_entry_per_path():
    """`save()` used to return None; callers that ignored it are unaffected,
    and the mapping has one entry per requested file, keyed by its path."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        paths = [os.path.join(tmp, "f.svg"), os.path.join(tmp, "f.pdf")]
        assert _figure().save(*paths) == {p: True for p in paths}


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_an_existing_file_keeps_its_mode_and_a_new_one_follows_the_umask(tmp_path):
    old, new = tmp_path / "old.svg", tmp_path / "new.svg"
    _figure().save(old)
    os.chmod(old, 0o640)
    _figure("A changed figure").save(old)
    assert old.stat().st_mode & 0o777 == 0o640
    mask = os.umask(0o022)
    try:
        _figure().save(new)
    finally:
        os.umask(mask)
    assert new.stat().st_mode & 0o777 == 0o644


@pytest.mark.skipif(os.name != "posix", reason="symbolic links")
def test_a_symbolic_link_is_followed(tmp_path):
    real = tmp_path / "real.svg"
    _figure().save(real)
    link = tmp_path / "link.svg"
    link.symlink_to(real)
    _figure("A changed figure").save(link, ids="document")
    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == _figure("A changed figure").to_svg(ids="document")
