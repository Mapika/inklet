"""Complete .blend scenes as physically sized, annotated figure layers."""
from dataclasses import dataclass, field
import glob
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from ..assets.cache import cache_root
from ..core import Diagram, ImagePrim, Vec2
from ..document.spec import BuildSpec, fingerprint, length, materialize
from ..themes.color import parse_color

PIPELINE_VERSION = 1
_WORKER = Path(__file__).with_name('blender')/'scene_worker.py'


def _error(message):
    from .blender.discover import BlenderError
    return BlenderError(message)


def _hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _vector(value, label):
    if isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError(f'{label} requires three finite coordinates')
    result = [float(v) for v in value]
    if not all(math.isfinite(v) for v in result):
        raise ValueError(f'{label} requires three finite coordinates')
    return result


def _bindings(values):
    result = {}
    for name, properties in values.items():
        normalized = {}
        for key, value in properties.items():
            if key in ('location', 'rotation_euler', 'scale'):
                normalized[key] = _vector(value, key)
            elif key == 'hide_render':
                if not isinstance(value, bool): raise ValueError('hide_render must be a boolean')
                normalized[key] = value
            elif key == 'color':
                rgb = [channel/255 for channel in parse_color(value)]
                normalized[key] = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]+[1.]
            else:
                raise ValueError(f'Unsupported scene binding {key!r}; use color, location, rotation_euler, scale or hide_render')
        result[str(name)] = normalized
    return result


def _landmarks(values):
    result = {}
    for name, target in values.items():
        if not isinstance(name, str) or not name: raise ValueError('Landmark names must be non-empty strings')
        if isinstance(target, str):
            result[name] = target
        elif isinstance(target, dict):
            if set(target) != {'object', 'point'} or not isinstance(target['object'], str):
                raise ValueError('Local landmarks require object and point')
            result[name] = dict(object=target['object'], point=_vector(target['point'], name))
        else:
            result[name] = _vector(target, name)
    return result


def _dependencies(paths):
    files = set()
    for value in paths:
        path = str(value)
        if '<UDIM>' in path: path = path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')
        matches = glob.glob(path) if glob.has_magic(path) else [path]
        if not matches:
            raise _error(f'Missing scene asset: {value}')
        for match in matches:
            file = Path(match).expanduser().resolve()
            if not file.is_file(): raise _error(f'Missing scene asset: {file}')
            files.add(str(file))
    return [dict(path=path, sha256=_hash(path)) for path in sorted(files)]


def _valid(record):
    try:
        return all(_hash(item['path']) == item['sha256'] for item in record['dependencies'])
    except (OSError, KeyError, TypeError):
        return False


def _cached(directory):
    try:
        record = json.loads((directory/'manifest.json').read_text())
        if _valid(record) and _hash(directory/'image.png') == record['image_sha256']:
            return record
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


@dataclass(frozen=True)
class SceneRender:
    """A rendered snapshot, its provenance and whether cached pixels were reused."""
    diagram: Diagram
    metadata: dict
    cache_hit: bool


def render_blend(path, *, width, height=None, camera=None, scene=None, frame=None,
                 dpi=150, engine=None, samples=32, seed=0, transparent=True,
                 landmarks=None, objects=None, collections=None, bindings=None,
                 assets=(), cache=None, blender=None, timeout=300, threads=4,
                 max_pixels=40_000_000):
    """Render an existing .blend file without modifying it.

    Preserve authored cameras, materials, lights and colour management. Choose
    a camera by name; omit height to preserve the authored resolution aspect.
    Landmarks accept object names, world XYZ or {object, point} local XYZ.
    Bindings explicitly override object color, location, rotation_euler, scale
    or hide_render. Include extra simulation/sequence files in assets.

    Blender is a subprocess with automatic Python execution disabled. The
    compositor and sequencer are bypassed; their file-output nodes are not run.
    Cycles uses CPU, a fixed seed and the requested sample count. Reproducibility
    across different Blender builds or hardware is not guaranteed.
    """
    from .blender.discover import find_blender
    source = Path(path).expanduser().resolve()
    if source.suffix.lower() != '.blend' or not source.is_file():
        raise ValueError(f'Expected an existing .blend file: {source}')
    width = length(width, 'scene width')
    height = None if height is None else length(height, 'scene height')
    dpi = length(dpi, 'scene dpi')
    timeout = length(timeout, 'scene timeout')
    for key, value, minimum in (('samples', samples, 1), ('seed', seed, 0),
                                ('threads', threads, 1), ('max_pixels', max_pixels, 1)):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f'{key} must be an integer >= {minimum}')
    if frame is not None and (isinstance(frame, bool) or not isinstance(frame, int)):
        raise ValueError('frame must be an integer')
    if engine not in (None, 'CYCLES', 'BLENDER_EEVEE_NEXT'):
        raise ValueError('engine must be CYCLES or BLENDER_EEVEE_NEXT')
    if not isinstance(transparent, bool): raise ValueError('transparent must be a boolean')
    for key, names in (('objects', objects), ('collections', collections)):
        if isinstance(names, str): raise ValueError(f'{key} must be a sequence of names')
        if names is not None and any(not isinstance(name, str) for name in names):
            raise ValueError(f'{key} must be a sequence of names')
    binary = find_blender(blender)
    request = dict(width=width, height=height, camera=camera, scene=scene, frame=frame,
        dpi=dpi, engine=engine, samples=samples, seed=seed, transparent=transparent,
        landmarks=_landmarks(landmarks or {}), objects=objects, collections=collections,
        bindings=_bindings(bindings or {}), threads=threads, max_pixels=max_pixels)
    inputs = _dependencies([source, *assets])
    key_data = dict(pipeline=PIPELINE_VERSION, worker=_hash(_WORKER),
                    blender=dict(path=str(binary.path), version=binary.release),
                    inputs=inputs, request=request)
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    directory = cache_root(cache)/'scenes'/key
    record = _cached(directory)
    data = None
    if record is not None:
        try:
            data=(directory/'image.png').read_bytes()
            if hashlib.sha256(data).hexdigest()!=record['image_sha256']:record=None
        except OSError:record=None
    hit = record is not None
    if record is None:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.render-', dir=directory) as scratch:
            stage = Path(scratch)
            (stage/'request.json').write_text(json.dumps(request | {'output': str(stage)}))
            command = [str(binary.path), '--factory-startup', '--disable-autoexec',
                       '--background', str(source), '--python-exit-code', '1',
                       '--python', str(_WORKER), '--', str(stage/'request.json')]
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                raise _error(f'Scene render exceeded {timeout:g} seconds') from None
            if process.returncode or not (stage/'scene.json').is_file():
                raise _error('Blender scene render failed:\n'+(process.stdout+process.stderr)[-5000:])
            record = json.loads((stage/'scene.json').read_text())
            record['dependencies'] = _dependencies([source, *assets, *record['dependencies']])
            if any(_hash(path) != digest for path,digest in record.pop('dependency_hashes').items()):
                raise _error('Scene asset changed during rendering; rebuild the figure')
            if any(_hash(item['path']) != item['sha256'] for item in inputs):
                raise _error('Scene input changed during rendering; rebuild the figure')
            record.update(source=str(source), cache_key=key, request=request,
                          image_sha256=_hash(stage/'image.png'))
            data=(stage/'image.png').read_bytes()
            # Commit pixels first and the validating manifest last. Each render
            # owns its staging directory, including concurrent identical requests.
            (stage/'image.png').replace(directory/'image.png')
            manifest = stage/'manifest.json'
            manifest.write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
            manifest.replace(directory/'manifest.json')
    diagram = Diagram(prim=ImagePrim('blender-scene:'+record['image_sha256'],
        record['width_mm'], record['height_mm'], tuple(record['pixels']), data=data),
        kind='blender-scene', notes={'scene_render': record})
    for name, point in record['landmarks'].items():
        diagram.anchor(name, Vec2(point['x_mm']-record['width_mm']/2,
                                 point['y_mm']-record['height_mm']/2))
    return SceneRender(diagram, record, hit)


def blend_scene(path, **options):
    """A complete Blender scene as a Diagram; see render_blend for options."""
    return render_blend(path, **options).diagram


@dataclass(eq=False)
class BlendSceneSpec(BuildSpec):
    """Deferred scene rendering with file and live-data cache invalidation."""
    path: object
    options: dict = field(default_factory=dict)
    _dependencies: tuple = field(default=(), repr=False)

    def signature(self, trail=()):
        paths = [Path(self.path).expanduser().resolve(), *self.options.get('assets', ()), *self._dependencies]
        dependencies = tuple((str(path), _hash(path) if Path(path).is_file() else None) for path in paths)
        return ('blend-scene', dependencies, fingerprint(self.options, trail))

    def render(self, context, width=None, height=None):
        options = materialize(self.options, context)
        options = dict(options)
        if width is not None: options['width'] = width
        # Auto-height discovery passes None; fixed pages specify a cell height.
        if height is not None: options['height'] = height
        result = render_blend(self.path, **options)
        self._dependencies = tuple(d['path'] for d in result.metadata['dependencies'])
        return result.diagram


def blend_scene_spec(path, **options):
    """Create a live scene panel that responds to asset and data changes."""
    return BlendSceneSpec(path, options)
