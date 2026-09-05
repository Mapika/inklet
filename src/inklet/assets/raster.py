"""Reading, writing and filtering rasters.

The narrow waist between Pillow and the rest of this package: everything past
here works on `uint8` arrays of shape (h, w, 4) in straight (unpremultiplied)
RGBA, and nothing else in the package imports Pillow. Keeping the conversion in
one place is what makes the pipeline testable without a file on disk, and what
stops a mode bug -- a palette image, a greyscale TIFF, a CMYK scan -- from
turning up four steps later as an inexplicable array shape.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from .deps import AssetError, numpy, pillow, require

__all__ = ["load_rgba", "save_png", "luminance", "blur", "shrink_mask"]


def load_rgba(path: str | Path) -> Any:
    """Load any image Pillow can read as straight RGBA.

    EXIF orientation is applied. A phone photograph is very often stored
    sideways with a tag saying so, and a silhouette traced from the stored
    pixels would be rotated relative to the picture the author saw.
    """
    np = numpy()
    Image, _ = pillow()
    orient = require("PIL.ImageOps")

    file = Path(path)
    if not file.is_file():
        raise AssetError(f"no such image: {str(file)!r}")
    try:
        with Image.open(file) as handle:
            handle = orient.exif_transpose(handle) or handle
            rgba = handle.convert("RGBA")
            return np.asarray(rgba, dtype=np.uint8).copy()
    except AssetError:
        raise
    except Exception as exc:
        # Pillow raises UnidentifiedImageError, OSError and a few decoder-specific
        # types; a caller only ever wants "this file is not a usable image".
        raise AssetError(f"cannot decode image {str(file)!r}: {exc}") from exc


def save_png(rgba: Any, path: str | Path) -> None:
    """Write straight RGBA to PNG in the smallest mode that is still exact.

    No metadata is attached on purpose. A tEXt or tIME chunk would put the
    build time or the library version into the file, and the file's bytes are
    most of the SVG's bytes.

    Nor is the mode: an RGBA PNG spends four bytes a pixel, and most of what
    goes through here does not need them. A micrograph is grey and opaque; a
    line-art cutout is a handful of colours with an alpha channel. Written as
    RGBA, `stress/electro/assets/sem.png` came back out 63% bigger than it went
    in, and every one of those bytes is then base64'd into the SVG at four
    thirds. So the array is measured first and written in whichever of L, LA,
    RGB, RGBA or a palette holds exactly the same pixels; where two could, both
    are encoded and the smaller wins, because which one that is depends on the
    picture -- indices compress worse than grey levels on a photograph and far
    better on a diagram. Nothing here is a quantiser: a palette is used only
    when the image already has 256 colours or fewer.
    """
    best: bytes | None = None
    for image, options in _lossless_encodings(rgba):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9,
                   **options)
        encoded = buffer.getvalue()
        if best is None or len(encoded) < len(best):
            best = encoded
    Path(path).write_bytes(best or b"")


def _lossless_encodings(rgba: Any) -> list[tuple[Any, dict]]:
    """Every PNG spelling that reproduces `rgba` exactly: image and save kwargs."""
    np = numpy()
    Image, _ = pillow()
    opaque = bool((rgba[:, :, 3] == 255).all())
    grey = bool((rgba[:, :, 0] == rgba[:, :, 1]).all()
                and (rgba[:, :, 1] == rgba[:, :, 2]).all())
    if grey:
        mode, planes = ("L", rgba[:, :, 0]) if opaque else ("LA", rgba[:, :, ::3])
    else:
        mode, planes = ("RGB", rgba[:, :, :3]) if opaque else ("RGBA", rgba)
    out = [(Image.fromarray(np.ascontiguousarray(planes), mode), {})]

    # Counting colours means sorting the pixels, so they are packed four bytes
    # to a word first: a one-dimensional unique over 2.5 million uint32s is a
    # different order of cost from a lexicographic one over 2.5 million rows.
    height, width = rgba.shape[:2]
    packed = np.ascontiguousarray(rgba).reshape(-1, 4).view(np.uint32).ravel()
    colours = np.unique(packed)
    if len(colours) > 256:
        return out
    table = colours.view(np.uint8).reshape(-1, 4)
    index = np.searchsorted(colours, packed).astype(np.uint8)
    indexed = Image.fromarray(index.reshape(height, width), "P")
    indexed.putpalette(bytes(table[:, :3].reshape(-1).tolist()))
    options = {} if opaque else {"transparency": bytes(table[:, 3].tolist())}
    return out + [(indexed, options)]


def luminance(image: Any) -> Any:
    """Perceptual grey in 0..1, for edge detection. Takes RGB or RGBA.

    Rec. 709 weights on gamma-encoded values -- deliberately not the linearised
    luminance `themes.color` computes. XDoG is a filter over what the eye sees
    as tone, and linearising first crushes the shadow contrast the line art is
    supposed to find.
    """
    np = numpy()
    rgb = image[:, :, :3].astype(np.float64) / 255.0
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def blur(gray: Any, sigma: float) -> Any:
    """Gaussian blur of a float 0..1 plane, via Pillow's separable filter.

    Pillow's implementation is a fixed three-pass box approximation, which is
    both faster than a NumPy convolution and, more importantly, exactly
    reproducible for a given radius -- there is no FFT and no threading in it.
    """
    np = numpy()
    Image, ImageFilter = pillow()
    if sigma <= 0:
        return gray
    plane = Image.fromarray(np.clip(gray * 255.0, 0, 255).astype(np.uint8), mode="L")
    blurred = plane.filter(ImageFilter.GaussianBlur(radius=float(sigma)))
    return np.asarray(blurred, dtype=np.float64) / 255.0


def shrink_mask(mask: Any, max_side: int) -> Any:
    """Reduce a boolean mask for contour tracing, keeping its extent.

    Area-averaging and then accepting any non-zero coverage is max-pooling in
    disguise: a foreground pixel anywhere in a box keeps the box foreground. It
    has to be, because the tracing frame is normalised so the mask's extreme
    rows and columns land exactly on the placed rectangle's edges. Ordinary
    thresholding would drop a thin tail -- a whisker, a tail, an antenna -- and
    the silhouette would then claim a different bounding box from the crop.
    """
    np = numpy()
    Image, _ = pillow()
    h, w = mask.shape
    longest = max(h, w)
    if longest <= max_side:
        return mask
    scale = max_side / longest
    nw, nh = max(2, round(w * scale)), max(2, round(h * scale))
    small = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    reduced = small.resize((nw, nh), Image.Resampling.BOX)
    return np.asarray(reduced, dtype=np.uint8) > 0
