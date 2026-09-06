"""Explicit Cycles device discovery and selection without importing bpy."""
import copy
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import time

from .render_jobs import check_cancel, emit, run_process

_PROBE=Path(__file__).with_name('blender')/'device_worker.py'
_BACKENDS=('OPTIX','CUDA','HIP','ONEAPI','METAL')
_cache={}
_lock=threading.Lock()


def _inventory(binary, timeout, refresh=False, cancel=None, progress=None):
    visibility=tuple(os.environ.get(name) for name in ('CUDA_VISIBLE_DEVICES','NVIDIA_VISIBLE_DEVICES',
        'HIP_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER','ZE_AFFINITY_MASK'))
    key=(str(binary.path),binary.release,binary.path.stat().st_mtime_ns,visibility)
    with _lock:
        cached=_cache.get(key)
        if not refresh and cached and time.monotonic()-cached[0] < 60:
            return copy.deepcopy(cached[1])
    check_cancel(cancel)
    emit(progress,'discovering','Checking Blender render devices')
    with tempfile.TemporaryDirectory(prefix='inklet-devices-') as scratch:
        output=Path(scratch)/'devices.json'
        command=[str(binary.path),'--factory-startup','--disable-autoexec','--background',
                 '--python-exit-code','1','--python',str(_PROBE),'--',str(output)]
        try: process=run_process(command,timeout=timeout,cancel=cancel)
        except subprocess.TimeoutExpired:
            from .blender.discover import BlenderError
            raise BlenderError(f'Device discovery exceeded {timeout:g} seconds') from None
        if process.returncode or not output.is_file():
            from .blender.discover import BlenderError
            raise BlenderError('Blender device discovery failed:\n'+process.stdout[-5000:])
        inventory=json.loads(output.read_text())
        with _lock:
            _cache[key]=(time.monotonic(),inventory)
            while len(_cache)>16: _cache.pop(next(iter(_cache)))
        return copy.deepcopy(inventory)


def render_devices(*, blender=None, timeout=30, refresh=False):
    """List Cycles backends, device IDs and discovery errors without rendering.

    Availability means Blender enumerated a device, not that a test render
    succeeded. Results are cached for 60 seconds; refresh=True probes again.
    """
    from .blender.discover import find_blender
    from ..document.spec import length
    return _inventory(find_blender(blender),length(timeout,'device discovery timeout'),refresh)


def device_options(device, devices, fallback, binary, *, timeout, cancel=None, progress=None):
    if not isinstance(device,str) or device.upper() not in ('CPU','AUTO',*_BACKENDS):
        raise ValueError('device must be CPU, AUTO, CUDA, OPTIX, HIP, ONEAPI or METAL')
    device=device.upper()
    if fallback not in ('error','cpu'):
        raise ValueError('fallback must be error or cpu')
    if isinstance(devices,str): raise ValueError('devices must be a sequence of device IDs')
    devices=tuple(devices or ())
    if any(not isinstance(item,str) or not item for item in devices) or len(set(devices))!=len(devices):
        raise ValueError('devices must contain unique, non-empty device IDs')
    if devices and device=='CPU': raise ValueError('GPU device IDs cannot be used with CPU')
    cpu=dict(requested=device,backend='CPU',devices=[],fallback_reason=None,
             host=dict(system=platform.system(),machine=platform.machine(),processor=platform.processor()))
    if device=='CPU': return cpu
    from .blender.discover import BlenderError
    try:
        inventory=_inventory(binary,min(timeout,30),cancel=cancel,progress=progress)
    except BlenderError as error:
        if fallback=='error': raise
        cpu['fallback_reason']='GPU discovery failed: '+str(error)
        return cpu
    for backend in (_BACKENDS if device=='AUTO' else (device,)):
        available=inventory['backends'].get(backend,{}).get('devices',[])
        selected=[item for item in available if not devices or item['id'] in devices]
        if selected and (not devices or {item['id'] for item in selected}==set(devices)):
            return dict(requested=device,backend=backend,devices=selected,fallback_reason=None,
                        host=inventory['host'])
    reason=f'No matching {device} GPU devices are available in this Blender installation'
    if fallback=='error':
        from .blender.discover import BlenderError
        raise BlenderError(reason+'; inspect render_devices() or explicitly use fallback="cpu"')
    cpu['fallback_reason']=reason
    return cpu
