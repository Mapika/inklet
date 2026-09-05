"""The Diagram tree.

A diagram is a primitive, or a group of diagrams, positioned by an affine
transform. Combinators never rewrite the things they arrange -- they wrap them
in a new parent that carries the placement. That is what keeps the handle the
caller is holding identical to the node inside the tree, so `fig.link(a, b)`
can find `a` after three levels of stacking.

Two coordinate frames matter, and mixing them up is the classic bug here:
  * local  -- the node's own frame, before `self.transform`
  * world  -- after every transform from the root down, including its own
Anchors and `local_envelope` are local. `resolve()` hands back world.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from itertools import count
from typing import Iterator, Mapping

from .envelope import Envelope
from .geom import IDENTITY, ORIGIN, Affine, Rect, Vec2
from .prims import Prim
from .style import EMPTY_STYLE, Style
from .trace import Trace

_ids = count(1)


def _new_id(kind: str) -> str:
    """Sequential rather than random: identical scripts produce identical SVG,
    which is the difference between a diffable figure and a binary blob."""
    return f"{kind}{next(_ids)}"


class DiagramError(Exception):
    pass


def note_through(transform: Affine, value: object) -> object:
    """One note value, re-expressed in the frame `transform` maps into (M19).

    **A `Rect` note names a region of the node** -- `plot_area` is the one the
    library ships -- so it travels with the node and comes back as the bounds
    of its transformed corners. That is exact for a translation, a scale and a
    mirror; under a rotation it is the upright box around a turned rectangle,
    which over-reports the extent and reports the *centre* exactly, and the
    centre is what every alignment in the library lines up on.

    **Everything else rides along unchanged**, because core cannot tell what
    frame it is in, or whether it is in one at all. The counterexample is in
    the tree already: `layout.flow` records `gap_axis` as a `Vec2`, and that
    `Vec2` is a *direction* -- putting it through `apply()` would translate a
    unit vector. A scalar has the matching hazard in the other direction:
    `gap` is the millimetres the author asked for, and `.scaled(2)` makes the
    page disagree with the note without core having any way to know that
    `gap` was metric and `columns` was not. A module whose note is metric and
    whose node gets scaled re-notes it; the library has no such pair.
    """
    if isinstance(value, Rect):
        return value.transform(transform)
    return value


@dataclass(frozen=True)
class Diagram:
    prim: Prim | None = None
    children: tuple["Diagram", ...] = ()
    transform: Affine = IDENTITY
    style: Style = EMPTY_STYLE
    kind: str = "g"
    name: str | None = None
    id: str = field(default="", compare=False)
    # Set to claim space the contents do not, e.g. padding. The trace is left
    # alone deliberately, so extra room never intercepts an arrow.
    envelope_override: Envelope | None = None
    # Ids of the nodes this one was built to touch -- the two shapes a connector
    # was clipped to, typically. Contact with them is the point, so a linter can
    # tell an arrowhead landing on its target apart from one straying across an
    # unrelated box. Excluded from equality, like `id`, so recording provenance
    # never changes what compares equal.
    attached_to: tuple[str, ...] = field(default=(), compare=False)
    # Anchors are annotations rather than structure, so they are mutable and
    # excluded from equality. `anchor()` returns self to keep call sites terse.
    anchors: dict[str, Vec2] = field(default_factory=dict, compare=False, repr=False)
    # Whatever a module upstream of the renderer wants to remember about this
    # node that core has no opinion on: the `gap=` a stack was asked for, the
    # numeric domain a colour key was mapped through. A real field rather than
    # an attribute stuck on with `object.__setattr__`, because `replace()`
    # carries fields and `replace()` is how `apply_theme` rebuilds the tree --
    # so an annotation survives `build()` without anyone special-casing it by
    # name. Mutable and excluded from equality, like `anchors`: recording that
    # a stack was given 6mm does not make it a different stack.
    notes: dict[str, object] = field(default_factory=dict, compare=False, repr=False)
    _cache: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, "id", _new_id(self.kind))

    # -- geometry ---------------------------------------------------------

    @property
    def local_envelope(self) -> Envelope:
        if self.envelope_override is not None:
            return self.envelope_override
        if "env" not in self._cache:
            own = self.prim.envelope() if self.prim is not None else Envelope.empty()
            self._cache["env"] = Envelope.union_all(
                (own, *(child.envelope for child in self.children)))
        return self._cache["env"]

    @property
    def envelope(self) -> Envelope:
        """As the parent sees it: local extent with this node's transform applied."""
        if "penv" not in self._cache:
            self._cache["penv"] = self.local_envelope.transform(self.transform)
        return self._cache["penv"]

    @property
    def local_trace(self) -> Trace:
        if "trace" not in self._cache:
            own = self.prim.trace() if self.prim is not None else Trace.empty()
            self._cache["trace"] = Trace.union_all(
                (own, *(child.trace for child in self.children)))
        return self._cache["trace"]

    @property
    def trace(self) -> Trace:
        if "ptrace" not in self._cache:
            self._cache["ptrace"] = self.local_trace.transform(self.transform)
        return self._cache["ptrace"]

    @property
    def bbox(self) -> Rect:
        """The upright box around this node as its parent sees it.

        Raises where `Envelope.bbox()` returns None, and the difference is
        deliberate: an envelope is allowed to be empty -- that is the identity
        for union, and `union_all` relies on it -- while a caller asking a
        *diagram* how wide it is has already assumed there is something there.
        Returning None would only move the crash one line further out.
        """
        box = self.envelope.bbox()
        if box is None:
            raise DiagramError(f"{self.id} is empty and has no bounding box")
        return box

    @property
    def local_bbox(self) -> Rect:
        box = self.local_envelope.bbox()
        if box is None:
            raise DiagramError(f"{self.id} is empty and has no bounding box")
        return box

    @property
    def width(self) -> float:
        return self.bbox.width

    @property
    def height(self) -> float:
        return self.bbox.height

    @property
    def is_empty(self) -> bool:
        return self.local_envelope.is_empty

    def extent(self, direction: Vec2) -> float:
        """How far this reaches along a direction, in the parent's frame. This is
        what stacking asks, and why a rotated shape packs tighter than its bbox."""
        value = self.envelope.extent(direction)
        return 0.0 if value is None else value

    # -- anchors ----------------------------------------------------------

    def anchor(self, name: str, at: tuple[float, float] | Vec2) -> "Diagram":
        """Register a named point. A tuple is read as fractions of the local
        bounding box, (0, 0) being its top-left corner -- the natural way to
        point at an ear in a photograph."""
        if isinstance(at, Vec2):
            self.anchors[name] = at
        else:
            box = self.local_bbox
            u, v = at
            self.anchors[name] = Vec2(box.x0 + u * box.width, box.y0 + v * box.height)
        return self

    def anchor_point(self, name: str = "center") -> Vec2:
        """Local coordinates of a named or compass anchor.

        Local means before this node's own transform, so a compass name here
        describes the *unturned* box. On a rotated node that is not the box
        `bbox` reports, and it is `bbox` that a caller can see -- which is why
        `Placement.point` resolves the compass again once the node is placed.
        A registered anchor has no such trouble: it is a point of the shape and
        travels with it -- including through the wrappers `translated`,
        `rotated` and `scaled` leave behind (see `registered_point`).
        """
        if name in self.anchors:
            return self.anchors[name]
        if name in _COMPASS_NAMES:
            return _compass(self.local_bbox, name, self)
        through = self.registered_point(name)
        if through is not None:
            return through
        return _compass(self.local_bbox, name, self)

    def registered_point(self, name: str) -> Vec2 | None:
        """A registered anchor's coordinates in *this* node's frame, or None.

        `placed()` wraps rather than rewrites, so `d.rotated(90)` is a new
        parent holding the very `d` the caller is still holding -- which is the
        point, and which used to mean the anchors went out of reach: the
        wrapper carries none of its own, so `d.anchor("tip", ...)` followed by
        `d.rotated(90).anchor_point("tip")` raised, and every consumer had to
        keep hold of the node the anchor was put on.

        So a transform wrapper answers for its child: one child, no primitive
        and no envelope override is exactly the shape `placed()` builds, and
        the answer comes back through `child.transform`, which is where the
        rotation lives. A tip travels with the shape, nested wrappers included.

        Deliberately not a search of the whole tree. Asking an `hstack` of five
        drawn shapes for "origin" would find the first child's and answer as if
        it were the stack's, which is worse than raising -- and `inklet.draw`'s
        `as_drawn` is built on exactly that question. A group of many children
        has no single point of the shape to hand back.
        """
        if name in self.anchors:
            return self.anchors[name]
        if (self.prim is None and len(self.children) == 1
                and self.envelope_override is None):
            child = self.children[0]
            inner = child.registered_point(name)
            if inner is not None:
                return child.transform.apply(inner)
        return None

    def note(self, key: str, value: object) -> "Diagram":
        """Record something about this node that core has no opinion on.

        Returns self, like `anchor()`, so it reads inline:
        `hstack(items, gap=6).note("gap", 6)`. Read it back with
        `node.notes.get(key)` -- and from another module, defensively, with
        `getattr(node, "notes", {}).get(key)`, since a note is by definition
        something the reader may not have been built against.
        """
        self.notes[key] = value
        return self

    def carry_notes(self, source: "Diagram") -> "Diagram":
        """Copy `source`'s notes onto this node, re-expressed in *this* frame.

        For a wrapper whose single child is `source` -- which is what
        `placed()` builds, and what `layout.pad` and `layout.frame` build too.
        The wrapper's local frame is the frame `source.transform` maps *into*,
        so a note that names a region of the source has to come across through
        that transform; `note_through` says which values those are (M19).

        Mutating and self-returning, like `note()` and `anchor()`: the caller
        has just built the wrapper and nobody else is holding it. Notes already
        recorded here win, so a combinator can declare its own answer first and
        inherit the rest.
        """
        notes = getattr(source, "notes", None)
        if not notes:
            return self
        at = source.transform
        for key, value in notes.items():
            self.notes.setdefault(key, note_through(at, value))
        return self

    def at(self, name: str) -> "AnchorRef":
        return AnchorRef(self, name)

    def __repr__(self) -> str:
        return f"Diagram({_brief(self)})"

    # -- transformation ---------------------------------------------------

    def placed(self, transform: Affine) -> "Diagram":
        """Wrap in a positioned parent, leaving this node untouched so callers
        keep a working handle on it.

        The wrapper inherits the node's notes, moved into its frame (M19), so
        `plot_area(panel.translated(dx, dy))` answers where the panel's data
        region now is instead of answering None. Anchors are deliberately *not*
        copied: `registered_point` already looks through a wrapper for those
        (M16), and `draw.as_drawn` reads `node.anchors` directly precisely to
        tell a placement someone meant from the recentring it undoes.
        """
        if transform.is_identity:
            return self
        wrapper = Diagram(children=(self,), transform=transform, kind="place")
        return wrapper.carry_notes(self)

    def translated(self, dx: float, dy: float = 0.0) -> "Diagram":
        return self.placed(Affine.translation(dx, dy))

    def rotated(self, degrees: float) -> "Diagram":
        return self.placed(Affine.rotation(degrees))

    def scaled(self, factor: float, factor_y: float | None = None) -> "Diagram":
        return self.placed(Affine.scaling(factor, factor_y))

    def centered(self) -> "Diagram":
        """Shift so the envelope's centre sits on the origin."""
        c = self.bbox.center
        return self.translated(-c.x, -c.y)

    def styled(self, **kwargs) -> "Diagram":
        merged = Style(**kwargs).over(self.style)
        return replace(self, style=merged, _cache={}, anchors=dict(self.anchors),
                       notes=dict(self.notes))

    def named(self, name: str) -> "Diagram":
        return replace(self, name=name, _cache={}, anchors=dict(self.anchors),
                       notes=dict(self.notes))

    def copy(self) -> "Diagram":
        """Fresh identities throughout, for placing the same shape twice.

        `attached_to` names nodes by id, so the renumbering has to reach it.
        An id from *outside* the subtree still means what it said -- two
        placements of one diagram both touch the original -- but an id from
        inside would leave the copy's connectors attached to the tree they
        were copied from. A panel is exactly that case: its links and the
        shapes they were clipped to are in one subtree, and copying it onto a
        page detached every arrow from its own target, so each beam was
        reported as crossing the optic it ends on.
        """
        renamed: dict[str, str] = {}
        clone = self._copied(renamed)
        for node in clone.walk():
            if any(end in renamed for end in node.attached_to):
                object.__setattr__(node, "attached_to", tuple(
                    renamed.get(end, end) for end in node.attached_to))
        return clone

    def _copied(self, renamed: dict[str, str]) -> "Diagram":
        """One node cloned, recording old id -> new id as it goes."""
        clone = Diagram(
            prim=self.prim,
            children=tuple(c._copied(renamed) for c in self.children),
            transform=self.transform,
            style=self.style,
            kind=self.kind,
            name=self.name,
            envelope_override=self.envelope_override,
            attached_to=self.attached_to,
        )
        clone.anchors.update(self.anchors)
        clone.notes.update(self.notes)
        renamed[self.id] = clone.id
        return clone

    # -- traversal --------------------------------------------------------

    def walk(self) -> Iterator["Diagram"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, name: str) -> "Diagram":
        for node in self.walk():
            if node.name == name:
                return node
        raise DiagramError(f"no diagram named {name!r}")


def _brief(node: Diagram) -> str:
    """A node named in one line: kind, name, id, and how much is under it.

    Diagrams nest, so the generated dataclass repr of a page is the page --
    printing one anchor of a stress figure dumped 12 kB. What a caller wants
    from a repr is which node this is.
    """
    head = node.kind if not node.name else f"{node.kind} {node.name!r}"
    rest: list[str] = [f"{head} {node.id}"]
    if node.prim is not None:
        rest.append(type(node.prim).__name__)
    if node.children:
        n = len(node.children)
        rest.append(f"{n} child" if n == 1 else f"{n} children")
    return ", ".join(rest)


#: Names `_compass` answers to. Kept beside the table it indexes so that
#: `anchor_point` can tell a side of a box from the name of a point on a shape
#: without building the table to find out.
_COMPASS_NAMES = frozenset(
    ("center", "c", "n", "s", "w", "e", "nw", "ne", "sw", "se"))


def _compass(box: Rect, name: str, node: Diagram) -> Vec2:
    """A compass point of a box. y grows downward, so north is the smaller y."""
    mid = box.center
    table = {
        "center": mid, "c": mid,
        "n": Vec2(mid.x, box.y0), "s": Vec2(mid.x, box.y1),
        "w": Vec2(box.x0, mid.y), "e": Vec2(box.x1, mid.y),
        "nw": Vec2(box.x0, box.y0), "ne": Vec2(box.x1, box.y0),
        "sw": Vec2(box.x0, box.y1), "se": Vec2(box.x1, box.y1),
    }
    if name not in table:
        known = ", ".join(sorted(set(table) | _reachable_anchors(node)))
        raise DiagramError(f"{node.id} has no anchor {name!r}; known: {known}")
    return table[name]


def _reachable_anchors(node: Diagram) -> set[str]:
    """Anchor names this node will answer to, wrappers included.

    The same one-child chain `registered_point` walks, so what the error says
    is known is what would in fact have been found.
    """
    names = set(node.anchors)
    while (node.prim is None and len(node.children) == 1
           and node.envelope_override is None):
        node = node.children[0]
        names |= set(node.anchors)
    return names


@dataclass(frozen=True, slots=True)
class AnchorRef:
    """A point on a diagram, resolvable once the tree has been laid out."""

    diagram: Diagram
    name: str = "center"

    def local(self) -> Vec2:
        return self.diagram.anchor_point(self.name)

    def __repr__(self) -> str:
        return f"AnchorRef({_brief(self.diagram)}, {self.name!r})"


def group(children, transform: Affine = IDENTITY, **kwargs) -> Diagram:
    return Diagram(children=tuple(children), transform=transform, **kwargs)


# -- resolution -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a node ended up. `world` maps its local frame into figure space."""

    diagram: Diagram
    world: Affine
    style: Style
    depth: int

    @property
    def envelope(self) -> Envelope:
        return self.diagram.local_envelope.transform(self.world)

    @property
    def trace(self) -> Trace:
        return self.diagram.local_trace.transform(self.world)

    @property
    def bbox(self) -> Rect | None:
        return self.envelope.bbox()

    def point(self, anchor: str = "center") -> Vec2:
        """Figure-space coordinates of one of the node's anchors.

        A registered anchor is a point *of the shape*: it is carried through
        the world transform, so `mouse.at("ear")` still names the ear after the
        mouse has been turned. A compass name is not a point of the shape but a
        side of its box, and the box a caller can see is the upright one that
        `bbox` reports -- so it is resolved here, against the placed envelope,
        rather than taken from the unturned local box and rotated with it. The
        two readings differ only for a node with rotation above it, where the
        old one put the "north" of a 30-degree label a centimetre inside the
        label's own bounding box.
        """
        if anchor in self.diagram.anchors:
            return self.world.apply(self.diagram.anchors[anchor])
        if anchor not in _COMPASS_NAMES:
            # Not a side of a box, so it can only be a point of a shape --
            # possibly of the shape inside a transform wrapper, which is what
            # `fig.link(part.rotated(30).at("tip"), ...)` hands us.
            through = self.diagram.registered_point(anchor)
            if through is not None:
                return self.world.apply(through)
        w = self.world
        if w.b == 0.0 and w.c == 0.0 and w.a > 0.0 and w.d > 0.0:
            # Axis-aligned and unmirrored, which is nearly every node: the
            # local box maps corner-to-corner onto the placed one, so the two
            # readings are the same point. Mapping the local one is not just
            # cheaper -- recomputing a midpoint from the placed box rounds
            # differently, and a figure whose routing is sensitive to the last
            # bit of a centre should not be perturbed to no purpose.
            return w.apply(_compass(self.diagram.local_bbox, anchor,
                                    self.diagram))
        box = self.bbox
        if box is None:
            raise DiagramError(
                f"{self.diagram.id} is empty, so it has no {anchor!r}")
        return _compass(box, anchor, self.diagram)


def resolve(root: Diagram, base: Affine = IDENTITY,
            base_style: Style = EMPTY_STYLE) -> dict[str, Placement]:
    """Flatten the tree into world transforms, keyed by node id.

    Placing one Diagram object in two spots leaves its id ambiguous; that is
    reported here rather than silently resolving to whichever came last.
    """
    placements: dict[str, Placement] = {}
    seen: Counter[str] = Counter()

    def visit(node: Diagram, parent: Affine, inherited: Style, depth: int) -> None:
        world = parent @ node.transform
        style = node.style.over(inherited)
        seen[node.id] += 1
        placements[node.id] = Placement(node, world, style, depth)
        for child in node.children:
            visit(child, world, style, depth + 1)

    visit(root, base, base_style, 0)

    repeats = [i for i, n in seen.items() if n > 1]
    if repeats:
        names = ", ".join(repeats[:3])
        raise DiagramError(
            f"diagram(s) {names} appear more than once in the tree; "
            "use .copy() to place the same shape twice"
        )
    return placements


@dataclass(frozen=True, slots=True)
class RenderItem:
    """One drawable, in world space, with style fully resolved."""

    prim: Prim
    world: Affine
    style: Style
    id: str
    name: str | None


def flatten(root: Diagram, base: Affine = IDENTITY,
            base_style: Style = EMPTY_STYLE) -> list[RenderItem]:
    """Depth-first draw order: a node's own primitive paints before its children."""
    items: list[RenderItem] = []

    def visit(node: Diagram, parent: Affine, inherited: Style) -> None:
        world = parent @ node.transform
        style = node.style.over(inherited)
        if node.prim is not None:
            items.append(RenderItem(node.prim, world, style, node.id, node.name))
        for child in node.children:
            visit(child, world, style)

    visit(root, base, base_style)
    return items


def world_point(ref: AnchorRef | Diagram, placements: Mapping[str, Placement]) -> Vec2:
    """Turn an anchor reference into figure-space coordinates."""
    diagram = ref.diagram if isinstance(ref, AnchorRef) else ref
    name = ref.name if isinstance(ref, AnchorRef) else "center"
    placement = placements.get(diagram.id)
    if placement is None:
        raise DiagramError(
            f"{diagram.id} is not part of this figure; add it before linking to it"
        )
    return placement.point(name)
