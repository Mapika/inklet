"""Small fixes, batch 3: empty annotation text, and one colour bar or key per chart.

* `annotate` with no words refuses at the call, in both APIs, instead of drawing
  a leader to bare paper (lint's ORPHAN_LEADER). The editor refuses to blank one.
* A chart that already draws a colour bar (a heatmap, a continuous scatter)
  takes a later `colorbar(...)` as an update to that bar, not a second bar.
  A second `legend(...)` updates the first key's options.
"""

from __future__ import annotations

import pytest

import inklet as i
from inklet.document.label_overrides import validate


def _steps(chart, method):
    return [options for _, name, _, options in chart.spec._steps if name == method]


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_diagram_annotate_refuses_text_with_no_words(text):
    box = i.box("target", width=20, height=10)
    with pytest.raises(ValueError, match="annotate\\(\\) needs text"):
        i.annotate(box, text, side="e", clear=8.0)


def test_panel_annotate_refuses_text_with_no_words():
    panel = i.panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError, match="annotate\\(\\) needs text"):
        panel.annotate(5, 5, "")


def test_recorded_annotate_refuses_text_with_no_words_at_the_call():
    chart = i.line(x=[1, 2], y=[1, 2])
    with pytest.raises(ValueError, match="annotate\\(\\) needs text"):
        chart.annotate(1, 1, "  ")


def test_a_blank_diagram_body_is_still_allowed():
    # The caller built its own label; only a string with no words is refused.
    box = i.box("target", width=20, height=10)
    assert i.annotate(box, i.text("", kind="label"), side="e", clear=8.0) is not None


def test_composition_annotate_refuses_text_with_no_words_at_the_call():
    with pytest.raises(ValueError, match="annotate\\(\\) needs text"):
        i.composition(100, 50).annotate("chart", "")


def test_editor_refuses_to_blank_an_annotation_label():
    with pytest.raises(ValueError, match="needs text"):
        validate({"peak": {"kind": "plot-annotate", "text": " "}})


def test_heatmap_then_colorbar_title_leaves_one_bar_titled_r():
    chart = i.heatmap([[1, 2], [3, 4]], colorbar=True)
    chart.colorbar(title="r")
    assert _steps(chart, "colorbar") == [{"title": "r"}]
    assert [d for d in chart.compile().lint() if d.code == "DUPLICATE_KEY"] == []


def test_colorbar_update_keeps_options_it_does_not_name():
    chart = i.heatmap([[1, 2], [3, 4]], colorbar="first")
    chart.colorbar(side="bottom")
    assert _steps(chart, "colorbar") == [{"title": "first", "side": "bottom"}]


def test_colorbar_without_an_earlier_bar_records_one():
    # A heatmap with no bar of its own still has a ramp, so the call records one.
    chart = i.heatmap([[1, 2], [3, 4]], colorbar=False)
    chart.colorbar(title="r")
    assert _steps(chart, "colorbar") == [{"title": "r"}]


def test_two_legend_calls_leave_one_key_with_the_second_options():
    chart = i.line(x=[1, 2], y=[1, 2], name="a")
    chart.legend(corner="se")
    chart.legend(corner="nw", title="series")
    assert _steps(chart, "legend") == [{"corner": "nw", "title": "series"}]


def test_a_second_legend_call_keeps_the_options_it_does_not_name():
    chart = i.line(x=[1, 2], y=[1, 2], name="a")
    chart.legend(corner="se", title="old")
    chart.legend(title="new")
    assert _steps(chart, "legend") == [{"corner": "se", "title": "new"}]


def test_two_legend_calls_draw_one_key():
    chart = i.line(x=[1, 2], y=[1, 2], name="a")
    chart.legend(corner="se")
    chart.legend(corner="nw")
    assert [name for _, name, _, _ in chart.plot()._steps].count("legend") == 1
