"""Inspect the devices exposed by this Blender build, without saving preferences."""
import json
from pathlib import Path
import platform
import sys
import bpy


def inventory():
    preferences=bpy.context.preferences.addons['cycles'].preferences
    backends={}
    supported={item[0] for item in preferences.get_device_types(bpy.context)}
    for backend in ('OPTIX','CUDA','HIP','ONEAPI','METAL'):
        devices=[];error=None
        if backend in supported:
            try:
                preferences.compute_device_type=backend
                found=preferences.get_devices_for_type(backend)
                devices=[dict(id=d.id,name=d.name) for d in found if d.type==backend]
            except Exception as exc:
                error=str(exc)
        backends[backend]=dict(supported=backend in supported,devices=devices,error=error)
    return dict(blender=bpy.app.version_string,backends=backends,
                host=dict(system=platform.system(),machine=platform.machine(),processor=platform.processor()))


if __name__=='__main__':
    Path(sys.argv[-1]).write_text(json.dumps(inventory(),indent=2))
