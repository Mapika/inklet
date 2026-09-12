"""Saved native 3D camera choices without replacing source geometry."""
from dataclasses import replace
import math

from .spec import ComponentSpec
from ..three.camera import as_camera

_FIELDS = {'azimuth', 'elevation', 'roll', 'perspective'}


def targets(item):
    from .. import model, solid
    if not isinstance(item, ComponentSpec) or item.factory not in (model, solid):
        return {}
    if item.kwargs.get('backend', 'builtin') != 'builtin':
        return {}
    camera = as_camera(item.kwargs.get('view'))
    # Explicit look-at cameras retain their eye, target and up vector. Angle
    # fields would be ignored by that camera and must not appear editable.
    fields = _FIELDS if camera.eye is None else _FIELDS - {'azimuth', 'elevation'}
    kind = 'native-orbit' if camera.eye is None else 'native-look-at'
    return {'view': ({'kind': kind, **{key: getattr(camera, key) for key in sorted(fields)}}, camera)}


def validate(value):
    if not isinstance(value, dict) or not value:
        raise ValueError('cameras must be a nonempty object')
    result = {}
    for key, fields in value.items():
        if key != 'view' or not isinstance(fields, dict):
            raise ValueError('camera choices require a view field object')
        kind = fields.get('kind')
        allowed = _FIELDS if kind == 'native-orbit' else _FIELDS - {'azimuth', 'elevation'}
        if kind not in ('native-orbit', 'native-look-at') or len(fields) < 2 or not set(fields) <= {'kind', *allowed}:
            raise ValueError('invalid camera kind or fields')
        for name, val in fields.items():
            if name == 'kind':
                continue
            if name == 'perspective':
                if type(val) is not bool:
                    raise ValueError('camera perspective must be a boolean')
            elif type(val) not in (int, float) or not math.isfinite(val):
                raise ValueError('camera angles must be finite numbers')
            elif name == 'elevation' and not -90 <= val <= 90:
                raise ValueError('camera elevation must be between -90 and 90 degrees')
        result[key] = dict(fields)
    return result


def apply(item, edits):
    camera = as_camera(item.kwargs.get('view'))
    changes = {key: val for key, val in edits['view'].items() if key != 'kind'}
    item.kwargs = {**item.kwargs, 'view': replace(camera, **changes)}
