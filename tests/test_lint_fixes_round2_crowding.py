"""CROWDING: a key's own parts, and naming the mark instead of the panel.

ISSUES-medicine-econ 4: a size key set below its plot reported its own
numbers as crowding its own circles, and every CROWDING against a mark named
the whole panel (`'1e7' and a are only 0.68mm apart`, `'Japan' and y2007 ...`),
so the hint "move the label rather than the mark" had nothing to point at.
"""

from __future__ import annotations

import warnings

import inklet as i


def crowding(figure):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return [d for d in figure.lint() if d.code == "CROWDING"]


def _compiled(spec, preset="scientific.modern"):
    doc = i.preset(preset).document()
    doc.add("a", spec)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return doc.compile()


def test_a_size_key_below_the_plot_does_not_crowd_itself():
    scale = i.plot.area_scale(1e9, 15)
    p = i.plot_spec(x=(0, 1), y=(0, 1))
    p.scatter([(0.5, 0.5)], size=2)
    p.axes(x="x", y="y")
    p.size_key(scale, values=[1e7, 1e8, 1e9], side="bottom")
    assert crowding(_compiled(p)) == []


def test_a_key_is_still_measured_against_the_data():
    # A legend plate 0.68mm from a histogram bar is a real near miss; it is
    # the key against the data, not the key against itself.
    p = i.plot_spec(80, 40, x=(0, 6), y=(0, 6))
    p.hist({"a": [1, 2, 2, 3, 3, 3, 4, 5, 5, 5, 5, 5]}, bins=list(range(0, 7)))
    p.axes().legend(corner="ne")
    doc = i.document(width=100)
    doc.add("a", p)
    (finding,) = crowding(doc.compile())
    assert finding.message.startswith("the legend plate ")
    # The other party is the bar, by id and by data position -- not "a".
    assert "and the mark " in finding.message and "at x=3, y=2.5" in finding.message
    assert " and a are" not in finding.message
    assert "move " in finding.hint and "rather than the mark" in finding.hint


def test_a_point_label_against_a_bubble_names_the_bubble_not_the_panel():
    p = i.plot_spec(60, 40, x=(0, 10), y=(0, 10))
    p.scatter([(5, 5)], size=8)
    # The bubble is 8mm across; the label's foot sits 0.3mm above its top.
    p.text(5, 5, "Japan", anchor="s", offset=(0, -4.3))
    p.axes()
    found = crowding(_compiled(p))
    assert found, "the label sits a hair off the bubble"
    (finding,) = found
    assert "the label 'Japan' (" in finding.message
    assert "and the mark (" in finding.message
    assert "at x=5, y=5" in finding.message
    assert "and a are" not in finding.message


def test_a_named_object_is_still_named():
    # Naming the mark only replaces a *container*; a model or a group the
    # author named is still the thing to move.
    from inklet.core import Diagram, EllipsePrim, resolve
    from inklet.diagnostics import build_context
    from inklet.diagnostics.rules import _is_container

    marks = Diagram(children=(Diagram(prim=EllipsePrim(1, 1), kind="mark"),),
                    name="mirror")
    page = Diagram(children=(marks,), kind="page")
    ctx = build_context(page, resolve(page))
    assert not _is_container(ctx, marks.id)
    assert _is_container(ctx, page.id)


def test_two_labels_of_one_key_are_still_measured_against_each_other():
    # The exemption is for a key's labels against its own swatches; numbers
    # in a key that nearly touch each other are still hard to read.
    from inklet.core import Diagram, resolve
    from inklet.diagnostics import build_context
    from inklet.diagnostics.rules import _same_key

    a = i.text("5,000", text_fill="#000000")
    b = i.text("2,000", text_fill="#000000").translated(a.width + 0.3, 0)
    key = Diagram(children=(a, b), kind="width-key")
    found = [d for d in i.lint(key, page=key.bbox.pad(5)) if d.code == "CROWDING"]
    assert found and "5,000" in found[0].message
    ctx = build_context(key, resolve(key))
    assert _same_key(ctx, a.id, b.id)
