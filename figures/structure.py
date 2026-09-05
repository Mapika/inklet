"""Figure 1 of a structural paper: how an ATP-site inhibitor reads the hinge.

Five panels and one argument. **(a)** says where the site is -- a slot between
the two lobes of the kinase, with the compound lying in it space-filling, so
that "pocket" is something the reader sees rather than a word in the caption.
**(b)** goes into the slot from the side and measures the three hydrogen bonds
that hold the compound there, with the distances re-measured off the geometry
at build time. **(c)** flattens the same contacts into the schematic a
medicinal chemist reads, and finds the residues in it by asking the deposited
coordinates which ones are close enough rather than by listing them here.
**(d)** and **(e)** are the experiment the geometry predicts: two of the three
bonds are to main-chain atoms, which no side-chain mutation can take away, and
one is to the gatekeeper's side chain, which one can.

**The structure is real and the assays are not.** The protein is PDB 1M17, the
EGFR kinase domain at 2.6 A, drawn from the deposited coordinates in
`data/`; the compound is invented and its pose is a restrained dock (see
`target.py`); every number in (d) and (e) comes from `structure_data.py`.

    .venv/bin/python figures/structure.py           # build, lint, save
    .venv/bin/python figures/structure.py a         # one panel, working
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inklet
from inklet.three import Mesh, merge

import annot
from inklet.three import protein as cartoon   # was figures/cartoon.py
import structure_data as data
import target
from bio3d import ball

TH = inklet.use_theme("nature")

PAGE = getattr(inklet, "COLUMN_DOUBLE", 183.0)
MARGIN = 4.0
CONTENT = PAGE - 2 * MARGIN
GAP = 5.0

# --- the palette -----------------------------------------------------------
#
# The page is coloured by **lobe**, not by secondary structure. Both are
# conventions and `drug_discovery.py` uses the other one for a good reason --
# a reader who has seen one cartoon knows an arrow is a strand -- but the
# claim this figure makes is about the cleft *between* two lobes and the strap
# that joins them, and colour is the only channel that can say which ribbon
# belongs to which half of the fold. The shape of the ribbon goes on saying
# what the secondary structure is, because that is what a ribbon is for.

# The hinge is drawn in the hydrogen-bond colour rather than in a third
# lobe colour, and that is the whole reason there are four hues instead of
# three. It was orange first, and orange is what the compound is: the strap
# and the thing bound to it merged into one warm shape and the panel lost the
# distinction it exists to make. Plum keeps the compound the only warm object
# on the page -- so the eye lands on it -- and says, before the caption does,
# that the strap is where the bonds in (b) and (c) go.
NLOBE = inklet.mix("#0072b2", TH.paper, 0.62)        # the beta sheet and aC
CLOBE = inklet.mix("#009e73", TH.paper, 0.52)        # the helical lobe
HINGE = inklet.mix("#7b3294", TH.paper, 0.42)        # the strap between them
COMPOUND = "#d55e00"                              # the invented inhibitor
COMPOUND_INK = inklet.mix(COMPOUND, "#000000", 0.20)
SIDECHAIN = inklet.mix(TH.ink, TH.paper, 0.42)       # pocket residues, as sticks
BOND = "#7b3294"                                  # hydrogen bonds, everywhere
BOND_INK = inklet.mix(BOND, "#000000", 0.10)
GREY = inklet.mix(TH.ink, TH.paper, 0.35)

#: What each face group is painted. One mesh carries all of them: the lobes
#: interleave in depth completely, so parts painted whole cannot be ordered.
LOOKS = {"n-lobe": NLOBE, "c-lobe": CLOBE, "hinge": HINGE,
         "compound": COMPOUND, "side-chain": SIDECHAIN}

#: The one heavy weight on the page. Three widths is the linter's budget and
#: the theme spends two of them, so every line that has to read as emphasis is
#: this one and no other.
EMPHASIS = 0.40

# --- how the chain is divided ----------------------------------------------
#
#: Where one lobe ends and the next begins, as residue numbers of the
#: deposited entry. Both boundaries fall on **coil** residues, and that is a
#: constraint rather than a preference: a run of ribbon is built with its own
#: frame chain, so two runs meeting at a helix or a strand meet at two
#: different orientations of a flat section and the join shows. A coil section
#: is a circle -- `cartoon.SECTIONS` -- and a circle has no orientation to
#: disagree about, so a join in coil is invisible. Cutting at 767 would also
#: put an arrowhead on the b5 strand two residues early, because the last
#: residue of a run looks like the last residue of a strand.
LOBES = (("n-lobe", 688, 768), ("hinge", 768, 772), ("c-lobe", 772, 958))

#: The hinge as this figure paints it, as a range for `range()`.
HINGE_RUN = (768, 773)

#: Van der Waals radii, in angstroms, and how much of one to draw. A true CPK
#: model at 1.0 has neighbouring atoms overlapping so far that the compound is
#: a single lozenge with no chemistry visible in it; at 0.72 the atoms are
#: still fused into one body -- which is the point, the thing has a volume and
#: it fills the slot -- and the reader can still count the rings.
VDW = {"C": 1.70, "N": 1.55, "O": 1.52, "Cl": 1.75}
FILL = 0.72


def elements() -> list[str]:
    """The element of every atom of the skeleton, in the skeleton's order."""
    atoms, _, named = target.skeleton()
    kind = ["C"] * len(atoms)
    for name, element in target.ELEMENTS.items():
        kind[named[name]] = element
    return kind


def space_filling(fraction: float = FILL, subdivisions: int = 1) -> Mesh:
    """The compound as fused spheres, where the docking put it.

    Space-filling rather than the ball-and-stick `target.ligand()` draws,
    because panel (a)'s claim is about *volume*: the compound is the right
    size and shape for the slot between the lobes, and a stick model shows a
    skeleton floating in a gap.
    """
    return merge([ball((p.x, p.y, p.z), VDW[element] * fraction,
                       subdivisions=subdivisions)
                  for p, element in zip(target.ligand_atoms(), elements())]
                 ).grouped("compound")


@lru_cache(maxsize=None)
def fold(sides: int, *, filled: bool = True) -> Mesh:
    """The whole domain, one mesh, its lobes told apart by face group.

    One mesh and not three: the lobes fold past each other and a ligand sits
    between them, so there is no order in which three parts could be painted
    that is right everywhere. Merged, hidden-line removal happens a facet at a
    time and the groups keep each piece its own colour.
    """
    here = target.structure()
    runs = []
    for name, first, last in LOBES:
        residues = [here[n] for n in range(first, last + 1) if here.get(n)]
        runs.append(cartoon.ribbon(residues, name=f"{name}", group=name,
                                   sides=sides))
    pieces = runs + [target.side_chains().grouped("side-chain")]
    pieces.append(space_filling() if filled else
                  target.ligand().grouped("compound"))
    return merge(pieces).transformed(target.orientation())


# ===========================================================================
# (a)  the site
# ===========================================================================

#: Azimuth and elevation, chosen by rendering the sweep in
#: `tmp/agents/structure/sweep_view.py`: at this azimuth every ring of the
#: compound clears the ribbon in front of it, and the elevation is the
#: shallowest that still shows the cleft as a slot rather than as an edge.
#: `target.orientation()` has already stood the molecule up -- N lobe above C
#: lobe, cleft toward the reader -- so this is the only camera choice left.
VIEW = (-16.0, 26.0)

#: How far the drawn ribbon may sit from the section it stands for, in
#: millimetres on the page. `cartoon.sides_for` turns it into a point count.
#: Looser than the 0.06 mm `drug_discovery.py` asks for, and the reason is the
#: facet budget rather than the printer: 0.06 wants 17 points round the
#: section at this width, which is 61,000 facets and four seconds, and 0.11 --
#: still under half a hairline -- wants 10.
TOLERANCE = 0.11

# --- why this panel is depth-cued and (b) is exact -------------------------
#
# `cartoon.steps_for` is the knob that was supposed to fix this, and it was
# built, measured and declined. It is the same trade as `sides_for` turned
# ninety degrees: spend fewer cross-sections along the chain where the chain
# is not doing anything, and the fold might come in under
# `inklet.three.AUTO_EXACT_FACETS` (22,000) and `AUTO_EXACT_PAIRS` (400,000),
# where the renderer compares every overlapping pair instead of ordering by
# mean depth. Measured on this camera at 71 mm, `sides=12`:
#
#     stations       faces    facets      pairs   model   exact offered
#     uniform 6     44,048    66,204    600,968   3.3 s   no  (shipped)
#     tol 0.11 mm   27,920    43,739    467,105   5.2 s   no
#     tol 0.22 mm   20,528    32,823    410,438   6.4 s   no  (pairs)
#     tol 0.30 mm   18,920    30,426    395,562   6.1 s   yes
#     uniform 2     18,128    29,184    385,638   3.9 s   yes
#
# **Three things came out of that table and all three say no.**
#
# The exact order is not worth anything *here*. Sorted exactly at the shipped
# 44,048 faces the panel differs from the depth-cued one in 16,098 pixels of
# 1,572,435 at print resolution -- one percent, all of it specks at the
# sphere-sphere seams of the compound and at two side-chain joins, none of it
# on the ribbon. Panel (b) is where an exact order earns its keep, because
# there the thing being ordered is three hydrogen bonds threading between
# atoms and one swapped facet is a bond drawn in front of the ring it goes
# behind. Here it is a fold, and a fold has no such reading.
#
# The coarse ribbon is worth a great deal, and all of it negative. The
# along-chain tolerance is *not* interchangeable with the across-section one:
# a section's departure is hidden inside a shaded surface, and a spline's
# departure lands on the **silhouette**, where a 2D corner is about the most
# legible thing a drawing has. At the 0.11 mm this panel already accepts
# across the section, the C lobe's helix ends are visibly cornered; by the
# 0.30 mm that fits the pair budget the loops are a chain of straight
# segments. Crops in tmp/agents/r6-structure/cmp_clobe.png. The honest
# along-chain figure at this scale is about 0.04 mm, three times tighter, and
# that saves 10 percent of the faces and no sort regime at all.
#
# And it would be slower. The exact sort at a mesh coarse enough to be offered
# it costs 6.1 s against the depth cue's 3.3 s, because dropping the facet
# count by a third drops the *pair* count by a third of that -- the pairs on
# this camera are mostly the compound's spheres against each other and the two
# lobes against each other, and neither is a ribbon-sampling question.
#
# So the fold stays at six stations a residue and takes the depth cue. The
# whole domain would fit the ceiling at `steps_for(scale, 0.04)` if it were
# drawn 14 mm wide, which is a thumbnail, and a thumbnail has no depth error
# worth sorting out either.


#: How wide the drawn model is, before the labels in the gutters beside it are
#: counted. The panel comes out about ten millimetres wider than this.
HERO = 71.0

#: Ink for a label that names a lobe. No leader goes with these two: the
#: colour is the identification, and a line from the word "N lobe" to a lobe
#: filling half the panel would be pointing at something nobody could miss.
NLOBE_INK = inklet.mix(NLOBE, "#000000", 0.42)
CLOBE_INK = inklet.mix(CLOBE, "#000000", 0.46)
HINGE_INK = inklet.mix(HINGE, "#000000", 0.30)


def hero(width: float = HERO) -> tuple[inklet.Diagram, float]:
    """The whole domain, and the millimetres-per-angstrom it came out at.

    The scale is returned rather than recomputed by the caller because it is
    what a scale bar and a zoom window both need, and recomputing it means
    two places that can come to disagree about the magnification.
    """
    probe = fold(cartoon.SIDES)
    scale = inklet.three.page_scale(probe, width=width, view=VIEW)
    mesh = fold(cartoon.sides_for(scale, TOLERANCE))
    anchors = {}
    for name, protein, tip, _ in target.contacts():
        anchors[f"{name}-tip"] = protein
        anchors[f"{name}-atom"] = tip
    # Every atom of the compound, so that anything drawn round the site can be
    # sized from where the compound actually landed on the page rather than
    # from a guess in millimetres. A centroid anchor cannot do this: it says
    # where the middle is and nothing about how far the thing reaches, and the
    # reach is what a ring has to enclose.
    # `upright`, because `ligand_atoms` is in the deposited frame and the mesh
    # has been through `orientation()`: an anchor has to be given in the frame
    # the model is drawn in, and `contacts()` above already is.
    for index, atom in enumerate(target.ligand_atoms()):
        anchors[f"atom{index}"] = target.upright(atom)
    node = inklet.three.model(
        mesh, width=width, view=VIEW, style="shaded", colors=LOOKS,
        crease=45.0, smooth=90.0, shading="smooth", levels=12,
        depth_cue=0.35, lift=0.20, shade=0.40, occlusion=0.18,
        stroke_width=TH.hairline, anchors=anchors, name="kinase")
    for name, run in target.label_runs().items():
        inklet.three.anchor3d(node, name, run, pick="visible")
    # `target.FEATURES` calls the hinge 767-771 and this figure paints 768-772,
    # because the two boundaries answer different questions -- theirs is which
    # residues a chemist calls the hinge, mine is where a ribbon may be cut
    # without the join showing. Left alone, the leader lands two residues into
    # the blue and points at the wrong colour. The label follows the paint.
    here = target.structure()
    inklet.three.anchor3d(node, "hinge", [target.upright(here[n].ca)
                                       for n in range(*HINGE_RUN)
                                       if here.get(n)], pick="visible")
    return node, scale


def site_box(scene: inklet.Diagram,
             scale: float) -> tuple[float, float, float, float]:
    """Centre and size of the compound on the page, in millimetres.

    Read off the projected atoms and grown by the largest van der Waals
    radius, so it encloses the drawn spheres and not their centres.
    """
    points = [annot.at(scene, f"atom{i}")
              for i in range(len(target.ligand_atoms()))]
    pad = max(VDW.values()) * FILL * scale
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0,
            max(xs) - min(xs) + 2.0 * pad, max(ys) - min(ys) + 2.0 * pad)


def panel_a(width: float = HERO) -> inklet.Diagram:
    """(a) Where the site is: the slot between the lobes, with a thing in
    it."""
    scene, scale = hero(width)
    half = width / 2.0
    cx, cy, box_w, box_h = site_box(scene, scale)

    # Three pieces of chain, three coloured words, no lines. A leader to the
    # hinge is the one callout this panel cannot draw honestly: the strap is
    # in the middle of the fold, the nearest clear ground is at the edge of
    # the picture, and the line between them cuts eighteen millimetres of
    # ribbon in half. Naming all three by colour instead makes the panel's own
    # palette the key -- the reader who finds "hinge" in plum finds the plum
    # under the compound -- and it costs nothing, because the two lobes were
    # never going to take a leader either.
    named = [("N lobe", NLOBE_INK, (-half - 5.0, -half * 1.24)),
             ("hinge", HINGE_INK, (-half - 5.0, cy + 3.0)),
             ("C lobe", CLOBE_INK, (-half - 5.0, half * 1.00))]
    items = [(where, inklet.text(text, size=TH.font_size_small, text_fill=ink,
                              kind="label")) for text, ink, where in named]

    # The site, ringed -- a fifth again as big as the compound, so that it
    # reads as a region rather than as an outline of the molecule, which is
    # what the spheres already are. `kind="mark"`: the ring is centred and
    # sized on projected anchors, so where it sits is the model speaking.
    ring_w, ring_h = box_w * 1.20, box_h * 1.55
    ring = annot.ring((cx, cy), ring_w, ring_h, name="site",
                      stroke=COMPOUND_INK, stroke_width=EMPHASIS,
                      stroke_dash=(1.4, 1.0),
                      kind="mark")[1].translated(cx, cy)
    # The leader lands on the ring, not inside it: the ring is what is being
    # named, and a line that crosses it is pointing past it.
    line, tag = annot.leader(
        "compound, in\nthe ATP site",
        (cx + ring_w * 0.34, cy + ring_h * 0.37),
        (half + 8.0, cy + 13.5), ink=COMPOUND_INK)
    items.append(tag)
    items += annot.leader("P-loop", annot.at(scene, "p-loop"),
                          (half + 6.5, -half * 0.52), ink=TH.muted)

    bar = inklet.scalebar(10.0 * scale, "10 \u00c5", plate=False, ink=TH.muted)
    items.append(((-half - 3.0, half * 1.30), bar))

    # The ring encloses the compound and the leader touches the ring, both on
    # purpose. Declared here rather than reported every run: `abutting` is
    # scoped to this subtree and symmetric, so it covers those two touches and
    # leaves the P-loop leader outside it, still checked against the model.
    on_the_fold = inklet.drawn([scene, ring, line],
                            kind=inklet.abutting("on-the-site"))
    return annot.on(on_the_fold, *items)


# ===========================================================================
# (b)  the three bonds, close up
# ===========================================================================

#: Panel (b)'s camera. A hundred and sixteen degrees round from panel (a)'s,
#: about the same vertical the whole page is drawn on, chosen from the sweep
#: in `tmp/agents/structure/pocket_sweep.py` as the azimuth where the compound
#: lies across the page and none of its three rings is behind another.
VIEW_B = (100.0, 22.0)

#: What panel (b) draws of the chain, as `range()` bounds. Two runs, split in
#: the coil at 768 exactly as panel (a) splits it, so the two panels agree
#: about where the hinge starts.
#:
#: It stops at 772 and does not go on into helix aD, and that is a decision
#: made by looking: four residues of helix are not enough turns to read as a
#: helix, so `cartoon` draws them as a flat blade a third the size of the
#: picture, pointing away from everything the panel is about.
STRAND_RUN = (760, 769)
STRAP_RUN = (768, 773)


@lru_cache(maxsize=None)
def site(sides: int) -> Mesh:
    """The hinge, its pocket side chains and the compound: one mesh.

    Small on purpose. Under `inklet.three.AUTO_EXACT_FACETS` the renderer sorts
    the facets exactly -- every pair that overlaps on the page compared and
    ordered -- instead of by mean depth, and that is worth the whole facet
    budget here: this is the panel where a side chain, a ribbon and a ring of
    the compound interleave within an angstrom of each other, which is the one
    arrangement mean depth gets wrong.
    """
    here = target.structure()
    runs = [(STRAND_RUN, "n-lobe"), (STRAP_RUN, "hinge")]
    pieces = [cartoon.ribbon([here[n] for n in range(*span) if here.get(n)],
                             name=group, group=group, sides=sides)
              for span, group in runs]
    pieces.append(target.side_chains().grouped("side-chain"))
    pieces.append(target.ligand().grouped("compound"))
    return merge(pieces).transformed(target.orientation())


def panel_b(width: float = 66.0) -> tuple[inklet.Diagram, int]:
    """(b) The ringed site of (a), turned, with the three bonds measured."""
    here = target.structure()
    mesh = site(cartoon.SIDES)
    anchors = {"Lys721": target.upright(here[721].atoms["NZ"])}
    for name, protein, tip, _span in target.contacts():
        anchors[f"{name}-tip"] = protein
        anchors[f"{name}-atom"] = tip
    scene = inklet.three.model(
        mesh, width=width, view=VIEW_B, style="shaded", colors=LOOKS,
        crease=45.0, smooth=90.0, shading="smooth", levels=14,
        depth_cue=0.28, lift=0.18, shade=0.40, occlusion=0.22,
        stroke_width=TH.hairline, anchors=anchors, name="site")
    scale = inklet.three.page_scale(mesh, width=width, view=VIEW_B)
    half_w, half_h = scene.width / 2.0, scene.height / 2.0

    labels: list = []
    lines: list = []
    for name, _p, _l, span in target.contacts():
        start = annot.at(scene, f"{name}-tip")
        end = annot.at(scene, f"{name}-atom")
        lines.append(annot.stroke([start, end], stroke=BOND,
                                  stroke_width=EMPHASIS,
                                  stroke_dash=(0.8, 0.6), kind="hbond"
                                  ).named(f"bond-{name}"))
        # Aimed at the middle of the dash, not at either end of it. The label
        # names the bond; one end of it is a ligand atom and the other is a
        # main-chain atom inside the ribbon, and a leader to either says the
        # measurement belongs to that atom rather than to the pair.
        middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        line, tag = annot.leader(
            inklet.text(f"{name}\n{{muted|{span:.2f} \u00c5}}",
                     size=TH.font_size_small, text_fill=BOND_INK,
                     kind="label"),
            middle, (LABEL_B[name][0] * half_w, LABEL_B[name][1] * half_h),
            ink=BOND_INK)
        lines.append(line)
        labels.append(tag)

    # The catalytic lysine, named because panel (e) mutates it and this is the
    # panel that has to show the reader it is not in contact with anything.
    line, tag = annot.leader("Lys721", annot.at(scene, "Lys721"),
                             (0.14 * half_w, 1.22 * half_h), ink=TH.muted)
    lines.append(line)
    labels.append(tag)

    bar = inklet.scalebar(5.0 * scale, "5 \u00c5", plate=False, ink=TH.muted)
    labels.append(((-half_w + bar.width / 2.0, -half_h + 3.0), bar))

    # Leaders and dashes both inside the declaration, and for the same reason.
    # A hydrogen bond runs between two atoms, so its dash ends inside both of
    # them; a label for that bond has to reach a point in the middle of a
    # packed pocket, and every route to it crosses a ribbon or a side chain.
    # That is what a close-up of a pocket is. Declared once here, so that the
    # report stays a list of things that are wrong.
    drawn = inklet.drawn([scene, *lines], kind=inklet.abutting("in-the-pocket"))
    return annot.on(drawn, *labels), len(mesh.faces)


#: Where each bond's label sits, as a fraction of the scene's half-width and
#: half-height. By hand, because there are three of them and they are the
#: panel: `pick="visible"` chooses which end of a run to touch, and nothing in
#: the library chooses which corner a label goes in.
LABEL_B = {"Met769": (-0.93, -0.20), "Gln767": (0.03, -0.60),
           "Thr766": (0.92, 0.56)}


# ===========================================================================
# (c)  the same contacts, flat
# ===========================================================================

#: How close two atoms have to be to count as touching, in angstroms. Two
#: carbons are in van der Waals contact at about 3.9; 4.0 is that, rounded to
#: a number a caption can print without implying a precision nobody has.
CONTACT = 4.0


def contact_residues() -> list[tuple[str, tuple[tuple[float, int], ...]]]:
    """Which residues line the site, and how near each atom of the compound.

    Measured, not listed. The alternative -- a tuple of residue numbers at the
    top of this file -- is a second opinion about the pose, and the moment
    `tools/dock_ligand.py` is re-run against a different restraint it becomes
    a wrong one that nothing can catch. Here the panel cannot name a residue
    the coordinates do not put next to the compound.

    Every atom within reach and not only the nearest, because a residue that
    touches one end of a ring can be drawn off either end of it, and which
    end has room is a question about the page that this cannot answer.

    One caveat the caption carries: `data/1m17-kinase.pdb` is trimmed to the
    main chain plus the four pocket residues, so a residue whose side chain
    would reach the compound but whose side chain is not in the file is
    measured from its backbone and can fall outside the cut. What is here is
    real; what is missing may be too.
    """
    here = target.structure()
    found: dict[str, dict[int, float]] = {}
    for index, point in enumerate(target.ligand_atoms()):
        for residue in here.near(point, CONTACT):
            span = min((atom - point).length
                       for atom in residue.atoms.values())
            reach = found.setdefault(residue.label, {})
            reach[index] = min(span, reach.get(index, span))
    ranked = {label: tuple(sorted((span, index)
                                  for index, span in reach.items()))
              for label, reach in found.items()}
    return sorted(ranked.items(), key=lambda row: (row[1][0], row[0]))


def hydrogen_bonds() -> dict[str, tuple[int, float]]:
    """Residue label -> the atom it bonds to and the distance, re-measured.

    `RESTRAINTS` says which atom of the compound each bond was asked for and
    `contacts()` says how long the bond came out; the index comes from the
    same `skeleton()` the flat drawing is built from, so the dash in this
    panel lands on the atom the pose actually bonded.
    """
    _, _, named = target.skeleton()
    measured = {name: span for name, _, _, span in target.contacts()}
    return {name: (named[atom], measured[name])
            for name, _, atom, _ in target.RESTRAINTS}


def _spread(wanted: list[float], widths: list[float], pad: float,
            low: float, high: float) -> list[float]:
    """Label positions along a line: as near what each asked for as fits.

    One sweep left to right opening every gap to what the two labels either
    side of it need, then a sweep back from whichever end overflowed. Enough
    for five labels on one row, and it keeps them in the order their atoms
    are in, which is the property that stops the connectors crossing.

    Widths per pair rather than one gap for all of them, because two of these
    labels carry a measurement and are half again as wide as the rest: spaced
    on the widest, five labels want more millimetres than the row has and the
    clamp drags the whole row sideways, which is how a dash to a pyrimidine
    carbon ended up running through the amide nitrogen.
    """
    out = list(wanted)
    for index in range(1, len(out)):
        need = (widths[index - 1] + widths[index]) / 2.0 + pad
        out[index] = max(out[index], out[index - 1] + need)
    if out and out[-1] + widths[-1] / 2.0 > high:
        out[-1] = high - widths[-1] / 2.0
        for index in range(len(out) - 2, -1, -1):
            need = (widths[index] + widths[index + 1]) / 2.0 + pad
            out[index] = min(out[index], out[index + 1] - need)
    if out and out[0] - widths[0] / 2.0 < low:
        out[0] = low + widths[0] / 2.0
        for index in range(1, len(out)):
            need = (widths[index - 1] + widths[index]) / 2.0 + pad
            out[index] = max(out[index], out[index - 1] + need)
    return out


def panel_c(width: float = 75.3) -> inklet.Diagram:
    """(c) The pocket unrolled: every contact the coordinates actually make."""
    atoms, bonds, named = target.skeleton()
    letters = {named[key]: element
               for key, element in target.ELEMENTS.items()}
    bonded = hydrogen_bonds()

    # Fit the skeleton to the width it is allowed, leaving room either side
    # for the residues that hang off it.
    xs = [x for x, _ in atoms]
    ys = [y for _, y in atoms]
    scale = (width - 24.0) / (max(xs) - min(xs))
    mid_x = (min(xs) + max(xs)) / 2.0
    mid_y = (min(ys) + max(ys)) / 2.0
    flat = [((x - mid_x) * scale, (mid_y - y) * scale) for x, y in atoms]

    items: list = []
    # The formula's own parts, kept in one declared group. The aromatic
    # circle of a ring sits a fraction of a millimetre inside the six bonds
    # it belongs to, which at this size is under the crowding clearance and
    # is exactly where it is supposed to be; declaring the formula says so
    # once instead of twelve times, and leaves the contact dashes -- which
    # are not part of the molecule -- still checked against it.
    molecule: list = []
    # Single lines whatever the bond order. A structural formula has to say
    # which bonds are double, because that is the claim it makes; this panel's
    # claim is about what touches what, and Kekule lines under a mesh of
    # contact dashes are ink competing with the subject. Panel (c) of
    # `drug_discovery.py` is the one that owes the reader a formula.
    for first, second, _order, _inner in bonds:
        start, end = flat[first], flat[second]
        for index, which in ((first, 0), (second, 1)):
            if index not in letters:
                continue
            here, other = flat[index], (end if which == 0 else start)
            dx, dy = other[0] - here[0], other[1] - here[1]
            span = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            moved = (here[0] + dx / span * 1.5, here[1] + dy / span * 1.5)
            start, end = (moved, end) if which == 0 else (start, moved)
        molecule.append(annot.stroke([start, end], stroke=COMPOUND_INK,
                                     stroke_width=TH.hairline, kind="bond"))
    # An inner circle rather than Kekule lines: it is the other standard way
    # to draw an aromatic ring, it is one stroke instead of three, and it
    # leaves the ring's own edge free for a contact dash to arrive at. Which
    # rings get one is read off the bond orders -- a ring bond that is double
    # names its own centre -- so the morpholine, which has none, gets none.
    aromatic = sorted({inner for _a, _b, order, inner in bonds
                       if order == 2 and inner is not None})
    for inner in aromatic:
        molecule.append(annot.ring(((inner[0] - mid_x) * scale,
                                    (mid_y - inner[1]) * scale),
                                   1.24 * scale, 1.24 * scale, kind="bond",
                                   stroke=COMPOUND_INK,
                                   stroke_width=TH.hairline))
    for index, element in letters.items():
        molecule.append(annot.text_at(element, flat[index],
                                      size=TH.font_size_small,
                                      text_fill=TH.ink, kind="atom"))

    # Residues above and below the compound. Which side is not a fact about
    # the fold -- the pocket wraps round the compound, so every contact is
    # "beside" it -- so the panel starts from which end of the flat drawing
    # each contact comes off and then evens the two rows up, moving whichever
    # residue is most level with the compound, because that is the one whose
    # side was least decided in the first place. Even rows are not cosmetic:
    # an unbalanced row runs out of width and pushes a label three atoms away
    # from the thing it names, which is how Leu820's dash spent a run lying
    # along the C-Cl bond.
    reach = max(abs(y) for _, y in flat) + 7.2
    rows: dict[int, list[tuple[float, str, int, bool]]] = {-1: [], 1: []}
    near = dict(contact_residues())
    for label, ranked in contact_residues():
        atom = bonded[label][0] if label in bonded else ranked[0][1]
        side = -1 if flat[atom][1] <= 0.0 else 1
        rows[side].append((flat[atom][0], label, atom, label in bonded))
    # Even to within one, not exactly even: the last move is always the one
    # that costs most, because by then every residue left is on the side its
    # own geometry put it on.
    while abs(len(rows[-1]) - len(rows[1])) >= 3:
        heavy = -1 if len(rows[-1]) > len(rows[1]) else 1
        # A hydrogen bond moves last. Its dash carries a number and has to
        # arrive at the atom it names from the nearest clear ground; a van der
        # Waals contact is a line to a residue and can come from either side.
        moved = min(rows[heavy],
                    key=lambda e: (e[3], abs(flat[e[2]][1]), e[1]))
        rows[heavy].remove(moved)
        # Re-aimed as well as moved. A residue drawn under the compound and
        # tied to an atom above it draws its dash straight through the middle
        # of the molecule; if it also touches an atom on the side it has been
        # moved to, that is the atom to name it by.
        _x, label, atom, is_bond = moved
        if not is_bond:
            below = [(span, index) for span, index in near[label]
                     if (-1 if flat[index][1] <= 0.0 else 1) == -heavy]
            if below:
                atom = min(below)[1]
        rows[-heavy].append((flat[atom][0], label, atom, is_bond))

    for side, entries in rows.items():
        entries.sort()
        tags = []
        for _x, label, atom, is_bond in entries:
            if is_bond:
                text = f"{label} {bonded[label][1]:.1f} \u00c5"
                tag = inklet.text(text, size=TH.font_size_small,
                               text_fill=BOND_INK, kind="label")
            else:
                tag = inklet.text(label, size=TH.font_size_small,
                               text_fill=TH.muted, kind="label")
            tags.append((tag, atom, is_bond, label))
        widths = [tag.width for tag, _, _, _ in tags]
        placed = _spread([x for x, _, _, _ in entries], widths, 1.8,
                         -width / 2.0, width / 2.0)
        for at_x, (tag, atom, is_bond, label) in zip(placed, tags):
            at_y = side * reach
            items.append(((at_x, at_y), tag))
            stop = at_y - side * (tag.height / 2.0 + 0.7)
            # Backed off along the line rather than straight up: a dash that
            # comes in at a shallow angle and is only offset vertically ends
            # up running past the atom's own letter, which is how the halogen
            # contact spent a run at 0.78 mm from the Cl.
            # In bond lengths, not millimetres: the panel is built to
            # whatever width the column leaves it, and a fixed back-off that
            # looked right at 75 mm leaves a visible hole at 66.
            reach_out = (0.81 if atom in letters else 0.29) * scale
            dx = at_x - flat[atom][0]
            dy = stop - flat[atom][1]
            span = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            start = (flat[atom][0] + dx / span * reach_out,
                     flat[atom][1] + dy / span * reach_out)
            style = (dict(stroke=BOND, stroke_width=EMPHASIS,
                          stroke_dash=(0.9, 0.7))
                     if is_bond else
                     dict(stroke=GREY, stroke_width=TH.hairline,
                          stroke_dash=(0.4, 0.7)))
            items.append(annot.stroke([start, (at_x, stop)], kind="leader",
                                      **style).named(f"to-{label}"))
    return inklet.place([inklet.place(molecule,
                                kind=inklet.abutting("structural-formula")),
                      *items])

# ===========================================================================
# (d, e)  the experiment the geometry predicts
# ===========================================================================

#: Atom names that belong to the main chain. Everything else in a residue is
#: its side chain, which is the only part an alanine substitution removes.
BACKBONE = frozenset({"N", "CA", "C", "O"})


def contact_class(one: data.Variant) -> str:
    """What the compound touches at this residue: read off `RESTRAINTS`.

    Not written down here, and that is the whole point of panels (d) and (e).
    The prediction they test -- mutating the hinge does nothing, mutating the
    gatekeeper does everything -- is a prediction *because* two of the three
    bonds are made by main-chain atoms and one by a side chain. If this
    function said so in its own words it could come to disagree with the pose
    the other panels draw, and the figure would be arguing with itself.
    """
    if one.residue is None:
        return "wild type"
    for name, atom, _atom_2d, _asked in target.RESTRAINTS:
        if int(name[3:]) == one.residue:
            return "side chain" if atom not in BACKBONE else "main chain"
    return "no contact"


#: What each class is drawn in. The wild type is the compound's own colour
#: because it is the compound's own affinity; a side-chain contact is the
#: hydrogen-bond colour, because a side-chain contact is a bond a mutation can
#: take away; a main-chain contact is the N-lobe blue, which is a colour the
#: page has already spent on "part of the fold, not part of the chemistry".
CLASS_INK = {"wild type": COMPOUND_INK, "side chain": BOND_INK,
             "main chain": NLOBE_INK, "no contact": TH.muted}

#: How the classes are ordered in the key, coarsest claim first.
CLASS_ORDER = ("wild type", "main chain", "side chain", "no contact")


#: The response axis of (d), in resonance units: two units of headroom past
#: the last tick at 40, and enough below zero to show the buffer step at the
#: start of an injection dipping under the baseline.
D_BOTTOM, D_TOP = -6.0, 42.0
D_SPAN = D_TOP - D_BOTTOM


def panel_d(width: float = 100.0, height: float = 40.0) -> inklet.Diagram:
    """(d) Kinetics: the wild-type titration, and what the gatekeeper does."""
    wild = data.variant("wild type")
    broken = data.variant("T766M")
    p = inklet.panel(width, height, x=(-18.0, 660.0), y=(D_BOTTOM, D_TOP))
    p.grid(x=False, y=True, count=5, stroke=TH.grid,
           stroke_width=TH.hairline)
    # The injection, as ground rather than as a line. Everything left of its
    # right edge is association and everything right of it is dissociation,
    # and a reader who knows that reads the two rate constants straight off
    # the picture.
    p.vspan(*data.INJECTION, fill=inklet.mix(COMPOUND, TH.paper, 0.90),
            stroke="none", front=False)

    for index, molar in enumerate(data.CONCENTRATIONS):
        shade = inklet.mix(COMPOUND, TH.paper, 0.66 - 0.14 * index)
        p.line(data.sensorgram(wild, molar, seed=index), stroke=shade,
               stroke_width=TH.hairline, kind="mark-line")
        p.line(data.fitted(wild, molar), stroke=shade,
               stroke_width=EMPHASIS, kind="mark-line")
    # The mutant at the top concentration only. Five more curves would say the
    # same thing five times; one, at the concentration where the wild type is
    # nearly saturated, is the comparison.
    top = data.CONCENTRATIONS[-1]
    p.line(data.sensorgram(broken, top, seed=9), stroke=BOND,
           stroke_width=TH.hairline, kind="mark-line")
    p.line(data.fitted(broken, top), stroke=BOND, stroke_width=EMPHASIS,
           stroke_dash=(1.5, 1.1), kind="mark-line")

    # The concentrations, written on their own curves. A key would need five
    # rows to say what five numbers say here, and would say them somewhere
    # other than on the curve each belongs to.
    #
    # Each one further along the dissociation than the last: at the end of the
    # injection the top two curves are ten millimetres apart and the bottom
    # three are inside two, so five labels in a vertical line is three labels
    # on top of each other. Walking them to the right spaces them by time
    # instead, which is an axis this panel has plenty of.
    def on_curve(one: data.Variant, molar: float, when: float) -> float:
        curve = data.fitted(one, molar)
        return min(curve, key=lambda point: abs(point[0] - when))[1]

    # How tall one of these labels is in response units, measured rather than
    # assumed: the panel is built to whatever box the row leaves it, so the
    # same five millimetres of text is a different number of units each time.
    tall = inklet.text("0", size=TH.font_size_small).height * D_SPAN / height
    for index, molar in enumerate(data.CONCENTRATIONS):
        when = data.INJECTION[1] + 46.0 + 74.0 * (len(data.CONCENTRATIONS)
                                                  - 1 - index)
        level = on_curve(wild, molar, when)
        # Five units above the curve, or as much of that as fits under the
        # roof of the plot box. The top injection reaches 36 of the 40 the
        # axis is marked to and the box stops at 42, so the unclamped lift
        # puts that one label half outside the frame -- and a frame is not a
        # crowding partner, so nothing reports it. It has to be looked at.
        lift = min(5.0, D_TOP - 0.6 - tall - level)
        p.text(when, level + lift, nanomolar(molar),
               anchor="s", size=TH.font_size_small,
               text_fill=inklet.mix(COMPOUND, "#000000", 0.15), kind="label")
    p.text(520.0, on_curve(broken, top, 520.0) - 1.6,
           f"T766M, {nanomolar(top)}", anchor="n",
           size=TH.font_size_small, text_fill=BOND_INK, kind="label")

    p.axis("bottom", ticks=[0, 150, 300, 450, 600], label="time (s)")
    p.axis("left", ticks=[0, 10, 20, 30, 40], label="response (RU)")
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)
    return p.build()


def nanomolar(molar: float) -> str:
    """A concentration in the unit a reader of this panel thinks in."""
    nano = molar * 1e9
    if nano < 1.0:
        return f"{nano * 1000:.0f} pM"
    return f"{nano:.1f} nM" if nano < 10.0 else f"{nano:.0f} nM"


def panel_e(width: float = 70.0, height: float = 40.0) -> inklet.Diagram:
    """(e) Affinity across the panel: which contacts a mutation can remove."""
    names = [one.name for one in data.VARIANTS]
    p = inklet.panel(width, height, x=names, y=inklet.log((1.0e-9, 1.0e-5)))
    p.grid(x=False, y=True, count=5, stroke=TH.grid,
           stroke_width=TH.hairline)
    wild = data.VARIANTS[0]
    p.hline(wild.kd, stroke=COMPOUND, stroke_width=TH.hairline,
            stroke_dash=(1.1, 0.9))

    for one in data.VARIANTS:
        ink = CLASS_INK[contact_class(one)]
        mean, spread = data.spread(one)
        p.line([(one.name, mean * math.exp(-spread)),
                (one.name, mean * math.exp(spread))],
               stroke=ink, stroke_width=TH.stroke, kind="mark-line")
        p.marks(inklet.marker("circle", 1.5, fill=ink, stroke=TH.paper,
                           stroke_width=TH.hairline), [(one.name, mean)])
        fold = data.fold_change(one)
        p.text(one.name, mean * math.exp(spread) * 2.1,
               f"{fold:.1f}\u00d7" if fold < 10.0
               else f"{fold:,.0f}\u00d7",
               anchor="s", size=TH.font_size_small, text_fill=ink,
               kind="label")

    p.axis("bottom", label=None)
    p.axis("left", label="K_{D} (M)")
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)
    key = inklet.legend([(f"{name} contact" if name not in
                       ("wild type", "no contact") else name,
                       CLASS_INK[name]) for name in CLASS_ORDER],
                     swatch=1.5, gap=1.1, row_gap=1.15, columns=2)
    return inklet.vstack([p.build(), key], gap=2.2, align="center")


# ===========================================================================
# the page
# ===========================================================================

#: What `inklet.letters` puts on the left of a panel for the letter itself.
LETTER_SLACK = 5.0

#: How much wider than its render `panel_b` finishes, in millimetres: the
#: Met769 and Thr766 callouts hang off the left and right edges of the scene.
#: Measured, not guessed: `figures/structure.py b` prints the panel's own box
#: next to the render width it was asked for.
B_OVERHANG = 2.4

#: What `inklet.letters` costs a panel on its left, in millimetres. Two of these
#: come out of the top row's width -- one for each column -- and the budget
#: has to know about them or the row runs off the page.
LETTER_GUTTER = 3.7

#: The plot boxes of the bottom row. `panel_e` is given the shorter box on
#: purpose: its variant names are set at an angle under the axis and cost it
#: about six millimetres that `panel_d`'s plain "time (s)" does not, so equal
#: boxes would finish as unequal panels and the row would not sit straight.
D_BOX = (84.0, 40.0)
E_BOX = (58.8, 34.0)

CAPTION = (
    "**Figure 1 | How an ATP-site inhibitor reads the kinase hinge.** "
    "**(a)** The EGFR kinase domain, residues {first}-{last} of PDB 1M17 at "
    "2.6 \u00c5, as a cartoon coloured by lobe: the N lobe's twisted sheet "
    "above, the C lobe's helices below, and the strap that joins them -- the "
    "hinge, {hinge_first}-{hinge_last} -- in plum. The compound is drawn "
    "space-filling at {fill:.0%} of van der Waals radius, in the pose "
    "//tools/dock_ligand.py// found; the dashed ring is the ATP site. "
    "Scale bar 10 \u00c5. "
    "**(b)** That site, turned {turn:.0f}\u00b0 about the vertical: the "
    "\u03b25 strand, the hinge strap, and the three pocket side chains, with "
    "the hydrogen bonds dashed. The lengths are measured off the coordinates "
    "at build time rather than quoted -- {bonds} -- against the {asked} "
    "\u00c5 the docking was asked for. {facets:,} facets, depth-sorted "
    "exactly rather than by mean depth. "
    "**(c)** The same pocket flat. Every residue with a deposited atom within "
    "{contact:.1f} \u00c5 of the compound, found by searching the "
    "coordinates rather than listed here; plum dashes are the three hydrogen "
    "bonds of (b) and carry their lengths, grey the rest. The deposited entry "
    "is trimmed to the main chain plus the four pocket residues, so a residue "
    "whose side chain is not in the file is measured from its backbone and "
    "may fall outside the cut. "
    "**(d)** Surface plasmon resonance against immobilised wild-type protein: "
    "{steps} three-fold concentration steps, {inject:.0f} s of injection "
    "(shaded) and {follow:.0f} s of buffer. Thin lines are the response, "
    "heavy lines the global 1:1 fit. The gatekeeper mutant T766M, at the top "
    "concentration, is in plum. "
    "**(e)** Dissociation constant per variant, geometric mean of "
    "{reps} fits \u00b1 1 s.d. in the log, with the fold change over wild "
    "type; the dashed rule is the wild-type value. Colour is what the "
    "compound touches at that residue, read off the pose rather than "
    "asserted: Thr766 is held by its //side chain//, and T766A costs "
    "{t766a:.1f} kcal/mol and T766M {t766m:.1f}; Gln767 and Met769 are held "
    "by //main-chain// atoms, which an alanine cannot take away, and neither "
    "substitution moves the affinity by more than {control:.1f}-fold. "
    "**The structure is real (PDB 1M17); all assay data are simulated.** "
    "There was no binding experiment: the compound does not exist, the "
    "mutants were never made, and every number in (d) and (e) comes out of "
    "figures/structure_data.py from a stated seed. The protein, the fold and "
    "every distance in (a)-(c) are the deposited coordinates."
)


def caption(facets: int) -> inklet.Diagram:
    """The caption, with every number in it read from what was drawn."""
    here = target.structure()
    bonds = "; ".join(f"{name} {span:.2f}"
                      for name, _p, _l, span in target.contacts())
    asked = ", ".join(f"{wanted:.1f}" for _n, _a, _l, wanted
                      in target.RESTRAINTS)
    controls = max(data.fold_change(data.variant(name))
                   for name in ("Q767A", "M769A"))
    text = CAPTION.format(
        first=here.residues[0].number, last=here.residues[-1].number,
        hinge_first=HINGE_RUN[0], hinge_last=HINGE_RUN[1] - 1,
        fill=FILL, turn=VIEW_B[0] - VIEW[0], bonds=bonds, asked=asked,
        facets=facets, contact=CONTACT, steps=len(data.CONCENTRATIONS),
        inject=data.INJECTION[1] - data.INJECTION[0], follow=data.FOLLOW,
        reps=len(data.replicates(data.VARIANTS[0])),
        t766a=data.ddg(data.variant("T766A")),
        t766m=data.ddg(data.variant("T766M")), control=controls)
    return inklet.text(text, size=TH.font_size_small * 0.94, align="justify",
                    width=CONTENT, text_fill=TH.muted, kind="caption")


#: The narrowest a gap between two panels is allowed to get while a row is
#: being squared up. Below this the row is genuinely overfull and the panels
#: have to shrink; above it, the leftovers of the column arithmetic are worth
#: less than a rebuild.
MIN_GAP = 3.0


def _gap(*panels: inklet.Diagram) -> float:
    """The gap that makes a row exactly `CONTENT` wide.

    The column widths below are arithmetic off measured panels, and a
    measurement can miss by a tenth of a millimetre in either direction: a
    panel overhangs its own render by however much label it has. Absorbing
    that in the gap costs nothing a reader can see. Letting it off the right
    edge of the page costs two `OFF_CANVAS` errors, and leaving it as slack
    on the right costs a row that does not reach the caption under it.
    """
    spare = CONTENT - sum(panel.width for panel in panels)
    return max(MIN_GAP, spare / (len(panels) - 1))


def build() -> inklet.Figure:
    """The whole page: five panels and the caption.

    The columns are sized off the hero rather than by hand. `panel_a` is as
    wide as `HERO` plus whatever its callouts stick out by, which depends on
    the projection, so the right column is measured from the drawn panel and
    the two panels in it are built to fit. Whatever is left over after that
    goes into the gap between the columns instead of off the edge of the
    page: a row that is 0.2 mm too wide is two `OFF_CANVAS` errors, and a gap
    that is 0.2 mm wider than `GAP` is nothing at all.
    """
    hero = panel_a()
    column = CONTENT - hero.width - GAP - 2.0 * LETTER_GUTTER
    site, facets = panel_b(width=column - B_OVERHANG)
    a, b, c, d, e = inklet.letters([hero, site, panel_c(width=column),
                                 panel_d(*D_BOX), panel_e(*E_BOX)])
    right = inklet.vstack([b, c], gap=GAP, align="left")
    top = inklet.hstack([a, right], align="top", gap=_gap(a, right))
    bottom = inklet.hstack([d, e], align="top", gap=_gap(d, e))
    fig = inklet.figure(width=f"{PAGE}mm", theme=TH, margin=MARGIN)
    fig.add(inklet.vstack([top, bottom, caption(facets)], gap=GAP + 1.5,
                       align="left"))
    return fig


#: Every panel by its letter, for the single-panel preview below. The point of
#: it is that a panel can be looked at at working size without waiting for the
#: other four, which on this page is the difference between a second and eight.
PANELS = {
    "a": panel_a,
    "b": lambda: panel_b()[0],
    "c": panel_c,
    "d": panel_d,
    "e": panel_e,
}


def main(argv: list[str]) -> int:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    if len(argv) > 1 and argv[1] in PANELS:
        letter = argv[1]
        panel = PANELS[letter]()
        # Cropped to the panel rather than left on a double-column page: the
        # point of the preview is to look at one panel at working size, and a
        # panel floating in 110 mm of white rasterises to a picture that is
        # mostly margin. Its own box is printed below, which is where
        # `B_OVERHANG` and the column budget in `build` come from.
        fig = inklet.figure(width=panel.width + 2.0 * MARGIN + LETTER_GUTTER,
                         theme=TH, margin=MARGIN)
        fig.add(inklet.letters([panel], start=letter)[0])
        print(f"panel {letter}  {panel.width:.2f} x {panel.height:.2f} mm")
        path = out / f"structure_panel_{letter}.svg"
    else:
        fig = build()
        path = out / "structure.svg"
    fig.save(path, compact=True)
    body, _ = fig.build()
    print(f"{path}  {body.width:.1f} x {body.height:.1f} mm")
    print(fig.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
