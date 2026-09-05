"""Figure 1 of a cheminformatics paper: 38 drugs seen through their fingerprints.

One argument in eight panels. **(a)** says which compounds are alike, and says
it in an order that makes the answer visible: the Tanimoto matrix, seriated by
optimal leaf ordering of an average-linkage tree, with the dendrogram that
produced the order drawn over it. **(b)** says what a fingerprint cannot --
which named substructures each compound actually contains, matched by explicit
subgraph isomorphism and drawn against the same ordering, so a block in (a)
lines up row for row with the fragments that make it one. **(c)** draws one
compound from each block properly, and **(d)** takes the first of them off the
page and into three dimensions, because a structural formula is a graph drawn
flat and a molecule is not flat. **(e)** is the same matrix as (a) in
alphabetical order, the honest "before", since alphabetical is the order a
supplementary table arrives in. **(f)** asks whether the blocks are blocks.
**(g)** checks the fingerprint against the seventeen hand-written queries,
which share nothing but the molecular graphs they are both computed from.
**(h)** is the whole set at once: the compounds as points in three dimensions,
from the Tanimoto distances alone.

Everything chemical is computed in `chem_data.py` and nothing is looked up:
no RDKit, no network, no cached descriptor file. The compounds are real, their
structures are SMILES parsed into explicit graphs, and every graph reproduces
its compound's published molecular formula -- which is the test that a string
typed from memory is the compound it is labelled with. The two three-
dimensional panels are computed there too, by the same forty-line eigensolver:
one embeds the distances between compounds, the other the distances inside one
of them.

    .venv/bin/python figures/chem_fingerprints.py          # build, lint, save
    .venv/bin/python figures/chem_fingerprints.py c        # one panel
    .venv/bin/python figures/chem_fingerprints.py sheet    # all 38 structures
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inklet

from inklet import three

import annot
import bio3d
import chem_data as chem

TH = inklet.use_theme("nature")

PAGE = getattr(inklet, "COLUMN_DOUBLE", 183.0)
MARGIN = 4.0
CONTENT = PAGE - 2 * MARGIN
GAP = 5.0

#: Three colour systems, each confined to what it means, and no fourth. The
#: ramp is *quantity* and appears only where a Tanimoto coefficient is drawn.
#: `BLOCK_COLORS` is *identity*: one hue per computed block, used on the block
#: numbers in (a) -- which is where the reader learns the key -- and on the
#: spheres in (h). `ELEMENTS` is the CPK convention every chemist already
#: knows, used on one molecule in (d). Everything else on the page is ink and
#: muted grey, which is what keeps the three legible.
SHADES = inklet.ramp("tol-ylorbr")
ACCENT = TH.accent
QUIET = TH.muted

#: One colour per block of (a), in block order. The theme's series is
#: Okabe-Ito, eight hues chosen to survive the common colour-vision
#: deficiencies, and nine blocks need one more than it has: the ninth is the
#: theme's muted grey. Black goes to the anilinoquinazolines and grey to the
#: sulfonamides deliberately -- they are the two blocks that sit furthest from
#: everything else in (h), where a neutral is easiest to follow. The series'
#: pale yellow is the one hue left out: it is illegible as a 5 pt numeral in
#: (a)'s gutter and it disappears entirely as a lit sphere in (h), so the
#: profens take the theme's darker ochre instead. The black is lightened by a
#: sixth of the way to paper: pure black takes no shading, so in (h) it turned
#: eight spheres into eight holes in the page, and #262626 is still plainly
#: the black of the nine at a millimetre and a half.
BLOCK_COLORS = (tuple(TH.color(i) for i in (1, 2, 3, 9, 5, 6, 7))
                + (inklet.mix(TH.color(0), TH.paper, 0.15), TH.muted))

#: CPK, near enough: carbon pale, nitrogen blue, oxygen red, chlorine green.
#: The four elements in the compound (d) draws, and no others, because a key
#: for elements that are not there is a key for nothing.
ELEMENTS = {"C": inklet.mix(TH.ink, TH.paper, 0.42), "N": TH.color(5),
            "O": TH.color(6), "Cl": TH.color(3)}


# ===========================================================================
# structural formulas
# ===========================================================================
#
# The house style of `figures/target.py`: a hexagonal-grid skeleton, single
# lines for the bonds, an inner circle for an aromatic ring, and a letter only
# where the atom is not carbon. The difference is that this figure draws
# thirty-eight compounds rather than one, so the coordinates come from
# `chem.depiction()` -- a layout under a test that asserts uniform bond
# length, no crossing bonds and no two unbonded atoms on top of each other --
# instead of being laid out by hand. Every one of them was rasterised at print
# scale and looked at before it shipped; the test is what stops the next one
# regressing.

#: Clear air between a bond and the letter it arrives at, in millimetres.
#: The letter's own box is measured; this is only the margin round it. A line
#: that runs into its letter reads as a strikethrough, and a line that stops
#: a whole letter-width short leaves the atom floating.
LETTER_CLEAR = 0.28

#: Separation of the two lines of a double bond, in bond lengths.
DOUBLE = 0.13


def _label(atom: chem.Atom) -> str | None:
    """What to write at an atom, or None for a plain carbon vertex.

    Hydrogens are written on the heteroatoms that carry them, because "OH" and
    "O" are different functional groups and a structural formula that draws
    both as O is ambiguous about the compound. Carbons never get a letter,
    hydrogens on carbon are never drawn: that is what a skeletal formula is.
    """
    if atom.element == "C":
        return None
    if atom.hydrogens == 0:
        return atom.element
    if atom.hydrogens == 1:
        return f"{atom.element}H"
    return f"{atom.element}H_{{{atom.hydrogens}}}"


def _aromatic_rings(mol: chem.Molecule,
                    where: tuple[tuple[float, float], ...]
                    ) -> list[tuple[tuple[float, float], float]]:
    """Centre and radius of every ring drawn with an inner circle.

    A ring qualifies when every one of its bonds is aromatic. The circle is
    the other standard way to draw an aromatic ring -- one stroke instead of
    three Kekule lines -- and it is the right one here because the parser
    never Kekulises: it would be dishonest to draw alternating bonds the graph
    does not claim.
    """
    found = []
    for ring in mol.rings():
        bonds = [mol.bond_between(a, b)
                 for a, b in zip(ring, ring[1:] + ring[:1])]
        if not all(bond is not None and bond.aromatic for bond in bonds):
            continue
        centre = (sum(where[a][0] for a in ring) / len(ring),
                  sum(where[a][1] for a in ring) / len(ring))
        radius = min(math.dist(centre, where[a]) for a in ring)
        found.append((centre, radius * 0.62))
    return found


def formula(mol: chem.Molecule, *, bond_mm: float, ink: str | None = None,
            size: float | None = None) -> inklet.Diagram:
    """One compound as a structural formula, at `bond_mm` per bond.

    Returned in its own drawn frame, declared `inklet.abutting` so that the
    letters sitting in the gaps of their own bonds -- which is what a formula
    is -- are not reported as thirty crowded pairs. The declaration covers the
    molecule and nothing else: anything placed beside it is still checked.
    """
    ink = ink or TH.ink
    size = size or TH.font_size_small
    flat = chem.depiction(mol)
    # y grows downward on the page and upward in the layout, so the drawing is
    # flipped once here rather than in the geometry, which stays mathematical.
    at = [(x * bond_mm, -y * bond_mm) for x, y in flat]
    letters = {i: inklet.text(text, size=size, text_fill=ink, kind="atom")
               for i, text in ((i, _label(a)) for i, a in enumerate(mol.atoms))
               if text}
    # Half the box each letter actually occupies. The vertical figure is the
    # ink rather than the line box: `inklet.text` reserves a full line of leading
    # and a bond that stopped at the leading would leave "OH" adrift from the
    # carbon it hangs off by most of a millimetre.
    room = {i: (art.width / 2.0, art.height * 0.36)
            for i, art in letters.items()}

    items: list = []
    for bond in mol.bonds:
        start, end = at[bond.a], at[bond.b]
        along = _direction(start, end)
        start = _step(start, along, _trim(room.get(bond.a), along))
        end = _step(end, along, -_trim(room.get(bond.b), along))
        across = (-along[1] * DOUBLE * bond_mm, along[0] * DOUBLE * bond_mm)
        offsets = {1: (0.0,), 2: (-1.0, 1.0), 3: (-1.0, 0.0, 1.0)}[bond.order]
        if bond.aromatic:
            offsets = (0.0,)
        for shift in offsets:
            items.append(inklet.polyline(
                [(start[0] + across[0] * shift, start[1] + across[1] * shift),
                 (end[0] + across[0] * shift, end[1] + across[1] * shift)],
                stroke=ink, stroke_width=TH.hairline, kind="bond"))
    for (cx, cy), radius in _aromatic_rings(mol, flat):
        # `annot.ring` and not `inklet.circle`: a circle is a box underneath and
        # takes no `kind`, and this one has to be tagged as part of the
        # molecule rather than as a container round it.
        items.append(annot.ring((cx * bond_mm, -cy * bond_mm),
                                radius * 2.0 * bond_mm, radius * 2.0 * bond_mm,
                                kind="bond", stroke=ink,
                                stroke_width=TH.hairline))
    for index, art in sorted(letters.items()):
        items.append((at[index], art))
    return inklet.place(items, kind=inklet.abutting("structural-formula"))


def _direction(start, end) -> tuple[float, float]:
    span = math.dist(start, end) or 1.0
    return ((end[0] - start[0]) / span, (end[1] - start[1]) / span)


def _step(point, along, distance) -> tuple[float, float]:
    return (point[0] + along[0] * distance, point[1] + along[1] * distance)


def _trim(box: tuple[float, float] | None, along: tuple[float, float]) -> float:
    """How far along a bond its letter reaches, plus the margin.

    Where the ray leaves the letter's own box, which is what makes "NH_2"
    push a horizontal bond further away than a vertical one -- the same
    number for both directions either cuts into the wide label or hangs the
    tall one in space.
    """
    if box is None:
        return 0.0
    half_w, half_h = box
    reach = min(half_w / abs(along[0]) if abs(along[0]) > 1e-9 else 1e9,
                half_h / abs(along[1]) if abs(along[1]) > 1e-9 else 1e9)
    return reach + LETTER_CLEAR


def sheet() -> inklet.Figure:
    """Every compound in the set, drawn, for looking at.

    Not part of the figure. It is the working view: thirty-eight structural
    formulas out of one layout rule, on one page, at the size panel (c) draws
    them -- which is the only way to find the one that comes out wrong.
    """
    cells = []
    for compound, mol in zip(chem.COMPOUNDS, chem.molecules()):
        art = formula(mol, bond_mm=2.6)
        name = inklet.text(compound.name, size=TH.font_size_small,
                        text_fill=TH.muted)
        cells.append(inklet.pad(inklet.vstack([art, name], gap=1.0), 1.5))
    fig = inklet.figure(width=f"{PAGE}mm", theme=TH, margin=MARGIN)
    fig.add(inklet.grid(cells, cols=5, gap=2.0))
    return fig



# ===========================================================================
# the compound axis, shared by (a) and (b)
# ===========================================================================
#
# Panels (a) and (b) are one picture cut in two: the same thirty-eight
# compounds, in the same computed order, on rows of the same pitch, so a block
# of similarity in (a) reads straight across into the fragments that make it
# one in (b). The pitch is therefore a page-level constant, not a panel one.

#: Compound names are set at this size and the row pitch is derived from it
#: rather than the other way round. Five point is the floor the linter enforces
#: and the floor a printed figure deserves; a matrix whose row labels had to be
#: thinned out to fit is a matrix without row labels.
NAME_PT = 5.0

#: Row pitch in millimetres: one line of `NAME_PT` type plus a hair. The hair
#: is what keeps two names' line boxes from overlapping -- at exactly the line
#: height they would touch, and OVERLAP is an error rather than an opinion.
PITCH = 2.42

#: Air to the left of the names, the width of the block gutter between them
#: and the matrix, and how tall the dendrogram strip over the matrix is.
NAME_GAP = 1.2
GUTTER = 4.1
DENDRO = 12.0

#: The one scale on the page that turns a number into a colour. Built once and
#: handed to both the matrix and its colorbar, which is what `Panel.matrix`
#: asks for: two scales that agree today are how a key stops describing its
#: picture. The domain is the whole range a Tanimoto coefficient can take, not
#: the range this set happens to occupy -- a coefficient is comparable between
#: papers only if the key says 0 to 1.
HEAT = inklet.linear((0.0, 1.0))


def _names(order: tuple[int, ...]) -> inklet.Diagram:
    """The compound names as one right-aligned block of type.

    A `inklet.vstack` and not thirty-eight separate placements, because the stack
    is what lets the linter read the six tenths of a millimetre between two
    names as leading rather than as a crowding fault -- which is the truth:
    the space between two lines of type is set in ems, and this one is a
    quarter of the type size. The stack's pitch is `PITCH` by construction, so
    centring it on the matrix lands every name on its own row without the
    figure computing a second set of coordinates that could drift from the
    first.
    """
    line = inklet.text("Ag", size=inklet.pt(NAME_PT)).height
    return inklet.vstack(
        [inklet.text(chem.COMPOUNDS[i].name, size=inklet.pt(NAME_PT),
                  text_fill=TH.ink) for i in order],
        gap=PITCH - line, align="right")


def _rows(p: inklet.Panel, count: int) -> tuple[float, float, float]:
    """(left edge, top edge, millimetres per row) of a panel's plot area.

    Read back out of the panel's own scales rather than recomputed from
    `PITCH`, so that anything hung beside the matrix is positioned by the
    same mapping that placed the cells.
    """
    left = p.point(0, 0).x
    top = p.point(0, 0).y
    return left, top, (p.point(0, count).y - top) / count


def _dendrogram(p: inklet.Panel, count: int) -> float:
    """The tree the ordering came out of, drawn over the matrix it ordered.

    Heights are cophenetic distances and they run *downward* from the top of
    the strip, so a late merge -- the one joining two blocks that have little
    in common -- sits far from the matrix, and the reader can see which
    divisions in the picture the tree thinks are the deep ones. Returns the
    tallest merge, because the caption quotes the scale and a number quoted
    from anywhere but the drawing is a number that can go stale.
    """
    rungs = chem.dendrogram()
    tallest = max(rung[2] for rung in rungs)
    left, top, pitch = _rows(p, count)
    lines = []
    for x0, x1, height, base in rungs:
        y_top = top - DENDRO * (height / tallest)
        y_base = top - DENDRO * (base / tallest)
        xa, xb = left + (x0 + 0.5) * pitch, left + (x1 + 0.5) * pitch
        lines.append(inklet.polyline([(xa, y_base), (xa, y_top),
                                   (xb, y_top), (xb, y_base)],
                                  stroke=TH.ink, stroke_width=TH.hairline,
                                  fill="none", kind="tree"))
    # Declared abutting: a tree's rungs meet its uprights, which is the
    # drawing working rather than two hundred crowded pairs.
    p.over(inklet.place(lines, kind=inklet.abutting("dendrogram")), clip=False)
    return tallest


def panel_matrix() -> tuple[inklet.Diagram, float]:
    """(a) The Tanimoto matrix in the order the tree chose, with the tree.

    Everything here is computed. The coefficients, the order of the rows, the
    tree over them, and the nine boxes on the diagonal -- which come from
    `chem.blocks()`, a function that raises if a textbook class is not a
    single unbroken run of the computed order. The boxes are a result, not an
    annotation drawn over one.
    """
    order = chem.seriation()
    sim = chem.similarity()
    n = len(order)
    side = PITCH * n
    p = inklet.panel(side, side, x=(0, n), y=(n, 0))
    p.matrix([[sim[i][j] for j in order] for i in order],
             ramp=SHADES, scale=HEAT,
             x=[i + 0.5 for i in range(n)], y=[i + 0.5 for i in range(n)])
    left, top, pitch = _rows(p, n)
    marks = []
    for number, block in enumerate(chem.blocks(order), start=1):
        p.rect(block.first, block.first, block.last + 1.0, block.last + 1.0,
               fill="none", stroke=TH.ink, stroke_width=TH.hairline,
               front=True)
        first, last = top + block.first * pitch, top + (block.last + 1) * pitch
        rule = left - 0.7
        # The gutter rule carries the block's colour and the numeral stays ink.
        # That pairing is the whole key for (h) -- nine numbered blocks here,
        # nine coloured clusters there, and no swatch table on the page -- and
        # it is this way round because a 5 pt numeral in Okabe-Ito orange on
        # white is a 2.3:1 contrast ratio, which the linter is right to refuse.
        # A bar can carry a hue at any contrast; a letterform cannot.
        marks.append(inklet.polyline([(rule, first + 0.2), (rule, last - 0.2)],
                                  stroke=BLOCK_COLORS[number - 1],
                                  stroke_width=inklet.mm(0.7), kind="tick"))
        marks.append(((rule - 1.7, (first + last) / 2.0),
                      inklet.text(str(number), size=inklet.pt(NAME_PT),
                               text_fill=TH.ink)))
    p.over(inklet.place(marks), clip=False)
    names = _names(order)
    p.over(inklet.place([((left - GUTTER - NAME_GAP - names.width / 2.0,
                        top + n * pitch / 2.0), names)]), clip=False)
    tallest = _dendrogram(p, n)
    p.colorbar(side="right", length=30.0, label="Tanimoto", pad=1.8)
    return p.build(), tallest


def panel_incidence() -> inklet.Diagram:
    """(b) Which named fragment is in which compound, on (a)'s rows.

    A dot matrix rather than a heatmap: containment is a yes or a no, and a
    ramp over two values invites the reader to look for a quantity that is not
    there. Columns are ordered by how many compounds carry the fragment, so
    the vocabulary reads from the near-universal benzene on the left to the
    three-compound beta-lactam on the right, and the blocks show up as the
    right-hand columns switching on and off together.
    """
    order = chem.seriation()
    inc = chem.incidence()
    n = len(order)
    columns = sorted(range(len(chem.FRAGMENTS)),
                     key=lambda f: (-sum(inc[f]), chem.FRAGMENTS[f].name))
    width = PITCH * len(columns)
    p = inklet.panel(width, PITCH * n, x=(0, len(columns)), y=(n, 0))
    left, top, pitch = _rows(p, n)
    hits = [(column + 0.5, row + 0.5)
            for column, f in enumerate(columns)
            for row, compound in enumerate(order) if inc[f][compound]]
    p.marks(inklet.marker("square", size=pitch * 0.56, fill=TH.ink,
                       stroke="none"), hits, name="contains")
    for block in chem.blocks(order)[:-1]:
        # The block rules are the only thing in (b) that is not a measurement:
        # they are (a)'s boxes, carried across so the eye can land on the same
        # nine runs in both panels without counting rows.
        p.hline(block.last + 1.0, stroke=TH.grid, stroke_width=TH.hairline,
                front=True)
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)
    line = inklet.text("Ag", size=inklet.pt(NAME_PT)).height
    labels = [inklet.text(chem.FRAGMENTS[f].name, size=inklet.pt(NAME_PT),
                       text_fill=TH.ink).rotated(-90.0) for f in columns]
    # Declared abutting, and this is the one declaration on the page that is
    # a workaround rather than a fact: these are column headings set at the
    # pitch of the columns they name, which is the same thing the linter
    # already forgives between two lines of horizontal type -- but its leading
    # test only looks for a *vertical* gap, so rotated headings fall through
    # it. Filed as the BACKLOG item "_is_leading is blind to rotated type".
    strip = inklet.hstack(labels, gap=PITCH - line, align="bottom")
    p.over(inklet.place([((left + width / 2.0, top - 0.9 - strip.height / 2.0),
                       inklet.place([strip], kind=inklet.abutting("headings")))]),
           clip=False)
    return p.build()


def panel_alphabetical(width: float, height: float) -> inklet.Diagram:
    """(e) The same matrix in alphabetical order: the honest before.

    Alphabetical is not a straw man. It is the order a supplementary table
    arrives in and the order this figure's own data file is written in, and
    the point of the panel is that the same 1,444 numbers carry no visible
    structure until something computes an order for them.
    """
    sim = chem.similarity()
    n = len(sim)
    p = inklet.panel(width, height, x=(0, n), y=(n, 0))
    p.matrix([[sim[i][j] for j in range(n)] for i in range(n)],
             ramp=SHADES, scale=HEAT,
             x=[i + 0.5 for i in range(n)], y=[i + 0.5 for i in range(n)])
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)
    p.title(inklet.text("alphabetical order", size=TH.font_size_small,
                     text_fill=TH.muted))
    return p.build()


def panel_spread(width: float, height: float) -> inklet.Diagram:
    """(f) Is a block a block? Every within-class coefficient, drawn.

    A swarm and not a bar of means, because there are between three and
    fifteen pairs in a class and a mean of three numbers drawn as a bar is
    the part of a figure a reader cannot check. The grey band behind is the
    middle half of the 636 coefficients that cross a class boundary, so the
    question -- do the classes separate? -- is answered by looking at how far
    each swarm sits above it, and the honest answer is *mostly*: the band's
    top is 0.14 and three classes have a pair below 0.3.
    """
    per_class = chem.block_similarity()
    outside = sorted(v for _, _, out in per_class for v in out)
    quarter = outside[len(outside) // 4]
    three_quarter = outside[3 * len(outside) // 4]
    labels = [str(i) for i in range(1, len(per_class) + 1)]
    p = inklet.panel(width, height, x=labels, y=(0.0, 1.0))
    p.hspan(quarter, three_quarter, fill=inklet.mix(QUIET, TH.paper, 0.82))
    p.swarm({label: list(inside)
             for label, (_, inside, _) in zip(labels, per_class)},
            size=0.85, colors=[ACCENT] * len(labels))
    p.axes(x="class", y="Tanimoto within class")
    return p.build()


def panel_agreement(width: float, height: float) -> tuple[inklet.Diagram, float]:
    """(g) The fingerprint against the fragment vocabulary, over all 703 pairs.

    Two descriptions of the same 38 graphs that share no code: one is a hash
    of every atom neighbourhood out to two bonds, folded into 2,048 bits; the
    other is seventeen queries somebody typed and a backtracking search. They
    are not measuring the same thing -- a fingerprint counts every
    neighbourhood, the vocabulary counts the ones with names -- so the
    agreement is evidence that the fingerprint is finding chemistry rather
    than finding hash structure, and the scatter of it is the honest picture
    of how much the two disagree on any given pair.
    """
    sim = chem.similarity()
    n = len(sim)
    pairs = [(sim[i][j], chem.fragment_jaccard(i, j))
             for i in range(n) for j in range(i + 1, n)]
    rho = chem.spearman([x for x, _ in pairs], [y for _, y in pairs])
    p = inklet.panel(width, height, x=(0.0, 1.0), y=(0.0, 1.0))
    p.scatter(pairs, size=0.7, color=ACCENT, fill_opacity=0.45,
              stroke="none")
    p.axes(x="Tanimoto", y="fragment Jaccard")
    # Bottom right: the corner two descriptions of one molecule cannot both
    # reach, since a high Tanimoto with no shared named fragment would mean the
    # hash found a similarity the vocabulary has no word for.
    p.text(0.97, 0.03, f"rho = {rho:.2f}", anchor="se",
           size=TH.font_size_small, text_fill=TH.ink)
    return p.build(), rho


#: One compound per block, in block order, for panel (c). Chosen for being the
#: member a chemist would name first, and checked against the depiction test
#: like every other structure in the set -- not chosen for drawing tidily.
DRAWN = ("diazepam", "diclofenac", "aspirin", "naproxen", "penicillin G",
         "adrenaline", "propranolol", "gefitinib", "sulfamethoxazole")


def panel_structures(bond_mm: float) -> inklet.Diagram:
    """(c) Nine compounds drawn, one from each block of (a).

    Numbered with the blocks, so the reader who wants to know what block 5 is
    can look it up in the picture rather than in the caption. Skeletal
    formulas in the house style of `figures/target.py`: carbon unlettered,
    heteroatoms lettered with the hydrogens they carry, an inner circle for an
    aromatic ring. The coordinates come from `chem.depiction()`.
    """
    order = chem.seriation()
    numbers = {}
    for number, block in enumerate(chem.blocks(order), start=1):
        for position in range(block.first, block.last + 1):
            numbers[order[position]] = number
    cells = []
    for name in DRAWN:
        index = chem.NAMES.index(name)
        art = formula(chem.molecules()[index], bond_mm=bond_mm)
        label = inklet.text(f"**{numbers[index]}**  {name}",
                         size=inklet.pt(NAME_PT + 0.5), text_fill=TH.ink)
        cells.append(inklet.vstack([art, label], gap=1.2, align="center"))
    # `hstack` and not `grid`: a grid gives every column the width of the
    # widest structure in it, and gefitinib is two and a half times the width
    # of adrenaline. Nine equal columns would be nine gefitinib-widths, which
    # does not fit the page and would space the small molecules out as if the
    # gaps meant something. Packed by their real widths they fit in one row,
    # which is what puts all nine blocks in front of the reader at once.
    return inklet.hstack(cells, gap=2.4, align="bottom")


# ===========================================================================
# three dimensions
# ===========================================================================
#
# Two panels and one method. `chem.mds` embeds a distance matrix in three
# dimensions; (d) hands it the distances inside one molecule and (h) hands it
# the distances between all thirty-eight. Both are drawn with `inklet.three`
# rather than as a flat scatter with a fake perspective, which buys three
# things a 2-D plot of 3-D data cannot have: the spheres occlude each other,
# so depth is unambiguous; the shading is a real light on a real surface, so a
# sphere in front reads as in front; and the whole thing is still vector line
# art that prints at any size.

#: The conformer panel's compound. Diazepam because it is the one compound in
#: the set whose 2-D formula is actively misleading about its shape: the
#: seven-membered ring is not planar and the pendant phenyl is not in the
#: plane of the benzo ring, and (c) draws it flat first so the reader can see
#: exactly what the flat drawing left out.
EMBODIED = "diazepam"

#: Angstrom radii for the ball-and-stick. Not van der Waals radii -- those
#: would touch and hide the bonds -- but the usual illustrative fractions of
#: them, kept in proportion to each other so chlorine still reads as the big
#: atom it is.
BALL = {"C": 0.33, "N": 0.32, "O": 0.31, "Cl": 0.42, "S": 0.40, "F": 0.28,
        "Br": 0.45}
STICK = 0.11

#: Azimuth and elevation for each 3-D panel, in degrees, both chosen by
#: rendering the alternatives and looking at them. The conformer is seen
#: nearly down the normal of its benzo ring, tilted enough that the pucker of
#: the seven-membered ring and the twist of the phenyl are both visible --
#: face-on the molecule would look flat, which is the one thing this panel
#: exists to deny. The cloud is seen from low down and a little round, where
#: its three tightest blocks separate instead of stacking and the second
#: principal coordinate is still a visible direction rather than a dot -- at
#: an azimuth of zero the triad's middle arrow points at the reader and the
#: panel loses the axis it is trying to name.
CONFORMER_VIEW = (0.0, 55.0)
SPACE_VIEW = (25.0, 20.0)

#: How the light falls on both scenes. The defaults wash a small sphere out to
#: near-white, which is fine for one grey solid and fatal for nine categorical
#: colours at a millimetre and a half: `lift` is pulled down and `shade` up so
#: that the hue survives the shading and blue can still be told from sky at
#: print scale. Chosen by rendering the nine together and looking.
LIGHT = {"lift": 0.06, "shade": 0.45}


def panel_conformer(width: float) -> inklet.Diagram:
    """(d) One compound as a shape, from the bonding alone.

    Distance geometry, computed in `chem_data.py`: bond lengths from a table,
    bond angles from hybridisation, planar aromatic rings from the same flat
    layout (c) draws, embedded by classical multidimensional scaling and
    relaxed against those distances. No force field, no experimental
    coordinates, no torsion term -- so the panel says "a conformer", the
    caption says how far the result is from the geometry it was asked for, and
    `chem.conformer_error` measures that on every build.

    Atoms are grouped into one part per element rather than one part per atom:
    thirty-nine parts would each be painted separately and a ball would show
    through a stick, and `order="exact"` settles depth facet by facet across
    the whole assembly, which is what a ball-and-stick needs and what a
    painter's ordering by part centroid cannot give.
    """
    mol = chem.molecules()[chem.NAMES.index(EMBODIED)]
    points = chem.conformer(mol)
    groups: dict[str, list] = {}
    for index, atom in enumerate(mol.atoms):
        groups.setdefault(atom.element, []).append(
            bio3d.ball(points[index], BALL.get(atom.element, 0.33),
                       subdivisions=1))
    parts = [("bonds", three.merge([bio3d.stick(points[bond.a], points[bond.b],
                                                STICK) for bond in mol.bonds]),
              {"color": inklet.mix(TH.ink, TH.paper, 0.55)})]
    parts += [(element, three.merge(balls),
               {"color": ELEMENTS.get(element, TH.ink)})
              for element, balls in sorted(groups.items())]
    scene = inklet.scene(parts, width=width, view=CONFORMER_VIEW, style="shaded",
                      order="exact", depth_cue=0.18, **LIGHT,
                      stroke_width=TH.hairline, name="conformer")
    label = inklet.text(f"**{EMBODIED}** {{muted|as a shape}}",
                     size=inklet.pt(NAME_PT + 0.5), text_fill=TH.ink)
    return inklet.vstack([scene, label], gap=1.0, align="center")


def panel_space(width: float) -> inklet.Diagram:
    """(h) The whole set as a cloud: principal coordinates of 1 - Tanimoto.

    Classical multidimensional scaling of the same distances (a) shows as a
    matrix, which is the same information asked a different question: not
    "which pairs are alike" but "what shape is the set". A sphere per
    compound, coloured by the block it fell in -- the colours the numbers in
    (a)'s gutter carry -- and sized so that its volume is its molecular mass,
    which is the only honest thing a size can be here and is at least a
    reminder that the fingerprint does not know how big a molecule is.

    Three axes carry a third of the positive eigenvalue mass and the caption
    says so. That is not a failure of the method, it is what a 2048-bit space
    is like, and the point of the panel is not the coordinates but the fact
    that nine blocks found in the matrix are nine clumps in the cloud.
    """
    coords, _ = chem.chemical_space()
    masses = [mol.mass() for mol in chem.molecules()]
    heaviest = max(masses)
    order = chem.seriation()
    colour = {block.klass: BLOCK_COLORS[i]
              for i, block in enumerate(chem.blocks(order))}
    groups: dict[str, list] = {}
    for index, compound in enumerate(chem.COMPOUNDS):
        radius = SPHERE * (masses[index] / heaviest) ** (1.0 / 3.0)
        groups.setdefault(compound.klass, []).append(
            bio3d.ball(coords[index], radius, subdivisions=2))
    parts = [(block.klass.replace(" ", "-").replace("/", "-"),
              three.merge(groups[block.klass]), {"color": colour[block.klass]})
             for block in chem.blocks(order)]
    # `order="parts"` and not `"exact"`: these spheres do not interpenetrate,
    # so painting whole blocks back to front by depth is exact already, and it
    # costs a tenth of what the facet-by-facet sort costs.
    scene = inklet.scene(parts, width=width, view=SPACE_VIEW, style="shaded",
                      order="parts", depth_cue=0.30, **LIGHT,
                      stroke_width=TH.hairline, name="space")
    frame = three.axes(width=width * 0.17, view=SPACE_VIEW,
                       labels=("PC1", "PC2", "PC3"),
                       label_size=inklet.pt(NAME_PT), style="lineart",
                       ink=QUIET, stroke_width=TH.hairline, name="pc-axes")
    box = scene.bbox
    # The triad goes in the corner the cloud leaves empty. The first principal
    # coordinate is almost entirely the sulfonamides' distance from everything
    # else, so at this view the cloud is a mass on the left and one island out
    # to the right of centre, and the top right corner is empty by
    # construction. It is placed off the scene's own box rather than by a
    # guessed offset, so it stays in the corner when the panel is resized.
    return inklet.place([((0.0, 0.0), scene),
                      ((box.width / 2.0 - frame.width / 2.0,
                        -box.height / 2.0 + frame.height / 2.0), frame)])


#: What each panel is asked for, in millimetres, in one place. The two rows
#: under the matrix are packed by width: nine structures and a conformer make
#: the first, and four plots the second, and every one of these numbers is the
#: largest that leaves the page 183 mm wide and inside Nature's 247 mm depth.
STRUCTURE_BOND = 2.2
CONFORMER_MM = 29.0
FOIL_MM = (18.0, 24.0)
SPREAD_MM = (36.0, 24.0)
AGREEMENT_MM = (30.0, 24.0)
SPACE_MM = 44.0

#: Sphere radius in (h) for the heaviest compound, in the units the embedding
#: came out in -- the cloud is about one unit across, so this is a sphere
#: about a twelfth of the picture wide.
SPHERE = 0.040


# ===========================================================================
# the page
# ===========================================================================

CAPTION = (
    "**Thirty-eight drugs, ordered by what they are made of.** Every number "
    "here is computed in `figures/chem_data.py` from SMILES strings and "
    "nothing else -- no RDKit, no descriptor file, no network. Each string is "
    "parsed into an atom-and-bond graph with aromaticity, formal charge and "
    "implicit hydrogens from a valence table, and every graph reproduces its "
    "compound's published molecular formula: the check that a string typed "
    "from memory is the compound it names. **(a)** Tanimoto over "
    "ECFP4-style circular fingerprints -- Morgan identifiers to radius "
    "{radius}, hashed with FNV-1a (64-bit, fixed offset and prime, where "
    "Python's `hash()` is salted per run) and folded to {bits:,} bits. It is "
    "lossy and the cost is measured: {raw:,} identifiers share {bits:,} slots "
    "with {collisions} collisions, raising the median coefficient by "
    "{median:.3f} and the worst by {worst:.3f}. Rows follow the tree above "
    "them -- average linkage over 1 - Tanimoto, leaves flipped by Bar-Joseph "
    "optimal leaf ordering, the exact dynamic program; tallest merge "
    "{tallest:.3f}. The ordering never sees a compound's class, and all nine "
    "still come out as unbroken runs, boxed on the diagonal and numbered in "
    "the gutter, whose coloured bars are (**h**)'s colours: {legend}. A "
    "random ordering does that with probability {odds}. "
    "Mean rank separation per unit of similarity falls from {before:.2f} rows "
    "alphabetically (**e**; {expected:.1f} for a shuffle) through {tree:.2f} "
    "for the tree's own leaf order to {after:.2f}; summed adjacent-row "
    "similarity rises from {near_before:.1f} to {near_after:.1f}. **(b)** "
    "Seventeen named fragments, each a query graph in the same dialect, "
    "matched by explicit subgraph isomorphism over the real graphs -- nothing "
    "inferred from the fingerprint or from the class. **(c)** One compound "
    "per block, from computed coordinates: carbon unlettered, heteroatoms "
    "with their hydrogens, an inner circle for a ring whose every bond is "
    "aromatic. **(d)** The first of them as a shape, by distance geometry -- "
    "bond lengths tabulated, angles from hybridisation, aromatic rings held "
    "planar, torsions free -- embedded by the eigensolver (**h**) uses and "
    "relaxed against those distances. No force field, no experimental "
    "coordinates; what it is is measured every build: bonds within "
    "{bond_error:.1f}% of table, angles within {angle_error:.1f} degrees, no "
    "unbonded pair closer than {contact:.2f} A. The seven-membered ring comes "
    "out {pucker:.2f} A rms from planar and the phenyl {twist:.0f} degrees "
    "out of the benzo plane; the formula in (**c**) says neither. Carbon "
    "grey, {{series5|nitrogen}}, {{series6|oxygen}}, {{series3|chlorine}}; "
    "hydrogens counted, never drawn. **(e)** Alphabetical order recovers one "
    "block by accident -- the six names beginning *sulfa* -- and scatters the "
    "other eight. **(f)** Every within-class coefficient as a point; the grey "
    "band is the interquartile range of the {crossing} that cross a class "
    "boundary. **(g)** The two descriptions over all {pairs} pairs, Spearman "
    "rho = {rho:.2f}: they share the graphs and nothing else. **(h)** Those "
    "distances as a shape instead of a table: classical multidimensional "
    "scaling, three leading eigenvectors of the double-centred matrix by "
    "power iteration, carrying {explained:.0%} of its positive eigenvalue "
    "mass. A sphere per compound, volume proportional to mass, coloured by "
    "block; the first coordinate is almost all the sulfonamides' distance "
    "from the rest."
)


def caption() -> inklet.Diagram:
    """The caption, with every number in it read out of the same functions the
    panels are drawn from. Nothing here is typed twice."""
    order = chem.seriation()
    sim = chem.similarity()
    alphabetical = tuple(range(len(order)))
    median, worst = chem.folding_cost()
    raw = len({i for mol in chem.molecules()
               for i in chem.identifiers(mol, chem.RADIUS)})
    per_class = chem.block_similarity()
    # `block_similarity` reports each class's outgoing coefficients, so a
    # cross-boundary pair appears in two classes' lists. Panel (f) pools them
    # -- harmless for a quartile, since duplicating every value leaves the
    # quantiles where they were -- but the caption must quote the number of
    # pairs there are, not the number of times they were counted.
    crossing = sum(len(out) for _, _, out in per_class) // 2
    n = len(order)
    pairs = n * (n - 1) // 2
    exponent = int(math.floor(math.log10(chem.contiguity_odds(order))))
    legend = "; ".join(
        f"{number} {block.klass}"
        for number, block in enumerate(chem.blocks(order), start=1))
    embodied = chem.molecules()[chem.NAMES.index(EMBODIED)]
    bond_error, angle_error, contact = chem.conformer_error(embodied)
    seven = max(embodied.rings(), key=len)
    text = CAPTION.format(
        radius=chem.RADIUS, bits=chem.BITS, raw=raw,
        bond_error=bond_error, angle_error=angle_error, contact=contact,
        pucker=chem.ring_pucker(embodied, seven),
        twist=chem.aromatic_ring_angle(embodied),
        explained=chem.chemical_space()[1],
        collisions=chem.bit_collisions(), median=median, worst=worst,
        tallest=max(rung[2] for rung in chem.dendrogram()),
        legend=legend, odds=f"1 in 10^{-exponent}",
        before=chem.band_energy(alphabetical, sim),
        expected=(n + 1) / 3.0,
        tree=chem.band_energy(chem.dendrogram_order(), sim),
        after=chem.band_energy(order, sim),
        near_before=chem.neighbour_similarity(alphabetical, sim),
        near_after=chem.neighbour_similarity(order, sim),
        crossing=crossing, pairs=pairs, rho=RHO[0],
    )
    return inklet.text(text, size=TH.font_size_small * 0.94, width=CONTENT,
                    align="justify", text_fill=TH.ink)


#: Panel (g) computes the correlation the caption quotes, and the caption is
#: built after the panels. A one-slot box rather than a global, so the value
#: can only be the one this build measured.
RHO: list[float] = [0.0]


def build() -> inklet.Figure:
    """The whole page: eight panels and the caption."""
    top, _ = panel_matrix()
    fragments = panel_incidence()
    structures = panel_structures(STRUCTURE_BOND)
    shape = panel_conformer(CONFORMER_MM)
    foil = panel_alphabetical(*FOIL_MM)
    swarm = panel_spread(*SPREAD_MM)
    scatter, rho = panel_agreement(*AGREEMENT_MM)
    RHO[0] = rho
    cloud = panel_space(SPACE_MM)

    a, b, c, d, e, f, g, h = inklet.letters(
        [top, fragments, structures, shape, foil, swarm, scatter, cloud])
    # `inklet.row` and not `hstack`: it lines up plot *areas*, which is what makes
    # (b)'s rows land on (a)'s rows even though (a) carries fifteen
    # millimetres of dendrogram above its area and (b) carries a strip of
    # rotated headings of a different height above its own.
    upper = inklet.row([a, b], gap=GAP, align="top")
    # The flat drawings and the embedded one are one row on purpose: the
    # reader meets diazepam as a formula and then, four centimetres to the
    # right, as an object, and the two are the same compound at the same
    # moment rather than on facing pages.
    middle = inklet.hstack([c, d], gap=GAP, align="bottom")
    # The three plots line up on their plot areas; the cloud is hung beside
    # them with `hstack`, because `row` aligns *areas* and a scene has none --
    # asked to align to a plot box it does not have, it lands four millimetres
    # lower and makes the row four millimetres taller for nothing.
    lower = inklet.hstack([inklet.row([e, f, g], gap=GAP, align="top"), h],
                       gap=GAP, align="top")
    fig = inklet.figure(width=f"{PAGE}mm", theme=TH, margin=MARGIN)
    fig.add(inklet.vstack([upper, middle, lower, caption()], gap=GAP - 1.9,
                       align="left"))
    return fig


#: Every panel on its own, for the preview path. Panel (a) is the one that
#: takes seconds to build, and being able to look at (c) without it is most of
#: what iterating on a molecule drawing is.
PANELS: dict[str, object] = {
    "a": lambda: panel_matrix()[0],
    "b": panel_incidence,
    "c": lambda: panel_structures(STRUCTURE_BOND),
    "d": lambda: panel_conformer(CONFORMER_MM),
    "e": lambda: panel_alphabetical(*FOIL_MM),
    "f": lambda: panel_spread(*SPREAD_MM),
    "g": lambda: panel_agreement(*AGREEMENT_MM)[0],
    "h": lambda: panel_space(SPACE_MM),
    "sheet": None,
}


def main(argv: list[str]) -> int:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    want = argv[1] if len(argv) > 1 else ""
    if want == "sheet":
        fig, path = sheet(), out / "chem_sheet.svg"
    elif want in PANELS:
        fig = inklet.figure(width=f"{PAGE}mm", theme=TH, margin=MARGIN)
        fig.add(inklet.letters([PANELS[want]()], start=want)[0])
        path = out / f"chem_{want}.svg"
    else:
        fig, path = build(), out / "chem_fingerprints.svg"
    fig.save(path)
    body, _ = fig.build()
    print(f"{path}  {body.width:.1f} x {body.height:.1f} mm")
    print(fig.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
