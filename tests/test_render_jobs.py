"""Real subprocess cancellation and bounded queue behaviour without Blender."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest
import inklet as i
from inklet.three.render_jobs import run_process, check_cancel, emit


def test_cancellation_stops_a_running_process(tmp_path):
    pidfile=tmp_path/'pid'
    script=('import os,time; from pathlib import Path; '
        f'Path({str(pidfile)!r}).write_text(str(os.getpid())); '
        'print(\'INKLET_EVENT {"phase":"rendering","message":"started"}\',flush=True); time.sleep(60)')
    cancel=threading.Event();events=[]
    def progress(event):events.append(event);cancel.set()
    start=time.monotonic()
    with pytest.raises(i.RenderCancelled):
        run_process([sys.executable,'-c',script],timeout=10,cancel=cancel,progress=progress)
    assert time.monotonic()-start<5
    assert events[0].phase=='rendering'
    if os.name=='posix':
        with pytest.raises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)


def test_timeout_and_callback_failure_stop_processes():
    with pytest.raises(subprocess.TimeoutExpired):
        run_process([sys.executable,'-c','import time; time.sleep(60)'],timeout=.15)
    def broken(event):raise ValueError('callback failed')
    with pytest.raises(ValueError,match='callback failed'):
        run_process([sys.executable,'-c',
            'import time; print(\'INKLET_EVENT {"phase":"rendering","message":"started"}\',flush=True); time.sleep(60)'],
            timeout=5,progress=broken)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux process-group lifecycle inspection')
def test_timeout_stops_descendants_after_parent_has_exited(tmp_path):
    pidfile=tmp_path/'child-pid'
    script=('import subprocess,sys; from pathlib import Path; '
            'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
            f'Path({str(pidfile)!r}).write_text(str(child.pid))')
    with pytest.raises(subprocess.TimeoutExpired):
        run_process([sys.executable,'-c',script],timeout=.5)
    pid=int(pidfile.read_text())
    try:
        os.kill(pid,0)
    except ProcessLookupError:
        return
    # An orphan may briefly remain as a zombie until the system reaps it.
    assert Path(f'/proc/{pid}/stat').read_text().split()[2]=='Z'


def test_queue_limits_gpu_jobs_and_cancels_a_waiting_job(monkeypatch):
    from inklet.three import scenes
    started=threading.Event();release=threading.Event();calls=[]
    def fake(path,*,cancel,progress,**opts):
        calls.append(path);started.set()
        while not release.wait(.01):check_cancel(cancel)
        emit(progress,'complete','ready',1)
        return path
    monkeypatch.setattr(scenes,'render_blend',fake)
    with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
        first=queue.submit('first.blend')
        assert started.wait(2)
        second=queue.submit('second.blend')
        assert second.cancel()
        with pytest.raises(i.RenderCancelled):second.result(2)
        assert calls==['first.blend']
        release.set()
        assert first.result(2)=='first.blend'
        assert first.progress.phase=='complete'
    with pytest.raises(RuntimeError,match='closed'):queue.submit('late.blend')


def test_queue_runs_cpu_jobs_in_parallel_and_shutdown_cancels(monkeypatch):
    from inklet.three import scenes
    barrier=threading.Barrier(3)
    def fake(path,*,cancel,**opts):
        barrier.wait(timeout=2)
        while True:
            check_cancel(cancel);time.sleep(.01)
    monkeypatch.setattr(scenes,'render_blend',fake)
    queue=i.RenderQueue(max_workers=2)
    jobs=[queue.submit(str(n),device='CPU') for n in range(2)]
    barrier.wait(timeout=2)
    queue.shutdown(cancel=True)
    for job in jobs:
        with pytest.raises(i.RenderCancelled):job.result()


def test_process_progress_parses_samples_and_bounds_diagnostic_tail():
    events=[]
    result=run_process([sys.executable,'-c',
        'print("Sample 3/8"); print("x"*5000); [print(n) for n in range(500)]'],timeout=5,progress=events.append)
    assert events[0].fraction==3/8
    assert len(result.stdout.splitlines())<=160
    assert result.stdout.endswith('499')


def test_queued_bindings_are_snapshotted_at_submission(monkeypatch):
    from inklet.three import scenes
    started=threading.Event();release=threading.Event()
    def fake(path,**opts):
        if path=='first':started.set();assert release.wait(2)
        return opts.get('bindings')
    monkeypatch.setattr(scenes,'render_blend',fake)
    with i.RenderQueue(max_workers=1) as queue:
        first=queue.submit('first',device='CPU')
        assert started.wait(2)
        bindings={'Book':{'color':'red'}}
        second=queue.submit('second',device='CPU',bindings=bindings)
        bindings['Book']['color']='blue'
        release.set();first.result(2)
        assert second.result(2)=={'Book':{'color':'red'}}
