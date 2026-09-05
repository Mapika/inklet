"""A protein cartoon: flat helices, arrowed strands, round coils.

The picture a structural paper shows is not the atoms. It is a ribbon threaded
along the backbone, whose *cross-section* says what the local secondary
structure is -- a wide flat band through a helix, a band with an arrowhead
along a strand, a thin round tube everywhere else. Every molecular viewer draws
it and they all draw it the same way, because the construction goes back to
Carson & Bugg's ribbon paper and nobody has improved on it.

    import inklet

    fold = inklet.cartoon(chain)                       # a Mesh
    panel = inklet.three.model(fold, width=80, view="three-quarter",
                            colors={"helix": "#c0504d", "strand": "#4f81bd"})

**What this reads.** Not a file format, and not one parser's classes. A
*residue* here is anything carrying an alpha carbon, a secondary-structure
letter and a number (`Residue` below); a *chain* is anything that can split
itself where the crystal lost it (`Chain`). `figures/pdbfile.py` in this
repository is one such reader in 180 lines, and a caller whose coordinates
come from somewhere else -- a simulation frame, an mmCIF library, a predicted
model -- owes this module three attributes rather than a conversion.

Four things have to be right or the result looks broken in a way that is hard
to diagnose from the picture:

**The trace has to be smoothed, and the frames must not be.** An alpha helix's
alpha carbons lie on a spiral of about 2.3 A radius; a ribbon threaded through
them is a corkscrew, not a helix. Averaging each point with its neighbours a
few times collapses the spiral onto the axis. But the *orientation* of the
ribbon is read off the raw geometry -- once smoothed, three consecutive points
are nearly collinear and the cross product that gives the frame is noise.

**The frame flips every residue in a strand and has to be flipped back.** The
pleat of a beta strand alternates, so the vector normal to three consecutive
alpha carbons points one way at residue i and the other way at i+1. Taken at
face value the ribbon makes a half turn per residue and comes out shredded.
Every frame is compared with the one before it and negated if they disagree.

**The chain breaks.** Residues either side of a disordered stretch are twenty
angstroms apart, and a spline through them draws a girder across the middle of
the fold -- a line with no evidence behind it, in the one kind of figure whose
whole claim is that it shows measured coordinates. That is what `Chain`
exists for: `cartoon()` draws one ribbon per continuous run and never joins
two of them.

**The section has to keep its point count.** A swept surface joins point k of
one ring to point k of the next, so the round coil, the flat helix and the
flaring arrowhead are all the same superellipse at different widths, and the
transitions between them are that superellipse's parameters interpolated.

And one thing about drawing it rather than building it: **the crease
threshold has to clear the sampling.** A ribbon's edge is a rounded corner
spread over several facets whose dihedrals run from twenty degrees to ninety,
so a threshold inside that range would once ink a band of near parallel lines
down both edges of every ribbon, which hidden-line removal then chopped into
short strokes until the protein came out hatched. `inklet.three.model` suppresses
all but the steepest edge across such a fan now, so the band is gone; what is
left to get right is the number. Below `360 / SIDES` the coil's own
longitudinal seams are sharper than the threshold and get inked, so a section
sampled at 13 points wants something like `crease=45`, comfortably above the
twenty-eight degrees the facets meet at and comfortably below the corner.

The same `360 / SIDES` shows up in the shading, and there it is the argument
for `shading="smooth"`. A coil sampled at 13 points is thirteen flat strips,
and flat shading paints all thirteen; no number of tone `levels` helps,
because the tone is constant across a facet by construction. Cutting the bands
out of the surface instead is the only thing that makes a tube read as round
at a sampling chosen for its outline.

Nothing here knows what a diagram is. It reads coordinates and returns a
`Mesh`, which `inklet.three.model` then draws.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .linalg import Vec3
from .mesh import Mesh, merge
from .solids import sweep

__all__ = ["HELIX", "STRAND", "COIL", "SECTIONS", "NAMES", "SIDES", "STEPS",
           "SMOOTHING", "ARROW_FLARE", "ARROW_POINT", "ARROW_MINIMUM",
           "Chain", "Residue", "Station", "cartoon", "ribbon", "sides_for",
           "stations", "steps_for"]

#: Secondary structure, one letter each, as everyone from DSSP down spells it.
#: These are the values `Residue.structure` is read for, and the keys of
#: `SECTIONS`, `SMOOTHING` and `NAMES`.
HELIX, STRAND, COIL = "H", "E", "C"


@runtime_checkable
class Residue(Protocol):
    """One residue, as this module needs it: a point, a letter and a number.

    A protocol rather than a class, because the coordinates come from
    somewhere else by definition -- a PDB or mmCIF reader, a trajectory frame,
    a predicted model -- and a library that insisted on its own residue type
    would make every caller convert one dataclass into another. Anything with
    these three attributes draws.

    `runtime_checkable` so the door checks below can say *which* attribute is
    missing rather than failing four frames down in the frame maths. That only
    tests for the attributes' presence, which is exactly the claim being made.
    """

    #: The alpha carbon, in angstroms. `None` for a residue the crystal placed
    #: no backbone for; `Chain.segments()` is what drops those.
    ca: Vec3 | None
    #: One of `HELIX`, `STRAND`, `COIL`.
    structure: str
    #: The number the deposited entry gives it. Used to name the mesh part, so
    #: a caller can find one segment again in `inklet.three.parts_of`.
    number: int


@runtime_checkable
class Chain(Protocol):
    """A whole chain, which knows where it is broken."""

    def segments(self) -> Sequence[Sequence[Residue]]:
        """The chain split into continuous runs, in sequence order."""


# --- how thick the ribbon is, in angstroms ---------------------------------
#: (half-width, half-thickness, superellipse exponent) per structure type. The
#: exponent is what makes a section rectangular rather than elliptical: 2 is an
#: ellipse, and by 5 the corners are tight enough to read as a flat band with
#: rounded edges, which is what a helix should look like edge-on.
SECTIONS = {
    HELIX:  (1.32, 0.22, 5.0),
    STRAND: (1.10, 0.20, 5.0),
    COIL:   (0.26, 0.26, 2.0),
}
#: How wide the arrow's shoulders are, as a multiple of the strand's own
#: half-width, and how narrow its point is. A strand shorter than this many
#: residues gets no arrow: there is no room for a shoulder and a point, and
#: what comes out is a dart rather than a strand.
ARROW_FLARE, ARROW_POINT, ARROW_MINIMUM = 1.75, 0.12, 3

#: Points around a cross-section, and the floor under `sides_for`.
#:
#: A floor rather than the answer, because how round the outline needs to be
#: depends on how big the drawing is and this does not: the section is a
#: superellipse with four corners and four flats, and below about a dozen
#: points the corners get fewer than two points each. The rounding stops being
#: a rounding, the coil reads as a square bar, and no amount of shrinking the
#: panel makes that acceptable. Same argument as `ROUND_FLOOR` in
#: `inklet.three.solids`, one step up because a flattened section spends its
#: points unevenly.
#:
#: It used to be twenty, and the reason was the *silhouette*: a ribbon doubles
#: back constantly, so large stretches of it are nearly tangent to the view,
#: and the outline the renderer drew there was a zig-zag through the facets
#: that grew a black fan across every helix end below about sixteen points.
#: The renderer now puts the outline on the surface the facets stand for
#: rather than on the facets -- `inklet.three.model(smooth=)` -- so that floor is
#: gone and the count is back to being a question about the section alone.
SIDES = 12
#: Cross-sections per residue along the spline, and the ceiling under
#: `steps_for`. Six keeps the facet length comparable to its width, so the
#: shading bands run across the ribbon rather than stretching into stripes
#: down it.
#:
#: A ceiling rather than the answer for the same reason `SIDES` is a floor:
#: six is what the *tightest* stretch of chain needs, and most of a fold is
#: not that. A helix turns fifty degrees a residue and its band twists with
#: it; a beta strand, smoothed twice, is very nearly a straight rail, and
#: sampling it six times a residue buys nothing but facets. `steps_for` spends
#: the difference.
STEPS = 6

#: Passes of neighbour-averaging on the alpha-carbon trace, per structure type.
#:
#: One pass for a helix, not four. Smoothing a helix hard collapses its spiral
#: onto its axis, and the ribbon that results is *worse*, not cleaner: the
#: frame keeps turning about the axis at fifty degrees a residue, so a band
#: threaded along a straight line comes out as a length of twisted tape. A
#: cartoon helix is meant to stay a spiral -- the coils are how a reader counts
#: the turns -- so the path keeps its radius and only the crystallographic
#: jitter is averaged out.
#:
#: Two for a strand, to take out the pleat. None for a coil: its wandering
#: *is* the shape, and smoothing it away turns a distinctive loop into a piece
#: of bent wire.
SMOOTHING = {HELIX: 1, STRAND: 2, COIL: 0}

#: What a face's group is called, which is what `colors=` is keyed on.
NAMES = {HELIX: "helix", STRAND: "strand", COIL: "coil"}


@dataclass(frozen=True, slots=True)
class Station:
    """One cross-section's worth of frame: where, and which way is across."""

    point: Vec3
    across: Vec3         # along the ribbon's width
    face: Vec3           # out of the ribbon's flat face
    structure: str
    #: Multiplies the section's half-width. 1 everywhere but an arrowhead.
    flare: float = 1.0


def _check_residues(what: str, residues) -> None:
    """Refuse anything that is not a run of drawable residues, at the door.

    Four mistakes -- a whole chain where a run goes, an object that is not a
    residue, a residue the crystal placed no backbone for, and a
    secondary-structure letter this module has no section for. Each of them is
    otherwise a `KeyError`, a `TypeError` on `None` or an `AttributeError`
    several frames down in the frame maths, naming neither the call nor the
    residue that caused it. Same reasoning as `_check_string`
    in `inklet`: the argument is the author's, so the message should be too.
    """
    if isinstance(residues, Chain):
        raise TypeError(
            f"{what}() takes one continuous run of residues, not a whole "
            f"chain: cartoon(chain) draws every run, or pass "
            f"chain.segments()[0] for the first")
    for index, residue in enumerate(residues):
        if not isinstance(residue, Residue):
            missing = [name for name in ("ca", "structure", "number")
                       if not hasattr(residue, name)]
            raise TypeError(
                f"{what}() got {type(residue).__name__} at position {index}, "
                f"which is missing {', '.join(missing)}; a residue needs "
                f"ca, structure and number")
        if residue.ca is None:
            raise ValueError(
                f"{what}() got residue {residue.number} with no alpha "
                f"carbon, and a cartoon is threaded through the alpha "
                f"carbons; chain.segments() drops the residues that have "
                f"none")
        if residue.structure not in SECTIONS:
            raise ValueError(
                f"{what}() got residue {residue.number} with structure "
                f"{residue.structure!r}; it has to be one of "
                f"{HELIX!r} (helix), {STRAND!r} (strand) or {COIL!r} (coil)")


def _smoothed(points: Sequence[Vec3], kinds: Sequence[str]) -> list[Vec3]:
    """Neighbour-average each point as many times as its structure asks for.

    Per-residue rather than per-pass so that a helix can be unwound without
    also straightening the loop it runs into. The endpoints of the segment
    never move: they are where the ribbon has to start and stop.
    """
    out = list(points)
    for _ in range(max(SMOOTHING.values())):
        nxt = list(out)
        for i in range(1, len(out) - 1):
            if SMOOTHING[kinds[i]] > _:
                nxt[i] = (out[i - 1] + out[i] * 2.0 + out[i + 1]) * 0.25
        out = nxt
    return out


def _frames(raw: Sequence[Vec3]) -> list[tuple[Vec3, Vec3]]:
    """(across, face) per residue, from the *unsmoothed* trace.

    `across` is normal to the plane of three consecutive alpha carbons, which
    is along the width of the ribbon for both a helix and a strand; `face` is
    what is left of the frame. Each is negated when it disagrees with the one
    before, which is the flip correction a strand's alternating pleat needs.
    """
    out: list[tuple[Vec3, Vec3]] = []
    previous = Vec3(0.0, 0.0, 1.0)
    for i in range(len(raw)):
        before = raw[max(i - 1, 0)]
        after = raw[min(i + 1, len(raw) - 1)]
        along = after - before
        if along.length < 1e-9:
            along = Vec3(0.0, 0.0, 1.0)
        along = along.normalized()
        across = (raw[min(i + 1, len(raw) - 1)] - raw[i]).cross(
            raw[max(i - 1, 0)] - raw[i])
        if across.length < 1e-6:                 # collinear: any perpendicular
            across = along.cross(Vec3(0.0, 0.0, 1.0))
            if across.length < 1e-6:
                across = along.cross(Vec3(1.0, 0.0, 0.0))
        across = across.normalized()
        if across.dot(previous) < 0.0:
            across = across * -1.0
        previous = across
        across = (across - along * across.dot(along))
        across = across.normalized() if across.length > 1e-9 else previous
        out.append((across, along.cross(across).normalized()))
    return out


def _flares(kinds: Sequence[str]) -> list[float]:
    """The half-width multiplier per residue: the arrowhead on each strand.

    A strand ends in an arrow that says which way the chain runs, and it is the
    only part of a cartoon that carries direction -- N to C, the direction the
    sequence is written in. The last residue is the point and the one before it
    is the shoulder, so the widening reads as a step rather than a taper.
    """
    out = [1.0] * len(kinds)
    for i, kind in enumerate(kinds):
        if kind != STRAND or (i + 1 < len(kinds)
                              and kinds[i + 1] == STRAND):
            continue
        run = 0
        while i - run >= 0 and kinds[i - run] == STRAND:
            run += 1
        if run < ARROW_MINIMUM:
            continue
        out[i], out[i - 1] = ARROW_POINT, ARROW_FLARE
    return out


def stations(residues: Sequence[Residue]) -> list[Station]:
    """One frame per residue of a continuous segment.

    The geometry `ribbon()` sweeps, before any sampling decision is taken:
    where each cross-section sits and which way is across it. Public because
    a figure that wants to hang a label off the ribbon needs the same frame
    the ribbon was built from, and recomputing it from the mesh is guesswork.
    """
    _check_residues("stations", residues)
    raw = [residue.ca for residue in residues]
    kinds = [residue.structure for residue in residues]
    smooth = _smoothed(raw, kinds)
    flares = _flares(kinds)
    return [Station(point, across, face, kind, flare)
            for point, (across, face), kind, flare
            in zip(smooth, _frames(raw), kinds, flares)]


def _catmull(a: Vec3, b: Vec3, c: Vec3, d: Vec3, t: float) -> Vec3:
    """The Catmull-Rom point between b and c. Passes through every guide point,
    which is the property that matters here: the ribbon has to touch the alpha
    carbons it claims to trace, not merely approach them."""
    t2, t3 = t * t, t * t * t
    return ((b * 2.0) + (c - a) * t
            + (a * 2.0 - b * 5.0 + c * 4.0 - d) * t2
            + (b * 3.0 - a - c * 3.0 + d) * t3) * 0.5


def _frame_at(one: Station, two: Station, t: float) -> tuple[Vec3, Vec3]:
    """Blend two residues' frames and re-square them to each other.

    Straight interpolation of the two axes shortens them and lets them drift
    out of square; for the fraction of a turn between adjacent residues that is
    cheaper and no worse-looking than a proper rotation interpolation.

    Squaring the ring to the *spline's* tangent instead is the obvious
    improvement and it is worse. On a helix the frame's wide axis lies along
    the helix axis and so does much of the tangent; subtracting the parallel
    part leaves a short, noisy remainder, and the ribbon pinches to a point
    once a turn. Rendered side by side the difference is not subtle. The frames
    already agree with the path at every residue, which is where it matters.
    """
    across = one.across * (1.0 - t) + two.across * t
    face = one.face * (1.0 - t) + two.face * t
    if across.length < 1e-9:
        across = one.across
    across = across.normalized()
    face = face - across * face.dot(across)
    return across, (face.normalized() if face.length > 1e-9 else one.face)


def _blend(one: str, two: str, t: float) -> tuple[float, float, float]:
    """The section's parameters between two structure types.

    Interpolating the *shape* rather than cutting from one to the other is what
    keeps the ribbon a single continuous surface: a helix does not end in a
    cliff, it narrows into the coil that follows it over about a residue.
    """
    a, b = SECTIONS[one], SECTIONS[two]
    return tuple(x * (1.0 - t) + y * t for x, y in zip(a, b))


def _section(angle: float, half_width: float, half_thick: float,
             power: float) -> tuple[float, float]:
    """One point of the superellipse, in the frame's own (across, face) plane.

    Split out of `_ring` so that `sides_for` can walk the same curve the sweep
    is going to be built from. A tolerance measured against a different
    parameterisation than the one that gets drawn is a tolerance measured
    against nothing.
    """
    cos, sin = math.cos(angle), math.sin(angle)
    return (math.copysign(abs(cos) ** (2.0 / power), cos) * half_width,
            math.copysign(abs(sin) ** (2.0 / power), sin) * half_thick)


def _ring(point: Vec3, across: Vec3, face: Vec3, half_width: float,
          half_thick: float, power: float, sides: int) -> list[Vec3]:
    """`sides` points round a superellipse in the frame's plane."""
    out = []
    for k in range(sides):
        u, v = _section(2.0 * math.pi * k / sides,
                        half_width, half_thick, power)
        out.append(point + across * u + face * v)
    return out


def _span(guides: Sequence[Vec3], i: int, last: int) -> tuple[Vec3, ...]:
    """The four guide points Catmull-Rom needs to draw the i-th span."""
    return (guides[max(i - 1, 0)], guides[i], guides[i + 1],
            guides[min(i + 2, last)])


def _at(marks: Sequence[Station], guides: Sequence[Vec3], i: int,
        t: float) -> tuple[Vec3, Vec3, Vec3, float, float, float]:
    """Everything one cross-section of span `i` is built from, at fraction `t`.

    Split out of `ribbon` for the same reason `_section` is split out of
    `_ring`: `steps_for` has to walk the surface the sweep is going to be
    built from, and a tolerance measured against a paraphrase of that surface
    is a tolerance measured against nothing.
    """
    across, face = _frame_at(marks[i], marks[i + 1], t)
    half_width, half_thick, power = _blend(
        marks[i].structure, marks[i + 1].structure, t)
    flare = marks[i].flare * (1.0 - t) + marks[i + 1].flare * t
    return (_catmull(*_span(guides, i, len(marks) - 1), t), across, face,
            half_width * flare, half_thick, power)


#: Points sampled inside each span when measuring how far the drawn polygon
#: departs from the section it stands for. The maximum is near the middle of a
#: span but not at it -- the superellipse's parameterisation is uneven, and at
#: power 5 it crowds samples toward the flats -- so the span is swept rather
#: than probed once. Fifteen agrees with a 4000-point sweep to four decimals.
_PROBES = 15


def _departure(sides: int, half_width: float, half_thick: float,
               power: float) -> float:
    """The furthest the true section gets from the polygon through its samples.

    In angstroms, like everything else here. Perpendicular distance to the
    chord rather than to the whole polygon: inside one span that is the same
    number, and it does not need the polygon assembled to compute.
    """
    worst = 0.0
    for k in range(sides):
        start, stop = 2.0 * math.pi * k / sides, 2.0 * math.pi * (k + 1) / sides
        x0, y0 = _section(start, half_width, half_thick, power)
        x1, y1 = _section(stop, half_width, half_thick, power)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0.0:
            continue
        for i in range(1, _PROBES + 1):
            angle = start + (stop - start) * i / (_PROBES + 1)
            px, py = _section(angle, half_width, half_thick, power)
            worst = max(worst, abs((px - x0) * dy - (py - y0) * dx) / length)
    return worst


def _check_bounds(what: str, floor: int, ceiling: int) -> None:
    """A search whose floor is above its ceiling silently returns the ceiling,
    which is a smaller number than the caller asked to be guaranteed. Say so
    instead: it is always a typo, never a request."""
    if floor > ceiling:
        raise ValueError(
            f"{what}() got floor={floor} above ceiling={ceiling}, so there is "
            f"nothing it may answer; raise the ceiling or lower the floor")


def sides_for(scale: float, tolerance: float = 0.06, *,
              floor: int = SIDES, ceiling: int = 64) -> int:
    """Points round a cross-section, chosen for the size it will be drawn at.

    `scale` is millimetres per angstrom -- `inklet.three.page_scale(mesh,
    width=..., view=...)` -- and `tolerance` is how far the drawn ribbon may
    sit from the section it stands for, in millimetres on the page. The answer
    is the smallest count that keeps *every* section type inside it, because
    one sweep carries all three and they share a point count by construction.

    This is the swept-surface half of what `inklet.three.solid` does for itself.
    A parametric solid knows its own formula, so the engine can pick its
    segment counts; a sweep is handed its cross-sections already built, so the
    only thing the engine can offer is the scale, and the arithmetic belongs
    next to the curve it is about.

    The floor is `SIDES`, which is about the shape of the section rather than
    about the page; raising it is how a caller states a stricter one. A
    `scale` or `tolerance` of zero or less is read as "no licence to coarsen"
    and answers the ceiling.
    """
    _check_bounds("sides_for", floor, ceiling)
    if scale <= 0.0 or tolerance <= 0.0:
        return ceiling
    for sides in range(max(floor, 3), ceiling):
        if all(_departure(sides, *section) * scale <= tolerance
               for section in SECTIONS.values()):
            return sides
    return ceiling


#: Points sampled inside each chord when measuring the sag along the ribbon.
#: Half of `_PROBES`, because a Catmull-Rom span has none of the superellipse's
#: crowding -- its parameterisation is even enough that seven samples find the
#: same maximum fifteen do, to three decimals, on every span of 1M17.
_SAG_PROBES = 7


def _rails(marks: Sequence[Station], guides: Sequence[Vec3], i: int,
           t: float) -> tuple[Vec3, Vec3, Vec3]:
    """The centre of a cross-section and the two edges of the band, at `t`.

    Three curves and not one, because a ribbon can be badly sampled two
    different ways. The centre line says the *path* is under-sampled -- a
    helix cutting corners off its own spiral. The two edges also say the
    *frame* is: where the band twists, its rails swing about a centre that is
    barely moving, and a chord across half a turn of that flattens the twist
    into a crease. The edges are where a reader sees it, so the edges are what
    the tolerance is asked about.
    """
    point, across, _face, half_width, _thick, _power = _at(marks, guides, i, t)
    return point, point + across * half_width, point - across * half_width


def _sag(marks: Sequence[Station], guides: Sequence[Vec3], i: int,
         steps: int) -> float:
    """The furthest span `i`'s rails get from the chords drawn for them.

    In angstroms. Along the ribbon what `_departure` is across it, and
    measured the same way: perpendicular distance to the chord, swept rather
    than probed once.
    """
    worst = 0.0
    for k in range(steps):
        start, stop = k / steps, (k + 1) / steps
        first = _rails(marks, guides, i, start)
        last = _rails(marks, guides, i, stop)
        for rail in range(3):
            along = last[rail] - first[rail]
            if along.length < 1e-9:
                continue
            for probe in range(1, _SAG_PROBES + 1):
                t = start + (stop - start) * probe / (_SAG_PROBES + 1)
                here = _rails(marks, guides, i, t)[rail]
                worst = max(worst,
                            (here - first[rail]).cross(along).length
                            / along.length)
    return worst


def steps_for(residues: Sequence[Residue], scale: float,
              tolerance: float = 0.06, *, floor: int = 1,
              ceiling: int = STEPS) -> list[int]:
    """Cross-sections per span of chain, chosen for the size it is drawn at.

    `sides_for` along the ribbon instead of across it: same `scale` in
    millimetres per angstrom, same `tolerance` in millimetres on the page, and
    the answer is again the coarsest sampling that stays inside it. One count
    per span -- `len(residues) - 1` of them, ready to hand to `ribbon(steps=)`
    -- because the two ends of a fold do not need the same sampling and giving
    them the same one is the whole cost being complained about.

    **What this buys is the exact depth sort.** A ribbon costs `spans * steps *
    sides * 2` facets, plus a cap at each end, and above
    `inklet.three.AUTO_EXACT_FACETS` the renderer
    orders facets by mean depth rather than comparing the pairs that overlap.
    The EGFR kinase domain at six steps everywhere is 38,952 of them and gets
    the approximation; the same fold sampled to a tolerance the page can see
    fits under the ceiling, and a whole domain can be ordered the way a
    close-up is.

    Six is the ceiling and one the floor, and the floor is real: below one
    cross-section per residue the ribbon would stop touching the alpha carbons
    it claims to trace, which is the one property `_catmull` was chosen for.

    **Ask for less here than you would of `sides_for`.** The default matches
    it, at 0.06 mm, and the two numbers are not worth the same: a section's
    departure from its polygon is hidden inside a shaded surface, and a
    spline's departure from its chords lands on the **silhouette**, where a
    two-dimensional corner is about the most legible thing a drawing has. On
    the EGFR domain at 1.85 mm/A the section is comfortable at 0.11 mm and the
    chain is visibly cornered there; 0.04 is the figure that holds. See the
    table beside `TOLERANCE` in `figures/structure.py` for what that cost and
    why that panel went back to six.

    Costs about 0.9 s on a 271-residue domain: the search runs upward from the
    floor and re-probes the span at each candidate. Fine once per figure, and
    the caller usually wants `functools.cache` round whatever builds the mesh.
    """
    _check_bounds("steps_for", floor, ceiling)
    marks = stations(residues)
    if len(marks) < 2:
        return []
    guides = [mark.point for mark in marks]
    if scale <= 0.0 or tolerance <= 0.0:
        return [ceiling] * (len(marks) - 1)
    out = []
    for i in range(len(marks) - 1):
        chosen = ceiling
        for steps in range(max(floor, 1), ceiling):
            if _sag(marks, guides, i, steps) * scale <= tolerance:
                chosen = steps
                break
        out.append(chosen)
    return out


def ribbon(residues: Sequence[Residue], *, name: str = "ribbon",
           group: str | None = None, sides: int = SIDES,
           steps: int | Sequence[int] = STEPS) -> Mesh:
    """The cartoon for one continuous run of residues.

    Faces are grouped by secondary structure -- `"helix"`, `"strand"`,
    `"coil"` -- unless `group` overrides it, so one mesh can be painted in
    three colours by `inklet.three.model(colors=...)` while still being sorted for
    depth a facet at a time.

    `steps` is cross-sections per span, either one number for the whole run or
    one per span -- `steps_for(residues, scale, tolerance)` builds the list.

    A run of fewer than two residues has no span to sweep and returns an empty
    mesh, which merges away: that is the answer a chain with a one-residue
    fragment in it needs, not an exception.
    """
    _check_residues("ribbon", residues)
    if sides < 3:
        raise ValueError(
            f"ribbon() needs at least three points round a cross-section, "
            f"and sides={sides} does not make a surface; SIDES is {SIDES}")
    marks = stations(residues)
    if len(marks) < 2:
        return Mesh((), ())
    guides = [mark.point for mark in marks]
    rings: list[list[Vec3]] = []
    names: list[str] = []
    last = len(marks) - 1
    counts = [steps] * last if isinstance(steps, int) else list(steps)
    if len(counts) != last:
        raise ValueError(
            f"ribbon() got {len(counts)} step counts for {last} spans; "
            f"steps_for() returns one per span")
    if min(counts) < 1:
        raise ValueError("ribbon() needs at least one cross-section a span: "
                         "below that the ribbon stops touching its alpha "
                         f"carbons, and steps={min(counts)} does not")
    for i in range(last):
        for step in range(counts[i]):
            point, across, face, half_width, half_thick, power = _at(
                marks, guides, i, step / counts[i])
            rings.append(_ring(point, across, face,
                               half_width, half_thick, power, sides))
            names.append(group or NAMES[marks[i].structure])
    across, face = marks[last].across, marks[last].face
    half_width, half_thick, power = SECTIONS[marks[last].structure]
    rings.append(_ring(guides[last], across, face,
                       half_width * marks[last].flare, half_thick, power,
                       sides))
    names.append(group or NAMES[marks[last].structure])
    return sweep(rings, groups=names, name=name)


def cartoon(chain: Chain, *, name: str = "cartoon", group: str | None = None,
            sides: int = SIDES, steps: int = STEPS) -> Mesh:
    """The whole chain: one ribbon per continuous segment, merged.

    Merged rather than left as separate parts because the segments interleave
    in space -- the two lobes of a kinase fold past each other -- and separate
    parts are depth-sorted as wholes. One mesh is sorted a facet at a time.

    Each segment keeps its own group name, `f"{name}-{first residue number}"`,
    so `inklet.three.parts_of` can still find one run of the chain again.
    """
    segments = getattr(chain, "segments", None)
    if not callable(segments):
        raise TypeError(
            f"cartoon() takes a chain that can split itself at its breaks, "
            f"and {type(chain).__name__} has no segments(); pass "
            f"ribbon(residues) for one continuous run")
    return merge(ribbon(run, name=f"{name}-{run[0].number}", group=group,
                        sides=sides, steps=steps)
                 for run in segments() if len(run) > 1)
