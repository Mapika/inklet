"""Portable placement decisions for named compositions, separate from content."""
from __future__ import annotations

import math
import re

from .compiler import LayoutError
from .spec import length

SCHEMA = 'inklet.composition-layout/0.2'
LEGACY_SCHEMA = 'inklet.composition-layout/0.1'
_PLACEMENT = {'x', 'y', 'anchor', 'width', 'height', 'scale'}
_PAGE = {'width', 'height', 'unit', 'fit_top'}
_NAME = r'[A-Za-z][A-Za-z0-9_-]*'


def _targets(recipe):
    from .composition import Composition
    result = {'/': (None, None, recipe)}

    def visit(node, path, trail):
        if id(node) in trail: raise LayoutError('cyclic composition layout dependency')
        for part in node._parts:
            key = path + part.name
            result[key] = (node, part, part.item)
            if isinstance(part.item, Composition): visit(part.item, key+'/', trail+(id(node),))
    visit(recipe, '/', ())
    return result


def _expression(value, *, encode=False, depth=0):
    from .composition import LayoutValue
    if depth > 32: raise ValueError('layout expressions support at most 32 nested operations')
    if type(value) in (int,float) and math.isfinite(value): return value
    if encode and isinstance(value, LayoutValue):
        value = {'op':value.operation, 'args':list(value.args)}
    if not isinstance(value,dict) or set(value) != {'op','args'}:
        raise ValueError('layout coordinates need finite numbers or measured expressions')
    op,args = value['op'],value['args']
    if not isinstance(op,str) or not isinstance(args,(list,tuple)):
        raise ValueError('invalid layout expression')
    if op in ('+','-','*','/') and len(args)==2:
        args = [_expression(a,encode=encode,depth=depth+1) for a in args]
    elif op=='page' and len(args)==1 and args[0] in ('width','height'):
        args = list(args)
    elif (op=='measure' and len(args)==2 and isinstance(args[0],str)
          and re.fullmatch(_NAME,args[0]) and args[1] in ('width','height')):
        args = list(args)
    elif (op=='point' and len(args)==3 and isinstance(args[0],str)
          and re.fullmatch(_NAME,args[0]) and isinstance(args[1],str)
          and args[1] and args[2] in ('x','y')):
        args = list(args)
    else: raise ValueError('invalid layout expression operation or arguments')
    return {'op':op,'args':args} if encode else LayoutValue(op,tuple(args))


def _placement(values, *, encode=False):
    result = {}
    if not isinstance(values,dict) or not values or not set(values)<=_PLACEMENT:
        raise ValueError('invalid placement override properties')
    for key,value in values.items():
        if key=='scale':
            from .composition import _scale
            result[key] = _scale(value)
        elif key=='anchor':
            if value is not None and (not isinstance(value,str) or not value):
                raise ValueError('placement anchors must be nonempty strings or null')
            result[key] = value
        elif value is None and key in ('width','height'): result[key] = None
        else:
            if encode and key in ('width','height') and isinstance(value,str):
                value = length(value, f'child {key}')
            result[key] = _expression(value,encode=encode)
            if key in ('width','height') and type(result[key]) in (int,float):
                length(result[key], f'child {key}')
    return result


def _page(values):
    if not isinstance(values,dict) or not values or not set(values)<=_PAGE:
        raise ValueError('invalid composition page override properties')
    result = {}
    for key,value in values.items():
        if key=='fit_top':
            if type(value) is not bool: raise ValueError('fit_top must be a boolean')
            result[key] = value
        else:
            if type(value) not in (int,float): raise ValueError(f'{key} must be a finite positive number')
            result[key] = length(value, f'composition {key}')
    return result


def capture(recipe, reference):
    """Record only changed layout fields; leave unedited source decisions live."""
    from .composition import Composition
    if not isinstance(reference,Composition): raise TypeError('reference must be a Composition')
    current, before = _targets(recipe), _targets(reference)
    if current.keys()!=before.keys():
        raise LayoutError('capture needs matching named composition structure')
    edits = {}
    for path,(_,part,item) in current.items():
        _,old_part,old_item = before[path]
        entry = {}
        if isinstance(item,Composition) != isinstance(old_item,Composition):
            raise LayoutError(f'composition structure changed at {path}')
        if part is not None:
            now = _placement({k:getattr(part,k) for k in sorted(_PLACEMENT)},encode=True)
            old = _placement({k:getattr(old_part,k) for k in sorted(_PLACEMENT)},encode=True)
            changed = {k:v for k,v in now.items() if v!=old[k]}
            if changed: entry['placement'] = changed
        if isinstance(item,Composition):
            now = _page({k:getattr(item,k) for k in sorted(_PAGE)})
            old = _page({k:getattr(old_item,k) for k in sorted(_PAGE)})
            changed = {k:v for k,v in now.items() if v!=old[k]}
            if changed: entry['page'] = changed
        if entry: edits[path] = entry
    return {'schema':SCHEMA,'targets':edits}


def _references(value):
    from .composition import LayoutValue
    if isinstance(value,LayoutValue):
        if value.operation in ('point','measure'): yield value.args[0]
        elif value.operation in ('+','-','*','/'):
            for arg in value.args: yield from _references(arg)


def apply(recipe, value, *, missing='error'):
    """Validate all edits, reconcile stable names, then edit an independent copy."""
    from .composition import Composition
    if missing not in ('error','drop'): raise ValueError('missing policy must be error or drop')
    if (not isinstance(value,dict) or set(value)!={'schema','targets'} or value['schema'] not in (SCHEMA,LEGACY_SCHEMA)
            or not isinstance(value['targets'],dict)):
        raise ValueError('invalid composition layout overrides')
    targets = _targets(recipe)
    prepared, orphaned = {}, []
    for path,entry in value['targets'].items():
        if not isinstance(path,str) or not re.fullmatch(r'/(?:'+_NAME+r'(?:/'+_NAME+r')*)?',path):
            raise ValueError('layout targets require absolute named composition paths')
        if not isinstance(entry,dict) or not entry or not set(entry)<={'placement','page'}:
            raise ValueError(f'invalid layout target properties: {path}')
        options = {}
        if 'placement' in entry:
            options['placement'] = _placement(entry['placement'])
            if value['schema']==LEGACY_SCHEMA and 'scale' in options['placement']:
                raise ValueError('scale requires composition layout schema 0.2')
        if 'page' in entry: options['page'] = _page(entry['page'])
        target = targets.get(path)
        invalid = target is None
        if target is not None:
            parent,part,item = target
            invalid = ('placement' in options and part is None) or ('page' in options and not isinstance(item,Composition))
            if 'placement' in options and parent is not None:
                names = {p.name for p in parent._parts}
                invalid |= any(ref not in names for val in options['placement'].values() for ref in _references(val))
        if invalid: orphaned.append(path)
        else: prepared[path] = options
    orphaned.sort()
    if orphaned and missing=='error': raise LayoutError('orphaned layout targets: '+', '.join(orphaned))
    # One nested definition may occur at several named paths. Contradictory
    # decisions for that shared object must not depend on JSON property order.
    assigned = {}
    for path,options in prepared.items():
        parent,part,item = targets[path]
        for group,fields in options.items():
            owner = (id(item),None) if group=='page' else (id(parent),part.name)
            for key,val in fields.items():
                identity = (*owner,group,key)
                if identity in assigned and assigned[identity]!=val:
                    raise LayoutError(f'conflicting layout overrides for shared definition at {path}')
                assigned[identity] = val
    result = recipe.copy()
    copied = _targets(result)
    for path,options in prepared.items():
        parent,part,item = copied[path]
        if 'page' in options: item.configure(**options['page'])
        if 'placement' in options: parent.place(part.name,**options['placement'])
    return result, {'orphaned_targets':orphaned,'missing_policy':missing}
