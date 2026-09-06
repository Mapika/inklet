"""Cancellable render processes and bounded, explicitly scheduled scene jobs."""
from collections import deque
import copy
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
import queue
import re
import signal
import subprocess
import threading
import time


class RenderCancelled(CancelledError):
    """Rendering was cancelled before a complete snapshot was committed."""


@dataclass(frozen=True)
class RenderProgress:
    """One render update; fraction is optional and refers to the current phase."""
    phase: str
    message: str
    fraction: float | None = None


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise RenderCancelled('Scene render cancelled')


def emit(callback, phase, message, fraction=None):
    if callback is not None:
        callback(RenderProgress(phase, message, fraction))


def _stop(process):
    if os.name == 'posix':
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: return
    else:
        if process.poll() is not None: return
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name != 'posix': process.kill()
    finally:
        if os.name == 'posix':
            # A parent can exit while a compiler child still owns the log pipe.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        process.wait()


def run_process(command, *, timeout, cancel=None, progress=None):
    """Drain output while polling cancellation; retain a bounded diagnostic tail."""
    check_cancel(cancel)
    start=time.monotonic()
    process=subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors='replace', bufsize=1, start_new_session=os.name=='posix')
    lines=queue.Queue(maxsize=256)
    stopping=threading.Event()

    def read():
        try:
            for line in process.stdout:
                while not stopping.is_set():
                    try: lines.put(line.rstrip(), timeout=.1); break
                    except queue.Full: pass
                if stopping.is_set(): break
        finally:
            process.stdout.close()

    reader=threading.Thread(target=read, daemon=True)
    reader.start();tail=deque(maxlen=160)
    try:
        while process.poll() is None or reader.is_alive() or not lines.empty():
            check_cancel(cancel)
            if time.monotonic()-start >= timeout:
                raise subprocess.TimeoutExpired(command, timeout)
            try: line=lines.get(timeout=.05)
            except queue.Empty: continue
            tail.append(line[-2000:])
            if line.startswith('INKLET_EVENT '):
                event=json.loads(line[len('INKLET_EVENT '):])
                emit(progress, event['phase'], event['message'], event.get('fraction'))
            elif match := re.search(r'(?:Sample|Rendered)\s+(\d+)\s*/\s*(\d+)', line):
                current,total=map(int,match.groups())
                emit(progress, 'rendering', line, min(current/total,1) if total else None)
            elif 'Loading render kernels' in line or 'Loading denoising kernels' in line:
                emit(progress,'kernels',line)
        check_cancel(cancel)
        return subprocess.CompletedProcess(command, process.wait(), '\n'.join(tail), '')
    finally:
        stopping.set()
        _stop(process)
        reader.join(timeout=3)


class RenderJob:
    """A queued or running scene render with cancellation and its latest update."""
    def __init__(self):
        self._cancel=threading.Event()
        self._future=None
        self._progress=RenderProgress('queued', 'Waiting for a render worker')
        self._lock=threading.Lock()

    @property
    def progress(self):
        """Return the latest immutable progress update."""
        with self._lock: return self._progress

    def cancel(self):
        """Request cancellation, including for running Blender processes."""
        if self._future.done(): return False
        self._cancel.set()
        if self._future.cancel():
            with self._lock: self._progress=RenderProgress('cancelled','Scene render cancelled')
        return True

    def done(self):
        return self._future.done()

    def result(self, timeout=None):
        """Wait for a SceneRender; timeout only limits this wait, not the render."""
        try: return self._future.result(timeout)
        except CancelledError:
            raise RenderCancelled('Scene render cancelled') from None


class RenderQueue:
    """Schedule scene renders with worker and GPU concurrency limits.

    Limits apply to this queue. GPU jobs use at most max_gpu_jobs slots;
    each Blender process still uses its own render_blend threads setting.
    Context exit waits for jobs, cancelling them if the block raised an error.
    """
    def __init__(self, max_workers=2, *, max_gpu_jobs=1):
        for name,value in (('max_workers',max_workers),('max_gpu_jobs',max_gpu_jobs)):
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        self._executor=ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='inklet-render')
        self._gpu=threading.BoundedSemaphore(max_gpu_jobs)
        self._jobs=set();self._lock=threading.Lock();self._closed=False

    def submit(self, path, **options):
        """Queue render_blend arguments and return a cancellable RenderJob."""
        if 'cancel' in options:
            raise ValueError('Use job.cancel() for queued renders')
        callback=options.pop('progress',None)
        if callback is not None and not callable(callback):
            raise TypeError('progress must be callable')
        options=copy.deepcopy(options)
        job=RenderJob()

        def report(event):
            with job._lock: job._progress=event
            if callback: callback(event)

        def run():
            from .scenes import render_blend
            acquired=False
            try:
                if str(options.get('device','AUTO')).upper() != 'CPU':
                    emit(report,'waiting','Waiting for a GPU render slot')
                    while not acquired:
                        check_cancel(job._cancel)
                        acquired=self._gpu.acquire(timeout=.05)
                check_cancel(job._cancel)
                return render_blend(path,**options,progress=report,cancel=job._cancel)
            except RenderCancelled:
                with job._lock: job._progress=RenderProgress('cancelled','Scene render cancelled')
                raise
            except BaseException as error:
                with job._lock: job._progress=RenderProgress('failed',str(error))
                raise
            finally:
                if acquired: self._gpu.release()

        with self._lock:
            if self._closed: raise RuntimeError('Render queue is closed')
            job._future=self._executor.submit(run)
            self._jobs.add(job)
        def forget(future):
            with self._lock: self._jobs.discard(job)
        job._future.add_done_callback(forget)
        return job

    def shutdown(self, *, wait=True, cancel=False):
        """Stop accepting jobs; optionally cancel pending and running renders."""
        with self._lock:
            self._closed=True; jobs=tuple(self._jobs)
        if cancel:
            for job in jobs: job.cancel()
        self._executor.shutdown(wait=wait)

    def __enter__(self): return self

    def __exit__(self, kind, value, traceback):
        self.shutdown(cancel=kind is not None)
