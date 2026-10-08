"""Lint hints that name things an author can find and act on.

* LINK_CROSSES names an unnamed box by the words written on it, not its id.
* CROWDING between plot labels names the knobs that usually open the gap.
* OVERLAP between long category tick labels offers `orient='h'`.
"""
import re
import warnings

import inklet as i


def _quietly(build):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return build()


def _codes(figure, code):
    return [d for d in figure.lint() if d.code == code]


def _crossing(figure):
    (finding,) = _codes(figure, 'LINK_CROSSES')
    return finding


def _crossed_figure(middle):
    a, b = i.box('A'), i.box('B')
    figure = i.figure(width=110)
    figure.add(i.hstack([a, middle, b], gap=12))
    figure.link(a, b)
    return figure


# -- LINK_CROSSES: name the box by its words ----------------------------------------

def test_an_unnamed_labelled_box_is_named_by_its_words_in_the_crossing_hint():
    hint = _crossing(_crossed_figure(i.box(i.text('Box 4')))).hint
    assert hint.startswith("move the box 'Box 4' off the line between A -> B")
    assert "link via the box 'Box 4' in two hops" in hint
    assert not re.search(r'\bbox\d+\b', hint), hint


def test_a_named_box_keeps_its_name_in_the_crossing_hint():
    hint = _crossing(_crossed_figure(i.box('Box 4'))).hint
    assert hint.startswith('move Box 4 off the line between A -> B')


# -- CROWDING between plot labels: the knobs that open the gap ----------------------

def test_crowded_labels_name_the_plot_knobs_that_open_them():
    figure = i.figure(width=90)
    figure.add(i.hstack([i.text('Alpha'), i.spacer(0.2, 4), i.text('Beta')], gap=0))
    (finding,) = _codes(figure, 'CROWDING')
    assert finding.hint.startswith('add ') and 'of separation' in finding.hint
    for knob in ('label_side=', 'ylim=', "width='double'"):
        assert knob in finding.hint


def test_crowded_boxes_without_text_are_not_sent_to_the_label_knobs():
    figure = i.figure(width=90)
    figure.add(i.hstack([i.box('Alpha'), i.spacer(0.2, 4), i.box('Beta')], gap=0))
    (finding,) = _codes(figure, 'CROWDING')
    assert 'label_side=' not in finding.hint


# -- OVERLAP between category tick labels: horizontal bars for long names -----------

def _category_bars(names, width=60):
    values = list(range(len(names)))
    chart = i.bar({'c': names, 'v': values}, x='c', y='v', width=width)
    return _quietly(lambda: chart.axes(x='c', y='v').compile())


def test_long_category_names_are_offered_horizontal_bars():
    names = [f'treatment condition number {k}' for k in range(12)]
    (finding,) = _codes(_category_bars(names), 'OVERLAP')
    assert "orient='h'" in finding.hint
    assert 'stack down the axis' in finding.hint


def test_short_category_names_are_not_offered_horizontal_bars():
    names = [f'cat {k}' for k in range(12)]
    (finding,) = _codes(_category_bars(names), 'OVERLAP')
    assert 'orient' not in finding.hint


def test_two_long_tick_labels_that_overlap_are_offered_horizontal_bars():
    names = ['treatment condition number one', 'treatment condition number two']
    figure = _category_bars(names, width=70)
    (finding,) = _codes(figure, 'OVERLAP')
    assert finding.message.startswith("the tick-label")
    assert "orient='h'" in finding.hint
    assert finding.hint.startswith('separate them by at least')


def test_numeric_tick_labels_are_not_offered_horizontal_bars():
    names = [f'{1000 * k:,}' for k in range(12)]
    findings = _codes(_category_bars(names), 'OVERLAP')
    assert all('orient' not in f.hint for f in findings)
