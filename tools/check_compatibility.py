"""Check public call shapes against inventories captured from released wheels.

Inventory keys are namespaced as ``module:Name`` or ``module:Class.method``,
for example ``inklet.experimental.volume:Volume.crop``. Baselines written
before namespacing (``api-3.1.json``) use bare names; they are read as
``inklet:Name``.

``--capture PATH`` writes the inventory of the installed inklet (top-level
``__all__`` plus every public ``inklet.experimental`` module). Run it only
from an isolated installation of a released wheel.
"""
from pathlib import Path
import argparse
import importlib
import inspect
import json
import pkgutil
import sys

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures/compatibility'
BASELINES=(FIXTURES/'api-3.1.json',FIXTURES/'api-4.2.json')
LIMITS=('Checks names, parameter kinds, public positional order and required arguments; '
        'does not prove semantic, default-value or rendering compatibility.')


def signature(value):
    try: parameters=inspect.signature(value).parameters.values()
    except (TypeError,ValueError): return None
    return [dict(name=p.name,kind=p.kind.name,required=p.default is inspect.Parameter.empty
                 and p.kind not in (p.VAR_POSITIONAL,p.VAR_KEYWORD)) for p in parameters]


def experimental_modules(package='inklet.experimental'):
    """Public modules below ``package``; private path components are skipped."""
    root=importlib.import_module(package)
    found=[]
    for info in pkgutil.walk_packages(root.__path__,package+'.'):
        if any(part.startswith('_') for part in info.name.split('.')): continue
        found.append(info.name)
    return sorted(found)


def exported(module,owner=None):
    """``__all__`` when defined, plus public names defined under ``owner``."""
    names=list(getattr(module,'__all__',()))
    if owner:
        for name,value in vars(module).items():
            source=getattr(value,'__module__',None)
            if (not name.startswith('_') and name not in names and isinstance(source,str)
                    and (source==owner or source.startswith(owner+'.'))):
                names.append(name)
    return names


def inventory(modules,owner=None,expect=()):
    """Deprecated aliases are part of the released API; inventory them quietly."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        return _inventory(modules,owner,expect)


def _inventory(modules,owner=None,expect=()):
    """Inventory ``modules`` (module objects or dotted paths).

    ``owner`` adds public names whose ``__module__`` lies under that package,
    for modules without ``__all__``. ``expect`` lists namespaced export keys
    that are resolved with ``getattr`` even when not otherwise listed, so
    lazily aliased names are still found.
    """
    if isinstance(modules,(str,type(sys))): modules=[modules]
    import inklet
    expected={}
    for key in expect:
        path,_,name=key.partition(':');expected.setdefault(path,[]).append(name)
    api,exports,paths,errors={},[],[],{}
    for module in modules:
        # Keys use the requested path: an old path aliased to a moved module
        # (``sys.modules`` entry) still reports under its released name.
        path=module if isinstance(module,str) else module.__name__
        if isinstance(module,str):
            try: module=importlib.import_module(module)
            except Exception as error:
                errors[path]=f'{type(error).__name__}: {error}';continue
        paths.append(path)
        names=exported(module,owner)
        names+=[n for n in expected.get(path,()) if n not in names and hasattr(module,n)]
        for name in names:
            key=f'{path}:{name}';exports.append(key)
            value=getattr(module,name)
            if callable(value): api[key]=signature(value)
            if inspect.isclass(value):
                for method,member in inspect.getmembers(value):
                    if not method.startswith('_') and (inspect.isfunction(member) or inspect.ismethod(member)):
                        api[f'{key}.{method}']=signature(member)
    result=dict(version=inklet.__version__,modules=paths,exports=exports,api=api)
    if errors: result['errors']=errors
    return result


def capture():
    """Released-API inventory: top-level ``__all__`` and experimental modules."""
    top=inventory(['inklet']);rest=inventory(experimental_modules(),owner='inklet.experimental')
    if rest.get('errors'): raise RuntimeError(f'cannot import {rest["errors"]}')
    return dict(version=top['version'],python=sys.version,modules=top['modules']+rest['modules'],
                exports=top['exports']+rest['exports'],api={**top['api'],**rest['api']})


def dump(snapshot):
    """Fixture text: one top-level field or API entry per line, as in api-3.1.json."""
    lines=[]
    for field,value in snapshot.items():
        if field!='api': lines.append(f'  {json.dumps(field)}: {json.dumps(value)}');continue
        entries=[f'    {json.dumps(k)}: {json.dumps(v)}' for k,v in value.items()]
        lines.append('  "api": {\n'+',\n'.join(entries)+'\n  }')
    return '{\n'+',\n'.join(lines)+'\n}\n'


def namespaced(key): return key if ':' in key else 'inklet:'+key


def normalise(snapshot):
    """Read bare-name baselines as ``inklet:`` keys."""
    exports=[namespaced(k) for k in snapshot['exports']]
    modules=snapshot.get('modules') or sorted({k.partition(':')[0] for k in exports})
    return dict(snapshot,modules=list(modules),exports=exports,
                api={namespaced(k):v for k,v in snapshot['api'].items()})


def differences(old,new):
    old,new=normalise(old),normalise(new)
    errors=new.get('errors',{})
    missing={m for m in old['modules'] if m not in new['modules']}
    problems=[f'{m}: module unavailable'+(f' ({errors[m]})' if m in errors else '') for m in sorted(missing)]
    live=lambda key: key.partition(':')[0] not in missing
    problems+=[f'{name}: removed export' for name in sorted(set(old['exports'])-set(new['exports'])) if live(name)]
    positional={'POSITIONAL_ONLY','POSITIONAL_OR_KEYWORD'}
    for name,parameters in old['api'].items():
        if not live(name): continue
        if name not in new['api']:
            problems.append(f'{name}: removed callable');continue
        if parameters is None: continue
        current=new['api'][name]
        if current is None:
            problems.append(f'{name}: signature unavailable');continue
        # Dataclass constructors expose private storage fields; these are not APIs.
        before={p['name']:p for p in parameters if not p['name'].startswith('_')}
        after={p['name']:p for p in current if not p['name'].startswith('_')}
        old_order=[p['name'] for p in before.values() if p['kind'] in positional]
        new_order=[p['name'] for p in after.values() if p['kind'] in positional]
        if new_order[:len(old_order)]!=old_order:
            problems.append(f'{name}: positional arguments changed order')
        for key,p in before.items():
            if key not in after:
                problems.append(f'{name}: removed parameter {key}');continue
            q=after[key]
            allowed={p['kind']}
            if p['kind'] in ('POSITIONAL_ONLY','KEYWORD_ONLY'): allowed.add('POSITIONAL_OR_KEYWORD')
            if q['kind'] not in allowed: problems.append(f'{name}: restricted parameter {key}')
            if not p['required'] and q['required']: problems.append(f'{name}: {key} became required')
        for key,p in after.items():
            if key not in before and p['required']: problems.append(f'{name}: new required parameter {key}')
    return problems


def check(baseline):
    """Compare the importable inklet with one baseline snapshot."""
    before=normalise(baseline)
    # Moved objects report their new stable ``__module__``; accept any inklet owner.
    after=inventory(before['modules'],owner='inklet',expect=before['exports'])
    return after,differences(before,after)


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--baseline',type=Path,action='append',
        help='released inventory to compare with; repeatable (default: api-3.1.json and api-4.2.json)')
    parser.add_argument('--output',type=Path,default=ROOT/'out/compatibility.json')
    parser.add_argument('--capture',type=Path,metavar='PATH',
        help='write the installed release inventory to PATH instead of checking')
    args=parser.parse_args()
    if args.capture:
        snapshot=capture()
        args.capture.parent.mkdir(parents=True,exist_ok=True)
        args.capture.write_text(dump(snapshot))
        print(json.dumps(dict(version=snapshot['version'],modules=len(snapshot['modules']),
            exports=len(snapshot['exports']),callables=len(snapshot['api']))))
        return 0
    results,problems,candidate=[],[],None
    for path in args.baseline or BASELINES:
        before=json.loads(path.read_text());after,found=check(before)
        candidate=after['version']
        results.append(dict(baseline=before['version'],file=path.name,modules=len(normalise(before)['modules']),
            exports=len(before['exports']),callables=len(before['api']),problems=found,passed=not found))
        problems+=[f'[{before["version"]}] {p}' for p in found]
    report=dict(baseline=', '.join(r['baseline'] for r in results),candidate=candidate,
        exports=sum(r['exports'] for r in results),callables=sum(r['callables'] for r in results),
        problems=problems,passed=not problems,baselines=results,limits=LIMITS)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return int(bool(problems))


if __name__=='__main__': raise SystemExit(main())
