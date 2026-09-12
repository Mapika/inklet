"""Explicit text targets within named recipes; never infer identity from ink."""
from __future__ import annotations

import math

from .spec import ComponentSpec, PlotSpec
from .module import ModuleSpec


def targets(item):
    """Return keyed, typed label controls and internal replacement locations."""
    from .. import text
    from .composition import Composition
    found = {}

    def add(key, kind, value, location, options=None):
        if not isinstance(key, str) or not key or not isinstance(value, str): return
        if key in found: raise ValueError(f'duplicate editable label key {key!r}')
        fields = dict(kind=kind, text=value)
        if options is not None:
            from ..core import mm
            clear = options.get('clear')
            fields.update(side=options.get('side', 'n'), leader=options.get('leader', True))
            # A measured clearance remains authored until explicitly replaced.
            from .composition import LayoutValue
            if not isinstance(clear, LayoutValue): fields['clear'] = None if clear is None else mm(clear)
        found[key] = (fields, location)

    if isinstance(item, ModuleSpec): add('label', 'module-label', item.label, ('module',))
    elif isinstance(item, ComponentSpec) and item.factory is text:
        add('text', 'component-text', item.args[0] if item.args else item.kwargs.get('content'), ('component',))
    elif isinstance(item, PlotSpec):
        for index, (key, method, args, options) in enumerate(item._steps):
            if method not in ('title', 'text', 'annotate'): continue
            position = 0 if method == 'title' else 2
            keyword = 'text' if method == 'annotate' else 'content'
            value = args[position] if len(args)>position else options.get(keyword)
            add(key, 'plot-'+method, value, ('plot', index, position, keyword),
                options if method == 'annotate' else None)
    elif isinstance(item, Composition):
        for index, (_, value, options) in enumerate(item._annotations):
            add(options.get('name'), 'composition-annotation', value, ('annotation', index),
                {'clear':2, **options})
    return found


def validate(value):
    if not isinstance(value, dict) or not value: raise ValueError('labels must be a nonempty object')
    result = {}
    for key, fields in value.items():
        if not isinstance(key, str) or not key or not isinstance(fields, dict):
            raise ValueError('labels require nonempty string keys and field objects')
        kind = fields.get('kind')
        allowed = {'kind', 'text'}
        if kind in ('plot-annotate', 'composition-annotation'): allowed |= {'side', 'clear', 'leader'}
        if (kind not in ('module-label','component-text','plot-title','plot-text','plot-annotate','composition-annotation')
                or not set(fields)<=allowed or len(fields)<2):
            raise ValueError('invalid label kind or fields')
        for name, val in fields.items():
            if name=='text' and not isinstance(val, str): raise ValueError('label text must be a string')
            if name=='side' and val not in ('n','ne','e','se','s','sw','w','nw'):
                raise ValueError('invalid annotation side')
            if name=='leader' and type(val) is not bool: raise ValueError('label leader must be a boolean')
            if name=='clear' and not (val is None and kind=='plot-annotate'):
                if type(val) not in (int,float) or not math.isfinite(val) or val<0:
                    raise ValueError('label clearance must be finite nonnegative millimetres')
        result[key] = dict(fields)
    return result


def apply(item, edits):
    available = targets(item)
    for key, fields in edits.items():
        current, location = available[key]
        changes = {k:v for k,v in fields.items() if k!='kind'}
        value = changes.pop('text', current['text'])
        if location[0]=='module': item.configure(value)
        elif location[0]=='component':
            if item.args: item.args = (value, *item.args[1:])
            else: item.kwargs['content'] = value
        elif location[0]=='plot':
            _, index, position, keyword = location
            found, method, args, kwargs = item._steps[index]
            args, kwargs = list(args), dict(kwargs)
            if len(args)>position: args[position] = value
            else: kwargs[keyword] = value
            item._steps[index] = (found, method, tuple(args), kwargs | changes)
        else:
            _, index = location
            target, _, options = item._annotations[index]
            item._annotations[index] = (target, value, options | changes)
