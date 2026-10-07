"""TICKS_DROPPED: explicit ticks an axis thinned away reach `report()`.

ISSUES-earth-life 3: an inset asked for six month ticks, printed three, and
said so only with a Python `UserWarning` on stderr while `report()` read
"clean". The axis now records what it dropped in a `ticks_dropped` note and
the linter reports it. The note is written by `plot/axis.py`; until that hook
lands the end-to-end test is an expected failure and the rule is exercised
on a note set by hand.
"""

from __future__ import annotations

import sys
import warnings

import pytest

import inklet as i
from inklet.diagnostics.plot_rules import TICKS_DROPPED_NOTE

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _axis_module():
    import inklet.plot.panel  # noqa: F401  (loads the module by its full name)
    return sys.modules["inklet.plot.axis"]


HOOKED = hasattr(_axis_module(), "TICKS_DROPPED_NOTE")


def found(diags):
    return [d for d in diags if d.code == "TICKS_DROPPED"]


def _month_panel(**options):
    p = i.plot.panel(27, 17, x=(0.5, 12.5), y=(0, 1))
    p.line([(1, 0), (12, 1)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.axes(x_options=dict(ticks=[2, 4, 6, 8, 10, 12],
                              format=lambda m: MONTHS[int(m) - 1], **options))
        return p.build()


def _x_axis(node):
    axes = [n for n in node.walk() if n.kind == "axis"]
    return max(axes, key=lambda n: n.bbox.width)


def _lint(node):
    return i.lint(node, page=node.bbox)


def test_a_dropped_tick_note_is_a_warning_naming_the_ticks():
    node = _month_panel()
    _x_axis(node).note(TICKS_DROPPED_NOTE, {
        "values": (4.0, 8.0, 12.0), "labels": ("Apr", "Aug", "Dec"),
        "supplied": 6, "side": "bottom"})
    (finding,) = found(_lint(node))
    assert finding.severity == "warning"
    assert "the x axis" in finding.message
    assert "3 of 6 explicitly supplied ticks" in finding.message
    assert finding.message.endswith("Apr, Aug, Dec")
    assert "thin=False" in finding.hint and "fewer ticks" in finding.hint
    assert "more width" in finding.hint


def test_values_stand_in_when_the_note_has_no_labels():
    node = _month_panel()
    _x_axis(node).note(TICKS_DROPPED_NOTE, {"values": (4.0, 8.0)})
    (finding,) = found(_lint(node))
    assert finding.message.endswith("4, 8")
    assert "2 explicitly supplied" in finding.message


def test_a_note_carried_up_onto_wrappers_is_reported_once():
    node = _month_panel()
    _x_axis(node).note(TICKS_DROPPED_NOTE, {"labels": ("Apr",), "supplied": 6})
    # A wrapper that inherited its single child's notes, as `carry_notes`
    # does, repeats the note; only the axis itself is reported.
    wrapper = i.Diagram(children=(node,))
    wrapper.notes[TICKS_DROPPED_NOTE] = {"labels": ("Apr",), "supplied": 6}
    assert len(found(_lint(wrapper))) == 1


def test_no_note_no_finding():
    assert found(_lint(_month_panel(thin=True))) == []


@pytest.mark.xfail(not HOOKED, strict=True,
                   reason="needs the plot/axis.py ticks_dropped note (see report)")
def test_the_published_repro_reports_the_dropped_months():
    sub = i.plot_spec(27, 17, x=(0.5, 12.5), y=(0, 1))
    sub.line([(1, 0), (12, 1)])
    sub.axes(x_options=dict(ticks=[2, 4, 6, 8, 10, 12],
                            format=lambda m: MONTHS[int(m) - 1]))
    p = i.plot_spec(89, 74, x=(0, 10), y=(0, 10))
    p.line([(0, 0), (10, 10)]).axes()
    p.inset(sub, corner="nw", width=None)
    doc = i.preset("scientific.modern", format="single-column").document()
    doc.add("a", p)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = doc.compile().report()
    assert "TICKS_DROPPED" in report
    assert "3 of 6" in report


def test_thin_true_or_false_is_an_answer_and_stays_quiet():
    for thin in (True, False):
        sub = i.plot_spec(27, 17, x=(0.5, 12.5), y=(0, 1))
        sub.line([(1, 0), (12, 1)])
        sub.axes(x_options=dict(ticks=[2, 4, 6, 8, 10, 12], thin=thin,
                                format=lambda m: MONTHS[int(m) - 1]))
        doc = i.preset("scientific.modern", format="single-column").document()
        doc.add("a", sub)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert "TICKS_DROPPED" not in doc.compile().report()
