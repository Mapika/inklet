"""A drug-discovery figure: target, binding, series, and trial.

Seven panels telling one story end to end -- what the compound binds, how it
binds, what the chemistry did to the series, what it does in cells, and what
happened in people. It exists to push `inklet` at the kind of figure that decides
whether a paper is read: a real 3D structure, a true zoom of it, a matrix, a
survival plot with its risk table, and a hundred-odd labels that all have to
miss each other.

**Every number in it is simulated.** See `trial.py` -- there is no DGM-431.

Run it with no arguments to build the whole page; pass a panel letter to build
just that one, which is how it was developed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inklet

import annot
from inklet.three import protein as cartoon   # was figures/cartoon.py
import target
import trial

TH = inklet.use_theme("nature")

PAGE = 178.0
GAP = 5.0

# --- the palette this figure speaks in -------------------------------------
#: The ribbons are mixed toward paper *here*, in the palette, rather than by
#: turning `lift=` up in the shading. The two are interchangeable for one
#: colour and not for five: the lift applies to the whole mesh, and the whole
#: mesh includes the compound, which is the one thing on the page that has to
#: stay saturated. Pale is a decision about the protein, not about the light.
BODY = inklet.mix(TH.ink, TH.paper, 0.77)            # coil: the connective tissue
HELIX = inklet.mix("#009e73", TH.paper, 0.49)        # alpha helices
SHEET = inklet.mix("#0072b2", TH.paper, 0.60)        # beta strands
DRUG = "#d95f02"                                  # DGM-431, everywhere it appears
DRUG_INK = inklet.mix(DRUG, "#000000", 0.22)         # the same orange, legible as type
SIDECHAIN = inklet.mix("#5f6b7a", TH.paper, 0.38)    # pocket residues
BOND = "#0072b2"                                  # hydrogen bonds
BOND_INK = inklet.mix(BOND, "#000000", 0.18)         # the same blue, legible as type
GREY = inklet.mix(TH.ink, TH.paper, 0.35)   # dark enough to be read as type

#: What each face group of `target.fold()` is painted. Colour by secondary
#: structure, which is the convention every structural paper uses, rather than
#: by the features this panel happens to label: a reader who has seen one
#: cartoon knows that the flat arrows are strands without being told, and the
#: labels are then free to name places rather than colours.
CARTOON = {"helix": HELIX, "strand": SHEET, "coil": BODY,
           "ligand": DRUG, "side-chain": SIDECHAIN}

#: The one heavy weight in the figure. Three widths is the linter's budget for
#: a page, and the shipped theme already spends two of them on hairlines and
#: ordinary strokes -- so every line that has to read as emphasis, a fitted
#: curve or a hydrogen bond, is this one width and no other.
EMPHASIS = 0.40

#: Azimuth and elevation. `target.orientation()` has already stood the molecule
#: up -- N lobe above C lobe, cleft towards the reader -- so the only thing
#: left to choose is how far to lean, and it was chosen by rendering the sweep.
#: Below about 30 degrees of elevation the compound is seen edge-on and reads
#: as a line of beads; above about 44 the camera looks down into the cleft and
#: the two lobes flatten into each other.
VIEW = (-12.0, 38.0)
WIDE = 68.0          # panel (a): the whole fold
CLOSE = 132.0        # panel (b): the same projection, about twice as big


def fold(width: float) -> inklet.Diagram:
    """The protein at one magnification, with every point a label may want.

    One mesh with five face groups rather than five meshes -- see
    `target.fold` for why -- so `colors=` is what keeps the ribbons, the
    compound and the side chains apart.

    `crease=45` inks the ribbon's own edge. A ribbon's edge is a rounded
    corner spread over a fan of facets whose dihedrals run from twenty degrees
    to ninety, so a bare threshold anywhere in between cuts through the middle
    of that fan and draws a band of near-parallel lines down both sides of
    every ribbon -- which is why this used to be `crease=180`, silhouette and
    nothing else. `ridges=True`, the default, keeps only the steepest edge
    across such a fan and drops its neighbours, so the band collapses to the
    one line a pen would draw and a threshold is usable again.

    Forty-five rather than thirty because a threshold has to clear the
    sampling as well as the shape: at 13 points round the section the coil's
    own facets meet at 360/13, near enough twenty-eight degrees, and a
    threshold below that inks the tube's longitudinal seams. Forty-five sits
    above the tessellation and below the ribbon's corner.

    `depth_cue` is the other thing that separates this from a flat-shaded
    solid: a fold doubles back over itself constantly, and shading alone says
    which way a surface faces, never which of two surfaces is nearer.

    **`shading="smooth"` with `levels=12`, not flat with 48.** The two numbers
    move together. Flat shading gives a facet one tone whatever the ramp is
    cut into, so 48 steps were free and bought a coil whose facets were at
    least small steps rather than large ones. Smooth shading cuts the bands
    out of the surface instead, so it pays for every step a triangle spans --
    and it does not need many, because the thing 48 was hiding was the
    staircase, and there is no staircase left to hide. Twelve smooth steps
    read as a rounder object than forty-eight flat ones and leave a *third*
    fewer elements on the page, since a coarser ramp is fewer distinct fills:
    10,555 elements down to 6,989. The bytes go the other way, 2.0 MB to
    3.0 MB, because a band boundary is a curve across the model where a facet
    boundary was three points. It is worth it here for one specific reason:
    the coil is a 13-sided tube and flat shading drew all thirteen of its
    sides.

    **The ribbon is sampled for the size it is about to be.** `page_scale`
    says what a millimetre is worth in angstroms at this width and
    `cartoon.sides_for` turns that into a point count round the section: 13
    points at 68 mm and 18 at 132, so the wide panel carries two thirds of the
    geometry of the close one instead of the same amount drawn smaller.

    `smooth=90` is what makes 13 points enough. It puts the silhouette on the
    surface the facets stand for rather than on the facets: a ribbon is nearly
    tangent to the view over long stretches, and there the facet outline is a
    zig-zag through the interior that grows a black fan at every helix end
    below about sixteen points. It is said out loud here because the default
    takes its threshold from `crease`, and `crease=45` would hand the smooth
    pass a right angle's worth of surface it is entitled to treat as curved.
    `inklet.three.model(smooth=)` is the long version.
    """
    anchors = {}
    for name, protein, tip, _ in target.contacts():
        anchors[f"{name}-tip"] = protein          # the atom that makes the bond
        anchors[f"{name}-atom"] = tip             # the compound's end of it
    # Measured on one mesh and used to build the real one. Changing the
    # sampling moves the projected bounds by the chord error itself -- under a
    # tenth of a millimetre on a 68 mm panel -- so the scale does not need
    # asking twice; `inklet.three.page_scale` has the long version. The probe asks
    # for `SIDES` by name rather than by omission so that the common answer
    # lands on the same `functools.cache` key and no mesh is built twice.
    probe = target.fold(sides=cartoon.SIDES)
    scale = inklet.three.page_scale(probe, width=width, view=VIEW)
    node = inklet.three.model(
        target.fold(sides=cartoon.sides_for(scale)),
        width=width, view=VIEW, style="shaded", colors=CARTOON,
        crease=45.0, smooth=90.0, shading="smooth", levels=12,
        depth_cue=0.35, lift=0.20, shade=0.40,
        stroke_width=TH.hairline, anchors=anchors, name="kinase")
    # The five named features get their anchors *after* the render, because
    # which residue of a run a leader should touch depends on what the fold
    # puts in front of it -- and that is only knowable once there is a drawing
    # to look at. `pick="visible"` rasterises this one once and reuses it.
    for name, run in target.label_runs().items():
        inklet.three.anchor3d(node, name, run, pick="visible")
    return node


def tagged(letter: str, body: inklet.Diagram) -> inklet.Diagram:
    """A panel with its letter on the top left, clear of the content."""
    mark = inklet.text(letter, size=TH.font_size_large, font_weight="bold",
                    kind="panel-tag")
    # Outside the content's own box, not tucked into its corner: a y-axis
    # label reaches the corner, and a letter sitting on it is the one collision
    # every multi-panel figure has.
    return inklet.place([
        ((0.0, 0.0), body),
        ((-body.width / 2 - mark.width / 2 - 1.6,
          -body.height / 2 + mark.height / 2), mark)])


# --- (a) the target --------------------------------------------------------

def panel_a() -> inklet.Diagram:
    scene = fold(WIDE)
    pocket = annot.at(scene, "ligand")
    # Five features, not eight. The activation loop and the linker are real
    # parts of the fold and are drawn, but naming them costs two more leaders
    # across the middle of a 68 mm picture and neither is in the story panel
    # (b) goes on to tell.
    labels = [
        ("β sheet", "sheet", (-40.0, -27.0)),
        ("αC helix", "helix-c", (40.0, -44.0)),
        ("P-loop", "p-loop", (40.0, -16.0)),
        ("hinge", "hinge", (-36.0, 8.0)),
        ("C lobe", "c-lobe", (-36.0, 40.0)),
    ]
    items: list[annot.Item] = []
    for text, point, where in labels:
        items += annot.leader(text, annot.at(scene, point), where)
    # `kind="mark"`, not "callout": the ring is centred on the projected pocket
    # anchor, so where it sits is the model speaking. Declared as furniture it
    # reports four findings for enclosing the thing it is drawn to enclose.
    ring = annot.ring((pocket[0] + 1.5, pocket[1]), 22.0, 13.5,
                      name="pocket", stroke=DRUG,
                      stroke_width=TH.stroke, stroke_dash=(1.3, 0.9),
                      kind="mark")
    # Aimed at an atom of the compound rather than at an offset from the pocket
    # anchor: the offset was measured against an earlier ligand and, once the
    # molecule was redrawn, quietly landed on the P-loop above it instead.
    #
    # This is the one label on the page that cannot be moved clear. The cleft
    # is in the middle of the fold, the only ground within reach of it at this
    # page width is a millimetre off the C lobe, and every alternative -- top
    # right, bottom right -- buys the clearance with a leader across the whole
    # beta sheet. So it stays, and the touch is declared rather than reported.
    line, name = annot.leader("DGM-431", annot.at(scene, "Met769-atom"),
                              (33.0, -4.0), ink=DRUG_INK, size=TH.font_size)
    # The ring and that one label are on the fold on purpose, and saying so is
    # cheaper than the two CROWDING infos they otherwise report every run --
    # an author reading the report has to re-derive "yes, that is the drawing"
    # each time, and a report with two known lines in it is a report nobody
    # reads. `inklet.abutting` is scoped to this subtree and symmetric, so it
    # covers ring-against-fold and label-against-fold and nothing else: the
    # five leaders stay outside it and go on being checked against the model,
    # including the five PATH_CROSSES warnings they earn for running over it.
    on_the_fold = inklet.drawn([scene, ring, name],
                            kind=inklet.abutting("on-the-fold"))
    return annot.on(on_the_fold, *items, line)


# --- (b) the binding site --------------------------------------------------

#: The crop, in the coordinates panel (b)'s own scene is drawn in, and how far
#: above the compound to centre it. All three hydrogen bonds run to protein
#: atoms above and to the left of the compound -- that is what a hinge binder
#: is -- so a window centred on the compound itself puts the topmost of them
#: on the edge. Two millimetres of headroom is what it takes to have all three
#: partners inside the frame with their labels beside them.
WINDOW = (58.0, 44.0)
RAISE = 2.0

def panel_b() -> inklet.Diagram:
    scene = fold(CLOSE)
    centre = annot.at(scene, "ligand")
    centre = (centre[0], centre[1] - RAISE)
    window = annot.zoom(scene, centre, *WINDOW)
    here = lambda name: annot.moved(centre, annot.at(scene, name))
    half_w, half_h = WINDOW[0] / 2, WINDOW[1] / 2

    # Measured off the docked pose and the deposited coordinates, every build.
    # The label and the dash therefore cannot come to disagree: they are two
    # readings of the same pair of atoms.
    measured = {name: distance for name, _, _, distance in target.contacts()}

    # Each leader lands on the protein end of its own dash. Gln767's is a
    # backbone oxygen tucked behind a ring of the compound and the leader
    # therefore stops on top of drawn atoms -- which is what the structure
    # does, and better than pointing somewhere clearer that is not the atom
    # the number was measured to.
    items: list[annot.Item] = []
    for name in measured:
        items.append(annot.stroke([here(f"{name}-tip"), here(f"{name}-atom")],
                                  stroke=BOND, stroke_width=EMPHASIS,
                                  stroke_dash=(0.85, 0.65), kind="hbond"))

    # Name and distance in one label, outside the window. Written on the bond
    # itself the number is unreadable -- a 54 x 36 mm crop of a protein has no
    # clear ground left -- and a plate behind it only hides more of the thing
    # the panel is a zoom of. Out here the blue ties it to its own dash.
    def tag(name: str) -> inklet.Diagram:
        # Stacked, not side by side: the panel is 86 mm wide once both margins
        # carry a label, and every millimetre of that comes off the picture.
        return inklet.vstack([
            inklet.text(name, size=TH.font_size_small, kind="label"),
            inklet.text(f"{measured[name]:.1f} Å", size=TH.font_size_small,
                     text_fill=BOND_INK, kind="label")], gap=0.5,
            align="center")

    # All three on the left, in the order their partners stack up the page.
    # A label on the right would be tidier and every one of its leaders would
    # cross the compound to get to a protein atom on the far side of it -- and
    # a line through the molecule reads as a bond, which is the one thing a
    # panel about bonds cannot afford.
    for name, where in (("Thr766", (-half_w - 9.5, -12.0)),
                        ("Gln767", (-half_w - 9.5, 0.5)),
                        ("Met769", (-half_w - 9.5, 13.0))):
        items += annot.leader(tag(name), here(f"{name}-tip"), where, ink=TH.ink)

    frame = inklet.polygon([(-half_w, -half_h), (half_w, -half_h),
                         (half_w, half_h), (-half_w, half_h)],
                        stroke=DRUG, stroke_width=TH.stroke, fill="none",
                        kind="callout").named("window")

    # What ties this to (a) is the orange: the dashed ring there and this frame
    # are the only two orange outlines on the page. A wedge between them is the
    # better convention and was tried first -- but the ring sits in the middle
    # of the fold, so every line out of it to the right crosses the hinge
    # helix, the ligand and the "hinge" label. A caption crosses nothing.
    caption = inklet.text("the pocket ringed in (a), at twice the magnification",
                       size=TH.font_size_small, text_fill=DRUG_INK,
                       kind="caption")
    return inklet.vstack([annot.on(window, *items, ((0.0, 0.0), frame)), caption],
                      gap=1.8, align="center")


# --- (c) the compound ------------------------------------------------------

#: Half the gap between the two lines of a double bond, in panel-(c) mm.
DOUBLE = 0.55

def panel_c() -> inklet.Diagram:
    """The same skeleton panels (a) and (b) bind, drawn flat.

    Straight off `target.skeleton()`, so the structural formula cannot come to
    disagree with the thing in the pocket -- which is the usual way a
    medicinal-chemistry figure goes wrong.
    """
    atoms, bonds, named = target.skeleton()
    scale = 4.0
    where = [(x * scale, -y * scale) for x, y in atoms]
    labelled = {index: text for text, index in
                ((target.ELEMENTS[key], named[key]) for key in target.ELEMENTS)}

    def draw(start, end):
        lines.append(annot.stroke([start, end], stroke=TH.ink,
                                  stroke_width=TH.stroke, kind="bond"))

    lines = []
    for a, b, order, inner in bonds:
        # Stop short at a labelled atom so the bond does not run under its
        # letter; the letter is the atom, and a line through it reads as a bond
        # to somewhere else.
        start, end = where[a], where[b]
        for index, point in ((a, "start"), (b, "end")):
            if index in labelled:
                other = end if point == "start" else start
                here = where[index]
                dx, dy = other[0] - here[0], other[1] - here[1]
                span = max((dx * dx + dy * dy) ** 0.5, 1e-6)
                shifted = (here[0] + dx / span * 1.8, here[1] + dy / span * 1.8)
                if point == "start":
                    start = shifted
                else:
                    end = shifted
        if order == 1:
            draw(start, end)
            continue
        dx, dy = end[0] - start[0], end[1] - start[1]
        span = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        nx, ny = -dy / span, dx / span
        if inner is None:
            # A carbonyl: two lines of the same length, either side of centre.
            for sign in (1.0, -1.0):
                draw((start[0] + nx * DOUBLE * sign, start[1] + ny * DOUBLE * sign),
                     (end[0] + nx * DOUBLE * sign, end[1] + ny * DOUBLE * sign))
            continue
        # A ring: the main line on the bond, the second one inside it and
        # shortened, which is how a Kekule ring is drawn and read.
        cx, cy = inner[0] * scale, -inner[1] * scale
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        sign = 1.0 if (cx - mid[0]) * nx + (cy - mid[1]) * ny > 0 else -1.0
        draw(start, end)
        trim = 0.18
        draw((start[0] + dx * trim + nx * DOUBLE * 1.7 * sign,
              start[1] + dy * trim + ny * DOUBLE * 1.7 * sign),
             (end[0] - dx * trim + nx * DOUBLE * 1.7 * sign,
              end[1] - dy * trim + ny * DOUBLE * 1.7 * sign))
    for index, text in labelled.items():
        lines.append(annot.text_at(text, where[index], size=TH.font_size,
                                   text_fill=TH.ink, kind="atom"))
    structure = inklet.place(lines)

    # Every number that also appears somewhere else on the page is read from
    # the same place that panel draws it from. Written out by hand this table
    # said 74-fold while (d) titrated 1,900-fold and (e) shaded a third figure.
    # Every number here is read from the place the rest of the page draws it
    # from: the formula and the weight are counted off the very bonds drawn to
    # the left, the potencies come from the curves in (d). Written by hand this
    # table said 74-fold while (d) titrated 1,900-fold and (e) shaded a third
    # figure, and quoted a weight the structure beside it does not add up to.
    # cLogP is gone rather than invented -- nothing on the page could check it.
    facts = (("target", "KIN-A"),
             ("formula", target.formula()),
             ("MW", f"{target.mass():.1f}"),
             ("IC_{50}, enzyme", f"{trial.COMPOUNDS[0][1] * 1e9:.1f} nM"),
             ("IC_{50}, cells", f"{trial.CELL_IC50 * 1e9:.0f} nM"),
             ("selectivity vs KIN-B", f"{trial.selectivity_fold():,.0f}-fold"))
    rows = [inklet.hstack([inklet.text(name, size=TH.font_size_small,
                                 text_fill=TH.muted, align="left"),
                        inklet.spacer(0.01, 0.01),
                        inklet.text(value, size=TH.font_size_small, align="right")],
                       gap=1.4, align="baseline")
            for name, value in facts]
    table = inklet.vstack(rows, gap=1.1, align="left")
    caption = inklet.text("DGM-431", size=TH.font_size, font_weight="bold",
                       text_fill=DRUG_INK)
    # Side by side. Stacked, the panel is 35 mm wide and sits under a 86 mm
    # zoom, leaving a hand-sized hole in the middle of the page; laid out this
    # way the two fill the column and the panel gets shorter as well.
    return inklet.hstack([structure, inklet.vstack([caption, table], gap=2.4,
                                             align="left")],
                      gap=4.0, align="center")


# --- (d) in vitro potency --------------------------------------------------

def panel_d() -> inklet.Diagram:
    def nano(value: float) -> str:
        for cut, suffix in ((1e5, "100k"), (1e4, "10k"), (1e3, "1k")):
            if abs(value - cut) < cut * 0.01:
                return suffix
        return f"{value:g}"

    def potency(molar: float) -> str:
        nano = molar * 1e9
        return f"{nano:.1f} nM" if nano < 1000 else f"{nano / 1000:.1f} µM"

    p = inklet.panel(78.0, 40.0, x=inklet.log((0.08, 2.0e5)), y=(-4.0, 106.0))
    p.grid(x=False, y=True, count=6, stroke=TH.grid,
           stroke_width=TH.hairline)
    p.under(inklet.polyline([(p.x.map(0.08), p.y.map(50.0)),
                          (p.x.map(2.0e5), p.y.map(50.0))],
                         stroke=inklet.mix(TH.muted, TH.paper, 0.55),
                         stroke_width=TH.hairline, stroke_dash=(1.0, 0.9)))

    series = [(name, ic50, slope, top, DRUG if index == 0 else
               inklet.mix(TH.ink, TH.paper, 0.10 + 0.25 * index))
              for index, (name, ic50, slope, top) in enumerate(trial.COMPOUNDS)]
    series.append((trial.COUNTER[0], *trial.COUNTER[1:], BOND))

    for index, (name, ic50, slope, top, colour) in enumerate(series):
        dashed = {"stroke_dash": (1.6, 1.1)} if index == len(series) - 1 else {}
        smooth = [(d * 1e9, trial.hill(d, ic50, slope, top))
                  for d in (10.0 ** (-10.0 + 0.06 * step) for step in range(101))]
        p.line(smooth, stroke=colour, stroke_width=EMPHASIS,
               kind="mark-line", **dashed)
        points = trial.response(ic50, slope, top, seed=1700 + index)
        for dose, mean, spread in points:
            p.line([(dose * 1e9, mean - spread), (dose * 1e9, mean + spread)],
                   stroke=colour, stroke_width=TH.stroke, kind="mark-line")
        p.marks(inklet.marker("circle", 1.05, fill=colour, stroke=TH.paper,
                           stroke_width=TH.hairline),
                [(dose * 1e9, mean) for dose, mean, _ in points])

    # The lead compound's IC50 as a rule down to the axis. No text on it: the
    # potencies are in the key, which is the one place in a crowded panel that
    # is guaranteed to have room for them.
    at = p.x.map(trial.COMPOUNDS[0][1] * 1e9)
    p.over(inklet.polyline([(at, p.y.map(-4.0)), (at, p.y.map(50.0))],
                        stroke=DRUG, stroke_width=TH.hairline,
                        stroke_dash=(0.9, 0.8)))
    p.axis("bottom", ticks=[0.1, 1, 10, 100, 1e3, 1e4, 1e5], format=nano,
           label="compound (nM)")
    p.axis("left", ticks=[0, 25, 50, 75, 100], label="inhibition (%)")
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)

    # Under the plot in two columns rather than beside it. A key on the right
    # costs 40 mm of page for four short rows, and the sigmoid has no free
    # corner to hide it in: the lead compound is at the top by 30 nM and the
    # counter-screen is along the bottom for the whole first decade.
    key = inklet.legend([(f"{name}  {potency(ic50)}", colour)
                      for name, ic50, _, _, colour in series],
                     swatch=1.5, gap=1.1, row_gap=1.15, columns=2,
                     title="IC_{50}, enzyme")
    return inklet.vstack([p.build(), key], gap=2.4, align="center")


# --- (e) selectivity across the panel --------------------------------------

def panel_e() -> inklet.Diagram:
    values = trial.selectivity()
    order = list(reversed(trial.KINASES))          # KIN-A at the top
    rows = list(reversed(values))
    short = [name.split("-")[1] for name in trial.SERIES]

    shades = inklet.ramp("tol-ylorbr")
    key_scale = inklet.linear((4.5, 9.5))
    p = inklet.panel(34.0, 56.0, x=short, y=order)
    p.matrix(rows, ramp=shades, scale=key_scale, x=short, y=order)
    p.outline(stroke=TH.ink, stroke_width=TH.hairline)
    p.axis("bottom", ticks=short, tick_size=0.6, tick_pad=1.0,
           label="DGM- compound")
    p.axis("left", ticks=order, tick_size=0.6, tick_pad=1.0, spine=False)

    # The target row, called out where the eye lands rather than in the caption.
    top = p.point(short[0], "KIN-A").y
    p.over(inklet.text("target", size=TH.font_size_small, text_fill=DRUG_INK,
                    align="left", kind="callout")
           .translated(p.width / 2 + 5.0, top))

    key = inklet.colorbar(shades, domain=(4.5, 9.5), scale=key_scale,
                       length=30.0, thickness=2.4, label="pIC_{50}",
                       ticks=[5, 6, 7, 8, 9], thin=False,
                       format=lambda v: f"{v:g}")
    return inklet.hstack([p.build(), key], gap=3.0, align="center")


# --- (f) progression-free survival -----------------------------------------

def _steps(points):
    """A survival curve as a staircase: hold, then drop."""
    out = [points[0]]
    for when, estimate in points[1:]:
        out.append((when, out[-1][1]))
        out.append((when, estimate))
    return out


def panel_f() -> inklet.Diagram:
    p = inklet.panel(64.0, 40.0, x=(0.0, trial.FOLLOW_UP), y=(0.0, 100.0))
    p.grid(x=False, y=True, count=5, stroke=TH.grid, stroke_width=TH.hairline)
    colours = (DRUG, GREY)
    for arm in (0, 1):
        steps, censored, _ = trial.survival(arm)
        p.line([(t, s * 100.0) for t, s in _steps(steps)],
               stroke=colours[arm], stroke_width=EMPHASIS,
               kind="mark-line")
        marks = []
        for when in censored:
            # The *last* step at or before the censoring, not the largest.
            # `max` over a decreasing series is always its first element, which
            # drew every tick on the 100% line: a solid bar across the top of
            # the panel saying nothing about when anyone actually left.
            level = next((s for t, s in reversed(steps) if t <= when), 1.0)
            marks.append((when, level * 100.0))
        p.marks(inklet.polyline([(0.0, -0.85), (0.0, 0.85)], stroke=colours[arm],
                             stroke_width=TH.stroke, kind="mark-line"),
                marks)
        median = trial.median_survival(arm)
        p.over(inklet.polyline([(p.x.map(median), p.y.map(0.0)),
                             (p.x.map(median), p.y.map(50.0))],
                            stroke=colours[arm], stroke_width=TH.hairline,
                            stroke_dash=(0.8, 0.7)))
    p.over(inklet.polyline([(p.x.map(0.0), p.y.map(50.0)),
                         (p.x.map(trial.median_survival(1)), p.y.map(50.0))],
                        stroke=TH.muted, stroke_width=TH.hairline,
                        stroke_dash=(0.8, 0.7)))
    p.axis("bottom", ticks=list(trial.RISK_TIMES), label="months from randomisation")
    p.axis("left", ticks=[0, 25, 50, 75, 100], label="progression-free (%)")
    p.outline(stroke=TH.grid, stroke_width=TH.hairline)

    summary = inklet.vstack([
        inklet.text(trial.hazard_text(), size=TH.font_size_small),
        inklet.text(f"median {trial.median_survival(0):.1f} vs "
                 f"{trial.median_survival(1):.1f} months",
                 size=TH.font_size_small, text_fill=TH.muted)],
        gap=0.8, align="left")

    built = p.build()
    ox, oy = annot.origin_of(built)
    table: list[annot.Item] = []
    heading = inklet.text("No. at risk", size=TH.font_size_small * 0.92,
                       text_fill=TH.muted, align="right", kind="risk-head")
    table.append(((ox - p.width / 2 - heading.width / 2 - 1.5,
                   oy + p.height / 2 + 10.6), heading))
    for arm in (0, 1):
        _, _, remaining = trial.survival(arm)
        for mark, count in zip(trial.RISK_TIMES, remaining):
            table.append(((ox + p.x.map(float(mark)),
                           oy + p.height / 2 + 8.6 + arm * 4.2),
                          inklet.text(str(count), size=TH.font_size_small * 0.92,
                                   text_fill=(DRUG_INK, GREY)[arm],
                                   kind="risk")))
    key = inklet.legend([(trial.ARMS[0][0], DRUG), (trial.ARMS[1][0], GREY)],
                     swatch=1.5, gap=1.1, row_gap=1.15)
    body = inklet.place([((0.0, 0.0), built), *table])
    # Below, not beside: the hazard ratio is a 40 mm line of type, and hanging
    # it off the right of a 64 mm plot spends more of the page on the sentence
    # than on the curves it describes.
    return inklet.vstack([body, inklet.hstack([key, summary], gap=5.0, align="top")],
                      gap=3.0, align="center")


# --- (g) best response -----------------------------------------------------

RESPONSE_COLOURS = {"complete": "#1b5e20", "partial": DRUG,
                    "stable": inklet.mix(TH.ink, TH.paper, 0.45),
                    "progressive": BOND}

def panel_g() -> inklet.Diagram:
    changes = trial.waterfall()
    p = inklet.panel(66.0, 40.0, x=(-0.6, len(changes) - 0.4), y=(-100.0, 55.0))
    for level, dash in ((trial.PARTIAL, (1.1, 0.9)), (trial.PROGRESSION, (1.1, 0.9))):
        p.under(inklet.polyline([(p.x.map(-0.6), p.y.map(level)),
                              (p.x.map(len(changes) - 0.4), p.y.map(level))],
                             stroke=inklet.mix(TH.muted, TH.paper, 0.4),
                             stroke_width=TH.hairline, stroke_dash=dash))
    bars = []
    for index, change in enumerate(changes):
        left, right = index - 0.42, index + 0.42
        corners = p.map([(left, 0.0), (right, 0.0), (right, change), (left, change)])
        bars.append(inklet.polygon(corners, fill=RESPONSE_COLOURS[
            trial.response_class(change)], stroke="none", kind="mark"))
    p.draw(*bars)
    p.over(inklet.polyline([(p.x.map(-0.6), p.y.map(0.0)),
                         (p.x.map(len(changes) - 0.4), p.y.map(0.0))],
                        stroke=TH.ink, stroke_width=TH.hairline))
    p.axis("left", ticks=[-100, -75, -50, -30, 0, 20, 50],
           label="change in target lesions (%)")
    p.axis("bottom", ticks=[], spine=True, tick_size=0,
           label=f"patients (n = {len(changes)}), best response")

    # Under the plot, as in (d). Inside is where a waterfall's key belongs --
    # sorted worst-first, its top left quarter is empty by construction -- but
    # the +20% RECIST line runs straight through the third row of the key at
    # every size that fits, and a reference line behind a swatch reads as part
    # of it.
    # Built from the classes that are actually on the panel. Written out by
    # hand the key listed a complete response nobody in the simulated cohort
    # had -- the one kind of error the linter cannot see, because a swatch for
    # a colour that is drawn nowhere collides with nothing.
    shown = {trial.response_class(change) for change in changes}
    key = inklet.legend([(name, RESPONSE_COLOURS[name]) for name in
                      ("complete", "partial", "stable", "progressive")
                      if name in shown],
                     swatch=1.5, gap=1.1, row_gap=1.15, columns=2,
                     title="best response")
    return inklet.vstack([p.build(), key], gap=2.4, align="center")


PANELS = {"a": panel_a, "b": panel_b, "c": panel_c, "d": panel_d,
          "e": panel_e, "f": panel_f, "g": panel_g}


def build() -> inklet.Figure:
    a, b, c = tagged("a", panel_a()), tagged("b", panel_b()), tagged("c", panel_c())
    d, e = tagged("d", panel_d()), tagged("e", panel_e())
    f, g = tagged("f", panel_f()), tagged("g", panel_g())

    top = inklet.hstack([a, inklet.vstack([b, c], gap=GAP, align="center")],
                     gap=GAP, align="top")
    middle = inklet.hstack([d, e], gap=GAP, align="top")
    bottom = inklet.hstack([f, g], gap=GAP, align="top")

    heading = inklet.title("DGM-431, a selective KIN-A inhibitor: "
                        "from structure to first-in-human")
    note = inklet.text(
        "Structure: the EGFR kinase domain, PDB 1M17 at 2.6 \u00c5. Every backbone "
        "coordinate, secondary-structure assignment and side chain in (a) and (b) is "
        "that deposited entry. Everything else is invented. DGM-431 does not exist; "
        "its pose is a restrained dock into the real ATP site, and the inhibitor "
        "crystallised there is neither drawn nor named. KIN-A, the series and every "
        "number in (c) to (g) come from figures/trial.py.",
        size=TH.font_size_small * 0.92, text_fill=TH.muted, align="left",
        width=PAGE - 4.0)

    fig = inklet.figure(width=PAGE)
    fig.add(inklet.vstack([heading, top, middle, bottom, note],
                       gap=GAP + 1.0, align="center"))
    return fig


def main(argv: list[str]) -> None:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    if len(argv) > 1 and argv[1] in PANELS:
        letter = argv[1]
        fig = inklet.figure(width=PAGE)
        fig.add(tagged(letter, PANELS[letter]()))
        path = out / f"panel_{letter}.svg"
    else:
        fig = build()
        path = out / "drug_discovery.svg"
    # The protein is thousands of small filled paths, so the readable spelling
    # costs about a quarter of the file and slows every viewer that opens it.
    fig.save(path, compact=True)
    body, _ = fig.build()
    print(f"{path}  {body.width:.1f} x {body.height:.1f} mm")
    print(fig.report())


if __name__ == "__main__":
    main(sys.argv)
