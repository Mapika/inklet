"""Portable, hash-verified source inventories; no network or code execution."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re


def name(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonempty string')
    return value


def relative_path(value):
    name(value, 'asset path')
    p = PurePosixPath(value)
    if (p.is_absolute() or p.as_posix() != value or '..' in p.parts
            or '\\' in value or ':' in value or not p.parts or p.parts[0] == '.inklet'):
        raise ValueError('asset paths must be portable relative paths outside .inklet')
    return value


def file_at(root, relative):
    root = Path(root).resolve()
    path = (root / relative_path(relative)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f'missing asset or path outside asset root: {relative}')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@dataclass(frozen=True)
class Asset:
    """One source file with author-supplied provenance and optional physical units."""
    id: str
    path: str
    sha256: str
    size: int
    source: str
    license: str
    role: str = 'data'
    unit: str | None = None

    def __post_init__(self):
        for field in ('id', 'source', 'license', 'role'):
            name(getattr(self, field), field)
        relative_path(self.path)
        if not isinstance(self.sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.sha256):
            raise ValueError('asset sha256 must be a SHA-256 hex digest')
        if type(self.size) is not int or self.size < 0:
            raise ValueError('asset size must be a nonnegative integer')
        if self.unit is not None:
            name(self.unit, 'unit')


@dataclass(frozen=True)
class AssetManifest:
    """Immutable inventory. Capture explicitly chosen files; verify before reuse."""
    assets: tuple[Asset, ...] = ()

    def __post_init__(self):
        items = tuple(self.assets)
        if any(not isinstance(a, Asset) for a in items):
            raise TypeError('manifest entries must be Asset objects')
        for field in ('id', 'path'):
            if len({getattr(a, field) for a in items}) != len(items):
                raise ValueError(f'duplicate asset {field}')
        object.__setattr__(self, 'assets', tuple(sorted(items, key=lambda a: a.id)))

    @classmethod
    def capture(cls, root, entries):
        """Capture dictionaries with id/path/source/license and optional role/unit."""
        items = []
        for entry in entries:
            path = file_at(root, entry['path'])
            items.append(Asset(**entry, size=path.stat().st_size, sha256=digest(path)))
        return cls(tuple(items))

    def verify(self, root):
        """Return verified file paths by asset ID; reject missing or changed bytes."""
        paths = {}
        for asset in self.assets:
            path = file_at(root, asset.path)
            if path.stat().st_size != asset.size or digest(path) != asset.sha256:
                raise ValueError(f'asset changed: {asset.id} ({asset.path})')
            paths[asset.id] = path
        return paths

    def to_dict(self):
        return {'schema': 'inklet.assets/0.1', 'assets': [asdict(a) for a in self.assets]}

    @classmethod
    def from_dict(cls, value):
        if (not isinstance(value, dict) or set(value) != {'schema', 'assets'}
                or value['schema'] != 'inklet.assets/0.1' or not isinstance(value['assets'], list)):
            raise ValueError('unsupported asset manifest')
        return cls(tuple(Asset(**a) for a in value['assets']))
