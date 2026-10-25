"""A house style for a whole figure set, stated once.

The figures of one project share more than a journal preset says: one font,
two or three line weights, one marker style, named colour maps for the things
the project keeps meaning (groups, doses, sizes), the panel letter, what text
may look like, the column widths, how files are written, and the checks that
keep all of it true. Written as module constants and helper functions in a
style file, those rules are restated in every script and drift; nothing tells
the author which figure broke which rule.

`Suite` holds them as one immutable value::

    house = inklet.suite(
        "lab", base="scientific.nature", font="Nimbus Sans",
        type=dict(tick=6, label=7, key=6, note=6, letter=8),
        lines=dict(data=0.6, fit=0.75, axis=0.5),
        palettes={"group": {"control": "#555555", "treated": "#0072b2"}},
        ramps={"size": ["#c6dbef", "#2171b5", "#08306b"], "dose": "tol-ylorbr"})

    with house:                                  # theme for everything built here
        p = house.panel(60, 40, x=(0, 1), y=(0, 1))
        house.axes(p, x="time (h)", y="response")
        p.line(points, **house.line("treated"))
        p.scatter(points, **house.mark("treated"))
        house.end_labels(p, {"treated": (1.0, 0.8)})
    house.save(p, "dose_response", out="figures/")      # svg+pdf+png, lint with house rules

Everything is millimetres except where a field says pt. `customize()`
returns a changed copy. A suite never changes global state outside a
`with` block; inside one it is the active theme and `current_suite()`.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .core import Diagram, pt

__all__ = ["Suite", "suite", "current_suite", "TypeScale", "LineWeights",
           "MarkerStyle", "LetterStyle", "TextRules", "Export", "SaveResult",
           "BuildReport", "BuildRow"]

_ACTIVE: list["Suite"] = []


def _pt(value: float, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
        raise ValueError(f"{what} must be a positive size in pt, not {value!r}")
    return float(value)


@dataclass(frozen=True)
class TypeScale:
    """Type sizes in pt by role: tick labels, axis titles, keys, in-plot
    notes and direct labels, and panel letters."""
    tick: float = 6.0
    label: float = 7.0
    key: float = 6.0
    note: float = 6.0
    letter: float = 8.0

    def __post_init__(self):
        for name in ("tick", "label", "key", "note", "letter"):
            object.__setattr__(self, name, _pt(getattr(self, name), f"type.{name}"))


@dataclass(frozen=True)
class LineWeights:
    """Stroke weights in pt by tier. `data` is a measured series, `fit` a
    model fit or reference line, `axis` axis lines and ticks. `extra` names
    further tiers (`{"guide": 0.4}`). Lint allows exactly these weights in
    plot panels (`STROKE_TIER`)."""
    data: float = 0.6
    fit: float = 0.75
    axis: float = 0.5
    extra: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("data", "fit", "axis"):
            object.__setattr__(self, name, _pt(getattr(self, name), f"lines.{name}"))
        object.__setattr__(self, "extra", {k: _pt(v, f"lines.{k}") for k, v in sorted(dict(self.extra).items())})

    def tiers(self) -> dict[str, float]:
        return {"data": self.data, "fit": self.fit, "axis": self.axis, **self.extra}


@dataclass(frozen=True)
class MarkerStyle:
    """Filled markers `size` mm across; `outline=False` draws them without an
    outline. Open markers are a ring `ring` mm wide in the series colour.
    `min_contrast` deepens a marker colour along its own lightness until it
    reaches that contrast ratio on the paper (1.0 leaves colours alone), so
    the palest stops of a sequential ramp stay visible without an edge."""
    size: float = 0.9
    outline: bool = False
    ring: float = 0.3
    min_contrast: float = 1.0


@dataclass(frozen=True)
class LetterStyle:
    """Panel letters: `case` 'lower' or 'upper', bold (the only bold text a
    suite allows) and `gap` mm between the letter and its panel."""
    case: str = "lower"
    bold: bool = True
    gap: float = 1.0

    def __post_init__(self):
        if self.case not in ("lower", "upper"):
            raise ValueError("letters.case must be 'lower' or 'upper'")


@dataclass(frozen=True)
class TextRules:
    """`bold='letters'` allows bold only for panel letters. `muted=False`
    forbids grey annotation text; `muted_colors` lists the greys of the
    palette by name. `label_contrast` is the WCAG ratio direct labels are
    deepened to (`Suite.text_color`); `halo` mm of paper behind them (None:
    none). `keys='outside'` forbids keys inside plot panels."""
    bold: str = "letters"
    muted: bool = False
    muted_colors: tuple[str, ...] = ()
    label_contrast: float = 4.5
    halo: float | None = None
    keys: str = "outside"


@dataclass(frozen=True)
class Export:
    """How `Suite.save` writes a figure: the formats, the PNG resolution, text
    as embedded fonts, files rewritten only when their bytes change, element
    ids numbered per file (so bytes do not depend on build order)."""
    formats: tuple[str, ...] = ("svg", "pdf", "png")
    dpi: float = 300
    text: str = "embed"
    write: str = "changed"
    ids: str = "document"

    def __post_init__(self):
        formats = tuple(f.lower().lstrip(".") for f in self.formats)
        if not formats or set(formats) - {"svg", "pdf", "png"}:
            raise ValueError("export.formats are svg, pdf and png")
        object.__setattr__(self, "formats", formats)


def _merge(kind, value):
    if value is None:
        return kind()
    if isinstance(value, kind):
        return value
    if isinstance(value, Mapping):
        return kind(**value)
    raise TypeError(f"expected {kind.__name__} or a dict of its fields, not {type(value).__name__}")


@dataclass(frozen=True)
class Suite:
    """A figure set's house style: fonts, type, line weights, markers, colours,
    letters, text rules, widths, export and lint. Build one with `suite()`.

    `base` is a preset name or `Preset` for everything the suite does not
    say. `font` is a CSS-style family list; the first family is measured and
    embedded (TrueType and CFF OpenType faces both embed as live text).
    `allowed_fonts` are the families lint accepts (`FONT_SUBSTITUTED`);
    default, the families in `font`. `palettes` are categorical maps
    {name: {key: colour}} or sequences; `ramps` are sequential maps given as
    an inklet ramp name, a list of stops (interpolated in OKLab) or an
    ordinal {key: colour} dict. `widths` names page widths in mm.
    `lint` holds extra `lint()` keywords (`min_font_pt`, `max_height_mm`).
    """
    name: str
    base: object = "scientific.nature"
    font: str = "Helvetica, Arial, Liberation Sans, sans-serif"
    allowed_fonts: tuple[str, ...] | None = None
    ink: str | None = None
    paper: str = "#ffffff"
    type: TypeScale = field(default_factory=TypeScale)
    lines: LineWeights = field(default_factory=LineWeights)
    markers: MarkerStyle = field(default_factory=MarkerStyle)
    letters: LetterStyle = field(default_factory=LetterStyle)
    text: TextRules = field(default_factory=TextRules)
    palettes: Mapping[str, object] = field(default_factory=dict)
    ramps: Mapping[str, object] = field(default_factory=dict)
    widths: Mapping[str, float] = field(default_factory=lambda: {"single": 89.0, "double": 183.0})
    export: Export = field(default_factory=Export)
    lint: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("a suite needs a name")
        for attr, kind in (("type", TypeScale), ("lines", LineWeights), ("markers", MarkerStyle),
                           ("letters", LetterStyle), ("text", TextRules), ("export", Export)):
            object.__setattr__(self, attr, _merge(kind, getattr(self, attr)))
        object.__setattr__(self, "palettes", dict(self.palettes))
        object.__setattr__(self, "ramps", dict(self.ramps))
        object.__setattr__(self, "widths", {k: float(v) for k, v in dict(self.widths).items()})
        object.__setattr__(self, "lint", dict(self.lint))
        if self.allowed_fonts is not None:
            object.__setattr__(self, "allowed_fonts", tuple(self.allowed_fonts))
        from .themes.color import parse_color
        parse_color(self.paper)
        if self.ink is not None:
            parse_color(self.ink)
        for name, value in self.palettes.items():
            values = value.values() if isinstance(value, Mapping) else value
            for color in values:
                parse_color(color)
        object.__setattr__(self, "_cache", {})

    # -- derived styles ---------------------------------------------------

    def customize(self, **changes) -> "Suite":
        """A copy with fields replaced; a dict for a nested field merges into it
        (`customize(lines={"data": 0.5})` keeps `fit` and `axis`)."""
        out = {}
        for key, value in changes.items():
            current = getattr(self, key)
            if dataclasses.is_dataclass(current) and isinstance(value, Mapping):
                value = dataclasses.replace(current, **value)
            out[key] = value
        return dataclasses.replace(self, **out)

    @property
    def preset(self):
        """The base preset with this suite's font, type and weights."""
        got = self._cache.get("preset")
        if got is None:
            from .document.presets import Preset, preset as get_preset
            base = self.base if isinstance(self.base, Preset) else get_preset(str(self.base))
            options = dict(font_family=self.font, font_pt=self.type.label,
                           small_font_pt=self.type.tick, paper=self.paper,
                           expected_fonts=self.font_families(allowed=True))
            if self.ink is not None:
                options["ink"] = self.ink
            if base.publication.letter_font_pt is not None or self.type.letter:
                options["letter_font_pt"] = self.type.letter
            got = self._cache["preset"] = base.customize(**options)
        return got

    @property
    def theme(self):
        """The theme everything in the suite is measured against: the font,
        tick / label / letter sizes and the data line weight as default stroke."""
        got = self._cache.get("theme")
        if got is None:
            base = self.preset.theme
            got = self._cache["theme"] = dataclasses.replace(
                base, name=self.name, font_size=pt(self.type.label),
                font_size_small=pt(self.type.tick), font_size_large=pt(self.type.letter),
                stroke=pt(self.lines.data), hairline=min(pt(self.lines.axis), pt(self.lines.data)),
                thick=pt(self.lines.fit), paper=self.paper)
        return got

    def font_families(self, *, allowed: bool = False) -> tuple[str, ...]:
        """The families in `font` (or `allowed_fonts`), generic names dropped."""
        if allowed and self.allowed_fonts is not None:
            return self.allowed_fonts
        from .typeset.fonts import public_family
        generic = {"sans-serif", "serif", "monospace", "sans", "system-ui"}
        names = [n.strip().strip("'\"") for n in public_family(self.font).split(",")]
        return tuple(n for n in names if n and n.lower() not in generic)

    def fonts(self) -> dict[str, dict]:
        """How each face the suite sets resolves on this machine: file, family,
        and whether a PDF can embed it as live text."""
        from .render.fontembed import embeddable
        from .typeset.fonts import find_font
        out = {}
        for style, (weight, italic) in {"regular": ("regular", False), "bold": ("bold", False),
                                        "italic": ("regular", True)}.items():
            face = find_font(self.font, weight, italic)
            out[style] = dict(path=face.path, family=face.family,
                              embeddable=embeddable(face.path, face.index),
                              allowed=face.family in self.font_families(allowed=True))
        return out

    # -- the active suite -------------------------------------------------

    def __enter__(self) -> "Suite":
        from . import current_theme, use_theme
        self._cache.setdefault("previous", []).append(current_theme())
        use_theme(self.theme)
        _ACTIVE.append(self)
        return self

    def __exit__(self, *exc) -> None:
        from . import use_theme
        _ACTIVE.pop()
        use_theme(self._cache["previous"].pop())

    def _using(self):
        """`with self` unless self is already active (re-entrant helpers)."""
        import contextlib
        return contextlib.nullcontext(self) if _ACTIVE and _ACTIVE[-1] is self else self

    # -- sizes ------------------------------------------------------------

    def size(self, role: str) -> float:
        """A type size in mm: 'tick', 'label', 'key', 'note' or 'letter'."""
        try:
            return pt(getattr(self.type, role))
        except AttributeError:
            raise ValueError(f"unknown type role {role!r}; roles are tick, label, key, note, letter") from None

    def stroke(self, tier: str = "data") -> float:
        """A line weight in mm by tier name ('data', 'fit', 'axis' or an extra)."""
        tiers = self.lines.tiers()
        if tier not in tiers:
            raise ValueError(f"unknown line tier {tier!r}; tiers are {', '.join(tiers)}")
        return pt(tiers[tier])

    def width(self, name: str | float = "double") -> float:
        """A named page width in mm ('single', 'double', ...), or a number as is."""
        if isinstance(name, (int, float)):
            return float(name)
        if name not in self.widths:
            raise ValueError(f"unknown width {name!r}; widths are {', '.join(self.widths)}")
        return self.widths[name]

    # -- colour -----------------------------------------------------------

    def palette(self, name: str):
        """A categorical palette as given: {key: colour} or a tuple."""
        if name not in self.palettes:
            raise ValueError(f"unknown palette {name!r}; palettes are {', '.join(self.palettes) or 'none'}")
        value = self.palettes[name]
        return dict(value) if isinstance(value, Mapping) else tuple(value)

    def color(self, key: str, palette: str | None = None) -> str:
        """The colour of `key`: from `palette`, or the first palette that has
        it; a colour string is returned unchanged."""
        names = [palette] if palette is not None else list(self.palettes)
        for name in names:
            value = self.palettes.get(name)
            if isinstance(value, Mapping) and key in value:
                return value[key]
        if palette is None:
            from .themes.color import ColorError, parse_color
            try:
                parse_color(key)
                return key
            except (ColorError, ValueError):
                pass
        raise KeyError(f"no colour for {key!r} in {palette or 'any palette'}")

    def ramp(self, name: str) -> Callable[[float], str]:
        """A sequential map as a function of t in [0, 1]. Ordinal dict ramps
        are sampled along their keys in order."""
        got = self._cache.get(("ramp", name))
        if got is not None:
            return got
        if name not in self.ramps:
            raise ValueError(f"unknown ramp {name!r}; ramps are {', '.join(self.ramps) or 'none'}")
        spec = self.ramps[name]
        from .themes.color import interpolate_oklab
        if isinstance(spec, str):
            from . import ramp as named_ramp
            got = named_ramp(spec)
        else:
            stops = list(spec.values()) if isinstance(spec, Mapping) else list(spec)
            if len(stops) < 2:
                raise ValueError(f"ramp {name!r} needs at least two stops")

            def got(t, _stops=tuple(stops)):
                return interpolate_oklab(_stops, max(0.0, min(1.0, float(t))))
        self._cache[("ramp", name)] = got
        return got

    def stops(self, name: str) -> dict:
        """An ordinal ramp's fixed {key: colour} stops."""
        spec = self.ramps.get(name)
        if not isinstance(spec, Mapping):
            raise ValueError(f"ramp {name!r} has no named stops")
        return dict(spec)

    def text_color(self, color: str) -> str:
        """`color` deepened along its own lightness until text in it reaches
        `text.label_contrast` on the paper; hue is kept. A grey becomes ink."""
        from .diagnostics.house_rules import HouseRules, _muted
        from .themes.color import readable
        color = self._resolve(color)
        # A neutral grey series is labelled in ink (a deepened grey is still grey).
        if _muted(color, HouseRules(muted_colors=self.text.muted_colors, muted_chroma=0.015,
                                    muted_lightness=0.0)):
            return self.theme.ink
        return readable(self._resolve(color), self.paper, self.text.label_contrast)

    def mark_color(self, color: str) -> str:
        from .themes.color import readable
        color = self._resolve(color)
        if self.markers.min_contrast <= 1.0:
            return color
        return readable(color, self.paper, self.markers.min_contrast)

    def _resolve(self, color: str) -> str:
        try:
            return self.color(color)
        except KeyError:
            raise KeyError(f"{color!r} is neither a colour nor a key of a suite palette") from None

    # -- drawing helpers --------------------------------------------------

    def line(self, color: str, tier: str = "data", **style) -> dict:
        """`Panel.line` keywords: the colour (a palette key or a colour) and
        the tier's weight."""
        return dict(color=self._resolve(color), stroke_width=self.stroke(tier), **style)

    def mark(self, color: str, *, hollow: bool = False, size: float | None = None, **style) -> dict:
        """`Panel.scatter` keywords for the house marker: filled without an
        outline, or open as a ring in the series colour."""
        col = self.mark_color(color)
        out = dict(size=self.markers.size if size is None else size, **style)
        if hollow:
            out.update(color=col, hollow=True, stroke=col, stroke_width=self.markers.ring)
        elif not self.markers.outline:
            out.update(color=col, stroke="none")
        else:
            out.update(color=col)
        return out

    def marker(self, shape: str, color: str, *, hollow: bool = False, size: float | None = None) -> Diagram:
        """One placed or key marker in the house style (see `mark`)."""
        from . import marker
        col = self.mark_color(color)
        size = self.markers.size if size is None else size
        if hollow:
            return marker(shape, size, fill=self.paper, stroke=col, stroke_width=self.markers.ring)
        return marker(shape, size, fill=col, stroke="none")

    def panel(self, width: float, height: float, **kwargs):
        """`inklet.panel` built under this suite's theme."""
        from . import panel
        with self._using():
            return panel(width, height, **kwargs)

    def axes(self, p, x=None, y=None, **kwargs):
        """`Panel.axes` at the suite's tick and label sizes and axis weight."""
        options = dict(tick_font_size=self.size("tick"), label_font_size=self.size("label"),
                       stroke_width=self.stroke("axis"))
        options.update(kwargs)
        with self._using():
            return p.axes(x=x, y=y, **options)

    def label(self, text: str, *, role: str = "note", color: str | None = None, **kwargs) -> Diagram:
        """A text node at a role's size, never bold, in ink or the deepened
        colour of `color`."""
        from . import text as make_text
        kwargs.setdefault("markup", False)
        fill = self.theme.ink if color is None else self.text_color(color)
        if self.text.halo is not None:
            kwargs.setdefault("halo", self.text.halo)
        with self._using():
            return make_text(text, size=self.size(role), text_fill=fill, **kwargs)

    def end_labels(self, p, labels: Mapping[str, tuple[float, float]], *,
                   colors: Mapping[str, str] | None = None, gap: float = 0.4,
                   dx: float = 1.0, anchor: str = "w", role: str = "note"):
        """Direct series labels at line ends, spread so none overlap.

        `labels` maps each label to the data point it names (usually the last
        point of its line); the colour is the label's palette colour, or
        `colors[label]`, deepened to `text.label_contrast`. Labels keep their
        order and are moved apart vertically by the least total amount that
        leaves `gap` mm between them (`layout.label_search.stack`), then set
        `dx` mm right of their point (`anchor='e'` puts them to the left).
        For curves drawn with `name=`, `Panel.label_lines` does the same from
        the curves themselves.
        """
        from .layout.label_search import stack
        names = list(labels)
        if not names:
            return p
        colors = dict(colors or {})
        height = self.size(role) * 1.0
        ys = [p.point(*labels[n]).y for n in names]
        area = p.area
        moved = stack(ys, [height] * len(names), gap=gap, top=area.y0 + height / 2,
                      bottom=area.y1 - height / 2)
        with self._using():
            for name, y0, y1 in zip(names, ys, moved):
                color = colors.get(name, name)
                try:
                    fill = self.text_color(color)
                except KeyError:
                    fill = self.theme.ink
                kw = {}
                if self.text.halo is not None:
                    kw["halo"] = self.text.halo
                p.text(*labels[name], name, anchor=anchor,
                       offset=(dx if anchor == "w" else -dx, y1 - y0),
                       size=self.size(role), text_fill=fill, markup=False, **kw)
        return p

    def mosaic(self, layout, panels, *, height: float, width: str | float = "double", **kwargs) -> Diagram:
        """`inklet.panel_mosaic` with the suite's letters (size, gap, case)."""
        from . import panel_mosaic
        options = dict(label_size=self.size("letter"), label_gap=self.letters.gap,
                       gap=3.0, margin=2.0)
        options.update(kwargs)
        if self.letters.case == "upper":
            rows = [row.split() if isinstance(row, str) else list(row) for row in layout]
            upper = {k: k.upper() for k in panels}
            layout = [" ".join(upper.get(k, k) for k in row) for row in rows]
            panels = {upper[k]: v for k, v in panels.items()}
        with self._using():
            return panel_mosaic(layout, panels, width=self.width(width), height=height, **options)

    def letter(self, text: str) -> Diagram:
        """A panel letter on its own, for hand-built layouts: the suite's
        size, bold, baseline-aligned like the mosaic's (`header_text`)."""
        from .layout.mosaic import header_text
        from .draw.annotate import LETTER_KIND
        text = text.upper() if self.letters.case == "upper" else text
        with self._using():
            return header_text(text, self.size("letter"), weight="bold" if self.letters.bold else None,
                               kind=LETTER_KIND)

    def figure(self, width: str | float = "double", **kwargs):
        """`inklet.figure` on the suite's theme and paper, at a named width."""
        from . import figure
        options = dict(theme=self.theme, background=self.paper, margin=0)
        options.update(kwargs)
        return figure(width=self.width(width), **options)

    def document(self, width: str | float = "double", **kwargs):
        """The suite preset's live `Document`, lettered in the suite's style."""
        doc = self.preset.document(width=self.width(width), **kwargs)
        return doc

    # -- checks -----------------------------------------------------------

    def lint_rules(self):
        """The suite's house rules as `HouseRules` for `lint(house=...)`."""
        from .diagnostics.house_rules import HouseRules
        tiers = tuple(pt(v) for v in self.lines.tiers().values())
        return HouseRules(stroke_tiers=tiers, marker_outlines=self.markers.outline,
                          muted_text=self.text.muted, muted_colors=self.text.muted_colors,
                          bold=self.text.bold, keys=self.text.keys)

    def lint_options(self) -> dict:
        profile = self.preset.publication
        options = dict(min_font_pt=profile.min_font_pt, expected_fonts=self.font_families(allowed=True),
                       house=self.lint_rules(), page_fill=self.paper)
        if profile.max_letter_pt is not None:
            options["max_letter_pt"] = max(profile.max_letter_pt, self.type.letter)
        options.update(self.lint)
        return options

    def check(self, figure, **kwargs):
        """Lint diagnostics for a figure under the suite's limits and house
        rules. Takes a Figure, compiled Document, Document or Diagram."""
        target = self.page(figure)
        options = self.lint_options()
        options.update(kwargs)
        return target.lint(**options)

    # -- output -----------------------------------------------------------

    def page(self, item, width=None):
        """`item` as something that saves and lints: a Figure or compiled
        Document passes through, a Document is compiled, and a Diagram or
        Panel is put on a suite figure as wide as it (or `width`)."""
        from .figure import Figure
        if isinstance(item, Figure) or hasattr(item, "_state"):
            return item
        if hasattr(item, "compile") and not isinstance(item, Diagram):
            return item.compile()
        node = item.build() if hasattr(item, "build") and not isinstance(item, Diagram) else item
        if not isinstance(node, Diagram):
            raise TypeError(f"cannot save a {type(item).__name__}; pass a Figure, Document or Diagram")
        box = node.bbox
        fig = self.figure(width=self.width(width) if width is not None else box.x1 if box.x0 >= 0 else box.width,
                          height=box.y1 if box.y0 >= 0 else box.height)
        fig.add(node)
        return fig

    def save(self, item, name: str, *, out: str | Path = ".", width=None, report: bool = False) -> "SaveResult":
        """Write `out/name.{formats}` and lint them. Returns a `SaveResult`."""
        fig = self.page(item, width)
        out = Path(out)
        paths = [out / f"{name}.{fmt}" for fmt in self.export.formats]
        kwargs = dict(text=self.export.text, write=self.export.write, dpi=self.export.dpi)
        if "svg" in self.export.formats or "png" in self.export.formats:
            kwargs["ids"] = self.export.ids
        written = fig.save(*paths, **kwargs) or {}
        diagnostics = self.check(fig)
        root = fig.root if hasattr(fig, "root") else fig.build()[0]
        result = SaveResult(name=name, paths=tuple(str(p) for p in paths),
                            written=any(written.values()), height_mm=round(root.bbox.height, 1),
                            diagnostics=tuple(diagnostics))
        if report:
            print(result.summary())
        return result

    def build(self, figures: Mapping[str, object] | Iterable[tuple[str, object]], *,
              out: str | Path, only: Sequence[str] | None = None, inputs: Mapping[str, Sequence] | None = None,
              depends: Sequence[str | Path] = (), force: bool = False, isolate: bool = True,
              report: bool = True) -> "BuildReport":
        """Build a set of figures, skip the unchanged ones, lint them all.

        `figures` maps an output name to a zero-argument callable returning a
        Figure, Document or Diagram, or to `"module:function"` (default
        function `make_figure`). A figure is skipped when its fingerprint --
        the suite, the source file of its function, `depends` (files every
        figure reads, such as the style module) and `inputs[name]` (its data
        files) -- matches the last build recorded in `out/.inklet-build.json`
        and its outputs exist. A changed figure that renders the same bytes
        leaves its files untouched (`Export.write`).

        `isolate=True` restores `sys.path` after each figure and forgets the
        project modules it imported (library modules stay cached), so two
        figure modules importing different helper modules of the same name
        (from different directories) do not see each other's. One figure's failure is reported and the rest still build.
        """
        import importlib
        import traceback
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        items = list(figures.items()) if isinstance(figures, Mapping) else list(figures)
        if only:
            unknown = sorted(set(only) - {n for n, _ in items})
            if unknown:
                raise ValueError(f"unknown figure(s): {', '.join(unknown)}")
            items = [(n, f) for n, f in items if n in set(only)]
        manifest_path = out / ".inklet-build.json"
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            manifest = {}
        rows = []
        for name, target in items:
            saved_modules, saved_path = (dict(sys.modules), list(sys.path)) if isolate else (None, None)
            try:
                func = target
                if isinstance(target, str):
                    module, _, attr = target.partition(":")
                    func = getattr(importlib.import_module(module), attr or "make_figure")
                files = [*depends, *(inputs or {}).get(name, ())]
                source = _source_file(func)
                if source is not None:
                    files.append(source)
                key = _fingerprint(self, files)
                outputs = [out / f"{name}.{fmt}" for fmt in self.export.formats]
                previous = manifest.get(name, {})
                if not force and previous.get("key") == key and all(p.exists() for p in outputs):
                    rows.append(BuildRow(name, "unchanged", previous.get("height_mm"),
                                         previous.get("errors", 0), previous.get("warnings", 0),
                                         tuple(previous.get("house", ()))))
                    continue
                with self:
                    result = self.save(func(), name, out=out)
                house = tuple(sorted({d.code for d in result.diagnostics
                                      if d.code in _house_codes() and d.severity == "warning"}))
                row = BuildRow(name, "written" if result.written else "same bytes", result.height_mm,
                               result.errors, result.warnings, house, result.report())
                manifest[name] = dict(key=key, height_mm=result.height_mm, errors=result.errors,
                                      warnings=result.warnings, house=list(house))
                rows.append(row)
            except Exception:                                 # noqa: BLE001
                rows.append(BuildRow(name, "failed", None, None, None, (), traceback.format_exc()))
                manifest.pop(name, None)
            finally:
                if isolate:
                    for mod in set(sys.modules) - set(saved_modules):
                        if _project_module(sys.modules[mod]):
                            del sys.modules[mod]
                    sys.modules.update(saved_modules)
                    sys.path[:] = saved_path
        tmp = manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        tmp.replace(manifest_path)
        result = BuildReport(tuple(rows))
        if report:
            print(result.table())
        return result


def _house_codes():
    from .diagnostics.house_rules import HOUSE_CODES
    return HOUSE_CODES


def _library_roots() -> tuple[str, ...]:
    import sysconfig
    paths = sysconfig.get_paths()
    roots = {paths.get(k) for k in ("stdlib", "platstdlib", "purelib", "platlib")}
    roots.add(str(Path(__file__).resolve().parent))         # inklet itself
    return tuple(sorted(str(Path(r).resolve()) for r in roots if r))


def _project_module(module) -> bool:
    """Whether `module` is the project's own code rather than a library.

    `Suite.build(isolate=True)` forgets the project modules a figure imported,
    so the next figure imports its own helper of the same name. Library
    modules stay cached: several (fontTools.subset, for one) patch other
    modules' classes when imported, and importing them a second time leaves
    two generations of those classes in the process.
    """
    path = getattr(module, "__file__", None)
    if not path:
        return False
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        return False
    return not any(resolved.startswith(root + "/") or resolved == root for root in _library_roots())


def _source_file(func) -> str | None:
    import inspect
    try:
        return inspect.getsourcefile(func)
    except TypeError:
        return None


def _fingerprint(house: Suite, files: Iterable) -> str:
    digest = hashlib.sha256()
    digest.update(repr(_suite_key(house)).encode())
    for path in sorted({str(Path(f)) for f in files}):
        digest.update(path.encode())
        try:
            digest.update(Path(path).read_bytes())
        except OSError:
            digest.update(b"<missing>")
    from . import __version__
    digest.update(__version__.encode())
    return digest.hexdigest()[:20]


def _suite_key(house: Suite):
    return tuple((f.name, repr(getattr(house, f.name))) for f in dataclasses.fields(house))


@dataclass(frozen=True)
class SaveResult:
    """What `Suite.save` wrote and found."""
    name: str
    paths: tuple[str, ...]
    written: bool
    height_mm: float
    diagnostics: tuple

    @property
    def errors(self) -> int:
        return sum(d.severity == "error" for d in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(d.severity == "warning" for d in self.diagnostics)

    def report(self) -> str:
        from .diagnostics import format_report
        return format_report([d for d in self.diagnostics if d.severity in ("error", "warning")])

    def summary(self) -> str:
        state = "written" if self.written else "unchanged on disk"
        return (f"[{self.name}] {self.height_mm} mm tall, {state}; {self.errors} errors, "
                f"{self.warnings} warnings\n{self.report()}")


@dataclass(frozen=True)
class BuildRow:
    name: str
    status: str            # written | same bytes | unchanged | failed
    height_mm: float | None
    errors: int | None
    warnings: int | None
    house: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class BuildReport:
    """One row per figure: status, height, lint counts and the house rules it breaks."""
    rows: tuple[BuildRow, ...]

    @property
    def ok(self) -> bool:
        """No figure failed and none has a lint error."""
        return all(r.status != "failed" and not r.errors for r in self.rows)

    def table(self) -> str:
        lines = [f"{'figure':28s} {'status':11s} {'mm':>6s} {'err':>4s} {'warn':>5s}  house rules broken"]
        for r in self.rows:
            mm = "-" if r.height_mm is None else f"{r.height_mm:.1f}"
            err = "-" if r.errors is None else str(r.errors)
            warn = "-" if r.warnings is None else str(r.warnings)
            lines.append(f"{r.name:28s} {r.status:11s} {mm:>6s} {err:>4s} {warn:>5s}  {', '.join(r.house)}")
        for r in self.rows:
            if r.status == "failed":
                lines.append(f"\n[{r.name}] failed:\n{r.detail}")
        return "\n".join(lines)


def suite(name: str, **options) -> Suite:
    """A house style for a figure set; see `Suite` for every field. Nested
    fields take dicts: `suite("lab", lines={"data": 0.6, "fit": 0.75})`."""
    return Suite(name, **options)


def current_suite() -> Suite | None:
    """The suite of the innermost `with suite:` block, or None."""
    return _ACTIVE[-1] if _ACTIVE else None
