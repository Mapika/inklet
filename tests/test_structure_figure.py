"""The structure figure, held to what it claims about itself.

Two of the five panels are renders of a 271-residue fold, so the figure is
built once for the module and the assertions share it; the determinism tests
are the exception, because they have to build it more than once on purpose.

The claims worth testing here are not "it runs". They are:

* it lints clean, with nothing defended away;
* two builds in two processes write the same bytes, which is what lets the
  committed SVG be a build artefact rather than a snapshot;
* every distance the caption quotes was measured off the deposited
  coordinates at build time and not typed in;
* the panels agree with each other about which contact is which, because the
  whole argument of (d) and (e) turns on two of the three hinge bonds being
  made by main-chain atoms and one by a side chain -- if `contact_class` and
  `target.RESTRAINTS` ever came apart, the figure would go on drawing a
  confident prediction of the wrong thing;
* the ribbon is cut where the figure says it may be cut. Colouring a fold by
  lobe means splitting one chain into three meshes, and a split shows unless
  it lands on a coil residue -- a coil section is a circle, and a circle has
  no frame orientation for the two halves to disagree about.

The caption is the thing most likely to rot, so it is checked hardest: it is
formatted from the same template with the same arguments the page uses, and
then read for the numbers the panels actually drew.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

inklet = importlib.import_module("inklet")
structure = importlib.import_module("figures.structure")
data = importlib.import_module("figures.structure_data")
target = importlib.import_module("figures.target")
cartoon = importlib.import_module("figures.cartoon")


@pytest.fixture(scope="module")
def figure():
    return structure.build()


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------

def test_the_figure_lints_clean(figure):
    """Clean, not "no errors". Every finding this figure collected was either
    fixed or declared with `inklet.abutting` at the point where the touch is
    deliberate, so there is nothing left to defend in prose."""
    assert not figure.lint(), figure.report()


def test_the_page_is_a_double_column(figure):
    body, _ = figure.build()
    assert body.width == pytest.approx(structure.PAGE, abs=0.01)


def test_the_top_row_fits_the_content_box():
    """The top row is sized off the hero, whose width depends on how far its
    callouts reach in the projection, so the column budget is arithmetic and
    not a constant. What has to close is the row: a lettered hero, a gap of at
    least `GAP`, and a lettered column of two panels, inside `CONTENT`. An
    `OFF_CANVAS` finding would already fail the lint test; this one says which
    sum was wrong, and it is the sum most likely to move -- `panel_b` overhangs
    its own render by a couple of millimetres of label, and `B_OVERHANG` is a
    measurement of that rather than a law about it."""
    hero = structure.panel_a()
    column = structure.CONTENT - hero.width - structure.GAP \
        - 2.0 * structure.LETTER_GUTTER
    assert column > 40.0
    site, _ = structure.panel_b(width=column - structure.B_OVERHANG)
    a, b, c = inklet.letters([hero, site, structure.panel_c(width=column)])
    right = inklet.vstack([b, c], gap=structure.GAP, align="left")
    gap = structure._gap(a, right)
    assert gap >= structure.MIN_GAP
    assert a.width + gap + right.width == pytest.approx(structure.CONTENT,
                                                        abs=0.01)


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

def test_the_same_figure_renders_byte_identically_twice(figure):
    assert figure.to_svg() == figure.to_svg()


def test_two_builds_in_one_process_agree_on_every_coordinate():
    """Ids come from a per-process counter, so two builds in one process
    number their nodes differently; nothing downstream of the data may. What
    is left after the ids are normalised away is the geometry, the text and
    the colours."""
    ids = re.compile(r'(id="|data-name="|url\(#|href="#)[A-Za-z-]*\d+')
    first = ids.sub(r"\1X", structure.build().to_svg())
    second = ids.sub(r"\1X", structure.build().to_svg())
    assert first == second


def test_two_builds_in_two_processes_write_the_same_bytes():
    """The claim the committed SVG rests on, and the reason it needs its own
    processes: the id counter starts at zero in each of them, so this compares
    the actual bytes rather than normalised ones. Slow -- it is two whole
    builds -- and worth it, because a figure whose output moves between runs
    turns every diff into a review of a hash."""
    probe = ("import hashlib, sys; sys.path.insert(0, %r);"
             "import figures.structure as s;"
             "print(hashlib.sha256(s.build().to_svg().encode()).hexdigest())"
             % ROOT)
    runs = [subprocess.run([sys.executable, "-c", probe], capture_output=True,
                           text=True, cwd=ROOT) for _ in range(2)]
    for run in runs:
        assert run.returncode == 0, run.stdout + run.stderr
    assert runs[0].stdout == runs[1].stdout
    assert len(runs[0].stdout.strip()) == 64


def test_the_simulated_data_are_seeded_not_sampled():
    """Two panels of noise, asked twice. This is the property the byte
    identity above actually rests on."""
    wild = data.variant("wild type")
    top = data.CONCENTRATIONS[-1]
    assert data.sensorgram(wild, top) == data.sensorgram(wild, top)
    assert data.replicates(wild) == data.replicates(wild)
    assert data.spread(wild) == data.spread(wild)


# ---------------------------------------------------------------------------
# the structure is real
# ---------------------------------------------------------------------------

def test_every_bond_length_on_the_page_was_measured_not_typed():
    """`target.RESTRAINTS` says what the dock was *asked* for; `contacts()`
    says what it *got*. The panels quote the second, and the two differ by up
    to half an angstrom, so a panel that had quietly gone back to quoting the
    restraint would show up here rather than in a reviewer's letter."""
    measured = {name: span for name, _p, _l, span in target.contacts()}
    asked = {name: wanted for name, _atom, _lig, wanted in target.RESTRAINTS}
    assert set(measured) == set(asked)
    assert measured != asked
    for name, span in measured.items():
        assert abs(span - asked[name]) < 0.6, name
    # (c) prints the same numbers to one decimal.
    for label, (_atom, span) in structure.hydrogen_bonds().items():
        assert span == pytest.approx(measured[label], abs=1e-9)


def test_the_pocket_residues_are_found_by_searching_the_coordinates():
    """(c) does not carry a list of what is in the pocket. It asks the
    deposited entry which residues have an atom within `CONTACT` of the
    compound, so the three hydrogen-bonded residues have to fall out of the
    search rather than be added to it."""
    found = dict(structure.contact_residues())
    for name, _p, _l, _span in target.contacts():
        assert name in found, found
    assert len(found) >= 8
    for _label, ranked in found.items():
        assert min(span for span, _index in ranked) <= structure.CONTACT


def test_the_ribbon_is_cut_only_where_a_cut_does_not_show():
    """Three lobes means three meshes off one chain, and a join between two
    ribbon sections shows unless both sides are coil: a coil section is a
    circle -- `cartoon.SECTIONS` -- and a circle has no orientation for the
    halves to disagree about. A strand would also get an arrowhead at the cut,
    two residues before the sheet actually ends."""
    here = target.structure()
    boundaries = {first for _name, first, _last in structure.LOBES[1:]}
    boundaries |= {last for _name, _first, last in structure.LOBES[:-1]}
    boundaries |= {structure.STRAP_RUN[1] - 1, structure.HINGE_RUN[0]}
    for number in sorted(boundaries):
        residue = here.get(number)
        assert residue is not None, number
        assert cartoon.NAMES[residue.structure] == "coil", \
            f"{residue.label} is {cartoon.NAMES[residue.structure]}"


def test_the_lobes_cover_the_domain_once_each():
    """No residue painted twice and none left grey: the three runs abut, and
    together they are the whole deposited domain."""
    here = target.structure()
    assert structure.LOBES[0][1] == here.residues[0].number
    assert structure.LOBES[-1][2] >= here.residues[-1].number
    for (_a, _first, last), (_b, first, _l) in zip(structure.LOBES,
                                                   structure.LOBES[1:]):
        assert last == first
    # `fold` draws each run inclusive of its last residue, so the boundary
    # residues are painted twice on purpose: two ribbon sections that share a
    # station meet without a gap between them. The overlap is one residue at
    # each join and no more, and together the runs are the whole domain.
    painted = [n for _name, first, last in structure.LOBES
               for n in range(first, last + 1) if here.get(n)]
    assert set(painted) == {r.number for r in here.residues}
    twice = sorted(n for n in set(painted) if painted.count(n) > 1)
    assert twice == sorted(first for _n, first, _l in structure.LOBES[1:])


def test_the_close_up_is_inside_the_exact_sort_budget():
    """(b) is the panel that spends the facet budget, and it spends it where
    exact ordering earns its cost: a compound wedged between a strand, a strap
    and four side chains is exactly the case a mean-depth sort gets wrong.
    The whole fold in (a) is far too big for it and is drawn by depth cue
    instead, which is why the close-up exists as its own panel."""
    from inklet.three import AUTO_EXACT_FACETS
    faces = len(structure.site(cartoon.SIDES).faces)
    assert 5000 < faces < AUTO_EXACT_FACETS
    assert len(structure.fold(cartoon.SIDES).faces) > AUTO_EXACT_FACETS


# ---------------------------------------------------------------------------
# stations along the ribbon
# ---------------------------------------------------------------------------

def _run(first=688, last=768):
    here = target.structure()
    return [here[n] for n in range(first, last + 1) if here.get(n)]


def test_steps_for_answers_once_per_span_and_inside_its_bounds():
    residues = _run()
    counts = cartoon.steps_for(residues, 1.85, 0.11)
    assert len(counts) == len(residues) - 1
    assert all(1 <= n <= cartoon.STEPS for n in counts)
    assert cartoon.steps_for(residues[:1], 1.85, 0.11) == []


def test_a_smaller_page_asks_for_fewer_stations():
    """The point of the knob: the tolerance is millimetres on the page, so the
    same fold drawn a fifth the size may be sampled a fifth as hard. Monotone
    rather than a fixed table, because the numbers are the geometry's."""
    residues = _run()
    big = sum(cartoon.steps_for(residues, 1.85, 0.11))
    small = sum(cartoon.steps_for(residues, 0.37, 0.11))
    assert small < big < len(residues) * cartoon.STEPS
    assert sum(cartoon.steps_for(residues, 0.0, 0.11)) == \
        (len(residues) - 1) * cartoon.STEPS      # no scale: no licence to coarsen


def test_a_ribbon_spends_the_stations_it_was_given():
    """`spans * steps * sides * 2` facets, plus a cap at each end of the run."""
    residues = _run()
    spans, sides = len(residues) - 1, cartoon.SIDES
    for steps in (1, 2, 6):
        mesh = cartoon.ribbon(residues, sides=sides, steps=steps)
        assert len(mesh.faces) == spans * steps * sides * 2 + 2 * sides
    uniform = cartoon.ribbon(residues, sides=sides, steps=[3] * spans)
    assert uniform.vertices == cartoon.ribbon(residues, sides=sides,
                                              steps=3).vertices


def test_a_ribbon_refuses_a_sampling_it_cannot_draw():
    residues = _run()
    with pytest.raises(ValueError, match="one per span"):
        cartoon.ribbon(residues, steps=[6, 6])
    with pytest.raises(ValueError, match="alpha"):
        cartoon.ribbon(residues, steps=0)


def test_the_hero_is_over_the_budget_even_sampled_to_tolerance():
    """Why (a) keeps the depth cue. `steps_for` was built to get the whole fold
    under `AUTO_EXACT_FACETS`, and at the hero's page scale it does not: the
    honest along-chain tolerance is about 0.04 mm -- three times tighter than
    the 0.11 the *section* is allowed, because a spline's departure lands on
    the silhouette where a section's is hidden inside a shaded surface -- and
    at 0.04 the fold is still nearly twice the ceiling. The comment block
    beside `structure.TOLERANCE` has the table and the crops."""
    from inklet.three import AUTO_EXACT_FACETS
    here = target.structure()
    probe = structure.fold(cartoon.SIDES)
    scale = inklet.three.page_scale(probe, width=structure.HERO,
                                 view=structure.VIEW)
    faces = 0
    for _name, first, last in structure.LOBES:
        residues = [here[n] for n in range(first, last + 1) if here.get(n)]
        faces += len(cartoon.ribbon(
            residues, sides=cartoon.SIDES,
            steps=cartoon.steps_for(residues, scale, 0.04)).faces)
    assert faces > 1.5 * AUTO_EXACT_FACETS


def test_the_hero_names_every_point_a_callout_lands_on():
    """A leader that cannot resolve its anchor throws at build time, so this
    is really a check that the names have not drifted -- `hinge` in
    particular, which the figure re-registers over its own painted run
    because `target.FEATURES` means a different five residues by the word."""
    scene, scale = structure.hero(structure.HERO)
    for name in ("hinge", "p-loop"):
        assert scene.at(name) is not None
    for name, _p, _l, _s in target.contacts():
        assert scene.at(f"{name}-tip") is not None
        assert scene.at(f"{name}-atom") is not None
    assert len(target.ligand_atoms()) > 20
    for index in range(len(target.ligand_atoms())):
        assert scene.at(f"atom{index}") is not None
    assert 0.1 < scale < 10.0


# ---------------------------------------------------------------------------
# the assays are not
# ---------------------------------------------------------------------------

def test_the_mutant_panels_read_the_contact_off_the_pose():
    """The prediction (d) and (e) draw is only a prediction because two of the
    three bonds are made by atoms an alanine cannot remove. `contact_class`
    works that out from `target.RESTRAINTS` instead of being told, so this
    test asserts the derivation and not a table."""
    assert structure.contact_class(data.variant("T766A")) == "side chain"
    assert structure.contact_class(data.variant("T766M")) == "side chain"
    assert structure.contact_class(data.variant("Q767A")) == "main chain"
    assert structure.contact_class(data.variant("M769A")) == "main chain"
    assert structure.contact_class(data.variant("K721A")) == "no contact"
    assert structure.contact_class(data.variant("wild type")) == "wild type"


def test_the_numbers_say_what_the_geometry_predicts():
    """The two main-chain controls barely move and the gatekeeper wrecks it.
    If the data module were ever retuned so that a hinge alanine cost as much
    as the gatekeeper, the figure would still draw, still lint and still be
    wrong, and this is what would notice."""
    for name in ("Q767A", "M769A"):
        assert data.fold_change(data.variant(name)) < 2.0
    assert data.fold_change(data.variant("T766A")) > 10.0
    assert data.fold_change(data.variant("T766M")) > 100.0
    assert 1.5 < data.ddg(data.variant("T766A")) < 2.5   # one hydrogen bond


def test_the_caption_quotes_the_numbers_the_panels_drew():
    facets = len(structure.site(cartoon.SIDES).faces)
    rendered = structure.caption(facets).text if hasattr(
        structure.caption(facets), "text") else None
    here = target.structure()
    bonds = "; ".join(f"{name} {span:.2f}"
                      for name, _p, _l, span in target.contacts())
    text = structure.CAPTION.format(
        first=here.residues[0].number, last=here.residues[-1].number,
        hinge_first=structure.HINGE_RUN[0],
        hinge_last=structure.HINGE_RUN[1] - 1,
        fill=structure.FILL, turn=structure.VIEW_B[0] - structure.VIEW[0],
        bonds=bonds,
        asked=", ".join(f"{w:.1f}" for _n, _a, _l, w in target.RESTRAINTS),
        facets=facets, contact=structure.CONTACT,
        steps=len(data.CONCENTRATIONS),
        inject=data.INJECTION[1] - data.INJECTION[0], follow=data.FOLLOW,
        reps=len(data.replicates(data.VARIANTS[0])),
        t766a=data.ddg(data.variant("T766A")),
        t766m=data.ddg(data.variant("T766M")),
        control=max(data.fold_change(data.variant(n))
                    for n in ("Q767A", "M769A")))
    assert rendered is None or isinstance(rendered, str)
    assert f"{facets:,} facets" in text
    for name, _p, _l, span in target.contacts():
        assert f"{name} {span:.2f}" in text
    assert "PDB 1M17" in text
    assert f"{structure.CONTACT:.1f} Å of the compound" in text
    # The one sentence the figure is not allowed to lose.
    assert ("**The structure is real (PDB 1M17); all assay data are "
            "simulated.**") in text
    assert structure.caption(facets) is not None


def test_the_caption_does_not_claim_an_experiment():
    """A caption for simulated data has to say so in words a reader who skips
    the methods will still meet. Both halves of the disclosure are asserted:
    that the structure is real, and that nothing else is."""
    assert "the compound does not exist" in structure.CAPTION
    assert "the mutants were never made" in structure.CAPTION
    assert "structure_data.py" in structure.CAPTION


# ---------------------------------------------------------------------------
# the panels, one at a time
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("letter", sorted(structure.PANELS))
def test_every_panel_builds_on_its_own(letter):
    """`figures/structure.py b` is how the panel was worked on, and a preview
    that no longer runs is a preview nobody will use."""
    panel = structure.PANELS[letter]()
    assert panel.width > 10.0 and panel.height > 10.0
