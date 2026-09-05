"""Feature edges and hidden-line removal, checked on shapes with exact answers.

A cube face-on has four silhouette edges. Not "about four", not "four plus the
odd degenerate": exactly four, because the silhouette test is a strict sign
comparison and the two faces sharing a vertical edge disagree exactly. Every
count in this file is an equality for the same reason -- an approximate
assertion here would pass on a renderer that draws the back of a solid through
the front of it, which is the one failure that matters.
"""

from __future__ import annotations

import math
from collections import Counter

import pytest

from inklet.core import Vec2
from inklet.three import (
    BOUNDARY, Camera, CREASE, FeatureEdge, Mesh, SILHOUETTE, Vec3,
    chain_edges, facing_faces, feature_edges, smooth_silhouette, visible_runs,
)
from inklet.three.hlr import polylines
from inklet.three.solids import box, cube, cylinder, plane, sphere


def drawn(mesh, view="front", crease=30.0, width=100.0, cull=None):
    """Run the whole edge pipeline once and hand back every stage of it."""
    resolved = Camera.named(view).frame(mesh, width=width)
    facing = facing_faces(mesh, resolved)
    edges = feature_edges(mesh, resolved, crease_degrees=crease, facing=facing)
    points, depths = resolved.project_all(mesh.vertices)
    runs, occluders = visible_runs(mesh, resolved, edges, points, depths,
                                   facing, cull=cull)
    return resolved, edges, points, runs


def kinds(items):
    return Counter(item.kind for item in items)


# -- silhouettes ----------------------------------------------------------


def test_a_face_on_cube_has_exactly_four_silhouette_edges():
    # Four, not eight. The facing test is `> 0`, with no dead band, so the
    # four edges of the face pointing straight at the camera are *not*
    # silhouette -- both their faces face forward. A tolerance band around
    # zero would classify them as silhouette and draw the square twice.
    _, edges, _, runs = drawn(cube(1.0), "front")
    assert kinds(edges)[SILHOUETTE] == 4
    assert kinds(runs) == {SILHOUETTE: 4}


def test_a_corner_view_of_a_cube_has_exactly_six_silhouette_edges():
    # The hexagonal outline of an isometric cube: three edges from each of the
    # two hidden octants' boundaries.
    for view in ("isometric", "three-quarter"):
        _, edges, _, runs = drawn(cube(1.0), view)
        assert kinds(edges)[SILHOUETTE] == 6, view
        assert kinds(runs)[SILHOUETTE] == 6, view


def test_the_silhouette_of_a_cube_closes_into_one_loop():
    _, edges, _, _ = drawn(cube(1.0), "isometric")
    chains = chain_edges([e.key for e in edges if e.kind == SILHOUETTE])
    assert len(chains) == 1
    vertices, closed = chains[0]
    assert closed and len(vertices) == 6


def test_the_silhouette_of_a_sphere_is_one_closed_ring():
    ball = sphere(0.5, subdivisions=2)
    _, edges, _, _ = drawn(ball, "three-quarter")
    chains = chain_edges([e.key for e in edges if e.kind == SILHOUETTE])
    assert len(chains) == 1 and chains[0][1]


def test_a_smooth_sphere_contributes_no_creases_at_thirty_degrees():
    # Level-2 subdivision bends by well under 30 degrees per edge, so a sphere
    # must draw as an outline and nothing else. If this ever fails the drawing
    # has turned back into a wireframe.
    _, edges, _, _ = drawn(sphere(0.5, subdivisions=2), "three-quarter")
    assert kinds(edges)[CREASE] == 0


# -- creases and boundaries -----------------------------------------------


def test_cube_creases_are_the_edges_that_are_not_silhouette():
    _, edges, _, _ = drawn(cube(1.0), "isometric")
    counted = kinds(edges)
    assert counted[SILHOUETTE] == 6 and counted[CREASE] == 6
    # Twelve real edges and no more: the six triangulation diagonals are flat,
    # so they must not be creases. Interior diagonals showing up here is the
    # classic "why does my box have a line across every face" bug.
    assert sum(counted.values()) == 12


def test_raising_the_crease_threshold_drops_shallower_folds():
    shallow = cylinder(0.4, 1.0, segments=32)
    few = drawn(shallow, "three-quarter", crease=30.0)[1]
    many = drawn(shallow, "three-quarter", crease=5.0)[1]
    assert kinds(many)[CREASE] > kinds(few)[CREASE]


def test_an_open_sheet_reports_its_rim_as_boundary():
    _, edges, _, _ = drawn(plane(1.0, 1.0, segments=2), "three-quarter")
    assert kinds(edges)[BOUNDARY] == 8


def test_a_closed_solid_has_no_boundary_edges():
    _, edges, _, _ = drawn(cube(1.0), "isometric")
    assert kinds(edges)[BOUNDARY] == 0


# -- one line down a fold, not a band -------------------------------------


#: One right-angled corner spread over four facets, steepest in the middle.
#: A real swept section is a superellipse and does the same thing; these are
#: round numbers so the test can name the answer.
_TURNS = (15.0, 25.0, 35.0, 15.0)


def _fanned_ribbon(length=3.0, rings=6):
    """A square tube whose four corners are fans of unequal folds.

    This is the shape the crease threshold has no good answer for: pick
    anything under 35 degrees and all four facets of every corner qualify, so
    a plain threshold inks four near-parallel lines where a pen would draw
    one.
    """
    section, heading, at = [], 0.0, (0.0, 0.0)
    for _ in range(4):
        section.append(at)
        at = (at[0] + math.cos(heading), at[1] + math.sin(heading))
        for turn in _TURNS:
            section.append(at)
            heading += math.radians(turn)
            at = (at[0] + 0.12 * math.cos(heading), at[1] + 0.12 * math.sin(heading))
    across = len(section)
    vertices = [Vec3(x, y, -length / 2 + length * ring / (rings - 1))
                for ring in range(rings) for (x, y) in section]
    faces = []
    for ring in range(rings - 1):
        for i in range(across):
            j = (i + 1) % across
            a, b = ring * across + i, ring * across + j
            c, d = (ring + 1) * across + j, (ring + 1) * across + i
            faces.append((a, b, c))
            faces.append((a, c, d))
    return Mesh(tuple(vertices), tuple(faces))


def _creases_of(mesh, ridges, crease=10.0):
    view = Camera.named("three-quarter").frame(mesh, width=100.0)
    facing = facing_faces(mesh, view)
    edges = feature_edges(mesh, view, crease_degrees=crease, facing=facing,
                          ridges=ridges)
    return view, [edge for edge in edges if edge.kind == CREASE]


def _fold_angle(mesh, edge):
    normals = mesh.face_normals
    one, two = mesh.edge_faces[edge.key]
    return math.degrees(math.acos(min(1.0, max(-1.0,
                                               normals[one].dot(normals[two])))))


def test_a_fan_of_folds_inks_the_steepest_one_and_drops_its_neighbours():
    mesh = _fanned_ribbon()
    _, band = _creases_of(mesh, ridges=False)
    _, line = _creases_of(mesh, ridges=True)
    # Four corners, five bands of quads along the tube, one line each.
    assert len(line) == 4 * 5
    assert len(band) == 70          # every facet of every fan, minus silhouette
    # Not "fewer lines" -- the right lines. Each survivor is the 35-degree
    # facet at the middle of its fan; nothing at 15 or 25 gets through.
    assert {round(_fold_angle(mesh, edge), 6) for edge in line} == {35.0}


def test_suppressing_a_fan_leaves_the_silhouette_and_the_rim_alone():
    mesh = _fanned_ribbon()
    view = Camera.named("three-quarter").frame(mesh, width=100.0)
    facing = facing_faces(mesh, view)
    counts = [kinds(feature_edges(mesh, view, crease_degrees=10.0,
                                  facing=facing, ridges=ridges))
              for ridges in (False, True)]
    for kind in (SILHOUETTE, BOUNDARY):
        assert counts[0][kind] == counts[1][kind] != 0
    assert counts[1][CREASE] < counts[0][CREASE]


def test_a_cube_keeps_all_of_its_edges_because_they_are_all_equal():
    # The suppression is strict: an edge is dropped only by a rival *sharper*
    # than it. Every edge of a cube is a right angle, so no edge beats any
    # other and the ridge rule is a no-op -- which is what stops a rule aimed
    # at rounded corners from quietly eating a box.
    box_ = cube(1.0)
    view = Camera.named("isometric").frame(box_, width=100.0)
    facing = facing_faces(box_, view)
    settings = dict(crease_degrees=30.0, facing=facing)
    assert (feature_edges(box_, view, ridges=True, **settings)
            == feature_edges(box_, view, ridges=False, **settings))


def test_a_fold_only_loses_to_a_rival_running_the_same_way():
    # A cylinder's rim is a ring of sharp edges and its side seams are sharp
    # too when the sampling is coarse, but the two run across each other, so
    # neither suppresses the other: the ring survives whole.
    tube = cylinder(0.5, 1.2, segments=8)
    rim = {key for key, faces in tube.edge_faces.items()
           if len(faces) == 2 and _fold_angle(tube, FeatureEdge(*key, CREASE))
           > 60.0}
    assert len(rim) == 16           # eight segments, two rims
    _, band = _creases_of(tube, ridges=False, crease=30.0)
    _, line = _creases_of(tube, ridges=True, crease=30.0)
    # The seams do shorten the list -- a coarse tube's side seams are 45
    # degrees and they do suppress each other along the length. The rim is
    # untouched, because nothing sharing a face with it runs its way.
    assert len(line) < len(band)
    assert {e.key for e in band} & rim == {e.key for e in line} & rim


# -- hidden-line removal --------------------------------------------------


def test_hlr_hides_every_back_edge_of_a_convex_solid():
    # An isometric cube shows three faces. Nine of its twelve edges bound
    # them; the three meeting at the far corner are behind the solid and must
    # be gone. Six silhouette plus three near creases is the whole drawing.
    _, edges, _, runs = drawn(cube(1.0), "isometric")
    assert kinds(runs) == {SILHOUETTE: 6, CREASE: 3}


def test_the_specific_far_corner_edges_are_the_ones_removed():
    # Not just "three fewer": *these* three. The far corner of an isometric
    # cube is the vertex with the greatest depth, and every edge touching it
    # has to be absent from the surviving runs.
    view, edges, points, runs = drawn(cube(1.0), "isometric")
    depths = [view.project(v).depth for v in cube(1.0).vertices]
    far = max(range(len(depths)), key=depths.__getitem__)
    touching = {i for i, e in enumerate(edges) if far in (e.a, e.b)}
    assert len(touching) == 3
    assert not touching & {r.edge for r in runs}


def test_the_near_corner_edges_all_survive_whole():
    view, edges, points, runs = drawn(cube(1.0), "isometric")
    depths = [view.project(v).depth for v in cube(1.0).vertices]
    near = min(range(len(depths)), key=depths.__getitem__)
    touching = [i for i, e in enumerate(edges) if near in (e.a, e.b)]
    surviving = {r.edge: r for r in runs}
    assert len(touching) == 3
    for index in touching:
        run = surviving[index]
        assert (run.t0, run.t1) == (0.0, 1.0)


def test_a_sphere_in_front_of_a_cube_cuts_the_cubes_edges_in_two_pieces():
    # The partial-occlusion case, which a back-face test alone cannot do: an
    # edge that is neither wholly visible nor wholly hidden has to come back
    # as two runs with a gap between them.
    from inklet.three import Mat4

    bar = box(3.0, 0.1, 0.1)
    blocker = sphere(0.5, 2).transformed(Mat4.translation(Vec3(0.0, -1.0, 0.0)))
    scene = bar.merged(blocker)
    _, edges, _, runs = drawn(scene, "front", cull=False)
    long_edges = [i for i, e in enumerate(edges)
                  if e.kind == SILHOUETTE
                  and abs(scene.vertices[e.a].x - scene.vertices[e.b].x) > 2.0]
    assert len(long_edges) == 2
    for index in long_edges:
        pieces = sorted((r.t0, r.t1) for r in runs if r.edge == index)
        assert len(pieces) == 2, "the sphere should bite a hole out of the bar"
        assert pieces[0][1] < pieces[1][0]


def test_turning_hlr_off_keeps_everything():
    mesh = cube(1.0)
    view = Camera.named("isometric").frame(mesh, width=100.0)
    facing = facing_faces(mesh, view)
    edges = feature_edges(mesh, view, facing=facing)
    assert len(edges) == 12


def test_culling_is_skipped_on_an_open_surface():
    # Back-face culling is exact only on a closed surface. On an open one the
    # inside of a far wall is genuinely visible through the opening, so a mesh
    # that is not closed must not be culled by default.
    bowl = plane(1.0, 1.0, segments=2)
    assert not bowl.is_closed
    _, _, _, runs = drawn(bowl, "three-quarter")
    assert runs


def test_a_hidden_crease_under_a_triangulation_diagonal_stays_hidden():
    # The reason the barycentric containment test is closed rather than
    # strict. In an isometric view of a box, the projected diagonal of a near
    # quad lands exactly on a far edge; with a strictly-interior test the far
    # edge slips between two triangles and gets drawn through the solid.
    _, _, _, runs = drawn(box(1.0, 1.0, 1.0), "isometric")
    assert kinds(runs)[CREASE] == 3


# -- polyline assembly ----------------------------------------------------


def test_polylines_split_by_kind_so_weights_do_not_merge():
    view, edges, points, runs = drawn(cube(1.0), "isometric")
    outline = polylines(edges, runs, points, (SILHOUETTE, BOUNDARY))
    creases = polylines(edges, runs, points, (CREASE,))
    assert len(outline) == 1 and outline[0][1] is True
    assert sum(len(chain) - 1 for chain, _ in creases) == 3


def test_polyline_points_are_the_projected_vertices():
    view, edges, points, runs = drawn(cube(1.0), "isometric", width=40.0)
    outline = polylines(edges, runs, points, (SILHOUETTE,))
    ring = outline[0][0]
    for p in ring:
        assert any(abs(p.x - q.x) < 1e-9 and abs(p.y - q.y) < 1e-9 for q in points)


def test_the_silhouette_ring_is_convex_for_a_convex_solid():
    view, edges, points, runs = drawn(cube(1.0), "isometric", width=40.0)
    ring = polylines(edges, runs, points, (SILHOUETTE,))[0][0]
    signs = []
    for i in range(len(ring)):
        a, b, c = ring[i], ring[(i + 1) % len(ring)], ring[(i + 2) % len(ring)]
        cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
        signs.append(cross > 0)
    assert len(set(signs)) == 1


# -- the spatial index ----------------------------------------------------


def test_the_grid_returns_a_superset_of_the_triangles_a_segment_touches():
    # The grid is an accelerator, never an authority: whatever it hands back is
    # filtered exactly afterwards, so a false positive costs time and nothing
    # else. What it must never do is *miss* a triangle, so its answer is
    # checked against brute-force box overlap for a fan of segments.
    from inklet.three.hlr import Occluders

    mesh = sphere(0.5, 2)
    view = Camera.named("three-quarter").frame(mesh, width=50.0)
    points, depths = view.project_all(mesh.vertices)
    occ = Occluders(mesh, view, points, depths, list(range(len(mesh.faces))))

    for angle in range(0, 360, 17):
        a = math.radians(angle)
        p = Vec2(-30.0 * math.cos(a), -30.0 * math.sin(a))
        q = Vec2(30.0 * math.cos(a), 30.0 * math.sin(a))
        found = set(occ.near(p, q))
        for index, face in enumerate(mesh.faces):
            tri = [points[i] for i in face]
            x0, x1 = min(t.x for t in tri), max(t.x for t in tri)
            y0, y1 = min(t.y for t in tri), max(t.y for t in tri)
            # Does the segment's own box overlap the triangle's? If not, the
            # grid is entitled to skip it; if so, it must not have.
            sx0, sx1 = min(p.x, q.x), max(p.x, q.x)
            sy0, sy1 = min(p.y, q.y), max(p.y, q.y)
            if _crosses(p, q, x0, y0, x1, y1) and sx0 <= x1 and sx1 >= x0 \
                    and sy0 <= y1 and sy1 >= y0:
                assert index in found, (angle, index)


def _crosses(p: Vec2, q: Vec2, x0: float, y0: float, x1: float, y1: float) -> bool:
    """Liang-Barsky, written out again here on purpose: a test that reuses the
    implementation it is checking proves only that the code is consistent."""
    dx, dy = q.x - p.x, q.y - p.y
    lo, hi = 0.0, 1.0
    for delta, room in ((-dx, p.x - x0), (dx, x1 - p.x), (-dy, p.y - y0), (dy, y1 - p.y)):
        if delta == 0.0:
            if room < 0.0:
                return False
            continue
        t = room / delta
        if delta < 0.0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return False
    return True


def test_a_segment_off_the_side_of_the_grid_finds_nothing_and_survives():
    from inklet.three.hlr import Occluders

    mesh = cube(1.0)
    view = Camera.named("front").frame(mesh, width=10.0)
    points, depths = view.project_all(mesh.vertices)
    occ = Occluders(mesh, view, points, depths, list(range(len(mesh.faces))))
    assert occ.near(Vec2(500.0, 500.0), Vec2(600.0, 600.0)) == []


# -- degenerate input -----------------------------------------------------


def test_an_edge_on_triangle_draws_nothing_rather_than_dividing_by_zero():
    sliver = Mesh((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(2, 0, 0)), ((0, 1, 2),))
    view = Camera.named("front").frame(cube(1.0), width=10.0)
    facing = facing_faces(sliver, view)
    edges = feature_edges(sliver, view, facing=facing)
    points, depths = view.project_all(sliver.vertices)
    runs, _ = visible_runs(sliver, view, edges, points, depths, facing, cull=False)
    assert all(math.isfinite(p.x) and math.isfinite(p.y) for p in points)
    assert isinstance(runs, list)


# -- the silhouette of the surface, not of the facets ---------------------


def smoothed(mesh, view="front", crease=180.0, width=100.0, degrees=None):
    """The edge pipeline again, with the smooth pass in the middle of it."""
    resolved = Camera.named(view).frame(mesh, width=width)
    facing = facing_faces(mesh, resolved)
    edges = feature_edges(mesh, resolved, crease_degrees=crease, facing=facing)
    points, depths = resolved.project_all(mesh.vertices)
    kwargs = {} if degrees is None else {"smooth_degrees": degrees}
    return resolved, edges, points, smooth_silhouette(
        mesh, resolved, edges, points, depths, **kwargs)


def ends(edges):
    """How many silhouette ends meet at each point, counted up by how many."""
    meeting = Counter(v for e in edges if e.kind == SILHOUETTE for v in e.key)
    return Counter(meeting.values())


def ink(edges, points):
    return sum((points[e.a] - points[e.b]).length
               for e in edges if e.kind == SILHOUETTE)


def test_the_smooth_silhouette_of_a_sphere_is_one_closed_curve():
    """One segment per triangle it crosses and no more, and they meet end to
    end. That is the property the whole approach is for: the zero set of a
    linear field on a triangle is one segment, so a fan cannot be built out of
    them however nearly tangent the surface gets."""
    ball = sphere(radius=1.0, subdivisions=3)
    _, _, _, result = smoothed(ball)
    curve = [e for e in result.edges if e.kind == SILHOUETTE]
    assert len(curve) == result.interpolated
    # Every crossing is shared by exactly the two triangles either side of the
    # mesh edge it sits on, so a closed curve uses every endpoint twice.
    assert ends(curve) == {2: len(curve)}
    assert len(chain_edges([e.key for e in curve])) == 1


def test_the_smooth_silhouette_lands_where_the_true_one_is():
    """A unit sphere seen from the front has its silhouette on the circle
    x^2 + y^2 = 1. The crossings sit on chords of that circle, so they are
    inside it by at most the sagitta of the mesh's longest edge, and never
    outside it at all."""
    ball = sphere(radius=1.0, subdivisions=3)
    view, _, _, result = smoothed(ball)
    made = {v for edge in result.edges if edge.kind == SILHOUETTE
            for v in edge.key if v >= len(ball.vertices)}
    assert made

    # The projection is a similarity, so the model radius comes straight back
    # off the page.
    radii = sorted(
        math.hypot(result.points[v].x - view.offset.x,
                   result.points[v].y - view.offset.y) / view.scale
        for v in made)
    longest = max((ball.vertices[a] - ball.vertices[b]).length
                  for a, b in ball.edges)
    sagitta = 1.0 - math.sqrt(1.0 - (longest / 2.0) ** 2)
    assert radii[-1] <= 1.0 + 1e-9
    assert radii[0] >= 1.0 - sagitta - 1e-9


def test_a_cube_keeps_its_own_edges_however_the_creases_are_set():
    """The guard that makes reading the crease angle as a statement about the
    geometry safe. `crease=180` says "ink the outline and nothing else", which
    is right for a ribbon and must not be heard as "this box has no corners":
    the smooth pass stops at a right angle whatever it is told."""
    for crease in (30.0, 180.0):
        _, _, _, result = smoothed(cube(1.0), "isometric", crease=crease)
        assert result.interpolated == 0
        assert kinds(result.edges)[SILHOUETTE] == 6


def test_nothing_smooth_enough_leaves_the_feature_edges_exactly_as_they_were():
    """The fallback has to be the identity, not an approximation of it: a mesh
    the pass cannot speak for must come out of it untouched."""
    ball = sphere(radius=1.0, subdivisions=3)
    _, edges, _, result = smoothed(ball, degrees=0.0)
    assert result.interpolated == 0
    assert result.edges == edges


def _corrugated(amplitude, waves):
    """A sphere with a standing wave on it: smooth, and not convex.

    Convexity is what makes a sphere's facet silhouette come out tidy -- facing
    changes once as you go round it, so the edges where it changes form one
    loop. A surface that waves in and out of facing does not have that, and
    that is the case this whole thing is about.
    """
    ball = sphere(radius=1.0, subdivisions=4)
    swelled = tuple(
        v * (1.0 + amplitude
             * math.sin(waves * math.atan2(v.y, v.x))
             * math.sin(waves * math.acos(max(-1.0, min(1.0, v.z)))))
        for v in ball.vertices)
    return Mesh(swelled, ball.faces)


def test_a_wavy_surface_stops_growing_fans_where_it_turns_away():
    """The measurement the whole thing exists for.

    A fan is a *branch*: three or more silhouette ends meeting at one vertex,
    which is what a nearly tangent surface produces when neighbouring facets
    disagree about facing in patches rather than along a line. The smooth
    silhouette cannot branch, because one linear field on one triangle has one
    zero segment -- so the count is not lower, it is zero. A quarter of the ink
    goes with it.
    """
    mesh = _corrugated(0.05, 8)
    _, facets, points, result = smoothed(mesh)

    branching = ends(facets)
    assert sum(n for degree, n in branching.items() if degree > 2) > 0
    assert not [degree for degree in ends(result.edges) if degree > 2]
    assert ink(result.edges, result.points) < 0.85 * ink(facets, points)
