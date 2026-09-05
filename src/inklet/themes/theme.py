"""Design tokens, and the one place that turns them into `core.style.Style`.

Everything downstream reads tokens. Nothing downstream writes a colour or a
stroke width, which is what makes "retheme the whole figure" a one-line change
and what lets the linter reason about contrast at all.

Sizes are millimetres throughout, per the contract -- including type sizes,
which are stored as `units.pt(n)` rather than as points, so that a font size
and a corner radius are the same kind of number and can be added.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..core.style import Style
from ..core.units import pt
from .color import contrast_ratio, mix, readable
from .palettes import OKABE_ITO, TOL_BRIGHT, TOL_MUTED

__all__ = [
    "Theme", "ThemeError", "THEMES", "ROLES", "GAP_NAMES", "HAIRLINE_FLOOR",
    "theme", "theme_names", "NATURE", "SLIDES", "NOTEBOOK",
]


class ThemeError(ValueError):
    """An unknown theme, role or spacing step."""


# 0.25pt. Below this a line either drops out of the plate on press or fills in
# on paper, depending on which way the printer errs; either way it is no longer
# a line you designed. Nothing scales a stroke under it.
HAIRLINE_FLOOR = 0.088

ROLES: tuple[str, ...] = (
    "arrowhead", "axis", "box", "code", "emphasis", "frame", "grid", "label",
    "link", "mark", "mark-line", "muted", "panel-title", "plot-area", "root",
    "text",
)

# 'm' is index 3 so that the named steps sit symmetrically in the middle of the
# scale and the extremes stay reachable by name too.
GAP_NAMES: dict[str, int] = {
    "2xs": 0, "xs": 1, "s": 2, "m": 3, "l": 4, "xl": 5, "2xl": 6,
}


@dataclass(frozen=True)
class Theme:
    """A complete set of design tokens.

    Frozen, because a theme is a value: handing one to a figure must not let
    that figure mutate it out from under another. `scaled()` is how you get a
    variant.
    """

    name: str

    # -- colour -----------------------------------------------------------
    ink: str            # primary foreground; never pure black, which prints muddy
    paper: str          # background the figure assumes it sits on
    muted: str          # secondary foreground, still readable as body text
    accent: str         # the one colour that means "look here"
    grid: str           # rules and guides, meant to sit under everything

    palette: tuple[str, ...]   # categorical series, colour-vision-deficiency safe

    # -- type -------------------------------------------------------------
    font_family: str
    font_mono: str
    font_size: float           # mm
    font_size_small: float     # mm
    font_size_large: float     # mm
    line_height: float         # multiple of font size, unitless

    # -- geometry (mm) ----------------------------------------------------
    stroke: float              # default outline weight
    hairline: float            # the thinnest line this theme will draw
    thick: float               # emphasis weight
    radius: float              # corner radius for boxes
    space: tuple[float, ...]   # spacing scale, small to large
    arrow_size: float          # arrowhead length
    link_radius: float = 0.0   # elbow rounding on a connector; 0 is square

    # -- roles ------------------------------------------------------------

    def style_for(self, role: str) -> Style:
        """The `Style` for a semantic role.

        Only the fields the role is actually about are set; everything else
        stays `None` so that `Style.over()` keeps inheriting. That is why
        `emphasis` can be dropped on any subtree and only change its weight and
        colour, leaving sizes and fills alone.
        """
        match role:
            case "root":
                # Sets the document-wide defaults every other node inherits.
                # `fill` is the literal "none" rather than None: None would mean
                # "inherit", and an unfilled path must stay unfilled.
                return Style(
                    fill="none", stroke=self.ink, stroke_width=self.stroke,
                    stroke_linecap="round", stroke_linejoin="round",
                    font_family=self.font_family, font_size=self.font_size,
                    line_height=self.line_height, text_fill=self.ink,
                )
            case "box":
                # Opaque paper fill, so a box laid over a link occludes it.
                return Style(
                    fill=self.paper, stroke=self.ink, stroke_width=self.stroke,
                    stroke_linejoin="round", corner_radius=self.radius,
                )
            case "frame":
                return Style(
                    fill="none", stroke=self.muted, stroke_width=self.hairline,
                    stroke_linejoin="round", corner_radius=self.radius,
                )
            case "text":
                return Style(
                    text_fill=self.ink, font_family=self.font_family,
                    font_size=self.font_size, line_height=self.line_height,
                )
            case "label":
                return Style(
                    text_fill=self.ink, font_family=self.font_family,
                    font_size=self.font_size_small, line_height=self.line_height,
                )
            case "panel-title":
                return Style(
                    text_fill=self.ink, font_family=self.font_family,
                    font_size=self.font_size_large, font_weight="bold",
                    line_height=self.line_height,
                )
            case "code":
                return Style(
                    text_fill=self.ink, font_family=self.font_mono,
                    font_size=self.font_size_small, line_height=self.line_height,
                )
            case "link":
                return Style(
                    fill="none", stroke=self.ink, stroke_width=self.stroke,
                    stroke_linecap="round", stroke_linejoin="round",
                )
            case "arrowhead":
                # Filled, and deliberately not stroked: a stroked arrowhead
                # grows by half the stroke width and stops meeting its line.
                return Style(fill=self.ink, stroke="none")
            case "grid":
                return Style(
                    fill="none", stroke=self.grid, stroke_width=self.hairline,
                    stroke_linecap="butt",
                )
            case "axis":
                # Butt caps, not round: a round cap hangs half a stroke width
                # past the end of a tick, so ticks poke through the spine and
                # the spine overshoots the corner. Nobody would notice one; a
                # reader notices a plot where every tick is blunt.
                return Style(
                    fill="none", stroke=self.ink, stroke_width=self.stroke,
                    stroke_linecap="butt", stroke_linejoin="miter",
                )
            case "plot-area":
                # Opaque, so a panel dropped over other content occludes it,
                # and unstroked -- the frame is the axis's job.
                return Style(fill=self.paper, stroke="none")
            case "mark":
                # A data mark is a filled shape. It is deliberately not stroked:
                # a stroke grows the mark by half its width, which breaks the
                # equal-area sizing `inklet.draw.marker` goes to some trouble for.
                return Style(fill=self.ink, stroke="none")
            case "mark-line":
                # The marks made of strokes rather than area -- cross, plus.
                return Style(
                    fill="none", stroke=self.ink, stroke_width=self.stroke,
                    stroke_linecap="round",
                )
            case "emphasis":
                # Colour and weight only, so it composes onto text or shapes.
                # Both `stroke` and `text_fill` are set because the role has to
                # work on either; this relies on the renderer colouring text
                # from `text_fill` and never stroking a glyph outline, which is
                # what `Style` keeps the two fields separate for.
                return Style(stroke=self.accent, text_fill=self.accent,
                             font_weight="bold")
            case "muted":
                return Style(stroke=self.muted, text_fill=self.muted)
            case _:
                raise ThemeError(f"unknown role {role!r}; known roles are {ROLES}")

    # -- palette ----------------------------------------------------------

    def color(self, index: int) -> str:
        """The categorical colour for series `index`.

        Inside the palette this is the *published* value, correct for fills.
        For a stroke or for text on `paper`, use `ink_color`.

        Past the end of the palette it is a *shade* of one rather than a repeat
        of one. A CVD-safe scheme is a fixed length -- Tol's bright set is
        seven -- and the old wrap made series 7 byte-identical to series 0, so
        an eight-series legend named two different things with one swatch.
        Editing a published, cited palette to reach a round number is the one
        thing `palettes.py` will not do, so the overflow is the palette again
        with its lightness moved: first lap away from whichever of `ink` and
        `paper` the colour already sits nearest, second lap back towards it,
        and further laps the same two directions taken harder. Choosing the
        direction per colour rather than per lap is what makes the step
        visible on *every* member -- Okabe-Ito opens with black, which a nudge
        towards a near-black ink would not have moved at all.

        The hue is kept, so a reader who separates the base colours separates
        these; eight or more categories is a chart that wants a different
        encoding, and this makes that legible rather than silently wrong.
        """
        size = len(self.palette)
        base = self.palette[index % size]
        laps = max(0, index // size)
        if laps == 0:
            return base
        far, near = self.paper, self.ink
        if contrast_ratio(base, near) > contrast_ratio(base, far):
            far, near = near, far
        toward = far if laps % 2 else near
        return mix(base, toward, min(0.30 + 0.15 * ((laps - 1) // 2), 0.75))

    def text_on(self, background: str, min_ratio: float = 4.5) -> str:
        """Ink that stays readable on `background`.

        `ink` is chosen against `paper`, so it says nothing about a label sitting
        on a filled box. Okabe-Ito's first colour is black and is a perfectly
        good fill -- but the theme's near-black ink on it is 1.2:1, which is not
        text, it is a rumour. Prefer `ink` and switch to `paper` only when that
        is the readable one, so the common case is unchanged.

        A mid-tone fill can defeat both ends at once: Tol's rose is 4.3:1 under
        the notebook theme's ink and 3.5:1 under its paper, so picking "the
        better one" returns a colour that still fails AA. When that happens the
        nearer of the two is walked along its own lightness by `readable` until
        it clears -- the same routine `inklet.plot` uses for a number written on a
        matrix cell, so a caption on a swatch and a label in a heatmap answer to
        one rule. Only this last case moves; both early returns are the old
        behaviour exactly.
        """
        here = contrast_ratio(self.ink, background)
        if here >= min_ratio:
            return self.ink
        there = contrast_ratio(self.paper, background)
        if there >= min_ratio:
            return self.paper
        return readable(self.ink if here >= there else self.paper,
                        background, min_ratio)

    def ink_color(self, index: int, min_ratio: float = 3.0) -> str:
        """`color(index)`, darkened towards `ink` until it clears `min_ratio`
        against `paper`.

        CVD-safe palettes are built for area, not for line. Okabe-Ito's yellow
        is 1.3:1 on white; drawn as a 0.25mm rule it is invisible. Rather than
        edit a published palette, we blend towards the theme's own ink, which
        preserves hue order while buying contrast. The 5% step is fixed so the
        result is byte-identical run to run.
        """
        color = self.color(index)
        for step in range(21):
            candidate = mix(color, self.ink, step / 20)
            if contrast_ratio(candidate, self.paper) >= min_ratio:
                return candidate
        return self.ink

    def text_color(self, index: int, min_ratio: float = 4.5) -> str:
        """`color(index)`, darkened along its own hue until it can carry text.

        The pale half of any CVD-safe palette cannot: Okabe-Ito's yellow is
        1.3:1 on white and its sky blue 1.9:1, so a tick label, a series name
        or a twinned axis painted in the series colour is a colour swatch
        rather than a word. `ink_color` buys contrast by blending towards the
        theme's ink, which is right for a *line* -- a rule is a graphical
        object, its threshold is 3:1, and a small drift towards grey is
        invisible at 0.25mm. Type needs 4.5:1, which is far enough that the
        blend arrives at something closer to grey than to the series, so this
        holds the hue instead and only moves the lightness.

        The result is a different colour from `color(index)` by construction,
        and deliberately so: it is the one that reads. Use it for the words and
        `color(index)` for the ink they name.
        """
        return readable(self.color(index), self.paper, min_ratio)

    # -- spacing ----------------------------------------------------------

    def gap(self, step: int | str) -> float:
        """A spacing value, by name ('xs' 's' 'm' 'l' 'xl') or by index."""
        index = GAP_NAMES.get(step, step) if isinstance(step, str) else step
        if isinstance(index, str):
            raise ThemeError(
                f"unknown spacing step {step!r}; "
                f"names are {tuple(sorted(GAP_NAMES))} or an index"
            )
        try:
            return self.space[index]
        except IndexError:
            raise ThemeError(
                f"spacing index {index} is outside the {len(self.space)}-step scale"
            ) from None

    # -- variants ---------------------------------------------------------

    def scaled(self, factor: float) -> "Theme":
        """The same design at a different physical size.

        Lengths multiply; colours and `line_height` do not, because a ratio and
        a hue have no size. The name is kept: scaling changes how big the design
        is drawn, not which design it is.
        """
        if factor <= 0:
            raise ThemeError(f"scale factor must be positive, got {factor}")
        return replace(
            self,
            font_size=self.font_size * factor,
            font_size_small=self.font_size_small * factor,
            font_size_large=self.font_size_large * factor,
            stroke=self.stroke * factor,
            hairline=max(self.hairline * factor, HAIRLINE_FLOOR),
            thick=self.thick * factor,
            radius=self.radius * factor,
            space=tuple(s * factor for s in self.space),
            arrow_size=self.arrow_size * factor,
            link_radius=self.link_radius * factor,
        )


# Nature's figure spec: Helvetica, 5-7pt, built for an 89mm single column.
# Type here is 7pt with 6pt labels, which leaves headroom under the 5pt floor
# even if the figure is reduced on the page. Strokes are 0.25pt-family weights.
NATURE = Theme(
    name="nature",
    ink="#1a1a1a",       # 17.4:1 on white; pure black on coated stock reads as a hole
    paper="#ffffff",
    muted="#5f6b7a",     # 5.4:1, clears WCAG AA for small text
    accent="#0072b2",    # Okabe-Ito blue, so the accent is also series colour 5
    grid="#e4e4e7",
    palette=OKABE_ITO.colors,
    font_family="Helvetica Neue, Helvetica, Arial, sans-serif",
    font_mono="SF Mono, Menlo, Consolas, monospace",
    font_size=pt(7),
    font_size_small=pt(6),
    font_size_large=pt(8),
    line_height=1.25,
    stroke=0.25,
    hairline=0.13,
    thick=0.5,
    radius=1.0,
    space=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0),
    arrow_size=1.6,
)

# Projected, from the back of a room: everything doubles, contrast goes up, and
# the palette switches to Tol's bright set, which holds its hues under a
# washed-out projector better than Okabe-Ito's softer greens.
SLIDES = Theme(
    name="slides",
    ink="#111418",       # 18.5:1
    paper="#ffffff",
    muted="#4b5563",     # 7.6:1 -- a projector eats the low end, so muted stays strong
    accent="#4477aa",    # Tol bright blue, the palette's own lead colour
    grid="#d4d4d8",
    palette=TOL_BRIGHT.colors,
    font_family="Inter, Helvetica Neue, Helvetica, Arial, sans-serif",
    font_mono="JetBrains Mono, SF Mono, Menlo, monospace",
    font_size=pt(14),
    font_size_small=pt(11),
    font_size_large=pt(20),
    line_height=1.3,
    stroke=0.6,
    hairline=0.3,
    thick=1.2,
    radius=2.0,
    space=(1.0, 2.0, 4.0, 6.0, 10.0, 16.0, 26.0),
    arrow_size=3.6,
)

# Screen-first: warm paper instead of clinical white, roomier leading, softer
# corners, and Tol's muted set, which brings nine hues instead of eight and
# reads as less severe than the print default.
NOTEBOOK = Theme(
    name="notebook",
    ink="#1f2328",       # 15.4:1 on this paper
    paper="#fcfcfa",     # off-white; pure white glares on a backlit display
    muted="#57606a",     # 6.2:1
    accent="#332288",    # Tol muted indigo, the palette's own lead colour
    grid="#e6e4e0",      # warm, to match the paper rather than fight it
    palette=TOL_MUTED.colors,
    font_family="Inter, Segoe UI, Roboto, Helvetica, sans-serif",
    font_mono="JetBrains Mono, SF Mono, Menlo, monospace",
    font_size=pt(9),
    font_size_small=pt(7.5),
    font_size_large=pt(12),
    line_height=1.4,
    stroke=0.35,
    hairline=0.18,       # a 0.13mm rule disappears on a 1x display
    thick=0.7,
    radius=1.8,
    space=(0.5, 1.5, 3.0, 4.5, 7.0, 11.0, 18.0),
    arrow_size=2.2,
)

THEMES: dict[str, Theme] = {t.name: t for t in (NATURE, SLIDES, NOTEBOOK)}


def theme(name: str = "nature") -> Theme:
    """Look up a theme by name. The default is the one built for print."""
    try:
        return THEMES[name.strip().lower()]
    except KeyError:
        raise ThemeError(
            f"unknown theme {name!r}; known themes are {theme_names()}"
        ) from None


def theme_names() -> tuple[str, ...]:
    """Sorted, so anything that prints or iterates these stays deterministic."""
    return tuple(sorted(THEMES))
