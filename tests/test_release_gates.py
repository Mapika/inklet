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


@pytest.mark.parametrize('problem', [None, 'case', 'renderer', 'empty', 'regression'])
def test_report_gate_requires_complete_renderer_matrix(problem):
    gate = tool('benchmark_reports')
    cases = [dict(name=name, python_checks=[{'passed': True}], browsers=[
        dict(renderer=renderer, backend=backend, checks=[{'passed': True}])
        for renderer, backend in gate.RENDERERS]) for name in gate.CASES]
    if problem == 'case': cases.pop()
    elif problem == 'renderer': cases[-1]['browsers'].pop()
    elif problem == 'empty': cases[-1]['browsers'][-1]['checks'] = []
    elif problem == 'regression': cases[-1]['browsers'][-1]['checks'][0]['passed'] = False
    if problem in ('case', 'renderer', 'empty'):
        with pytest.raises(ValueError): gate.complete_results(cases)
    else:
        assert gate.complete_results(cases) is (problem is None)


def test_browser_shutdown_releases_descendant_file_handles(tmp_path):
    import os,subprocess,sys,time
    if os.name!='posix': pytest.skip('POSIX process group release gate')
    import fcntl
    gate=tool('benchmark_reports')
    lock=tmp_path/'writer.lock';ready=tmp_path/'ready'
    child="""import fcntl,signal,sys,time
from pathlib import Path
signal.signal(signal.SIGTERM,signal.SIG_IGN)
with open(sys.argv[1],'w') as stream:
 fcntl.flock(stream,fcntl.LOCK_EX)
 Path(sys.argv[2]).touch()
 time.sleep(60)
"""
    parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],*sys.argv[2:]]); time.sleep(60)"
    process=subprocess.Popen([sys.executable,'-c',parent,child,str(lock),str(ready)],start_new_session=True)
    try:
        deadline=time.monotonic()+5
        while not ready.exists() and time.monotonic()<deadline: time.sleep(.01)
        assert ready.exists(),'descendant did not start'
        with lock.open() as stream:
            with pytest.raises(BlockingIOError): fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            gate.stop_browser(process)
            deadline=time.monotonic()+2
            while True:
                try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>=deadline: raise
                    time.sleep(.01)
        assert process.poll() is not None
    finally:
        gate.stop_browser(process)


def test_profile_cleanup_retries_only_transient_writer_races(monkeypatch):
    import errno
    gate=tool('benchmark_reports');remove=gate.shutil.rmtree;calls=[]
    def racing(path):
        calls.append(path)
        if len(calls)==1: raise OSError(errno.ENOTEMPTY,'writer finishing')
        remove(path)
    monkeypatch.setattr(gate.shutil,'rmtree',racing)
    with gate.browser_profile() as profile: Path(profile,'data').write_text('fixture')
    assert len(calls)==2 and not Path(profile).exists()
    def denied(path): raise OSError(errno.EACCES,'permission denied')
    monkeypatch.setattr(gate.shutil,'rmtree',denied)
    profile=None
    try:
        with pytest.raises(OSError,match='permission denied'):
            with gate.browser_profile() as profile: pass
    finally:
        if profile: remove(profile)
