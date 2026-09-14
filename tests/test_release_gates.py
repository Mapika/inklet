"""Release tooling must reject incomplete acceptance and missing performance limits."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('problem', [None, 'skipped', 'failure', 'error', 'missing'])
def test_acceptance_requires_every_workflow_without_skips(tmp_path, problem):
    gate = tool('acceptance')
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite')
    for name in gate.MODULES:
        if problem == 'missing' and name == gate.MODULES[-1]:
            continue
        case = ET.SubElement(suite, 'testcase', classname='tests.'+name, name='workflow')
        if problem in ('skipped', 'failure', 'error') and name == gate.MODULES[-1]:
            ET.SubElement(case, problem)
    path = tmp_path/'report.xml'
    ET.ElementTree(root).write(path)
    if problem:
        with pytest.raises(ValueError, match='Incomplete acceptance'):
            gate.validate_report(path)
    else:
        assert gate.validate_report(path) == 4


def test_project_budget_rejects_regression_and_missing_stage():
    gate = tool('benchmark_project')
    assert gate.check_budgets({'edit': .1}, {'edit': .2})[0]['passed']
    assert not gate.check_budgets({'edit': .3}, {'edit': .2})[0]['passed']
    assert not gate.check_budgets({'edit': float('nan')}, {'edit': .2})[0]['passed']
    with pytest.raises(ValueError, match='match measured stages'):
        gate.check_budgets({'edit': .1, 'reopen': .2}, {'edit': .2})
    for value in (0, -1, True, float('inf'), float('nan')):
        with pytest.raises(ValueError, match='Invalid project budget'):
            gate.check_budgets({'edit': .1}, {'edit': value})
