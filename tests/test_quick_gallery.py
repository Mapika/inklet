"""The chart gallery shows every public one-call chart, lints clean and matches its generator."""
import ast
import importlib.util
from pathlib import Path

import pytest

from inklet import quick

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('quick_gallery', ROOT / 'tools' / 'quick_gallery.py')
gallery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gallery)

# Names in quick.__all__ that build a chart object or a layout rather than a chart.
NOT_CHARTS = {'Chart', 'Layout', 'LayoutWarning', 'chart'}


def _called(code):
    return {node.func.attr for node in ast.walk(ast.parse(code))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


def test_gallery_shows_every_public_chart():
    public = {name for name in quick.__all__ if name not in NOT_CHARTS}
    assert all(callable(getattr(quick, name)) for name in public)
    shown = set().union(*(_called(gallery.code_of(example)) for example in gallery.EXAMPLES))
    assert public <= shown, f'missing from the chart gallery: {sorted(public - shown)}'


def test_each_example_is_on_exactly_one_card():
    cards = [name for _, _, group in gallery.FAMILIES for name, _ in group]
    assert sorted(cards) == sorted(example.name for example in gallery.EXAMPLES)


def test_cards_link_to_their_sections():
    text = gallery.markdown()
    by_name = {example.name: example for example in gallery.EXAMPLES}
    for _, _, group in gallery.FAMILIES:
        for name, _ in group:
            title = by_name[name].title
            assert f'page": "quick-gallery.md#{gallery.anchor(title)}"' in text
            assert f'\n### {title}\n' in text


def test_page_matches_generator():
    assert (ROOT / 'docs' / 'quick-gallery.md').read_text() == gallery.markdown()


@pytest.mark.parametrize('example', gallery.EXAMPLES, ids=lambda example: example.name)
def test_example_lints_clean(example):
    try:
        gallery.render(example)
    except SystemExit as exc:  # render() reports the errors and warnings it found
        pytest.fail(str(exc))
