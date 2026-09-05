"""The protein cartoon as a library API, drawn from residues nobody parsed.

`inklet.three.protein` used to be `figures/cartoon.py`, and the promotion is only
worth anything if the geometry no longer knows where the coordinates came
from. So the residues below are a dataclass declared in this file: no PDB
file, no `figures/` on `sys.path`, no reader of any kind. If these pass, a
caller with coordinates out of a trajectory, an mmCIF library or a predicted
model can draw a cartoon of them.

The numbers the ribbon actually produces are pinned by
`tests/test_structure_figure.py` against the real 1M17 fold; what is pinned
here is the contract -- the protocol, the group names, the arithmetic that
relates spans and steps and sides to facets, and every door check.
"""

from __future__ import annotations

import ast
import math
import pathlib
from dataclasses import dataclass, field

import pytest

import inklet
from inklet.three import Vec3
from inklet.three import protein
from inklet.three.protein import COIL, HELIX, STRAND


@dataclass(frozen=True)
class Res:
    """A residue this library has never heard of, satisfying the protocol."""

    number: int
    structure: str
    ca: Vec3 | None


@dataclass(frozen=True)
class Chain:
    """A chain this library has never heard of, satisfying the protocol."""

    residues: tuple[Res, ...]
    breaks: tuple[int, ...] = field(default=())

    def segments(self) -> list[list[Res]]:
        runs: list[list[Res]] = [[]]
        for residue in self.residues:
            if residue.number in self.breaks and runs[-1]:
                runs.append([])
            runs[-1].append(residue)
        return [run for run in runs if run]


def helix(first: int, count: int, *, z: float = 0.0) -> list[Res]:
    """An idealised alpha helix: 2.3 A radius, 1.5 A rise, 100 deg a residue.
    Real enough that the smoothing and the frame flip both have work to do."""
    out = []
    for i in range(count):
        angle = math.radians(100.0 * i)
        out.append(Res(first + i, HELIX,
                       Vec3(2.3 * math.cos(angle), 2.3 * math.sin(angle),
                            z + 1.5 * i)))
    return out


def strand(first: int, count: int, *, z: float = 0.0) -> list[Res]:
    """A pleated beta strand: 3.3 A along, alternating half an angstrom
    sideways, which is the pleat whose frame flips every residue."""
    return [Res(first + i, STRAND,
                Vec3(3.3 * i, 0.5 * (-1) ** i, z))
            for i in range(count)]


def coil(first: int, count: int, *, z: float = 0.0) -> list[Res]:
    return [Res(first + i, COIL, Vec3(3.8 * i, 2.0 * i, z))
            for i in range(count)]


def a_run() -> list[Res]:
    """Helix into coil into strand: all three sections and both transitions."""
    return helix(1, 8) + coil(9, 3, z=12.0) + strand(12, 6, z=20.0)


# --- the promotion -------------------------------------------------------

def test_the_cartoon_is_reachable_by_its_public_spellings():
    assert inklet.cartoon is protein.cartoon
    assert inklet.three.ribbon is protein.ribbon
    assert "cartoon" in inklet.__all__ and "ribbon" in inklet.three.__all__


def test_the_library_module_imports_nothing_from_figures():
    """The whole point of the move. `figures/pdbfile.py` is a reader that
    happens to live in this repository; the geometry may not depend on it, and
    a docstring that names it as an example is not a dependency -- so this
    reads the import statements rather than the text."""
    source = pathlib.Path(protein.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * node.level + (node.module or ""))

    assert imported == {"__future__", "math", "dataclasses", "typing",
                        ".linalg", ".mesh", ".solids"}


def test_a_foreign_residue_type_draws():
    mesh = protein.ribbon(a_run(), sides=protein.SIDES, steps=2)

    assert len(mesh.faces) > 0
    assert mesh.group_names == ("coil", "helix", "strand")


def test_the_facet_count_is_spans_times_steps_times_sides():
    """`spans * steps * sides * 2`, plus a cap at each end of the run. The
    same identity `test_structure_figure` asserts on the real fold, kept here
    so a change to the sweep is caught without a 271-residue render."""
    run = a_run()
    spans, sides = len(run) - 1, 10
    for steps in (1, 3, 6):
        mesh = protein.ribbon(run, sides=sides, steps=steps)
        assert len(mesh.faces) == spans * steps * sides * 2 + 2 * sides


def test_one_count_per_span_matches_the_same_count_everywhere():
    run = a_run()
    per_span = [4] * (len(run) - 1)

    assert (protein.ribbon(run, steps=per_span).vertices
            == protein.ribbon(run, steps=4).vertices)


def test_group_overrides_the_secondary_structure():
    mesh = protein.ribbon(a_run(), group="n-lobe", steps=1)

    assert mesh.group_names == ("n-lobe",)


# --- the chain -----------------------------------------------------------

def test_a_chain_is_drawn_one_run_per_segment_and_never_across_a_break():
    """A spline through a disordered stretch draws a girder across the fold.
    Two runs means two sweeps, so the vertex count is the sum of the parts and
    not the count of one ribbon through everything."""
    residues = tuple(helix(1, 8) + helix(20, 8, z=40.0))
    chain = Chain(residues, breaks=(20,))

    whole = protein.cartoon(chain, steps=2)
    parts = [protein.ribbon(run, steps=2) for run in chain.segments()]

    assert len(whole.vertices) == sum(len(part.vertices) for part in parts)
    assert len(whole.faces) == sum(len(part.faces) for part in parts)


def test_a_one_residue_fragment_is_dropped_rather_than_raising():
    chain = Chain(tuple(helix(1, 6) + [Res(30, COIL, Vec3(0.0, 0.0, 90.0))]),
                  breaks=(30,))

    assert len(protein.cartoon(chain).faces) == len(
        protein.ribbon(chain.segments()[0]).faces)


def test_a_run_too_short_to_sweep_is_an_empty_mesh():
    assert protein.ribbon([]).faces == ()
    assert protein.ribbon(helix(1, 1)).faces == ()


# --- the sampling knobs --------------------------------------------------

def test_sides_for_is_monotone_in_the_page_scale():
    assert (protein.sides_for(20.0) > protein.sides_for(10.0)
            >= protein.SIDES)
    assert protein.sides_for(0.0) == 64            # no scale: no licence


def test_steps_for_answers_once_per_span_inside_its_bounds():
    run = a_run()
    counts = protein.steps_for(run, 1.85, 0.11)

    assert len(counts) == len(run) - 1
    assert all(1 <= n <= protein.STEPS for n in counts)
    assert protein.steps_for(run[:1], 1.85, 0.11) == []


def test_a_smaller_page_asks_for_no_more_stations():
    run = a_run()

    assert (sum(protein.steps_for(run, 0.37, 0.11))
            <= sum(protein.steps_for(run, 1.85, 0.11))
            <= (len(run) - 1) * protein.STEPS)


# --- the door ------------------------------------------------------------

def test_a_residue_with_no_alpha_carbon_is_named():
    run = a_run()
    run[3] = Res(run[3].number, run[3].structure, None)

    with pytest.raises(ValueError, match=r"residue 4 with no alpha carbon"):
        protein.ribbon(run)


def test_an_unknown_structure_letter_lists_the_three():
    run = a_run()
    run[2] = Res(run[2].number, "G", run[2].ca)     # 3-10 helix, unsupported

    with pytest.raises(ValueError, match="'H' .helix.") as raised:
        protein.ribbon(run)
    assert "'G'" in str(raised.value)


def test_something_that_is_not_a_residue_says_what_it_lacks():
    with pytest.raises(TypeError, match="missing ca, structure, number"):
        protein.ribbon([Vec3(0.0, 0.0, 0.0)])


def test_a_chain_handed_to_ribbon_is_sent_to_cartoon():
    with pytest.raises(TypeError, match="not a whole chain"):
        protein.ribbon(Chain(tuple(a_run())))


def test_a_run_handed_to_cartoon_is_sent_to_ribbon():
    with pytest.raises(TypeError, match="no segments"):
        protein.cartoon(a_run())


def test_a_ribbon_refuses_a_sampling_it_cannot_draw():
    run = a_run()
    with pytest.raises(ValueError, match="one per span"):
        protein.ribbon(run, steps=[6, 6])
    with pytest.raises(ValueError, match="alpha"):
        protein.ribbon(run, steps=0)
    with pytest.raises(ValueError, match="three points"):
        protein.ribbon(run, sides=2)


def test_a_search_whose_floor_is_over_its_ceiling_says_so():
    with pytest.raises(ValueError, match="nothing it may answer"):
        protein.sides_for(1.0, floor=70, ceiling=64)
    with pytest.raises(ValueError, match="nothing it may answer"):
        protein.steps_for(a_run(), 1.0, floor=9, ceiling=6)


# --- the shim ------------------------------------------------------------

def test_the_frames_survive_the_pleat():
    """The flip correction, on the one shape that needs it. A strand's normal
    alternates residue to residue; uncorrected, consecutive frames disagree by
    almost a half turn and the ribbon comes out shredded."""
    marks = protein.stations(strand(1, 8))

    # Interior stations only. `_frames` clamps the index at both ends, so one
    # arm of the cross product is the zero vector there and the first and last
    # frames come from the degenerate branch rather than from the pleat -- a
    # real wart, filed in BACKLOG, not something this test should hide.
    for one, two in zip(marks[1:-1], marks[2:-1]):
        assert one.across.dot(two.across) > 0.0
