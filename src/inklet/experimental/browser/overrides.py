"""Versioned visual decisions for named plot definitions, separate from data state."""
import copy
import math
import re

SCHEMA = 'inklet.visual-overrides/0.1'


def targets(figure):
    from . import ScatterView, LineView, BarView, IntervalView, ECDFView, SeriesView, FacetView
    result = {}
    for definition in figure._views:
        view = definition.view if isinstance(definition, FacetView) else definition
        if type(view) not in (ScatterView, LineView, BarView, IntervalView, ECDFView, SeriesView):
            continue
        defaults = {'color': view.color}
        for prop in ('radius_mm', 'line_width_mm'):
            if hasattr(view, prop) and not (isinstance(view, ECDFView) and prop == 'line_width_mm'):
                defaults[prop] = getattr(view, prop)
        names = ([f'{view.name}__facet_{n}' for n in range(len(definition.values))]
                 if isinstance(definition, FacetView) else [view.name])
        result[view.name] = dict(kind=('FacetView/' if isinstance(definition, FacetView) else '')+
                                type(view).__name__, layers=names, defaults=defaults)
    return result


def validate_shape(value, table):
    if (not isinstance(value, dict) or set(value) != {'schema', 'table', 'targets'} or
            value['schema'] != SCHEMA or value['table'] != table or not isinstance(value['targets'], dict)):
        raise ValueError('invalid visual overrides or different table')
    if len(value['targets']) > 12:
        raise ValueError('at most twelve override targets are supported')
    for name, edits in value['targets'].items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
            raise ValueError('override targets require stable view names')
        if (not isinstance(edits, dict) or not isinstance(edits.get('kind'), str) or
                not set(edits) <= {'kind', 'color', 'radius_mm', 'line_width_mm'} or len(edits) < 2):
            raise ValueError(f'invalid override properties: {name}')
        for key, val in edits.items():
            if key == 'kind':
                continue
            if key == 'color':
                valid = isinstance(val, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', val)
            else:
                valid = type(val) in (int, float) and math.isfinite(val) and 0 < val <= 10
            if not valid:
                raise ValueError(f'invalid override {name}.{key}')
    return copy.deepcopy(value)


def reconcile(value, table, descriptors, missing='error'):
    if missing not in ('error', 'drop'):
        raise ValueError('override missing policy must be error or drop')
    value = validate_shape(value, table)
    orphaned = []
    for name, edits in value['targets'].items():
        target = descriptors.get(name)
        if (target is None or target['kind'] != edits['kind'] or
                not (set(edits)-{'kind'}) <= set(target['defaults'])):
            orphaned.append(name)
    orphaned.sort()
    if orphaned and missing == 'error':
        raise ValueError('orphaned visual overrides: '+', '.join(orphaned))
    for name in orphaned:
        del value['targets'][name]
    return value, dict(orphaned_targets=orphaned, missing_policy=missing)


def rebase_overrides(value, figure, *, missing='error'):
    """Retain compatible named edits; reject or explicitly report removed targets."""
    return reconcile(value, figure.table.name, targets(figure), missing)


def apply_overrides(payload, value, descriptors):
    value, _ = reconcile(value, payload['table'], descriptors)
    result = copy.deepcopy(payload)
    for name, edits in value['targets'].items():
        for layer in result['layers']:
            if layer['name'] not in descriptors[name]['layers']:
                continue
            if 'color' in edits:
                layer['color'] = edits['color']
            if 'radius_mm' in edits and 'radius' in layer:
                layer['radius'] = edits['radius_mm']
            for mark in layer.get('marks', []):
                if mark.get('reference'):
                    continue
                if 'color' in edits:
                    mark['color'] = edits['color']
                if mark['kind'] == 'circle' and 'radius_mm' in edits:
                    mark['geometry'][2] = edits['radius_mm']
                if mark['kind'] == 'line' and 'line_width_mm' in edits:
                    if 'selected_width' in mark:
                        mark['selected_width'] += edits['line_width_mm']-mark['width']
                    mark['width'] = edits['line_width_mm']
    return result
