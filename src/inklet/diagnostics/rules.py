"""Geometry diagnostics over a resolved diagram tree.

An agent generating a figure cannot see it. These rules turn "the label sticks
out of the box" into a sentence with a node id, a side and a millimetre count,
which is the only form of feedback a blind generator can act on. Everything
here is pure geometry over `core.resolve()` output: no rendering, no fonts, no
rasterisation, no I/O.

Two properties matter as much as the rules themselves:

* **Determinism.** Same tree in, byte-identical diagnostic list out, in the
  same order, so a fix loop can diff two runs.
* **Silence on good input.** A linter that fires on a well-formed figure is
  worse than no linter, because the agent learns to ignore it. Every rule here
  has a documented suppression heuristic, and `OVERLAP` in particular is
  deliberately conservative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from ..core import (
    Affine, Diagram, DiagramError, EllipsePrim, ImagePrim, PathPrim,
    PhantomPrim, Placement, Prim, Rect, RectPrim, Style, TextPrim, Trace, Vec2,
    to_pt,
)
# `inklet.draw` owns two things a rule cannot restate: the exact area of a shape
# clipped to a box, and the convention by which an author declares a stroke
# width to be data.
from ..draw.clip import area_within, polygon_area
from ..draw.path import is_encoded_kind
# A raster whose pixels are the samples says so with this kind, and the back
# ends read the same constant to turn smoothing off. LOW_DPI has to know.
from ..plot.raster import MATRIX_KIND
# The one place a rule needs to know what a link is rather than what it drew:
# a router that could not do what it was asked leaves a flag behind, and only
# `inklet.links` says how that flag is written down.
from ..links import (FLAG_COINCIDENT, FLAG_NO_CLEAR_ROUTE, FLAG_OVERLAP,
                     HEAD_KIND, LABEL_KIND,
                     FLAG_SHORT, FLAG_SOURCE_MISSED, FLAG_SOURCE_NO_EXTENT,
                     FLAG_SOURCE_NO_TRACE, FLAG_TARGET_MISSED,
                     FLAG_TARGET_NO_EXTENT, FLAG_TARGET_NO_TRACE,
                     FLAG_ZERO_LENGTH, LINK_KIND, link_ends, link_flags,
                     link_name)
from ..typeset.outline import TEXT_NOTE, text_to_paths
from .abut import is_abutting_kind
from .cross import declared_crossings
from .color import contrast_ratio
# Reading a raster's pixels is the one thing in here that is not pure geometry.
# It is quarantined in its own module, is optional, and says so: with no Pillow
# installed `average_colour` returns None and the contrast rule stays silent
# rather than judging a caption against a page it is nowhere near.
from .image import average_colour

__all__ = [
    "Diagnostic", "Item", "LintContext", "Rule", "RULES", "SEVERITIES",
    "build_context", "run_rules",
]

SEVERITIES = ("error", "warning", "info")
_SEVERITY_RANK = {name: i for i, name in enumerate(SEVERITIES)}

# Sub-tolerance geometry. Below this a difference is float noise or a hairline
# rounding artefact, not something a human could see or an agent should chase.
_EPS_MM = 0.02

# Default thresholds for the rules that take no explicit knob in `lint()`.
DEFAULT_MIN_CLEARANCE_MM = 1.0
DEFAULT_MIN_OVERLAP_FRACTION = 0.08
DEFAULT_MAX_STROKE_WIDTHS = 3
DEFAULT_PAGE_FILL = "#ffffff"

# WCAG 2.x: normal text needs 4.5:1, "large" text (>=18pt, or >=14pt bold)
# only 3:1. Applying the large-text allowance keeps display type from being
# reported as broken when it is in fact compliant.
#: "not in the memo yet", for a memo whose legitimate answer is None.
_UNASKED = object()

_CONTRAST_NORMAL = 4.5
_CONTRAST_LARGE = 3.0
_LARGE_TEXT_PT = 18.0
_LARGE_BOLD_PT = 14.0

# What can serve as "the shape a label sits in or on". A filled `PathPrim`
# counts: everything `inklet.draw` emits is one, so leaving it out meant a label
# inside a drawn bar was contrast-checked against the *page* -- white on
# #0072b2 reported as 1.00:1 -- and was invisible to the overflow rule. An
# unfilled path is not a backdrop, because there is nothing behind the text.
_SHAPE_PRIMS = (RectPrim, EllipsePrim, PathPrim)


@dataclass(frozen=True)
class Diagnostic:
    """One actionable finding. `where` is figure-space, in millimetres."""

    code: str
    severity: str
    message: str
    targets: tuple[str, ...]
    where: Rect | Vec2 | None
    hint: str | None = None

    @property
    def sort_key(self) -> tuple:
        return (_SEVERITY_RANK.get(self.severity, len(SEVERITIES)),
                self.code, self.targets, self.message)


# -- formatting helpers ---------------------------------------------------


def _mm(value: float) -> str:
    return f"{value:.2f}mm"


def _pts(value: float) -> str:
    return f"{value:.1f}pt"


def _text_excerpt(prim: TextPrim, limit: int = 32) -> str:
    return _excerpt(prim.text, limit)


def _excerpt(text: str, limit: int = 32) -> str:
    words = " ".join(text.split())
    return words if len(words) <= limit else words[: limit - 3] + "..."


def _noted_words(node: Diagram | None) -> str | None:
    """What an outlined block recorded of its own text, or None.

    `render.outline_text` stamps `notes["text"]` on every block it turns into
    paths, because after that nothing in the tree spells the words -- and a
    block whose `{fill|text}` markup asked for two colours keeps no primitive
    at all, so there is not even a shrunken `TextPrim` left to excerpt. The
    note is the only excerpt available for those, and it says exactly what the
    live block would have said.
    """
    if node is None:
        return None
    notes = getattr(node, "notes", None)
    if not isinstance(notes, Mapping):
        return None
    words = notes.get(TEXT_NOTE)
    return _excerpt(words) if isinstance(words, str) and words.strip() else None


def _written_name(node: Diagram) -> str | None:
    """A node's name as its author wrote it.

    Routing appends whatever went wrong to a link's name, because a `Diagram`
    has nowhere else to record it and the linter has to be able to read it
    back. That is an internal channel, and quoting it turns a report about the
    excitation beam into one about `beam-objective-specimen!zero-length`.
    """
    return link_name(node) if node.kind == LINK_KIND else node.name


#: Kinds that exist only to carry geometry a transform generated. They are
#: never named, never authored, and quoting their ids in a finding tells a
#: reader nothing: `inklet.outline_text` turns one text block into a `glyphs`
#: child per colour, so `OFF_CANVAS glyphs3` is a report about a word the
#: author cannot find. The block above is the thing they wrote; see
#: `Item.block`.
_CARRIER_KINDS = frozenset({"glyphs"})


def _spoken_by(nodes: Mapping[str, Diagram], parent: Mapping[str, str | None],
               node_id: str) -> Diagram | None:
    """The nearest ancestor of a carrier node that an author would recognise."""
    if nodes[node_id].kind not in _CARRIER_KINDS:
        return None
    current = parent.get(node_id)
    while current is not None:
        node = nodes.get(current)
        if node is None:
            return None
        if node.kind not in _CARRIER_KINDS:
            return node
        current = parent.get(current)
    return None


# -- the resolved view a rule sees ---------------------------------------


@dataclass(frozen=True, slots=True)
class Item:
    """A node that carries a primitive, with its world geometry precomputed."""

    id: str
    node: Diagram
    prim: Prim
    world: Affine
    style: Style
    bbox: Rect
    scale: float
    depth: int
    #: For a generated carrier (see `_CARRIER_KINDS`), the authored node it
    #: was made from; None for everything else, which is nearly everything.
    block: Diagram | None = None

    @property
    def label(self) -> str:
        own = _written_name(self.node)
        if own:
            return own
        if self.block is not None:
            return _written_name(self.block) or self.block.id
        return self.id

    @property
    def is_text(self) -> bool:
        return isinstance(self.prim, TextPrim)

    @property
    def is_shape(self) -> bool:
        if isinstance(self.prim, PathPrim):
            return self.prim.filled
        return isinstance(self.prim, _SHAPE_PRIMS)

    @property
    def is_backdrop(self) -> bool:
        """Opaque ink a label could be set on top of.

        A raster counts. Paper-white type over a dark micrograph is the
        universal journal style, and while the image carries no `fill` for the
        contrast rule to read, it is the most emphatically opaque thing on the
        page -- judging that caption against the page it does not touch was the
        one guaranteed false positive in `LOW_CONTRAST`.
        """
        if isinstance(self.prim, ImagePrim):
            return self.draws
        return self.is_shape and self.draws and _opaque_fill(self.style.fill)

    @property
    def draws(self) -> bool:
        """PhantomPrim occupies space on purpose and paints nothing."""
        return not isinstance(self.prim, PhantomPrim)

    @property
    def is_computed(self) -> bool:
        """Position derived from a source -- data, or a mesh -- not chosen.

        Two boxes 0.3mm apart is a layout mistake; two scatter points, or two
        triangles of one solid, 0.3mm apart is what the measurement or the
        geometry says. Telling an author to "add 0.7mm of separation" between
        them asks them to falsify the figure.
        """
        return self.node.kind in _COMPUTED_KINDS

    @property
    def encodes_width(self) -> bool:
        """True when this node declares that its stroke width carries a value.

        A Sankey ribbon, a graph edge scaled by projection strength, a contour
        scaled by level: there the width *is* the datum, and drawing twenty of
        them is one design decision, not twenty. `inklet.encoded(kind)` is how the
        author says so; see `rule_inconsistent_stroke`.
        """
        return is_encoded_kind(self.node.kind)

    @property
    def described(self) -> str:
        prim = self.prim
        if not isinstance(prim, TextPrim) and self.block is not None:
            # Outlining leaves the words nowhere unless the block kept its
            # prim, but when it did they are what the reader is looking for.
            prim = self.block.prim
        if isinstance(prim, TextPrim):
            return f"{self.label} {_text_excerpt(prim)!r}"
        # No `TextPrim` anywhere: an outlined block. It wrote its own words
        # down on the way past for exactly this, on the node itself when it
        # kept one path and on the authored block above when the markup asked
        # for two colours and it kept none.
        words = _noted_words(self.node) or _noted_words(self.block)
        if words is not None:
            return f"{self.label} {words!r}"
        return self.label


@dataclass(frozen=True)
class LintContext:
    """Everything the rules read. Built once per `lint()` call."""

    root: Diagram
    placements: Mapping[str, Placement]
    items: tuple[Item, ...]
    nodes: Mapping[str, Diagram]
    parent: Mapping[str, str | None]
    page: Rect | None
    page_fill: str
    min_font_pt: float
    min_stroke_mm: float
    min_dpi: float
    min_clearance_mm: float = DEFAULT_MIN_CLEARANCE_MM
    min_overlap_fraction: float = DEFAULT_MIN_OVERLAP_FRACTION
    max_stroke_widths: int = DEFAULT_MAX_STROKE_WIDTHS
    #: {node id: the ids it was built to touch}, from `Diagram.attached_to`.
    attachments: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    _by_id: dict[str, Item] = field(default_factory=dict, repr=False, compare=False)
    _memo: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._by_id.update({item.id: item for item in self.items})

    def item(self, node_id: str) -> Item | None:
        return self._by_id.get(node_id)

    def label(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        if node is None:
            return node_id
        block = _spoken_by(self.nodes, self.parent, node_id)
        if block is not None:
            return _written_name(block) or block.id
        return _written_name(node) or node_id

    def ancestors(self, node_id: str) -> Iterable[str]:
        current = self.parent.get(node_id)
        while current is not None:
            yield current
            current = self.parent.get(current)

    def is_related(self, a: str, b: str) -> bool:
        """True when one node is an ancestor of the other (or they are equal)."""
        return a == b or b in self.ancestors(a) or a in self.ancestors(b)

    def chain(self, node_id: str) -> tuple[str, ...]:
        """Root-first path down to a node, itself included. Memoised, because
        the quadratic rules ask for it once per candidate pair."""
        chains = self._memo.setdefault("chains", {})
        known = chains.get(node_id)
        if known is None:
            parent = self.parent.get(node_id)
            head = self.chain(parent) if parent is not None else ()
            known = chains[node_id] = head + (node_id,)
        return known

    def abutting_home(self, node_id: str) -> str | None:
        """The nearest ancestor-or-self declared `inklet.abutting`, or None.

        A `inklet.scene` counts without being asked, and the *whole* scene does:
        its parts are one object's geometry -- an atom, the bond drawn into
        it, the cell edge the atom is threaded on -- and where they meet is
        the mesh, not the layout. `stress/electro_figure.py` panel (b)
        reported sixty-six pairs of them 0.05mm apart, every one offering to
        "add 0.95mm of separation" between two halves of one crystal. Each
        part of a scene is a `model` in its own right, so the outermost one
        is the object; two scenes side by side keep their own claims.

        A written declaration is the nearest one, which lets a declaration
        nested inside another name the smaller claim, and is what makes two
        neighbouring declared groups report against each other. Memoised on
        the chain like `paints_parts`, and for the same reason: the quadratic
        rules ask it once per candidate.
        """
        known = self._memo.setdefault("abutting", {})
        answer = known.get(node_id, _UNASKED)
        if answer is _UNASKED:
            answer = None
            for step in reversed(self.chain(node_id)):
                node = self.nodes.get(step)
                if node is None:
                    continue
                if is_abutting_kind(node.kind):
                    answer = step
                    break
                if node.kind == _SCENE_KIND:
                    answer = step      # keep going: the outermost one wins
            known[node_id] = answer
        return answer

    def abuts(self, a: str, b: str) -> bool:
        """True when one `inklet.abutting` declaration covers both nodes.

        Symmetric and scoped: the claim is that the parts of *this* thing
        touch each other, not that this thing may touch anything else.
        """
        home = self.abutting_home(a)
        return home is not None and home == self.abutting_home(b)

    def crosses_by_declaration(self, stroke: str, shape: str) -> bool:
        """True when `inklet.crossing` declared this stroke through this shape.

        Directional, unlike `abuts`: the stroke names what it goes through and
        a shape never names what may go through it. The declaration reaches
        down as well as up on both sides -- a leader declared through a scene
        is declared through every atom in it, and a leader group's declaration
        covers the shaft the router put inside it -- so the author names the
        two objects and not their internals.

        Read by the crossing rules alone. `OVERLAP` and `CROWDING` do not ask,
        which is the whole difference between this and every other exemption
        in the file: the label at the far end of a declared leader is still
        measured against the model it is naming.
        """
        declared: set[str] = set()
        for step in self.chain(stroke):
            node = self.nodes.get(step)
            if node is not None:
                declared.update(declared_crossings(node))
        if not declared:
            return False       # the common case, and it costs one chain walk
        return any(step in declared for step in self.chain(shape))

    def paints_parts(self, node_id: str) -> bool:
        """True for ink inside a fused scene's single drawing pass.

        See `_FUSED_KIND`. Memoised on the chain, which the quadratic rules
        already ask for once per candidate.
        """
        known = self._memo.setdefault("fused", {})
        answer = known.get(node_id)
        if answer is None:
            answer = known[node_id] = any(
                node is not None and node.kind == _FUSED_KIND
                for node in (self.nodes.get(step) for step in self.chain(node_id)))
        return answer

    def common_ancestor(self, a: str, b: str) -> str | None:
        """Deepest node containing both, or None when they share no tree."""
        deepest: str | None = None
        for mine, theirs in zip(self.chain(a), self.chain(b)):
            if mine != theirs:
                break
            deepest = mine
        return deepest

    def is_attached(self, a: str, b: str) -> bool:
        """True when one node belongs to something built to touch the other.

        `is_related` is the same idea one step in: there, one node is *inside*
        the other. Here a connector's arrowhead rests on the shape the router
        clipped it to, which is what an arrow is for. A head near a shape the
        link has nothing to do with stays a finding.
        """
        if not self.attachments:
            return False       # a figure with no connectors pays nothing here
        return self._attaches(a, b) or self._attaches(b, a)

    def _attaches(self, a: str, b: str) -> bool:
        target = frozenset(self.chain(b))
        for node_id in self.chain(a):
            if any(end in target for end in self.attachments.get(node_id, ())):
                return True
        return False

    def enclosing_shape_item(self, node_id: str) -> Item | None:
        """Nearest ancestor carrying a fillable shape of its own.

        This is the structural notion of "the box this label belongs to", which
        is what TEXT_OVERFLOW is about: a label is the responsibility of the
        shape it was nested inside.
        """
        for ancestor in self.ancestors(node_id):
            item = self.item(ancestor)
            if item is not None and item.is_shape:
                return item
        return None

    @property
    def _filled_shapes(self) -> "_PointIndex":
        """Grid over opaque backdrops, so `background_of` is not a third
        quadratic rule hiding behind a linear-looking loop."""
        if "shapes" not in self._memo:
            self._memo["shapes"] = _PointIndex(
                [i for i in self.items if i.is_backdrop])
        return self._memo["shapes"]

    def background_of(self, item: Item) -> tuple[str | None, Item | None]:
        """(colour, the thing it came from) behind a text item.

        Geometric rather than structural: the tightest backdrop whose bbox
        contains the text wins. `Diagram(children=(rect, label))` -- rect and
        label as siblings -- is at least as common as nesting the label inside
        the rect, and only a containment test handles both. Candidates come
        from a point query on the text's centre, which is sound because any box
        containing the whole text block contains its centre.

        The colour is `None` when the backdrop is a raster whose pixels cannot
        be read -- no Pillow, or no readable file. That is not the same as
        white: the caller stops checking rather than measuring against a page
        the text is nowhere near.
        """
        best: Item | None = None
        for candidate in self._filled_shapes.at(item.bbox.center):
            if candidate is item or not _contains(candidate.bbox, item.bbox):
                continue
            if not _covers(candidate, item.bbox):
                continue
            if best is None or (_area(candidate.bbox), candidate.id) < (
                _area(best.bbox), best.id
            ):
                best = candidate
        if best is None:
            return self.page_fill, None
        if isinstance(best.prim, ImagePrim):
            return average_colour(best.prim, best.world, item.bbox), best
        return str(best.style.fill), best


Rule = Callable[[LintContext], list[Diagnostic]]


# -- geometry helpers -----------------------------------------------------


def _area(rect: Rect) -> float:
    return max(rect.width, 0.0) * max(rect.height, 0.0)


def _covers(shape: Item, box: Rect) -> bool:
    """Does the shape's ink lie under all of `box`?

    Containment in a *box* is enough for a rectangle and near enough for an
    ellipse, but a filled path can enclose a text block's box while leaving
    most of it on the page -- and half a backdrop is not a backdrop: there is
    no single colour to measure the contrast against. Asked with a 1% tolerance
    so the flattening of a curved edge does not disqualify it.
    """
    rings = _rings(shape)
    if rings is None:
        return True
    wanted = _area(box)
    if wanted <= 0.0:
        return True
    return sum(area_within(ring, box) for ring in rings) >= wanted * 0.99


def _opaque_fill(fill: str | None) -> bool:
    return fill is not None and str(fill).strip().lower() not in ("none", "transparent")


def _contains(outer: Rect, inner: Rect, slop: float = 0.05) -> bool:
    return (inner.x0 >= outer.x0 - slop and inner.x1 <= outer.x1 + slop
            and inner.y0 >= outer.y0 - slop and inner.y1 <= outer.y1 + slop)


def _gap(a: Rect, b: Rect) -> float:
    """Shortest distance between two axis-aligned boxes; 0 when they touch."""
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0.0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0.0)
    return math.hypot(dx, dy)


def _ink_box(ctx: LintContext, item: Item) -> Rect:
    """The box the glyphs actually fill, for text; the ordinary bbox otherwise.

    A text node's bbox is its *line* box: the full advance wide, and ascender
    to descender tall. For a font whose ascender clears its capitals by a
    quarter of the em -- most of them -- a row of digits leaves nearly a
    millimetre of empty box above the ink and half of one below, and two labels
    that meet corner to corner across that emptiness are reported as 0.97mm
    apart when a reader sees 2.2mm. `examples/gallery.py` had exactly that at
    the corner of a log-log panel, where the last tick of one axis sits
    diagonally from the first tick of the other.

    Outlining the block answers it exactly instead of guessing at a cap height,
    and costs a shaping pass over a string that is nearly always a handful of
    characters. It is only ever asked about a pair the box test has already
    called crowded, and memoised per node, so it is off the hot path. A block
    the shaper did not build (`font_path` is None -- a hand-made prim in a
    test) has no outlines to take, and keeps its line box.
    """
    if not item.is_text:
        return item.bbox
    boxes = ctx._memo.setdefault("ink", {})
    known = boxes.get(item.id)
    if known is None:
        known = boxes[item.id] = _measure_ink(item)
    return known


def _measure_ink(item: Item) -> Rect:
    try:
        paths = text_to_paths(item.prim)  # type: ignore[arg-type]
    except Exception:
        return item.bbox
    drawn = [box for box in (_prim_bbox(path, item.world) for path, _ in paths)
             if box is not None]
    if not drawn:
        return item.bbox
    hull = drawn[0]
    for box in drawn[1:]:
        hull = hull.union(box)
    return hull


def _ink_gap(ctx: LintContext, first: Item, second: Item) -> float:
    """`_gap`, re-measured on ink when either side is text."""
    if not (first.is_text or second.is_text):
        return _gap(first.bbox, second.bbox)
    return _gap(_ink_box(ctx, first), _ink_box(ctx, second))


def _outside(inner: Rect, container: Rect) -> dict[str, float]:
    """How far `inner` pokes out of `container`, per side, above tolerance."""
    sides = {
        "left": container.x0 - inner.x0,
        "right": inner.x1 - container.x1,
        "top": container.y0 - inner.y0,
        "bottom": inner.y1 - container.y1,
    }
    return {side: amount for side, amount in sides.items() if amount > _EPS_MM}


def _sides_phrase(sides: Mapping[str, float]) -> str:
    order = ("left", "right", "top", "bottom")
    return ", ".join(f"{_mm(sides[s])} on the {s}" for s in order if s in sides)


def _prim_bbox(prim: Prim, world: Affine) -> Rect | None:
    """World bbox of a node's own primitive, ignoring its children."""
    try:
        return prim.envelope().transform(world).bbox()
    except Exception:
        return None


def _effective_stroke(item: Item) -> float | None:
    """Resolved stroke width at final scale, or None when nothing is stroked."""
    if not item.draws or item.is_text or isinstance(item.prim, ImagePrim):
        return None
    width = item.style.stroke_width
    if width is None or width <= 0.0:
        return None
    stroke = item.style.stroke
    if stroke is not None and str(stroke).strip().lower() in ("none", "transparent"):
        return None
    return float(width) * item.scale


def _effective_font_pt(item: Item) -> float:
    prim = item.prim
    assert isinstance(prim, TextPrim)
    return to_pt(prim.font_size * item.scale)


def _effective_font_mm(item: Item) -> float:
    """The same size in the units the page is measured in."""
    prim = item.prim
    assert isinstance(prim, TextPrim)
    return prim.font_size * item.scale


# -- context construction -------------------------------------------------


def build_context(
    root: Diagram,
    placements: Mapping[str, Placement],
    *,
    page: Rect | None = None,
    page_fill: str = DEFAULT_PAGE_FILL,
    min_font_pt: float = 5.0,
    min_stroke_mm: float = 0.088,
    min_dpi: float = 300.0,
    min_clearance_mm: float = DEFAULT_MIN_CLEARANCE_MM,
    min_overlap_fraction: float = DEFAULT_MIN_OVERLAP_FRACTION,
    max_stroke_widths: int = DEFAULT_MAX_STROKE_WIDTHS,
) -> LintContext:
    nodes: dict[str, Diagram] = {}
    parent: dict[str, str | None] = {}
    attachments: dict[str, tuple[str, ...]] = {}

    def visit(node: Diagram, parent_id: str | None) -> None:
        nodes[node.id] = node
        parent[node.id] = parent_id
        if node.attached_to:
            attachments[node.id] = tuple(node.attached_to)
        for child in node.children:
            visit(child, node.id)

    visit(root, None)

    items: list[Item] = []
    for node_id, node in nodes.items():
        if node.prim is None:
            continue
        placement = placements.get(node_id)
        if placement is None:
            continue  # caller handed us placements from a different resolve()
        bbox = _prim_bbox(node.prim, placement.world)
        if bbox is None:
            continue  # a degenerate prim: no lines, no points, nothing to check
        items.append(Item(
            id=node_id, node=node, prim=node.prim, world=placement.world,
            style=placement.style, bbox=bbox,
            scale=placement.world.uniform_scale(), depth=placement.depth,
            block=_spoken_by(nodes, parent, node_id),
        ))
    items.sort(key=lambda i: i.id)

    return LintContext(
        root=root, placements=placements, items=tuple(items), nodes=nodes,
        parent=parent, page=page, page_fill=page_fill, min_font_pt=min_font_pt,
        min_stroke_mm=min_stroke_mm, min_dpi=min_dpi,
        min_clearance_mm=min_clearance_mm,
        min_overlap_fraction=min_overlap_fraction,
        max_stroke_widths=max_stroke_widths,
        attachments=attachments,
    )


# -- pair generation ------------------------------------------------------
#
# OVERLAP and CROWDING are the only quadratic rules. Below `_NAIVE_LIMIT` items
# the naive O(N^2) sweep is both exact and faster than building an index. Above
# it we bucket into a uniform grid sized to the mean box extent, which brings
# the expected cost to O(N * k) for k neighbours per cell. Two boxes that
# overlap (after padding) always share at least one cell, so bucketing returns
# a superset of the naive pairs and cannot change the diagnostics -- only the
# time taken to find them.

_NAIVE_LIMIT = 200
_MAX_CELLS_PER_ITEM = 256


def _cell_size(boxes: Sequence[Rect]) -> float:
    """Mean box extent: small enough to separate neighbours, large enough that
    an ordinary box lands in a handful of cells rather than hundreds."""
    if not boxes:
        return 1.0
    span = sum(b.width + b.height for b in boxes) / (2 * len(boxes))
    return max(span, 1e-3)


class _PointIndex:
    """Uniform grid over item bboxes, queried by point.

    Items whose box would span more than `_MAX_CELLS_PER_ITEM` cells -- a
    page-wide background, typically -- go in `always` instead of being smeared
    across the whole grid.
    """

    __slots__ = ("cell", "grid", "always", "items")

    def __init__(self, items: Sequence[Item]) -> None:
        self.grid: dict[tuple[int, int], list[Item]] = {}
        self.always: list[Item] = []
        self.items: tuple[Item, ...] = tuple(items)
        self.cell = _cell_size([i.bbox for i in items])
        for item in items:
            box = item.bbox
            cx0, cx1 = math.floor(box.x0 / self.cell), math.floor(box.x1 / self.cell)
            cy0, cy1 = math.floor(box.y0 / self.cell), math.floor(box.y1 / self.cell)
            if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > _MAX_CELLS_PER_ITEM:
                self.always.append(item)
                continue
            for cx in range(cx0, cx1 + 1):
                for cy in range(cy0, cy1 + 1):
                    self.grid.setdefault((cx, cy), []).append(item)

    def at(self, point: Vec2) -> list[Item]:
        key = (math.floor(point.x / self.cell), math.floor(point.y / self.cell))
        found = self.grid.get(key)
        if not self.always:
            return found or []
        return (found or []) + self.always

    def overlapping(self, box: Rect) -> list[Item]:
        """Items sharing a cell with `box`, in id order.

        A superset of the true overlaps, which is all a prefilter owes. A box
        spanning most of the page is cheaper to answer with everything than to
        walk cell by cell.
        """
        cx0, cx1 = math.floor(box.x0 / self.cell), math.floor(box.x1 / self.cell)
        cy0, cy1 = math.floor(box.y0 / self.cell), math.floor(box.y1 / self.cell)
        if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > _MAX_CELLS_PER_ITEM:
            return list(self.items)
        found: dict[str, Item] = {}
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                for item in self.grid.get((cx, cy), ()):
                    found[item.id] = item
        for item in self.always:
            found[item.id] = item
        return [found[key] for key in sorted(found)]


def _candidate_pairs(boxes: Sequence[Rect], pad: float = 0.0, *,
                     apart: Sequence[object] | None = None,
                     ) -> list[tuple[int, int]]:
    """Index pairs whose padded boxes share a grid cell, in index order.

    `apart[i]` is an optional key grouping items the caller has *already*
    decided cannot report against each other: two indices with the same
    non-`None` key are never returned. This is not a tolerance and it changes
    no result -- it is the caller's own first `continue` moved one step
    earlier, where it can be answered by a lookup instead of a walk up two
    ancestor chains.

    It is also the difference between linear and quadratic on a shaded mesh.
    The grid assumes boxes are local, and a `inklet.model` breaks that: it merges
    every facet of one tone into a single path, and each of those paths spans
    most of the object. On panel (a) of `figures/drug_discovery.py` the median
    candidate box is 20mm across on a 66mm panel, so the grid degenerates to
    the naive product -- 5.08 million pairs out of a possible 6.39 million --
    and 3,568 of the 3,575 candidates are facets of one model that CROWDING
    discards one at a time. Keyed apart, the same panel produces 25 thousand
    pairs, and the rule stops costing more than everything else together.
    """
    n = len(boxes)
    if n < 2:
        return []
    if n <= _NAIVE_LIMIT:
        return [(i, j) for i in range(n) for j in range(i + 1, n)
                if _keeps(apart, i, j)]

    padded = [b.pad(pad) if pad else b for b in boxes]
    cell = _cell_size(padded)

    grid: dict[tuple[int, int], list[int]] = {}
    oversized: list[int] = []
    for index, box in enumerate(padded):
        cx0, cx1 = math.floor(box.x0 / cell), math.floor(box.x1 / cell)
        cy0, cy1 = math.floor(box.y0 / cell), math.floor(box.y1 / cell)
        if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > _MAX_CELLS_PER_ITEM:
            # A page-spanning background would otherwise fill the whole grid.
            oversized.append(index)
            continue
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                grid.setdefault((cx, cy), []).append(index)

    pairs: set[tuple[int, int]] = set()
    for key in sorted(grid):
        _pair_within(pairs, grid[key], apart)
    for index in oversized:
        mine = None if apart is None else apart[index]
        for other in range(n):
            if other == index or (mine is not None and mine == apart[other]):
                continue
            pairs.add((index, other) if index < other else (other, index))
    return sorted(pairs)


def _keeps(apart: Sequence[object] | None, i: int, j: int) -> bool:
    """Whether a pair survives the caller's `apart` keys."""
    return apart is None or apart[i] is None or apart[i] != apart[j]


def _pair_within(pairs: set[tuple[int, int]], bucket: Sequence[int],
                 apart: Sequence[object] | None) -> None:
    """Every pair inside one grid cell, minus the ones keyed apart.

    Split into blocks by key rather than filtered pair by pair: a bucket of a
    thousand facets of one mesh is a thousand *iterations* that way and half a
    million the other, and on a degenerate grid the bucket is the whole figure.
    """
    if apart is None:
        for a in range(len(bucket)):
            i = bucket[a]
            for b in range(a + 1, len(bucket)):
                j = bucket[b]
                pairs.add((i, j) if i < j else (j, i))
        return
    blocks: dict[object, list[int]] = {}
    loose: list[int] = []
    for index in bucket:
        key = apart[index]
        if key is None:
            loose.append(index)
        else:
            blocks.setdefault(key, []).append(index)
    _pair_within(pairs, loose, None)
    keyed = list(blocks.values())
    for block in keyed:
        _pair_between(pairs, loose, block)
    for a in range(len(keyed)):
        for b in range(a + 1, len(keyed)):
            _pair_between(pairs, keyed[a], keyed[b])


def _pair_between(pairs: set[tuple[int, int]], left: Sequence[int],
                  right: Sequence[int]) -> None:
    for i in left:
        for j in right:
            pairs.add((i, j) if i < j else (j, i))


#: `inklet.scene(order="exact")` draws all its parts in one pass and wraps that
#: pass in this kind. What is under it is a *painting* of parts that are
#: themselves nodes -- each still there as an outline of its own -- so the
#: shapes to report against are the parts, and the painting is skipped. Naming
#: the painting instead would be useless twice over: it says "the stack"
#: where the author needs "the membrane", and no `through=` can cite it,
#: because no part contains it.
_FUSED_KIND = "model-fused"

#: `inklet.scene` -- one projected 3D object, whatever its parts are called.
#: Spelled out rather than imported: `inklet.three` imports the linter, so the
#: dependency only goes the other way at the bottom of this file.
_SCENE_KIND = "model"


def _pairable(ctx: LintContext, item: Item) -> bool:
    """Items whose bbox is an honest stand-in for their ink.

    An unfilled `PathPrim` is excluded: a diagonal connector's bounding box is
    mostly empty, so bbox overlap says nothing about whether the line actually
    crosses a label. Reporting those would be the single largest source of
    false positives, and text-crosses-connector needs segment tests that belong
    to the link layer, not to a bbox linter.
    """
    if not item.draws:
        return False
    if isinstance(item.prim, PathPrim) and not item.prim.filled:
        return False
    if ctx.paints_parts(item.id):
        return False
    return _area(item.bbox) > 0.0


# -- rules ----------------------------------------------------------------


def rule_text_overflow(ctx: LintContext) -> list[Diagnostic]:
    """A label wider or taller than the box it was put inside.

    Compared against the container primitive's bounding box. For an ellipse
    that is generous -- text can clear the bbox and still clip the curve -- but
    a tighter test would fire on ordinary centred labels, and a false positive
    costs more than a missed near-miss.
    """
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text:
            continue
        container = ctx.enclosing_shape_item(item.id)
        if container is None:
            continue
        sides = _outside(item.bbox, container.bbox)
        if not sides:
            continue
        horizontal = sides.get("left", 0.0) + sides.get("right", 0.0)
        vertical = sides.get("top", 0.0) + sides.get("bottom", 0.0)
        fixes = []
        if horizontal > 0:
            fixes.append(f"widen {container.label} by {_mm(horizontal)} "
                         f"(to {_mm(container.bbox.width + horizontal)})")
        if vertical > 0:
            fixes.append(f"heighten {container.label} by {_mm(vertical)} "
                         f"(to {_mm(container.bbox.height + vertical)})")
        shrink = ""
        if horizontal > 0 and item.bbox.width > 0:
            factor = container.bbox.width / item.bbox.width
            shrink = (f", or shrink the text to {factor * 100:.0f}% "
                      f"({_pts(_effective_font_pt(item) * factor)})")
        out.append(Diagnostic(
            code="TEXT_OVERFLOW",
            severity="error",
            message=(f"{item.described} overflows {container.label} by "
                     f"{_sides_phrase(sides)}"),
            targets=(item.id, container.id),
            where=item.bbox,
            hint=" and ".join(fixes) + shrink,
        ))
    return out


def rule_off_canvas(ctx: LintContext) -> list[Diagnostic]:
    """Anything drawable that leaves the page."""
    if ctx.page is None:
        return []
    page = ctx.page
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.draws:
            continue
        sides = _outside(item.bbox, page)
        if not sides:
            continue
        if page.overlap(item.bbox) is None:
            message = (f"{item.described} is entirely off the page "
                       f"(bbox x {item.bbox.x0:.2f}..{item.bbox.x1:.2f}mm, "
                       f"y {item.bbox.y0:.2f}..{item.bbox.y1:.2f}mm; page is "
                       f"{_mm(page.width)} x {_mm(page.height)})")
        else:
            message = (f"{item.described} runs off the page by "
                       f"{_sides_phrase(sides)}")
        worst = max(sides.values())
        out.append(Diagnostic(
            code="OFF_CANVAS",
            severity="error",
            message=message,
            targets=(item.id,),
            where=item.bbox,
            hint=(f"move {item.label} back inside the page or grow the page by "
                  f"{_mm(worst)} on the "
                  f"{max(sides, key=lambda s: sides[s])}"),
        ))
    return out


def rule_tiny_text(ctx: LintContext) -> list[Diagnostic]:
    """Type below the legibility floor once every enclosing scale is applied."""
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        effective = _effective_font_pt(item)
        if effective >= ctx.min_font_pt - 1e-9:
            continue
        nominal = to_pt(item.prim.font_size)  # type: ignore[union-attr]
        scale_note = ("" if abs(item.scale - 1.0) < 1e-9
                      else f" ({_pts(nominal)} at {item.scale:.3g}x scale)")
        needed = ctx.min_font_pt / item.scale if item.scale else ctx.min_font_pt
        out.append(Diagnostic(
            code="TINY_TEXT",
            severity="error",
            message=(f"{item.described} renders at {_pts(effective)}{scale_note}, "
                     f"below the {_pts(ctx.min_font_pt)} minimum"),
            targets=(item.id,),
            where=item.bbox,
            hint=(f"set font_size to at least {_pts(needed)} "
                  f"(pt({needed:.1f})), or stop scaling the group down"),
        ))
    return out


def rule_hairline(ctx: LintContext) -> list[Diagnostic]:
    """Strokes that vanish on press. 0.088mm is the usual 0.25pt floor."""
    out: list[Diagnostic] = []
    artwork: dict[str, list[tuple[Item, float]]] = {}
    for item in ctx.items:
        width = _effective_stroke(item)
        if width is None or width >= ctx.min_stroke_mm - 1e-12:
            continue
        owner = _object_of(ctx, item.id)
        if owner != item.id and is_abutting_kind(ctx.nodes[owner].kind):
            artwork.setdefault(owner, []).append((item, width))
            continue
        nominal = float(item.style.stroke_width or 0.0)
        scale_note = ("" if abs(item.scale - 1.0) < 1e-9
                      else f" ({_mm(nominal)} at {item.scale:.3g}x scale)")
        needed = ctx.min_stroke_mm / item.scale if item.scale else ctx.min_stroke_mm
        out.append(Diagnostic(
            code="HAIRLINE",
            severity="warning",
            message=(f"{item.described} has a {_mm(width)} stroke{scale_note}, "
                     f"below the {ctx.min_stroke_mm:.3f}mm print minimum"),
            targets=(item.id,),
            where=item.bbox,
            hint=f"raise stroke_width to at least {needed:.3f}mm",
        ))
    for owner, strokes in artwork.items():
        # Keep every target and the full affected region. This consolidates a
        # repeated print warning within one explicitly named illustration; it
        # does not exempt that artwork from the print threshold.
        box = strokes[0][0].bbox
        for item, _ in strokes[1:]:
            box = box.union(item.bbox)
        count = len(strokes)
        out.append(Diagnostic(
            code='HAIRLINE', severity='warning',
            message=(f"{ctx.label(owner)} contains {count} "
                     f"{'stroke' if count == 1 else 'strokes'} below the "
                     f"{ctx.min_stroke_mm:.3f}mm print minimum; thinnest is "
                     f"{_mm(min(width for _, width in strokes))}"),
            targets=tuple(item.id for item, _ in strokes), where=box,
            hint=f'raise each effective stroke width to at least {ctx.min_stroke_mm:.3f}mm',
        ))
    return out


def rule_low_contrast(ctx: LintContext) -> list[Diagnostic]:
    """Text that does not separate from what is behind it.

    Foreground resolution is taken from `render/svg.py` rather than reasoned
    about, and the renderer's rule is: `text_fill` is written onto the `<text>`
    element and nothing else is. So a `text_fill` in scope wins outright --
    including over a `fill` the author set on the text node itself, which is
    what `TEXT_FILL_IGNORED` is for -- and with no `text_fill` in scope the
    `<text>` carries no fill and inherits the enclosing group's.

    Which leaves one deliberate divergence, and it is worth naming. A label
    nested in a filled box, in a tree with no theme, is painted by the cascade
    in that box's own fill -- invisible, and the renderer really does it. It is
    not reported, because `inklet.themes` sets `text_fill` on every page, so the
    only trees that reach it are ones nobody renders, and a rule that answers
    "your white label on your white box is invisible" four hundred times for a
    grid built without a figure is a rule an author switches off. Only
    `text_fill`, or a `fill` written on the text node, counts as the author
    having chosen a colour; failing both, the renderer default of black.

    The backdrop may be a raster (see `Item.is_backdrop`), in which case the
    colour is an average over the covered pixels and needs Pillow; without it
    `background_of` returns None and this rule declines to guess.
    """
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        foreground = item.style.text_fill or item.node.style.fill or "#000000"
        background, source = ctx.background_of(item)
        ratio = contrast_ratio(foreground, background)
        if ratio is None:
            continue  # unknown or translucent colour: say nothing rather than guess
        effective_pt = _effective_font_pt(item)
        bold = str(item.style.font_weight or "").lower() in ("bold", "bolder", "700",
                                                             "800", "900")
        threshold = (_CONTRAST_LARGE
                     if effective_pt >= _LARGE_TEXT_PT
                     or (bold and effective_pt >= _LARGE_BOLD_PT)
                     else _CONTRAST_NORMAL)
        if ratio >= threshold - 1e-9:
            continue
        if source is None:
            against = f"the page background {background}"
        elif isinstance(source.prim, ImagePrim):
            against = f"{source.label}, averaging {background} under the text"
        else:
            against = f"{source.label}'s {background}"
        out.append(Diagnostic(
            code="LOW_CONTRAST",
            severity="warning",
            message=(f"{item.described} in {foreground} on {against} has a "
                     f"contrast ratio of {ratio:.2f}:1, below WCAG "
                     f"{threshold:.1f}:1"),
            targets=(item.id,) if source is None else (item.id, source.id),
            where=item.bbox,
            hint=(f"darken or lighten the text fill until the ratio reaches "
                  f"{threshold:.1f}:1 (currently {ratio:.2f}:1)"
                  + (", or set the caption on a plate -- an average is not a "
                     "guarantee, and one bright patch of a micrograph swallows "
                     "white type whatever the mean says"
                     if source is not None and isinstance(source.prim, ImagePrim)
                     else "")),
        ))
    return out


def rule_text_fill_ignored(ctx: LintContext) -> list[Diagnostic]:
    """`fill=` on a text node, where the glyph colour is `text_fill=`.

    `inklet.label("x", fill="red")` prints in the theme's ink. The renderer writes
    `style.text_fill` onto the `<text>` element and nothing else, so the `fill`
    the author wrote lands on the wrapping `<g>` -- where the text element's
    own `fill` overrides it, and where it would repaint any shape in the same
    group besides. Nothing raises, nothing collides, and the label is simply
    the wrong colour.

    Two shapes of the same mistake, and the difference is worth reporting:

    * A `text_fill` is in scope -- true under every theme, since `inklet.themes`
      sets one on the page. The author's colour is discarded outright, which
      is a **warning**.
    * No `text_fill` anywhere. The `<text>` inherits the group's fill and the
      colour does come out as asked, by accident of the cascade. That is
      **info**: it works today and stops working the moment the figure gets a
      theme, or the label gets a sibling shape.

    `LOW_CONTRAST` resolves the foreground exactly as the renderer does, so the
    two rules always agree about which colour is on the page.
    """
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        wanted = item.node.style.fill
        if wanted is None or item.node.style.text_fill is not None:
            continue
        drawn = item.style.text_fill
        if drawn is not None:
            severity = "warning"
            outcome = f"renders in {drawn}, the text_fill it inherits"
        else:
            severity = "info"
            outcome = ("only picks that colour up from the group around it, "
                       "which any theme or enclosing text_fill will take back")
        out.append(Diagnostic(
            code="TEXT_FILL_IGNORED",
            severity=severity,
            message=(f"{item.described} sets fill={wanted!r} but {outcome}; "
                     f"glyph colour is the text_fill channel"),
            targets=(item.id,),
            where=item.bbox,
            hint=f"write text_fill={wanted!r} instead of fill={wanted!r}",
        ))
    return out


def rule_low_dpi(ctx: LintContext) -> list[Diagnostic]:
    """Rasters placed larger than their pixels support.

    `ImagePrim.effective_dpi()` is a local-frame number; an image inside a 0.5x
    group is printed at half the width and so at twice the dpi, which is why
    the world scale divides in here.

    An image whose pixels *are* the data is exempt (`_is_a_measurement`). A
    60 x 60 experiment printed at 40mm is 38dpi and asking for 472 pixels
    across asks for 400,000 measurements nobody took; the right answer there
    is to draw it at the resolution it has, which is what
    `inklet.plot.raster_matrix` does. It says so two ways -- the `raster-matrix`
    kind the back ends already read to turn resampling off, and
    `ImagePrim.smooth = False`, which is the same statement made by an author
    who built the image themselves.
    """
    out: list[Diagnostic] = []
    for item in ctx.items:
        prim = item.prim
        if not isinstance(prim, ImagePrim) or not item.draws:
            continue
        if _is_a_measurement(item, prim):
            continue
        local_dpi = prim.effective_dpi()
        if local_dpi is None:
            continue  # no pixel_size recorded; nothing to check
        scale = item.scale or 1.0
        dpi = local_dpi / scale
        if dpi >= ctx.min_dpi - 1e-9:
            continue
        printed_mm = prim.width * scale
        pixels = prim.pixel_size[0] if prim.pixel_size else 0
        needed = math.ceil(ctx.min_dpi * printed_mm / 25.4)
        out.append(Diagnostic(
            code="LOW_DPI",
            severity="warning",
            message=(f"{item.label} ({prim.source}) is {pixels}px wide at "
                     f"{_mm(printed_mm)} = {dpi:.0f}dpi, below {ctx.min_dpi:.0f}dpi"),
            targets=(item.id,),
            where=item.bbox,
            hint=(f"supply a {needed}px-wide source, or place it at "
                  f"{_mm(pixels * 25.4 / ctx.min_dpi / scale)} instead"),
        ))
    return out


def _is_a_measurement(item: Item, prim: ImagePrim) -> bool:
    """Whether this raster's pixels are samples rather than a reproduction."""
    return item.node.kind == MATRIX_KIND or getattr(prim, "smooth", None) is False


#: `_candidate_pairs(apart=)` key for OVERLAP, carried by every item that is
#: not text. Its own identity is the whole of it -- it only has to be a value
#: no other key can equal.
_WORDLESS = object()


def _one_block(item: Item) -> str | None:
    """The authored node this item is a *piece of the geometry of*, or None.

    A carrier (`_CARRIER_KINDS`) is one fragment of one authored thing:
    `inklet.outline_text` cuts a block into a `glyphs` child per colour, and
    `typeset.onpath` sets a run as a `glyphs` child per shaping cluster. Two
    fragments of the same block are not two elements that collide -- they are
    one word, and the letters of a word touch. A curved label on a 16mm dial
    reported eleven OVERLAPs against itself before this was here, because a
    rotated glyph's axis-aligned box is inflated by the turn while its ink is
    not; the pair is discarded on what the tree says rather than on a
    tolerance, so a curved label crossing a *different* label still reports.

    `Item.block` is already this node, resolved once when the context was
    built, which is why this costs a field read rather than an ancestor walk.
    """
    return None if item.block is None else item.block.id


def rule_overlap(ctx: LintContext) -> list[Diagnostic]:
    """Colliding elements, filtered hard against false positives.

    The heuristic, in order:

    1. At least one of the pair is a `TextPrim`. Shapes overlapping shapes is
       ordinary composition (a badge on a card, a shaded band behind a row);
       text landing on anything is what actually ruins a figure.
    2. Neither is an ancestor of the other -- a label nested in its box is the
       normal idiom, not a collision.
    3. Neither bbox contains the other (0.05mm slop). This is the "shape
       overlapping its own frame" guard, and it is geometric rather than
       structural on purpose: `Diagram(children=(rect, label))` puts the frame
       and the label side by side in the tree, so an ancestor test alone would
       miss the most common way figures are built.
    4. Unfilled `PathPrim`s are excluded entirely (see `_pairable`).
    5. A *filled* `PathPrim`, and a cut-out `ImagePrim`, are measured against
       their real outline rather than their box. A Sankey ribbon or a tapered
       graph edge fills a fraction of its own bounding box, and every
       percentage label beside one read as a collision until this was here:
       eighteen of the twenty-two warnings on one sheet of
       `stress/mega_figure` were a label sitting in the empty corner of a
       curve's box. A photograph is the same case with a silhouette instead of
       subpaths.
    6. The intersection must cover at least `min_overlap_fraction` (default 8%)
       of the smaller shape *and* at least 0.25mm^2. Glyph bounding boxes carry
       ascender and descender slack, so a couple of percent of touching is
       normal typesetting rather than a defect.
    7. Both sides under one `inklet.abutting(kind)` node. That one is the
       author's, not a heuristic: see `diagnostics.abut`.
    8. Two fragments of one authored block -- the letters of a curved label,
       the two colours of an outlined one. See `_one_block`.
    """
    candidates = [i for i in ctx.items if _pairable(ctx, i)]
    boxes = [i.bbox for i in candidates]
    # Test 1 above, asked once per item instead of once per pair: two shapes
    # are a pair this rule was never going to keep. See `_candidate_pairs`.
    apart = [_one_block(item) or (None if item.is_text else _WORDLESS)
             for item in candidates]
    out: list[Diagnostic] = []
    for a, b in _candidate_pairs(boxes, apart=apart):
        first, second = candidates[a], candidates[b]
        if ctx.is_related(first.id, second.id):
            continue
        if ctx.abuts(first.id, second.id):
            continue
        intersection = first.bbox.overlap(second.bbox)
        if intersection is None:
            continue
        if _contains(first.bbox, second.bbox) or _contains(second.bbox, first.bbox):
            continue
        area, intersection = _ink_overlap(first, second, intersection)
        smaller = min(_ink_area(first), _ink_area(second))
        if smaller <= 0.0 or area <= 0.0:
            continue
        fraction = area / smaller
        if fraction < ctx.min_overlap_fraction or area < 0.25:
            continue
        both_text = first.is_text and second.is_text
        out.append(Diagnostic(
            code="OVERLAP",
            severity="error" if both_text else "warning",
            message=(f"{first.described} overlaps {second.described} over "
                     f"{area:.2f}mm^2, {fraction * 100:.0f}% of the smaller box "
                     f"({_mm(intersection.width)} x {_mm(intersection.height)})"),
            targets=tuple(sorted((first.id, second.id))),
            where=intersection,
            hint=(f"separate them by at least "
                  f"{_mm(min(intersection.width, intersection.height) + ctx.min_clearance_mm)} "
                  f"along the shorter axis"),
        ))
    return out


def _rings(item: Item) -> list[list[Vec2]] | None:
    """A filled path's outline in world space, or None when its box is honest.

    Holes are not subtracted: a ring drawn as an outer and an inner subpath
    reports the outer area, which over-states rather than hides. Over-stating
    is the safe direction for a linter -- it keeps a finding that a reader can
    dismiss, instead of dropping one they never see.
    """
    prim = item.prim
    if isinstance(prim, ImagePrim) and prim.outline:
        # A cutout is a filled shape that happens to be made of pixels, and its
        # box is the photograph's rather than the subject's. A mouse lying
        # along the frame leaves corners big enough to set a caption in, which
        # is the whole reason the silhouette was traced.
        return [[item.world.apply(point) for point in prim.outline]]
    if not isinstance(prim, PathPrim) or not prim.filled:
        return None
    rings = [[item.world.apply(point) for point in sub.points]
             for sub in prim.subpaths if len(sub.points) >= 3]
    return rings or None


def _ink_area(item: Item) -> float:
    rings = _rings(item)
    if rings is None:
        return _area(item.bbox)
    return sum(polygon_area(ring) for ring in rings)


def _ink_overlap(first: Item, second: Item,
                 intersection: Rect) -> tuple[float, Rect]:
    """Refine a box-against-box overlap using whatever real geometry is there.

    Only one side can need it: the rule already requires the other to be text,
    whose box is its ink. That is what keeps this exact rather than approximate
    -- clipping a concave ribbon to a rectangle is Sutherland-Hodgman's own
    case, where clipping two concave outlines to each other would not be.
    """
    shape = second if first.is_text else first
    if shape.is_text:
        return _area(intersection), intersection
    rings = _rings(shape)
    if rings is None:
        return _area(intersection), intersection
    box = (first if shape is second else second).bbox
    area = sum(area_within(ring, box) for ring in rings)
    return area, intersection


def rule_inconsistent_stroke(ctx: LintContext) -> list[Diagnostic]:
    """Too many distinct line weights reads as accidental rather than designed.

    Widths the author declared as data -- `inklet.encoded(kind)` -- sit outside
    the count. A ribbon chart legitimately draws thirty widths, and reporting
    each step of one scale as a separate choice buries every real finding under
    the figure working correctly. The excluded count is still named in the
    message, so the exemption is never silent.

    The count alone is not a finding anyone can act on. A themed figure already
    spends most of its budget on the theme's own weights, so being told it has
    four of them, listed in order of size, leaves the author to work out which
    one was the mistake. The odd weight out is the rare one: a design system
    gets used over and over and an accident gets used once. So the message
    carries how many items wear each width, and the hint names the rarest
    rather than reciting the range.
    """
    widths: dict[float, str] = {}
    counts: dict[float, int] = {}
    scale: set[float] = set()
    for item in ctx.items:
        width = _effective_stroke(item)
        if width is None:
            continue
        key = round(width, 2)  # 0.01mm buckets; finer is float noise, not design
        if item.encodes_width:
            scale.add(key)
            continue
        counts[key] = counts.get(key, 0) + 1
        if key not in widths or item.id < widths[key]:
            widths[key] = item.id
    if len(widths) <= ctx.max_stroke_widths:
        return []
    ordered = sorted(widths)
    listing = ", ".join(f"{w:.2f}mm on {counts[w]} ({ctx.label(widths[w])})"
                        for w in ordered)
    extra = scale - set(ordered)
    note = (f"; {len(extra)} further width(s) carry data and were not counted"
            if extra else "")
    return [Diagnostic(
        code="INCONSISTENT_STROKE",
        severity="info",
        message=(f"figure uses {len(ordered)} distinct stroke widths "
                 f"(max {ctx.max_stroke_widths}): {listing}{note}"),
        targets=tuple(widths[w] for w in ordered),
        where=None,
        hint=_stroke_hint(ordered, counts, ctx.max_stroke_widths),
    )]


def _stroke_hint(ordered: Sequence[float], counts: Mapping[float, int],
                 cap: int) -> str:
    """Which weights to fold away, rarest first.

    Ties break on the width itself so two equally rare weights come back in the
    same order on every run; a hint that reshuffles between runs is a hint a
    fix loop cannot diff.
    """
    spare = sorted(ordered, key=lambda w: (counts[w], w))[:len(ordered) - cap]
    naming = ", ".join(f"{w:.2f}mm" for w in spare)
    keeping = sorted(set(ordered) - set(spare))
    return (f"fold {naming} into a neighbouring weight -- it is the least used "
            f"here, and {cap} weights is the budget: "
            f"{' / '.join(f'{w:.2f}mm' for w in keeping)}")


# Below this many pairs, a group still reads one line at a time and naming
# both halves of each pair is the more actionable report. At or above it, the
# same gap repeating under one container is an arrangement rather than an
# accident, and the pairs bury everything else.
_CROWDING_GROUP_MIN = 3

# Kinds whose position was *computed from a source* rather than chosen by a
# layout: `inklet.plot` marks come from the scales, `inklet.three` facets and strokes
# come from the mesh. Two of them a fifth of a millimetre apart is what the
# measurement or the geometry says, and telling an author to separate them asks
# them to falsify the figure.
#
# A colorbar's bands are the same story with a sharper edge. `_bands` draws each
# slice a whole band long into its neighbour's space, so that the antialiased
# seam falls inside solid colour instead of showing as a pale rule across the
# bar. Slices exactly two apart therefore *abut*, and `Rect.overlap` returns
# None for a zero-area intersection -- so an abutment arrives here as a 0.00mm
# gap. Left out, the library's own key generator cannot lint clean at any step
# count, which puts noise in the one channel a blind author has.
#
# Deliberately absent: ticks, spines, tick labels, legends, model *labels*.
# Those are furniture placed around the computed thing, and they collide for
# real -- which is most of what this rule is for.
_COMPUTED_KINDS = frozenset({
    "mark", "mark-line", "colorband",
    "model-facet", "model-outline", "model-crease", "model-ink",
})

# Wrappers that carry a transform and nothing else. `translated()` makes one per
# mark, so a scatter's points are never each other's siblings -- their nearest
# shared *structural* ancestor is the panel. Skipping past these is what lets
# "same mark set" be asked at all.
_POSITIONING_KINDS = frozenset({"place", "g"})

#: `Figure.build` wraps everything in one of these, and names it.
PAGE_KIND = "page"


def rule_crowding(ctx: LintContext) -> list[Diagnostic]:
    """Neighbours that clear each other but only just.

    Restricted to pairs that do not overlap and are not nested, so a label in
    its box never trips it. Same quadratic-with-bucketing shape as OVERLAP; the
    grid is padded by the clearance so near misses still share a cell.

    A pair the boxes call close is measured again on ink before it is reported
    (`_ink_box`): a line box is taller than its glyphs and wider than them by
    two side bearings, and a reader sees the glyphs. The re-measure can only
    open the gap, never close it, so it takes findings away and never adds
    one -- which also means a pair whose *line* boxes overlap is still left to
    OVERLAP even when the ink between them is a tenth of a millimetre.

    Two things keep the output readable, and both are about intent rather than
    tolerance -- raising the clearance would hide real findings instead:

    * A link's own geometry is exempt against the shapes it was routed to.
      `inklet` clips connectors to the real boundary on purpose, so a 0.00mm gap
      between an arrowhead and its target is the arrow working. A head near a
      box the link has nothing to do with is still reported.
    * Pairs sharing a container *and* a gap collapse into one finding. A grid's
      cells are meant to be evenly and tightly spaced; reporting all 49 of its
      neighbouring pairs separately is quadratic noise around a single fact.
      `targets` still names every node involved, so nothing actionable is lost.
    * A pair inside one `inklet.abutting(kind)` node. Unlike everything above
      that is a declaration rather than an inference -- see `diagnostics.abut`.
    * An arrowhead against a shape on its own axis. A head lands on what it
      points at, and the shaft is cut back by the head's length so its base
      lands on what it leaves; `is_attached` says so for a routed link, and
      `_along_the_arrow` says the same for a head an author drew.
    * Two strokes drawn into one `inklet.plot` panel. Their spacing is the data's
      -- see `_drawn_into`, which is `_sealed_in` for shapes that carry no
      `mark` kind to recognise them by.
    * Two things a stack was *asked* to put this far apart -- see
      `_spaced_on_purpose`.
    * Arrowheads converging on one shape are pooled by that shape rather than
      reported pair by pair -- see `_same_arrival`.
    * Two fragments of one authored block: the letters of a curved label are
      meant to be a letter-space apart -- see `_one_block`.
    * Text that sits on a plate, against anything outside that plate. The
      plate is the ink the reader sees a gap to, and it is always the nearer
      of the two, so the text's own pair restates a finding the plate has
      already made -- `stress/mega_figure.py` panel (p) said "box and
      label-plate 0.19mm" and "box and '1 s' 0.79mm" about one collision.
    """
    candidates = [i for i in ctx.items if _pairable(ctx, i)]
    boxes = [i.bbox for i in candidates]
    clearance = ctx.min_clearance_mm
    # The same-source and abutting tests below, asked once per item instead of
    # once per pair. Both are a `continue` either way; asking them first is
    # what keeps a shaded mesh from costing a quadratic number of ancestor
    # walks. A declaration outranks the source home because it is the stronger
    # claim: it covers the whole subtree, sources and layout alike.
    apart = [ctx.abutting_home(item.id) or _sealed_in(ctx, item)
             or _drawn_into(ctx, item) or _one_block(item)
             for item in candidates]
    plates: dict[str, Item | None] = {}

    groups: dict[tuple[str | None, float], list[tuple[Item, Item, float]]] = {}
    objects: dict[tuple[str, str], list[tuple[Item, Item, float]]] = {}
    against: dict[tuple[str, str], list[tuple[Item, Item, float]]] = {}
    fans: dict[str, list[tuple[Item, Item, float]]] = {}
    for a, b in _candidate_pairs(boxes, pad=clearance, apart=apart):
        first, second = candidates[a], candidates[b]
        if ctx.is_related(first.id, second.id):
            continue
        if ctx.is_attached(first.id, second.id):
            continue
        if _same_connector(ctx, first.id, second.id):
            continue
        homes = _source_homes(ctx, first, second)
        if homes is not None and _same_object(ctx, *homes):
            continue
        if first.bbox.overlap(second.bbox) is not None:
            continue  # OVERLAP's business, not ours
        gap = _gap(first.bbox, second.bbox)
        if gap >= clearance - _EPS_MM:
            continue
        gap = _ink_gap(ctx, first, second)
        if gap >= clearance - _EPS_MM:
            continue  # line boxes, not glyphs, were what came close
        if _is_leading(ctx, first, second, gap):
            continue
        if _spaced_on_purpose(ctx, first, second):
            continue
        if _along_the_arrow(first, second) or _along_the_arrow(second, first):
            continue
        if (_spoken_for(ctx, plates, first, second)
                or _spoken_for(ctx, plates, second, first)):
            continue
        if homes is not None:
            # Keyed on what the author named, not on the group the facets
            # happened to land in. `scene` splits one part's triangles across a
            # group per depth-sorted run, and keying on those turned two
            # touching parts into a finding per pair of runs.
            objects.setdefault(_object_pair(ctx, first.id, second.id),
                               []).append((first, second, gap))
            continue
        arrival = _same_arrival(ctx, first, second)
        if arrival is not None:
            fans.setdefault(arrival, []).append((first, second, gap))
            continue
        lone = _lone_object(ctx, first, second)
        if lone is not None:
            against.setdefault(lone, []).append((first, second, gap))
            continue
        # Bucketed at the precision the message prints in, so "the same gap"
        # means the same thing to the grouping as it does to the reader.
        key = (ctx.common_ancestor(first.id, second.id), round(gap, 2))
        groups.setdefault(key, []).append((first, second, gap))

    out: list[Diagnostic] = []
    for (container, rounded), pairs in groups.items():
        if container is None or len(pairs) < _CROWDING_GROUP_MIN:
            out.extend(_crowded_pair(first, second, gap, clearance)
                       for first, second, gap in pairs)
        else:
            out.append(_crowded_group(ctx, container, rounded, pairs, clearance))
    out.extend(_crowded_objects(ctx, homes, pairs, clearance)
               for homes, pairs in objects.items())
    out.extend(_crowded_against(ctx, key, pairs, clearance)
               for key, pairs in against.items())
    out.extend(_crowded_fan(ctx, target, pairs, clearance)
               for target, pairs in sorted(fans.items()))
    out.extend(stroke_near_misses(ctx, clearance))
    return out


def _spoken_for(ctx: LintContext, plates: dict[str, "Item | None"],
                text: Item, other: Item) -> bool:
    """Whether `text`'s backdrop already states this clearance.

    A label knocked out on a plate is not the nearest ink on its side of the
    gap; the plate is, and by containment the plate's gap to anything outside
    it is the smaller of the two. So the pair against the text says the same
    thing as the pair against the plate, a tenth of a millimetre less
    urgently, and an author reading both moves one thing twice.

    Nothing is lost when the plate is left out of `CROWDING` for touching its
    neighbour: that is `OVERLAP`'s finding, and it is the louder one.
    """
    if not text.is_text:
        return False
    if text.id not in plates:
        plates[text.id] = ctx.background_of(text)[1]
    plate = plates[text.id]
    return (plate is not None and plate.id != other.id
            and not _contains(plate.bbox, other.bbox))


def _spaced_on_purpose(ctx: LintContext, first: Item, second: Item) -> bool:
    """Whether the only thing between these two is a gap the author chose.

    The clearance floor is a guess about reading: a millimetre is roughly what
    two things need in order to look like two things. A stack's `gap=` is not
    a guess -- it is a number the author wrote, usually as a theme token, and
    it applies to every pair the stack creates. `stress/mega_figure.py` asked
    for `th.gap("2xs")` between a swatch and its percentage three times and
    was told three times that half a millimetre is too little, which is a
    complaint about the theme's smallest token dressed up as a complaint about
    a figure. There is nothing to move: moving it means not using the token.

    So the exemption is deliberately narrow, and each condition is load
    bearing. The two items are in *adjacent* children of the stack, because a
    stack only ever separates neighbours -- anything closer than the gap
    between children two apart got there some other way. The distance between
    them *along the stack's axis* is the declared gap to within `_EPS_MM`,
    because that is what it means for this gap to be the stack's doing: a
    child whose ink reaches further than its neighbour's, or two things pushed
    together inside one child, both come out under the declared figure and
    stay findings.

    Read through `getattr` on `notes`, core's annotation slot (M17), with the
    plain `stack_gap` attribute as a fallback: a tree built by hand, by an
    older version, or by something that is not a stack at all simply has no
    declaration to honour, and says so by having nothing there.
    """
    container = ctx.common_ancestor(first.id, second.id)
    node = ctx.nodes.get(container) if container is not None else None
    if node is None or (node.kind != _GRID_KIND and node.kind not in _BLOCK_KINDS):
        return False
    slots = _slots_under(ctx, node, container, first, second)
    if slots is None:
        return False
    if node.kind == _GRID_KIND:
        return _grid_gap_asked_for(node, slots, first, second)
    if node.kind not in _BLOCK_KINDS:
        return False
    asked = getattr(node, "notes", {}).get("gap")
    if asked is None:
        asked = getattr(node, "stack_gap", None)
    unit = _stack_axis(node)
    if not isinstance(asked, (int, float)) or unit is None:
        return False
    mine, theirs = slots
    if abs(mine - theirs) != 1:
        return False
    along = _gap_along(unit, first.bbox, second.bbox)
    return abs(along - float(asked)) <= _EPS_MM


def _slots_under(ctx: LintContext, node: Diagram, container: str,
                 first: Item, second: Item) -> tuple[int, int] | None:
    """Which child of `container` each item lives under, by position.

    A container separates its own children; anything below one of them got
    where it is by some other means, so the pair is only the container's doing
    if the two items descend from two different children of it.
    """
    depth = len(ctx.chain(container))
    indices = ctx._memo.setdefault("child_indices", {})
    kids = indices.get(container)
    if kids is None:
        kids = indices[container] = {child.id: index for index, child in enumerate(node.children)}
    mine = kids.get(ctx.chain(first.id)[depth])
    theirs = kids.get(ctx.chain(second.id)[depth])
    if mine is None or theirs is None:
        return None
    return mine, theirs


def _grid_gap_asked_for(node: Diagram, slots: tuple[int, int],
                        first: Item, second: Item) -> bool:
    """`_spaced_on_purpose` for a grid, where adjacency is two-dimensional.

    A grid is not a stack with a longer index. Cells 1 and 2 of a three-column
    grid are neighbours in the child list and on opposite sides of the page,
    because the row wrapped between them; the cell directly *below* cell 1 is
    three slots away and is the pair a reader actually sees as a pair. So the
    test is on the row and column, never on the child index: same row and
    columns one apart is the column gap's doing, same column and rows one
    apart is the row gap's, and everything else -- diagonals, wrap-arounds,
    anything further -- stays a finding.

    Two gaps, so two declarations: `col_gap` is checked across the row and
    `row_gap` down the column, each against the distance measured along its
    own axis. The older `gap` note is `min` of the two and is deliberately not
    read here -- on a grid whose gaps differ it would report the row spacing
    as the column's intent.

    Silent on a grid that records nothing, which is every grid built before
    `layout/flow.py` began writing these notes: the pair is then reported the
    way it is today, and no figure gets quieter by accident.
    """
    cells = (_grid_cell(node, slots[0]), _grid_cell(node, slots[1]))
    if cells[0] is None or cells[1] is None:
        return False
    (row, col), (other_row, other_col) = cells
    notes = getattr(node, "notes", {})
    if row == other_row and abs(col - other_col) == 1:
        asked, unit = notes.get("col_gap"), Vec2(1.0, 0.0)
    elif col == other_col and abs(row - other_row) == 1:
        asked, unit = notes.get("row_gap"), Vec2(0.0, 1.0)
    else:
        return False
    if not isinstance(asked, (int, float)) or isinstance(asked, bool):
        return False
    along = _gap_along(unit, first.bbox, second.bbox)
    return abs(along - float(asked)) <= _EPS_MM


def _grid_cell(node: Diagram, slot: int) -> tuple[int, int] | None:
    """The (row, column) of a grid's `slot`-th child, or None if unrecorded.

    `layout/flow.py` writes `grid_cells` as one pair per child in
    `node.children` order, which is why this looks the cell up by position
    rather than by node id: `copy()` remints ids and does not reorder
    children. A grid built before that note existed has nothing here, and the
    caller then declines to exempt anything.
    """
    notes = getattr(node, "notes", {})
    if not isinstance(notes, Mapping):
        return None
    listed = notes.get("grid_cells")
    if not isinstance(listed, Sequence) or not 0 <= slot < len(listed):
        return None
    return _as_cell(listed[slot])


def _as_cell(value: object) -> tuple[int, int] | None:
    """`value` as a (row, column) pair of non-negative ints, or None."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) != 2:
        return None
    row, col = value
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
               for v in (row, col)):
        return None
    return (row, col)


def _stack_axis(node: Diagram) -> Vec2 | None:
    """Which way a stack stacked, as a unit vector, or None if it cannot tell.

    `inklet.layout.flow` records it as the `gap_axis` note beside the gap itself,
    which is the reading that survives: a stack nested in another is
    `replace()`d when its parent positions it, and the plain `stack_axis`
    attribute an earlier round wrote does not survive that. Failing both, the
    axis is read back off the geometry. Two children a stack separated are
    disjoint along it and, at any `align`, overlapping or flush across it; if
    that is true of neither pair of edges this is not a run of things in a
    line and the exemption does not apply.
    """
    noted = getattr(node, "notes", {})
    stamped = noted.get("gap_axis") if isinstance(noted, Mapping) else None
    if not isinstance(stamped, Vec2):
        stamped = getattr(node, "stack_axis", None)
    if isinstance(stamped, Vec2):
        return stamped
    boxes = []
    for child in node.children:
        try:
            boxes.append(child.bbox)
        except DiagramError:
            continue                        # an empty child occupies no line
        if len(boxes) == 2:
            break
    if len(boxes) < 2:
        return None
    first, second = boxes
    if first.x1 <= second.x0 + _EPS_MM or second.x1 <= first.x0 + _EPS_MM:
        return Vec2(1.0, 0.0)
    if first.y1 <= second.y0 + _EPS_MM or second.y1 <= first.y0 + _EPS_MM:
        return Vec2(0.0, 1.0)
    return None


def _gap_along(unit: Vec2, first: Rect, second: Rect) -> float:
    """Clear distance between two boxes measured along `unit`, or 0 if they
    overlap on it. Projection, so a diagonal stack axis works too."""
    def span(box: Rect) -> tuple[float, float]:
        reach = [unit.x * x + unit.y * y
                 for x in (box.x0, box.x1) for y in (box.y0, box.y1)]
        return min(reach), max(reach)

    low, high = span(first)
    other_low, other_high = span(second)
    return max(other_low - high, low - other_high, 0.0)


#: A gap between two lines of type, as a multiple of the type size. Leading is
#: usually a fifth of this; a whole size between them is loose but still one
#: block, and past it they read as two.
_LEADING_MULTIPLE = 1.0

#: Containers that put their children in a deliberate one-dimensional
#: sequence, where "adjacent" means the child index differs by one.
_BLOCK_KINDS = frozenset({"stack"})

#: The two-dimensional one, which needs its own adjacency test and has two
#: declared gaps rather than one. See `_grid_gap_asked_for`.
_GRID_KIND = "grid"


def _same_connector(ctx: LintContext, a: str, b: str) -> bool:
    """Whether two nodes are both parts of one routed connector.

    A link draws up to four things -- a shaft, a head, a label, and the plate
    that keeps the label off whatever it crosses -- and the router decides
    where all four go. The head resting a fraction of a millimetre off its own
    label plate is a label sitting on an arrow, which is the connector working;
    there is nothing in that message for an author to move. `is_attached` is
    the same idea one step further out, covering the head against the shape it
    was clipped to.
    """
    ancestor = ctx.common_ancestor(a, b)
    node = ctx.nodes.get(ancestor) if ancestor is not None else None
    return node is not None and node.kind == LINK_KIND


def _is_leading(ctx: LintContext, first: Item, second: Item, gap: float) -> bool:
    """Whether a sub-clearance gap between two text items is line spacing.

    The clearance floor is a distance between *objects*: a millimetre is about
    what two things on a page need in order to read as two things. Lines of
    type are not two things, and their spacing is not measured in millimetres
    at all -- leading is a multiple of the type size, and at 6pt the ink of one
    line clears the next by four tenths of a millimetre. That is a well-set
    paragraph. Reporting it asks the author to open their leading to a third of
    a line in order to satisfy a constant that was never about type, and an
    author with no way to look at the page will do exactly that.

    Three things have to hold and each is doing work. Both items are text,
    because two boxes that close really are crowded. The gap is across the
    lines rather than along them, because words jammed together sideways are
    precisely what this rule should catch. And a stack put them there, which is
    the author saying they belong to one block -- two labels that merely happen
    to land near each other still get a word.
    """
    if not (first.is_text and second.is_text):
        return False
    if not _across_the_lines(first.bbox, second.bbox):
        return False
    container = ctx.common_ancestor(first.id, second.id)
    node = ctx.nodes.get(container) if container is not None else None
    if node is None or node.kind not in _BLOCK_KINDS:
        return False
    size = max(_effective_font_mm(first), _effective_font_mm(second))
    return gap <= _LEADING_MULTIPLE * size


#: cos of the half-angle within which a neighbour counts as lying on an
#: arrow's own line. 0.8 is 37 degrees, and the corpus is nowhere near it:
#: every head-against-its-target pair in `stress/mega_figure`'s two graph
#: panels scores above 0.93, and the one pair that is genuinely side by side
#: -- two heads converging on the same box from different directions --
#: scores 0.15. There is no threshold to tune between those.
_ARROW_AXIS_COS = 0.8


def _arrow_axis(item: Item) -> tuple[Vec2, Vec2] | None:
    """(tip, base midpoint) of a triangular arrowhead, in figure space.

    Found geometrically rather than by vertex order, because the order is the
    private business of whoever built the triangle -- `inklet.links` puts the tip
    first and a figure drawing its own arrows need not. The apex is the vertex
    farthest from the middle of the side opposite it, which is the apex of any
    triangle longer than it is wide, and an arrowhead always is.
    """
    if item.node.kind != HEAD_KIND or not isinstance(item.prim, PathPrim):
        return None
    points = [p for sub in item.prim.subpaths for p in sub.points]
    if len(points) != 3:
        return None       # an `open` head is unfilled and a `dot` has no axis
    world = [item.world.apply(p) for p in points]
    bases = [(world[(i + 1) % 3] + world[(i + 2) % 3]) * 0.5 for i in range(3)]
    apex = max(range(3), key=lambda i: (world[i] - bases[i]).length)
    return world[apex], bases[apex]


def _nearest_in(box: Rect, point: Vec2) -> Vec2:
    """The point of `box` closest to `point`; `point` itself when inside."""
    return Vec2(min(max(point.x, box.x0), box.x1),
                min(max(point.y, box.y0), box.y1))


def _along_the_arrow(head: Item, other: Item) -> bool:
    """Whether `other` sits on `head`'s own line, ahead of it or behind it.

    An arrowhead has two ends and both of them are meant to land on
    something. The tip rests on the shape the arrow points at -- that is what
    an arrow is -- and because the shaft is cut back by the head's length so
    the two do not pile up into a bulge, the *base* rests where the line left
    its source. Either way there is nothing in the message for an author to
    move: the head is wherever the shaft ends, and the shaft ends where the
    two shapes are.

    `is_attached` already says this for a link the router built, reading the
    `attached_to` it wrote down. A figure that draws its own arrows -- because
    it needs a self-loop, or two separated reciprocal arcs, neither of which
    `inklet.links` can route -- has no such record, and 24 of the 78 infos on
    `stress/mega_figure` were that gap. This is the same fact asked of the
    geometry instead.

    A shape *beside* a head is still a finding, which is the case worth
    keeping: two arrowheads converging on one box from different directions
    really can collide.
    """
    axis = _arrow_axis(head)
    if axis is None:
        return False
    tip, base = axis
    span = tip - base
    if span.length <= _EPS_MM:
        return False
    forward = span.normalized()
    for anchor, direction in ((tip, forward), (base, -forward)):
        towards = _nearest_in(other.bbox, anchor) - anchor
        if towards.length <= _EPS_MM:
            return True     # touching at the tip, or at the base
        if towards.normalized().dot(direction) >= _ARROW_AXIS_COS:
            return True
    return False


def _across_the_lines(a: Rect, b: Rect) -> bool:
    """True when the whole gap between two boxes is vertical.

    Same decomposition `_gap` uses: no horizontal separation means the columns
    overlap, so one box sits above the other rather than beside it.
    """
    return max(a.x0 - b.x1, b.x0 - a.x1, 0.0) <= _EPS_MM


def _source_homes(ctx: LintContext, first: Item,
                  second: Item) -> tuple[str, str] | None:
    """The two containers a pair of computed parts came out of, or None when
    this is not a pair of computed parts at all.

    Equal homes means one source: marks inside one plot were positioned by one
    pair of scales, facets inside one solid by one mesh, and their spacing is
    the source speaking rather than a layout slip. Different homes means two
    objects that nearly touch -- a real finding, but one to report about the
    *objects*, not about triangle 33011 and triangle 33021.
    """
    if not (first.is_computed and second.is_computed):
        return None
    mine, theirs = _source_home(ctx, first.id), _source_home(ctx, second.id)
    if mine is None or theirs is None:
        return None
    return (mine, theirs) if mine <= theirs else (theirs, mine)


def _sealed_in(ctx: LintContext, item: Item) -> str | None:
    """The named object whose *source* placed this item, or None.

    Two items with the same non-None answer are exactly the pair
    `_source_homes` finds and `_same_object` discards: both computed, both
    with a source home, one named object above both. Precomputing it per item
    is what lets `_candidate_pairs(apart=)` skip them all without walking an
    ancestor chain for each, and the answer is the same either way -- the rule
    reaches `continue` on every one of them.
    """
    if not item.is_computed:
        return None
    home = _source_home(ctx, item.id)
    return None if home is None else _object_of(ctx, home)


def _source_home(ctx: LintContext, node_id: str) -> str | None:
    """The nearest ancestor that is structure rather than a transform."""
    for ancestor in reversed(ctx.chain(node_id)[:-1]):
        node = ctx.nodes.get(ancestor)
        if node is not None and node.kind not in _POSITIONING_KINDS:
            return ancestor
    return None


#: `inklet.plot`'s data area. Everything under it sits where a scale put it.
_PANEL_KIND = "panel"

#: Shapes an author draws as *geometry*, as opposed to furniture placed near
#: it. A `Panel.draw` polyline is one of these and a tick label is not.
_DRAWN_KINDS = frozenset({"path", "polyline", "polygon", "curve",
                          "mark", "mark-line"})


def _drawn_into(ctx: LintContext, item: Item) -> str | None:
    """The plot panel that put this stroke where it is, or None.

    `_sealed_in` answers the same question for a `mark`, by kind. It cannot
    answer it for a stroke, because `inklet.path` is a hand-drawn shape
    everywhere else on the page -- but a stroke reached through `Panel.draw`
    is at data coordinates just as much as a scatter point is, and 416 pairs
    of one panel's 120 traces reporting "add 0.63mm of separation" asks the
    author to redraw the measurement. What makes it answerable is that the
    panel is directly overhead: `Panel.draw` wraps each shape in a `place` and
    nothing else, so a stroke whose nearest structural ancestor is a `panel`
    was drawn into that panel's data area and a stroke anywhere else was not.
    """
    if item.is_text or item.node.kind not in _DRAWN_KINDS:
        return None
    home = _source_home(ctx, item.id)
    if home is None:
        return None
    node = ctx.nodes.get(home)
    return home if node is not None and node.kind == _PANEL_KIND else None


def _lone_object(ctx: LintContext, first: Item,
                 second: Item) -> tuple[str, str] | None:
    """A furniture item against one named computed object, or None.

    The mirror image of `_source_homes`: exactly one side was placed by a
    source, and the thing it was placed inside has a name. A label 0.1mm from
    a mesh is one finding about the label and the mesh, however many triangles
    of that mesh its bounding box happens to reach -- and a cartoon beta strand
    is a single triangle 20mm across, so it reaches plenty. Nothing named above
    the computed side means there is nothing better to point at than the facet
    itself, and the pair goes down the ordinary path.
    """
    computed = [item for item in (first, second) if item.is_computed]
    if len(computed) != 1:
        return None
    mark = computed[0]
    free = second if mark is first else first
    object_id = _object_of(ctx, mark.id)
    return None if object_id == mark.id else (free.id, object_id)


def _same_arrival(ctx: LintContext, first: Item, second: Item) -> str | None:
    """The shape two crowded arrowheads both point at, or None.

    A hub with eight arrows into it is one decision -- the hub is too small,
    or the sources are too close together, or the heads are too big -- and it
    arrives as up to twenty-eight pairs, each naming two anonymous triangles.
    `stress/dense_graph.py` reported "3 pairs of items inside links89 are
    0.53mm apart" and "4 pairs ... 0.54mm", which says nothing about where to
    look or what to change. Pooled by the shape they converge on, the same
    fact is one sentence with a name in it and a fix that exists.

    Only heads of *different* links count: one link's two heads belong to one
    arrow, and `_same_connector` has already dealt with them.
    """
    if first.node.kind != HEAD_KIND or second.node.kind != HEAD_KIND:
        return None
    mine, theirs = _arrival_of(ctx, first), _arrival_of(ctx, second)
    if mine is None or theirs is None or mine != theirs:
        return None
    return mine


def _arrival_of(ctx: LintContext, head: Item) -> str | None:
    """The endpoint shape an arrowhead rests on, by its tip.

    Read from the geometry rather than from `attached_to`'s order, because a
    link wears a head at either end or both and only the tip knows which end
    this one is. `link_ends` gives the two candidates; the tip picks.
    """
    owner = _link_owner(ctx, head.id)
    if owner is None:
        return None
    axis = _arrow_axis(head)
    if axis is None:
        return None
    tip = axis[0]
    best: tuple[float, str] | None = None
    for end in link_ends(ctx.attachments[owner]):
        # The endpoint is usually a group -- a `framed` box, a panel -- and a
        # group draws nothing, so `ctx.item` has no entry for it. Its
        # placement does.
        placement = ctx.placements.get(end)
        box = None if placement is None else placement.bbox
        if box is None:
            continue
        reach = (_nearest_in(box, tip) - tip).length
        if best is None or reach < best[0]:
            best = (reach, end)
    return None if best is None else best[1]


def _crowded_fan(ctx: LintContext, target: str,
                 pairs: Sequence[tuple[Item, Item, float]],
                 clearance: float) -> Diagnostic:
    """One finding for every arrowhead crowding another on one shape."""
    heads: dict[str, Item] = {}
    where = pairs[0][0].bbox
    for first, second, _ in pairs:
        heads[first.id] = first
        heads[second.id] = second
        where = where.union(first.bbox).union(second.bbox)
    tightest = min(gap for _, _, gap in pairs)
    named = _object_label(ctx, target)
    # Every link that lands here, not only the ones in a crowded pair: the
    # number an author needs is how much traffic the shape is taking.
    arriving = _arrivals(ctx).get(target, set())
    size = max((_head_length(head) for head in heads.values()), default=0.0)
    return Diagnostic(
        code="CROWDING",
        severity="info",
        message=(f"{len(arriving)} links arrive at {named}; their heads are "
                 f"{_mm(tightest)} apart, under the {_mm(clearance)} clearance"),
        targets=tuple(sorted(heads)),
        where=where,
        hint=(f"spread the shapes feeding {named} further apart, or draw the "
              f"heads smaller than arrow_size={size:g}"),
    )


def _arrivals(ctx: LintContext) -> dict[str, set[str]]:
    """{shape id: the links whose heads land on it}. Memoised per lint."""
    known = ctx._memo.get("arrivals")
    if known is None:
        known = ctx._memo["arrivals"] = {}
        for item in ctx.items:
            if item.node.kind != HEAD_KIND:
                continue
            target = _arrival_of(ctx, item)
            owner = _link_owner(ctx, item.id)
            if target is not None and owner is not None:
                known.setdefault(target, set()).add(owner)
    return known


def _head_length(head: Item) -> float:
    axis = _arrow_axis(head)
    return 0.0 if axis is None else (axis[0] - axis[1]).length


def _crowded_against(ctx: LintContext, key: tuple[str, str],
                     pairs: Sequence[tuple[Item, Item, float]],
                     clearance: float) -> Diagnostic:
    """One finding for a label against one object, however many parts it met."""
    free_id, object_id = key
    where = pairs[0][0].bbox
    involved: set[str] = set()
    for first, second, _ in pairs:
        where = where.union(first.bbox).union(second.bbox)
        involved.update((first.id, second.id))
    tightest = min(gap for _, _, gap in pairs)
    first, second, _ = min(pairs, key=lambda pair: pair[2])
    free = first if first.id == free_id else second
    places = "" if len(pairs) == 1 else f" at {len(pairs)} points"
    return Diagnostic(
        code="CROWDING",
        severity="info",
        message=(f"{free.described} and {_object_label(ctx, object_id)} are "
                 f"only {_mm(tightest)} apart{places}, under the "
                 f"{_mm(clearance)} clearance"),
        targets=tuple(sorted(involved)),
        where=where,
        hint=_crowding_hint(first, second, tightest, clearance,
                            named=_object_label(ctx, object_id)),
    )


def _object_pair(ctx: LintContext, first: str, second: str) -> tuple[str, str]:
    """Two items as the pair of named objects they belong to.

    Resolved from the items, not from their source homes: a home is only the
    nearest structural ancestor, and for anything sitting straight on the page
    that ancestor *is* the page.
    """
    mine, theirs = _object_of(ctx, first), _object_of(ctx, second)
    return (mine, theirs) if mine <= theirs else (theirs, mine)


def _same_object(ctx: LintContext, first: str, second: str) -> bool:
    """Whether two source containers are parts of one thing the author named.

    `_source_home` stops at the nearest structural ancestor, and inside a
    `inklet.model` that is a facet group rather than the model: a solid drawn as
    shaded faces *and* creases has two of them, whose triangles are 0.02mm
    apart because they are the same triangles seen twice. That produced the
    unanswerable "scan_lens and scan_lens come within 0.31mm".

    One named object above both means one source, which is what the
    equal-homes test was reaching for. Two sub-objects the author never named
    are suppressed with it -- there would be nothing in the message to move.
    """
    return first == second or _object_of(ctx, first) == _object_of(ctx, second)


def _crowded_pair(first: Item, second: Item, gap: float,
                  clearance: float) -> Diagnostic:
    return Diagnostic(
        code="CROWDING",
        severity="info",
        message=(f"{first.described} and {second.described} are only "
                 f"{_mm(gap)} apart, under the {_mm(clearance)} clearance"),
        targets=tuple(sorted((first.id, second.id))),
        where=first.bbox.union(second.bbox),
        hint=_crowding_hint(first, second, gap, clearance),
    )


def _crowding_hint(first: Item, second: Item, gap: float,
                   clearance: float, *, named: str | None = None) -> str:
    """What to do about it -- which depends on whether this is a layout at all.

    "Add separation" is the right answer when both sides were placed by a
    layout. It is the wrong answer, and a damaging one, when exactly one side
    was computed from data: a jittered cell sitting just inside its own violin,
    a mark against the contour it belongs to. Moving those apart falsifies the
    figure, which is the outcome `Item.is_computed` exists to prevent -- and an
    author with no way to look at the page will do exactly what the hint says.

    The pair is not exempt, and should not be: the exemption needs *both* sides
    computed, because a mark near a tick label really is crowded and that is
    most of what this rule is for. What the one-sided case needs is not silence
    but the other fix -- say that the drawn side is data too, and the pair goes
    quiet on the same terms as every other computed pair.

    Which is only ever true of a *shape*. Furniture is the other half of the
    pair here at least as often, and telling an author to declare a tick label
    as data would trade one wrong hint for a worse one -- it would silence the
    finding this rule exists to make. So the escape route is offered for drawn
    geometry and withheld from type and from axis parts, and in those cases the
    separation really is the fix.
    """
    computed = [item for item in (first, second) if item.is_computed]
    if len(computed) != 1:
        return f"add {_mm(clearance - gap)} of separation or padding"
    drawn = second if computed[0] is first else first
    # `named` is the object the computed side belongs to, when the caller has
    # already decided to talk about that instead of the facet.
    mark = named or computed[0].described
    room = f"add {_mm(clearance - gap)} of separation"
    if drawn.is_text or drawn.node.kind in _FURNITURE_KINDS:
        return (f"{mark} was positioned by data, so move "
                f"{drawn.described} rather than the mark -- {room}")
    return (f"{mark} was positioned by data, so moving it "
            f"changes what the figure says -- if {drawn.described} is data too, "
            f"pass kind=\"mark\" when you build it and this pair goes quiet; "
            f"otherwise {room}")


#: Parts placed *around* the computed thing rather than by it. Named here only
#: to keep `_crowding_hint` from suggesting they be declared as data; the
#: reason they are absent from `_COMPUTED_KINDS` is written there.
_FURNITURE_KINDS = frozenset({
    "spine", "tick", "tick-label", "axis-label", "axis",
    "legend", "label", "title", "gridline",
})


def _crowded_group(ctx: LintContext, container: str, gap: float,
                   pairs: Sequence[tuple[Item, Item, float]],
                   clearance: float) -> Diagnostic:
    where = pairs[0][0].bbox
    involved: set[str] = set()
    for first, second, _ in pairs:
        where = where.union(first.bbox).union(second.bbox)
        involved.update((first.id, second.id))
    label = ctx.label(container)
    node = ctx.nodes.get(container)
    noun = "cells" if node is not None and node.kind == "grid" else "items"
    return Diagnostic(
        code="CROWDING",
        severity="info",
        message=(f"{len(pairs)} pairs of {noun} inside {label} are {_mm(gap)} "
                 f"apart, under the {_mm(clearance)} clearance"),
        targets=tuple(sorted(involved)),
        where=where,
        hint=(f"add {_mm(clearance - gap)} of separation inside {label}, or "
              f"lower min_clearance_mm if the spacing is deliberate"),
    )


def _crowded_objects(ctx: LintContext, homes: tuple[str, str],
                     pairs: Sequence[tuple[Item, Item, float]],
                     clearance: float) -> Diagnostic:
    """One finding for two objects that nearly touch, however many of their
    parts are involved.

    An author moves the mirror, not the mirror's eleventh triangle. Panel a of
    `stress/mega_figure` produced 61 facet-pair infos across seven optics; the
    same geometry stated this way is six sentences, each naming something that
    can actually be moved.
    """
    where = pairs[0][0].bbox
    involved: set[str] = set()
    for first, second, _ in pairs:
        where = where.union(first.bbox).union(second.bbox)
        involved.update((first.id, second.id))
    tightest = min(gap for _, _, gap in pairs)
    left, right = (_object_label(ctx, home) for home in homes)
    parts = "" if len(pairs) == 1 else f" at {len(pairs)} points"
    return Diagnostic(
        code="CROWDING",
        severity="info",
        message=(f"{left} and {right} come within {_mm(tightest)}{parts}, "
                 f"under the {_mm(clearance)} clearance"),
        targets=tuple(sorted(involved)),
        where=where,
        hint=(f"move {left} or {right} {_mm(clearance - tightest)} apart; "
              f"their parts are placed by the source, so only the objects "
              f"themselves can be separated"),
    )


def _object_of(ctx: LintContext, node_id: str) -> str:
    """The nearest ancestor-or-self an author would recognise, which is a
    named one.

    A mesh's facet group is `model-facets33010`, and nobody named that. The
    `inklet.model` above it is `turning mirror`, and that is the thing to move.
    Nothing named anywhere above means the node is all there is to point at.

    The page is not a candidate however it is named. `Figure.build` names it,
    and above every object on the page is the page -- so a callout with nothing
    named between it and the sheet came back as `backbone and page2974 come
    within 0.00mm`, naming the one thing in a figure that cannot be moved.
    """
    for ancestor in reversed(ctx.chain(node_id)):
        node = ctx.nodes.get(ancestor)
        if node is not None and node.name and node.kind != PAGE_KIND:
            return ancestor
    return node_id


def _object_label(ctx: LintContext, node_id: str) -> str:
    """What to call the object a node belongs to. For anything the author
    named themselves this is just its own label."""
    return ctx.label(_object_of(ctx, node_id))


# -- LINK_CROSSES ---------------------------------------------------------
#
# A connector running through a shape it was never routed to is the most
# visible way a dense figure looks broken, and it is precisely what the bbox
# rules above cannot see: a vertical shaft's bounding box is *zero-width*, so
# no amount of box arithmetic will ever notice it, and `_pairable` drops
# unfilled paths for exactly that reason. This rule walks the shaft's real
# segments and asks each shape's own `Trace` -- the same ray question `link()`
# uses to find a boundary -- how much of each segment lands inside it.

#: A shaft is about a stroke wide, so a shorter incursion than this is a touch
#: rather than a crossing. Measuring the *interior run* rather than counting
#: boundary hits is also what disposes of the tangent case: a shaft sliding
#: along a box's edge registers hits on the two perpendicular edges and would
#: otherwise be indistinguishable from going straight through.
_MIN_CROSSING_MM = 0.2

#: Parity direction for point-in-outline. Deliberately off-axis: a ray fired
#: along an axis out of an axis-aligned rectangle is the one direction that
#: can leave through a corner and be counted twice.
_PARITY_DIR = Vec2(0.8660254037844387, 0.5)


def _link_owner(ctx: LintContext, node_id: str) -> str | None:
    """The routed link a node belongs to: the nearest ancestor-or-self whose
    `attached_to` records what it was built to touch."""
    for candidate in reversed(ctx.chain(node_id)):
        if candidate in ctx.attachments:
            return candidate
    return None


def _in_link_label(ctx: LintContext, node_id: str) -> bool:
    """True for a node inside a routed link's label group, plate included."""
    for candidate in ctx.chain(node_id):
        node = ctx.nodes.get(candidate)
        if node is not None and node.kind == LABEL_KIND:
            return True
    return False


def _boxes_touch(a: Rect, b: Rect) -> bool:
    """Overlap including the degenerate boxes `Rect.overlap` calls a miss --
    which is every segment of an axis-aligned shaft."""
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def _outline(item: Item) -> Trace:
    """The item's own boundary in figure space.

    Its *own*: `Placement.trace` unions in every child, which would make a box
    answer for the label inside it. And an outline rather than a box, because
    a shaft clipping the empty corner of an ellipse's bbox is a false positive
    and `Trace` is the thing that knows where the curve actually is.
    """
    return item.prim.trace().transform(item.world)


def _inside(outline: Trace, point: Vec2) -> bool:
    """Strictly inside a closed outline, by ray-casting parity.

    A point sitting *on* the boundary counts as outside, and that clause is
    the whole reason the tangent case works: a shaft sliding along a box's
    edge is a point on the boundary all the way along, and parity alone would
    call every one of those points interior and report the edge as a crossing.
    `_PARITY_DIR` is a unit vector, so a hit at |t| <= _EPS_MM is the boundary
    passing through the point itself.
    """
    hits = outline.hits
    if hits is None:
        return False
    ahead = 0
    for t in hits(point, _PARITY_DIR):
        if abs(t) <= _EPS_MM:
            return False
        if t > 0.0:
            ahead += 1
    return ahead % 2 == 1


def _interior_run(outline: Trace, a: Vec2, b: Vec2) -> float:
    """Millimetres of the segment a->b that lie inside a closed outline."""
    hits = outline.hits
    if hits is None:
        return 0.0
    span = b - a
    length = span.length
    # Ray parameters are in units of `span`, so a crossing inside the segment
    # is a t in (0, 1) and the gaps between crossings are the runs to measure.
    cuts = sorted({0.0, 1.0}.union(t for t in hits(a, span) if 0.0 < t < 1.0))
    inside = 0.0
    for lo, hi in zip(cuts, cuts[1:]):
        if _inside(outline, a + span * ((lo + hi) / 2)):
            inside += (hi - lo) * length
    return inside


def _shaft_segments(ctx: LintContext, item: Item) -> tuple[tuple[Vec2, Vec2], ...]:
    """A path prim's flattened geometry in figure space, built once per lint.

    Six rules walk every stroke in the figure, and each of them used to
    re-transform its points: on `stress/mega_figure.py` that was 18,418 calls
    and 95ms, the single largest line in the rule budget. The world frame a
    stroke lands in does not change between rules, so it is computed once and
    kept on the context, the way `path_rules._runs_of` already keeps the runs
    it builds on top of these.
    """
    cache = ctx._memo.setdefault("segments", {})
    known = cache.get(item.id)
    if known is None:
        known = cache[item.id] = _flatten_shaft(item)
    return known


def _flatten_shaft(item: Item) -> tuple[tuple[Vec2, Vec2], ...]:
    """The uncached flattening. `_shaft_segments` is the one rules should call.

    `Subpath.points` is always the flattened form, beziers included, so this
    follows a rounded elbow without knowing what a bezier is.

    Built as a list rather than yielded, and with the world transform's six
    coefficients hoisted out of the loop: a generator resumption per segment
    cost more here than the arithmetic it was pacing, because a figure of this
    weight has twelve thousand of them and two generators stacked on each.
    """
    prim = item.prim
    if not isinstance(prim, PathPrim):
        return ()
    world = item.world
    xx, yx, xy, yy, dx, dy = (world.a, world.b, world.c,
                              world.d, world.e, world.f)
    out: list[tuple[Vec2, Vec2]] = []
    for sub in prim.subpaths:
        raw = sub.points
        if len(raw) < 2:
            continue
        points = [Vec2(xx * p.x + xy * p.y + dx, yx * p.x + yy * p.y + dy)
                  for p in raw]
        if sub.closed:
            points.append(points[0])
        previous = points[0]
        for point in points[1:]:
            # `(point - previous).length` to the last bit, without the Vec2
            # the subtraction would allocate and immediately drop.
            if math.hypot(point.x - previous.x, point.y - previous.y) > _EPS_MM:
                out.append((previous, point))
            previous = point
    return tuple(out)


def _crossable(ctx: LintContext, owner: str, endpoints: Sequence[str],
               shape: Item) -> bool:
    """True when this link has no business touching this shape."""
    if ctx.is_related(owner, shape.id) or ctx.is_attached(owner, shape.id):
        return False
    # A container the link starts or ends *inside*: an arrow leaving a panel
    # has to cross the panel's own outline, and reporting that would fire on
    # every figure that nests anything.
    return not any(shape.id in ctx.chain(end) for end in endpoints)


def rule_link_crosses(ctx: LintContext) -> list[Diagnostic]:
    """A connector running straight through a shape it was not routed to.

    Only routed links are examined -- a node whose `attached_to` says which
    shapes it was clipped to. A hand-drawn `PathPrim` records no endpoints, so
    there is no way to tell a deliberate crossing from a mistake and it is
    left alone; a figure with no connectors at all pays nothing here.

    What is exempt, and why each one has to be:

    * The link's own endpoints and anything inside them (`is_attached`). A
      shaft necessarily meets what it was clipped to.
    * Anything the author declared with `through=`. A beam that stops at the
      dichroic it transmits through is a lie about the instrument; the
      alternative to this exemption is a figure that has to choose between
      being right and being quiet.
    * Any shape *containing* an endpoint. An arrow out of a panel must cross
      the panel.
    * Other links' shafts and heads. Connectors crossing each other is
      ordinary in a branch-and-merge flow. Their *labels* are not exempt: a
      plate covers the ink beneath it, but a connector routed later is drawn
      over the plate, and a word with a line through it is as broken here as
      anywhere. The router places labels off every shaft it knows about, so
      this fires when an author pinned `label_side` into the way.

    Severity is `warning`, except when the shaft cuts through glyphs: a line
    splitting a word reads as broken in the way `TEXT_OVERFLOW` does, so text
    is an `error`, the same two-tier split `OVERLAP` makes. A crossed label is
    folded into the finding for the box holding it rather than reported twice
    -- one line through a box and the word inside it is one defect.
    """
    if not ctx.attachments:
        return []

    shafts: dict[str, list[Item]] = {}
    for item in ctx.items:
        if not item.draws or not isinstance(item.prim, PathPrim) or item.prim.filled:
            continue
        owner = _link_owner(ctx, item.id)
        if owner is not None:
            shafts.setdefault(owner, []).append(item)

    candidates = [i for i in ctx.items
                  if _pairable(ctx, i) and (_link_owner(ctx, i.id) is None
                                       or _in_link_label(ctx, i.id))]
    if not shafts or not candidates:
        return []

    index = _PointIndex(candidates)
    outlines: dict[str, Trace] = {}
    out: list[Diagnostic] = []

    for owner in sorted(shafts):
        endpoints = ctx.attachments.get(owner, ())
        verdict: dict[str, bool] = {}
        depth: dict[str, float] = {}
        for item in shafts[owner]:
            for a, b in _shaft_segments(ctx, item):
                span = Rect.hull((a, b))
                for shape in index.overlapping(span):
                    if not _boxes_touch(span, shape.bbox):
                        continue
                    allowed = verdict.get(shape.id)
                    if allowed is None:
                        allowed = verdict[shape.id] = (
                            _link_owner(ctx, shape.id) != owner
                            and _crossable(ctx, owner, endpoints, shape))
                    if not allowed:
                        continue
                    outline = outlines.get(shape.id)
                    if outline is None:
                        outline = outlines[shape.id] = _outline(shape)
                    run = _interior_run(outline, a, b)
                    if run > 0.0:
                        depth[shape.id] = depth.get(shape.id, 0.0) + run
        out.extend(_crossings(ctx, owner, endpoints, depth))
    return out


def _crossings(ctx: LintContext, owner: str, endpoints: Sequence[str],
               depth: Mapping[str, float]) -> list[Diagnostic]:
    """One link's measured incursions, turned into findings in id order."""
    hit = {node_id: run for node_id, run in depth.items()
           if run >= _MIN_CROSSING_MM}
    crossed = [item for item in (ctx.item(node_id) for node_id in sorted(hit))
               if item is not None]

    # Geometric rather than structural containment, for the reason
    # `background_of` gives: `frame()` puts the rectangle and its label side by
    # side in the tree, so an ancestor test would miss the commonest idiom.
    cut_text: dict[str, list[str]] = {}
    for item in crossed:
        if not item.is_text:
            continue
        holder = min((other for other in crossed
                      if not other.is_text and _contains(other.bbox, item.bbox)),
                     key=lambda o: (_area(o.bbox), o.id), default=None)
        if holder is not None:
            cut_text.setdefault(holder.id, []).append(item.id)
    folded = {node_id for ids in cut_text.values() for node_id in ids}

    ends = link_ends(endpoints)
    between = " -> ".join(ctx.label(end) for end in ends)
    elbow_helps = _elbow_has_room(ctx, ends)

    # Parts of one object are one finding, for the reason `_crowded_objects`
    # gives: a shaft through a mesh cuts a dozen facets, and the author moves
    # the mirror rather than its eleventh triangle. A shape the author named
    # is its own object, so the ordinary figure is unaffected.
    groups: dict[str, list[Item]] = {}
    for item in crossed:
        if item.id in folded:
            continue
        # Text names itself by what it says, so it is never rolled into
        # anything: 'titanium headplate' tells an author more than the group
        # the label happens to sit in.
        home = item.id if item.is_text else _object_of(ctx, item.id)
        groups.setdefault(home, []).append(item)

    out: list[Diagnostic] = []
    for object_id in sorted(groups):
        parts = groups[object_id]
        texts = tuple(t for part in parts for t in cut_text.get(part.id, ()))
        note = ("" if not texts else ", cutting through "
                + ", ".join(ctx.item(t).described for t in texts))  # type: ignore[union-attr]
        label = _object_label(ctx, parts[0].id)
        deepest = max(hit[part.id] for part in parts)
        where = parts[0].bbox
        for part in parts[1:]:
            where = where.union(part.bbox)
        if len(parts) == 1:
            named = parts[0].described if parts[0].id == object_id else label
            through = f"{named} for {_mm(deepest)}"
        else:
            # Per-part runs of one object overlap in projection -- a ray
            # through a solid crosses its near facets and its far ones -- so
            # adding them up would report a length nothing on the page has.
            # The deepest single run is a measurement.
            through = (f"{label} across {len(parts)} of its parts, up to "
                       f"{_mm(deepest)} through one")
        out.append(Diagnostic(
            code="LINK_CROSSES",
            severity=("error" if texts or any(p.is_text for p in parts)
                      else "warning"),
            message=f"{ctx.label(owner)} ({between}) runs through {through}{note}",
            targets=(owner,) + tuple(sorted(p.id for p in parts)) + texts,
            where=where,
            # Moving the shape leads, because it is the fix that always
            # works. The elbow is only offered when it could actually turn.
            hint=_crossing_hint(label, between, elbow_helps),
        ))
    return out


#: Endpoints closer than this on an axis leave an elbow nowhere to turn.
_ELBOW_SLACK_MM = 0.5


def _elbow_has_room(ctx: LintContext, endpoints: tuple[str, ...]) -> bool:
    """Whether `route="orthogonal"` could route around anything at all.

    An elbow needs an offset on both axes to have a corner to put. Endpoints
    sharing a column -- a skip connection down one stack, which is exactly the
    case this rule fires on most -- collapse it to the same straight line, so
    suggesting it would send the author round in a circle.
    """
    boxes = [ctx.placements[end].bbox for end in endpoints if end in ctx.placements]
    if len(boxes) != 2 or any(box is None for box in boxes):
        return False
    first, second = (box.center for box in boxes)   # type: ignore[union-attr]
    return (abs(first.x - second.x) > _ELBOW_SLACK_MM
            and abs(first.y - second.y) > _ELBOW_SLACK_MM)


def _crossing_hint(label: str, between: str, elbow_helps: bool) -> str:
    options = [f"move {label} off the line between {between}"]
    if elbow_helps:
        options.append('give the link route="orthogonal" so it can turn around it')
    options.append(f"link via {label} in two hops")
    return ", or ".join(options)


def rule_route_blocked(ctx: LintContext) -> list[Diagnostic]:
    """A link that asked to go around the obstacles and could not.

    `route="avoid"` searches for a corridor and, when there is none -- an
    endpoint walled in, every way out sealed, or a figure so dense the search
    is called off before it starts -- draws the ordinary elbow instead. That
    is the right thing to draw, and the wrong thing to do silently: the
    author asked for something the figure could not give, and without this
    they would only find out by looking at a connector running through a box
    with no explanation of why avoiding it did not work.

    LINK_CROSSES reports the *consequence*, and only when the elbow really
    does cut through something. This reports the cause, whether or not the
    fallback happens to land badly, because the fix is different: crossing
    asks you to move a shape, this asks you to make room.
    """
    out: list[Diagnostic] = []
    for node_id in sorted(ctx.attachments):
        node = ctx.nodes.get(node_id)
        if node is None or FLAG_NO_CLEAR_ROUTE not in link_flags(node):
            continue
        endpoints = link_ends(ctx.attachments[node_id])
        between = " -> ".join(ctx.label(end) for end in endpoints)
        boxes = [ctx.placements[end].bbox for end in endpoints
                 if end in ctx.placements and ctx.placements[end].bbox is not None]
        out.append(Diagnostic(
            code="ROUTE_BLOCKED",
            severity="warning",
            message=(f"{ctx.label(node_id)} ({between}) asked to route around "
                     f"the shapes in its way and found no clear corridor; it "
                     f"was drawn as a plain elbow instead"),
            targets=(node_id,) + tuple(endpoints),
            where=boxes[0].union(boxes[1]) if len(boxes) == 2 else None,
            hint=("open a gap between the shapes it has to pass, move one of "
                  "them, or link in two hops via something in between"),
        ))
    return out


#: Why a connector came out unreadable, in the order the reasons are worth
#: hearing. A link that overlaps its target also has zero length, and being
#: told the cause is more use than being told the symptom, so the causes come
#: first and only the first match is reported.
_COLLAPSED: tuple[tuple[str, str, str], ...] = (
    (FLAG_COINCIDENT,
     "is between two shapes centred on the same point, so it has no direction "
     "to point in",
     "move one of them, or aim the link at an anchor on each rather than at "
     "the shapes"),
    (FLAG_OVERLAP,
     "runs between two shapes that overlap on the page, so its clipped ends "
     "crossed over each other",
     "separate the two shapes, or drop the link and let the overlap say what "
     "it was going to say"),
    (FLAG_ZERO_LENGTH,
     "came out with both ends on the same point",
     "separate the two shapes, or reduce standoff= so the clipping leaves "
     "something to draw"),
    (FLAG_SHORT,
     "came out shorter than its own arrowhead",
     "separate the two shapes, or pass a smaller arrow_size="),
)


def rule_link_collapsed(ctx: LintContext) -> list[Diagnostic]:
    """An arrow the author asked for that is not on the page.

    Routing already knows when this happens -- it flags the link and draws a
    point, or a stub, because a head on a point is a blob and an arrow between
    overlapping shapes would point the wrong way. Drawing something harmless is
    the right call; leaving it at that is not. The author wrote a `inklet.link`,
    the figure came back without it, and nothing in between said a word: the
    only way to find out is to notice a missing arrow in a panel of thirty.

    ROUTE_BLOCKED is the neighbouring case and stays separate, because there
    the connector is drawn and merely takes a worse path. Here there is no
    connector, so the fix is never "make room to go around" -- it is to move
    the two shapes apart, or to accept that two things touching do not need an
    arrow to say so.
    """
    out: list[Diagnostic] = []
    for node_id in sorted(ctx.attachments):
        node = ctx.nodes.get(node_id)
        if node is None:
            continue
        flags = link_flags(node)
        reason = next(((why, fix) for flag, why, fix in _COLLAPSED if flag in flags),
                      None)
        if reason is None:
            continue
        endpoints = link_ends(ctx.attachments[node_id])
        between = " -> ".join(ctx.label(end) for end in endpoints)
        vanished = FLAG_ZERO_LENGTH in flags
        drawn = ("it was drawn as a point" if vanished
                 else "only a stub of it was drawn")
        boxes = [ctx.placements[end].bbox for end in endpoints
                 if end in ctx.placements and ctx.placements[end].bbox is not None]
        out.append(Diagnostic(
            code="LINK_COLLAPSED",
            # A point is not a shorter arrow, it is no arrow: the relation the
            # author wrote is not on the page at all, which is the same
            # missing-content class as TEXT_OVERFLOW and MISSING_GLYPHS. A stub
            # still draws a line going the right way and stays a warning.
            severity="error" if vanished else "warning",
            message=f"{ctx.label(node_id)} ({between}) {reason[0]}; {drawn}",
            targets=(node_id,) + tuple(endpoints),
            where=boxes[0].union(boxes[1]) if len(boxes) == 2 else None,
            hint=reason[1],
        ))
    return out


#: Why an arrow ran into its endpoint instead of stopping on it, by side.
#: Ordered like `_COLLAPSED`: the cause that explains the most comes first, and
#: only the first match on a side is reported.
_UNCLIPPED: tuple[tuple[Mapping[str, str], str, str], ...] = (
    ({"source": FLAG_SOURCE_NO_EXTENT, "target": FLAG_TARGET_NO_EXTENT},
     "has no size on the page, so the arrow was aimed at the origin of its "
     "transform instead",
     "give the endpoint an extent, or aim at whichever shape stands for it"),
    ({"source": FLAG_SOURCE_NO_TRACE, "target": FLAG_TARGET_NO_TRACE},
     "draws nothing for the clip to land on, so the arrow ran to its centre",
     "aim at a drawn shape rather than a spacer or a phantom -- or, when the "
     "invisible node is exactly the point, at a named position on it with "
     ".at(...), which is placed rather than clipped"),
    ({"source": FLAG_SOURCE_MISSED, "target": FLAG_TARGET_MISSED},
     "has its centre outside its own outline, so the ray fired to clip the "
     "arrow never crossed that outline and the arrow ran to the centre",
     "aim at a named position with .at(...): a ring, a crescent or any shape "
     "with a hole in the middle offers no boundary point in that direction to "
     "clip on"),
)


#: A projected outline enclosing less than this is not a shape a reader can
#: see, let alone aim at: 0.3mm^2 is a tenth of the area of the smallest legible
#: glyph on the page. Covers the degenerate case, where the projection collapses
#: to a line and the area is exactly zero.
_SLIVER_AREA_MM2 = 0.3

#: ...and a part can enclose plenty of area and still be invisible if it is
#: edge-on. A crystal plane within two degrees of the view direction projects to
#: a hairline: 40mm long, 1mm^2 of ink, and a bbox centre that falls outside its
#: own outline, which is exactly the flag this rewords.
#:
#: Area over span is the width that hairline averages, which is the measurement
#: that does not care which way the sliver is turned: a diagonal one fills a
#: bbox as tall as it is wide, so any test on the bbox's own aspect ratio sees
#: a square and passes it. Below half a stroke width there is nothing on the
#: page.
_SLIVER_WIDTH_MM = 0.4


def _sliver_reason(ctx: LintContext, node_id: str) -> tuple[str, str] | None:
    """The reworded reason for an endpoint with no projected area, or None.

    `LINK_UNCLIPPED` normally tells an author the centre of their shape is
    outside its own outline and offers `.at(...)`, which is true and useless
    when the shape is a `{111}` plane seen two degrees off edge-on: the real
    problem is that there is nothing on the page to point at, and no anchor
    fixes that. Only asked once a link has already been flagged, so the walk
    over the endpoint's subtree is paid by the figures that have the defect.
    """
    ink = 0.0
    box: Rect | None = None
    for item in ctx.items:
        if not item.draws or node_id not in ctx.chain(item.id):
            continue
        if item.is_text:
            return None      # type is never a sliver; whatever this is, it shows
        ink += _ink_area(item)
        box = item.bbox if box is None else box.union(item.bbox)
    if box is None:
        return None          # nothing drawable at all: NO_TRACE already says so
    span = max(box.width, box.height)
    average = ink / span if span > 0.0 else 0.0
    if ink > _SLIVER_AREA_MM2 and average > _SLIVER_WIDTH_MM:
        return None
    return (
        f"has {ink:.2f}mm^2 of projected area over a {_mm(span)} span, an "
        f"average of {_mm(average)} wide, so it is effectively invisible "
        f"from this camera and the arrow has nothing to land on",
        "turn the scene until the part has a face towards the camera, or aim "
        "the link at the assembly it belongs to -- an anchor would only place "
        "the head exactly on something the reader cannot see",
    )


def rule_link_unclipped(ctx: LintContext) -> list[Diagnostic]:
    """An arrow that did not stop where the thing it points at stops.

    Clipping is the promise this library opens with: aim a link at a node and
    it lands on that node's boundary, wherever the layout has since moved it
    to. When the boundary cannot be found the router aims at the centre
    instead, because the centre is the one point it is sure of. That is the
    right fallback and the wrong picture -- on a filled shape the head vanishes
    under the fill, on an unfilled one it drives through the outline into the
    middle, and on a node with no extent at all it lands on blank paper.

    This is the failure a blind author is least equipped to catch. Nothing
    overlaps, nothing overflows, no measurement is out of range: the figure is
    not broken, it is quietly pointing at the wrong place, and the only way to
    find it is to look at it. The router has known all along. This says so.

    Reported per side, because a link can miss one end and be perfect at the
    other, and because the fix belongs to the endpoint rather than to the link.
    LINK_COLLAPSED is the neighbour -- there the connector had no length to
    draw, here it drew the wrong length.
    """
    out: list[Diagnostic] = []
    for node_id in sorted(ctx.attachments):
        node = ctx.nodes.get(node_id)
        if node is None:
            continue
        flags = link_flags(node)
        endpoints = link_ends(ctx.attachments[node_id])
        if len(endpoints) < 2:
            continue
        between = " -> ".join(ctx.label(end) for end in endpoints)
        for side, end in zip(("source", "target"), endpoints):
            reason = next(((why, fix) for sides, why, fix in _UNCLIPPED
                           if sides[side] in flags), None)
            if reason is None:
                continue
            reason = _sliver_reason(ctx, end) or reason
            placement = ctx.placements.get(end)
            out.append(Diagnostic(
                code="LINK_UNCLIPPED",
                severity="warning",
                message=(f"{ctx.label(node_id)} ({between}): the {side} end is "
                         f"not clipped -- {ctx.label(end)} {reason[0]}"),
                targets=(node_id, end),
                where=placement.bbox if placement is not None else None,
                hint=reason[1],
            ))
    return out


def rule_font_substituted(ctx: LintContext) -> list[Diagnostic]:
    """Type that was shaped in a font nobody asked for.

    `fc-match` never fails, so a request for Helvetica quietly becomes whatever
    is installed, and the figure ships in the wrong typeface with metrics to
    match. `TextPrim.requested_family` records the ask; this compares it to
    what was actually used.

    Findings are grouped by (requested, resolved) pair rather than emitted per
    label: one missing font usually affects every string in the figure, and
    fifty identical lines would drown the rest of the report.
    """
    groups: dict[tuple[str, str], list[str]] = {}
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        requested = getattr(item.prim, "requested_family", None)
        actual = item.prim.font_family  # type: ignore[union-attr]
        if not requested or _same_family(requested, actual):
            continue
        groups.setdefault((requested, actual), []).append(item.id)

    out: list[Diagnostic] = []
    for (requested, actual), ids in groups.items():
        ids.sort()
        shown = ", ".join(ctx.label(i) for i in ids[:3])
        if len(ids) > 3:
            shown += f", +{len(ids) - 3} more"
        out.append(Diagnostic(
            code="FONT_SUBSTITUTED",
            severity="warning",
            message=(f"{len(ids)} text prim(s) asked for {requested!r} but were "
                     f"shaped with {actual!r}: {shown}"),
            targets=tuple(ids),
            where=None,
            hint=(f"install {requested!r}, or set the family to {actual!r} so the "
                  f"figure says what it means"),
        ))
    return out


def _same_family(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def rule_missing_glyphs(ctx: LintContext) -> list[Diagnostic]:
    """Text no installed font can draw, which prints as a row of empty boxes.

    This is the quietest way a figure can fail. A font with no glyph for a
    character still reports an advance -- the .notdef box has a width -- so the
    line measures, wraps and fits exactly as if it were real type, and nothing
    upstream has any reason to complain. The typesetter looks for a face that
    covers the characters and records what it could not place; this reports it.

    Grouped by the set of undrawable characters: one absent script usually
    ruins every string in a language, and naming it once is the actionable
    form.
    """
    groups: dict[str, list[str]] = {}
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        missing = getattr(item.prim, "missing", "")
        if missing:
            groups.setdefault(missing, []).append(item.id)

    out: list[Diagnostic] = []
    for missing, ids in sorted(groups.items()):
        ids.sort()
        shown = ", ".join(ctx.label(i) for i in ids[:3])
        if len(ids) > 3:
            shown += f", +{len(ids) - 3} more"
        points = " ".join(f"U+{ord(char):04X}" for char in missing[:6])
        if len(missing) > 6:
            points += f", +{len(missing) - 6} more"
        out.append(Diagnostic(
            code="MISSING_GLYPHS",
            severity="error",
            message=(f"no installed font can draw {points} in {len(ids)} text "
                     f"prim(s): {shown}"),
            targets=tuple(ids),
            where=None,
            hint=("install a font covering these characters -- the text is "
                  "measured and laid out as .notdef boxes until you do, so the "
                  "spacing around it is wrong as well as the glyphs"),
        ))
    return out


def rule_empty_diagram(ctx: LintContext) -> list[Diagnostic]:
    """Nodes that draw nothing, and figures that draw nothing at all.

    A node carrying an `envelope_override` is exempt: like `PhantomPrim`, it
    claims space on purpose and drawing nothing is the whole point.
    """
    out: list[Diagnostic] = []
    for node_id, node in sorted(ctx.nodes.items()):
        if getattr(node, "envelope_override", None) is not None:
            continue
        if node.prim is None and not node.children:
            out.append(Diagnostic(
                code="EMPTY_DIAGRAM",
                severity="warning",
                message=(f"{ctx.label(node_id)} has no primitive and no children, "
                         f"so it draws nothing and occupies no space"),
                targets=(node_id,),
                where=None,
                hint="give it a prim, give it children, or drop it from the tree",
            ))
    if not any(item.draws for item in ctx.items):
        out.append(Diagnostic(
            code="EMPTY_DIAGRAM",
            severity="error",
            message=(f"figure {ctx.label(ctx.root.id)} contains nothing drawable "
                     f"({len(ctx.nodes)} nodes, 0 visible primitives)"),
            targets=(ctx.root.id,),
            where=None,
            hint="add at least one RectPrim/TextPrim/PathPrim to the tree",
        ))
    return out


# Rules big enough to want their own file. The import sits *here*, below every
# name they borrow, because each of those modules does `from .rules import
# LintContext` -- at the top of this file the borrowed names would not exist
# yet. A new rule module joins by adding its import beside these and one line
# to the table below; nothing else in this file needs to know about it.
from .key_rules import rule_key_mismatch                            # noqa: E402
from .link_rules import (rule_coincident_shaft,                     # noqa: E402
                         rule_label_covers_shaft, rule_link_crosses_link)
from .path_rules import (rule_path_crosses,                         # noqa: E402
                         stroke_near_misses)
from .plot_rules import rule_off_panel                              # noqa: E402
from .break_rules import rule_break_distorts                       # noqa: E402
from .three_rules import rule_depth_order                           # noqa: E402

RULES: dict[str, Rule] = {
    "TEXT_OVERFLOW": rule_text_overflow,
    "OFF_CANVAS": rule_off_canvas,
    "OFF_PANEL": rule_off_panel,
    "BREAK_DISTORTS": rule_break_distorts,
    "TINY_TEXT": rule_tiny_text,
    "HAIRLINE": rule_hairline,
    "LOW_CONTRAST": rule_low_contrast,
    "TEXT_FILL_IGNORED": rule_text_fill_ignored,
    "LOW_DPI": rule_low_dpi,
    "OVERLAP": rule_overlap,
    "INCONSISTENT_STROKE": rule_inconsistent_stroke,
    "CROWDING": rule_crowding,
    "LINK_CROSSES": rule_link_crosses,
    "LINK_CROSSES_LINK": rule_link_crosses_link,
    "PATH_CROSSES": rule_path_crosses,
    "ROUTE_BLOCKED": rule_route_blocked,
    "LINK_COLLAPSED": rule_link_collapsed,
    "LINK_UNCLIPPED": rule_link_unclipped,
    "COINCIDENT_SHAFT": rule_coincident_shaft,
    "LABEL_COVERS_SHAFT": rule_label_covers_shaft,
    "KEY_MISMATCH": rule_key_mismatch,
    "DEPTH_ORDER": rule_depth_order,
    "EMPTY_DIAGRAM": rule_empty_diagram,
    "FONT_SUBSTITUTED": rule_font_substituted,
    "MISSING_GLYPHS": rule_missing_glyphs,
}

#: Emitted when a rule itself blows up. A broken rule must degrade the report,
#: never abort it -- the other nine findings are still worth having.
RULE_FAILED = "LINT_RULE_FAILED"


def run_rules(ctx: LintContext, selected: Mapping[str, Rule]) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for code in sorted(selected):
        rule = selected[code]
        try:
            out.extend(rule(ctx))
        except Exception as exc:  # a rule bug must not cost the whole report
            out.append(Diagnostic(
                code=RULE_FAILED,
                severity="info",
                message=f"rule {code} failed: {type(exc).__name__}: {exc}",
                targets=(),
                where=None,
                hint="report this as a inklet.lint bug; other rules still ran",
            ))
    out.sort(key=lambda d: d.sort_key)
    return out
