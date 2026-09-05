"""`inklet.fit` builds a recipe until it fits, and says so when it cannot.

The loop this replaces was written by hand five times in `stress/panels/` and
a sixth time by a fresh agent working from the brief alone, which is as clear a
signal as a library gets that a function is missing. So the tests here are
mostly about the promises the hand-written versions could not make: never
overshoot the budget, come back the exact size that was asked for, and fail
loudly rather than quietly returning something too big.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import Diagram, DiagramError, RectPrim, Vec2

BODY = ("Participants were assessed for eligibility between March 2021 and "
        "November 2022 at four centres, and randomised in permuted blocks.")


def rect(width: float, height: float = 10.0) -> Diagram:
    """A builder whose measurement is exactly its parameter."""
    return Diagram(prim=RectPrim(width, height), kind="box")


def wrapped(width: float) -> Diagram:
    """A builder that moves in steps, because text wraps in whole words."""
    return inklet.box(inklet.text(BODY, width=width))


# -- the size it was asked for --------------------------------------------


def test_a_continuous_recipe_lands_on_the_target():
    assert inklet.fit(rect, width=50.0).width == pytest.approx(50.0, abs=0.05)


def test_the_result_is_the_width_it_was_asked_for_even_in_steps():
    """Wrapping cannot hit 52mm. Padding the slack is what makes a row line up."""
    assert inklet.fit(wrapped, width=52.0).width == pytest.approx(52.0, abs=1e-9)


def test_without_exact_the_content_keeps_its_own_size():
    loose = inklet.fit(wrapped, width=52.0, exact=False)

    assert loose.width < 52.0
    assert inklet.fit(wrapped, width=52.0).width > loose.width


def test_the_budget_is_never_overshot():
    """The half that matters. A `fit` that returns something too wide is the
    silent failure the whole function exists to remove."""
    for target in (30.0, 41.0, 52.0, 63.5, 80.0):
        assert inklet.fit(wrapped, width=target, exact=False).width <= target


def test_it_finds_the_widest_build_that_still_fits():
    coarse = max((wrapped(w / 10.0).width for w in range(10, 1200)
                  if wrapped(w / 10.0).width <= 52.0), default=0.0)

    assert inklet.fit(wrapped, width=52.0, exact=False).width == pytest.approx(coarse)


def test_height_is_fitted_the_same_way():
    tall = inklet.fit(lambda h: rect(20.0, h), height=33.0)

    assert tall.height == pytest.approx(33.0, abs=0.05)
    assert tall.width == pytest.approx(20.0)


# -- saying so when it cannot ---------------------------------------------


def test_a_recipe_with_a_minimum_larger_than_the_budget_raises():
    with pytest.raises(DiagramError) as caught:
        inklet.fit(lambda w: inklet.box(inklet.text("Supercalifragilistic", width=w)),
                width=4.0)

    message = str(caught.value)
    assert "could not get this below" in message
    assert "minimum size of its own" in message


def test_the_failure_names_the_smallest_it_managed():
    """The number an author needs is the floor, not the fact of failure."""
    floor = inklet.box(inklet.text("Supercalifragilistic")).width

    with pytest.raises(DiagramError) as caught:
        inklet.fit(lambda w: inklet.box(inklet.text("Supercalifragilistic", width=w)),
                width=4.0)

    assert f"{floor:.4g}mm" in str(caught.value)


def test_fitting_both_axes_is_refused():
    with pytest.raises(DiagramError, match="not both and not neither"):
        inklet.fit(rect, width=50.0, height=20.0)


def test_fitting_neither_axis_is_refused():
    with pytest.raises(DiagramError, match="not both and not neither"):
        inklet.fit(rect)


def test_a_target_of_zero_is_refused():
    with pytest.raises(DiagramError, match="positive width"):
        inklet.fit(rect, width=0.0)


def test_a_builder_that_returns_something_else_says_which_call_broke():
    with pytest.raises(DiagramError, match="has to return a Diagram"):
        inklet.fit(lambda w: "not a diagram", width=50.0)


# -- what survives the fit ------------------------------------------------


def test_anchors_registered_by_the_recipe_survive_the_padding():
    """`row` lines panels up on an anchor, and `fit` is what a panel goes
    through on the way into a row. Every combinator drops anchors."""
    def build(width: float) -> Diagram:
        node = wrapped(width)
        return node.anchor("origin", Vec2(0.0, 0.0))

    fitted = inklet.fit(build, width=52.0)

    assert fitted.anchor_point("origin") == Vec2(0.0, 0.0)


def test_a_guess_changes_the_work_and_not_the_answer():
    calls: list[int] = []

    def counted(width: float) -> Diagram:
        calls.append(1)
        return wrapped(width)

    near = inklet.fit(counted, width=52.0, guess=48.0, exact=False).width
    close = len(calls)
    calls.clear()
    far = inklet.fit(counted, width=52.0, guess=0.5, exact=False).width

    assert near == pytest.approx(far)
    assert close < len(calls)


def test_the_same_request_gives_the_same_answer():
    first = inklet.fit(wrapped, width=52.0)
    second = inklet.fit(wrapped, width=52.0)

    assert first.width == second.width
    assert first.height == second.height


def test_a_fitted_panel_drops_into_a_stack_at_its_full_width():
    left = inklet.fit(wrapped, width=52.0)
    right = inklet.fit(lambda w: inklet.box(inklet.text("Short", width=w)), width=30.0)

    row = inklet.hstack([left, right], gap=4.0)

    assert row.width == pytest.approx(52.0 + 4.0 + 30.0)
