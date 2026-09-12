"""Bounded appearance controls for named recipes, preserving data mappings."""
from __future__ import annotations

import math

from .spec import ComponentSpec, PlotSpec
from .module import ModuleSpec

_FIELDS = {
    'plot-line': ('stroke', 'stroke_width', 'opacity'),
    'plot-scatter': ('color', 'size', 'opacity'),
    'plot-text': ('fill', 'size'),
    'plot-annotate': ('fill', 'size'),
    'component-text': ('fill', 'size'),
    'module-text': ('fill', 'size'),
    'module-box': ('fill', 'stroke', 'stroke_width'),
    'composition-annotation': ('fill', 'size'),
}


def targets(item):
    from .. import text
    from ..core import mm
    from .composition import Composition
    found = {}

    def add(key, kind, options, location):
        if not isinstance(key,str) or not key: return
        values = {'kind':kind}
        for field in _FIELDS[kind]:
            value = options.get(field)
            if field=='size' and kind!='plot-scatter':
                value = options.get('font_size') if options.get('font_size') is not None else options.get('size')
            if kind=='plot-scatter' and field=='color' and options.get('ramp') is not None: continue
            if field in ('size','stroke_width') and isinstance(value,str):
                try: value=mm(value)
                except (TypeError,ValueError): continue
            if value is not None:
                if field in ('fill','stroke','color'):
                    if not isinstance(value,str): continue
                elif type(value) not in (int,float) or not math.isfinite(value): continue
            values[field] = value
        if key in found: raise ValueError(f'duplicate editable style key {key!r}')
        found[key] = (values,location)

    if isinstance(item,ModuleSpec):
        add('box','module-box',item.box_style,('module','box_style'))
        if isinstance(item.label,str):add('text','module-text',item.text_style,('module','text_style'))
    elif isinstance(item,ComponentSpec) and item.factory is text:
        add('text','component-text',item.kwargs,('component',))
    elif isinstance(item,PlotSpec):
        for index,(key,method,args,options) in enumerate(item._steps):
            if 'plot-'+method not in _FIELDS: continue
            if method in ('text','annotate'):
                value=args[2] if len(args)>2 else options.get('text' if method=='annotate' else 'content')
                if not isinstance(value,str): continue
            add(key,'plot-'+method,options,('plot',index))
    elif isinstance(item,Composition):
        for index,(_,value,options) in enumerate(item._annotations):
            if isinstance(value,str):add(options.get('name'),'composition-annotation',options,('annotation',index))
    return found


def validate(value):
    if not isinstance(value,dict) or not value:raise ValueError('styles must be a nonempty object')
    result={}
    for key,fields in value.items():
        if not isinstance(key,str) or not key or not isinstance(fields,dict):
            raise ValueError('styles require nonempty string keys and field objects')
        kind=fields.get('kind')
        if not isinstance(kind,str) or kind not in _FIELDS or len(fields)<2 or not set(fields)<={'kind',*_FIELDS[kind]}:
            raise ValueError('invalid style kind or fields')
        for name,val in fields.items():
            if name=='kind' or val is None:continue
            if name in ('fill','stroke','color'):
                from ..themes.color import parse_color
                if not isinstance(val,str):raise ValueError('style colours must be strings')
                if not (val=='none' and name!='color'):parse_color(val)
            else:
                if type(val) not in (int,float) or not math.isfinite(val):raise ValueError('style dimensions must be finite numbers')
                if name=='opacity':valid=0<=val<=1
                elif name=='stroke_width':valid=val>=0
                else:valid=val>0
                if not valid:raise ValueError('style dimension or opacity outside its valid range')
        result[key]=dict(fields)
    return result


def apply(item,edits):
    available=targets(item)
    for key,fields in edits.items():
        _,location=available[key]
        changes={k:v for k,v in fields.items() if k!='kind'}
        def merged(options):
            result=dict(options)
            if 'size' in changes and fields['kind']!='plot-scatter':result.pop('font_size',None)
            for key,val in changes.items():
                if val is None:result.pop(key,None)
                else:result[key]=val
            return result
        if location[0]=='module':item.configure(**{location[1]:merged(getattr(item,location[1]))})
        elif location[0]=='component':item.kwargs=merged(item.kwargs)
        elif location[0]=='plot':
            index=location[1];found,method,args,kwargs=item._steps[index]
            item._steps[index]=(found,method,args,merged(kwargs))
        else:
            index=location[1];target,text,options=item._annotations[index]
            item._annotations[index]=(target,text,merged(options))
