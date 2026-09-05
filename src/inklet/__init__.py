"""inklet -- publication-quality diagrams that lay themselves out.

The premise: an author should never compute a coordinate. Boxes size themselves
to their text, stacks space themselves, and arrows find the boundary of what
they point at. What is left to write is what the diagram *means*.

    import inklet

    encoder = inklet.box("Encoder\\n(ViT-B/16)")
    decoder = inklet.box("Decoder")
    panel = inklet.vstack([encoder, decoder], gap=6)

    fig = inklet.figure(width="89mm")
    fig.add(panel)
    fig.link(encoder, decoder, label="latent z")
    print(fig.report())
    fig.save("fig1.svg")
"""

from __future__ import annotations

from dataclasses import replace as _replace

from .assets import asset
from .core import (
    COLUMN_DOUBLE, COLUMN_SINGLE, Affine, Diagram, DiagramError, Envelope, Rect, Style, StyleError,
    Vec2,
    mm, pt, resolve, text_features,
)
from .figure import Figure, apply_theme, figure
from .layout import (
    Graph, GraphEdge, GraphError, LabelChoice, LabelWeights,
    Sankey, SankeyError, SankeyFlow, SankeyNode,
    align_to, beside, box as _box_container, fit, flow, frame, graph, grid,
    hstack, label_plan, overlay, pad, place_labels, sankey, spacer, stack,
    vstack,
)
from .links import Link, link, route, route_all
from .diagnostics import (Diagnostic, abutting, crossing, format_report,
                          lint)
from .draw import (
    annotate, annotation_side, arc, as_drawn, bracket, clip, curve, dimension,
    drawn, encoded, label_slot, label_specs, letters, marker, path, place,
    placed_anchor, plot_area, polygon, polyline, scalebar, sector,
)
from .plot.categories import CategorySet, categories
from .components import database, feature_matrix, sequence
from .render import outline_text, save_pdf, save_svg, to_pdf, to_svg
from .plot import (
    Panel, Ramp, Scale, axis, band, grouped_band, broken, colorbar, column, dates, facets,
    histogram, inset, legend, linear, log, panel, ramp, ribbon, row, symlog,
)
from .plot import (
    PolarPanel, circular_histogram, circular_mean, polar, theta_ticks,
)
from .three import (
    Mat4, Mesh, Vec3, anchor3d, axes, cartoon, model, outline_of, scene, solid,
)
from .typeset import (Baseline, baseline, baseline_arc, escape_markup, measure,
                      shape, strip_markup, theme_colors)
from .typeset import onpath as _onpath
from .themes import (THEMES, Theme, contrast_ratio, darken, lighten, mix,
                     readable, theme)

from contextvars import ContextVar

_current: Theme = theme("nature")
_theme_context = ContextVar("inklet_theme", default=None)


def use_theme(name: str | Theme) -> Theme:
    """Set the theme new content is built against.

    Colour is resolved late, at figure build time, but *geometry* -- padding,
    corner radius, gaps -- has to be decided while shapes are being made. This
    is where those defaults come from.
    """
    global _current
    chosen = theme(name) if isinstance(name, str) else name
    if _theme_context.get() is not None:
        _theme_context.set(chosen)
    else:
        _current = chosen
    return chosen


def current_theme() -> Theme:
    """The theme new nodes are being styled with right now.

    Read it for the design tokens rather than typing numbers: `t.stroke`,
    `t.hairline`, `t.thick`, `t.ink`, `t.muted`, `t.paper`, `t.accent`,
    `t.color(i)` for the categorical series, `t.gap("m")` for the standard
    spacings. Styling from these is what keeps a figure looking like one thing.
    """
    return _theme_context.get() or _current


def text(content: str, *, size: float | str | None = None, font: str | None = None,
         weight: str | None = None, align: str = "center",
         width: float | str | None = None, line_height: float | None = None,
         features: dict[str, bool | int] | None = None, markup: bool = True,
         angle: float = 0.0, kind: str = "text", **style) -> Diagram:
    """Shaped text as a diagram. Its envelope is the real inked extent, which is
    what lets a box around it actually fit.

    Inline markup, every piece of it escapable with `\\` and composable with
    the rest:

    * `**bold**` and `//italic//`, set in the real bold and italic faces of the
      family and measured in them, so a bold phrase in a justified column takes
      the width it will draw at. Doubled delimiters because a lone `*` belongs
      to `*CO` and a lone `/` to a URL.
    * `{accent|text}` colours a span: a theme token (`ink`, `muted`, `accent`,
      `paper`, `grid`, `series0`...) or any literal fill, `{#c1121f|text}`.
    * `H_{2}O` and `x^{2}` set sub- and superscripts; the braces are the
      markup, so `file_name` and `m^-1` are typed as they are.

    `markup=False` turns all of it off for a string that must reach the page
    exactly as typed. `weight` sets the face for the whole block (`"bold"`,
    `"bold italic"`); `features` are OpenType tags, e.g. `{"tnum": True}` for
    the tabular figures an axis wants.

    `angle` turns the block. **Degrees, and positive is clockwise on the page**
    -- y grows downward in inklet, so the rotation carrying +x toward +y is the
    one a reader sees turn clockwise, and `angle=-90` is the bottom-to-top
    y-axis label. The *shaped block* turns, not the letters one at a time: the
    line was measured once, horizontally, and is then placed, so a turned
    label is tracked exactly like the upright one. What the node reports turns
    with it, so `hstack` packs the diagonal of a 45-degree label rather than
    its upright box and `inklet.lint` measures clearance to the letters where
    they actually are.
    """
    _check_string("text", content)
    th = current_theme()
    asked = weight if weight is not None else style.get("font_weight") or "regular"
    # A slant asked for as a style field is the same request as one written
    # into the weight, and either way the block has to be *measured* in the
    # sloped face: italic is a different design, not the upright leaned over,
    # and a viewer re-shaping it inside a box built for the upright overruns.
    if style.get("font_style") == "italic" and not _slanted(asked):
        asked = f"{asked} italic"
    prim = shape(
        content,
        font=font or th.font_family,
        size=mm(size) if size is not None else th.font_size,
        weight=asked,
        align=align,
        width=mm(width) if width is not None else None,
        line_height=line_height or th.line_height,
        features=features,
        markup=markup,
        colors=theme_colors(th),
    )
    # Record what it was shaped with. Anything that reshapes the block later --
    # outlining it to paths, placing live glyphs -- must ask for the same
    # features or it positions glyphs by different rules than these advances,
    # and ten tabular digits drift 2.8mm. `getattr` because `shape()` may
    # already have stamped it (M13).
    if features and not getattr(prim, "features", ()):
        prim = _replace(prim, features=text_features(features))
    # The block was measured in the face `weight` names, so the live `<text>`
    # has to ask for the same one or a viewer re-shapes it inside a box built
    # for something else. Weight and slant are separate fields on `Style`, so
    # `weight="bold italic"` sets both and neither can be said by the other.
    if weight is not None:
        words = weight.replace("-", " ").replace("_", " ").split()
        upright = " ".join(w for w in words if w.lower() not in _SLANT_WORDS)
        if upright and upright != "regular" and "font_weight" not in style:
            style["font_weight"] = upright
        if _slanted(weight) and "font_style" not in style and _STYLE_TAKES_SLANT:
            style["font_style"] = "italic"
    node = Diagram(prim=prim, kind=kind,
                   envelope_override=_halo_envelope(prim, style.get("halo")))
    node = node.styled(**style) if style else node
    return node if not angle else node.rotated(angle)


def _halo_envelope(prim, halo) -> Envelope | None:
    """The space a haloed block claims: the block, grown by the paper that
    shows around each stem.

    A halo is a stroke painted *under* the glyphs, half of which the glyph
    itself covers, so `halo=0.4` puts 0.2mm of ink outside the block on every
    side. Layout spaces by the envelope and `inklet.lint` measures gaps with it,
    so without this a haloed label is packed as though the halo were not there
    and the first thing it touches is its neighbour. Nothing is shaped
    differently -- a halo has no advance -- and the trace is deliberately left
    alone, exactly as padding leaves it alone: an arrow aimed at a label should
    still land on the letters.
    """
    if not halo:
        return None
    return prim.envelope().pad(mm(halo) / 2)


def label(content: str, **kwargs) -> Diagram:
    """Smaller, quieter text -- for annotating rather than naming."""
    _check_string("label", content)
    kwargs.setdefault("size", current_theme().font_size_small)
    kwargs.setdefault("kind", "label")
    return text(content, **kwargs)


def title(content: str, **kwargs) -> Diagram:
    """`text` at the theme's large size, tagged as a title.

    The tag is what lets a theme style titles apart from body text later; the
    size is the theme's, so titles across a figure agree without being told to.

    The weight is the theme's too, and it is taken *here* rather than left to
    the role applied at build time: a title the theme sets bold has to be
    measured in the bold face, or the box it was stacked into was sized for a
    lighter one and the type overruns it.
    """
    _check_string("title", content)
    kwargs.setdefault("size", current_theme().font_size_large)
    kwargs.setdefault("kind", "title")
    kwargs.setdefault("weight", _role_face(current_theme().style_for("panel-title")))
    return text(content, **kwargs)


def text_on_path(content: str | Diagram, along, **kwargs) -> Diagram:
    """Set a line of text along a curve, one shaping cluster per station.

        ring = inklet.arc(18, -140, -40)
        inklet.drawn([ring, inklet.text_on_path("excitation", ring, size=2.4,
                                          lift=0.8)])

    `along` is a drawn node, a `inklet.typeset.Baseline`, or anything
    `inklet.baseline()` takes. A string is shaped here with `inklet.text`'s options
    (`size=`, `weight=`, `fill=`, markup and all), which is why they are
    accepted alongside the placement's own `align`, `start_offset`, `lift`,
    `side`, `flip`, `overflow`, `spacing` and `pivot` -- see
    `inklet.typeset.text_on_path` for those and for the sign convention, which is
    the library's: positive is clockwise. If the figure also *draws* the
    curve, pass `lift=` to raise the type off the stroke.
    """
    return _onpath.text_on_path(_to_set(content, kwargs), along, **kwargs)


def text_on_arc(content: str | Diagram, radius: float, angle: float,
                **kwargs) -> Diagram:
    """Set a line of text around a circle, centred on the bearing `angle`.

        inklet.text_on_arc("270", 21, 90, side="outside", gap=1.0)

    Degrees, 0 due east and increasing clockwise on the page. `side` is named
    for the circle here -- `"outside"` keeps the ink clear of `radius` on the
    far side from the centre, `"inside"` on the near side, by `gap` mm -- and
    the run turns itself over on the half of the circle where it would
    otherwise read upside-down. `inklet.typeset.text_on_arc` has the rest.
    """
    return _onpath.text_on_arc(_to_set(content, kwargs), radius, angle, **kwargs)


def _to_set(content: str | Diagram, kwargs: dict) -> Diagram:
    """A string becomes a shaped block, taking the `inklet.text` options out of
    the placement's keywords; a node the caller already built is left alone."""
    if isinstance(content, Diagram):
        return content
    _check_string("text_on_path", content)
    opts = {name: kwargs.pop(name) for name in list(kwargs)
            if name not in _PLACEMENT_ARGS}
    return text(content, **opts)


#: The keywords that belong to the placement rather than to the typesetting,
#: so that `inklet.text_on_arc("x", 10, 0, size=2, gap=1)` can carry both.
_PLACEMENT_ARGS = frozenset({
    "align", "start_offset", "lift", "side", "flip", "overflow", "spacing",
    "pivot", "kind", "gap", "centre", "sweep",
})


#: Slant tokens a `weight=` string may carry, e.g. `weight="bold italic"`.
_SLANT_WORDS = ("italic", "oblique")

#: Whether this build of core can carry a slant on a `Style`. Read rather than
#: assumed, so a figure asking for italic on an older core is set in the italic
#: face and merely says so less precisely in the file.
_STYLE_TAKES_SLANT = hasattr(Style(), "font_style")


def _slanted(weight: str) -> bool:
    """Whether a weight string asks for a sloped face."""
    return any(word.lower() in _SLANT_WORDS
               for word in weight.replace("-", " ").replace("_", " ").split())


def _role_face(role: Style) -> str:
    """A theme role's face as one `weight=` string.

    A role may set a slant as well as a weight, and both have to reach the
    typesetter: the role is applied at build time, long after the title was
    measured and stacked, so a title a theme sets bold italic has to be
    measured in the bold italic or the box it went into was sized for another
    face. Same reasoning as the weight, which has been read here all along.
    """
    weight = role.font_weight or "regular"
    if getattr(role, "font_style", None) == "italic":
        return f"{weight} italic"
    return weight


def box(content: str | Diagram | None = None, *, pad: float | str | None = None,
        radius: float | str | None = None, shape_: str = "rect",
        width: float | str | None = None, height: float | str | None = None,
        **style) -> Diagram:
    """A labelled container that sizes itself to what is inside it.

    The first argument is what goes *in* the box -- a string or a diagram --
    not how big it is: `width=` and `height=` are minimum sizes, and with no
    content at all they are the whole story, so `box(width=16, height=10)` is
    an empty 16x10 box.
    """
    th = current_theme()
    if radius is not None:
        style.setdefault("corner_radius", mm(radius))
    _check_content("box", content, width, height)
    if content is None:
        content = spacer()
    inner = text(content, width=width) if isinstance(content, str) else content
    node = _box_container(
        inner,
        pad=th.gap("m") if pad is None else mm(pad),
        radius=th.radius if radius is None else mm(radius),
        shape=shape_,
        min_width=mm(width) if width is not None else None,
        min_height=mm(height) if height is not None else None,
    )
    # The name is what the linter and `fig.report()` quote back, so it is what
    # the reader sees rather than what was typed: `box("**(a)** Cell")` is
    # named "(a) Cell". The markup drew the label; repeating the delimiters in
    # a diagnostic only makes the diagnostic harder to read.
    node = node.named(strip_markup(content)) if isinstance(content, str) else node
    return node.styled(**style) if style else node


def circle(content: str | Diagram | None = None, **kwargs) -> Diagram:
    """`box` with an elliptical outline, taking the same keywords.

    It sizes itself to its content like a box does, which means a long label
    gives a wide ellipse rather than a big circle. A circle of a stated size is
    `circle(width=16, height=16)` -- the first argument is the label, not the
    diameter, so that one function covers both and neither reading is a guess.
    """
    _check_content("circle", content, kwargs.get("width"), kwargs.get("height"))
    kwargs["shape_"] = "ellipse"
    return box(content, **kwargs)


def _check_string(what: str, content) -> None:
    """Refuse anything but a string where the words go, at the door and by name.

    Same reasoning as `_check_content`, and the same two mistakes: `text(16)`
    is either a number someone meant to set, or a size they expected the first
    argument to be. Left alone it raises `argument of type 'int' is not
    iterable` from inside the markup scanner, three frames down and naming
    neither the function nor what was wrong with the call.
    """
    if isinstance(content, str):
        return
    if isinstance(content, (int, float)) and not isinstance(content, bool):
        raise TypeError(
            f"{what}() takes the words to set, not a size: write "
            f"{what}({str(content)!r}) to set the number as text, or "
            f"{what}('...', size={content!r}) to set the type size"
        )
    raise TypeError(
        f"{what}() takes a string, not {type(content).__name__} ({content!r})"
    )


def _check_content(what: str, content, width, height) -> None:
    """Refuse a size where the content goes, at the door and by name.

    `inklet.circle(16)` is the reading everyone tries first, and left alone it
    raises `'int' object has no attribute 'envelope'` four frames inside
    `layout`, naming neither the function nor the argument. A number here is
    never anything but this mistake, so it is worth one check to say so.
    """
    if content is None or isinstance(content, (str, Diagram)):
        return
    if isinstance(content, (int, float)):
        size = f"width={content!r}" + ("" if width or height else
                                       f", height={content!r}")
        raise TypeError(
            f"{what}() takes the label that goes inside it, not a size: "
            f"write {what}({size}) for the size, or "
            f"{what}('text', {size}) for both"
        )
    raise TypeError(
        f"{what}() takes a string or a Diagram, not "
        f"{type(content).__name__} ({content!r})"
    )


from .document import (PublicationProfile, publication, subfigure, Composition, LayoutValue, composition, ModuleSpec, module, Document, CompiledFigure, LayoutError, document, PlotSpec,
                       ComponentSpec, plot_spec, component, Dataset, DataRef, Source,
                       Series, SharedScale, dataset, shared_scale, CategoryEncoding, FileRef, DerivedData, derive)

__all__ = [
    # live documents
    "PublicationProfile", "publication",
    "subfigure", "Composition", "LayoutValue", "composition", "ModuleSpec", "module",
    "Document", "CompiledFigure", "LayoutError", "document", "PlotSpec", "ComponentSpec",
    "plot_spec", "component", "Dataset", "DataRef", "Source", "Series", "SharedScale",
    "dataset", "shared_scale", "CategoryEncoding", "FileRef", "DerivedData", "derive",
    # authoring
    "text", "label", "title", "box", "circle", "asset", "escape_markup",
    "strip_markup",
    "text_on_path", "text_on_arc", "baseline", "baseline_arc", "Baseline",
    # drawing
    "path", "polyline", "polygon", "curve", "arc", "sector", "marker", "place",
    "clip", "encoded", "drawn", "as_drawn", "placed_anchor", "plot_area",
    # annotating
    "annotate", "annotation_side", "bracket", "dimension", "scalebar",
    "letters", "label_slot", "label_specs",
    "place_labels", "label_plan", "LabelChoice", "LabelWeights",
    # scientific diagram components
    "database", "feature_matrix", "sequence",
    # plotting
    "panel", "Panel", "row", "column", "axis", "colorbar", "legend",
    "linear", "log", "symlog", "band", "grouped_band", "broken", "dates", "Scale",
    "ramp", "Ramp", "CategorySet", "categories",
    "inset", "ribbon", "facets", "histogram",
    "polar", "PolarPanel", "theta_ticks",
    "circular_mean", "circular_histogram",
    "model", "solid", "scene", "axes", "cartoon",
    "Mesh", "Vec3", "Mat4", "anchor3d", "outline_of",
    "hstack", "vstack", "stack", "grid", "flow", "overlay", "pad", "frame",
    "spacer",
    "beside", "align_to", "fit",
    "graph", "Graph", "GraphEdge", "GraphError",
    "sankey", "Sankey", "SankeyError", "SankeyFlow", "SankeyNode",
    "link", "Link", "route", "route_all",
    "figure", "Figure",
    # theming
    "theme", "Theme", "THEMES", "use_theme", "current_theme", "contrast_ratio",
    "mix", "lighten", "darken", "readable",
    # inspection and output
    "lint", "abutting", "crossing", "Diagnostic", "format_report",
    "to_svg", "save_svg",
    "to_pdf", "save_pdf", "outline_text",
    "shape", "measure", "apply_theme", "resolve",
    # core types and units
    "Diagram", "DiagramError", "Style", "StyleError", "Vec2", "Rect", "Affine",
    "mm", "pt", "COLUMN_SINGLE", "COLUMN_DOUBLE",
]

__version__ = "2.5.0"
