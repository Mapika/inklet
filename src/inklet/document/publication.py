"""Physical publication defaults and print-size checks, independent of journals."""
from dataclasses import dataclass, replace

from ..themes import theme as get_theme
from ..themes import Theme
from ..core import pt
from .spec import length


@dataclass(frozen=True)
class PublicationProfile:
    """An editable set of physical page, typography, stroke and export defaults.

    These are general authoring presets, not journal submission certifications.
    Thresholds are applied to the final transformed artwork at its export size.
    """
    name: str
    width: float
    font_pt: float = 8
    small_font_pt: float = 7
    stroke_mm: float = .18
    min_font_pt: float = 6
    min_stroke_mm: float = .1
    min_dpi: float = 300
    dpi: float = 300
    text: str = 'embed'
    base_theme: Theme | str = 'nature'
    title_font_pt: float | None = None
    max_font_pt: float | None = None
    max_height_mm: float | None = None

    def __post_init__(self):
        for name in ('width','font_pt','small_font_pt','stroke_mm','min_font_pt','min_stroke_mm','min_dpi','dpi'):
            length(getattr(self,name), name)
        if self.text not in ('embed','outline'): raise ValueError('publication text must be embed or outline')
        if isinstance(self.base_theme, str): get_theme(self.base_theme)
        elif not isinstance(self.base_theme, Theme): raise TypeError('base_theme must be a Theme or theme name')
        if self.title_font_pt is not None: length(self.title_font_pt, 'title_font_pt')
        for name in ('max_font_pt', 'max_height_mm'):
            if getattr(self, name) is not None: length(getattr(self, name), name)
        if self.max_font_pt is not None and self.max_font_pt < self.min_font_pt:
            raise ValueError('max_font_pt must be at least min_font_pt')

    @property
    def theme(self):
        base = get_theme(self.base_theme) if isinstance(self.base_theme, str) else self.base_theme
        return replace(base, font_size=pt(self.font_pt),
                       font_size_small=pt(self.small_font_pt),
                       font_size_large=pt(self.font_pt+1 if self.title_font_pt is None else self.title_font_pt),
                       stroke=self.stroke_mm,hairline=max(self.min_stroke_mm,self.stroke_mm*.6))

    @property
    def checks(self):
        checks = dict(min_font_pt=self.min_font_pt,min_stroke_mm=self.min_stroke_mm,min_dpi=self.min_dpi)
        checks.update({name: getattr(self, name) for name in ('max_font_pt', 'max_height_mm')
                       if getattr(self, name) is not None})
        return checks

    def document(self, **options):
        """Create a document with this profile's theme, checks and export defaults."""
        from .compiler import Document
        return Document(**(dict(width=self.width,theme=self.theme,publication=self) | options))


def publication(name='double-column', **options):
    """Choose single-column (89 mm), double-column (183 mm), or slide (254 mm).

    Override dimensions and print thresholds to match the actual destination.
    Use profile.document() to apply the profile throughout authoring and export.
    """
    profiles = {
        'single-column': PublicationProfile('single-column',89),
        'double-column': PublicationProfile('double-column',183),
        'slide': PublicationProfile('slide',254,font_pt=12,small_font_pt=10,
                                    stroke_mm=.3,min_font_pt=9,min_stroke_mm=.18,min_dpi=150,dpi=150),
    }
    if name not in profiles: raise ValueError(f'unknown publication profile {name!r}; choose {", ".join(profiles)}')
    return replace(profiles[name], **options)
