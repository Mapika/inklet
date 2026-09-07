"""Packaged, parameterised starter scenes authored by an optional Blender process."""
from collections.abc import Mapping
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .render_jobs import check_cancel, run_process

_CATALOG = Path(__file__).with_name('templates.json')
_WORKER = Path(__file__).with_name('blender')/'template_worker.py'


def scene_templates():
    """Return a fresh JSON-compatible catalogue; Blender is not required.

    Entries describe parameter defaults/ranges, camera names, landmark objects,
    template revisions and the authored conversion from scene units to metres.
    """
    return json.loads(_CATALOG.read_text(encoding='utf-8'))


def _parameters(template, supplied):
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, Mapping):
        raise ValueError('parameters must be a mapping of named template parameters')
    schema = template['parameters']
    unknown = set(supplied)-set(schema)
    if unknown:
        raise ValueError('Unknown scene parameters: '+', '.join(sorted(map(str, unknown))))
    result = {}
    for name, spec in schema.items():
        value = supplied.get(name, spec['default'])
        if spec.get('type') == 'color':
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError(f'{name} must be a #RRGGBB colour')
            value = value.lower()
        else:
            if isinstance(value, (bool, str, bytes)):
                raise ValueError(f'{name} must be a number from {spec["min"]} to {spec["max"]}')
            try:
                value = float(value)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f'{name} must be a finite number') from None
            if not math.isfinite(value) or not spec['min'] <= value <= spec['max']:
                raise ValueError(f'{name} must be from {spec["min"]} to {spec["max"]}')
        result[name] = value
    return result


def create_scene(template, path, *, parameters=None, blender=None, overwrite=False,
                 timeout=90, progress=None, cancel=None):
    """Create an editable .blend from laboratory, product or architecture.

    Geometry, lights, named cameras and landmark empties are included in the
    installed package. Creation does not render pixels or download assets.
    Existing files are preserved unless overwrite=True. A complete file is
    committed atomically; failures and cancellation leave the destination intact.
    Returns an absolute Path. Use render_blend() to render the authored scene.
    """
    catalog = scene_templates()
    if not isinstance(template, str) or template not in catalog:
        raise ValueError('template must be one of '+', '.join(catalog))
    definition = catalog[template]
    resolved = _parameters(definition, parameters)
    destination = Path(path).expanduser().absolute()
    if destination.suffix.lower() != '.blend':
        raise ValueError('Scene output must have a .blend extension')
    if type(overwrite) is not bool:
        raise ValueError('overwrite must be a boolean')
    timeout = float(timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if progress is not None and not callable(progress):
        raise TypeError('progress must be callable')
    if os.path.lexists(destination) and not overwrite:
        raise FileExistsError(f'{destination} already exists; choose a new path or overwrite=True')
    check_cancel(cancel)
    from .blender.discover import BlenderError, find_blender
    binary = find_blender(blender)
    provenance = dict(name=template, revision=definition['revision'], parameters=resolved,
        unit=definition['unit'], metres_per_unit=definition['metres_per_unit'],
        cameras=definition['cameras'], landmarks=definition['landmarks'],
        generator_sha256=hashlib.sha256(_WORKER.read_bytes()).hexdigest(),
        catalog_sha256=hashlib.sha256(_CATALOG.read_bytes()).hexdigest(),
        license='MIT', geometry='Original Inklet procedural geometry')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.inklet-scene-', dir=destination.parent) as tmp:
        stage = Path(tmp)
        output = stage/'scene.blend'
        request = stage/'request.json'
        request.write_text(json.dumps(dict(template=provenance, output=str(output))), encoding='utf-8')
        process = run_process([str(binary.path), '--background', '--factory-startup',
            '--disable-autoexec', '--threads', '4', '--python-exit-code', '1',
            '--python', str(_WORKER), '--', str(request)],
            timeout=timeout, progress=progress, cancel=cancel)
        if process.returncode or not output.is_file():
            raise BlenderError('Scene template creation failed:\n'+process.stdout[-6000:])
        with output.open('rb') as stream:
            if stream.read(7) != b'BLENDER':
                raise BlenderError('Scene template did not produce an uncompressed Blender file')
        check_cancel(cancel)
        if overwrite:
            os.replace(output, destination)
        else:
            # The same-filesystem hard link commits without a check/replace race.
            os.link(output, destination)
    return destination
