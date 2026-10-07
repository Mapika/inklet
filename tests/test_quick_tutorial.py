"""The one-call tutorial runs in order, draws no warnings and matches its figures.

`docs/quick-charts.md` is one script: every python block runs in order in one
namespace, so a later block may reuse a name from an earlier one. Each chart
the blocks leave behind must lint with no errors or warnings, and no block may
emit a Python warning (a layout problem, a width the layout cannot use, and so on).
"""
import importlib.util
import warnings
from pathlib import Path

from inklet.quick import Chart, Layout

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs' / 'quick-charts.md'
spec = importlib.util.spec_from_file_location('tutorial_figures', ROOT / 'tools' / 'tutorial_figures.py')
tutorial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tutorial)


def serious(figure):
    return [d for d in figure.lint() if d.severity in ('error', 'warning')]


def test_the_tutorial_has_its_python_blocks_and_the_data_it_reads():
    found = tutorial.blocks(PAGE.read_text())
    assert len(found) >= 15
    assert (ROOT / 'docs' / 'assets' / 'data' / 'growth-assay.csv').is_file()
    assert 'assets/data/growth-assay.csv' in PAGE.read_text()


def test_every_python_block_runs_in_order_and_draws_no_warnings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run = tutorial.run(PAGE.read_text())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        seen = 0
        while True:
            before = len(caught)
            try:
                index, code, _, namespace = next(run)
            except StopIteration:
                break
            new = caught[before:]
            assert not new, f'block {index + 1} warned: ' + '; '.join(str(w.message) for w in new)
            charts = {id(v): v for v in namespace.values() if isinstance(v, (Chart, Layout))}
            for chart in charts.values():
                figure = chart.compile()
                assert not serious(figure), f'block {index + 1}:\n' + figure.report()
            seen += 1
    assert seen == len(tutorial.blocks(PAGE.read_text()))


def test_the_committed_figures_are_the_ones_the_page_code_draws(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    drawn = tutorial.draw(tmp_path / 'figures')
    assert drawn, 'the page declares no figures'
    for path in drawn:
        committed = ROOT / 'docs' / 'assets' / 'tutorial' / path.name
        assert committed.is_file(), f'{path.name} is not committed; run python tools/tutorial_figures.py'
        assert committed.read_bytes() == path.read_bytes(), (
            f'{path.name} is out of date; run python tools/tutorial_figures.py')
