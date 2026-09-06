"""Numeric Blender passes and physically aligned visualizations."""
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import math
from pathlib import Path
import struct

from ..core import Diagram, DiagramError, ImagePrim


def _numpy():
    try:
        import numpy
    except ImportError:
        raise DiagramError('Pass arrays and visualizations require inklet[images]') from None
    return numpy


@dataclass(frozen=True)
class ScenePass:
    """Immutable little-endian float32 pixels, in top-left row order.

    Depth is axial camera Z distance in scene units (1e10 denotes background).
    Normals are world-space XYZ. Object IDs are integer-valued floats; zero
    denotes background. These are numeric data, without display colour transforms.
    """
    name: str
    pixels: tuple[int, int]
    channels: int
    width_mm: float
    height_mm: float
    data: bytes = field(repr=False)

    def __post_init__(self):
        expected = {'depth': 1, 'normal': 3, 'object_id': 1}
        if self.name not in expected or self.channels != expected[self.name]:
            raise ValueError('Invalid scene pass name or channels')
        if len(self.pixels) != 2 or any(type(v) is not int or v <= 0 for v in self.pixels):
            raise ValueError('Pass dimensions must be two positive integers')
        if not all(math.isfinite(v) and v > 0 for v in (self.width_mm, self.height_mm)):
            raise ValueError('Pass physical dimensions must be finite and positive')
        object.__setattr__(self, 'pixels', tuple(self.pixels))
        object.__setattr__(self, 'data', bytes(self.data))
        if len(self.data) != self.pixels[0] * self.pixels[1] * self.channels * 4:
            raise ValueError('Pass byte count does not match its dimensions')

    def value(self, x, y):
        """Read one pixel without NumPy; normals return an XYZ tuple."""
        if type(x) is not int or type(y) is not int:
            raise TypeError('Pixel coordinates must be integers')
        if not (0 <= x < self.pixels[0] and 0 <= y < self.pixels[1]):
            raise IndexError('Pixel is outside the scene pass')
        values = struct.unpack_from('<' + 'f' * self.channels, self.data,
                                    (y * self.pixels[0] + x) * self.channels * 4)
        return values[0] if self.channels == 1 else values

    def to_numpy(self):
        """Return a read-only H×W or H×W×3 NumPy view; requires inklet[images]."""
        np = _numpy()
        shape = (self.pixels[1], self.pixels[0])
        if self.channels > 1:
            shape += (self.channels,)
        return np.frombuffer(self.data, dtype='<f4').reshape(shape)

    def save(self, path):
        """Save numeric data as .npy without losing precision or changing axes."""
        target = Path(path)
        if target.suffix != '.npy':
            raise ValueError('Scene passes save numeric arrays to .npy files')
        values = self.to_numpy()
        target.parent.mkdir(parents=True, exist_ok=True)
        _numpy().save(target, values, allow_pickle=False)

    def _diagram(self, rgba, **settings):
        from PIL import Image
        stream = BytesIO()
        Image.fromarray(rgba).save(stream, format='PNG')
        data = stream.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        return Diagram(prim=ImagePrim('scene-pass:' + digest, self.width_mm,
            self.height_mm, self.pixels, data=data), kind='raster-layer',
            notes={'raster_layer': dict(reason='scene ' + self.name + ' visualization',
                sha256=digest, source_sha256=hashlib.sha256(self.data).hexdigest(),
                pixels=list(self.pixels), pass_name=self.name, **settings)})

    def to_diagram(self, *, value_range=None):
        """Visualize a pass with transparent background; requires inklet[images].

        Depth maps near to white and far to black. Supply value_range=(near, far)
        for comparable views; otherwise the finite foreground range is recorded.
        Normals map [-1,1] to RGB; object IDs use a fixed categorical palette.
        """
        np = _numpy()
        values = self.to_numpy()
        rgba = np.zeros((self.pixels[1], self.pixels[0], 4), dtype=np.uint8)
        settings = {}
        if self.name != 'depth' and value_range is not None:
            raise ValueError('value_range applies only to depth')
        if self.name == 'depth':
            valid = np.isfinite(values) & (values >= 0) & (values < 1e10)
            if value_range is None:
                near = float(values[valid].min()) if valid.any() else 0.
                far = float(values[valid].max()) if valid.any() else 1.
                if far == near:
                    far = near + 1.
            else:
                near, far = map(float, value_range)
                if not (math.isfinite(near) and math.isfinite(far) and 0 <= near < far):
                    raise ValueError('Depth range must be finite with 0 <= near < far')
            grey = np.zeros(values.shape, dtype=np.uint8)
            grey[valid] = np.rint(255 * (1 - np.clip((values[valid] - near) / (far - near), 0, 1))).astype(np.uint8)
            rgba[:, :, :3] = grey[:, :, None]
            settings['value_range'] = [near, far]
        elif self.name == 'normal':
            valid = np.isfinite(values).all(axis=2) & (np.linalg.norm(values, axis=2) > 0)
            rgba[valid, :3] = np.rint(255 * (np.clip(values[valid], -1, 1) + 1) / 2).astype(np.uint8)
        else:
            valid = np.isfinite(values) & (values > 0)
            palette = np.array([(36,107,142),(235,145,52),(85,168,104),(164,112,182),
                                (206,83,93),(77,175,182),(166,137,88),(132,144,160)], dtype=np.uint8)
            rgba[valid, :3] = palette[(values[valid].astype(np.int64) - 1) % len(palette)]
        rgba[valid, 3] = 255
        return self._diagram(rgba, **settings)

    def object_mask(self, ids):
        """Make a white alpha stencil for object IDs, aligned with the scene."""
        if self.name != 'object_id':
            raise ValueError('Object masks require an object_id pass')
        np = _numpy()
        ids = tuple(ids)
        if not ids or any(type(v) is not int or v <= 0 for v in ids):
            raise ValueError('Choose at least one positive object ID')
        rgba = np.full((self.pixels[1], self.pixels[0], 4), 255, dtype=np.uint8)
        rgba[:, :, 3] = np.isin(self.to_numpy(), ids).astype(np.uint8) * 255
        return self._diagram(rgba, object_ids=list(ids))
