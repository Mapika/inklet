"""Run all reference workflows; release acceptance rejects skips and missing cases."""
from pathlib import Path
import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('test_regional_report', 'test_engineering_report',
           'test_scientific_report', 'test_project_acceptance')


def validate_report(path):
    cases = list(ET.parse(path).getroot().iter('testcase'))
    missing = set(MODULES) - {case.get('classname', '').split('.')[-1] for case in cases}
    rejected = [case.get('name') for case in cases
                if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))]
    if missing or rejected:
        raise ValueError(f'Incomplete acceptance: missing modules={sorted(missing)}, unsuccessful cases={rejected}')
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/acceptance.xml')
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # A stale report must never stand in for this invocation.
    output.unlink(missing_ok=True)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-m', 'acceptance',
        *(str(ROOT/'tests'/f'{name}.py') for name in MODULES), f'--junitxml={output}'], cwd=ROOT)
    if result.returncode:
        return result.returncode
    count = validate_report(output)
    print(f'Acceptance passed: {count} cases across all four reference workflows; no skips.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
