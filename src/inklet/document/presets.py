"""Figure presets combining editable styles, physical formats and export defaults."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from ..core import pt
from ..themes import Theme, theme as get_theme
from ..themes.color import parse_color
from .publication import PublicationProfile
from .spec import length


@dataclass(frozen=True)
class FigureFormat:
    """Physical page dimensions in millimetres; None height fits the content."""
    name: str
    width: float
    height: float | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError('format needs a non-empty name')
        object.__setattr__(self, 'width', length(self.width, 'format width'))
        if self.height is not None:
            object.__setattr__(self, 'height', length(self.height, 'format height'))


@dataclass(frozen=True)
class PlotDefaults:
    """Defaults for live plot recipes; explicit recipe options take precedence."""
    grid: str = 'none'
    legend_side: str = 'bottom'
    tick_count: int = 5
    bar_fill: str = 'neutral'

    def __post_init__(self):
        if self.grid not in ('none', 'x', 'y', 'both'):
            raise ValueError('grid must be none, x, y or both')
        if self.legend_side not in ('bottom', 'top', 'left', 'right'):
            raise ValueError('legend_side must be bottom, top, left or right')
        if isinstance(self.tick_count, bool) or not isinstance(self.tick_count, int) or self.tick_count < 2:
            raise ValueError('tick_count must be an integer >= 2')
        if self.bar_fill not in ('neutral', 'accent'):
            raise ValueError('bar_fill must be neutral or accent')


@dataclass(frozen=True)
class GuidelineSource:
    """Journal guidance provenance, distinguishing reviewed and unverified sources."""
    title: str
    url: str
    reviewed_on: str | None
    status: str
    scope: str


@dataclass(frozen=True)
class Preset:
    """An immutable figure style, format, plot policy and publication profile.

    Use preset() to select a built-in, customize() to create a value with
    overrides, and document() to start authoring. Journal names describe
    authoring defaults; sources explain which guidance was actually reviewed.
    """
    name: str
    description: str
    format: FigureFormat
    publication: PublicationProfile
    plot: PlotDefaults = PlotDefaults()
    margin: float = 4
    gap: float = 6
    letter_style: str = 'bold-lower'
    sources: tuple[GuidelineSource, ...] = ()

    def __post_init__(self):
        if not isinstance(self.format, FigureFormat): raise TypeError('format must be a FigureFormat')
        if not isinstance(self.publication, PublicationProfile): raise TypeError('publication must be a PublicationProfile')
        if not isinstance(self.plot, PlotDefaults): raise TypeError('plot must be PlotDefaults')
        for field in ('margin', 'gap'):
            object.__setattr__(self, field, length(getattr(self, field), field, zero=True))
        if 2*self.margin >= self.format.width:
            raise ValueError('preset margins leave no page width')
        if self.format.height is not None and 2*self.margin >= self.format.height:
            raise ValueError('preset margins leave no page height')
        if self.letter_style not in ('bold-lower', 'lower', 'upper', 'bold-upper', 'paren'):
            raise ValueError('unknown panel letter style')
        if self.publication.width != self.format.width:
            raise ValueError('publication width must match the format width')
        object.__setattr__(self, 'sources', tuple(self.sources))

    @property
    def theme(self) -> Theme:
        """The resolved typography, palette and geometry used for measurement."""
        return self.publication.theme

    def customize(self, **options) -> Preset:
        """Return a preset with explicit overrides; dimensions use millimetres.

        Typography uses font_pt, small_font_pt and title_font_pt. Theme options
        include font_family, font_mono, accent, palette, paper, ink, muted,
        grid_color, radius and line_height. An accent override also changes
        the first automatic series colour unless palette is supplied.
        """
        theme_fields = {'font_family', 'font_mono', 'accent', 'palette', 'paper',
                        'ink', 'muted', 'radius', 'line_height', 'grid_color'}
        profile_fields = {'font_pt', 'small_font_pt', 'title_font_pt', 'stroke_mm',
                          'min_font_pt', 'min_stroke_mm', 'min_dpi', 'dpi', 'text'}
        other_fields = {'width', 'height', 'margin', 'gap', 'letter_style',
                        'grid', 'legend_side', 'tick_count', 'bar_fill'}
        unknown = set(options) - theme_fields - profile_fields - other_fields
        if unknown: raise TypeError(f'unknown preset options: {", ".join(sorted(unknown))}')
        changes = {key: value for key, value in options.items() if key in theme_fields}
        if 'grid_color' in changes: changes['grid'] = changes.pop('grid_color')
        if 'palette' in changes:
            if isinstance(changes['palette'], str): raise TypeError('palette must be a sequence of colours')
            changes['palette'] = tuple(changes['palette'])
            if not changes['palette']: raise ValueError('palette must not be empty')
            for color in changes['palette']: parse_color(color)
        elif 'accent' in changes:
            changes['palette'] = (changes['accent'], *self.theme.palette[1:])
        for key in ('accent', 'paper', 'ink', 'muted', 'grid'):
            if key in changes: parse_color(changes[key])
        for key in ('font_family', 'font_mono'):
            if key in changes and (not isinstance(changes[key], str) or not changes[key].strip()):
                raise ValueError(f'{key} must be a non-empty font family')
        for key in ('radius', 'line_height'):
            if key in changes: changes[key] = length(changes[key], key, zero=key == 'radius')
        physical = replace(self.format, **{k: options[k] for k in ('width', 'height') if k in options})
        profile = replace(self.publication, width=physical.width,
                          base_theme=replace(self.theme, **changes),
                          **{k: v for k, v in options.items() if k in profile_fields})
        return replace(self, format=physical, publication=profile,
                       plot=replace(self.plot, **{k: options[k] for k in ('grid', 'legend_side', 'tick_count', 'bar_fill') if k in options}),
                       **{k: options[k] for k in ('margin', 'gap', 'letter_style') if k in options})

    def document(self, **options):
        """Create a live document, retaining explicit page overrides on preset switches."""
        from .compiler import Document
        defaults = dict(width=self.format.width, height=self.format.height,
                        margin=self.margin, gap=self.gap, theme=self.theme,
                        publication=self.publication)
        doc = Document(**(defaults | options), preset=self)
        doc._preset_overrides = dict(options)
        return doc

    def as_dict(self):
        """Return a JSON-compatible record of resolved settings and source guidance."""
        result = asdict(self)
        result['theme'] = asdict(self.theme)
        return result


_FORMATS = {
    'single-column': FigureFormat('single-column', 89),
    'double-column': FigureFormat('double-column', 183),
    'report': FigureFormat('report', 180),
    'slide': FigureFormat('slide', 254, 142.875),
    'a4': FigureFormat('a4', 210, 297),
    'square': FigureFormat('square', 180, 180),
    'poster': FigureFormat('poster', 594, 841),
}

# The registry is private; callers receive immutable values through preset().
_STYLES = {
    'scientific.general': ('double-column', 'Compact figures for papers and technical reports.'),
    'scientific.nature': ('double-column', 'Nature main-figure typography and column widths.'),
    'scientific.science': ('double-column', 'Scientific authoring style; Science guidance review pending.'),
    'scientific.cell': ('double-column', 'Scientific authoring style; Cell guidance review pending.'),
    'educational.textbook': ('report', 'Readable labels and light horizontal guides for printed explanations.'),
    'educational.classroom': ('slide', 'Large projected labels and grids for teaching.'),
    'educational.worksheet': ('a4', 'Monochrome figures and grids for printed exercises.'),
    'marketing.report': ('report', 'Clear titles, strong accents and restrained horizontal guides.'),
    'marketing.presentation': ('slide', 'Large titles and labels for presentations.'),
    'marketing.infographic': ('square', 'Roomy square compositions with prominent headings.'),
}


def preset_names(family=None) -> tuple[str, ...]:
    """List built-in presets, optionally restricted to one family."""
    families = ('scientific', 'educational', 'marketing')
    if family is not None and family not in families:
        raise ValueError(f'unknown preset family {family!r}; choose {", ".join(families)}')
    return tuple(name for name in sorted(_STYLES) if family is None or name.startswith(family+'.'))


def format_names() -> tuple[str, ...]:
    """List built-in physical formats accepted by preset()."""
    return tuple(sorted(_FORMATS))


def preset(name='scientific.general', *, format=None, **overrides) -> Preset:
    """Choose a scientific, educational or marketing preset and physical format.

    For example, preset('educational.classroom', format='slide').document().
    Format accepts a registered name or a custom FigureFormat. The legacy
    theme() and publication() defaults are unchanged.
    """
    if not isinstance(name, str): raise TypeError('preset name must be a string')
    name = name.strip().lower()
    if name not in _STYLES:
        raise ValueError(f'unknown preset {name!r}; choose {", ".join(preset_names())}')
    default_format, description = _STYLES[name]
    chosen = default_format if format is None else format
    if isinstance(chosen, str):
        if chosen not in _FORMATS:
            raise ValueError(f'unknown format {chosen!r}; choose {", ".join(format_names())}')
        chosen = _FORMATS[chosen]
    if not isinstance(chosen, FigureFormat): raise TypeError('format must be a name or FigureFormat')
    factor = {'slide': 2., 'poster': 4.}.get(chosen.name, 1.)
    family = name.split('.')[0]
    base = get_theme('nature')
    palette = ('#0072b2', '#d55e00', '#009e73', '#cc79a7', '#e69f00', '#56b4e9')
    font, small, title, stroke, radius = 8., 7., 9., .18, .8
    grid, letters, margin, gap = 'none', 'bold-lower', 4., 6.
    min_font = 6.
    sources = ()
    if family == 'educational':
        font, small, title, stroke, radius = 10., 9., 13., .25, 1.5
        grid, letters, margin, gap, min_font = 'y', 'paren', 6., 8., 8.
        palette = ('#245b8a', '#b85318', '#277456', '#80529a', '#a27900')
        if name.endswith('classroom'): grid = 'both'
        if name.endswith('worksheet'):
            palette = ('#202020', '#666666', '#999999')
            radius, grid = 0., 'both'
    elif family == 'marketing':
        font, small, title, stroke, radius = 10., 8., 16., .3, 2.
        grid, letters, margin, gap, min_font = 'y', 'bold-upper', 6., 8., 7.
        palette = ('#635baf', '#137c76', '#b94d2d', '#486ba8', '#91643e')
        if name.endswith('infographic'): title, grid = 18., 'none'
    elif name == 'scientific.nature':
        font, small, title, min_font = 7., 6., 7., 5.
        radius = 0.
        sources = (GuidelineSource(
            'Nature research figure guide',
            'https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/',
            '2026-09-05', 'reviewed',
            'Main figures: 89/183 mm widths, 5–7 pt text, standard sans-serif fonts and editable embedded text. '
            'Other formats scale typography for their destination. Maximum height and maximum font size '
            'are guidance only; existing diagnostics check minimum type, strokes and raster resolution.'),)
    elif name in ('scientific.science', 'scientific.cell'):
        journal = name.split('.')[1]
        letters = 'bold-upper'
        sources = (GuidelineSource(
            'Science author instructions' if journal == 'science' else 'Cell figure guidelines',
            'https://www.science.org/content/page/instructions-preparing-initial-manuscript' if journal == 'science'
            else 'https://www.cell.com/figureguidelines',
            None, 'unverified',
            'Publisher page could not be accessed for review on 2026-09-05. Dimensions, type sizes '
            'and lettering are Inklet authoring defaults, not verified journal requirements.'),)
    base = replace(base, name=name, palette=palette, accent=palette[0],
                   font_family='Arial, Helvetica, Liberation Sans, DejaVu Sans, sans-serif',
                   font_mono='DejaVu Sans Mono, monospace',
                   font_size=pt(font), font_size_small=pt(small), font_size_large=pt(title),
                   stroke=stroke, hairline=max(.1, stroke*.6), thick=stroke*2,
                   radius=radius, arrow_size=1.6 if family == 'scientific' else 2.2,
                   space=tuple(v*(1 if family == 'scientific' else 1.3) for v in base.space),
                   muted='#525a65', grid='#dedee3').scaled(factor)
    profile = PublicationProfile(name, chosen.width, font*factor, small*factor,
                                 stroke*factor, min_font*factor, .1*factor,
                                 min_dpi=150 if chosen.name == 'slide' else 300,
                                 dpi=150 if chosen.name == 'slide' else 300,
                                 base_theme=base, title_font_pt=title*factor)
    bar_fill = 'accent' if family in ('educational', 'marketing') and not name.endswith('worksheet') else 'neutral'
    return Preset(name, description, chosen, profile, PlotDefaults(grid, bar_fill=bar_fill),
                  margin*factor, gap*factor, letters, sources).customize(**overrides)
