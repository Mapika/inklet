"""Explicit Cycles render-quality choices, independent of publication styling."""
from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class RenderQuality:
    """Physical resolution and Cycles sampling settings for scene renders."""
    name: str
    dpi: float
    samples: int
    denoise: bool
    noise_threshold: float

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError('Render quality needs a name')
        if not math.isfinite(self.dpi) or self.dpi <= 0:
            raise ValueError('Render DPI must be finite and positive')
        if type(self.samples) is not int or self.samples < 1:
            raise ValueError('Render samples must be a positive integer')
        if type(self.denoise) is not bool:
            raise ValueError('denoise must be a boolean')
        if not math.isfinite(self.noise_threshold) or not 0 <= self.noise_threshold <= 1:
            raise ValueError('noise_threshold must be between zero and one')


_QUALITIES = {
    'draft': RenderQuality('draft', 100, 16, True, .1),
    'preview': RenderQuality('preview', 180, 64, True, .03),
    'final': RenderQuality('final', 300, 256, True, .01),
}


def render_quality(name='preview', **overrides):
    """Get immutable draft, preview or final settings, with validated overrides.

    These control scene pixels and Cycles sampling, not figure fonts or layout.
    A zero noise threshold disables adaptive sampling. Explicit render_blend
    arguments take precedence over a supplied quality preset.
    """
    try:
        quality = _QUALITIES[name]
    except (KeyError, TypeError):
        raise ValueError('Choose draft, preview or final render quality') from None
    return replace(quality, **overrides) if overrides else quality


def quality_options(quality, dpi, samples, denoise, noise_threshold):
    if isinstance(quality, str):
        quality = render_quality(quality)
    if quality is not None and not isinstance(quality, RenderQuality):
        raise TypeError('quality must be a name or RenderQuality')
    if dpi is None:
        dpi = quality.dpi if quality else 150
    if samples is None:
        samples = quality.samples if quality else 32
    if denoise is None and quality:
        denoise = quality.denoise
    if noise_threshold is None and quality:
        noise_threshold = quality.noise_threshold
    if denoise is not None and type(denoise) is not bool:
        raise ValueError('denoise must be a boolean or None')
    if noise_threshold is not None and (not math.isfinite(noise_threshold) or not 0 <= noise_threshold <= 1):
        raise ValueError('noise_threshold must be between zero and one')
    return quality, dpi, samples, denoise, noise_threshold
