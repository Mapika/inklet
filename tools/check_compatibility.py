"""Check public call shapes against an inventory captured from a released wheel."""
from pathlib import Path
import argparse
import inspect
import json

ROOT=Path(__file__).resolve().parents[1]


def inventory(module):
    def signature(value):
        try: parameters=inspect.signature(value).parameters.values()
        except (TypeError,ValueError): return None
        return [dict(name=p.name,kind=p.kind.name,required=p.default is inspect.Parameter.empty
                     and p.kind not in (p.VAR_POSITIONAL,p.VAR_KEYWORD)) for p in parameters]
    api={}
    for name in module.__all__:
        value=getattr(module,name)
        if callable(value): api[name]=signature(value)
        if inspect.isclass(value):
            for method,member in inspect.getmembers(value):
                if not method.startswith('_') and (inspect.isfunction(member) or inspect.ismethod(member)):
                    api[name+'.'+method]=signature(member)
    return dict(version=module.__version__,exports=list(module.__all__),api=api)


def differences(old,new):
    problems=[f'{name}: removed export' for name in sorted(set(old['exports'])-set(new['exports']))]
    positional={'POSITIONAL_ONLY','POSITIONAL_OR_KEYWORD'}
    for name,parameters in old['api'].items():
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


def main():
    import inklet
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'tests/fixtures/compatibility/api-3.1.json')
    parser.add_argument('--output',type=Path,default=ROOT/'out/compatibility.json')
    args=parser.parse_args()
    before=json.loads(args.baseline.read_text());after=inventory(inklet)
    problems=differences(before,after)
    report=dict(baseline=before['version'],candidate=after['version'],
        exports=len(before['exports']),callables=len(before['api']),problems=problems,passed=not problems,
        limits='Checks names, parameter kinds, public positional order and required arguments; does not prove semantic, default-value or rendering compatibility.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return int(bool(problems))


if __name__=='__main__': raise SystemExit(main())
