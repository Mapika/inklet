"""`inklet.fit()` -- build something at the size you asked for.

Every other function here takes diagrams and arranges them. This one takes a
*recipe* and runs it until the result is the width you wanted, which is the one
thing a diagramming library is asked for constantly and the one thing
composition alone cannot give you.

The reason is that some sizes are only knowable after the fact. `inklet.panel(w,
h)` sizes the plot **area**; the tick labels, the axis name and the colorbar
hang outside it, and how much room they take is not known until the text has
been shaped. A column of boxes is the same story from the other end: the text
decides the box, the box decides the column, and the column is the number you
were given. In both directions the parameter you can set and the measurement
you care about are separated by the whole layout, so the only way across is to
build, measure and build again.

That loop was written by hand five times inside this project's own stress
figures before it was written once here, and a fresh agent handed the library
and a figure brief wrote a sixth. Two of those five had independently learned
the same two lessons, and both are kept below: a plain step on the raw error
either oscillates or crawls depending on the shape being fitted, and content
has a floor -- a legend, a long axis name, a word that will not hyphenate --
below which shrinking the parameter stops changing the measurement at all.
"""

from __future__ import annotations

from typing import Callable

from ..core import Diagram, DiagramError, mm
from .flow import Length, pad

__all__ = ["fit"]

#: How far the bracket is allowed to open before we conclude the builder is not
#: responding. Twelve halvings is a factor of four thousand: past that the
#: parameter is not what decides the size.
_SPREAD = 12

#: The bracket's upper end, as a multiple of the guess, when the guess already
#: fits. Growth is geometric so a bad guess costs a handful of builds, not a
#: linear walk.
_GROWTH = 2.0


def fit(build: Callable[[float], Diagram], width: Length | None = None,
        height: Length | None = None, *, guess: float | None = None,
        tries: int = 10, tolerance: Length = 0.05,
        exact: bool = True, with_extras: bool = False):
    """Call `build` with sizes until what it returns fits the target.

    `build` takes one number and returns a diagram. What the number *means* is
    entirely yours -- a plot area, a wrap width, a radius, a font size -- and
    `fit` never needs to know, because it only ever compares the measurement it
    asked for against the target it was given:

        panel = inklet.fit(lambda area: scatter_panel(area), width=87)
        card  = inklet.fit(lambda w: inklet.box(inklet.text(body, width=w)), width=52)

    Exactly one of `width` or `height` is the target; a recipe has one knob, so
    constraining both axes would be asking it to solve two equations with it.

    **The target is a budget, not an equation.** Text wraps in whole words and
    an axis ticks in whole steps, so the measurement moves in jumps and most
    targets cannot be hit exactly by any parameter at all. So `fit` returns the
    largest build that still *fits* -- never one that overshoots -- and by
    default pads the remainder symmetrically, so the diagram you get back
    measures the width you asked for and drops into a row beside its siblings.
    Pass `exact=False` for the content's own size, slack and all.

    `guess` is the first parameter tried, and defaults to the target itself,
    which is right whenever the number you are solving for is a length in the
    same direction. A better guess costs fewer builds and nothing else: the
    bracket opens geometrically in whichever direction it needs to.

    Raises `DiagramError` when nothing fits -- when the recipe has a minimum
    size of its own and that minimum is larger than the budget. It reports the
    smallest width it managed, because that number is the actual finding: no
    layout will rescue a legend wider than the column it has to sit in.

    `with_extras=True` is for a recipe that produces more than a diagram --
    the usual case being links, which are declared against the nodes of one
    particular build and are meaningless against another. The builder then
    returns `(diagram, extras)` and `fit` returns `(diagram, extras)` from the
    build it kept, so the two cannot be mismatched:

        panel, leaders = inklet.fit(brain_panel, width=87, with_extras=True)
        fig.add(panel); fig.links(leaders)

    `extras` is whatever you put there -- a list of links, a dict of anchors, a
    measurement the caller wants back. `fit` never looks inside it. Without
    this the loop has to be written out by hand to keep the pairing, which is
    the sixth hand-rolled copy of it this function exists to stop.

    One assumption, and it holds for every real recipe: what `build` returns
    must not get *smaller* as its parameter grows.
    """
    target, axis = _target(width, height)
    tol = mm(tolerance)
    start = target if guess is None else float(guess)
    if start <= 0.0:
        raise DiagramError("fit() needs a positive guess to start from")

    measure = _measured(build, axis, with_extras)
    seen: dict[float, tuple[Diagram, object, float]] = {}

    def look(x: float) -> tuple[Diagram, object, float]:
        if x not in seen:
            seen[x] = measure(x)
        return seen[x]

    low, high = _bracket(look, start, target, tol)
    node, extras, size = look(low)
    # Bisection rather than a secant. The extra builds are cheap next to being
    # wrong: a step function has flat runs where a secant divides by nothing,
    # and this one is asked to land on a particular side of the step.
    for _ in range(tries):
        if high - low <= 1e-9 or target - size <= tol:
            break
        middle = (low + high) / 2.0
        candidate, candidate_extras, measured = look(middle)
        if measured <= target + tol:
            low, node, extras, size = middle, candidate, candidate_extras, measured
        else:
            high = middle
    if exact:
        node = _padded(node, axis, target - size)
    return (node, extras) if with_extras else node


def _target(width: Length | None, height: Length | None) -> tuple[float, str]:
    """The one extent being fitted, in millimetres."""
    if (width is None) == (height is None):
        raise DiagramError(
            "fit() takes width= or height=, not both and not neither: a recipe "
            "has one parameter, so it can satisfy one target")
    axis = "width" if width is not None else "height"
    target = mm(width if width is not None else height)  # type: ignore[arg-type]
    if target <= 0.0:
        raise DiagramError(f"fit() needs a positive {axis}, got {target}")
    return target, axis


def _measured(build: Callable[[float], Diagram], axis: str,
              with_extras: bool) -> Callable[[float], tuple[Diagram, object, float]]:
    """`build`, with its result measured on the axis being fitted.

    Under `with_extras` the builder owes a `(diagram, extras)` pair, and the
    error says so: a recipe that forgot to return its links reports the
    forgotten half rather than failing later on a diagram that is a tuple.
    """
    def measure(x: float) -> tuple[Diagram, object, float]:
        result = build(x)
        extras = None
        if with_extras:
            if not (isinstance(result, tuple) and len(result) == 2):
                raise DiagramError(
                    f"fit(with_extras=True) called its builder with {x:.4g} "
                    f"and got a {type(result).__name__}; under with_extras it "
                    "has to return a (Diagram, extras) pair")
            result, extras = result
        if not isinstance(result, Diagram):
            raise DiagramError(
                f"fit() called its builder with {x:.4g} and got a "
                f"{type(result).__name__}; it has to return a Diagram")
        return result, extras, getattr(result.bbox, axis)
    return measure


def _bracket(look: Callable[[float], tuple[Diagram, object, float]], start: float,
             target: float, tol: float) -> tuple[float, float]:
    """A parameter that fits and one that does not, in that order.

    Halving downward is the half that can fail, and failing here is the useful
    failure: a recipe whose measurement will not come down is a recipe with a
    minimum, and the author needs to hear the minimum rather than watch the
    search grind.
    """
    _, _, size = look(start)
    if size <= target + tol:
        low, high = start, start * _GROWTH
        for _ in range(_SPREAD):
            _, _, grown = look(high)
            if grown > target + tol:
                return low, high
            low, high = high, high * _GROWTH
        # Nothing in four thousand times the guess overshoots: the parameter
        # does not drive this measurement upward, so the first fit is the fit.
        return start, start
    high, low = start, start / _GROWTH
    smallest = size
    for _ in range(_SPREAD):
        _, _, shrunk = look(low)
        smallest = min(smallest, shrunk)
        if shrunk <= target + tol:
            return low, high
        high, low = low, low / _GROWTH
    raise DiagramError(
        f"fit() could not get this below {smallest:.4g}mm, and the target is "
        f"{target:.4g}mm; something in the recipe has a minimum size of its "
        "own -- a legend, an axis name, a word that will not break -- and no "
        "parameter will shrink it further")


def _padded(node: Diagram, axis: str, slack: float) -> Diagram:
    """`node` grown to the exact target, with its anchors carried across.

    Notes come across on their own: `pad` inherits them from its single child
    (core M19), which is what keeps the `plot_area` a row is about to line this
    panel up on. Anchors do not, deliberately -- `as_drawn` reads `node.anchors`
    to tell a placement someone meant from the recentring it undoes -- so they
    are re-registered here, because `fit` is what a panel goes through on the
    way into a row and a row falls back to the `origin` anchor.

    Through `node.transform`, both times. An anchor is written in the node's
    own frame and the wrapper's frame is the one that transform maps *into*;
    copying the raw coordinates put a fitted panel's origin and plot area
    4.2mm from where they are, which is exactly the panel's own recentring
    offset and exactly the misalignment `plot_area` exists to remove.
    """
    if slack <= 1e-9:
        return node
    half = slack / 2.0
    wrapper = (pad(node, 0.0, half) if axis == "width"
               else pad(node, half, 0.0))
    for name, point in node.anchors.items():
        wrapper.anchor(name, node.transform.apply(point))
    return wrapper
