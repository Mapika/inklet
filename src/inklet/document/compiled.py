"""Completed document state, diagnostics and exports, independent of authoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..core import Diagram, Placement
from ..diagnostics import lint, format_report
from ..render.page import RenderedPage
from ..render.scene import RenderScene


@dataclass(frozen=True)
class CompiledState:
    """The resolved drawing and render snapshot owned by one compilation."""
    root: Diagram
    placements: Mapping[str, Placement]
    scene: RenderScene
    paper: str

    @property
    def page(self) -> RenderedPage:
        return RenderedPage(self.scene, self.paper)


@dataclass(frozen=True)
class CompiledFigure:
    """A resolved snapshot; later authoring changes cannot alter its exports."""
    _state: CompiledState = field(repr=False)
    cells: Mapping
    diagnostics: tuple
    metadata: Mapping
    stats: Mapping

    @property
    def scene(self):
        """Shared compiled rendering snapshot used by every native export."""
        return self._state.scene

    @property
    def root(self):
        return self._state.root

    def build(self):
        """Return the retained drawing and read-only resolved placements."""
        return self._state.root, self._state.placements

    def lint(self, **kwargs):
        if not kwargs: return list(self.diagnostics)
        profile=self.metadata.get('publication',{})
        defaults={k:profile[k] for k in ('min_font_pt','min_stroke_mm','min_dpi','max_font_pt','max_height_mm') if k in profile}
        options = defaults | kwargs
        options.setdefault('page_fill', self._state.paper)
        return lint(self.root, page=self.root.bbox, placements=self._state.placements, **options)

    def report(self, **kwargs):
        return format_report(self.lint(**kwargs))

    def to_svg(self, *, text=None, **kwargs):
        if text is None: text=self.metadata.get('publication',{}).get('text','embed')
        return self._state.page.to_svg(text=text, **kwargs)

    def to_pdf(self, *, text=None, **kwargs):
        if text is None: text=self.metadata.get('publication',{}).get('text','embed')
        return self._state.page.to_pdf(text=text, **kwargs)

    def to_png(self, *, dpi=None, **kwargs):
        if dpi is None: dpi=self.metadata.get('publication',{}).get('dpi',150)
        return self._state.page.to_png(dpi=dpi, **kwargs)

    def save(self, *paths, **kwargs):
        kwargs.setdefault('text', self.metadata.get('publication',{}).get('text','embed'))
        return self._state.page.save(*paths, **kwargs)

    def export(self, directory, **kwargs):
        from ..render.bundle import export_bundle
        profile=self.metadata.get('publication')
        if profile:
            kwargs.setdefault('dpi',profile['dpi'])
            kwargs.setdefault('text',profile['text'])
        return export_bundle(self, directory, **kwargs)
