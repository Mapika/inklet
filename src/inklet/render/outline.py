"""Text as geometry, for output that must not depend on an installed font.

The SVG backend ships live `<text>` with a `font-family` chain, which is the
right default: the file stays searchable, restyleable and small. It also means
the geometry was measured against whichever face *this* machine resolved that
chain to, and a renderer that resolves it differently re-shapes the type inside
boxes that were sized for the original. Outlining is how that stops being a
risk -- a glyph turned into a filled path draws the same everywhere, because
there is nothing left to resolve.

This is a transform on the tree rather than a mode inside a backend, so every
backend gets it at once and none of them has to know what a glyph is:

    inklet.to_svg(inklet.outline_text(tree))       # or fig.save("f.svg", text="outline")

The rewrite is deliberately shape-preserving. Node ids, names, kinds,
transforms and children survive, because a caller's handle and a link's
`attached_to` are keyed on the id; and each outlined node keeps the *text
block's* envelope rather than the ink's, so the page a figure was built to is
the page it renders on. What changes is the leaf primitive and two style
fields: the resolved `text_fill` moves to `fill`, and `stroke` is pinned to
`none` the way the SVG backend pins it on `<text>` -- without that, a label
inside a group that strokes its shapes would come out as a clumsy fake bold.

The one leaf that does not stay a leaf is a block whose `{fill|text}` markup
asked for more than one colour: a filled `PathPrim` carries one fill, so such a
node keeps its envelope and its id and grows a child per colour underneath.
"""

from __future__ import annotations

from dataclasses import replace

from ..core.diagram import Diagram
from ..core.envelope import Envelope
from ..core.geom import Rect
from ..core.prims import PathPrim, PhantomPrim, TextPrim
from ..core.style import EMPTY_STYLE, Style
from ..typeset.outline import TEXT_NOTE, text_to_paths

__all__ = ["outline_text", "TEXT_MODES", "resolve_text_mode", "TEXT_NOTE"]

#: Spellings accepted wherever a backend takes a `text=` mode. `outline` and
#: `embed` are the two ways to stop depending on an installed font: throw the
#: font away and keep the ink, or keep the font and carry it along. Only the
#: SVG backend can do the second, because it needs a `<style>` element.
TEXT_MODES = ("names", "outline", "embed")

# Type properties that only a `<text>` element could have used. Dropping them
# from a leaf that no longer holds text is worth doing: on `panels.svg` the
# theme puts a family and a size on every label, and they are pure bytes once
# the glyphs are paths.
_TYPE_FIELDS = ("font_family", "font_size", "font_weight", "text_fill", "line_height")


def resolve_text_mode(mode: str) -> str:
    """Validate a `text=` mode name, so a typo fails at the call site."""
    if mode not in TEXT_MODES:
        raise ValueError(
            f"unknown text mode {mode!r}; expected one of {', '.join(TEXT_MODES)}"
        )
    return mode


def outline_text(root: Diagram) -> Diagram:
    """Return `root` with every shaped text block replaced by its glyph outlines.

    The result draws identically and depends on no font at render time, at the
    cost of a file a designer can no longer retype. Reach for it when the SVG
    or PDF is leaving this machine -- a submission, a co-author, a print shop --
    and keep `inklet.to_svg` as it is when the file is still being worked on.

    Each block is reshaped under the OpenType features it was measured with,
    which it carries itself (`TextPrim.features`) -- so there is nothing to
    pass and nothing to get wrong.

    Raises ValueError if any text block was not produced by `inklet.typeset.shape`
    and so has no `font_path` to reopen.
    """

    def visit(node: Diagram, inherited: Style) -> Diagram:
        resolved = node.style.over(inherited)
        children = tuple(visit(child, resolved) for child in node.children)
        text = node.prim if isinstance(node.prim, TextPrim) else None
        style = _restyle(node.style, resolved, ink=text is not None and not children)

        if text is None:
            if style is node.style and all(new is old for new, old
                                           in zip(children, node.children)):
                return node
            return replace(node, children=children, style=style, id=node.id,
                           _cache={}, anchors=dict(node.anchors))

        prim, glyphs, fill, override = _outlined(text, children,
                                                 node.envelope_override)
        return replace(
            node,
            prim=prim,
            children=glyphs + children,
            style=style if fill is None else style.with_(fill=fill),
            envelope_override=override,
            id=node.id,
            _cache={},
            anchors=dict(node.anchors),
            notes={**node.notes, TEXT_NOTE: text.text},
        )

    def _outlined(text: TextPrim, children: tuple[Diagram, ...],
                  override: Envelope | None,
                  ) -> tuple[PathPrim | PhantomPrim | None, tuple[Diagram, ...],
                             str | None, Envelope | None]:
        """The leaf's replacement: a primitive, the children it grew, the fill
        to put on the node, and the envelope to pin on it.

        One entry back from `text_to_paths` is the whole corpus, and stays one
        leaf holding one path -- if that entry asked for a colour, the colour
        goes on the node rather than on a child that exists only to carry it. A
        block whose `{fill|text}` markup asked for more than one colour cannot
        stay a leaf: a `PathPrim` carries a single fill, so the node keeps no
        primitive of its own and gains a child per colour instead.
        """
        box = Rect.from_size(text.width, text.height)
        paths = text_to_paths(text)
        if not paths:
            # Whitespace, or a line with no drawable glyph. It still claimed
            # space in the layout, and a phantom is exactly that claim.
            return PhantomPrim(box), (), None, override
        # Glyph ink is narrower than the block that was stacked -- no descender
        # on "cue", no ascender on "raw traces" -- so the block's envelope is
        # carried over explicitly. Without it every box in the figure would
        # shrink-wrap to the letters and the page would move. A text node with
        # children of its own is not something this library builds, but if one
        # arrives its children keep the space they claimed.
        if override is None:
            override = (Envelope.from_rect(box) if not children else
                        Envelope.union_all((Envelope.from_rect(box),
                                            *(child.envelope for child in children))))
        if len(paths) == 1:
            prim, fill = paths[0]
            return prim, (), fill, override
        return None, tuple(_ink(prim, fill) for prim, fill in paths), None, override

    def _ink(prim: PathPrim, fill: str | None) -> Diagram:
        """One colour's glyphs. `fill` of None inherits the node's, which is
        where the resolved `text_fill` has just been put."""
        return Diagram(prim=prim, kind="glyphs",
                       style=Style(fill=fill) if fill else EMPTY_STYLE)

    return visit(root, EMPTY_STYLE)


def _restyle(own: Style, resolved: Style, *, ink: bool) -> Style:
    """What a node's own style becomes once no text is left under it.

    `ink` is set on the leaf whose glyphs these are, and does the two things a
    `<text>` element did for itself: it takes its colour from `text_fill`,
    which paints nothing else and so has no meaning on a path, and it refuses
    a stroke, which live text is exempt from and a path is not -- inheriting
    one from the group that strokes its shapes is a clumsy fake bold.

    Type properties then go from *every* node, not only that leaf. Nothing in
    the tree can use them any more, and on `panels.svg` the theme sets a family
    and a size on the page root and on each label group.
    """
    style = own
    if ink:
        if resolved.text_fill is not None:
            style = style.with_(fill=resolved.text_fill)
        if resolved.stroke not in (None, "none"):
            style = style.with_(stroke="none")
    if any(getattr(style, name) is not None for name in _TYPE_FIELDS):
        style = replace(style, **{name: None for name in _TYPE_FIELDS})
    return style
