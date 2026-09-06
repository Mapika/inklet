"""The Figure: a canvas, a theme, some content, and the links between it.

Composition and connection are deliberately two phases. You build the content
tree first and let layout settle it, and only then are links routed, because an
arrow's endpoints are a function of where things actually ended up. Trying to
declare connectors inside the composition tree is how diagram libraries tie
themselves in knots.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from .core import (
    COLUMN_SINGLE, EMPTY_STYLE, Affine, AnchorRef, Diagram, Envelope, Placement,
    Rect, Style, group, mm, resolve,
)
from .core.prims import TextPrim
from .layout import frame, vstack
from .links import Link, link as make_link, route_all
from .diagnostics import Diagnostic, format_report, lint
from .render import (PDF_TEXT_MODES, TEXT_MODES, resolve_text_mode, to_pdf,
                     to_svg)
from .typeset import shape, theme_colors
from .themes import Theme, theme as get_theme

# A node's `kind` is its semantic role; the theme decides what that looks like.
# Structural wrappers carry no role of their own and simply pass style through.
_ROLE_OF_KIND = {
    "page": "root",
    "box": "box",
    "frame": "frame",
    "text": "text",
    "label": "label",
    "title": "panel-title",
    "emphasis": "emphasis",
    "muted": "muted",
    # What inklet.links emits. The arrowhead is a filled shape while the shaft is
    # a stroked one, so they cannot share a role.
    "link": "link",
    "connector": "link",
    "arrowhead": "arrowhead",
    "link-label": "label",
    # What inklet.draw and inklet.plot emit. A tick label and an axis label are just
    # labels; everything else here is geometry the theme has an opinion about.
    "mark": "mark",
    "mark-line": "mark-line",
    "axis": "axis",
    "spine": "axis",
    "tick": "axis",
    "tick-label": "label",
    "axis-label": "label",
    # Not "grid": that is `layout.grid`, a container, and styling it would
    # bleed a pale hairline onto every child that does not set its own.
    "gridline": "grid",
    "plot-area": "plot-area",
}


def _without(style: Style, authored: Style) -> Style:
    """Drop every property an ancestor set by hand.

    A theme default on a child would otherwise beat an author's intent on its
    parent: `box("x", stroke="red")` styles the container, but the rectangle
    inside it carries the theme's own stroke and, being nearer, wins. Removing
    those properties from the child's defaults lets the authored value inherit.
    """
    changes = {f.name: None for f in fields(Style)
               if getattr(authored, f.name) is not None}
    return replace(style, **changes) if changes else style


def apply_theme(root: Diagram, theme: Theme) -> Diagram:
    """Slide theme styles *underneath* whatever the author set explicitly.

    Node ids are preserved, because caller handles and link references are keyed
    on them and a restyled tree must still be the same tree.
    """

    def visit(node: Diagram, authored: Style, behind: str) -> Diagram:
        role = _ROLE_OF_KIND.get(node.kind)
        if role is None:
            style = node.style
        else:
            style = node.style.over(_without(theme.style_for(role), authored))
        if (isinstance(node.prim, TextPrim)
                and node.style.text_fill is None and authored.text_fill is None):
            # The theme's ink is picked against `paper`, but this glyph may be
            # sitting on a filled box. Nobody authored a colour here, so the
            # theme is free to choose one that can actually be read.
            style = replace(style, text_fill=theme.text_on(behind))
        inherited = node.style.over(authored)
        fill = inherited.fill
        under = behind if fill in (None, "none") else fill
        clone = replace(
            node,
            children=tuple(visit(child, inherited, under)
                           for child in node.children),
            style=style,
            id=node.id,
            _cache={},
            anchors=dict(node.anchors),
        )
        _carry_annotations(node, clone)
        return clone

    return visit(root, EMPTY_STYLE, theme.paper)


#: Every name `Diagram` declares as a field. Anything else on an instance was
#: stamped there by whoever built it.
_DIAGRAM_FIELDS = frozenset(f.name for f in fields(Diagram))


def _carry_annotations(node: Diagram, clone: Diagram) -> None:
    """Copy the attributes a builder stamped on a node outside its fields.

    `Diagram.notes` (core M17) is the supported home for an annotation and
    needs nothing from here: it is a field, so `replace` already brings it
    through. Nothing inside `inklet` stamps an attribute any more -- `inklet.plot`'s
    `scale_domain`, the last one, is a note now, and with it went the three
    lines of this function's caller that used to lift it across the rebuild by
    name.

    What is left is a safety net for a caller who hangs something of their own
    on a node, which `dataclasses.replace` would otherwise drop on the first
    restyle. Carried by inspection rather than by name, so it needs no edit to
    keep working; it skips every field by name, `notes` included, so it can
    never overwrite the carried dict with a stale one.
    """
    for name, value in vars(node).items():
        if name not in _DIAGRAM_FIELDS:
            object.__setattr__(clone, name, value)


#: Breathing room between a link label and the edge of its plate, in mm.
_PLATE_PAD = 0.5


def _default_theme() -> Theme:
    """Whatever `inklet.use_theme` last set, read at construction time.

    A late import, and deliberately so: `inklet/__init__` is still executing its
    own module body when it imports this one, so the current theme can only be
    read when a figure is actually made. Which is the right moment anyway --
    geometry is built against the current theme from the first `inklet.box`, and
    a page that then paints itself in a different one measures in one font and
    ships another.
    """
    from . import current_theme

    return current_theme()


@dataclass
class Figure:
    width: float = COLUMN_SINGLE
    height: float | None = None
    theme: Theme = field(default_factory=_default_theme)
    margin: float = 2.0
    background: str | None = None
    _content: list[Diagram] = field(default_factory=list, repr=False)
    _links: list[Link] = field(default_factory=list, repr=False)
    _built: tuple[Diagram, dict[str, Placement]] | None = field(
        default=None, repr=False, compare=False)

    def __post_init__(self):
        self.width = mm(self.width)
        self.margin = mm(self.margin)
        if self.height is not None:
            self.height = mm(self.height)
        if isinstance(self.theme, str):
            self.theme = get_theme(self.theme)

    # -- authoring --------------------------------------------------------

    def add(self, *diagrams: Diagram) -> Diagram:
        """Stack content vertically. Returns the last item for chaining."""
        self._content.extend(diagrams)
        self._built = None
        return diagrams[-1] if diagrams else None

    def link(self, source, target, *, label: str | Diagram | None = None,
             label_plate: bool = True, **kwargs) -> Link:
        """Connect two things. The link module works in geometry alone, so a
        string label is shaped here, where the theme is known.

        A label rides at a point along the shaft, and that point is regularly
        over something else -- a box the line passes, or the very shapes a
        branch converges from. `label_plate` puts an opaque plate behind it so
        it stays legible without being dragged away from the line it names.
        """
        if isinstance(label, str):
            # `colors=` is what turns `{accent|sample}` into the accent colour
            # rather than into five literal characters on the page. It is the
            # theme's table, so a link label names a token the same way a
            # caption does; without it the span parses and then has nowhere to
            # look the name up, and the markup silently does nothing.
            label = Diagram(
                prim=shape(label, font=self.theme.font_family,
                           size=self.theme.font_size_small,
                           line_height=self.theme.line_height,
                           colors=theme_colors(self.theme)),
                kind="label",
            )
        if label is not None and label_plate:
            label = frame(label, pad=_PLATE_PAD, kind="label-plate").styled(
                fill=self.theme.paper, stroke="none")
        kwargs.setdefault("arrow_size", self.theme.arrow_size)
        # Not a `setdefault`: `corner_radius=` is the other spelling of the
        # same field, and a theme default must not shadow either of them.
        if (getattr(self.theme, "link_radius", 0.0)
                and "corner" not in kwargs and "corner_radius" not in kwargs):
            kwargs["corner"] = self.theme.link_radius
        connector = make_link(source, target, label=label, **kwargs)
        self._links.append(connector)
        self._built = None
        return connector

    # -- resolution -------------------------------------------------------

    def build(self) -> tuple[Diagram, dict[str, Placement]]:
        """Lay out the content, route the links over it, put it on the page.

        Cached until the figure changes. Routing mints fresh nodes, so building
        twice would otherwise renumber every connector and two calls to
        `to_svg()` would disagree byte for byte.

        Combinators centre their results on the origin, which is right for
        composing but not for a page: the canvas runs from (0, 0) to
        (width, height). The content is moved into that frame here, once,
        after links are routed so connectors travel with what they connect.
        """
        if self._built is not None:
            return self._built
        if not self._content:
            return Diagram(), {}

        content = (self._content[0] if len(self._content) == 1
                   else vstack(self._content, gap=self.theme.gap("l")))

        if self._links:
            # A plain group, deliberately not `overlay`: overlay aligns each
            # item on its own bbox centre, which would shift the connectors
            # relative to the very things they were routed to.
            connectors = route_all(self._links, resolve(content))
            content = Diagram(children=(content, connectors), kind="content")

        box = content.bbox
        page = self.page_rect(box)
        # Centre horizontally in the column; the top margin is fixed.
        offset_x = (page.width - box.width) / 2 - box.x0
        placed = content.translated(offset_x, self.margin - box.y0)
        # The root claims the whole page, so the renderer's viewBox is the page
        # rather than a shrink-wrap around the ink.
        framed = Diagram(children=(placed,), kind="page",
                         envelope_override=Envelope.from_rect(page))

        themed = apply_theme(framed, self.theme)
        self._built = (themed, resolve(themed))
        return self._built

    def page_rect(self, content_box: Rect | None = None) -> Rect:
        """The finished page, in millimetres.

        A figure given no `height` grows to whatever it holds plus a margin on
        each side, which is why the number is only knowable once there is
        content to measure.
        """
        if self.height is not None:
            return Rect(0.0, 0.0, self.width, self.height)
        height = (content_box.height + 2 * self.margin) if content_box else 2 * self.margin
        return Rect(0.0, 0.0, self.width, height)

    def lint(self, **kwargs) -> list[Diagnostic]:
        """Every rule, run over the built figure. See `inklet.lint`.

        Prefer this to `inklet.lint(node)`: the figure knows its page and its
        paper colour, so the rules that need them -- OFF_CANVAS, LOW_CONTRAST
        -- can only answer properly from here. Thresholds are keywords:
        `min_font_pt`, `min_clearance_mm`, `max_stroke_widths`, `min_contrast`,
        `min_dpi`.
        """
        root, placements = self.build()
        if not placements:
            return lint(root, **kwargs)
        kwargs.setdefault("page_fill", self.background or self.theme.paper)
        return lint(root, page=root.bbox, placements=placements, **kwargs)

    def report(self, **kwargs) -> str:
        """`lint()`, formatted for a human or an agent to read.

        The same keywords, and the one most callers want: a figure being
        generated by something that cannot see it has this as its only
        feedback channel, so `print(fig.report())` belongs at the end of
        every script that builds one.
        """
        return format_report(self.lint(**kwargs))

    # -- output -----------------------------------------------------------

    def to_svg(self, *, text: str = "names", **kwargs) -> str:
        """The figure as SVG text, page frame and background included.

        `text` is `"names"` (the default: live `<text>` carrying a font-family
        chain, editable and searchable), `"outline"` (every glyph a filled
        path, so the file draws the same on a machine that has never heard of
        the font it was measured against) or `"embed"` (live text, with a
        subset of each face carried inside the file). `inklet.to_svg` says what
        each costs; `inklet.outline_text` is the tree transform behind the second.
        """
        root, _ = self.build()
        options = dict(
            margin=0.0,   # the page frame is already part of the tree
            background=self.background or self.theme.paper,
            text=resolve_text_mode(text),
        )
        options.update(kwargs)
        return to_svg(root, **options)

    def to_pdf(self, *, text: str = "outline", **kwargs) -> bytes:
        """The figure as PDF bytes, on the same page as `to_svg` puts it.

        `text` is `"outline"` (the default: every glyph a filled path, so the
        file depends on no installed font, which is the point of a PDF and the
        reason it cannot be searched) or `"embed"` (the same glyphs at the
        same places, written as real text against a subset of each face --
        searchable and copyable, at the cost of a font program per face).
        There is no `"names"`: PDF has no font-name mode worth having, so the
        searchable PDF is `text="embed"`. `inklet.to_pdf` says what each costs.

        Spelled out rather than passed through `**kwargs` so that a typo is
        refused here, with the figure's own name on the traceback, and so that
        the mode appears in the reference beside `to_svg`'s three.
        """
        if text not in PDF_TEXT_MODES:
            raise ValueError(
                f"unknown text mode {text!r} for PDF; expected one of "
                f"{', '.join(PDF_TEXT_MODES)}"
                + ("; PDF has no font-name mode, so a searchable PDF is "
                   "text='embed'" if text == "names" else ""))
        root, _ = self.build()
        options = dict(
            margin=0.0,   # the page frame is already part of the tree
            background=self.background or self.theme.paper,
            text=text,
        )
        options.update(kwargs)
        return to_pdf(root, **options)

    def to_png(self, *, dpi=150, **kwargs) -> bytes:
        """Render PNG at physical DPI with optional resvg, without a browser."""
        from .render.raster import to_png
        root, _ = self.build()
        return to_png(root, dpi=dpi, **(dict(background=self.background or self.theme.paper) | kwargs))

    def export(self, directory: str | Path, *, name: str = "figure",
               dpi: float = 150, text: str = "embed", compare_pdf: bool = True,
               png_backend: str = 'resvg', compare_to=None) -> dict[str, Path]:
        """Write SVG, PDF, PNG, diagnostics and a local HTML review page.

        Returns paths keyed by `svg`, `pdf`, `png`, `review`, `diagnostics`,
        `manifest` and (by default) `pdf_png`. PNG previews require inklet[render] (resvg and Pillow);
        png_backend="chromium" uses the earlier browser path. The independent
        PDF preview also requires Poppler.
        Set `compare_pdf=False` to omit that preview. Text is embedded by
        default; `text="outline"` is also supported.

        All files are rendered before an existing bundle is replaced. Files
        use `name` as a prefix, so several figures can share a directory.
        """
        from .render.bundle import export_bundle
        return export_bundle(self, directory, name=name, dpi=dpi, text=text,
                             compare_pdf=compare_pdf, png_backend=png_backend,compare_to=compare_to)

    def save(self, *paths: str | Path, **kwargs) -> None:
        """Write the figure to SVG, PDF or PNG, following each filename suffix.

        The format follows the suffix, so `fig.save("f.svg", "f.pdf")` writes
        both from one build -- which is what a paper wants, the PDF to submit
        and the SVG to keep editing.

        `text` says what the type in each file *is*, and the two formats do not
        offer the same three: SVG takes `"names"` (the default -- a font-family
        chain), `"outline"` or `"embed"`, while PDF has no font-name mode and
        takes only `"outline"` (its default) or `"embed"`. So `text="embed"`
        crosses both, and `fig.save("f.svg", "f.pdf", text="embed")` is how you
        get a searchable PDF and a searchable SVG from one build. `"names"` is
        an SVG answer to a question PDF does not ask, so a PDF written under it
        outlines -- the safe reading of "I did not think about the PDF" -- and
        anything that is neither raises here rather than at whichever file
        happens to come first in the list.
        """
        mode = kwargs.get("text")
        if mode is not None and mode not in TEXT_MODES:
            raise ValueError(
                f"unknown text mode {mode!r}; expected one of "
                f"{', '.join(TEXT_MODES)}"
            )
        for path in paths:
            target = Path(path)
            suffix = target.suffix.lower()
            if suffix not in (".svg", ".pdf", ".png"):
                raise NotImplementedError(
                    f"{target.suffix} output is not supported; write .svg, .pdf or .png"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            if suffix == '.png':
                target.write_bytes(self.to_png(**kwargs))
            elif suffix == ".pdf":
                options = {k: v for k, v in kwargs.items() if k != "text"}
                if mode in PDF_TEXT_MODES:
                    options["text"] = mode
                target.write_bytes(self.to_pdf(**options))
            else:
                target.write_text(self.to_svg(**kwargs), encoding="utf-8")


def figure(width: float | str = COLUMN_SINGLE, **kwargs) -> Figure:
    """A page to put content on. See `Figure` for everything it can do.

    `width` is the page width, not a constraint on the content: whatever you
    `add` keeps the size it already has, and content wider than the page is
    reported as OFF_CANVAS rather than shrunk. `inklet.fit` is how you build
    content *to* a width. The height follows the content unless you set it.
    """
    return Figure(width=width, **kwargs)
